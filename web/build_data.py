#!/usr/bin/env python3
"""Собирает web/data.js из aquarium.py: рисунки, ники, фразы и константы.

Веб-версия не дублирует тексты: после правки aquarium.py запустите
    python3 web/build_data.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aquarium as a  # noqa: E402

CONSTS = [
    "MAX_PER_SPECIES", "FOOD_RADIUS", "FLEE_SPEED", "RETURN_SPEED_FACTOR",
    "MIN_RETURN_SPEED", "FOOD_FALL", "MAX_BUBBLES", "BUBBLE_RISE", "BUBBLE_RATE",
    "SPEECH_TTL", "MAX_SPEAKERS", "SPEECH_RATE", "EGG_PRESSES", "EGG_GAP",
    "SPEED_RANGE", "SWARM_SIZE", "SWARM_SPREAD", "SCARE_RADIUS", "PANIC_CHANCE",
    "HOME_CHANCE", "FIRE_RATE", "SHOT_SPEED", "MAX_SHOTS", "SHOT_RIGHT", "SHOT_LEFT",
    "FLASH_TTL", "SPLAT_TTL", "HIT_CHANCE", "RIDER_SEAT", "SWING_TICKS",
    "SHOUT_TIME", "QUIET_TIME", "EYES",
]


def build():
    return {
        "species": [
            {"name": s.name, "right": s.right, "left": s.left,
             "speed": list(s.speed), "icon": s.icon}
            for s in a.SPECIES.values()
        ],
        "nicks": a.NICKS,
        "phrases": a.PHRASES,
        "speciesPhrases": a.SPECIES_PHRASES,
        "nickPhrases": a.NICK_PHRASES,
        "riderFrames": a.RIDER_FRAMES,
        "tinyRiderFrames": a.TINY_RIDER_FRAMES,
        "riderCries": a.RIDER_CRIES,
        "tinyCries": a.TINY_CRIES,
        "flashes": a.FLASHES,
        "splats": a.SPLATS,
        "stormBanner": a.STORM_BANNER.strip(),
        "help": a.HELP,
        "const": {name: getattr(a, name) for name in CONSTS},
    }


def main():
    out = Path(__file__).resolve().parent / "data.js"
    text = json.dumps(build(), ensure_ascii=False, indent=1)
    out.write_text(
        "// Сгенерировано web/build_data.py из aquarium.py — руками не править.\n"
        f"window.AQUA = {text};\n",
        encoding="utf-8",
    )
    print(f"записано {out}")


if __name__ == "__main__":
    main()
