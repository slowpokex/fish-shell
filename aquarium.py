#!/usr/bin/env python3
"""Терминальный аквариум со случайными рыбами и смешными никами."""
import curses
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

MAX_PER_SPECIES = 20


# --- конфиг ---------------------------------------------------------------

def config_path():
    return Path.home() / ".config" / "aquarium" / "config.json"


def load_config(path, species):
    """Возвращает {вид: количество} или None, если конфига нет или он негоден."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    counts = {name: 0 for name in species}
    for name, value in data.items():
        if name not in counts:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        counts[name] = max(0, min(MAX_PER_SPECIES, value))
    if sum(counts.values()) == 0:
        return None
    return counts


def save_config(path, counts):
    """Пишет конфиг; при ошибке записи возвращает False."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(counts, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return False
    return True


# --- виды и ники ----------------------------------------------------------

class Species(NamedTuple):
    name: str
    right: list
    left: list
    speed: tuple


_MIRROR = str.maketrans("<>()[]{}/\\", "><)(][}{\\/")


def _mirror(lines):
    width = max(len(line) for line in lines)
    return [line.ljust(width)[::-1].translate(_MIRROR) for line in lines]


def _species(name, right, speed):
    return Species(name, right, _mirror(right), speed)


SPECIES = {s.name: s for s in [
    _species("Рыбка", ["><>"], (6, 12)),
    _species("Рыба-меч", [">=_('>"], (10, 16)),
    _species("Окунь", ["><(((°>"], (5, 10)),
    _species("Акула", [" __/|__", "><_____o>"], (8, 14)),
    _species("Кит", [" ,---.__", "(o     _)>"], (3, 6)),
    _species("Медуза", ["(~~~)", " }{}{"], (1, 3)),
]}

NICKS = [
    "segfault_петя", "NullPointer_Вася", "пельмень_42", "котлета_0xFF",
    "борщ_dev", "дед_инсайд", "git_push_force", "rm_rf_слэш",
    "undefined_behavior", "стековерфлоу", "багфикс_в_пятницу", "docker_ушёл",
    "кофе_без_сахара", "merge_conflict", "tab_vs_space", "вайбкодер",
    "sudo_make_me_fish", "ctrl_c_ctrl_v", "ночной_деплой", "legacy_код",
    "прод_упал", "работает_у_меня", "TODO_потом", "hotfix_final_v3",
    "кот_в_проде", "regex_мастер", "бэкап_был", "оно_само",
    "main_без_ревью", "localhost_forever", "cache_miss", "off_by_one",
    "рекурсия_рекурсия", "memory_leak_олег", "семён_senior", "junior_на_максималках",
    "agile_акула", "скрам_мастер_рыб", "ci_красный", "lgtm_не_читая",
    "node_modules_5ГБ", "pip_install_всё", "комментарий_не_нужен", "чайник_python",
]

COLORS = 6


# --- модель рыбы ----------------------------------------------------------

@dataclass
class Fish:
    species: str
    x: float
    y: float
    dx: int
    speed: float
    color: int
    nick: str


FOOD_RADIUS = 15


def fish_lines(fish):
    sp = SPECIES[fish.species]
    return sp.right if fish.dx > 0 else sp.left


def fish_width(fish):
    return max(len(line) for line in fish_lines(fish))


def _bounds(fish, width, height):
    return max(0, width - fish_width(fish)), max(1, height - 3)


def spawn_fish(counts, width, height, rng):
    nicks = []
    result = []
    for name, count in counts.items():
        for _ in range(count):
            if not nicks:
                nicks = NICKS[:]
                rng.shuffle(nicks)
            fish = Fish(
                species=name, x=0.0, y=1.0, dx=rng.choice((1, -1)),
                speed=rng.uniform(*SPECIES[name].speed),
                color=rng.randint(1, COLORS), nick=nicks.pop(),
            )
            max_x, max_y = _bounds(fish, width, height)
            fish.x = rng.uniform(0, max_x)
            fish.y = float(rng.randint(1, max_y))
            result.append(fish)
    return result


