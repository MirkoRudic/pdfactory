"""Installed fonts: families with regular / bold / italic / bold-italic files.

The list is cached in data/fonts.json and rebuilt when a font folder changes.
"""
import json
import os
import re
import sys
from pathlib import Path

import applog

log = applog.get("fonts")
_families: dict[str, dict] = {}
_cache: Path | None = None
EXT = {".ttf", ".otf", ".ttc"}


def font_dirs() -> list[Path]:
    if sys.platform == "win32":
        dirs = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
        la = os.environ.get("LOCALAPPDATA")
        if la:
            dirs.append(Path(la) / "Microsoft" / "Windows" / "Fonts")
    else:
        dirs = [Path("/usr/share/fonts"), Path.home() / ".fonts", Path("/usr/local/share/fonts")]
    return [d for d in dirs if d.exists()]


def _stamp() -> str:
    parts = []
    for d in font_dirs():
        try:
            parts.append(f"{d}:{d.stat().st_mtime_ns}:{sum(1 for _ in d.rglob('*'))}")
        except OSError:
            pass
    return "|".join(parts)


def _style_key(style: str) -> str:
    s = style.lower()
    bold = re.search(r"\bbold\b", s) is not None
    italic = "italic" in s or "oblique" in s
    return "bi" if bold and italic else "b" if bold else "i" if italic else "r"


def _scan() -> dict:
    from PIL import ImageFont
    fam: dict[str, dict] = {}
    for d in font_dirs():
        for p in d.rglob("*"):
            if p.suffix.lower() not in EXT:
                continue
            try:
                f = ImageFont.truetype(str(p), 12)
                family, style = f.getname()
            except Exception:
                continue
            if not family:
                continue
            style = style or "Regular"
            # other weights (Light, Semibold, Condensed...) are separate families
            extra = re.sub(r"(?i)\b(regular|normal|bold|italic|oblique|roman|book)\b", "", style).strip()
            name = f"{family} {extra}".strip()
            k = _style_key(style)
            e = fam.setdefault(name, {"name": name, "files": {}})
            e["files"].setdefault(k, str(p))
    for e in fam.values():
        if "r" not in e["files"]:
            e["files"]["r"] = next(iter(e["files"].values()))
    return dict(sorted(fam.items(), key=lambda kv: kv[0].lower()))


def init(cache_path):
    global _cache, _families
    _cache = Path(cache_path)
    stamp = _stamp()
    try:
        c = json.loads(_cache.read_text(encoding="utf-8"))
        if c.get("stamp") == stamp and c.get("families"):
            _families = c["families"]
            return
    except (OSError, ValueError):
        pass
    with applog.timed("fonts", "font scan"):
        _families = _scan()
    log.info("%d font families", len(_families))
    try:
        _cache.write_text(json.dumps({"stamp": stamp, "families": _families}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        log.exception("font cache not written")


def families() -> list[dict]:
    return [{"name": n, "styles": sorted(e["files"].keys())} for n, e in _families.items()]


def file_for(name: str, key: str = "r") -> str | None:
    e = _families.get(name)
    if not e:
        return None
    f = e["files"]
    return f.get(key) or f.get("r")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def match(pdf_font_name: str) -> str:
    """Closest installed family for a font name from a PDF (e.g. 'ABCDEF+Calibri-Bold')."""
    n = pdf_font_name.split("+", 1)[-1]
    base = re.split(r"[-,]", n)[0]
    base = re.sub(r"(?i)(mt|ps|psmt|bold|italic|regular)$", "", base)
    nb = _norm(base)
    aliases = {"helvetica": "Arial", "arialmt": "Arial", "timesnewromanps": "Times New Roman", "times": "Times New Roman",
               "courier": "Courier New", "couriernewps": "Courier New"}
    if nb in aliases and aliases[nb] in _families:
        return aliases[nb]
    # metric-compatible stand-ins (when the original font is not installed)
    twins = {"calibri": "Carlito", "cambria": "Caladea", "arial": "Liberation Sans", "timesnewroman": "Liberation Serif",
             "couriernew": "Liberation Mono", "helvetica": "Liberation Sans"}
    for name in _families:
        if _norm(name) == nb:
            return name
    for name in _families:
        if nb and _norm(name).startswith(nb):
            return name
    if twins.get(nb) in _families:
        return twins[nb]
    for fallback in ("Arial", "DejaVu Sans", "Liberation Sans"):
        if fallback in _families:
            return fallback
    return next(iter(_families), "")


def default_family() -> str:
    for f in ("Arial", "Calibri", "DejaVu Sans", "Liberation Sans"):
        if f in _families:
            return f
    return next(iter(_families), "")
