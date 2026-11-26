"""PDFactory - launcher.

    PDFactory.pyw                 opens the window (starts the server if needed)
    PDFactory.pyw "C:\\x.pdf"     opens a file (double click on a PDF when PDFactory is the default app)
    PDFactory.pyw --tiho          start with Windows: server + tray icon, no window
    PDFactory.pyw --restart       after an update: stops the old server and starts the new code
    PDFactory.pyw --instaliraj    desktop shortcut, start with Windows, PDF app (called by "Install PDFactory.vbs")
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
_sp = Path(sys.executable).parent / "Lib" / "site-packages"
if (Path(sys.executable).parent / "python._pth").exists() or any(Path(sys.executable).parent.glob("python3*._pth")):
    import site                     # installed build (embedded Python): runs pywin32.pth & co.
    site.addsitedir(str(_sp))
sys.path.insert(0, str(APP_DIR / "app"))
DATA = APP_DIR / "data"
PORT = int(os.environ.get("PDFACTORY_PORT", "8802"))
URL = f"http://127.0.0.1:{PORT}/"
TITLE = "PDFactory"

for _old in (DATA / "logs").glob("pdfabrika_*.log"):      # logs from the first name keep showing in Log
    try:
        _old.rename(_old.with_name(_old.name.replace("pdfabrika_", "pdfactory_", 1)))
    except OSError:
        pass

import applog  # noqa: E402

applog.setup(DATA / "logs", "pdfactory")
log = applog.get("launcher")


def health():
    try:
        with urllib.request.urlopen(URL + "health", timeout=1.5) as r:
            d = json.loads(r.read() or b"{}")
            return d if d.get("app") == "pdfactory" else None
    except Exception:
        return None


def post(path, body=None, timeout=3):
    req = urllib.request.Request(URL + path, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def edge():
    for exe in (shutil.which("msedge"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", shutil.which("chrome"),
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if exe and Path(exe).exists():
            return exe
    return None


def app_windows():
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(h, _):
        if u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(h, b, 256)
            c = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(h, c, 64)
            if b.value.startswith(TITLE) and c.value.startswith("Chrome_WidgetWin"):
                found.append(h)
        return True
    u.EnumWindows(each, 0)
    return found


def focus_window():
    try:
        import ctypes
        u = ctypes.windll.user32
        w = app_windows()
        if not w:
            return False
        if u.IsIconic(w[0]):
            u.ShowWindow(w[0], 9)          # SW_RESTORE
        u.SetForegroundWindow(w[0])
        return True
    except Exception as e:
        log.warning("focus: %s", e)
        return False


def close_windows():
    """P4: shutting down also closes the app window (Edge would stay as an empty window)."""
    try:
        import ctypes
        for h in app_windows():
            ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE
    except Exception as e:
        log.warning("close windows: %s", e)


def edge_prefs(profile: Path):
    """Edge settings for the app's own profile (P3), written while no app window is open (Edge rewrites the file on exit):
    no mini menu over selected text (edge_quick_search.show_mini_menu, measured on 24.11.2026)."""
    f = Path(profile) / "Default" / "Preferences"
    try:
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        q = d.setdefault("edge_quick_search", {})
        if q.get("show_mini_menu") is False:
            return
        q["show_mini_menu"] = False
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(d), encoding="utf-8")
        os.replace(tmp, f)
    except Exception as e:
        log.warning("edge prefs: %s", e)


def open_window():
    exe = edge()
    if not exe:
        import webbrowser
        webbrowser.open(URL)
        return
    if not app_windows():
        edge_prefs(DATA / "edge")
    subprocess.Popen([exe, f"--app={URL}", f"--user-data-dir={DATA / 'edge'}", "--no-first-run",
                      "--no-default-browser-check", "--disable-sync", "--start-maximized",
                      # no Edge writing assistant ("Ask Edge to help me write") over text boxes. Edge's feature
                      # names are not documented; unknown names are ignored, so the known variants are all listed.
                      "--disable-features=Compose,ComposeInline,msEdgeCompose,msEdgeComposeInline,msComposeInline,"
                      "msEdgeWritingAssistance,msWritingAssistance,msEdgeCopilotCompose,msCopilotCompose,"
                      "msEdgeRewrite,msEdgeInlineRewrite,EdgeCompose,msEdgeHelpMeWrite"])
    threading.Thread(target=taskbar_icon, name="ikonica-na-traci", daemon=True).start()


def taskbar_icon():
    """The app window (Edge --app) gets the PDFactory icon and its own taskbar group (from Ghostcut)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import uuid
        from ctypes import wintypes
        u, sh, ole = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.ole32
        ole.CoInitialize(None)
        ico = str(APP_DIR / "assets" / "pdfactory.ico")
        import winsetup
        cmd = f'"{winsetup.app_exe()}" "{APP_DIR / "PDFactory.pyw"}"'

        class GUID(ctypes.Structure):
            _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort), ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]

        def guid(t):
            g = GUID()
            ctypes.memmove(ctypes.byref(g), uuid.UUID(t).bytes_le, 16)
            return g

        class PKEY(ctypes.Structure):
            _fields_ = [("fmtid", GUID), ("pid", ctypes.c_ulong)]

        class PROPVARIANT(ctypes.Structure):
            _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                        ("p", ctypes.c_void_p), ("p2", ctypes.c_void_p)]

        FMT = "9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"
        IID_PS = guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
        vals = [(5, "VAJB.PDFactory"), (2, cmd), (3, ico + ",0"), (4, TITLE)]
        bufs = [ctypes.create_unicode_buffer(v) for _, v in vals]
        u.LoadImageW.restype = ctypes.c_void_p
        u.LoadImageW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        u.SendMessageTimeoutW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, ctypes.c_void_p,
                                          ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_size_t)]
        hicon = u.LoadImageW(None, ico, 1, 0, 0, 0x10 | 0x40)
        sh.SHGetPropertyStoreForWindow.argtypes = [wintypes.HWND, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]

        def mark(h):
            ps = ctypes.c_void_p()
            if sh.SHGetPropertyStoreForWindow(h, ctypes.byref(IID_PS), ctypes.byref(ps)) != 0 or not ps:
                return
            vt = ctypes.cast(ctypes.cast(ps, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
            SetValue = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(PKEY), ctypes.POINTER(PROPVARIANT))(vt[6])
            Commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vt[7])
            Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])
            for (pid, _), b in zip(vals, bufs):
                SetValue(ps, ctypes.byref(PKEY(guid(FMT), pid)), ctypes.byref(PROPVARIANT(vt=31, p=ctypes.cast(b, ctypes.c_void_p))))
            Commit(ps)
            Release(ps)
            if hicon:
                r = ctypes.c_size_t(0)
                for big in (0, 1):
                    u.SendMessageTimeoutW(h, 0x80, big, hicon, 2, 200, ctypes.byref(r))
        done = set()
        for _ in range(60):                       # ~30 s: the window appears, Edge may re-set its icon once
            for h in app_windows():
                if h not in done:
                    done.add(h)
                    mark(h)
            time.sleep(0.5)
    except Exception as e:
        log.warning("taskbar icon: %s", e)


