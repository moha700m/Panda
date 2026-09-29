"""Configuration and profile persistence for Panda."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

APP_NAME = "PandaTrainingStandalone"

ENGINE_DEFAULTS: dict[str, Any] = {
    # Legacy names (preset, fov, dead, smooth, strength, max_corr, yoff, conf,
    # ads, fps and slot) are retained so existing config.json files migrate.
    "target_color": "red",
    "fov": 170,
    "dead": 4,
    "min_area": 18,
    "max_area": 12000,
    "kernel": 3,
    "smooth": 0.42,
    "strength": 0.23,
    "max_corr": 7500,
    "max_x": 7500,
    "max_y": 7500,
    "x_strength": 1.0,
    "y_strength": 1.0,
    "horizontal_smooth": 0.42,
    "vertical_smooth": 0.42,
    "acceleration": 0.0,
    "curve": "linear",
    "yoff": -0.10,
    "horizontal_offset_px": 0,
    "vertical_offset_px": 0,
    "target_anchor": "upper",
    "head_offset": 0.0,
    "center_mass_offset": 0.0,
    "conf": 18,
    "detection_threshold": 50,
    "target_selection": "closest_to_crosshair",
    "target_persistence_ms": 0,
    "lost_timeout_ms": 0,
    "detection_hz": 120,
    "ramp_up_ms": 0,
    "ramp_down_ms": 0,
    "correction_delay_ms": 0,
    "target_switch_delay_ms": 0,
    "noise_filter": False,
    "ads": 45,
    "activation_mode": "ads_only",
    "manual_hotkey": "HOME",
    "fps": 120,
    "capture_monitor": 0,
    "capture_region": "center",
    "custom_width": 640,
    "custom_height": 640,
    "preview_enabled": False,
    "show_fov": True,
    "show_marker": True,
    "overlay_opacity": 0.75,
    "preview_fps": 15,
    "slot": -1,
    "enabled": True,
    "hsv_h_min": 0,
    "hsv_s_min": 120,
    "hsv_v_min": 120,
    "hsv_h_max": 10,
    "hsv_s_max": 255,
    "hsv_v_max": 255,
}

UI_DEFAULTS: dict[str, Any] = {
    "last_profile": "Default",
    "auto_load_last_profile": True,
    "start_minimized": False,
    "remember_window_position": True,
    "window_geometry": None,
    "launch_on_startup": False,
    "minimize_to_tray": False,
    "dark_mode": True,
    "accent_color": "#C7F36B",
}

DEFAULTS = {**ENGINE_DEFAULTS, **UI_DEFAULTS}
PROFILE_KEYS = tuple(ENGINE_DEFAULTS)

PROFILE_TEMPLATES: dict[str, dict[str, Any]] = {
    "Default": {},
    "Red Target": {"target_color": "red"},
    "Purple Target": {"target_color": "purple"},
    "Fast": {"smooth": 0.68, "horizontal_smooth": 0.68, "vertical_smooth": 0.68, "strength": 0.30, "curve": "dynamic"},
    "Smooth": {"smooth": 0.62, "horizontal_smooth": 0.62, "vertical_smooth": 0.62, "strength": 0.17, "curve": "smooth"},
    "Custom 1": {},
}

RESPONSE_PRESETS = {
    "Smooth": {
        "smooth": 0.62,
        "horizontal_smooth": 0.62,
        "vertical_smooth": 0.62,
        "strength": 0.17,
        "curve": "smooth",
        "acceleration": 0.0,
        "ramp_up_ms": 0,
    },
    "Balanced": {
        "smooth": 0.42,
        "horizontal_smooth": 0.42,
        "vertical_smooth": 0.42,
        "strength": 0.23,
        "curve": "linear",
        "acceleration": 0.0,
        "ramp_up_ms": 0,
    },
    "Responsive": {
        "smooth": 0.72,
        "horizontal_smooth": 0.72,
        "vertical_smooth": 0.72,
        "strength": 0.30,
        "curve": "dynamic",
        "acceleration": 0.18,
        "ramp_up_ms": 35,
    },
}


def app_data_dir() -> Path:
    """Return the per-user application data directory."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    if os.name == "nt":
        return Path.home() / "AppData" / "Roaming" / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    """Replace a JSON file atomically, keeping the temporary file nearby."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _bounded_int(value: Any, fallback: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _bounded_float(value: Any, fallback: float, low: float, high: float) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return fallback
        return max(low, min(high, number))
    except (TypeError, ValueError, OverflowError):
        return fallback


def normalize_settings(values: dict[str, Any] | None) -> dict[str, Any]:
    """Merge old and current settings, applying safe, bounded values."""
    raw = dict(values or {})
    if "target_color" not in raw and "preset" in raw:
        raw["target_color"] = raw["preset"]
    out = {**ENGINE_DEFAULTS, **{key: value for key, value in raw.items() if key in ENGINE_DEFAULTS}}
    out["target_color"] = out["target_color"] if out["target_color"] in {"red", "purple", "yellow", "green", "custom"} else "red"
    int_ranges = {
        "fov": (30, 600), "dead": (0, 200), "min_area": (1, 100000),
        "max_area": (1, 1000000), "kernel": (1, 31), "max_corr": (100, 32767),
        "max_x": (100, 32767), "max_y": (100, 32767), "conf": (0, 100),
        "detection_threshold": (0, 100), "target_persistence_ms": (0, 2000),
        "lost_timeout_ms": (0, 2000), "detection_hz": (15, 240), "ads": (0, 255),
        "ramp_up_ms": (0, 2000), "ramp_down_ms": (0, 2000),
        "correction_delay_ms": (0, 2000), "target_switch_delay_ms": (0, 2000),
        "fps": (30, 240), "capture_monitor": (0, 15), "custom_width": (64, 7680),
        "custom_height": (64, 4320), "preview_fps": (1, 60),
        "hsv_h_min": (0, 179), "hsv_s_min": (0, 255), "hsv_v_min": (0, 255),
        "hsv_h_max": (0, 179), "hsv_s_max": (0, 255), "hsv_v_max": (0, 255),
    }
    for key, (low, high) in int_ranges.items():
        out[key] = _bounded_int(out[key], ENGINE_DEFAULTS[key], low, high)
    # Map the pre-v2 single cap into both axes when loading an older config.
    if "max_x" not in raw and "max_corr" in raw:
        out["max_x"] = out["max_corr"]
    if "max_y" not in raw and "max_corr" in raw:
        out["max_y"] = out["max_corr"]
    if "horizontal_smooth" not in raw and "smooth" in raw:
        out["horizontal_smooth"] = out["smooth"]
    if "vertical_smooth" not in raw and "smooth" in raw:
        out["vertical_smooth"] = out["smooth"]
    out["kernel"] += int(out["kernel"] % 2 == 0)
    if out["max_area"] < out["min_area"]:
        out["max_area"] = out["min_area"]
    float_ranges = {
        "smooth": (0.01, 1.0), "strength": (0.01, 1.0), "x_strength": (0.0, 2.0),
        "y_strength": (0.0, 2.0), "horizontal_smooth": (0.01, 1.0),
        "vertical_smooth": (0.01, 1.0), "acceleration": (0.0, 1.0),
        "yoff": (-1.0, 1.0), "head_offset": (-1.0, 1.0),
        "center_mass_offset": (-1.0, 1.0), "overlay_opacity": (0.1, 1.0),
    }
    for key, (low, high) in float_ranges.items():
        out[key] = _bounded_float(out[key], ENGINE_DEFAULTS[key], low, high)
    for key, allowed, fallback in (
        ("capture_region", {"full", "center", "custom"}, "center"),
        ("target_anchor", {"upper", "center"}, "upper"),
        ("target_selection", {"closest_to_crosshair", "largest", "highest_confidence"}, "closest_to_crosshair"),
        ("curve", {"linear", "smooth", "dynamic"}, "linear"),
        ("activation_mode", {"ads_only", "manual_hotkey", "disabled"}, "ads_only"),
    ):
        if out[key] not in allowed:
            out[key] = fallback
    if out["manual_hotkey"] not in {"HOME", "F8", "F9", "F10", "F11", "F12"}:
        out["manual_hotkey"] = "HOME"
    out["slot"] = _bounded_int(out["slot"], -1, -1, 3)
    for key in ("noise_filter", "preview_enabled", "show_fov", "show_marker", "enabled"):
        out[key] = bool(out[key])
    return out


def apply_response_preset(settings: dict[str, Any], preset_name: str) -> dict[str, Any]:
    """Apply a named response preset to a copy of the current engine settings."""
    if preset_name not in RESPONSE_PRESETS:
        raise ValueError(f"Unknown response preset: {preset_name}")
    result = dict(settings)
    result.update(RESPONSE_PRESETS[preset_name])
    return normalize_settings(result)


class ConfigStore:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else app_data_dir()
        self.path = self.root / "config.json"

    def load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except (OSError, json.JSONDecodeError):
            raw = {}
        # Migrate legacy engine values and retain current appearance/window preferences.
        current = dict(DEFAULTS)
        current.update({key: value for key, value in raw.items() if key in DEFAULTS})
        return {**normalize_settings(raw), **{key: current[key] for key in UI_DEFAULTS}}

    def save(self, settings: dict[str, Any]) -> None:
        value = {**DEFAULTS, **normalize_settings(settings)}
        for key in UI_DEFAULTS:
            if key in settings:
                value[key] = settings[key]
        atomic_json_write(self.path, value)


def _profile_filename(name: str) -> str:
    clean = re.sub(r"[^\w -]", "", name, flags=re.UNICODE).strip()
    clean = re.sub(r"\s+", " ", clean)
    if not clean or len(clean) > 48:
        raise ValueError("Profile name must contain 1–48 letters, numbers, spaces, dashes or underscores.")
    if clean.casefold().split(".")[0] in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}:
        raise ValueError("That name is reserved by Windows.")
    return clean.casefold().replace(" ", "_") + ".json"


class ProfileManager:
    def __init__(self, root: Path | str | None = None):
        data_root = Path(root) if root is not None else app_data_dir()
        self.directory = data_root / "profiles"

    def ensure_defaults(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if any(self.directory.glob("*.json")):
            return
        for name, overrides in PROFILE_TEMPLATES.items():
            self.save(name, {**ENGINE_DEFAULTS, **overrides})

    def list(self) -> list[str]:
        self.directory.mkdir(parents=True, exist_ok=True)
        names: list[str] = []
        for path in sorted(self.directory.glob("*.json"), key=lambda p: p.name.casefold()):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("name"), str):
                    names.append(data["name"])
            except (OSError, json.JSONDecodeError):
                continue
        return names

    def _path(self, name: str) -> Path:
        return self.directory / _profile_filename(name)

    def load(self, name: str) -> dict[str, Any]:
        path = self._path(name)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("name", "").casefold() != name.casefold():
            raise ValueError(f"Profile name mismatch: {name}")
        return normalize_settings(data.get("settings", {}))

    def save(self, name: str, settings: dict[str, Any]) -> None:
        path = self._path(name)
        for existing in self.list():
            if existing.casefold() != name.casefold() and self._path(existing) == path:
                raise ValueError(f"A profile named '{existing}' uses the same file name.")
            if existing.casefold() == name.casefold() and self._path(existing) != path:
                raise ValueError(f"A profile named '{existing}' already exists.")
        atomic_json_write(path, {"name": name, "settings": normalize_settings(settings)})

    def create(self, name: str, settings: dict[str, Any] | None = None) -> None:
        if any(existing.casefold() == name.casefold() for existing in self.list()):
            raise ValueError(f"A profile named '{name}' already exists.")
        self.save(name, settings or ENGINE_DEFAULTS)

    def duplicate(self, source_name: str, new_name: str) -> None:
        self.create(new_name, self.load(source_name))

    def rename(self, old_name: str, new_name: str) -> None:
        if old_name.casefold() == "default":
            raise ValueError("The Default profile is kept as the recovery profile.")
        old_path = self._path(old_name)
        if any(existing.casefold() == new_name.casefold() for existing in self.list()):
            raise ValueError(f"A profile named '{new_name}' already exists.")
        settings = self.load(old_name)
        self.save(new_name, settings)
        old_path.unlink()

    def delete(self, name: str) -> None:
        if name.casefold() == "default":
            raise ValueError("The Default profile cannot be deleted.")
        self._path(name).unlink(missing_ok=False)
