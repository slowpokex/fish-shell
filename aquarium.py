#!/usr/bin/env python3
"""Терминальный аквариум со случайными рыбами и смешными никами."""
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
