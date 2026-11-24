"""PDFactory - setup with a progress window ("Install PDFactory.vbs" starts it with the system Python).

Steps: .venv -> packages -> Serbian OCR languages -> PDFactory.pyw --instaliraj (shortcut, start with Windows,
PDF app) and the app opens. A second double click while setup runs only brings this window to the front.
Output of every step goes to data/logs/install.log (appended).
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

APP = Path(__file__).resolve().parent
LOGS = APP / "data" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
LOG = LOGS / "install.log"
LOCK = APP / "data" / "install.lock"
VENV = APP / ".venv"
PY = VENV / "Scripts" / "python.exe"
PYW = VENV / "Scripts" / "pythonw.exe"
OCR_SRC = Path(r"D:\VAJB\kontrolaizbora\podaci\ocr\tessdata")
NOWIN = 0x08000000
TITLE = "PDFactory - setup"
BG, FG, MUTED, ACCENT, RED = "#121316", "#e8e9eb", "#9a9ea6", "#d9a441", "#e5484d"


def log(line):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {line}\n")


def other_running() -> bool:
    """Another installer window is open: bring it to the front and stop (P5: no os.kill)."""
    if not LOCK.exists():
        return False
    try:
        import ctypes
        pid = int(LOCK.read_text().strip())
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        if code.value != 259:
            return False
        u = ctypes.windll.user32
        w = u.FindWindowW(None, TITLE)
        if w:
            u.ShowWindow(w, 9)
            u.SetForegroundWindow(w)
        return True
    except Exception:
        return False


def run(cmd, status):
    log("$ " + " ".join(str(c) for c in cmd))
    p = subprocess.Popen([str(c) for c in cmd], cwd=APP, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
    with open(LOG, "a", encoding="utf-8") as f:
        for line in p.stdout:
            f.write(line)
            t = line.strip()
            if t.startswith(("Collecting", "Downloading", "Installing collected")):
                status(t.replace("Collecting", "Downloading").replace("Downloading", "Downloading")
                       .replace("Installing collected packages:", "Installing:")[:70])
    return p.wait()


class Win:
    def __init__(self):
        self.r = tk.Tk()
        self.r.title(TITLE)
        self.r.configure(bg=BG)
        self.r.resizable(False, False)
        try:
            self.r.iconbitmap(str(APP / "assets" / "pdfactory.ico"))
        except Exception:
            pass
        w, h = 460, 190
        self.r.geometry(f"{w}x{h}+{(self.r.winfo_screenwidth() - w) // 2}+{(self.r.winfo_screenheight() - h) // 2}")
        st = ttk.Style(self.r)
        st.theme_use("clam")
        st.configure("A.Horizontal.TProgressbar", troughcolor="#2a2d33", background=ACCENT, bordercolor=BG,
                     lightcolor=ACCENT, darkcolor=ACCENT)
        tk.Label(self.r, text="PDFactory", bg=BG, fg=FG, font=("Segoe UI Semibold", 15)).pack(pady=(26, 6))
        self.msg = tk.Label(self.r, text="Preparing…", bg=BG, fg=MUTED, font=("Segoe UI", 10), wraplength=400)
        self.msg.pack()
        self.bar = ttk.Progressbar(self.r, style="A.Horizontal.TProgressbar", length=400, maximum=100)
        self.bar.pack(pady=18)
        self.btns = tk.Frame(self.r, bg=BG)
        self.btns.pack()

    def status(self, text, pct=None, color=MUTED):
        def f():
            self.msg.configure(text=text, fg=color)
            if pct is not None:
                self.bar.stop()
                self.bar.configure(mode="determinate", value=pct)
        self.r.after(0, f)

    def busy(self):
        self.r.after(0, lambda: (self.bar.configure(mode="indeterminate"), self.bar.start(12)))

    def fail(self, text):
        def f():
            self.status(text, 0, RED)
            for label, fn in (("Open log", lambda: os.startfile(LOG)), ("Close", self.r.destroy)):
                tk.Button(self.btns, text=label, command=fn, bg="#1a1c20", fg=FG, activebackground="#2a2d33",
                          activeforeground=FG, relief="flat", padx=14, pady=4, bd=0).pack(side="left", padx=6)
        self.r.after(0, f)


def work(w: Win):
    try:
        log("=== instalacija ===")
        if not PY.exists():
            w.status("Creating the Python environment…", 5)
            w.busy()
            base = Path(sys.executable).with_name("python.exe")
            if run([base if base.exists() else sys.executable, "-m", "venv", VENV], w.status):
                return w.fail("The Python environment was not created.")
        w.status("Installing packages (1–3 minutes the first time)…", 20)
        w.busy()
        run([PY, "-m", "pip", "install", "--upgrade", "pip", "-q"], w.status)
        if run([PY, "-m", "pip", "install", "-r", APP / "requirements.txt"], w.status):
            return w.fail("Packages were not installed. Send the log to Claude.")
        w.status("Text recognition languages…", 85)
        for name in ("srp.traineddata", "srp_latn.traineddata"):
            if (OCR_SRC / name).exists() and not (APP / "tessdata" / name).exists():
                shutil.copy2(OCR_SRC / name, APP / "tessdata" / name)
                log(f"copied {name}")
        w.status("Shortcut, start with Windows, PDF app…", 95)
        subprocess.Popen([str(PYW), str(APP / "PDFactory.pyw"), "--instaliraj"], cwd=APP)
        log("PDFactory.pyw --instaliraj started")
        w.status("Done. PDFactory is opening.", 100, ACCENT)
        time.sleep(2.5)
        w.r.after(0, w.r.destroy)
    except Exception as e:
        log(f"ERROR {e!r}")
        w.fail("Installation failed. Send the log to Claude.")


def main():
    if other_running():
        return
    LOCK.write_text(str(os.getpid()))
    try:
        w = Win()
        threading.Thread(target=work, args=(w,), daemon=True).start()
        w.r.mainloop()
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
