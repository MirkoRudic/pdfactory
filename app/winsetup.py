"""Windows integration: desktop shortcut, start with Windows, PDF file association, file dialogs.
Everything is per-user (HKCU), no admin rights needed."""
import os
import subprocess
import sys
import threading
from pathlib import Path

import applog

log = applog.get("windows")
APP_DIR = Path(__file__).resolve().parents[1]
LAUNCHER = APP_DIR / "PDFactory.pyw"
NAME = "PDFactory"            # shown everywhere in Windows
# internal ids keep the first name: the user's default-app choice is stored against PROGID
ICON = APP_DIR / "assets" / "pdfabrika.ico"          # the program
FILE_ICON = APP_DIR / "assets" / "pdf_fajl.ico"     # .pdf files in Explorer
PROGID = "PDFabrika.PDF"
NOWIN = 0x08000000
WIN = sys.platform == "win32"


def pythonw() -> str:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


_exe_lock = threading.Lock()


INSTALLED = (APP_DIR / "python" / "PDFactory.exe").exists()   # installed by PDFactory-Setup.exe (own Python inside)


def app_exe() -> str:
    if INSTALLED:                  # built with our icon and name at packaging time
        return str(APP_DIR / "python" / "PDFactory.exe")
    with _exe_lock:        # launcher threads call this at the same time (measured: EndUpdateResource error 110)
        return _app_exe()


def _app_exe() -> str:
    """PDFactory.exe = copy of the venv's pythonw.exe with our icon. Windows shows the program's
    name and icon from the .exe, so with pythonw.exe it says 'Python' in Default apps and Task Manager.
    Falls back to pythonw.exe when the copy can't be made or doesn't start the venv."""
    if not WIN:
        return pythonw()
    src = Path(pythonw())
    dst = src.with_name("PDFactory.exe")
    ok_flag = dst.with_suffix(".ok")
    try:
        stamp = f"{src.stat().st_size}:{src.stat().st_mtime_ns}:{ICON.stat().st_mtime_ns}"
        if dst.exists() and ok_flag.exists() and ok_flag.read_text() == stamp:
            return str(dst)
        tmp = dst.with_suffix(".new.exe")
        import shutil
        shutil.copy2(src, tmp)
        _set_exe_icon(tmp, ICON)
        r = subprocess.run([str(tmp), "-c", "import sys,fitz;print(sys.prefix)"], capture_output=True, text=True,
                           timeout=60, creationflags=NOWIN)
        prefix = (r.stdout or "").strip()
        if r.returncode or Path(prefix).resolve() != src.parents[1].resolve():
            log.warning("PDFactory.exe does not start the venv (rc=%s, %s %s)", r.returncode, prefix, r.stderr[-200:])
            tmp.unlink(missing_ok=True)
            return str(src)
        old = dst.with_name("PDFactory.old.exe")
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            if dst.exists():
                os.replace(dst, old)     # a running .exe can't be overwritten, but it can be renamed
            os.replace(tmp, dst)
        except OSError:
            tmp.unlink(missing_ok=True)
            log.warning("PDFactory.exe in use, icon updated on next start")
            return str(dst) if dst.exists() else str(src)
        ok_flag.write_text(stamp)
        for oldname in ("PDFabrika.exe", "PDFabrika.ok", "PDFabrika.old.exe"):     # previous app name
            try:
                (src.parent / oldname).unlink(missing_ok=True)
            except OSError:
                pass
        log.info("PDFactory.exe ready")
        return str(dst)
    except Exception:
        log.exception("PDFactory.exe not made")
        return str(dst) if dst.exists() else str(src)


