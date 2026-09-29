"""Screen color detection and right-stick correction calculations."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class DetectionResult:
    correction_x: int = 0
    correction_y: int = 0
    confidence: int = 0
    found: bool = False
    point: tuple[float, float] | None = None
    box: tuple[int, int, int, int] | None = None
    preview_frame: Any = None


class Vision:
    def __init__(self):
        self.sx = 0.0
        self.sy = 0.0
        self._last_valid = DetectionResult()
        self._last_valid_at = 0.0
        self._last_point: tuple[float, float] | None = None
        self._switch_point: tuple[float, float] | None = None
        self._switch_since = 0.0

    @staticmethod
    def _mask(frame: np.ndarray, settings: dict[str, Any]) -> np.ndarray:
        color = settings["target_color"]
        b, g, r = (frame[:, :, i].astype(np.int16) for i in range(3))
        threshold = int(settings["detection_threshold"])
        if color == "purple":
            minimum = 70 + threshold
            mask = (r > minimum) & (b > minimum) & (g < 195 - threshold // 2) & ((r + b - g) > 150)
        elif color == "yellow":
            mask = (r > 120 + threshold) & (g > 100 + threshold) & (b < 140) & ((r + g - b) > 260)
        elif color == "green":
            minimum = 100 + threshold
            mask = (g > minimum) & (g > r * 1.08) & (g > b * 1.08)
        elif color == "custom":
            import cv2

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            low = [settings["hsv_h_min"], settings["hsv_s_min"], settings["hsv_v_min"]]
            high = [settings["hsv_h_max"], settings["hsv_s_max"], settings["hsv_v_max"]]
            if low[0] <= high[0]:
                return cv2.inRange(hsv, np.asarray(low, dtype=np.uint8), np.asarray(high, dtype=np.uint8)) > 0
            first = cv2.inRange(hsv, np.asarray([0, low[1], low[2]], dtype=np.uint8), np.asarray(high, dtype=np.uint8))
            second = cv2.inRange(hsv, np.asarray(low, dtype=np.uint8), np.asarray([179, high[1], high[2]], dtype=np.uint8))
            return cv2.bitwise_or(first, second) > 0
        else:
            minimum = 80 + int(1.5 * threshold)
            ratio = 1.10 + 0.003 * threshold
            mask = (r > minimum) & (r > g * ratio) & (r > b * ratio)
        return mask

    @staticmethod
    def _box(xs: np.ndarray, ys: np.ndarray) -> tuple[int, int, int, int]:
        left, right = int(xs.min()), int(xs.max())
        top, bottom = int(ys.min()), int(ys.max())
        return left, top, right - left + 1, bottom - top + 1

    def _select(self, mask: np.ndarray, settings: dict[str, Any], center_x: float, center_y: float):
        min_area, max_area = int(settings["min_area"]), int(settings["max_area"])
        fov = int(settings["fov"])
        selection = settings["target_selection"]
        if selection == "closest_to_crosshair":
            ys, xs = np.nonzero(mask)
            if not len(xs):
                return None
            distance_sq = (xs - center_x) ** 2 + (ys - center_y) ** 2
            index = int(np.argmin(distance_sq))
            px, py = int(xs[index]), int(ys[index])
            radius = max(8, int(settings["kernel"]) * 4)
            near = (np.abs(xs - px) <= radius) & (np.abs(ys - py) <= radius)
            area = int(near.sum())
            if area < min_area or area > max_area:
                return None
            cluster_x, cluster_y = xs[near], ys[near]
            target_x = float(cluster_x.mean())
            target_y = float(cluster_y.mean()) + radius * float(settings["yoff"])
            box = self._box(cluster_x, cluster_y)
            distance = math.hypot(target_x - center_x, target_y - center_y)
            if distance > fov:
                return None
            confidence = int(max(0, min(100, max(0, 1 - distance / max(1, fov)) * 80 + min(1, area / 80) * 20)))
            return target_x, target_y, area, confidence, box

        import cv2

        binary = mask.astype(np.uint8) * 255
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, 8)
        candidates = []
        for index in range(1, count):
            x, y, width, height, area = (int(v) for v in stats[index])
            if area < min_area or area > max_area:
                continue
            target_x, target_y = (float(v) for v in centroids[index])
            distance = math.hypot(target_x - center_x, target_y - center_y)
            if distance > fov:
                continue
            confidence = int(max(0, min(100, max(0, 1 - distance / max(1, fov)) * 80 + min(1, area / 80) * 20)))
            candidates.append((target_x, target_y, area, confidence, (x, y, width, height)))
        if not candidates:
            return None
        if selection == "largest":
            return max(candidates, key=lambda item: item[2])
        return max(candidates, key=lambda item: item[3])

    def _lost(self, settings: dict[str, Any], now: float) -> DetectionResult:
        if self._last_valid_at <= 0:
            self.sx *= 0.65
            self.sy *= 0.65
            return DetectionResult()
        elapsed_ms = (now - self._last_valid_at) * 1000
        persistence = int(settings["target_persistence_ms"])
        timeout = int(settings["lost_timeout_ms"])
        if elapsed_ms <= persistence:
            return DetectionResult(
                self._last_valid.correction_x,
                self._last_valid.correction_y,
                max(0, int(self._last_valid.confidence * (1 - elapsed_ms / max(1, persistence)))),
                True,
                self._last_valid.point,
                self._last_valid.box,
            )
        fade_elapsed = elapsed_ms - persistence
        if timeout and fade_elapsed < timeout:
            factor = max(0.0, 1 - fade_elapsed / timeout)
            return DetectionResult(
                int(self._last_valid.correction_x * factor),
                int(self._last_valid.correction_y * factor),
                int(self._last_valid.confidence * factor),
                factor > 0,
                self._last_valid.point,
                self._last_valid.box,
            )
        self.sx *= 0.65
        self.sy *= 0.65
        self._last_valid_at = 0.0
        self._last_point = None
        self._switch_point = None
        return DetectionResult()

    def detect(
        self,
        frame: np.ndarray | None,
        settings: dict[str, Any],
        now: float | None = None,
        make_preview: bool = False,
    ) -> DetectionResult:
        now = time.perf_counter() if now is None else now
        if frame is None:
            return self._lost(settings, now)
        mask = self._mask(frame, settings)
        if settings["noise_filter"]:
            import cv2

            size = int(settings["kernel"])
            kernel = np.ones((size, size), dtype=np.uint8)
            mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel) > 0
        height, width = frame.shape[:2]
        center_x, center_y = width / 2, height / 2
        selected = self._select(mask, settings, center_x, center_y)
        if selected is None:
            return self._lost(settings, now)
        target_x, target_y, area, confidence, box = selected
        if confidence < int(settings["conf"]):
            return self._lost(settings, now)

        point = (target_x, target_y)
        switch_delay = int(settings["target_switch_delay_ms"])
        if self._last_point is not None and switch_delay:
            change = math.hypot(target_x - self._last_point[0], target_y - self._last_point[1])
            if change > max(20, int(settings["fov"] * 0.12)):
                if self._switch_point is None or math.hypot(target_x - self._switch_point[0], target_y - self._switch_point[1]) > 20:
                    self._switch_point, self._switch_since = point, now
                    return self._last_valid
                if (now - self._switch_since) * 1000 < switch_delay:
                    return self._last_valid
        self._switch_point = None

        if settings["target_anchor"] == "upper":
            target_y += box[3] * float(settings["head_offset"])
        else:
            target_y += box[3] * float(settings["center_mass_offset"])
        dx = target_x - center_x + int(settings["horizontal_offset_px"])
        dy = target_y - center_y + int(settings["vertical_offset_px"])
        fov = max(1, int(settings["fov"]))
        distance = math.hypot(dx, dy)
        if distance > fov:
            return self._lost(settings, now)

        self.sx += (dx - self.sx) * float(settings["horizontal_smooth"])
        self.sy += (dy - self.sy) * float(settings["vertical_smooth"])
        filtered_x = 0.0 if abs(self.sx) <= int(settings["dead"]) else self.sx
        filtered_y = 0.0 if abs(self.sy) <= int(settings["dead"]) else self.sy
        normalized = min(1.0, math.hypot(filtered_x, filtered_y) / fov)
        curve = settings["curve"]
        if curve == "smooth":
            response = normalized * normalized * (3 - 2 * normalized)
        elif curve == "dynamic":
            response = min(1.0, normalized * (1 + float(settings["acceleration"])))
        else:
            response = 1.0
        strength = float(settings["strength"]) * response
        max_x = min(int(settings["max_corr"]), int(settings["max_x"]))
        max_y = min(int(settings["max_corr"]), int(settings["max_y"]))
        correction_x = int(max(-max_x, min(max_x, filtered_x / fov * 32767 * strength * float(settings["x_strength"]))))
        correction_y = int(max(-max_y, min(max_y, -filtered_y / fov * 32767 * strength * float(settings["y_strength"]))))
        result = DetectionResult(correction_x, correction_y, confidence, True, point, box)
        self._last_valid = result
        self._last_valid_at = now
        self._last_point = point
        if settings["preview_enabled"] and make_preview:
            result.preview_frame = frame.copy()
        return result

    def reset(self) -> None:
        self.sx = self.sy = 0.0
        self._last_valid = DetectionResult()
        self._last_valid_at = 0.0
        self._last_point = self._switch_point = None