def edge_fallback(path):
    """PDFactory did not start: the PDF still opens (in Edge) so a double click never does nothing."""
    exe = edge()
    log.error("server did not start, opening %s in the browser", path)
    if exe:
        subprocess.Popen([exe, path])
    else:
        os.startfile(path)


def serve():
    import uvicorn
    try:
        from main import app
        uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning", log_config=None)
        log.info("server stopped")
    except BaseException:
        log.exception("server crashed")
        raise


def alive():
    """Anything answering /health on our port (also a server of an earlier version)."""
    try:
        with urllib.request.urlopen(URL + "health", timeout=1.5):
            return True
    except Exception:
        return False


def stop_old():
    try:
        post("api/shutdown")
    except Exception:
        pass
    for _ in range(50):
        if not alive():
            return True
        time.sleep(0.2)
    return False


def refresh_windows_setup():
    """Every start: PDF program registration and shortcuts point to the current PDFactory.exe and icon."""
    try:
        import winsetup
        if winsetup.WIN:
            winsetup.register()
            if not winsetup.INSTALLED:   # the installer owns the shortcuts of an installed copy
                winsetup.desktop_shortcut()
            if winsetup.autostart_enabled():
                winsetup.set_autostart(True)
    except Exception:
        log.exception("windows setup refresh")


