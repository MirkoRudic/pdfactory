"""VAJB version 1.0 (PRAVILA.md V1). Copy into the app and set APP_NAME; bump VERSION with every push."""
from pathlib import Path

APP_NAME = "PDFactory"
VERSION = "0.4.1"
_GIT = Path(__file__).resolve().parent


def git_commit() -> str:
    """Short hash of HEAD, read from .git without running git."""
    g = next((p / ".git" for p in [_GIT, *_GIT.parents] if (p / ".git").exists()), None)
    if not g:
        return ""
    try:
        head = (g / "HEAD").read_text().strip()
        if not head.startswith("ref: "):
            return head[:7]
        ref = head[5:]
        if (g / ref).exists():
            return (g / ref).read_text().strip()[:7]
        for line in (g / "packed-refs").read_text().splitlines():
            if line.endswith(" " + ref):
                return line.split()[0][:7]
    except OSError:
        pass
    return ""


def label() -> str:
    c = git_commit()
    return f"{APP_NAME} {VERSION}" + (f" · {c}" if c else "")
