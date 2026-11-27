"""VAJB settings 1.0 - one readable JSON file; old files are only extended (RULES.md F2, UI12).

    import settings
    settings.init(APP_DIR / "data" / "settings.json", DEFAULTS)
    s = settings.load(); settings.save(s)
"""
import copy
import json
import os
import threading
from pathlib import Path

BASE_DEFAULTS = {
    "theme": "dark",          # UI12: light | dark
    "log_auto_trim_mb": 500,  # L1
}

_path: Path | None = None
_defaults: dict = {}
_lock = threading.Lock()


def init(path, defaults: dict | None = None):
    global _path, _defaults
    _path = Path(path)
    _defaults = {**BASE_DEFAULTS, **(defaults or {})}


def _fill(d: dict, defaults: dict) -> dict:
    for k, v in defaults.items():
        if k not in d:
            d[k] = copy.deepcopy(v)
        elif isinstance(v, dict) and isinstance(d[k], dict):
            _fill(d[k], v)
    return d


def load() -> dict:
    with _lock:
        try:
            d = json.loads(_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            d = {}
        except ValueError:
            # broken file is kept next to the new one, never silently dropped
            _path.replace(_path.with_suffix(".broken.json"))
            d = {}
        return _fill(d, _defaults)


def save(d: dict):
    with _lock:
        _path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _path.with_suffix(".saving")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, _path)  # atomic: a crash never leaves half a file
