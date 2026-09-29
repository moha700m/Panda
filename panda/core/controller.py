"""Lazy XInput reader and ViGEm virtual Xbox controller bridge."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass


class Gamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", wintypes.SHORT),
        ("sThumbLY", wintypes.SHORT),
        ("sThumbRX", wintypes.SHORT),
        ("sThumbRY", wintypes.SHORT),
    ]


class State(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", Gamepad)]


BUTTON_BITS = (
    (1, "D-pad Up"), (2, "D-pad Down"), (4, "D-pad Left"), (8, "D-pad Right"),
    (16, "Start"), (32, "Back"), (64, "Left Stick"), (128, "Right Stick"),
    (256, "LB"), (512, "RB"), (4096, "A"), (8192, "B"), (16384, "X"), (32768, "Y"),
)
VIGEM_BUTTONS = (
    (1, "XUSB_GAMEPAD_DPAD_UP"), (2, "XUSB_GAMEPAD_DPAD_DOWN"),
    (4, "XUSB_GAMEPAD_DPAD_LEFT"), (8, "XUSB_GAMEPAD_DPAD_RIGHT"),
    (16, "XUSB_GAMEPAD_START"), (32, "XUSB_GAMEPAD_BACK"),
    (64, "XUSB_GAMEPAD_LEFT_THUMB"), (128, "XUSB_GAMEPAD_RIGHT_THUMB"),
    (256, "XUSB_GAMEPAD_LEFT_SHOULDER"), (512, "XUSB_GAMEPAD_RIGHT_SHOULDER"),
    (4096, "XUSB_GAMEPAD_A"), (8192, "XUSB_GAMEPAD_B"),
    (16384, "XUSB_GAMEPAD_X"), (32768, "XUSB_GAMEPAD_Y"),
)


@dataclass(frozen=True)
class ControllerSnapshot:
    slot: int
    buttons: int
    left_trigger: int
    right_trigger: int
    lx: int
    ly: int
    rx: int
    ry: int

    @property
    def button_states(self) -> dict[str, bool]:
        return {name: bool(self.buttons & mask) for mask, name in BUTTON_BITS}


class XInputReader:
    def __init__(self, requested_slot: int = -1):
        if os.name != "nt":
            raise OSError("XInput is only available on Windows.")
        self.requested_slot = requested_slot
        self._dll = self._load_xinput()

    @staticmethod
    def _load_xinput():
        loader = getattr(ctypes, "WinDLL", None)
        if loader is None:
            raise OSError("Windows XInput libraries are unavailable.")
        for name in ("xinput1_4.dll", "xinput9_1_0.dll", "xinput1_3.dll"):
            try:
                dll = loader(name)
                dll.XInputGetState.argtypes = [wintypes.DWORD, ctypes.POINTER(State)]
                dll.XInputGetState.restype = wintypes.DWORD
                return dll
            except OSError:
                continue
        raise OSError("XInput was not found on this Windows installation.")

    def read(self) -> ControllerSnapshot | None:
        slots = range(4) if self.requested_slot < 0 else (self.requested_slot,)
        for slot in slots:
            state = State()
            if self._dll.XInputGetState(slot, ctypes.byref(state)) == 0:
                gamepad = state.Gamepad
                return ControllerSnapshot(
                    slot=slot,
                    buttons=int(gamepad.wButtons),
                    left_trigger=int(gamepad.bLeftTrigger),
                    right_trigger=int(gamepad.bRightTrigger),
                    lx=int(gamepad.sThumbLX),
                    ly=int(gamepad.sThumbLY),
                    rx=int(gamepad.sThumbRX),
                    ry=int(gamepad.sThumbRY),
                )
        return None


class VirtualXbox:
    """Create vgamepad only after the caller has checked ViGEmBus."""

    def __init__(self):
        try:
            import vgamepad as vg
        except Exception as exc:
            if "VIGEM_ERROR_BUS_NOT_FOUND" in str(exc):
                raise RuntimeError(
                    "ViGEmBus is not installed or is not running. Install/repair the driver, restart Windows, and reopen Panda."
                ) from exc
            raise
        self._vg = vg
        self._gamepad = vg.VX360Gamepad()

    def write(self, snapshot: ControllerSnapshot, correction_x: int = 0, correction_y: int = 0) -> None:
        gamepad = self._gamepad
        for mask, button_name in VIGEM_BUTTONS:
            button = getattr(self._vg.XUSB_BUTTON, button_name)
            if snapshot.buttons & mask:
                gamepad.press_button(button=button)
            else:
                gamepad.release_button(button=button)
        gamepad.left_trigger(value=snapshot.left_trigger)
        gamepad.right_trigger(value=snapshot.right_trigger)
        # Keep the left stick byte-for-byte passthrough. CV corrections affect RX/RY only.
        gamepad.left_joystick(x_value=snapshot.lx, y_value=snapshot.ly)
        rx = max(-32768, min(32767, snapshot.rx + int(correction_x)))
        ry = max(-32768, min(32767, snapshot.ry + int(correction_y)))
        gamepad.right_joystick(x_value=rx, y_value=ry)
        gamepad.update()

    def reset(self) -> None:
        try:
            self._gamepad.reset()
            self._gamepad.update()
        except Exception:
            pass