def step_fish(fish, width, height, dt, food):
    max_x, max_y = _bounds(fish, width, height)
    if food is not None and abs(food[0] - fish.x) <= FOOD_RADIUS:
        fish.dx = 1 if food[0] >= fish.x else -1
        step = fish.speed * dt
        fish.x += max(-step, min(step, food[0] - fish.x))
        fish.y += max(-step, min(step, food[1] - fish.y))
    else:
        fish.x += fish.dx * fish.speed * dt
    if fish.x >= max_x:
        fish.x, fish.dx = max_x, -1
    elif fish.x <= 0:
        fish.x, fish.dx = 0.0, 1
    fish.y = max(1.0, min(float(max_y), fish.y))


# --- экран выбора ---------------------------------------------------------

@dataclass
class PickerState:
    counts: dict
    cursor: int = 0


def picker_handle_key(state, key, rng):
    """Меняет состояние; возвращает "start", "quit" или None."""
    names = list(SPECIES)
    name = names[state.cursor]
    if key == "up":
        state.cursor = (state.cursor - 1) % len(names)
    elif key == "down":
        state.cursor = (state.cursor + 1) % len(names)
    elif key == "right":
        state.counts[name] = min(MAX_PER_SPECIES, state.counts[name] + 1)
    elif key == "left":
        state.counts[name] = max(0, state.counts[name] - 1)
    elif key == "space":
        state.counts[name] = 0 if state.counts[name] else 1
    elif key == "r":
        for n in names:
            state.counts[n] = rng.randint(0, 5)
        if sum(state.counts.values()) == 0:
            state.counts[rng.choice(names)] = 1
    elif key == "enter":
        return "start" if sum(state.counts.values()) > 0 else None
    elif key == "q":
        return "quit"
    return None


def safe_addstr(win, y, x, text, attr=0):
    """addstr, не падающий на выходе за границы окна."""
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


_KEYS = {
    curses.KEY_UP: "up", curses.KEY_DOWN: "down",
    curses.KEY_LEFT: "left", curses.KEY_RIGHT: "right",
    ord(" "): "space", 10: "enter", 13: "enter", curses.KEY_ENTER: "enter",
    ord("q"): "q", ord("Q"): "q", ord("r"): "r", ord("R"): "r",
}


def draw_picker(stdscr, state):
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    box_w = 39
    left = max(0, (width - box_w) // 2)
    top = max(0, (height - (len(SPECIES) + 9)) // 2)
    inner = box_w - 2

    def row(i, text, attr=0):
        safe_addstr(stdscr, top + i, left, "│" + text.ljust(inner)[:inner] + "│", attr)

    safe_addstr(stdscr, top, left, "┌─ АКВАРИУМ " + "─" * (inner - 11) + "┐")
    row(1, "")
    row(2, "  Выбери рыб (пробел — вкл/выкл)")
    row(3, "")
    for i, (name, count) in enumerate(state.counts.items()):
        mark = "x" if count else " "
        pointer = "▶" if i == state.cursor else " "
        art = SPECIES[name].right[-1].strip()
        attr = curses.A_BOLD if i == state.cursor else 0
        row(4 + i, f" {pointer} [{mark}] {art:<11} {name:<9} × {count}", attr)
    n = 4 + len(SPECIES)
    row(n, "")
    row(n + 1, "  ←/→ количество   ↑/↓ выбор")
    row(n + 2, "  r — случайный набор   q — выход")
    row(n + 3, "")
    row(n + 4, "      [  ENTER — СТАРТ  ]", curses.A_REVERSE)
    safe_addstr(stdscr, top + n + 5, left, "└" + "─" * inner + "┘")
    stdscr.refresh()


def run_picker(stdscr, initial):
    """Показывает выбор; возвращает {вид: количество} или None при выходе."""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(-1)
    counts = {name: initial.get(name, 0) for name in SPECIES}
    state = PickerState(counts=counts)
    rng = random.Random()
    while True:
        draw_picker(stdscr, state)
        code = stdscr.getch()
        key = _KEYS.get(code)
        if code == curses.KEY_RESIZE or key is None:
            continue
        action = picker_handle_key(state, key, rng)
        if action == "start":
            return dict(state.counts)
        if action == "quit":
            return None
