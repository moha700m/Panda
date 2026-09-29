import json
import tempfile
import unittest
from pathlib import Path

from panda.core.config import ConfigStore, ProfileManager, apply_response_preset, normalize_settings


class ConfigTests(unittest.TestCase):
    def test_legacy_config_migrates_and_saves_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config.json").write_text(
                json.dumps({"preset": "purple", "fov": 240, "kernel": 4, "slot": 2}),
                encoding="utf-8",
            )
            store = ConfigStore(root)
            config = store.load()
            self.assertEqual(config["target_color"], "purple")
            self.assertEqual(config["fov"], 240)
            self.assertEqual(config["kernel"], 5)
            self.assertEqual(config["slot"], 2)
            config["last_profile"] = "Custom One"
            store.save(config)
            self.assertEqual(store.load()["last_profile"], "Custom One")
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_bad_values_are_bounded_and_response_presets_change_runtime_values(self):
        settings = normalize_settings({"fov": 5000, "strength": -5, "target_color": "nope"})
        self.assertEqual(settings["fov"], 600)
        self.assertEqual(settings["strength"], 0.01)
        self.assertEqual(settings["target_color"], "red")
        fast = apply_response_preset(settings, "Responsive")
        self.assertEqual(fast["curve"], "dynamic")
        self.assertEqual(fast["strength"], 0.3)


class ProfileTests(unittest.TestCase):
    def test_create_load_save_duplicate_rename_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileManager(temp)
            profiles.ensure_defaults()
            self.assertIn("Default", profiles.list())
            profiles.create("My Profile", {"target_color": "yellow", "strength": 0.44})
            self.assertEqual(profiles.load("My Profile")["strength"], 0.44)
            profiles.duplicate("My Profile", "Copy")
            profiles.save("Copy", {"target_color": "green"})
            self.assertEqual(profiles.load("Copy")["target_color"], "green")
            profiles.rename("Copy", "Renamed")
            self.assertIn("Renamed", profiles.list())
            profiles.delete("Renamed")
            self.assertNotIn("Renamed", profiles.list())
            with self.assertRaises(ValueError):
                profiles.delete("Default")
            with self.assertRaises(ValueError):
                profiles.rename("Default", "Primary")

    def test_names_cannot_escape_profile_directory_or_alias_a_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileManager(temp)
            profiles.create("Alpha Beta")
            with self.assertRaises(ValueError):
                profiles.create("Alpha   Beta")
            profiles.create("../../Beta")
            self.assertEqual(len(list((Path(temp) / "profiles").glob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
