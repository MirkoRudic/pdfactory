"""VAJB tempdir 1.0 - temporary files only inside <app>/data/tmp (PRAVILA.md F1).

    import tempdir
    tempdir.init(APP_DIR / "data" / "tmp")   # at startup: empties leftovers
    with tempdir.folder("render") as d: ...  # deleted on exit, also on error
Never use tempfile.gettempdir(), /tmp or %TEMP%: on Windows "/tmp/x" becomes D:\\tmp\\x.
"""
import atexit
import contextlib
import shutil
import tempfile
import time
from pathlib import Path

_root: Path | None = None


def init(root, older_than_h: float | None = None) -> Path:
    """Empties the tmp folder (or only items older than N hours) and registers cleanup at exit."""
    global _root
    _root = Path(root)
    _root.mkdir(parents=True, exist_ok=True)
    clean(older_than_h)
    atexit.register(clean)
    return _root


def root() -> Path:
    if _root is None:
        raise RuntimeError("tempdir.init() was not called")
    return _root


def clean(older_than_h: float | None = None):
    if _root is None or not _root.exists():
        return
    cut = time.time() - (older_than_h or 0) * 3600
    for p in _root.iterdir():
        try:
            if older_than_h is None or p.stat().st_mtime < cut:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        except OSError:
            pass


@contextlib.contextmanager
def folder(prefix="tmp"):
    d = Path(tempfile.mkdtemp(prefix=prefix + "_", dir=root()))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def file(suffix="", prefix="tmp") -> Path:
    """Path for a single temp file inside tmp/; removed by clean()."""
    fd, p = tempfile.mkstemp(suffix=suffix, prefix=prefix + "_", dir=root())
    import os
    os.close(fd)
    return Path(p)
