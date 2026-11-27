"""VAJB hardexit 1.0 - leave the process at once without skipping cleanup (RULES.md P11). From PDFactory 0.5.1.

    import hardexit
    hardexit.exit()          # instead of os._exit(0): tray "Quit", /api/shutdown, restart after an update

os._exit ends the process immediately and skips everything registered with atexit: tempdir.clean() (data/tmp stays
full), the last "shutdown" line of applog, and whatever the app registered itself (e.g. saving session copies).
exit() runs those handlers first, then os._exit. Anything the app must do on the way out goes to atexit.register.
"""
import atexit
import os


def exit(code: int = 0):
    try:
        atexit._run_exitfuncs()   # each handler once; an error in one is printed and the rest still run
    finally:
        os._exit(code)
