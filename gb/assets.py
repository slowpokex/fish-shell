#!/usr/bin/env python3
"""Генератор графики и текстов для Game Boy Color версии аквариума.

Читает тексты из aquarium.py, рисует тайлы из ASCII-карт пикселей и пишет
C-файлы для GBDK-2020 в gb/src/gen_*.c|h. Запускается из gb/build.py.

Обозначения пикселей в картах:
  '.' — прозрачный (у спрайтов) или фон (у тайлов фона), цвет 0
  'd' — тёмный контур, цвет 1
  'b' — основной цвет, цвет 2
  'w' — светлый (глаза, блики), цвет 3
"""
import math
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aquarium as aq  # noqa: E402

SRC = Path(__file__).resolve().parent / "src"
LINE = 18          # символов в строке диалога
LABEL = 18         # символов в заголовке диалога (ник)
MAX_FISH = 8
EVENTS = ["idle", "food_seen", "food_eaten", "poke", "panic", "home", "hit"]

# --- шрифт 7×7 (8-я строка и 8-й столбец — пробел между буквами) ------------

_G = {}


def glyph(chars, *rows):
    assert len(rows) == 7, chars
    for r in rows:
        assert len(r) == 7, (chars, r)
    for ch in chars:
        _G[ch] = rows


glyph("AА", "..###..", ".#...#.", "#.....#", "#######", "#.....#", "#.....#", "#.....#")
glyph("BВ", "######.", "#.....#", "#.....#", "######.", "#.....#", "#.....#", "######.")
glyph("CС", ".#####.", "#.....#", "#......", "#......", "#......", "#.....#", ".#####.")
glyph("D", "#####..", "#....#.", "#.....#", "#.....#", "#.....#", "#....#.", "#####..")
glyph("EЕ", "#######", "#......", "#......", "######.", "#......", "#......", "#######")
glyph("F", "#######", "#......", "#......", "######.", "#......", "#......", "#......")
glyph("G", ".#####.", "#.....#", "#......", "#..####", "#.....#", "#.....#", ".#####.")
glyph("HН", "#.....#", "#.....#", "#.....#", "#######", "#.....#", "#.....#", "#.....#")
glyph("I", ".#####.", "...#...", "...#...", "...#...", "...#...", "...#...", ".#####.")
glyph("J", "..#####", "....#..", "....#..", "....#..", "#...#..", "#...#..", ".###...")
glyph("KК", "#....#.", "#...#..", "#..#...", "###....", "#..#...", "#...#..", "#....#.")
glyph("L", "#......", "#......", "#......", "#......", "#......", "#......", "#######")
glyph("MМ", "#.....#", "##...##", "#.#.#.#", "#..#..#", "#.....#", "#.....#", "#.....#")
glyph("N", "#.....#", "##....#", "#.#...#", "#..#..#", "#...#.#", "#....##", "#.....#")
glyph("OО", ".#####.", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#", ".#####.")
glyph("PР", "######.", "#.....#", "#.....#", "######.", "#......", "#......", "#......")
glyph("Q", ".#####.", "#.....#", "#.....#", "#.....#", "#...#.#", "#....#.", ".####.#")
glyph("R", "######.", "#.....#", "#.....#", "######.", "#...#..", "#....#.", "#.....#")
glyph("S", ".#####.", "#.....#", "#......", ".#####.", "......#", "#.....#", ".#####.")
glyph("TТ", "#######", "...#...", "...#...", "...#...", "...#...", "...#...", "...#...")
glyph("U", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#", ".#####.")
glyph("V", "#.....#", "#.....#", "#.....#", ".#...#.", ".#...#.", "..#.#..", "...#...")
glyph("W", "#.....#", "#.....#", "#.....#", "#..#..#", "#.#.#.#", "##...##", "#.....#")
glyph("XХ", "#.....#", ".#...#.", "..#.#..", "...#...", "..#.#..", ".#...#.", "#.....#")
glyph("Y", "#.....#", ".#...#.", "..#.#..", "...#...", "...#...", "...#...", "...#...")
glyph("Z", "#######", ".....#.", "....#..", "...#...", "..#....", ".#.....", "#######")
glyph("Б", "#######", "#......", "#......", "######.", "#.....#", "#.....#", "######.")
glyph("Г", "#######", "#......", "#......", "#......", "#......", "#......", "#......")
glyph("Д", "..####.", ".#...#.", ".#...#.", ".#...#.", ".#...#.", "#######", "#.....#")
glyph("Ж", "#..#..#", ".#.#.#.", "..###..", "...#...", "..###..", ".#.#.#.", "#..#..#")
glyph("З3", ".#####.", "#.....#", "......#", "..####.", "......#", "#.....#", ".#####.")
glyph("И", "#.....#", "#....##", "#...#.#", "#..#..#", "#.#...#", "##....#", "#.....#")
glyph("Й", "..###..", "#.....#", "#....##", "#...#.#", "#..#..#", "#.#...#", "##....#")
glyph("Л", "..#####", ".#....#", ".#....#", ".#....#", ".#....#", ".#....#", "#.....#")
glyph("П", "#######", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#")
glyph("У", "#.....#", "#.....#", "#.....#", ".######", "......#", "#.....#", ".#####.")
glyph("Ф", "...#...", ".#####.", "#..#..#", "#..#..#", ".#####.", "...#...", "...#...")
glyph("Ц", "#....#.", "#....#.", "#....#.", "#....#.", "#....#.", "#######", "......#")
glyph("Ч", "#.....#", "#.....#", "#.....#", ".######", "......#", "......#", "......#")
glyph("Ш", "#..#..#", "#..#..#", "#..#..#", "#..#..#", "#..#..#", "#..#..#", "#######")
glyph("Щ", "#.#.#..", "#.#.#..", "#.#.#..", "#.#.#..", "#.#.#..", "######.", ".....#.")
glyph("Ъ", "##.....", ".#.....", ".#.....", ".#####.", ".#....#", ".#....#", ".#####.")
glyph("Ы", "#.....#", "#.....#", "#.....#", "####..#", "#...#.#", "#...#.#", "####..#")
glyph("Ь", "#......", "#......", "#......", "######.", "#.....#", "#.....#", "######.")
glyph("Э", ".#####.", "#.....#", "......#", "..#####", "......#", "#.....#", ".#####.")
glyph("Ю", "#..###.", "#.#...#", "#.#...#", "###...#", "#.#...#", "#.#...#", "#..###.")
glyph("Я", ".######", "#.....#", "#.....#", ".######", "...#..#", "..#...#", "##....#")
glyph("Ё", ".#..#..", "#######", "#......", "######.", "#......", "#......", "#######")
glyph("0", ".#####.", "#....##", "#...#.#", "#..#..#", "#.#...#", "##....#", ".#####.")
glyph("1", "...#...", "..##...", ".#.#...", "...#...", "...#...", "...#...", ".#####.")
glyph("2", ".#####.", "#.....#", "......#", "..####.", ".#.....", "#......", "#######")
glyph("4", "....##.", "...#.#.", "..#..#.", ".#...#.", "#######", ".....#.", ".....#.")
glyph("5", "#######", "#......", "######.", "......#", "......#", "#.....#", ".#####.")
glyph("6", ".#####.", "#......", "#......", "######.", "#.....#", "#.....#", ".#####.")
glyph("7", "#######", "......#", ".....#.", "....#..", "...#...", "...#...", "...#...")
glyph("8", ".#####.", "#.....#", "#.....#", ".#####.", "#.....#", "#.....#", ".#####.")
glyph("9", ".#####.", "#.....#", "#.....#", ".######", "......#", ".....#.", ".####..")
glyph(" ", *["......."] * 7)
glyph("!", "...#...", "...#...", "...#...", "...#...", "...#...", ".......", "...#...")
glyph("#", "..#.#..", "..#.#..", "#######", "..#.#..", "#######", "..#.#..", "..#.#..")
glyph("$", "...#...", ".#####.", "#..#...", ".#####.", "...#..#", ".#####.", "...#...")
glyph("%", "##....#", "##...#.", "....#..", "...#...", "..#....", ".#...##", "#....##")
glyph("(", "....#..", "...#...", "..#....", "..#....", "..#....", "...#...", "....#..")
glyph(")", "..#....", "...#...", "....#..", "....#..", "....#..", "...#...", "..#....")
glyph("*", ".......", "#..#..#", ".#.#.#.", "..###..", ".#.#.#.", "#..#..#", ".......")
glyph("+", ".......", "...#...", "...#...", "#######", "...#...", "...#...", ".......")
glyph(",", ".......", ".......", ".......", ".......", "...##..", "...#...", "..#....")
glyph("-", ".......", ".......", ".......", ".#####.", ".......", ".......", ".......")
glyph(".", ".......", ".......", ".......", ".......", ".......", "..##...", "..##...")
glyph("/", "......#", ".....#.", "....#..", "...#...", "..#....", ".#.....", "#......")
glyph(":", ".......", "..##...", "..##...", ".......", "..##...", "..##...", ".......")
glyph("<", ".....#.", "....#..", "...#...", "..#....", "...#...", "....#..", ".....#.")
glyph(">", ".#.....", "..#....", "...#...", "....#..", "...#...", "..#....", ".#.....")
glyph("=", ".......", ".......", "#######", ".......", "#######", ".......", ".......")
glyph("?", ".#####.", "#.....#", "......#", "...##..", "...#...", ".......", "...#...")
glyph("^", "...#...", "..#.#..", ".#...#.", ".......", ".......", ".......", ".......")
glyph("_", ".......", ".......", ".......", ".......", ".......", ".......", "#######")
glyph("«", ".......", "..#..#.", ".#..#..", "#..#...", ".#..#..", "..#..#.", ".......")
glyph("»", ".......", ".#..#..", "..#..#.", "...#..#", "..#..#.", ".#..#..", ".......")
glyph("—", ".......", ".......", ".......", "#######", ".......", ".......", ".......")
glyph("…", ".......", ".......", ".......", ".......", ".......", ".......", "#..#..#")
glyph("×", ".......", ".#...#.", "..#.#..", "...#...", "..#.#..", ".#...#.", ".......")
glyph("▶", "#......", "##.....", "###....", "####...", "###....", "##.....", "#......")
glyph("'", "...#...", "...#...", "..#....", ".......", ".......", ".......", ".......")
glyph('"', "..#.#..", "..#.#..", ".......", ".......", ".......", ".......", ".......")
glyph("~", ".......", ".......", ".##...#", "#..#.#.", "....#..", ".......", ".......")
glyph("@", ".#####.", "#.....#", "#.###.#", "#.#.#.#", "#.####.", "#......", ".#####.")
glyph("&", ".###...", "#...#..", ".#.#...", "..#....", ".#.#..#", "#...##.", ".###..#")

# --- спрайты (8×16): рисунки смотрят вправо, высота 16 ----------------------

FISH = {
    "Рыбка": [
        "................",
        "................",
        "................",
        ".....dddddd.....",
        "d...dbbbbbbdd...",
        "dd.dbbbbbbbwwd..",
        "dbddbbbbbbbwddd.",
        "dbbbbbbbbbbbbbbd",
        "dbddbbbbbbbbbdd.",
        "dd.dbbbbbbbbbd..",
        "d...ddbbbbbdd...",
        "......ddddd.....",
        "................",
        "................",
        "................",
        "................",
    ],
    "Рыба-меч": [
        "........................",
        "........................",
        "........................",
        "........................",
        "......dd................",
        "d....dbbdddd............",
        "dd..dbbbbbbbdd..........",
        "dbddbbbbbbbwwbd.........",
        "dbbbbbbbbbbwdbbdddddddd.",
        "dbddbbbbbbbbbbd.........",
        "dd..dbbbbbbbdd..........",
        "d....dbbdddd............",
        "......dd................",
        "........................",
        "........................",
        "........................",
    ],
    "Окунь": [
        "........................",
        "........d.d.d...........",
        ".......dbdbdbd..........",
        "......dbbbbbbbdd........",
        "d...ddbbdbbdbbbbdd......",
        "dd.dbbbbdbbdbbbbbbd.....",
        "dbdbbbbbdbbdbbbbwwbd....",
        "dbbbbbbbdbbdbbbbwdbbd...",
        "dbbbbbbbdbbdbbbbbbbbbd..",
        "dbdbbbbbdbbdbbbbbbbdd...",
        "dd.dbbbbdbbdbbbbbbd.....",
        "d...ddbbdbbdbbbbdd......",
        "......dbbbbbbbdd........",
        ".......dd..dd...........",
        "........................",
        "........................",
    ],
    "Акула": [
        "................................",
        "................................",
        "..............dd................",
        ".............dbd................",
        "............dbbd................",
        "d..........dbbbd................",
        "dd......ddddbbbbdddddddd........",
        "dbd...ddbbbbbbbbbbbbbbbbddd.....",
        "dbbddddbbbbbbbbbbbbbbbbwwbbdd...",
        "dbbbbbbbbbbbbbbbbbbbbbbwdbbbbbd.",
        "dbbddddwwwwwwwwwwwwwwwwwwwwwdd..",
        "dbd...ddwwwwwwwwwwwwwwwwwwdd....",
        "dd......dddddddddbdddddddd......",
        "d...............dbd.............",
        "................dd..............",
        "................................",
    ],
    "Кит": [
        "................................",
        "......................w.w.......",
        ".......................w........",
        ".......................w........",
        "...............ddddddddd........",
        "............ddbbbbbbbbbbdd......",
        "d.........ddbbbbbbbbbbbbbbdd....",
        "dd......ddbbbbbbbbbbbbbbbbbbd...",
        "dbd...ddbbbbbbbbbbbbbbbbbwwbd...",
        "dbbdddbbbbbbbbbbbbbbbbbbbwdbbd..",
        "dbbbbbbbbbbbbbbbbbbbbbbbbbbbbbd.",
        "dbbdddwwwwwwwwwwwwwwwwwwwwwwwd..",
        "dbd...ddwwwwwwwwwwwwwwwwwwwdd...",
        "dd......ddddddddddddddddddd.....",
        "d...............................",
        "................................",
    ],
    "Медуза": [
        "....dddddddd....",
        "..ddbbbbbbbbdd..",
        ".dbbbwbbbbbbbbd.",
        "dbbbbbbbbbbbbbbd",
        "dbbwdbbbbbbwdbbd",
        "dbbbbbbbbbbbbbbd",
        ".dddddddddddddd.",
        "..d.d..d..d.d...",
        "..b.b..b..b.b...",
        ".b..b.b..b..b...",
        ".b...b...b...b..",
        "..b..b..b...b...",
        "..b...b..b.b....",
        ".b...b....b.b...",
        "................",
        "................",
    ],
    "Ангел": [
        "......dd........",
        ".....dbbd.......",
        "....dbdbd.......",
        "...dbbdbbd......",
        "d.dbbbdbbbdd....",
        "dddbbbdbbbbwwd..",
        "dbbbbbdbbbbwdbd.",
        "dddbbbdbbbbbbbd.",
        "d.dbbbdbbbbbdd..",
        "...dbbdbbbdd....",
        "....dbdbbd......",
        ".....dbbd.......",
        "......dd........",
        "................",
        "................",
        "................",
    ],
    "Скат": [
        "........................",
        "........................",
        "........................",
        "........................",
        "...........dddd.........",
        ".........ddbbbbdd.......",
        ".......ddbbbbbbbbdd.....",
        ".....ddbbbbbbbbwdbbdd...",
        "dddddbbbbbbbbbbbbbbbbdd.",
        ".....ddbbbbbbbbwdbbdd...",
        ".......ddbbbbbbbbdd.....",
        ".........ddbbbbdd.......",
        "...........dddd.........",
        "........................",
        "........................",
        "........................",
    ],
    "Осьминог": [
        "................",
        "....dddddd......",
        "..ddbbbbbbdd....",
        ".dbbbbbbbbbbd...",
        ".dbwdbbbbwdbd...",
        ".dbbbbbbbbbbd...",
        ".dbbbddddbbbd...",
        "..dbbbbbbbbd....",
        "..dbbdbbdbbd....",
        ".db.db.db.db.d..",
        ".b..b..b..b..b..",
        "b..b...b...b..b.",
        "b...b.b...b...b.",
        ".b..........b...",
        "................",
        "................",
    ],
    "Конёк": [
        "......ddd.......",
        ".....dbbbd......",
        ".....dbwdbddd...",
        ".....dbbbbbbbd..",
        "......dbbdddd...",
        ".....dbbbd......",
        "....dbbbbbd.....",
        "...ddbbbbbd.....",
        "....dbbbbbd.....",
        ".....dbbbbd.....",
        "......dbbd......",
        "......dbd.......",
        ".....dbd..dd....",
        ".....db..dbd....",
        "......dbbbd.....",
        ".......ddd......",
    ],
    "Пиранья": [
        "................",
        "................",
        "................",
        "....ddddddd.....",
        "d..dbbbbbbbdd...",
        "dddbbbbbbbbwwd..",
        "dbbbbbbbbbbwdbd.",
        "dbbbbbbbbbbbwdw.",
        "dbbbbbbbbbbbd...",
        "dbbbbbbbbbbbwdw.",
        "dddbbbbbbbbbbd..",
        "d..dbbbbbbbdd...",
        "....ddddddd.....",
        "................",
        "................",
        "................",
    ],
    "Мальки": [
        "................",
        "..d.ddd.........",
        "..ddbbwd........",
        "..d.ddd.........",
        "................",
        "................",
        "........d.ddd...",
        "........ddbbwd..",
        "........d.ddd...",
        "................",
        "................",
        "...d.ddd........",
        "...ddbbwd.......",
        "...d.ddd........",
        "................",
        "................",
    ],
}

RIDER_BODY = [
    "....dddddd......",
    "...dddddddd.....",
    "...dddddddd.....",
    "..dwwwwwwwwd....",
    ".ddwdwwwwdwdd...",
    ".ddwwwwwwwwdd...",
    "..dwwddddwwd....",
    "...dwwwwwwd.....",
    "....dbbbbd......",
    "...dbbbbbbd.....",
    "..dbbdbbdbbbd...",
    "..dbbbbbbbbd....",
    "..dbbdbbdbbd....",
    "...dbbbbbbd.....",
    "...dd....dd.....",
    "..dd......dd....",
]

SABER = [  # вверх, вперёд, вниз; рука в рядах 9–10 слева
    ["........", ".......w", "......ww", ".....ww.", "....ww..", "...ww...",
     "..ww....", ".ww.....", "dd......", "bd......", "........", "........",
     "........", "........", "........", "........"],
    ["........", "........", "........", "........", "........", "........",
     "........", "........", "........", "bdwwwwww", "d.......", "........",
     "........", "........", "........", "........"],
    ["........", "........", "........", "........", "........", "........",
     "........", "........", "........", "bd......", ".dw.....", "..ww....",
     "...ww...", "....ww..", ".....ww.", "......ww"],
]

TINY_RIDER = [  # казачок 8×8 в верхней половине спрайта, три взмаха
    ["......w.", ".ddd.w..", ".www.w..", ".www.w..", "..bbw...", ".bbb....",
     ".bbb....", ".d.d...."],
    ["........", ".ddd....", ".www....", ".www....", "..bbwwww", ".bbb....",
     ".bbb....", ".d.d...."],
    ["........", ".ddd....", ".www....", ".www....", "..bb....", ".bbbw...",
     ".bbb.w..", ".d.d..w."],
]

SHOT = ["........", "........", "......w.", ".w...www", "w.w.wwww", "...w.ww.",
        "........", "........"]
SPLAT = ["........", ".w...w..", "..w.w...", "wwwwwww.", "..www...", ".w.w.w..",
         "w..w..w.", "........"]
FOOD = ["........", "........", "...dd...", "..dbbd..", "..dbbd..", "...dd...",
        "........", "........"]
BUBBLE = ["........", "..ww....", ".w..w...", ".w..w...", "..ww....", "........",
          "........", "........"]
CURSOR = [".wwwww..", "..www...", "...w....", "........", "........", "........",
          "........", "........"]
MARK = ["...ww...", "...ww...", "...ww...", "...ww...", "........", "...ww...",
        "........", "........"]


def dick_shape(w, h, balls, shaft, glans, slit=True, veins=True):
    """Процедурный хуй: круги яиц, прямоугольник ствола, эллипс головки."""
    inside = [[False] * w for _ in range(h)]
    for (cx, cy, r) in balls:
        for y in range(h):
            for x in range(w):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    inside[y][x] = True
    x0, y0, x1, y1 = shaft
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            inside[y][x] = True
    gx, gy, rx, ry = glans
    for y in range(h):
        for x in range(w):
            if ((x - gx) / rx) ** 2 + ((y - gy) / ry) ** 2 <= 1.0:
                inside[y][x] = True
    rows = [["."] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not inside[y][x]:
                continue
            edge = any(
                not (0 <= y + dy < h and 0 <= x + dx < w and inside[y + dy][x + dx])
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
            rows[y][x] = "d" if edge else "b"
    # шов между яйцами
    mid = (balls[0][1] + balls[1][1]) // 2
    for x in range(0, x0):
        if inside[mid][x]:
            rows[mid][x] = "d"
    # граница головки
    for y in range(h):
        x = int(gx - rx * math.sqrt(max(0.0, 1 - ((y - gy) / ry) ** 2)))
        if 0 <= x < w and inside[y][x] and y0 <= y <= y1:
            rows[y][x] = "d"
    # блики
    for x in range(x0 + 2, x1 - 2, 2):
        if rows[y0 + 2][x] == "b":
            rows[y0 + 2][x] = "w"
    for (cx, cy, r) in balls:
        for (hx, hy) in ((cx - r // 2, cy - r // 2), (cx - r // 2 + 1, cy - r // 2)):
            if 0 <= hy < h and 0 <= hx < w and rows[hy][hx] == "b":
                rows[hy][hx] = "w"
    if veins and y1 - y0 > 6:
        vy = (y0 + y1) // 2
        for x in range(x0 + 4, x1 - 4):
            yy = vy + int(round(1.5 * math.sin(x / 3.0)))
            if rows[yy][x] == "b":
                rows[yy][x] = "d"
    if slit:
        tip = int(gx + rx) - 1
        for x in range(tip - max(1, int(rx // 3)), tip):
            if 0 <= x < w and rows[gy][x] in "bw":
                rows[gy][x] = "d"
    return ["".join(r) for r in rows]


BIG_DICK = dick_shape(96, 32, [(11, 9, 9), (11, 22, 9)], (14, 9, 80, 22), (85, 16, 10.5, 13.5))
MEDIUM_DICK = dick_shape(32, 16, [(4, 5, 4), (4, 11, 4)], (6, 5, 25, 11), (27, 8, 4.5, 6.5),
                         veins=False)
SMALL_DICK = dick_shape(16, 16, [(2, 6, 2), (2, 10, 2)], (3, 6, 11, 10), (12, 8, 3.2, 3.5),
                        veins=False)

# --- фон ---------------------------------------------------------------------

WATER = ["........"] * 8
WAVE = ["dd....dd", "..dbbd..", "........", "........", "........", "........",
        "........", "........"]
WEED = [  # два кадра: верхушка и стебель
    [".....d..", "....db..", "...dbd..", "...db...", "....db..", ".....bd.", ".....db.",
     "....dbd."],
    ["....db..", "...db...", "...dbd..", "....db..", ".....bd.", ".....db.", "....dbd.",
     "...db..."],
    ["..d.....", "..bd....", "..dbd...", "...bd...", "..bd....", ".db.....", ".bd.....",
     ".dbd...."],
    ["..bd....", "...bd...", "..dbd...", "..bd....", ".db.....", ".bd.....", ".dbd....",
     "...bd..."],
]
SAND_TOP = ["........", "..b.....", "bbbbbb.b", "bbwbbbbb", "bbbbbdbb", "bdbbbbbb",
            "bbbbbbwb", "bbbbbbbb"]
SAND = ["bbbbbbbb", "bbdbbbbb", "bbbbbbwb", "bbbbbbbb", "bwbbbdbb", "bbbbbbbb",
        "bbbbdbbb", "bbbbbbbb"]
BOX = {  # рамка диалога: цвет 1 — линия
    "H": ["........", "........", "........", "dddddddd", "........", "........", "........",
          "........"],
    "V": ["...d...."] * 8,
    "TL": ["........", "........", "........", "...ddddd", "...d....", "...d....", "...d....",
           "...d...."],
    "TR": ["........", "........", "........", "dddd....", "...d....", "...d....", "...d....",
           "...d...."],
    "BL": ["...d....", "...d....", "...d....", "...ddddd", "........", "........", "........",
           "........"],
    "BR": ["...d....", "...d....", "...d....", "dddd....", "........", "........", "........",
           "........"],
}

# --- палитры (RGB 0–255) ----------------------------------------------------

WATER_RGB = (26, 90, 140)
NAVY = (11, 26, 46)
BG_PALETTES = [
    [WATER_RGB, (13, 43, 69), (95, 182, 232), (255, 255, 255)],   # 0 вода и текст
    [NAVY, (95, 240, 255), (58, 126, 168), (255, 255, 255)],      # 1 диалог
    [NAVY, (95, 240, 255), (192, 138, 16), (255, 225, 77)],       # 2 ник в рамке
    [WATER_RGB, (15, 74, 34), (47, 174, 74), (143, 240, 138)],    # 3 водоросли
    [WATER_RGB, (138, 106, 53), (201, 164, 92), (236, 212, 154)], # 4 песок
    [WATER_RGB, (90, 16, 64), (255, 92, 200), (255, 196, 238)],   # 5 большой хуй
    [WATER_RGB, (200, 244, 255), (95, 182, 232), (255, 255, 255)],  # 6 поверхность
    [(192, 16, 42), (96, 0, 16), (255, 128, 128), (255, 255, 255)],  # 7 баннер
]
FISH_COLORS = [  # тёмный, основной
    ((90, 10, 20), (255, 77, 94)),
    ((10, 74, 28), (77, 255, 138)),
    ((90, 74, 0), (255, 225, 77)),
    ((10, 42, 90), (77, 168, 255)),
    ((74, 10, 70), (255, 77, 242)),
    ((0, 74, 80), (77, 246, 255)),
]
OBJ_PALETTES = [[(0, 0, 0), d, b, (255, 255, 255)] for d, b in FISH_COLORS] + [
    [(0, 0, 0), (90, 16, 64), (255, 92, 200), (255, 196, 238)],   # 6 хуи
    [(0, 0, 0), (16, 16, 24), (208, 32, 48), (255, 255, 255)],    # 7 казак, капли, ui
]

# --- кодирование -------------------------------------------------------------

PIX = {".": 0, "d": 1, "b": 2, "w": 3}


def tile_bytes(rows8):
    out = []
    for row in rows8:
        lo = hi = 0
        for i, ch in enumerate(row):
            v = PIX[ch]
            lo |= (v & 1) << (7 - i)
            hi |= ((v >> 1) & 1) << (7 - i)
        out += [lo, hi]
    return out


def glyph_tile(rows7):
    rows = [r.replace("#", "w") + "." for r in rows7] + ["........"]
    return tile_bytes(rows)


def image_tiles(rows, w_tiles, h_tiles, order="sprite16"):
    """Нарезает картинку на тайлы. sprite16 — пары верх/низ по столбцам (8×16)."""
    rows = [r.ljust(w_tiles * 8, ".") for r in rows]
    rows += ["." * (w_tiles * 8)] * (h_tiles * 8 - len(rows))
    tiles = []

    def cut(tx, ty):
        return tile_bytes([rows[ty * 8 + y][tx * 8:tx * 8 + 8] for y in range(8)])

    if order == "sprite16":
        for tx in range(w_tiles):
            for ty in range(h_tiles):
                tiles.append(cut(tx, ty))
    else:  # построчно, для фона
        for ty in range(h_tiles):
            for tx in range(w_tiles):
                tiles.append(cut(tx, ty))
    return tiles


def pad16(rows8):
    return rows8 + ["........"] * (16 - len(rows8))


def wrap(text):
    """Две строки по LINE символов: сначала по словам, иначе как получится."""
    lines = textwrap.wrap(text, LINE, break_long_words=True, break_on_hyphens=False)
    if len(lines) > 2:
        lines = [text[:LINE], text[LINE:].strip()]
    assert len(lines) <= 2 and all(len(x) <= LINE for x in lines), text
    return lines


class Font:
    def __init__(self, base):
        self.base = base
        self.chars = []

    def code(self, ch):
        if ch not in _G:
            raise SystemExit(f"нет глифа для {ch!r}")
        if ch not in self.chars:
            self.chars.append(ch)
        return self.base + self.chars.index(ch)

    def encode(self, text, lines=None):
        out = []
        parts = lines if lines is not None else [text]
        for i, part in enumerate(parts):
            if i:
                out.append(0xFE)
            out += [self.code(c) for c in part.upper()]
        return out + [0xFF]


def c_bytes(data, per_line=16):
    lines = []
    for i in range(0, len(data), per_line):
        lines.append("    " + ", ".join(f"0x{b:02X}" for b in data[i:i + per_line]) + ",")
    return "\n".join(lines)


def rgb(c):
    return f"RGB8({c[0]}, {c[1]}, {c[2]})"


# --- сборка ------------------------------------------------------------------

def build():
    SRC.mkdir(exist_ok=True)
    species = list(aq.SPECIES)
    nicks = list(aq.NICKS)
    # фон: служебные тайлы, потом шрифт, потом большой хуй
    bg_tiles = []
    names = {}

    def add_bg(name, data):
        names[name] = len(bg_tiles)
        bg_tiles.append(data)

    add_bg("WATER", tile_bytes(WATER))
    add_bg("WAVE", tile_bytes(WAVE))
    add_bg("WEED_TOP", tile_bytes(WEED[0]))
    add_bg("WEED_STEM", tile_bytes(WEED[1]))
    add_bg("SAND_TOP", tile_bytes(SAND_TOP))
    add_bg("SAND", tile_bytes(SAND))
    for k in ("H", "V", "TL", "TR", "BL", "BR"):
        add_bg("BOX_" + k, tile_bytes(BOX[k]))
    font_base = 16
    while len(bg_tiles) < font_base:
        bg_tiles.append(tile_bytes(WATER))
    font = Font(font_base)

    # тексты: всё, что попадёт в ром
    texts = []      # (байты)
    index = {}

    def add_text(s, lines=None):
        key = (s, tuple(lines) if lines else None)
        if key not in index:
            index[key] = len(texts)
            texts.append(font.encode(s, lines))
        return index[key]

    def pool(items):
        return [add_text(p, wrap(p)) for p in items]

    pools = []      # (start, count) в pool_items
    pool_items = []

    def add_pool(items):
        ids = pool(items)
        pools.append((len(pool_items), len(ids)))
        pool_items.extend(ids)
        return len(pools) - 1

    common = [add_pool(aq.PHRASES.get(e, [])) for e in EVENTS]
    species_pools = [[add_pool(aq.SPECIES_PHRASES.get(s, {}).get(e, [])) for e in EVENTS]
                     for s in species]
    nick_pools = [add_pool(aq.NICK_PHRASES.get(n, [])) for n in nicks]
    cries = add_pool(aq.RIDER_CRIES)
    tiny_cries = add_pool(aq.TINY_CRIES)
    nick_ids = [add_text(n[:LABEL]) for n in nicks]
    species_ids = [add_text(s) for s in species]

    ui = {
        "TITLE": "АКВАРИУМ",
        "PAUSE": "ПАУЗА",
        "BANNER": "ШКВАЛ ХУЁВ!!!",
        "COSSACK": "ВАЙБ-КАЗАК",
        "TINY": "КАЗАЧОК",
        "KIND": "ВИД: ",
        "HINT1": "<> КОЛ-ВО  A: СТАРТ",
        "HINT2": "SELECT: СЛУЧАЙНО",
        "HINT3": "B: СБРОС  РЫБ:",
        "OF": "/8",
        "TIMES": "×",
        "ARROW": "▶",
        "DIGITS": "0123456789",
    }
    ui_bytes = {k: font.encode(v) for k, v in ui.items()}
    help_lines = ["A-КОРМ   B-ТЫК", "START-ПАУЗА <>РЫБА"]
    assert all(len(x) <= LINE for x in help_lines)
    ui_bytes["HELP"] = font.encode(None, help_lines)

    # шрифт — в тайлы
    for ch in font.chars:
        bg_tiles.append(glyph_tile(_G[ch]))
    big_base = len(bg_tiles)
    bg_tiles += image_tiles(BIG_DICK, 12, 4, order="rows")
    assert len(bg_tiles) <= 256, len(bg_tiles)

    # спрайты (банк VRAM 1), всё 8×16
    spr = []
    snames = {}

    def add_spr(name, rows, w_tiles):
        snames[name] = len(spr)
        spr.extend(image_tiles(rows, w_tiles, 2))

    fish_info = []
    for s in species:
        rows = FISH[s]
        assert len(rows) == 16, s
        w = len(rows[0])
        assert all(len(r) == w for r in rows), s
        add_spr("FISH_" + s, rows, w // 8)
        lo, hi = aq.SPECIES[s].speed
        fish_info.append((snames["FISH_" + s], w // 8, max(1, round(lo * 0.8)),
                          max(2, round(hi * 0.8))))
    add_spr("MEDIUM", MEDIUM_DICK, 4)
    add_spr("SMALL", SMALL_DICK, 2)
    add_spr("RIDER", RIDER_BODY, 2)
    for i, f in enumerate(SABER):
        add_spr(f"SABER{i}", f, 1)
    for i, f in enumerate(TINY_RIDER):
        add_spr(f"TINY{i}", pad16(f), 1)
    for name, img in (("SHOT", SHOT), ("SPLAT", SPLAT), ("FOOD", FOOD), ("BUBBLE", BUBBLE),
                      ("CURSOR", CURSOR), ("MARK", MARK)):
        add_spr(name, pad16(img), 1)
    assert len(spr) <= 256, len(spr)

    blob = []
    offsets = []
    for t in texts:
        offsets.append(len(blob))
        blob += t
    write_text_c(blob, offsets, pools, pool_items, common, species_pools, nick_pools,
                 cries, tiny_cries, nick_ids, species_ids, len(species), len(nicks))
    write_gfx_c(bg_tiles, spr)
    write_data(names, snames, big_base, fish_info, ui_bytes, len(species), len(nicks),
               font_base, len(bg_tiles), len(spr))
    preview(bg_tiles, spr)
    print(f"тайлов фона {len(bg_tiles)}, спрайтов {len(spr)}, глифов {len(font.chars)}, "
          f"текстов {len(texts)} ({len(blob)} байт)")


def write_text_c(blob, offsets, pools, pool_items, common, species_pools, nick_pools,
                 cries, tiny_cries, nick_ids, species_ids, n_species, n_nicks):
    ev = len(EVENTS)
    sp_flat = [p for row in species_pools for p in row]
    out = f"""// Сгенерировано gb/assets.py — руками не править.
#pragma bank 1
#include <gb/gb.h>
#include <stdint.h>
#include "gen_text.h"

static const uint8_t blob[] = {{
{c_bytes(blob)}
}};
static const uint16_t offs[] = {{ {", ".join(map(str, offsets))} }};
static const uint16_t pool_start[] = {{ {", ".join(str(s) for s, _ in pools)} }};
static const uint8_t pool_count[] = {{ {", ".join(str(c) for _, c in pools)} }};
static const uint16_t items[] = {{ {", ".join(map(str, pool_items))} }};
static const uint8_t common_pool[] = {{ {", ".join(map(str, common))} }};
static const uint16_t species_pool[] = {{ {", ".join(map(str, sp_flat))} }};
static const uint16_t nick_pool[] = {{ {", ".join(map(str, nick_pools))} }};
static const uint16_t nick_text[] = {{ {", ".join(map(str, nick_ids))} }};
static const uint16_t species_text[] = {{ {", ".join(map(str, species_ids))} }};

static void copy(uint16_t id, uint8_t *out) {{
    const uint8_t *s = blob + offs[id];
    do {{ *out++ = *s; }} while (*s++ != 0xFF);
}}

static uint16_t pick(uint16_t p, uint16_t k) {{
    return items[pool_start[p] + k];
}}

uint8_t get_phrase(uint8_t sp, uint8_t nick, uint8_t event, uint16_t r, uint8_t *out) BANKED {{
    uint16_t c = common_pool[event];
    uint16_t s = species_pool[(uint16_t)sp * {ev} + event];
    uint16_t n = nick_pool[nick];
    uint16_t cc = pool_count[c], sc = pool_count[s];
    uint16_t nc = (event == EV_IDLE || event == EV_POKE) ? pool_count[n] : 0;
    uint16_t total = cc + 2 * (sc + nc);
    uint16_t k;
    if (!total) {{ out[0] = 0xFF; return 0; }}
    k = r % total;
    if (k < cc) copy(pick(c, k), out);
    else {{
        k = (k - cc) >> 1;
        if (k < sc) copy(pick(s, k), out); else copy(pick(n, k - sc), out);
    }}
    return 1;
}}

void get_cry(uint8_t tiny, uint16_t r, uint8_t *out) BANKED {{
    uint16_t p = tiny ? {tiny_cries} : {cries};
    copy(pick(p, r % pool_count[p]), out);
}}

void get_nick(uint8_t nick, uint8_t *out) BANKED {{ copy(nick_text[nick], out); }}

void get_species_name(uint8_t sp, uint8_t *out) BANKED {{ copy(species_text[sp], out); }}
"""
    (SRC / "gen_text.c").write_text(out, encoding="utf-8")
    hdr = f"""// Сгенерировано gb/assets.py — руками не править.
#ifndef GEN_TEXT_H
#define GEN_TEXT_H
#include <gb/gb.h>
#include <stdint.h>

#define N_SPECIES {n_species}
#define N_NICKS {n_nicks}
{chr(10).join(f"#define EV_{e.upper()} {i}" for i, e in enumerate(EVENTS))}

// Тексты: коды тайлов шрифта, 0xFE — перевод строки, 0xFF — конец.
uint8_t get_phrase(uint8_t sp, uint8_t nick, uint8_t event, uint16_t r, uint8_t *out) BANKED;
void get_cry(uint8_t tiny, uint16_t r, uint8_t *out) BANKED;
void get_nick(uint8_t nick, uint8_t *out) BANKED;
void get_species_name(uint8_t sp, uint8_t *out) BANKED;
#endif
"""
    (SRC / "gen_text.h").write_text(hdr, encoding="utf-8")


def write_gfx_c(bg_tiles, spr):
    bg_pals = ",\n".join("    " + ", ".join(rgb(c) for c in p) for p in BG_PALETTES)
    obj_pals = ",\n".join("    " + ", ".join(rgb(c) for c in p) for p in OBJ_PALETTES)
    out = f"""// Сгенерировано gb/assets.py — руками не править.
#pragma bank 2
#include <gb/gb.h>
#include <gb/cgb.h>
#include <stdint.h>
#include "gen_gfx.h"

static const uint8_t bg_data[] = {{
{c_bytes([b for t in bg_tiles for b in t])}
}};
static const uint8_t spr_data[] = {{
{c_bytes([b for t in spr for b in t])}
}};
static const palette_color_t bg_pal[] = {{
{bg_pals}
}};
static const palette_color_t obj_pal[] = {{
{obj_pals}
}};

void load_graphics(void) BANKED {{
    VBK_REG = VBK_BANK_0;
    set_bkg_data(0, {len(bg_tiles)}, bg_data);
    VBK_REG = VBK_BANK_1;
    set_sprite_data(0, {len(spr)}, spr_data);
    VBK_REG = VBK_BANK_0;
    set_bkg_palette(0, 8, bg_pal);
    set_sprite_palette(0, 8, obj_pal);
}}
"""
    (SRC / "gen_gfx.c").write_text(out, encoding="utf-8")


def write_data(names, snames, big_base, fish_info, ui_bytes, n_species, n_nicks, font_base,
               n_bg, n_spr):
    defs = [f"#define T_{k} {v}" for k, v in names.items()]
    defs.append(f"#define T_BIG_DICK {big_base}")
    defs.append(f"#define T_FONT {font_base}")
    for k, v in snames.items():
        if not k.startswith("FISH_"):
            defs.append(f"#define S_{k} {v}")
    weed = [b for f in WEED for b in tile_bytes(f)]
    wave = tile_bytes(WAVE)
    ui_c = "\n".join(
        f"const uint8_t UI_{k}[] = {{ {', '.join(map(str, v))} }};" for k, v in ui_bytes.items())
    ui_h = "\n".join(f"extern const uint8_t UI_{k}[];" for k in ui_bytes)
    hdr = f"""// Сгенерировано gb/assets.py — руками не править.
#ifndef GEN_GFX_H
#define GEN_GFX_H
#include <gb/gb.h>
#include <stdint.h>

// тайлы фона (банк VRAM 0) — всего {n_bg}
{chr(10).join(defs)}

// спрайты 8×16 (банк VRAM 1) — всего {n_spr}
typedef struct {{ uint8_t tile, width, speed_lo, speed_hi; }} SpeciesGfx;
extern const SpeciesGfx species_gfx[{n_species}];
extern const uint8_t weed_frames[{len(weed)}];
extern const uint8_t wave_tile[16];
{ui_h}

void load_graphics(void) BANKED;
#endif
"""
    (SRC / "gen_gfx.h").write_text(hdr, encoding="utf-8")
    fish_c = ",\n".join(f"    {{ {t}, {w}, {lo}, {hi} }}" for t, w, lo, hi in fish_info)
    data = f"""// Сгенерировано gb/assets.py — руками не править.
#include <gb/gb.h>
#include <stdint.h>
#include "gen_gfx.h"

const SpeciesGfx species_gfx[] = {{
{fish_c}
}};
const uint8_t weed_frames[] = {{
{c_bytes(weed)}
}};
const uint8_t wave_tile[] = {{
{c_bytes(wave)}
}};
{ui_c}
"""
    (SRC / "gen_data.c").write_text(data, encoding="utf-8")


def preview(bg_tiles, spr):
    """Картинка всех тайлов для проверки глазами: build/preview.png."""
    try:
        from PIL import Image
    except ImportError:
        return
    out = Path(__file__).resolve().parent / "build"
    out.mkdir(exist_ok=True)
    pal = [(26, 90, 140), (20, 20, 30), (255, 92, 200), (255, 255, 255)]

    def draw(tiles, cols, pair):
        n = len(tiles)
        if pair:
            rows_ = (n // 2 + cols - 1) // cols
            img = Image.new("RGB", (cols * 9, rows_ * 17), (60, 60, 60))
        else:
            rows_ = (n + cols - 1) // cols
            img = Image.new("RGB", (cols * 9, rows_ * 9), (60, 60, 60))
        for i, t in enumerate(tiles):
            if pair:
                idx, half = divmod(i, 2)
                ox, oy = (idx % cols) * 9, (idx // cols) * 17 + half * 8
            else:
                ox, oy = (i % cols) * 9, (i // cols) * 9
            for y in range(8):
                lo, hi = t[y * 2], t[y * 2 + 1]
                for x in range(8):
                    v = ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)
                    img.putpixel((ox + x, oy + y), pal[v])
        return img

    a = draw(bg_tiles, 16, False)
    b = draw(spr, 16, True)
    img = Image.new("RGB", (max(a.width, b.width), a.height + b.height + 4), (0, 0, 0))
    img.paste(a, (0, 0))
    img.paste(b, (0, a.height + 4))
    img = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
    img.save(out / "preview.png")


if __name__ == "__main__":
    build()
