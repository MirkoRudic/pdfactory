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
LAUNCHER = APP_DIR / "PDFabrika.pyw"
ICON = APP_DIR / "assets" / "pdfabrika.ico"
PROGID = "PDFabrika.PDF"
NOWIN = 0x08000000
WIN = sys.platform == "win32"


def pythonw() -> str:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def app_exe() -> str:
    """PDFabrika.exe = copy of the venv's pythonw.exe with our icon. Windows shows the program's
    name and icon from the .exe, so with pythonw.exe it says 'Python' in Default apps and Task Manager.
    Falls back to pythonw.exe when the copy can't be made or doesn't start the venv."""
    if not WIN:
        return pythonw()
    src = Path(pythonw())
    dst = src.with_name("PDFabrika.exe")
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
            log.warning("PDFabrika.exe does not start the venv (rc=%s, %s %s)", r.returncode, prefix, r.stderr[-200:])
            tmp.unlink(missing_ok=True)
            return str(src)
        os.replace(tmp, dst)
        ok_flag.write_text(stamp)
        log.info("PDFabrika.exe ready")
        return str(dst)
    except Exception:
        log.exception("PDFabrika.exe not made")
        return str(src)


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
         f"$s.Description = 'PDFabrika'\n"
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
    """P1: one shortcut; an old PDFabrika shortcut under another name is removed."""
    d = _desktop()
    for old in d.glob("*.lnk"):
        if old.name != "PDFabrika.lnk" and "pdfabrika" in old.name.lower():
            try:
                old.unlink()
            except OSError:
                pass
    ok = _shortcut(d / "PDFabrika.lnk")
    log.info("desktop shortcut: %s", ok)
    return ok


def autostart_enabled() -> bool:
    return WIN and (_startup_dir() / "PDFabrika.lnk").exists()


def set_autostart(on: bool):
    if not WIN:
        return False
    lnk = _startup_dir() / "PDFabrika.lnk"
    if on:
        return _shortcut(lnk, "--tiho")
    lnk.unlink(missing_ok=True)
    return True


def register():
    """Registers PDFabrika as a PDF program so it is offered in Windows 'Default apps'."""
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
    put(base, "", "PDF dokument")
    put(base + r"\DefaultIcon", "", f"{ICON},0")
    put(base + r"\shell\open\command", "", cmd)
    put(base + r"\shell\open", "FriendlyAppName", "PDFabrika")
    put(base + r"\Application", "ApplicationName", "PDFabrika")
    put(base + r"\Application", "ApplicationIcon", f"{ICON},0")
    put(base + r"\Application", "ApplicationCompany", "VAJB")
    # name Windows shows for the program file (otherwise 'Python' from pythonw.exe)
    mui = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
    for e in {exe, pythonw()}:
        put(mui, e + ".FriendlyAppName", "PDFabrika")
        put(mui, e + ".ApplicationCompany", "VAJB")
    put(r"Software\Classes\.pdf\OpenWithProgids", PROGID, "")
    if Path(exe).name == "PDFabrika.exe":     # never on pythonw.exe: that key is shared by every Python app
        app = r"Software\Classes\Applications\PDFabrika.exe"
        put(app, "FriendlyAppName", "PDFabrika")
        put(app + r"\shell\open\command", "", cmd)
        put(app + r"\SupportedTypes", ".pdf", "")
    for old in (r"Software\Classes\Applications\PDFabrika.pyw\shell\open\command", r"Software\Classes\Applications\PDFabrika.pyw\shell\open",
                r"Software\Classes\Applications\PDFabrika.pyw\shell", r"Software\Classes\Applications\PDFabrika.pyw\SupportedTypes",
                r"Software\Classes\Applications\PDFabrika.pyw"):      # 0.1.0 registered the .pyw
        try:
            winreg.DeleteKey(C, old)
        except OSError:
            pass
    cap = r"Software\PDFabrika\Capabilities"
    put(cap, "ApplicationName", "PDFabrika")
    put(cap, "ApplicationDescription", "Čitanje i izmene PDF fajlova")
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


def is_default() -> bool:
    if not WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice") as k:
            return winreg.QueryValueEx(k, "ProgId")[0] == PROGID
    except OSError:
        return False


def current_default() -> str:
    if not WIN:
        return ""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice") as k:
            return winreg.QueryValueEx(k, "ProgId")[0]
    except OSError:
        return ""


def open_default_apps():
    """Windows lets only the user pick the default program: opens the PDFabrika page in Settings."""
    register()
    os.startfile("ms-settings:defaultapps?registeredAppUser=PDFabrika")


def install():
    """Called by Instaliraj.vbs (--instaliraj): shortcut, autostart, file association."""
    desktop_shortcut()
    set_autostart(True)
    register()


# ---------- file dialogs (Windows standard Open / Save, owned by the app window) ----------

_dlg_lock = threading.Lock()


def _tk():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        root.iconbitmap(str(ICON))
    except Exception:
        pass
    return root


def ask_open(initial_dir: str | None = None, multiple=True) -> list[str]:
    with _dlg_lock:
        from tkinter import filedialog
        root = _tk()
        try:
            res = filedialog.askopenfilenames(
                parent=root, title="Otvori", initialdir=initial_dir or str(Path.home() / "Documents"),
                filetypes=[("PDF i slike", "*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("Svi fajlovi", "*.*")])
            return list(res) if multiple else list(res)[:1]
        finally:
            root.destroy()


def ask_save(initial: str | None) -> str | None:
    with _dlg_lock:
        from tkinter import filedialog
        root = _tk()
        try:
            p = Path(initial) if initial else Path.home() / "Documents" / "dokument.pdf"
            res = filedialog.asksaveasfilename(parent=root, title="Sačuvaj kao", initialdir=str(p.parent),
                                               initialfile=p.name, defaultextension=".pdf",
                                               filetypes=[("PDF", "*.pdf")])
            return res or None
        finally:
            root.destroy()


def ask_folder(initial: str | None) -> str | None:
    with _dlg_lock:
        from tkinter import filedialog
        root = _tk()
        try:
            return filedialog.askdirectory(parent=root, title="Izaberi folder", initialdir=initial) or None
        finally:
            root.destroy()


def show_in_folder(path: str):
    if WIN:
        subprocess.Popen(["explorer", "/select,", str(Path(path))], creationflags=NOWIN)