def _set_exe_icon(exe: Path, ico: Path):
    """Replaces the icon group of an .exe with the icons from an .ico (pywin32 resource API)."""
    import struct
    import win32api
    import win32con
    data = ico.read_bytes()
    _, _, count = struct.unpack_from("<HHH", data, 0)
    entries = [struct.unpack_from("<BBBBHHII", data, 6 + 16 * i) for i in range(count)]
    mod = win32api.LoadLibraryEx(str(exe), 0, 0x2)  # LOAD_LIBRARY_AS_DATAFILE
    try:
        groups = win32api.EnumResourceNames(mod, win32con.RT_GROUP_ICON) or [1]
        langs = win32api.EnumResourceLanguages(mod, win32con.RT_GROUP_ICON, groups[0]) or [1033]
    finally:
        win32api.FreeLibrary(mod)
    h = win32api.BeginUpdateResource(str(exe), False)
    grp = struct.pack("<HHH", 0, 1, count)
    for i, (w, hh, colors, res, planes, bits, size, off) in enumerate(entries):
        rid = 200 + i
        win32api.UpdateResource(h, win32con.RT_ICON, rid, data[off:off + size], langs[0])
        grp += struct.pack("<BBBBHHIH", w, hh, colors, res, planes, bits, size, rid)
    win32api.UpdateResource(h, win32con.RT_GROUP_ICON, groups[0], grp, langs[0])
    win32api.EndUpdateResource(h, False)


def _ps(script: str) -> bool:
    """Runs a PowerShell script from a file in data/tmp (quotes in -Command get mangled by Windows)."""
    import tempdir
    f = tempdir.file(".ps1", "ps")
    f.write_text(script, encoding="utf-8-sig")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(f)],
                           capture_output=True, text=True, creationflags=NOWIN, timeout=60)
    finally:
        f.unlink(missing_ok=True)
    if r.returncode:
        log.error("powershell: %s", (r.stderr or r.stdout)[-400:])
    return r.returncode == 0


def _shortcut(lnk: Path, args: str = ""):
    q = lambda v: str(v).replace("'", "''")        # PowerShell single-quoted strings
    s = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{q(lnk)}')\n"
         f"$s.TargetPath = '{q(app_exe())}'\n"
         f"$s.Arguments = '\"{q(LAUNCHER)}\" {q(args)}'\n"
         f"$s.WorkingDirectory = '{q(APP_DIR)}'\n"
         f"$s.IconLocation = '{q(ICON)},0'\n"
         f"$s.Description = 'PDFactory'\n"
         "$s.Save()\n")
    return _ps(s)


def _desktop() -> Path:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            return Path(os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0]))
    except OSError:
        return Path.home() / "Desktop"


def _startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def desktop_shortcut():
    """P1: one shortcut; old shortcuts of this app (PDFabrika, other names) are removed."""
    d = _desktop()
    for old in d.glob("*.lnk"):
        if old.name != "PDFactory.lnk" and any(n in old.name.lower() for n in ("pdfabrika", "pdfactory")):
            try:
                old.unlink()
            except OSError:
                pass
    ok = _shortcut(d / "PDFactory.lnk")
    log.info("desktop shortcut: %s", ok)
    return ok


def autostart_enabled() -> bool:
    return WIN and any((_startup_dir() / n).exists() for n in ("PDFactory.lnk", "PDFabrika.lnk"))


def set_autostart(on: bool):
    if not WIN:
        return False
    (_startup_dir() / "PDFabrika.lnk").unlink(missing_ok=True)      # old name
    lnk = _startup_dir() / "PDFactory.lnk"
    if on:
        return _shortcut(lnk, "--tiho")
    lnk.unlink(missing_ok=True)
    return True


def register():
    """Registers PDFactory as a PDF program so it is offered in Windows 'Default apps'."""
    if not WIN:
        return False
    import winreg
    exe = app_exe()
    cmd = f'"{exe}" "{LAUNCHER}" "%1"'
    C = winreg.HKEY_CURRENT_USER

    def put(path, name, value):
        with winreg.CreateKey(C, path) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    base = rf"Software\Classes\{PROGID}"
    put(base, "", "PDF document")
    put(base + r"\DefaultIcon", "", f"{FILE_ICON},0")
    put(base + r"\shell\open\command", "", cmd)
    put(base + r"\shell\open", "FriendlyAppName", NAME)
    put(base + r"\Application", "ApplicationName", NAME)
    put(base + r"\Application", "ApplicationIcon", f"{ICON},0")
    put(base + r"\Application", "ApplicationCompany", "VAJB")
    # name Windows shows for the program file (otherwise 'Python' from pythonw.exe)
    mui = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
    for e in {exe, pythonw()}:
        put(mui, e + ".FriendlyAppName", NAME)
        put(mui, e + ".ApplicationCompany", "VAJB")
    put(r"Software\Classes\.pdf\OpenWithProgids", PROGID, "")
    if Path(exe).name == "PDFactory.exe":     # never on pythonw.exe: that key is shared by every Python app
        app = r"Software\Classes\Applications\PDFactory.exe"
        put(app, "FriendlyAppName", NAME)
        put(app + r"\shell\open\command", "", cmd)
        put(app + r"\SupportedTypes", ".pdf", "")
    for old in (r"Software\Classes\Applications\PDFabrika.exe\shell\open\command", r"Software\Classes\Applications\PDFabrika.exe\shell\open",
                r"Software\Classes\Applications\PDFabrika.exe\shell", r"Software\Classes\Applications\PDFabrika.exe\SupportedTypes",
                r"Software\Classes\Applications\PDFabrika.exe",         # 0.1.x exe name
                r"Software\Classes\Applications\PDFabrika.pyw\shell\open\command", r"Software\Classes\Applications\PDFabrika.pyw\shell\open",
                r"Software\Classes\Applications\PDFabrika.pyw\shell", r"Software\Classes\Applications\PDFabrika.pyw\SupportedTypes",
                r"Software\Classes\Applications\PDFabrika.pyw"):      # 0.1.0 registered the .pyw
        try:
            winreg.DeleteKey(C, old)
        except OSError:
            pass
    cap = r"Software\PDFabrika\Capabilities"
    put(cap, "ApplicationName", NAME)
    put(cap, "ApplicationDescription", "Read and edit PDF files")
    put(cap, "ApplicationIcon", f"{ICON},0")
    put(cap + r"\FileAssociations", ".pdf", PROGID)
    put(r"Software\RegisteredApplications", "PDFabrika", cap)
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:
        pass
    log.info("registered as PDF program")
    return True


_FILEEXTS = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf"


def current_default() -> str:
    """ProgId Windows really uses for .pdf. Asked from the shell (AssocQueryString), which knows every
    Windows 11 variant; the registry (UserChoiceLatest\\ProgId, UserChoiceLatest, UserChoice) is the fallback."""
    if not WIN:
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        f = ctypes.windll.shlwapi.AssocQueryStringW
        f.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        n = wintypes.DWORD(512)
        buf = ctypes.create_unicode_buffer(512)
        if f(0, 20, ".pdf", None, buf, ctypes.byref(n)) == 0 and buf.value:   # ASSOCSTR_PROGID
            return buf.value
    except Exception:
        log.exception("AssocQueryString")
    import winreg
    for sub, name in (("UserChoiceLatest\\ProgId", "ProgId"), ("UserChoiceLatest", "ProgId"), ("UserChoice", "ProgId")):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _FILEEXTS + "\\" + sub) as k:
                v = winreg.QueryValueEx(k, name)[0]
                if v:
                    return v
        except OSError:
            pass
    return ""


def is_default() -> bool:
    cur = current_default()
    ok = cur == PROGID or any(n in cur.lower() for n in ("pdfabrika", "pdfactory"))   # also "Applications\\PDFactory.exe" ("Open with")
    global _last_default
    if cur != _last_default:          # logged once per change, the settings window asks every 1.5 s
        log.info("PDF default is %r", cur)
        _last_default = cur
    return ok


_last_default = None


