#!/usr/bin/env python3
"""Терминальный аквариум со случайными рыбами и смешными никами."""
import json
from pathlib import Path

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
