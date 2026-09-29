"""Lazy DXcam setup and monitor-local capture regions."""

from __future__ import annotations

import ctypes
import os
import re
from typing import Any


def output_dimensions(dxcam_module: Any, output_idx: int) -> tuple[int, int]:
    """Read the selected output dimensions from DXcam, with a primary-screen fallback."""
    try:
        info = dxcam_module.output_info()
        for line in str(info).splitlines():
            match = re.search(rf"Output\[{output_idx}\].*?Res:\((\d+),\s*(\d+)\)", line)
            if match:
                return int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
        except Exception:
            pass
    return 1920, 1080


class ScreenCapture:
    def __init__(self):
        self.camera = None
        self.width = 0
        self.height = 0
        self.output_idx = 0

    def start(self, output_idx: int) -> None:
        if self.camera is not None and self.output_idx == output_idx:
            return
        self.release()
        try:
            import dxcam
        except Exception as exc:
            raise RuntimeError(f"DXcam could not be loaded: {exc}") from exc
        try:
            self.camera = dxcam.create(output_idx=output_idx, output_color="BGR")
            if self.camera is None:
                raise RuntimeError("DXcam did not create a capture device.")
            self.output_idx = output_idx
            self.width, self.height = output_dimensions(dxcam, output_idx)
        except Exception as exc:
            self.release()
            raise RuntimeError(f"Display {output_idx + 1} capture failed: {exc}") from exc

    def region_for(self, settings: dict[str, Any]) -> tuple[int, int, int, int]:
        width, height = self.width, self.height
        mode = settings["capture_region"]
        if mode == "full":
            return 0, 0, width, height
        if mode == "custom":
            region_width = min(width, int(settings["custom_width"]))
            region_height = min(height, int(settings["custom_height"]))
        else:
            region_width = min(width, max(2, int(settings["fov"]) * 2))
            region_height = min(height, max(2, int(settings["fov"]) * 2))
        left = max(0, (width - region_width) // 2)
        top = max(0, (height - region_height) // 2)
        return left, top, left + region_width, top + region_height

    def grab(self, settings: dict[str, Any]):
        output_idx = int(settings["capture_monitor"])
        if self.camera is None or self.output_idx != output_idx:
            self.start(output_idx)
        try:
            return self.camera.grab(region=self.region_for(settings))
        except Exception as exc:
            raise RuntimeError(f"Screen capture failed: {exc}") from exc

    def release(self) -> None:
        camera, self.camera = self.camera, None
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass
