"""PDFabrika - instalacija sa prozorom napretka (pokreće je Instaliraj.vbs sistemskim Python-om).

Koraci: .venv -> paketi -> srpski OCR jezici -> PDFabrika.pyw --instaliraj (prečica, start sa Windows-om,
PDF program) i otvaranje aplikacije. Drugi dvoklik dok instalacija radi samo vrati ovaj prozor napred.
Izlaz svih koraka ide u data/logs/instalacija.log (dopisuje se).
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
LOG = LOGS / "instalacija.log"
LOCK = APP / "data" / "instalacija.lock"
VENV = APP / ".venv"
PY = VENV / "Scripts" / "python.exe"
PYW = VENV / "Scripts" / "pythonw.exe"
OCR_SRC = Path(r"D:\VAJB\kontrolaizbora\podaci\ocr\tessdata")
NOWIN = 0x08000000
TITLE = "PDFabrika - instalacija"
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
                status(t.replace("Collecting", "Preuzimam").replace("Downloading", "Preuzimam")
                       .replace("Installing collected packages:", "Instaliram:")[:70])
    return p.wait()


class Win:
    def __init__(self):
        self.r = tk.Tk()
        self.r.title(TITLE)
        self.r.configure(bg=BG)
        self.r.resizable(False, False)
        try:
            self.r.iconbitmap(str(APP / "assets" / "pdfabrika.ico"))
        except Exception:
            pass
        w, h = 460, 190
        self.r.geometry(f"{w}x{h}+{(self.r.winfo_screenwidth() - w) // 2}+{(self.r.winfo_screenheight() - h) // 2}")
        st = ttk.Style(self.r)
        st.theme_use("clam")
        st.configure("A.Horizontal.TProgressbar", troughcolor="#2a2d33", background=ACCENT, bordercolor=BG,
                     lightcolor=ACCENT, darkcolor=ACCENT)
        tk.Label(self.r, text="PDFabrika", bg=BG, fg=FG, font=("Segoe UI Semibold", 15)).pack(pady=(26, 6))
        self.msg = tk.Label(self.r, text="Pripremam…", bg=BG, fg=MUTED, font=("Segoe UI", 10), wraplength=400)
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
            for label, fn in (("Otvori dnevnik", lambda: os.startfile(LOG)), ("Zatvori", self.r.destroy)):
                tk.Button(self.btns, text=label, command=fn, bg="#1a1c20", fg=FG, activebackground="#2a2d33",
                          activeforeground=FG, relief="flat", padx=14, pady=4, bd=0).pack(side="left", padx=6)
        self.r.after(0, f)


def work(w: Win):
    try:
        log("=== instalacija ===")
        if not PY.exists():
            w.status("Pravim Python okruženje…", 5)
            w.busy()
            base = Path(sys.executable).with_name("python.exe")
            if run([base if base.exists() else sys.executable, "-m", "venv", VENV], w.status):
                return w.fail("Python okruženje nije napravljeno.")
        w.status("Instaliram pakete (prvi put traje 1–3 minuta)…", 20)
        w.busy()
        run([PY, "-m", "pip", "install", "--upgrade", "pip", "-q"], w.status)
        if run([PY, "-m", "pip", "install", "-r", APP / "requirements.txt"], w.status):
            return w.fail("Paketi nisu instalirani. Pošalji Claude-u dnevnik.")
        w.status("Jezici za prepoznavanje teksta…", 85)
        for name in ("srp.traineddata", "srp_latn.traineddata"):
            if (OCR_SRC / name).exists() and not (APP / "tessdata" / name).exists():
                shutil.copy2(OCR_SRC / name, APP / "tessdata" / name)
                log(f"copied {name}")
        w.status("Prečica, start sa Windows-om, PDF program…", 95)
        subprocess.Popen([str(PYW), str(APP / "PDFabrika.pyw"), "--instaliraj"], cwd=APP)
        log("PDFabrika.pyw --instaliraj started")
        w.status("Gotovo. PDFabrika se otvara.", 100, ACCENT)
        time.sleep(2.5)
        w.r.after(0, w.r.destroy)
    except Exception as e:
        log(f"ERROR {e!r}")
        w.fail("Instalacija nije uspela. Pošalji Claude-u dnevnik.")


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
