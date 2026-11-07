#!/usr/bin/env python3
"""Терминальный аквариум со случайными рыбами и смешными никами."""
import curses
import json
import random
import sys
import time
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
    icon: str


_MIRROR = str.maketrans("<>()[]{}/\\`'", "><)(][}{\\/'`")


def _mirror(lines):
    width = max(len(line) for line in lines)
    return [line.ljust(width)[::-1].translate(_MIRROR) for line in lines]


def _species(name, right, speed, icon):
    return Species(name, right, _mirror(right), speed, icon)


# Рисунки смотрят вправо; "o", "°" и "@" считаются глазами и рисуются ярче.
SPECIES = {s.name: s for s in [
    _species("Рыбка", [
        r"  ,--.  ",
        r"><(  o)>",
        r"  `--'  ",
    ], (6, 12), "><(o)>"),
    _species("Рыба-меч", [
        r"       ,___     ",
        r"~~===<  o >-----",
        r"       `--'     ",
    ], (10, 16), "=<o>---"),
    _species("Окунь", [
        r"    ,-./|\,   ",
        r" \,'  |||  `. ",
        r"  >=  ||||  o>",
        r" /`.  |||  ,' ",
        r"    `-\|/'    ",
    ], (5, 10), "><(|o>"),
    _species("Акула", [
        r"           /|     ",
        r"          / |     ",
        r"  _______/  |___  ",
        r"><_____________o_>",
        r"  `-.______,.-'   ",
    ], (8, 14), "><__o_>"),
    _species("Кит", [
        r"          \|/        ",
        r"           |         ",
        r"    ,-----------.__  ",
        r" __/               `.",
        r"/              o    _\>",
        r"\_    ___________,-'  ",
        r"  `--'               ",
    ], (3, 6), "(____o>"),
    _species("Медуза", [
        r"  .-===-.  ",
        r" /       \ ",
        r"| o     o |",
        r" \_______/ ",
        r"  | | | |  ",
        r"  ) ( ) (  ",
    ], (1, 3), "(o_o)"),
    _species("Ангел", [
        r"       /\       ",
        r"      /  \      ",
        r"     /    \     ",
        r" ><(   .  o  )> ",
        r"     \    /     ",
        r"      \  /      ",
        r"       \/       ",
    ], (4, 8), "/o\\"),
    _species("Скат", [
        r"      __       ",
        r"   .-'  `-.    ",
        r"  <  o  o   >~~~",
        r"   `-.____.-'  ",
    ], (4, 9), "<o o>~"),
    _species("Осьминог", [
        r"   ,---.   ",
        r"  ( o o )  ",
        r"  /`---'\  ",
        r" // | | \\ ",
        r" ~~ ~ ~ ~~ ",
    ], (2, 5), "(oo)~"),
    _species("Конёк", [
        r"  _   ",
        r" (o`> ",
        r" ) /  ",
        r" ( (  ",
        r"  ) ) ",
        r" (_/  ",
    ], (2, 4), "(o`>"),
    _species("Пиранья", [
        r"    ,--.   ",
        r"><( o |vvv>",
        r"    `--'   ",
    ], (10, 18), "><(ovv>"),
    _species("Мальки", [
        r" ><>   ",
        r"    ><>",
        r" ><>   ",
    ], (8, 14), "><> ><>"),
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
    # снизу остаются ник, два ряда водорослей и строка подсказки
    return max(0, width - fish_width(fish)), max(1, height - 4 - len(fish_lines(fish)))


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
        art = SPECIES[name].icon
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


# --- экран аквариума ------------------------------------------------------

MIN_WIDTH = 50
MIN_HEIGHT = 16
FOOD_FALL = 4.0
HELP = "q — выход · f — покормить · p — пауза · c — выбор рыб"
MAX_BUBBLES = 40
BUBBLE_RISE = 3.0
BUBBLE_RATE = 0.15  # пузырьков в секунду на одну рыбу
EYES = "o°@"
ACCENT_PAIR = 7
PALETTE = [curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW,
           curses.COLOR_BLUE, curses.COLOR_MAGENTA, curses.COLOR_CYAN]


def relayout_fish(fish_list, old_width, new_width, height, rng):
    """При смене размера окна растягивает x и заново раскидывает рыб по рядам."""
    for fish in fish_list:
        max_x, max_y = _bounds(fish, new_width, height)
        fish.x = min(float(max_x), fish.x * new_width / max(1, old_width))
        fish.y = float(rng.randint(1, max_y))


def accent_positions(fish):
    """Клетки (ряд, столбец) рисунка рыбы, которые рисуются ярче: глаза."""
    return [(r, c) for r, line in enumerate(fish_lines(fish))
            for c, ch in enumerate(line) if ch in EYES]


def bubble_step(bubbles, fish_list, dt, rng):
    """Поднимает пузырьки к поверхности и иногда выпускает новые у морды рыб."""
    for bubble in bubbles:
        bubble[1] -= BUBBLE_RISE * dt
    bubbles[:] = [b for b in bubbles if b[1] >= 1]
    for fish in fish_list:
        if len(bubbles) < MAX_BUBBLES and rng.random() < BUBBLE_RATE * dt:
            head = fish.x + (fish_width(fish) - 1 if fish.dx > 0 else 0)
            bubbles.append([head, fish.y])


def tank_too_small(width, height):
    return width < MIN_WIDTH or height < MIN_HEIGHT


def feed_step(foods, fish_list, height, dt):
    """Роняет корм и убирает съеденный или упавший на дно."""
    for food in foods:
        food[1] += FOOD_FALL * dt
    foods[:] = [
        f for f in foods
        if f[1] < height - 3 and not any(_touches(fish, f) for fish in fish_list)
    ]


def _touches(fish, food):
    rows = len(fish_lines(fish))
    return (fish.x <= food[0] < fish.x + fish_width(fish)
            and round(fish.y) <= round(food[1]) < round(fish.y) + rows)


def _nearest_food(fish, foods):
    near = [f for f in foods if abs(f[0] - fish.x) <= FOOD_RADIUS]
    if not near:
        return None
    best = min(near, key=lambda f: abs(f[0] - fish.x) + abs(f[1] - fish.y))
    return best[0], best[1]


def _init_colors():
    if not (curses.has_colors() and curses.COLORS >= 8):
        return False
    curses.start_color()
    curses.use_default_colors()
    for i, color in enumerate(PALETTE, start=1):
        curses.init_pair(i, color, -1)
    curses.init_pair(ACCENT_PAIR, curses.COLOR_WHITE, -1)
    return True


def draw_aquarium(stdscr, fish_list, foods, bubbles, colors, tick, paused):
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    safe_addstr(stdscr, 0, 0, ("^^^^ " * (width // 5 + 1))[:width - 1])
    for fish in fish_list:
        attr = curses.color_pair(fish.color) if colors else 0
        x, y = int(fish.x), int(fish.y)
        lines = fish_lines(fish)
        for i, line in enumerate(lines):
            safe_addstr(stdscr, y + i, x, line, attr)
        eye = (curses.color_pair(ACCENT_PAIR) if colors else 0) | curses.A_BOLD
        for row, col in accent_positions(fish):
            safe_addstr(stdscr, y + row, x + col, lines[row][col], eye)
        nick_x = max(0, x + (fish_width(fish) - len(fish.nick)) // 2)
        safe_addstr(stdscr, y + len(lines), nick_x, fish.nick[:width - nick_x - 1], attr)
    for bx, by in bubbles:
        safe_addstr(stdscr, int(by), int(bx), "°" if int(by) % 2 else "o")
    for food in foods:
        safe_addstr(stdscr, int(food[1]), int(food[0]), "*")
    green = curses.color_pair(2) if colors else 0
    for x in range(1, width - 1, 7):
        for row in (height - 3, height - 2):
            sway = (tick // 8 + x + row) % 2
            safe_addstr(stdscr, row, x, "}" if sway else "{", green)
    status = HELP + ("  [пауза]" if paused else "")
    safe_addstr(stdscr, height - 1, 0, status[:width - 1])
    stdscr.refresh()


def run_aquarium(stdscr, counts):
    """Крутит аквариум; возвращает "quit" или "setup" (клавиша c)."""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(50)
    colors = _init_colors()
    rng = random.Random()
    height, width = stdscr.getmaxyx()
    size = (width, height)
    fish_list = spawn_fish(counts, width, height, rng)
    foods = []
    bubbles = []
    paused = False
    tick = 0
    last = time.monotonic()
    while True:
        now = time.monotonic()
        dt = min(now - last, 0.2)
        last = now
        height, width = stdscr.getmaxyx()
        if (width, height) != size:
            relayout_fish(fish_list, size[0], width, height, rng)
            size = (width, height)
        code = stdscr.getch()
        if code in (ord("q"), ord("Q")):
            return "quit"
        if code in (ord("c"), ord("C")):
            return "setup"
        if code in (ord("p"), ord("P")):
            paused = not paused
        if code in (ord("f"), ord("F")) and not tank_too_small(width, height):
            foods.append([float(rng.randint(0, width - 2)), 1.0])
        if tank_too_small(width, height):
            stdscr.erase()
            msg = "окно слишком маленькое"
            safe_addstr(stdscr, height // 2, max(0, (width - len(msg)) // 2),
                        msg[:max(0, width - 1)])
            stdscr.refresh()
            continue
        if not paused:
            tick += 1
            for fish in fish_list:
                step_fish(fish, width, height, dt, _nearest_food(fish, foods))
            feed_step(foods, fish_list, height, dt)
            bubble_step(bubbles, fish_list, dt, rng)
        else:
            for fish in fish_list:
                step_fish(fish, width, height, 0.0, None)
        draw_aquarium(stdscr, fish_list, foods, bubbles, colors, tick, paused)


# --- точка входа ----------------------------------------------------------

def choose_start(config, setup_flag):
    return "picker" if config is None or setup_flag else "aquarium"


def main(argv):
    if not sys.stdout.isatty():
        return 0
    path = config_path()
    counts = load_config(path, list(SPECIES))
    stage = choose_start(counts, "--setup" in argv)
    try:
        while True:
            if stage == "picker":
                picked = curses.wrapper(run_picker, counts or {})
                if picked is None:
                    return 0
                counts = picked
                save_config(path, counts)
            if curses.wrapper(run_aquarium, counts) != "setup":
                return 0
            stage = "picker"
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
