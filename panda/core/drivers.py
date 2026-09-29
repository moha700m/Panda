"""Windows driver checks and elevated vendor installer launch."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

VIGEM_URL = "https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBus_1.22.0_x64_x86_arm64.exe"
HIDHIDE_URL = "https://github.com/nefarius/HidHide/releases/download/v1.5.230.0/HidHide_1.5.230_x64.exe"


def service_installed(name: str) -> bool:
    """Check the Windows service registry without importing winreg at startup."""
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SYSTEM\CurrentControlSet\Services\{name}"):
            return True
    except (OSError, ImportError):
        return False


def driver_status() -> dict[str, bool]:
    return {"vigem": service_installed("ViGEmBus"), "hidhide": service_installed("HidHide")}


def open_hidhide_client() -> bool:
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    candidates = (
        program_files / "Nefarius Software Solutions" / "HidHide" / "HidHideClient.exe",
        program_files / "Nefarius Software Solutions e.U" / "HidHide" / "HidHideClient.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            if os.name == "nt":
                subprocess.Popen([str(candidate)])
                return True
    return False


def set_launch_on_startup(enabled: bool, app_name: str = "PandaTrainingStandalone") -> None:
    if os.name != "nt":
        raise OSError("Windows startup settings are only available on Windows.")
    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            if getattr(sys, "frozen", False):
                command = f'"{sys.executable}"'
            else:
                script = Path(sys.argv[0]).resolve()
                command = f'"{sys.executable}" "{script}"'
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "PandaTrainingStandalone/2.0"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        while chunk := response.read(256 * 1024):
            output.write(chunk)


def _run_elevated(installer: Path, args: str) -> bool:
    if os.name != "nt":
        return False
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(installer), args, None, 1)
    return result > 32


def install_or_repair_drivers() -> str:
    """Download official vendor installers and request elevation for each missing driver."""
    if os.name != "nt":
        raise OSError("Driver installation is only available on Windows.")
    work = Path(tempfile.gettempdir()) / "PandaTrainingStandalone" / "drivers"
    work.mkdir(parents=True, exist_ok=True)
    state = driver_status()
    launched: list[str] = []
    if not state["vigem"]:
        installer = work / "ViGEmBus_Setup.exe"
        _download(VIGEM_URL, installer)
        if not _run_elevated(installer, "/qn"):
            raise OSError("Windows did not start the ViGEmBus installer with administrator approval.")
        launched.append("ViGEmBus")
    if not state["hidhide"]:
        installer = work / "HidHide_Setup.exe"
        _download(HIDHIDE_URL, installer)
        if not _run_elevated(installer, "/install /quiet"):
            raise OSError("Windows did not start the HidHide installer with administrator approval.")
        launched.append("HidHide")
    if not launched:
        return "Both drivers are already installed."
    return f"Started installer(s): {', '.join(launched)}. Windows may require a restart."