def install():
    import tempdir
    import winsetup
    tempdir.init(DATA / "tmp")
    winsetup.install()
    log.info("installed")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    path = str(Path(args[0]).resolve()) if args else None
    # winsetup marker (data/tmp/choose-default.pdf): PDFactory was just picked, nothing to open.
    # Only that file: a user's own choose-default.pdf elsewhere is opened, not deleted.
    if path and Path(path).parent == (DATA / "tmp").resolve() and Path(path).stem == "choose-default":
        Path(path).unlink(missing_ok=True)
        path = None
    if "--instaliraj" in flags:
        install()
    if "--uninstall" in flags:          # called by the uninstaller (Setup.exe)
        import winsetup
        try:
            post("api/shutdown")
        except Exception:
            pass
        winsetup.unregister()
        return
    if "--want-default" in flags:       # Setup.exe task "Make PDFactory the default": the app asks, with context, on start
        import winsetup
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / "ask_default").write_text("1", encoding="utf-8")
        winsetup.register()
        return
    if "--default" in flags:            # opens Windows Settings directly (kept for older installers)
        import tempdir
        import winsetup
        tempdir.init(DATA / "tmp")
        winsetup.register()
        winsetup.open_default_apps().join(300)   # keeps the Windows dialog / Settings thread alive
        return
    if "--restart" in flags and alive():
        stop_old()
    h = health()
    if h:
        if path:
            try:
                post("api/open-external", {"path": path})
            except Exception:
                log.exception("open-external")
        if "--tiho" not in flags and not focus_window():
            open_window()
        return
    try:
        import winsetup
        winsetup.remove_first_name()         # before the window asks whether PDFactory is the default
    except Exception:
        log.exception("first name cleanup")
    t = threading.Thread(target=serve, name="server", daemon=True)
    t.start()
    for _ in range(100):
        if health():
            break
        time.sleep(0.15)
    else:
        if path:
            edge_fallback(path)
        log.error("server not up after 15 s")
        return
    if path:
        post("api/open-external", {"path": path})
    threading.Thread(target=refresh_windows_setup, name="windows-setup", daemon=True).start()
    # after a silent update the installer starts us with --updated: the old window is still open and reloads by itself
    if "--tiho" not in flags and not ("--updated" in flags and app_windows()):
        open_window()
    if "--instaliraj" in flags:
        try:
            import winsetup
            if not winsetup.is_default():
                time.sleep(2)
                winsetup.open_default_apps()
        except Exception:
            log.exception("default apps page")
    try:
        import pystray
        from PIL import Image
        from main import app as web

        def quit_all(icon=None, _=None):
            close_windows()
            if icon:
                icon.stop()
            os._exit(0)
        def ask_quit(icon, _):
            """P4: the question is asked in the app window, not here."""
            import main as m
            m.ASK_QUIT = True
            if not focus_window():
                open_window()
        icon = pystray.Icon("pdfactory", Image.open(APP_DIR / "assets" / "pdfactory_256.png"), TITLE, menu=pystray.Menu(
            pystray.MenuItem("Open PDFactory", lambda i, _: (focus_window() or open_window()), default=True),
            pystray.MenuItem("Quit", ask_quit)))
        web.state.quit = lambda: quit_all(icon)
        web.state.stop = lambda: (icon.stop(), os._exit(0))      # update: server only, the window waits and reloads
        icon.run()
    except Exception as e:
        log.warning("tray not available: %s", e)
        t.join()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("launcher crashed")
        raise
