#!/usr/bin/env python3
"""Собирает ром для Game Boy Color: gb/aquarium.gbc.

Нужен GBDK-2020 в tools/gbdk (или путь в переменной GBDK_HOME).
    python gb/build.py
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GBDK = Path(os.environ.get("GBDK_HOME", ROOT / "tools" / "gbdk"))
LCC = GBDK / "bin" / ("lcc.exe" if platform.system() == "Windows" else "lcc")
BUILD = HERE / "build"
ROM = HERE / "aquarium.gbc"

# CGB-only, MBC5 + RAM + батарейка (сохранение набора рыб), 4 банка ПЗУ, 1 банк ОЗУ
LINK_FLAGS = [
    "-Wm-yC", "-Wm-yt0x1B", "-Wm-yo4", "-Wm-ya1", "-Wm-ynAQUARIUM",
]
SOURCES = ["main.c", "gen_data.c", "gen_gfx.c", "gen_text.c"]


def run(cmd):
    print(" ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    if not LCC.exists():
        sys.exit(f"не найден {LCC}: скачайте GBDK-2020 в tools/gbdk или задайте GBDK_HOME")
    run([sys.executable, "-X", "utf8", HERE / "assets.py"])
    BUILD.mkdir(exist_ok=True)
    objs = []
    for src in SOURCES:
        obj = BUILD / (Path(src).stem + ".o")
        run([LCC, "-Wf--max-allocs-per-node50000", "-c", "-o", obj, HERE / "src" / src])
        objs.append(obj)
    out = BUILD / "aquarium.gbc"
    run([LCC, *LINK_FLAGS, "-o", out, *objs])
    shutil.copyfile(out, ROM)
    print(f"готово: {ROM} ({ROM.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