def _front_settings_window(timeout=8.0):
    """Settings opened by the background server starts behind the app (Windows foreground lock).
    Finds its window and brings it to the front (Alt-key trick unlocks SetForegroundWindow)."""
    import ctypes
    import time
    from ctypes import wintypes
    u = ctypes.windll.user32
    titles = ("Settings", "Postavke", "Settings", "Postavke sustava", "Einstellungen")
    end = time.time() + timeout
    while time.time() < end:
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(h, _):
            if u.IsWindowVisible(h):
                b = ctypes.create_unicode_buffer(128)
                u.GetWindowTextW(h, b, 128)
                c = ctypes.create_unicode_buffer(64)
                u.GetClassNameW(h, c, 64)
                if b.value in titles and c.value == "ApplicationFrameWindow":
                    found.append(h)
            return True
        u.EnumWindows(each, 0)
        if found:
            h = found[0]
            u.keybd_event(0x12, 0, 0, 0)        # Alt down
            u.keybd_event(0x12, 0, 2, 0)        # Alt up
            if u.IsIconic(h):
                u.ShowWindow(h, 9)
            u.SetForegroundWindow(h)
            u.BringWindowToTop(h)
            log.info("settings window in front")
            return True
        time.sleep(0.25)
    log.warning("settings window not found")
    return False


def open_default_apps():
    """Windows lets only the user pick the default program: opens the PDFactory page in Settings, in front."""
    register()
    os.startfile("ms-settings:defaultapps?registeredAppUser=PDFabrika")
    threading.Thread(target=_front_settings_window, name="podesavanja-napred", daemon=True).start()


