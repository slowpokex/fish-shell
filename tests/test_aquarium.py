import io
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class PickerTests(unittest.TestCase):
    def setUp(self):
        self.names = list(aquarium.SPECIES)
        self.state = aquarium.PickerState(counts={n: 0 for n in self.names}, cursor=0)
        self.rng = random.Random(3)

    def press(self, *keys):
        result = None
        for key in keys:
            result = aquarium.picker_handle_key(self.state, key, self.rng)
        return result

    def test_picker_right_increments_and_clamps_at_20(self):
        self.press(*["right"] * 25)
        self.assertEqual(self.state.counts[self.names[0]], 20)

    def test_picker_left_clamps_at_0(self):
        self.press("left")
        self.assertEqual(self.state.counts[self.names[0]], 0)

    def test_picker_space_toggles(self):
        self.press("right", "right", "space")
        self.assertEqual(self.state.counts[self.names[0]], 0)
        self.press("space")
        self.assertEqual(self.state.counts[self.names[0]], 1)

    def test_picker_cursor_wraps_up_down(self):
        self.press("up")
        self.assertEqual(self.state.cursor, len(self.names) - 1)
        self.press("down")
        self.assertEqual(self.state.cursor, 0)

    def test_picker_enter_with_zero_total_does_not_start(self):
        self.assertIsNone(self.press("enter"))

    def test_picker_enter_starts_when_total_positive(self):
        self.press("right")
        self.assertEqual(self.press("enter"), "start")

    def test_picker_q_quits(self):
        self.assertEqual(self.press("q"), "quit")

    def test_picker_random_sum_at_least_one(self):
        for seed in range(50):
            self.state.counts = {n: 0 for n in self.names}
            aquarium.picker_handle_key(self.state, "r", random.Random(seed))
            self.assertGreaterEqual(sum(self.state.counts.values()), 1)
            self.assertTrue(all(0 <= v <= 5 for v in self.state.counts.values()))


class TankTests(unittest.TestCase):
    def test_tank_too_small_boundaries(self):
        self.assertTrue(aquarium.tank_too_small(39, 12))
        self.assertTrue(aquarium.tank_too_small(40, 11))
        self.assertFalse(aquarium.tank_too_small(40, 12))

    def test_fish_and_nick_stay_above_weeds(self):
        counts = {name: 10 for name in aquarium.SPECIES}
        for f in aquarium.spawn_fish(counts, 80, 12, random.Random(4)):
            self.assertLessEqual(f.y + len(aquarium.fish_lines(f)), 12 - 4)

    def test_feed_step_food_falls_and_hits_bottom(self):
        foods = [[10.0, 1.0]]
        aquarium.feed_step(foods, [], 20, 1.0)
        self.assertGreater(foods[0][1], 1.0)
        aquarium.feed_step(foods, [], 20, 100.0)
        self.assertEqual(foods, [])

    def test_feed_step_fish_eats_food(self):
        fish = aquarium.Fish("Рыбка", 10.0, 5.0, 1, 5.0, 1, "n")
        foods = [[11.0, 5.0], [60.0, 2.0]]
        aquarium.feed_step(foods, [fish], 24, 0.0)
        self.assertEqual(foods, [[60.0, 2.0]])


class EntryTests(unittest.TestCase):
    def test_choose_start_no_config_is_picker(self):
        self.assertEqual(aquarium.choose_start(None, False), "picker")

    def test_choose_start_with_config_is_aquarium(self):
        self.assertEqual(aquarium.choose_start({"Рыбка": 1}, False), "aquarium")

    def test_choose_start_setup_flag_forces_picker(self):
        self.assertEqual(aquarium.choose_start({"Рыбка": 1}, True), "picker")

    def test_main_non_tty_exits_quietly(self):
        class NotTty(io.StringIO):
            def isatty(self):
                return False

        out = NotTty()
        with mock.patch("sys.stdout", out), mock.patch.object(
            aquarium.curses, "wrapper", side_effect=AssertionError("curses used")
        ):
            self.assertEqual(aquarium.main([]), 0)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
