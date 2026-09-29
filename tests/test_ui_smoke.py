import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from panda.core.config import ConfigStore
from panda.ui.main_window import MainWindow


class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["panda-ui-tests"])

    def test_window_opens_without_driver_or_controller_and_presets_are_live(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ConfigStore(Path(temp))
            snapshot = {
                "application_version": "2.0.0",
                "windows_version": "Windows test",
                "screen_resolution": "1920 × 1080",
                "monitor_count": 1,
                "controller_connected": False,
                "controller_name": "Not connected",
                "xinput_slot": None,
                "vigem_installed": False,
                "hidhide_installed": False,
            }
            with patch("panda.ui.main_window.ConfigStore", return_value=store), patch(
                "panda.ui.main_window.system_snapshot", return_value=snapshot
            ):
                window = MainWindow()
                window.show()
                self.app.processEvents()
                self.assertEqual(len(window.pages), 9)
                self.assertFalse(window.system["vigem_installed"])
                self.assertFalse(window.system["controller_connected"])
                self.assertIsNone(window.worker)
                self.assertNotIn("vgamepad", __import__("sys").modules)

                window._apply_preset("Responsive")
                self.assertEqual(window.engine_settings["curve"], "dynamic")
                self.assertEqual(window.engine_settings["strength"], 0.3)
                window._persist()
                self.assertEqual(store.load()["last_profile"], "Default")
                window.close()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
