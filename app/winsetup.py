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


def _ps(script: str) -> bool:
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True, creationflags=NOWIN, timeout=60)
    if r.returncode:
        log.error("powershell: %s", (r.stderr or r.stdout)[-400:])
    return r.returncode == 0


def _shortcut(lnk: Path, args: str = ""):
    s = (f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{lnk}");'
         f'$s.TargetPath="{pythonw()}";$s.Arguments=\'"{LAUNCHER}" {args}\';'
         f'$s.WorkingDirectory="{APP_DIR}";$s.IconLocation="{ICON},0";$s.Description="PDFabrika";$s.Save()')
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
    cmd = f'"{pythonw()}" "{LAUNCHER}" "%1"'
    C = winreg.HKEY_CURRENT_USER

    def put(path, name, value):
        with winreg.CreateKey(C, path) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    base = rf"Software\Classes\{PROGID}"
    put(base, "", "PDF dokument")
    put(base + r"\DefaultIcon", "", f"{ICON},0")
    put(base + r"\shell\open\command", "", cmd)
    put(r"Software\Classes\.pdf\OpenWithProgids", PROGID, "")
    app = r"Software\Classes\Applications\PDFabrika.pyw"
    put(app, "FriendlyAppName", "PDFabrika")
    put(app + r"\shell\open\command", "", cmd)
    put(app + r"\SupportedTypes", ".pdf", "")
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
