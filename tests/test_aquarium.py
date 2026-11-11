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
        self.assertTrue(aquarium.tank_too_small(49, 16))
        self.assertTrue(aquarium.tank_too_small(50, 15))
        self.assertFalse(aquarium.tank_too_small(50, 16))

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


class SpeciesTests(unittest.TestCase):
    def test_twelve_species_with_3_to_7_lines(self):
        self.assertEqual(len(aquarium.SPECIES), 12)
        heights = [len(sp.right) for sp in aquarium.SPECIES.values()]
        self.assertTrue(all(3 <= h <= 7 for h in heights), heights)
        self.assertGreaterEqual(max(heights), 6)

    def test_old_species_names_kept(self):
        for name in ("Рыбка", "Рыба-меч", "Окунь", "Акула", "Кит", "Медуза"):
            self.assertIn(name, aquarium.SPECIES)

    def test_left_art_is_a_full_mirror(self):
        for sp in aquarium.SPECIES.values():
            self.assertEqual(len(sp.left), len(sp.right), sp.name)
            width = max(len(line) for line in sp.right)
            self.assertTrue(all(len(line) == width for line in sp.left), sp.name)
            self.assertEqual(aquarium._mirror(sp.left), [l.ljust(width) for l in sp.right], sp.name)

    def test_every_species_has_icon(self):
        for sp in aquarium.SPECIES.values():
            self.assertTrue(sp.icon, sp.name)

    def test_tall_fish_and_nick_stay_above_weeds_at_min_height(self):
        counts = {name: 10 for name in aquarium.SPECIES}
        for f in aquarium.spawn_fish(counts, 80, 16, random.Random(8)):
            self.assertLessEqual(f.y + len(aquarium.fish_lines(f)), 16 - 4)

    def test_accent_positions_mark_eyes(self):
        fish = aquarium.Fish("Рыбка", 0.0, 1.0, 1, 5.0, 1, "n")
        cells = aquarium.accent_positions(fish)
        self.assertTrue(cells)
        lines = aquarium.fish_lines(fish)
        for row, col in cells:
            self.assertIn(lines[row][col], "o°@")

    def test_old_config_loads_with_new_species_at_zero(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "config.json"
        path.write_text(json.dumps({"Рыбка": 2, "Акула": 1}), encoding="utf-8")
        counts = aquarium.load_config(path, list(aquarium.SPECIES))
        self.assertEqual(counts["Рыбка"], 2)
        self.assertEqual(sum(counts.values()), 3)


class BubbleTests(unittest.TestCase):
    class AlwaysRng:
        def random(self):
            return 0.0

    def make_fish(self, x=10.0):
        return aquarium.Fish("Рыбка", x, 5.0, 1, 5.0, 1, "n")

    def test_bubbles_rise_and_vanish_at_surface(self):
        bubbles = [[5.0, 10.0]]
        aquarium.bubble_step(bubbles, [], 1.0, random.Random(1))
        self.assertLess(bubbles[0][1], 10.0)
        aquarium.bubble_step(bubbles, [], 100.0, random.Random(1))
        self.assertEqual(bubbles, [])

    def test_bubble_comes_from_fish_head(self):
        fish = self.make_fish()
        bubbles = []
        aquarium.bubble_step(bubbles, [fish], 1.0, self.AlwaysRng())
        self.assertEqual(len(bubbles), 1)
        self.assertEqual(bubbles[0][0], fish.x + aquarium.fish_width(fish) - 1)

    def test_bubbles_are_capped(self):
        fish = [self.make_fish() for _ in range(200)]
        bubbles = []
        aquarium.bubble_step(bubbles, fish, 1.0, self.AlwaysRng())
        self.assertLessEqual(len(bubbles), aquarium.MAX_BUBBLES)


class SpeechTests(unittest.TestCase):
    class AlwaysRng(random.Random):
        def random(self):
            return 0.0

    def make_fish(self, species="Рыбка", nick="n", x=10.0, y=5.0, dx=1):
        return aquarium.Fish(species, x, y, dx, 5.0, 1, nick)

    def test_phrases_fit_bubble(self):
        pools = list(aquarium.PHRASES.values())
        pools += [p for d in aquarium.SPECIES_PHRASES.values() for p in d.values()]
        pools += list(aquarium.NICK_PHRASES.values())
        for pool in pools:
            for phrase in pool:
                self.assertLessEqual(len(phrase), 28, phrase)
                self.assertTrue(phrase.isprintable(), phrase)

    def test_lore_keys_exist(self):
        self.assertLessEqual(set(aquarium.SPECIES_PHRASES), set(aquarium.SPECIES))
        self.assertLessEqual(set(aquarium.NICK_PHRASES), set(aquarium.NICKS))
        for events in aquarium.SPECIES_PHRASES.values():
            self.assertLessEqual(set(events), set(aquarium.PHRASES))
            self.assertIn("idle", events)
            self.assertIn("poke", events)

    def test_pick_phrase_uses_event_pools(self):
        fish = self.make_fish("Акула", "ночной_деплой")
        for event in aquarium.PHRASES:
            allowed = set(aquarium.PHRASES[event])
            allowed |= set(aquarium.SPECIES_PHRASES["Акула"].get(event, []))
            if event in ("idle", "poke"):
                allowed |= set(aquarium.NICK_PHRASES["ночной_деплой"])
            rng = random.Random(1)
            for _ in range(200):
                self.assertIn(aquarium.pick_phrase(fish, event, rng), allowed)

    def test_nick_phrases_heard_on_idle_not_on_food(self):
        fish = self.make_fish(nick="ночной_деплой")
        nick = set(aquarium.NICK_PHRASES["ночной_деплой"])
        rng = random.Random(2)
        idle = {aquarium.pick_phrase(fish, "idle", rng) for _ in range(500)}
        eaten = {aquarium.pick_phrase(fish, "food_eaten", rng) for _ in range(500)}
        self.assertTrue(idle & nick)
        self.assertFalse(eaten & nick)

    def test_unknown_nick_still_speaks(self):
        fish = self.make_fish(nick="никто")
        self.assertTrue(aquarium.pick_phrase(fish, "poke", random.Random(3)))

    def test_speech_expires(self):
        class NeverRng(random.Random):
            def random(self):
                return 1.0
        fish = self.make_fish()
        aquarium.say(fish, "poke", random.Random(4))
        aquarium.speech_step([fish], aquarium.SPEECH_TTL + 0.1, NeverRng(0))
        self.assertEqual(fish.speech, "")

    def test_speakers_are_capped(self):
        fish = [self.make_fish() for _ in range(20)]
        rng = self.AlwaysRng(5)
        for _ in range(50):
            aquarium.speech_step(fish, 0.01, rng)
        self.assertEqual(sum(1 for f in fish if f.speech), aquarium.MAX_SPEAKERS)

    def test_feed_step_returns_eaters(self):
        eater = self.make_fish(x=10.0)
        other = self.make_fish(x=60.0, y=12.0)
        foods = [[11.0, 5.0]]
        self.assertEqual(aquarium.feed_step(foods, [eater, other], 24, 0.0), [eater])
        self.assertEqual(aquarium.feed_step([], [eater], 24, 0.0), [])

    def test_nearest_fish(self):
        a, b = self.make_fish(x=10.0), self.make_fish(x=20.0)
        self.assertIs(aquarium.nearest_fish([a, b], 18.0), b)
        self.assertIsNone(aquarium.nearest_fish([a, b], 70.0))

    def test_layout_above_fish_with_connector(self):
        fish = self.make_fish(y=5.0)
        fish.speech = "кто трогал прод?"
        row, col, text, conn = aquarium.speech_layout(fish, 80)
        self.assertEqual((row, text), (3, "( кто трогал прод? )"))
        self.assertEqual(conn, (4, 10 + aquarium.fish_width(fish) - 1))

    def test_layout_near_surface(self):
        fish = self.make_fish(y=2.0)
        fish.speech = "x"
        self.assertEqual(aquarium.speech_layout(fish, 80)[0::3], (1, None))
        fish.y = 1.0
        row, _, _, conn = aquarium.speech_layout(fish, 80)
        self.assertEqual(row, 1 + len(aquarium.fish_lines(fish)) + 1)
        self.assertIsNone(conn)

    def test_layout_stays_on_screen(self):
        for x, dx in ((0.0, -1), (71.0, 1)):
            fish = self.make_fish(x=x, dx=dx)
            fish.speech = "очень длинная реплика тут"
            _, col, text, conn = aquarium.speech_layout(fish, 80)
            self.assertGreaterEqual(col, 0)
            self.assertLess(col + len(text), 80)
            self.assertLess(conn[1], 79)
        fish.speech = "x" * 100
        _, col, text, _ = aquarium.speech_layout(fish, 50)
        self.assertLess(col + len(text), 50)

    def test_no_connector_when_head_offscreen(self):
        fish = self.make_fish(x=-20.0, dx=-1)
        fish.speech = "ААА"
        _, col, _, conn = aquarium.speech_layout(fish, 80)
        self.assertEqual(col, 0)
        self.assertIsNone(conn)


class EasterEggTests(unittest.TestCase):
    X = ord("x")

    def make_fish(self, x=40.0, dx=1):
        return aquarium.Fish("Рыбка", x, 5.0, dx, 5.0, 1, "n")

    def press(self, codes_and_times):
        count, last, fired = 0, 0.0, []
        for code, now in codes_and_times:
            count, last, egg = aquarium.register_x(count, last, code, now)
            fired.append(egg)
        return fired

    def test_five_x_in_a_row_triggers_once(self):
        fired = self.press([(self.X, 1.0 + i * 0.2) for i in range(6)])
        self.assertEqual(fired, [False] * 4 + [True, False])

    def test_capital_x_counts(self):
        fired = self.press([(ord("X"), 1.0 + i * 0.2) for i in range(5)])
        self.assertTrue(fired[-1])

    def test_other_key_resets_but_no_key_does_not(self):
        seq = [(self.X, 1.0), (self.X, 1.1), (-1, 1.2), (self.X, 1.3),
               (ord("f"), 1.4), (self.X, 1.5), (self.X, 1.6), (self.X, 1.7), (self.X, 1.8)]
        self.assertFalse(any(self.press(seq)))
        seq = [(self.X, 1.0), (-1, 1.1), (self.X, 1.2), (self.X, 1.3), (-1, 1.4),
               (self.X, 1.5), (self.X, 1.6)]
        self.assertTrue(self.press(seq)[-1])

    def test_slow_presses_do_not_count(self):
        fired = self.press([(self.X, 1.0 + i * 2.0) for i in range(6)])
        self.assertFalse(any(fired))

    def test_art_is_rectangular_enough_and_mirrors(self):
        art = aquarium.dick_art(30)
        self.assertGreaterEqual(len(art), 8)
        # ствол сверху и снизу одной длины, головка стоит ровно
        self.assertEqual(art[1].index("."), art[2].rindex("|"))
        self.assertEqual(art[2].rindex("|"), art[5].index("`"))
        self.assertEqual(len(aquarium._mirror(art)), len(art))

    def test_monster_spawns_offscreen_and_inside_tank(self):
        for seed in range(10):
            m = aquarium.spawn_monster(80, 30, random.Random(seed))
            w = aquarium.monster_width(m)
            self.assertTrue(m.x + w <= 0 or m.x >= 80)
            self.assertGreaterEqual(m.y, 2)
            self.assertLessEqual(m.y + len(m.lines), 30 - 3)

    def test_monster_scares_fish_ahead_and_leaves(self):
        m = aquarium.spawn_monster(80, 30, random.Random(0))
        near = self.make_fish(x=10.0 if m.dx > 0 else 65.0, dx=-m.dx)
        far = self.make_fish(x=65.0 if m.dx > 0 else 10.0)
        rng = random.Random(1)
        swarm = [m]
        self.assertTrue(aquarium.swarm_step(swarm, [near, far], 80, 0.5, rng))
        self.assertEqual(near.mood, "flee")
        self.assertEqual(near.dx, m.dx)
        self.assertEqual(far.mood, "")
        for _ in range(100):
            if not aquarium.swarm_step(swarm, [near, far], 80, 0.5, rng):
                break
        self.assertEqual(swarm, [])
        self.assertEqual({near.mood, far.mood}, {"return"})

    def test_swarm_is_mixed_one_direction_led_by_big(self):
        for seed in range(20):
            swarm = aquarium.spawn_swarm(100, 30, random.Random(seed))
            heights = sorted(len(m.lines) for m in swarm)
            lo = sum(lo for lo, _ in aquarium.SWARM_SIZE.values())
            hi = sum(hi for _, hi in aquarium.SWARM_SIZE.values())
            self.assertTrue(lo <= len(swarm) <= hi)
            self.assertEqual(set(heights), {1, 5, 9})
            self.assertEqual(len({m.dx for m in swarm}), 1)
            self.assertEqual(swarm[0].delay, 0.0)
            self.assertEqual(len(swarm[0].lines), 9)
            self.assertTrue(all(0 <= m.delay <= aquarium.SWARM_SPREAD for m in swarm))

    def test_fish_outrun_every_dick(self):
        for lo, hi in aquarium.SPEED_RANGE.values():
            self.assertLess(hi, aquarium.FLEE_SPEED)

    def test_every_dick_fits_tank(self):
        for seed in range(30):
            for m in aquarium.spawn_swarm(80, 20, random.Random(seed)):
                self.assertGreaterEqual(m.y, 2)
                self.assertLessEqual(m.y + len(m.lines), 20 - 3)

    def test_delayed_dick_waits_and_does_not_scare(self):
        m = aquarium.spawn_monster(80, 30, random.Random(0), "small", dx=1, delay=1.0)
        fish = self.make_fish(x=1.0)
        x0 = m.x
        self.assertTrue(aquarium.monster_step(m, [fish], 80, 0.5, random.Random(1)))
        self.assertEqual((m.x, fish.mood), (x0, ""))

    def test_fish_wait_until_last_dick_is_gone(self):
        rng = random.Random(2)
        first = aquarium.spawn_monster(80, 30, rng, "small", dx=1)
        late = aquarium.spawn_monster(80, 30, rng, "small", dx=1, delay=100.0)
        fish = self.make_fish(x=5.0)
        swarm = [first, late]
        for _ in range(20):
            aquarium.swarm_step(swarm, [fish], 80, 0.5, rng)
        self.assertEqual(swarm, [late])
        self.assertEqual(fish.mood, "flee")

    def test_medium_and_small_art(self):
        art = aquarium.dick_art_medium(14)
        self.assertEqual(art[1].index("."), art[2].index("|"))
        self.assertEqual(art[2].index("|"), art[3].rindex("|"))
        self.assertEqual(art[3].rindex("|"), art[4].rindex("`"))
        self.assertEqual(aquarium.dick_art_small(5), ["8=====D"])

    def test_fleeing_fish_leaves_screen_and_waits(self):
        fish = self.make_fish(x=40.0, dx=1)
        fish.mood = "flee"
        for _ in range(20):
            self.assertFalse(aquarium.step_fish(fish, 80, 30, 0.5, None))
        # спряталась вместе с ником, но не уплыла в бесконечность
        self.assertGreaterEqual(fish.x, 80)
        self.assertLessEqual(fish.x, 80 + aquarium.fish_width(fish) + len(fish.nick) + 2)

    def test_returning_fish_swims_back_home(self):
        fish = self.make_fish(x=82.0, dx=1)
        fish.mood = "return"
        max_x, _ = aquarium._bounds(fish, 80, 30)
        home = False
        for _ in range(100):
            if aquarium.step_fish(fish, 80, 30, 0.2, None):
                home = True
                break
            self.assertEqual(fish.dx, -1)
        self.assertTrue(home)
        self.assertEqual(fish.mood, "")
        self.assertLessEqual(fish.x, max_x)

    def test_panic_and_home_phrases_exist(self):
        fish = self.make_fish()
        for event in ("panic", "home"):
            self.assertTrue(aquarium.pick_phrase(fish, event, random.Random(0)))

    def test_clip_addstr(self):
        win = mock.Mock()
        aquarium.clip_addstr(win, 3, -2, "abcdef", 80)
        win.addstr.assert_called_with(3, 0, "cdef", 0)
        win.reset_mock()
        aquarium.clip_addstr(win, 3, 76, "abcdef", 80)
        win.addstr.assert_called_with(3, 76, "abc", 0)
        win.reset_mock()
        aquarium.clip_addstr(win, 3, -10, "abc", 80)
        win.addstr.assert_not_called()


class ShootingTests(unittest.TestCase):
    def onscreen(self, kind, dx, x):
        m = aquarium.spawn_monster(100, 30, random.Random(0), kind, dx=dx)
        m.x, m.cooldown = x, 0.0
        return m

    def test_muzzle_is_the_tip_row(self):
        rng = random.Random(0)
        self.assertEqual(aquarium.spawn_monster(100, 30, rng, "big", dx=1).muzzle, 3)
        self.assertEqual(aquarium.spawn_monster(100, 30, rng, "medium", dx=1).muzzle, 3)
        self.assertEqual(aquarium.spawn_monster(100, 30, rng, "small", dx=-1).muzzle, 0)

    def test_fires_forward_from_tip_with_flash(self):
        for dx in (1, -1):
            m = self.onscreen("big", dx, 20.0)
            shots, effects = [], []
            aquarium.fire_step([m], shots, effects, 100, 0.05, random.Random(1))
            self.assertEqual(len(shots), 1)
            shot = shots[0]
            self.assertEqual((shot.dx, shot.y), (dx, m.y + m.muzzle))
            tip = m.x + aquarium.monster_width(m) if dx > 0 else m.x - 3
            self.assertEqual(shot.x, tip)
            self.assertGreater(shot.speed, aquarium.FLEE_SPEED)
            self.assertIn(effects[0][2], aquarium.FLASHES)
            self.assertGreater(m.cooldown, 0)

    def test_no_fire_while_waiting_offscreen_or_cooling(self):
        m = self.onscreen("small", 1, 20.0)
        m.delay = 1.0
        hidden = self.onscreen("small", 1, -50.0)
        cooling = self.onscreen("small", 1, 20.0)
        cooling.cooldown = 5.0
        shots = []
        aquarium.fire_step([m, hidden, cooling], shots, [], 100, 0.05, random.Random(1))
        self.assertEqual(shots, [])

    def test_shots_are_capped(self):
        ms = [self.onscreen("small", 1, 10.0) for _ in range(100)]
        shots = []
        aquarium.fire_step(ms, shots, [], 100, 0.05, random.Random(1))
        self.assertEqual(len(shots), aquarium.MAX_SHOTS)

    def test_shot_flies_and_leaves_screen(self):
        shots = [aquarium.Shot(50.0, 5, 1, 60.0)]
        aquarium.shot_step(shots, [], [], 100, 0.1, random.Random(1))
        self.assertEqual(shots[0].x, 56.0)
        aquarium.shot_step(shots, [], [], 100, 1.0, random.Random(1))
        self.assertEqual(shots, [])

    def test_shot_hits_fish_splats_and_fish_screams(self):
        class Always(random.Random):
            def random(self):
                return 0.0
        fish = aquarium.Fish("Рыбка", 30.0, 5.0, 1, 5.0, 1, "n")
        shots = [aquarium.Shot(26.0, 6, 1, 20.0)]
        effects = []
        aquarium.shot_step(shots, effects, [fish], 100, 0.1, Always(1))
        self.assertEqual(shots, [])
        self.assertIn(effects[0][2], aquarium.SPLATS)
        self.assertIn(fish.speech, aquarium.PHRASES["hit"])

    def test_shot_misses_other_row(self):
        fish = aquarium.Fish("Рыбка", 30.0, 5.0, 1, 5.0, 1, "n")
        shots = [aquarium.Shot(26.0, 12, 1, 20.0)]
        aquarium.shot_step(shots, [], [fish], 100, 0.1, random.Random(1))
        self.assertEqual(len(shots), 1)

    def test_effects_fade(self):
        effects = [[1, 1, "пиу!", 0.3], [1, 1, "*шлёп*", 0.8]]
        aquarium.effect_step(effects, 0.5)
        self.assertEqual([e[2] for e in effects], ["*шлёп*"])


class RiderTests(unittest.TestCase):
    def test_cries_fit_bubble(self):
        for cry in aquarium.RIDER_CRIES + aquarium.TINY_CRIES:
            self.assertLessEqual(len(cry), 28, cry)
        self.assertIn("ЗА ВАЙБ-КОД И ДВОР!", aquarium.RIDER_CRIES)
        self.assertIn("Я СТРЕЛЯЮ В УПОР!", aquarium.RIDER_CRIES)

    def test_saber_swings_through_three_frames(self):
        m = aquarium.spawn_monster(100, 30, random.Random(0), "big", dx=1)
        frames = {tuple(aquarium.rider_layout(m, t * aquarium.SWING_TICKS)[2])
                  for t in range(3)}
        self.assertEqual(len(frames), 3)

    def test_rider_sits_on_shaft_and_mirrors(self):
        for kind in ("big", "medium", "small"):
            for dx in (1, -1):
                m = aquarium.spawn_monster(100, 30, random.Random(1), kind, dx=dx)
                m.x = 10.0
                top, col, lines = aquarium.rider_layout(m, 0)
                w = aquarium.monster_width(m)
                # над хуем, внутри его длины, ноги на нужном ряду
                self.assertTrue(10 <= col and col + len(lines[0]) <= 10 + w, (kind, dx))
                bottom = top + len(lines) - 1
                self.assertEqual(bottom, m.y if kind != "small" else m.y - 1)
                # крик над казаком не залезает на поверхность воды
                self.assertGreaterEqual(top - 1, 1, (kind, dx))
                if kind != "small":
                    # шашка (=) с той стороны, куда он скачет
                    arm = lines[2]
                    saber_ahead = arm.index("=") > arm.index("#")
                    self.assertEqual(saber_ahead, dx > 0, (kind, dx))

    def test_riders_shout_then_pause(self):
        m = aquarium.spawn_monster(100, 30, random.Random(2), "big", dx=1)
        m.shout_ttl = 0.0
        rng = random.Random(3)
        aquarium.rider_step([m], 0.05, rng)
        self.assertIn(m.speech, aquarium.RIDER_CRIES)
        aquarium.rider_step([m], aquarium.SHOUT_TIME[1] + 0.1, rng)
        self.assertEqual(m.speech, "")
        tiny = aquarium.spawn_monster(100, 30, random.Random(2), "small", dx=1)
        tiny.shout_ttl = 0.0
        aquarium.rider_step([tiny], 0.05, rng)
        self.assertIn(tiny.speech, aquarium.TINY_CRIES)

    def test_waiting_rider_is_silent(self):
        m = aquarium.spawn_monster(100, 30, random.Random(2), "big", dx=1, delay=2.0)
        m.shout_ttl = 0.0
        aquarium.rider_step([m], 0.05, random.Random(3))
        self.assertEqual(m.speech, "")


class RelayoutTests(unittest.TestCase):
    def test_relayout_spreads_fish_after_shrink_then_grow(self):
        rng = random.Random(5)
        fish = aquarium.spawn_fish({"Рыбка": 20}, 120, 40, rng)
        for f in fish:
            aquarium.step_fish(f, 60, 12, 0.05, None)
        aquarium.relayout_fish(fish, 60, 120, 40, rng)
        rows = {round(f.y) for f in fish}
        self.assertGreater(len(rows), 5)
        for f in fish:
            max_x, max_y = aquarium._bounds(f, 120, 40)
            self.assertTrue(0 <= f.x <= max_x)
            self.assertTrue(1 <= f.y <= max_y)


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
