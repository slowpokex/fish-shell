import json
import tempfile
import unittest
from pathlib import Path

import aquarium

SPECIES = ["a", "b", "c"]


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "aquarium" / "config.json"

    def write_raw(self, text):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")

    def test_load_missing_returns_none(self):
        self.assertIsNone(aquarium.load_config(self.path, SPECIES))

    def test_load_corrupt_json_returns_none(self):
        self.write_raw("{not json")
        self.assertIsNone(aquarium.load_config(self.path, SPECIES))

    def test_load_unknown_species_returns_none(self):
        self.write_raw(json.dumps({"a": 1, "zzz": 2}))
        self.assertIsNone(aquarium.load_config(self.path, SPECIES))

    def test_load_zero_total_returns_none(self):
        self.write_raw(json.dumps({"a": 0, "b": 0}))
        self.assertIsNone(aquarium.load_config(self.path, SPECIES))

    def test_load_non_int_returns_none(self):
        for bad in ('"3"', "2.5"):
            self.write_raw('{"a": %s}' % bad)
            self.assertIsNone(aquarium.load_config(self.path, SPECIES), bad)

    def test_load_clamps_to_0_20(self):
        self.write_raw(json.dumps({"a": 99, "b": -4, "c": 2}))
        self.assertEqual(
            aquarium.load_config(self.path, SPECIES), {"a": 20, "b": 0, "c": 2}
        )

    def test_save_then_load_roundtrip(self):
        counts = {"a": 3, "b": 0, "c": 1}
        self.assertTrue(aquarium.save_config(self.path, counts))
        self.assertEqual(aquarium.load_config(self.path, SPECIES), counts)

    def test_save_unwritable_returns_false(self):
        blocker = Path(self.tmp.name) / "file"
        blocker.write_text("x")
        self.assertFalse(aquarium.save_config(blocker / "config.json", {"a": 1}))


if __name__ == "__main__":
    unittest.main()
