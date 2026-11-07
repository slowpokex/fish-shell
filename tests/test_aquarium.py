import json
import random
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


class FishTests(unittest.TestCase):
    W, H = 80, 24

    def make_fish(self, **kw):
        base = dict(species="Рыбка", x=10.0, y=5.0, dx=1, speed=10.0, color=1, nick="n")
        base.update(kw)
        return aquarium.Fish(**base)

    def test_spawn_counts_match(self):
        fish = aquarium.spawn_fish({"Рыбка": 3, "Акула": 1}, self.W, self.H, random.Random(1))
        self.assertEqual(sorted(f.species for f in fish), ["Акула", "Рыбка", "Рыбка", "Рыбка"])

    def test_spawn_more_fish_than_nicks_does_not_crash(self):
        count = len(aquarium.NICKS) + 60
        fish = aquarium.spawn_fish({"Рыбка": count}, self.W, self.H, random.Random(1))
        self.assertEqual(len(fish), count)

    def test_nicks_have_at_least_40(self):
        self.assertGreaterEqual(len(aquarium.NICKS), 40)
        self.assertIn("segfault_петя", aquarium.NICKS)
        self.assertIn("NullPointer_Вася", aquarium.NICKS)

    def test_spawn_positions_inside_tank(self):
        counts = {name: 5 for name in aquarium.SPECIES}
        for f in aquarium.spawn_fish(counts, self.W, self.H, random.Random(2)):
            self.assertGreaterEqual(f.x, 0)
            self.assertLessEqual(f.x, self.W - aquarium.fish_width(f))
            self.assertGreaterEqual(f.y, 1)
            self.assertLessEqual(f.y, self.H - 3)
            self.assertIn(f.dx, (1, -1))
            self.assertIn(f.color, range(1, 7))

    def test_step_turns_at_right_edge(self):
        f = self.make_fish()
        f.x = self.W - aquarium.fish_width(f) - 0.1
        aquarium.step_fish(f, self.W, self.H, 1.0, None)
        self.assertEqual(f.dx, -1)
        self.assertLessEqual(f.x, self.W - aquarium.fish_width(f))

    def test_step_turns_at_left_edge(self):
        f = self.make_fish(x=0.1, dx=-1)
        aquarium.step_fish(f, self.W, self.H, 1.0, None)
        self.assertEqual(f.dx, 1)
        self.assertGreaterEqual(f.x, 0)

    def test_step_clamps_after_shrink(self):
        f = self.make_fish(x=200.0, y=40.0)
        aquarium.step_fish(f, 60, 20, 0.05, None)
        self.assertLessEqual(f.x, 60 - aquarium.fish_width(f))
        self.assertLessEqual(f.y, 20 - 3)

    def test_step_moves_toward_food(self):
        f = self.make_fish(x=20.0, y=5.0, dx=-1)
        aquarium.step_fish(f, self.W, self.H, 0.5, (30.0, 12.0))
        self.assertGreater(f.x, 20.0)
        self.assertGreater(f.y, 5.0)
        self.assertEqual(f.dx, 1)

    def test_step_ignores_far_food(self):
        f = self.make_fish(x=10.0, dx=-1)
        aquarium.step_fish(f, self.W, self.H, 0.1, (70.0, 12.0))
        self.assertEqual(f.dx, -1)
        self.assertEqual(f.y, 5.0)


if __name__ == "__main__":
    unittest.main()
