"""VAJB runlock 1.0 - one running instance of a job at a time (PRAVILA.md P5).

    from runlock import RunLock
    lock = RunLock(APP_DIR / "data" / "RUN.lock", max_age_h=3)
    if not lock.acquire(): sys.exit(0)      # someone else is running
    try: ... lock.refresh() during long work
    finally: lock.release()

WARNING: on Windows os.kill(pid, 0) is TerminateProcess - it KILLS the process.
Process liveness is checked with OpenProcess + GetExitCodeProcess (from StanFinder, 28.09.2026).
A lock older than max_age_h or held by a dead PID is ignored.
"""
import os
from datetime import datetime, timezone
from pathlib import Path


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5  # access denied = exists
        try:
            code = wintypes.DWORD()
            if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)  # POSIX only: signal 0 just checks
        return True
    except PermissionError:
        return True
    except OSError:
        return False


class RunLock:
    def __init__(self, path, max_age_h: float = 3.0):
        self.path, self.max_age_h = Path(path), max_age_h

    def _read(self):
        try:
            rows = dict(r.split("=", 1) for r in self.path.read_text(encoding="utf-8").splitlines() if "=" in r)
            return int(rows["pid"]), datetime.fromisoformat(rows["time"])
        except (OSError, KeyError, ValueError):
            return None

    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(f"pid={os.getpid()}\ntime={datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")

    def held_by_other(self) -> int | None:
        r = self._read()
        if not r:
            return None
        pid, t = r
        age_h = (datetime.now(timezone.utc) - t).total_seconds() / 3600
        if pid == os.getpid() or age_h > self.max_age_h or not pid_alive(pid):
            return None
        return pid

    def acquire(self) -> bool:
        if self.held_by_other():
            return False
        self._write()
        return True

    def refresh(self) -> bool:
        r = self._read()
        if r and r[0] == os.getpid():
            self._write()
            return True
        return False

    def release(self):
        r = self._read()
        if r and r[0] == os.getpid():
            try:
                self.path.unlink()
            except OSError:
                pass
