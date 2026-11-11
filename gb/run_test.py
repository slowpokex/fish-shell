#!/usr/bin/env python3
"""Прогоняет ром в эмуляторе PyBoy без окна и сохраняет скриншоты в gb/build/shots.

    tools/venv/Scripts/python gb/run_test.py

Сценарий: экран выбора → случайный набор → аквариум → корм, тычок, выбор рыбы →
B×5 (шквал) → ждём, пока все вернутся. Сохранение в SRAM стирается перед
запуском, чтобы всегда начинать с экрана выбора.
"""
import sys
from pathlib import Path

from pyboy import PyBoy

HERE = Path(__file__).resolve().parent
ROM = HERE / "aquarium.gbc"
OUT = HERE / "build" / "shots"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    ram = ROM.with_suffix(".gbc.ram")
    if ram.exists():
        ram.unlink()
    pb = PyBoy(str(ROM), window="null", cgb=True, sound_emulated=False)
    pb.set_emulation_speed(0)
    n = [0]

    def shot(name, ticks=0):
        if ticks:
            pb.tick(ticks, True)
        n[0] += 1
        path = OUT / f"{n[0]:02d}-{name}.png"
        pb.screen.image.save(path)
        print("кадр", path.name)

    def press(btn, wait=6):
        pb.button(btn, 3)
        pb.tick(wait, True)

    pb.tick(240, True)          # заставка CGB и старт
    shot("picker")
    press("select")              # случайный набор
    press("down"); press("down")
    shot("picker-random", 10)
    press("a", 30)               # старт
    shot("tank-help", 30)
    shot("tank", 200)
    press("right", 10)           # выбрать рыбу: показывает ник
    shot("select-fish", 5)
    press("a", 40)               # корм
    shot("feed", 5)
    press("b", 10)               # тычок
    shot("poke", 5)
    shot("feeding", 200)
    for _ in range(5):           # пасхалка
        press("b", 8)
    for i in range(6):
        shot(f"swarm-{i}", 45)
    shot("swarm-late", 240)
    shot("after", 600)
    press("start", 10)
    shot("pause", 5)
    press("start", 10)
    pb.stop(save=False)


if __name__ == "__main__":
    sys.exit(main())
