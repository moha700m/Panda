"""Hardware-independent diagnostics and rotating application logs."""

from __future__ import annotations

import logging
import os
import platform
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from panda import __version__
from panda.core.config import app_data_dir
from panda.core.controller import XInputReader
from panda.core.drivers import driver_status


class DiagnosticLog:
    def __init__(self, root: Path | str | None = None):
        self.directory = (Path(root) if root is not None else app_data_dir()) / "logs"
        self.path = self.directory / "panda.log"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("panda")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not any(isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(self.path) for handler in self.logger.handlers):
            handler = RotatingFileHandler(self.path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
            self.logger.addHandler(handler)

    def write(self, message: str) -> None:
        self.logger.info(message)

    def read(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def clear(self) -> None:
        for handler in self.logger.handlers:
            if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(self.path):
                handler.acquire()
                try:
                    handler.close()
                    self.logger.removeHandler(handler)
                finally:
                    handler.release()
        self.path.unlink(missing_ok=True)
        # Re-open the log after truncation so subsequent diagnostics are captured.
        self.logger = logging.getLogger("panda")
        handler = RotatingFileHandler(self.path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        self.logger.addHandler(handler)

    def close(self) -> None:
        """Release the log file so application data can be moved or removed."""
        for handler in tuple(self.logger.handlers):
            if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(self.path):
                self.logger.removeHandler(handler)
                handler.close()


def monitor_details() -> tuple[int, int, int]:
    """Return primary display width, height, and Windows monitor count."""
    if os.name != "nt":
        return 0, 0, 0
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1)), int(user32.GetSystemMetrics(80))
    except Exception:
        return 0, 0, 0


def xinput_status(slot: int = -1) -> tuple[bool, int | None, str]:
    try:
        snapshot = XInputReader(slot).read()
        if snapshot is None:
            return False, None, "Not connected"
        return True, snapshot.slot, f"Xbox controller (XInput slot {snapshot.slot})"
    except Exception as exc:
        return False, None, str(exc)


def system_snapshot(slot: int = -1) -> dict[str, Any]:
    width, height, monitors = monitor_details()
    controller, resolved_slot, controller_name = xinput_status(slot)
    drivers = driver_status()
    return {
        "application_version": __version__,
        "windows_version": f"Windows {platform.release()} ({platform.version()})" if os.name == "nt" else f"{platform.system()} {platform.release()}",
        "screen_resolution": f"{width} × {height}" if width and height else "Unavailable",
        "monitor_count": monitors,
        "controller_connected": controller,
        "controller_name": controller_name,
        "xinput_slot": resolved_slot,
        "vigem_installed": drivers["vigem"],
        "hidhide_installed": drivers["hidhide"],
    }


def format_diagnostics(snapshot: dict[str, Any], runtime: dict[str, Any] | None = None) -> str:
    runtime = runtime or {}
    lines = [
        f"Application version: {snapshot.get('application_version', __version__)}",
        f"OS: {snapshot.get('windows_version', 'Unknown')}",
        f"Screen resolution: {snapshot.get('screen_resolution', 'Unavailable')}",
        f"Monitor count: {snapshot.get('monitor_count', 0)}",
        f"Capture status: {runtime.get('capture_status', 'Idle')}",
        f"Capture FPS: {runtime.get('capture_fps', 0):.0f}",
        f"Controller: {snapshot.get('controller_name', 'Not connected')}",
        f"XInput slot: {snapshot.get('xinput_slot', 'Auto')}",
        f"ViGEmBus: {'Installed' if snapshot.get('vigem_installed') else 'Missing'}",
        f"HidHide: {'Installed' if snapshot.get('hidhide_installed') else 'Optional / missing'}",
        f"Virtual controller: {runtime.get('virtual_controller', 'Offline')}",
    ]
    return "\n".join(lines)
