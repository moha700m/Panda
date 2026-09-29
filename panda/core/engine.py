"""Background capture, vision and controller passthrough loop."""

from __future__ import annotations

import ctypes
import os
import queue
import threading
import time
from typing import Any

from panda.core.capture import ScreenCapture
from panda.core.config import normalize_settings
from panda.core.controller import ControllerSnapshot, VirtualXbox, XInputReader
from panda.core.drivers import driver_status
from panda.core.vision import DetectionResult, Vision

HOTKEY_CODES = {"HOME": 0x24, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B}


class EngineWorker(threading.Thread):
    """Own all hardware loops outside the GUI thread; publish plain telemetry snapshots."""

    def __init__(self, settings: dict[str, Any], events: queue.Queue):
        super().__init__(name="PandaEngine", daemon=True)
        self._settings = normalize_settings(settings)
        self._settings_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self.events = events
        self.stop_event = threading.Event()
        self._telemetry: dict[str, Any] = self._empty_telemetry()
        self._latest_preview = None

    @staticmethod
    def _empty_telemetry() -> dict[str, Any]:
        return {
            "running": False,
            "capture_status": "Idle",
            "capture_fps": 0.0,
            "controller_connected": False,
            "controller_name": "Not connected",
            "slot": None,
            "virtual_controller": "Offline",
            "vigem_installed": False,
            "hidhide_installed": False,
            "ads": False,
            "active": False,
            "target_found": False,
            "confidence": 0,
            "correction_x": 0,
            "correction_y": 0,
            "inputs": {"LT": 0, "RT": 0, "LX": 0, "LY": 0, "RX": 0, "RY": 0},
            "buttons": {},
            "capture_error": "",
        }

    def update(self, settings: dict[str, Any]) -> None:
        new_settings = normalize_settings(settings)
        with self._settings_lock:
            old_settings = self._settings
            self._settings = new_settings
        if not new_settings["preview_enabled"] or new_settings["capture_monitor"] != old_settings["capture_monitor"]:
            with self._state_lock:
                self._latest_preview = None

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self._telemetry)

    def latest_preview(self):
        with self._state_lock:
            return self._latest_preview

    def stop(self) -> None:
        self.stop_event.set()

    def _set_telemetry(self, data: dict[str, Any]) -> None:
        with self._state_lock:
            self._telemetry = dict(data)
            if data.get("preview_frame") is not None:
                self._latest_preview = (data["preview_frame"], data.get("preview_point"), data.get("preview_box"))
        self.events.put(("telemetry", data))

    def _settings_copy(self) -> dict[str, Any]:
        with self._settings_lock:
            return dict(self._settings)

    @staticmethod
    def _hotkey_pressed(name: str) -> bool:
        if os.name != "nt":
            return False
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(HOTKEY_CODES[name]) & 0x8000)
        except Exception:
            return False

    def _is_active(self, snapshot: ControllerSnapshot, settings: dict[str, Any]) -> bool:
        mode = settings["activation_mode"]
        if mode == "disabled":
            return False
        if mode == "manual_hotkey":
            return self._hotkey_pressed(settings["manual_hotkey"])
        return snapshot.left_trigger >= settings["ads"]

    def run(self) -> None:
        virtual: VirtualXbox | None = None
        capture = ScreenCapture()
        vision = Vision()
        capture_status = "Idle"
        capture_error = ""
        capture_retry_at = 0.0
        capture_count = 0
        capture_started = time.perf_counter()
        next_driver_check = 0.0
        state = {"vigem": False, "hidhide": False}
        measured_capture_fps = 0.0
        last_telemetry_at = 0.0
        last_loop_tick = time.perf_counter()
        last_slot = object()
        reader: XInputReader | None = None
        last_connected = False
        last_active = False
        active_since = 0.0
        target_since = 0.0
        lost_since = 0.0
        last_target_output = (0, 0)
        result = DetectionResult()
        last_detection_at = 0.0
        last_preview_at = 0.0

        try:
            state = driver_status()
            if not state["vigem"]:
                self.events.put(("status", "ViGEmBus is missing; install or repair the driver to start the engine."))
                self.events.put(("fatal", "ViGEmBus is not installed. The application remains available for driver setup and diagnostics."))
                return
            self.events.put(("log", "ViGEmBus detected"))
            virtual = VirtualXbox()
            self.events.put(("log", "Virtual Xbox controller initialized"))
            config = self._settings_copy()
            reader = XInputReader(config["slot"])
            last_slot = config["slot"]
            self.events.put(("status", "Running · waiting for controller"))
            self.events.put(("log", "Engine started"))
            try:
                capture.grab(config)
                capture_status = "Ready"
                self.events.put(("log", f"Capture initialized · Display {config['capture_monitor'] + 1}"))
            except Exception as exc:
                capture_status = "Error"
                capture_error = str(exc)
                capture_retry_at = time.perf_counter() + 2.0
                self.events.put(("capture_error", capture_error))

            while not self.stop_event.is_set():
                config = self._settings_copy()
                now = time.perf_counter()
                if config["slot"] != last_slot:
                    try:
                        reader = XInputReader(config["slot"])
                        last_slot = config["slot"]
                        self.events.put(("log", f"XInput slot changed to {'Auto' if last_slot == -1 else last_slot}"))
                    except Exception as exc:
                        self.events.put(("warning", f"XInput selection failed: {exc}"))
                snapshot = reader.read() if reader else None
                connected = snapshot is not None
                if connected != last_connected:
                    self.events.put(("log", f"Controller {'connected' if connected else 'disconnected'}"))
                    last_connected = connected
                if snapshot is None:
                    if config["enabled"] and config["preview_enabled"]:
                        capture_period = 1.0 / min(int(config["fps"]), int(config["detection_hz"]))
                        make_preview = now - last_preview_at >= 1.0 / int(config["preview_fps"])
                        if now - last_detection_at >= capture_period and now >= capture_retry_at:
                            try:
                                frame = capture.grab(config)
                                capture_status = "Ready"
                                if frame is not None:
                                    try:
                                        result = vision.detect(frame, config, now=now, make_preview=make_preview)
                                        if make_preview and result.preview_frame is None:
                                            result.preview_frame = frame.copy()
                                        capture_error = ""
                                        capture_count += 1
                                        if make_preview:
                                            last_preview_at = now
                                    except Exception as exc:
                                        result = DetectionResult()
                                        capture_error = f"Vision unavailable: {exc}"
                                        capture_status = "Error"
                                        if make_preview:
                                            result.preview_frame = frame.copy()
                                        self.events.put(("capture_error", capture_error))
                                last_detection_at = now
                            except Exception as exc:
                                message = str(exc)
                                if message != capture_error:
                                    capture_error = message
                                    self.events.put(("capture_error", message))
                                capture_status = "Error"
                                capture_retry_at = now + 2.0
                                last_detection_at = now
                    if now - capture_started >= 0.5:
                        measured_capture_fps = capture_count / (now - capture_started)
                        capture_count = 0
                        capture_started = now
                    if now - last_telemetry_at >= 0.2:
                        if now >= next_driver_check:
                            state = driver_status()
                            next_driver_check = now + 10.0
                        data = self._empty_telemetry()
                        data.update({
                            "running": True,
                            "capture_status": capture_status,
                            "capture_error": capture_error,
                            "capture_fps": measured_capture_fps,
                            "virtual_controller": "Ready",
                            "vigem_installed": state["vigem"],
                            "hidhide_installed": state["hidhide"],
                            "preview_frame": result.preview_frame if config["preview_enabled"] else None,
                            "preview_point": result.point,
                            "preview_box": result.box,
                        })
                        self._set_telemetry(data)
                        last_telemetry_at = now
                    time.sleep(0.10)
                    continue

                ads = snapshot.left_trigger >= config["ads"]
                active = self._is_active(snapshot, config) and bool(config["enabled"])
                if active and not last_active:
                    active_since = now
                    vision.reset()
                    result = DetectionResult()
                if not active and last_active:
                    result = DetectionResult()
                    target_since = lost_since = 0.0
                    last_target_output = (0, 0)
                last_active = active

                wants_capture = bool(config["enabled"] and (active or config["preview_enabled"]))
                capture_period = 1.0 / min(int(config["fps"]), int(config["detection_hz"]))
                make_preview = bool(config["preview_enabled"] and now - last_preview_at >= 1.0 / int(config["preview_fps"]))
                if wants_capture and now - last_detection_at >= capture_period:
                    if now >= capture_retry_at:
                        try:
                            frame = capture.grab(config)
                            capture_status = "Ready"
                            if frame is not None:
                                try:
                                    result = vision.detect(frame, config, now=now, make_preview=make_preview)
                                    if make_preview and result.preview_frame is None:
                                        result.preview_frame = frame.copy()
                                    capture_error = ""
                                    if make_preview:
                                        last_preview_at = now
                                except Exception as exc:
                                    result = DetectionResult()
                                    message = f"Vision unavailable: {exc}"
                                    if message != capture_error:
                                        capture_error = message
                                        self.events.put(("capture_error", message))
                                    capture_status = "Error"
                                    if make_preview:
                                        result.preview_frame = frame.copy()
                                capture_count += 1
                            else:
                                capture_error = ""
                            last_detection_at = now
                        except Exception as exc:
                            message = str(exc)
                            if message != capture_error:
                                capture_error = message
                                self.events.put(("capture_error", message))
                            capture_status = "Error"
                            capture_retry_at = now + 2.0
                            last_detection_at = now
                    else:
                        capture_status = "Error"
                        last_detection_at = now
                elif not wants_capture:
                    result = DetectionResult()
                    vision.reset()
                    target_since = lost_since = 0.0
                    last_target_output = (0, 0)

                correction_x = correction_y = 0
                if active:
                    if result.found:
                        if target_since == 0:
                            target_since = now
                        lost_since = 0.0
                        delay_done = (now - active_since) * 1000 >= int(config["correction_delay_ms"])
                        ramp_up = int(config["ramp_up_ms"])
                        ramp = 1.0 if ramp_up == 0 else min(1.0, (now - target_since) * 1000 / ramp_up)
                        if delay_done:
                            correction_x = int(result.correction_x * ramp)
                            correction_y = int(result.correction_y * ramp)
                            last_target_output = (correction_x, correction_y)
                    else:
                        target_since = 0.0
                        ramp_down = int(config["ramp_down_ms"])
                        if ramp_down and last_target_output != (0, 0):
                            if lost_since == 0:
                                lost_since = now
                            ramp = max(0.0, 1 - (now - lost_since) * 1000 / ramp_down)
                            correction_x = int(last_target_output[0] * ramp)
                            correction_y = int(last_target_output[1] * ramp)
                            if ramp == 0:
                                last_target_output = (0, 0)
                virtual.write(snapshot, correction_x, correction_y)

                loop_elapsed = max(1e-6, now - last_loop_tick)
                last_loop_tick = now
                loop_fps = 1.0 / loop_elapsed
                if now - capture_started >= 0.5:
                    measured_capture_fps = capture_count / (now - capture_started)
                    capture_count = 0
                    capture_started = now
                if now - last_telemetry_at >= 0.1:
                    if now >= next_driver_check:
                        state = driver_status()
                        next_driver_check = now + 10.0
                    data = {
                        "running": True,
                        "capture_status": capture_status,
                        "capture_error": capture_error,
                        "capture_fps": measured_capture_fps,
                        "loop_fps": loop_fps,
                        "controller_connected": True,
                        "controller_name": f"Xbox controller · XInput {snapshot.slot}",
                        "slot": snapshot.slot,
                        "virtual_controller": "Ready",
                        "vigem_installed": state["vigem"],
                        "hidhide_installed": state["hidhide"],
                        "ads": ads,
                        "active": active,
                        "target_found": bool(result.found and active),
                        "confidence": result.confidence if active else 0,
                        "correction_x": correction_x,
                        "correction_y": correction_y,
                        "inputs": {
                            "LT": round(snapshot.left_trigger * 100 / 255),
                            "RT": round(snapshot.right_trigger * 100 / 255),
                            "LX": round(snapshot.lx * 100 / 32767),
                            "LY": round(snapshot.ly * 100 / 32767),
                            "RX": round(snapshot.rx * 100 / 32767),
                            "RY": round(snapshot.ry * 100 / 32767),
                        },
                        "buttons": snapshot.button_states,
                        "preview_frame": result.preview_frame if make_preview else None,
                        "preview_point": result.point,
                        "preview_box": result.box,
                    }
                    self._set_telemetry(data)
                    last_telemetry_at = now
                time.sleep(1 / max(60, int(config["fps"]) * 4))
        except Exception as exc:
            self.events.put(("fatal", str(exc)))
            self.events.put(("log", f"Engine error: {exc}"))
        finally:
            capture.release()
            if virtual is not None:
                virtual.reset()
            self.events.put(("status", "Stopped"))
            self.events.put(("log", "Engine stopped"))
            data = self._empty_telemetry()
            data.update({"capture_status": capture_status, "capture_error": capture_error})
            try:
                drivers = driver_status()
                data.update({"vigem_installed": drivers["vigem"], "hidhide_installed": drivers["hidhide"]})
            except Exception:
                pass
            self._set_telemetry(data)
