import queue
import sys
import time
import types
import unittest
from unittest.mock import patch

import numpy as np

from panda.core.capture import ScreenCapture
from panda.core.config import ENGINE_DEFAULTS, normalize_settings
from panda.core.controller import ControllerSnapshot, VirtualXbox
from panda.core.engine import EngineWorker
from panda.core.vision import Vision


class ImportAndFallbackTests(unittest.TestCase):
    def test_core_imports_do_not_load_hardware_libraries(self):
        import panda.core.diagnostics  # noqa: F401
        import panda.core.drivers  # noqa: F401

        self.assertNotIn("vgamepad", sys.modules)

    def test_engine_reports_missing_vigem_without_importing_virtual_controller(self):
        events = queue.Queue()
        worker = EngineWorker(ENGINE_DEFAULTS, events)
        with patch("panda.core.engine.driver_status", return_value={"vigem": False, "hidhide": False}):
            worker.run()
        messages = []
        while not events.empty():
            messages.append(events.get_nowait())
        self.assertTrue(any(kind == "fatal" and "ViGEmBus" in message for kind, message in messages))
        self.assertNotIn("vgamepad", sys.modules)

    def test_preview_keeps_working_while_physical_controller_is_missing(self):
        class FakeReader:
            def __init__(self, slot): pass
            def read(self): return None

        class FakeVirtual:
            def reset(self): pass

        class FakeCapture:
            def __init__(self): self.frame = np.zeros((340, 340, 3), dtype=np.uint8)
            def grab(self, settings): return self.frame.copy()
            def release(self): pass

        events = queue.Queue()
        settings = normalize_settings({**ENGINE_DEFAULTS, "preview_enabled": True, "preview_fps": 15})
        worker = EngineWorker(settings, events)
        with patch("panda.core.engine.driver_status", return_value={"vigem": True, "hidhide": False}), patch(
            "panda.core.engine.XInputReader", FakeReader
        ), patch("panda.core.engine.VirtualXbox", FakeVirtual), patch("panda.core.engine.ScreenCapture", FakeCapture):
            worker.start()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and worker.latest_preview() is None:
                time.sleep(0.01)
            worker.stop()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(worker.snapshot()["controller_connected"])
        self.assertIsNotNone(worker.latest_preview())

    def test_capture_region_supports_full_center_and_custom_without_dxcam(self):
        capture = ScreenCapture()
        capture.width, capture.height = 1920, 1080
        settings = normalize_settings({"capture_region": "center", "fov": 170})
        self.assertEqual(capture.region_for(settings), (790, 370, 1130, 710))
        settings["capture_region"] = "full"
        self.assertEqual(capture.region_for(settings), (0, 0, 1920, 1080))
        settings.update({"capture_region": "custom", "custom_width": 640, "custom_height": 480})
        self.assertEqual(capture.region_for(settings), (640, 300, 1280, 780))


class RuntimeTests(unittest.TestCase):
    def test_left_stick_is_exact_passthrough_and_correction_only_changes_right(self):
        recorded = {}

        class FakePad:
            def press_button(self, **kwargs): pass
            def release_button(self, **kwargs): pass
            def left_trigger(self, **kwargs): pass
            def right_trigger(self, **kwargs): pass
            def left_joystick(self, **kwargs): recorded["left"] = kwargs
            def right_joystick(self, **kwargs): recorded["right"] = kwargs
            def update(self): pass
            def reset(self): pass

        fake_module = types.ModuleType("vgamepad")
        fake_module.XUSB_BUTTON = types.SimpleNamespace(**{name: name for _, name in (
            (1, "XUSB_GAMEPAD_DPAD_UP"), (2, "XUSB_GAMEPAD_DPAD_DOWN"),
            (4, "XUSB_GAMEPAD_DPAD_LEFT"), (8, "XUSB_GAMEPAD_DPAD_RIGHT"),
            (16, "XUSB_GAMEPAD_START"), (32, "XUSB_GAMEPAD_BACK"),
            (64, "XUSB_GAMEPAD_LEFT_THUMB"), (128, "XUSB_GAMEPAD_RIGHT_THUMB"),
            (256, "XUSB_GAMEPAD_LEFT_SHOULDER"), (512, "XUSB_GAMEPAD_RIGHT_SHOULDER"),
            (4096, "XUSB_GAMEPAD_A"), (8192, "XUSB_GAMEPAD_B"),
            (16384, "XUSB_GAMEPAD_X"), (32768, "XUSB_GAMEPAD_Y"),
        )})
        fake_module.VX360Gamepad = FakePad
        snapshot = ControllerSnapshot(0, 0, 0, 0, 1234, -5678, 900, -1200)
        with patch.dict(sys.modules, {"vgamepad": fake_module}):
            bridge = VirtualXbox()
            bridge.write(snapshot, 500, -300)
        self.assertEqual(recorded["left"], {"x_value": 1234, "y_value": -5678})
        self.assertEqual(recorded["right"], {"x_value": 1400, "y_value": -1500})

    def test_existing_color_detector_still_finds_a_red_cluster(self):
        settings = normalize_settings(ENGINE_DEFAULTS)
        frame = np.zeros((340, 340, 3), dtype=np.uint8)
        frame[165:175, 215:225] = (0, 0, 255)
        found = Vision().detect(frame, settings, now=1.0)
        self.assertTrue(found.found)
        self.assertGreater(found.confidence, 0)
        self.assertGreater(found.correction_x, 0)
        self.assertEqual(found.correction_y, 0)

    def test_default_color_masks_keep_the_existing_purple_green_and_yellow_cutoffs(self):
        settings = normalize_settings(ENGINE_DEFAULTS)
        purple = np.array([[[255, 175, 130]]], dtype=np.uint8)
        green = np.array([[[100, 151, 100]]], dtype=np.uint8)
        yellow = np.array([[[10, 240, 240]]], dtype=np.uint8)
        settings["target_color"] = "purple"
        self.assertFalse(bool(Vision._mask(purple, settings)[0, 0]))
        settings["target_color"] = "green"
        self.assertTrue(bool(Vision._mask(green, settings)[0, 0]))
        settings["target_color"] = "yellow"
        self.assertTrue(bool(Vision._mask(yellow, settings)[0, 0]))


if __name__ == "__main__":
    unittest.main()