def unregister():
    """Uninstall: removes what register() and set_autostart() wrote (HKCU only)."""
    if not WIN:
        return
    import winreg
    C = winreg.HKEY_CURRENT_USER

    def rmtree(path):
        try:
            with winreg.OpenKey(C, path) as k:
                subs = []
                i = 0
                while True:
                    try:
                        subs.append(winreg.EnumKey(k, i))
                        i += 1
                    except OSError:
                        break
            for sub in subs:
                rmtree(path + "\\" + sub)
            winreg.DeleteKey(C, path)
        except OSError:
            pass

    def rmval(path, name):
        try:
            with winreg.OpenKey(C, path, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except OSError:
            pass
    rmtree(rf"Software\Classes\{PROGID}")
    rmtree(r"Software\Classes\Applications\PDFactory.exe")
    rmtree(r"Software\PDFabrika")
    rmval(r"Software\Classes\.pdf\OpenWithProgids", PROGID)
    rmval(r"Software\RegisteredApplications", "PDFabrika")
    for n in ("PDFactory.lnk", "PDFabrika.lnk"):
        (_startup_dir() / n).unlink(missing_ok=True)
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass
    log.info("unregistered")


def install():
    """Called by Instaliraj.vbs (--instaliraj): shortcut, autostart, file association."""
    desktop_shortcut()
    set_autostart(True)
    register()


# ---------- file dialogs (standard Windows Open / Save / folder, owned by the app window) ----------
# Plain Win32 (comdlg32 / shell32) through ctypes: no tkinter, which the installed build's embedded Python lacks.

_dlg_lock = threading.Lock()


def _owner():
    """The PDFactory window, so the dialog opens in front of it and is modal to it."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(h, _):
        if u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(h, b, 256)
            if b.value.startswith(NAME):
                found.append(h)
        return True
    u.EnumWindows(each, 0)
    if found:
        u.keybd_event(0x12, 0, 0, 0)
        u.keybd_event(0x12, 0, 2, 0)
        u.SetForegroundWindow(found[0])
    return found[0] if found else None


def _ofn(title, initial_dir, initial_file, filters, flags, save=False, def_ext=None):
    import ctypes
    from ctypes import wintypes

    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [("lStructSize", wintypes.DWORD), ("hwndOwner", wintypes.HWND), ("hInstance", wintypes.HINSTANCE),
                    ("lpstrFilter", wintypes.LPCWSTR), ("lpstrCustomFilter", wintypes.LPWSTR), ("nMaxCustFilter", wintypes.DWORD),
                    ("nFilterIndex", wintypes.DWORD), ("lpstrFile", ctypes.c_void_p), ("nMaxFile", wintypes.DWORD),
                    ("lpstrFileTitle", wintypes.LPWSTR), ("nMaxFileTitle", wintypes.DWORD), ("lpstrInitialDir", wintypes.LPCWSTR),
                    ("lpstrTitle", wintypes.LPCWSTR), ("Flags", wintypes.DWORD), ("nFileOffset", wintypes.WORD),
                    ("nFileExtension", wintypes.WORD), ("lpstrDefExt", wintypes.LPCWSTR), ("lCustData", wintypes.LPARAM),
                    ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", wintypes.LPCWSTR), ("pvReserved", ctypes.c_void_p),
                    ("dwReserved", wintypes.DWORD), ("FlagsEx", wintypes.DWORD)]
    n = 65536
    buf = ctypes.create_unicode_buffer(n)
    if initial_file:
        buf.value = initial_file
    o = OPENFILENAMEW()
    o.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    o.hwndOwner = _owner()
    o.lpstrFilter = "".join(f"{a}\0{b}\0" for a, b in filters) + "\0"
    o.lpstrFile = ctypes.cast(buf, ctypes.c_void_p)
    o.nMaxFile = n
    o.lpstrInitialDir = initial_dir
    o.lpstrTitle = title
    o.Flags = flags
    o.lpstrDefExt = def_ext
    fn = ctypes.windll.comdlg32.GetSaveFileNameW if save else ctypes.windll.comdlg32.GetOpenFileNameW
    if not fn(ctypes.byref(o)):
        return None
    raw = ctypes.wstring_at(ctypes.addressof(buf), n)
    return raw.split("\0\0", 1)[0].split("\0")


def ask_open(initial_dir: str | None = None, multiple=True) -> list[str]:
    with _dlg_lock:
        OFN_EXPLORER, OFN_FILEMUSTEXIST, OFN_ALLOWMULTISELECT, OFN_HIDEREADONLY = 0x80000, 0x1000, 0x200, 0x4
        parts = _ofn("Open", initial_dir or str(Path.home() / "Documents"), None,
                     [("PDF and images", "*.pdf;*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tif;*.tiff"), ("All files", "*.*")],
                     OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_HIDEREADONLY | (OFN_ALLOWMULTISELECT if multiple else 0))
        if not parts:
            return []
        if len(parts) == 1:
            return parts
        return [str(Path(parts[0]) / f) for f in parts[1:]]       # folder, then the file names


def ask_save(initial: str | None) -> str | None:
    with _dlg_lock:
        OFN_EXPLORER, OFN_OVERWRITEPROMPT, OFN_HIDEREADONLY = 0x80000, 0x2, 0x4
        p = Path(initial) if initial else Path.home() / "Documents" / "document.pdf"
        parts = _ofn("Save as", str(p.parent), p.name, [("PDF", "*.pdf")],
                     OFN_EXPLORER | OFN_OVERWRITEPROMPT | OFN_HIDEREADONLY, save=True, def_ext="pdf")
        return parts[0] if parts else None


def ask_folder(initial: str | None) -> str | None:
    with _dlg_lock:
        import ctypes
        from ctypes import wintypes

        class BROWSEINFOW(ctypes.Structure):
            _fields_ = [("hwndOwner", wintypes.HWND), ("pidlRoot", ctypes.c_void_p), ("pszDisplayName", wintypes.LPWSTR),
                        ("lpszTitle", wintypes.LPCWSTR), ("ulFlags", wintypes.UINT), ("lpfn", ctypes.c_void_p),
                        ("lParam", wintypes.LPARAM), ("iImage", ctypes.c_int)]
        ctypes.windll.ole32.CoInitialize(None)
        name = ctypes.create_unicode_buffer(260)
        bi = BROWSEINFOW(hwndOwner=_owner(), pszDisplayName=name, lpszTitle="Choose folder", ulFlags=0x0041)  # NEWDIALOGSTYLE | RETURNONLYFSDIRS
        sh = ctypes.windll.shell32
        sh.SHBrowseForFolderW.restype = ctypes.c_void_p
        pidl = sh.SHBrowseForFolderW(ctypes.byref(bi))
        if not pidl:
            return None
        path = ctypes.create_unicode_buffer(1024)
        sh.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
        ok = sh.SHGetPathFromIDListW(pidl, path)
        ctypes.windll.ole32.CoTaskMemFree(ctypes.c_void_p(pidl))
        return path.value if ok else None


def show_in_folder(path: str):
    if WIN:
        subprocess.Popen(["explorer", "/select,", str(Path(path))], creationflags=NOWIN)
