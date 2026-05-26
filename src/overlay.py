import ctypes
import math
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont

_q: queue.Queue = queue.Queue()

_HEIGHT = 52
_PAD_X = 18
_DOT_R = 11
_DOT_GAP = 14
_FONT_SIZE = 20

import sys as _sys
if _sys.platform == "darwin":
    _FONT_FAMILY = "Helvetica Neue"
elif _sys.platform == "win32":
    _FONT_FAMILY = "Segoe UI"
else:
    _FONT_FAMILY = "DejaVu Sans"

_STATES = {
    "rec":  {"text": "REC",  "lo": (170, 0,   0),   "hi": (255, 30,  30)},
    "lock": {"text": "LOCK", "lo": (100, 0,   160),  "hi": (180, 30,  255)},
    "save": {"text": "SAVE", "lo": (140, 80,  0),    "hi": (220, 140, 0)},
    "trns": {"text": "TRNS", "lo": (0,   100, 140),  "hi": (0,   180, 220)},
    "cast": {"text": "CAST", "lo": (160, 90,  0),    "hi": (255, 160, 0)},
    "form": {"text": "FORM", "lo": (40,  60,  180),  "hi": (90,  130, 255)},
    "impr": {"text": "IMPR", "lo": (0,   120, 100),  "hi": (0,   210, 170)},
}

# Corgi colors
_CORGI_BODY  = "#D4860A"
_CORGI_DARK  = "#8B5E0A"
_CORGI_WHITE = "#F5E6D0"
_CORGI_BLACK = "#1a1a1a"

_CORGI_W  = 120
_CORGI_H  = 70
_CORGI_SPD = 7    # pixels per frame
_CORGI_FPS = 40   # ms per frame


def _hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"


def _draw_corgi(canvas, frame):
    """Draw a left-facing corgi on a 120×70 canvas."""
    canvas.delete("all")
    wag = 6 if frame % 6 < 3 else -6

    # Tail (right side, wags up/down)
    canvas.create_oval(88, 20 + wag, 112, 36 + wag, fill=_CORGI_WHITE, outline="")

    # Body
    canvas.create_oval(22, 26, 96, 56, fill=_CORGI_BODY, outline="")
    # Belly patch
    canvas.create_oval(32, 32, 86, 54, fill=_CORGI_WHITE, outline="")

    # Legs — two pairs alternate for running
    if frame % 4 < 2:
        canvas.create_rectangle(28, 52, 38, 68, fill=_CORGI_DARK,  outline="")
        canvas.create_rectangle(44, 52, 54, 62, fill=_CORGI_BODY,  outline="")
        canvas.create_rectangle(64, 52, 74, 62, fill=_CORGI_BODY,  outline="")
        canvas.create_rectangle(78, 52, 88, 68, fill=_CORGI_DARK,  outline="")
    else:
        canvas.create_rectangle(28, 52, 38, 62, fill=_CORGI_BODY,  outline="")
        canvas.create_rectangle(44, 52, 54, 68, fill=_CORGI_DARK,  outline="")
        canvas.create_rectangle(64, 52, 74, 68, fill=_CORGI_DARK,  outline="")
        canvas.create_rectangle(78, 52, 88, 62, fill=_CORGI_BODY,  outline="")

    # Head (left side, dog faces left)
    canvas.create_oval(4, 12, 40, 44, fill=_CORGI_BODY, outline="")

    # Ears (pointy, dark)
    canvas.create_polygon(6, 16,  14, 2,  22, 16, fill=_CORGI_DARK, outline="")
    canvas.create_polygon(18, 14, 28, 1,  36, 14, fill=_CORGI_DARK, outline="")

    # Eye
    canvas.create_oval(12, 20, 20, 28, fill=_CORGI_BLACK, outline="")
    canvas.create_oval(14, 21, 16, 23, fill="white",       outline="")

    # Nose
    canvas.create_oval(4, 30, 10, 36, fill=_CORGI_BLACK, outline="")


def _launch_corgi(root, word):
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    y = sh - _CORGI_H - 48

    lbl_font = tkfont.Font(family=_FONT_FAMILY, size=9, weight="bold")

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.configure(bg="#111111")

    canvas = tk.Canvas(win, width=_CORGI_W, height=_CORGI_H,
                       bg="#111111", highlightthickness=0)
    canvas.pack()

    lbl = tk.Label(win, text=word.upper(), font=lbl_font,
                   fg="white", bg="#111111")
    lbl.place(x=0, y=0, width=_CORGI_W)

    x_start = sw
    x_end = sw - sw // 4

    win.geometry(f"{_CORGI_W}x{_CORGI_H}+{x_start}+{y}")

    state = {"x": x_start, "frame": 0}

    def step():
        state["x"] -= _CORGI_SPD
        state["frame"] += 1
        _draw_corgi(canvas, state["frame"])
        win.geometry(f"{_CORGI_W}x{_CORGI_H}+{state['x']}+{y}")
        if state["x"] > x_end:
            root.after(_CORGI_FPS, step)
        else:
            try:
                win.destroy()
            except Exception:
                pass

    root.after(_CORGI_FPS, step)


def _show_startup_banner(root):
    font = tkfont.Font(family=_FONT_FAMILY, size=_FONT_SIZE, weight="bold")

    w1 = font.measure("tongue")
    w2 = font.measure("pasta")
    width = _PAD_X + w1 + w2 + _PAD_X

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = sw - width - 16
    y = sh - _HEIGHT - 56

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.95)
    win.configure(bg="#111111")
    win.geometry(f"{width}x{_HEIGHT}+{x}+{y}")

    canvas = tk.Canvas(win, width=width, height=_HEIGHT,
                       bg="#111111", highlightthickness=0)
    canvas.pack()

    cy = _HEIGHT // 2
    canvas.create_text(_PAD_X,          cy, text="tongue", fill="#FF8C5A",
                       font=font, anchor="w")
    canvas.create_text(_PAD_X + w1,     cy, text="pasta",  fill="#FFD166",
                       font=font, anchor="w")

    def _close():
        try:
            win.destroy()
        except Exception:
            pass

    root.after(2500, _close)


def _show_error_popup(root, msg: str):
    popup_w = 380
    hdr_font = tkfont.Font(family=_FONT_FAMILY, size=12, weight="bold")
    msg_font = tkfont.Font(family=_FONT_FAMILY, size=10)

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.95)
    win.configure(bg="#1a0000")

    tk.Frame(win, bg="#cc3333", height=3).pack(fill="x")

    inner = tk.Frame(win, bg="#1a0000", padx=14, pady=10)
    inner.pack(fill="both", expand=True)

    tk.Label(inner, text="ERROR", font=hdr_font,
             fg="#ff5555", bg="#1a0000", anchor="w").pack(fill="x")
    tk.Label(inner, text=msg, font=msg_font,
             fg="#f0f0f0", bg="#1a0000", anchor="w",
             wraplength=popup_w - 28, justify="left").pack(fill="x", pady=(4, 0))

    win.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    popup_h = win.winfo_reqheight()
    win.geometry(f"{popup_w}x{popup_h}+{sw - popup_w - 16}+{sh - popup_h - 56 - _HEIGHT - 12}")

    def _close():
        try:
            win.destroy()
        except Exception:
            pass

    win.bind("<Button-1>", lambda _: _close())
    root.after(8000, _close)


def _run():
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.95)
    root.configure(bg="#111111")
    root.withdraw()

    # Prevent overlay from stealing keyboard focus from the source window
    if _sys.platform == "win32":
        _GWL_EXSTYLE = -20
        _WS_EX_NOACTIVATE = 0x08000000
        hwnd = root.winfo_id()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style | _WS_EX_NOACTIVATE)

    font = tkfont.Font(family=_FONT_FAMILY, size=_FONT_SIZE, weight="bold")

    def make_window(state_key):
        cfg = _STATES[state_key]
        text_w = font.measure(cfg["text"])
        width = _PAD_X + _DOT_R * 2 + _DOT_GAP + text_w + _PAD_X

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = sw - width - 16
        y = sh - _HEIGHT - 56
        root.geometry(f"{width}x{_HEIGHT}+{x}+{y}")

        for w in root.winfo_children():
            w.destroy()

        canvas = tk.Canvas(root, width=width, height=_HEIGHT,
                           bg="#111111", highlightthickness=0)
        canvas.pack()

        cy = _HEIGHT // 2
        dx = _PAD_X + _DOT_R
        dot = canvas.create_oval(dx - _DOT_R, cy - _DOT_R,
                                  dx + _DOT_R, cy + _DOT_R,
                                  fill=_hex(*cfg["lo"]), outline="")
        canvas.create_text(dx + _DOT_R + _DOT_GAP, cy,
                           text=cfg["text"], fill="white",
                           font=font, anchor="w")
        return dot, cfg

    state = {"key": None, "dot": None, "cfg": None, "tick": 0, "running": False}

    def animate():
        if state["running"] and state["dot"]:
            t = (math.sin(state["tick"] * 0.08) + 1) / 2
            lo, hi = state["cfg"]["lo"], state["cfg"]["hi"]
            r = int(lo[0] + (hi[0] - lo[0]) * t)
            g = int(lo[1] + (hi[1] - lo[1]) * t)
            b = int(lo[2] + (hi[2] - lo[2]) * t)
            root.winfo_children()[-1].itemconfig(state["dot"], fill=_hex(r, g, b))
            state["tick"] += 1
        root.after(30, animate)

    def poll():
        try:
            while True:
                msg = _q.get_nowait()
                if msg in _STATES:
                    dot, cfg = make_window(msg)
                    state.update(key=msg, dot=dot, cfg=cfg, tick=0, running=True)
                    root.deiconify()
                elif msg == "hide":
                    state["running"] = False
                    root.withdraw()
                elif msg == "startup":
                    _show_startup_banner(root)
                elif msg.startswith("trigger:"):
                    word = msg[len("trigger:"):]
                    _launch_corgi(root, word)
                elif msg.startswith("error:"):
                    _show_error_popup(root, msg[6:])
        except queue.Empty:
            pass
        root.after(40, poll)

    root.after(0, animate)
    root.after(0, poll)
    root.mainloop()


def push_audio(_chunk):
    pass


def start():
    threading.Thread(target=_run, daemon=True).start()


def startup():
    _q.put("startup")


def show():
    _q.put("rec")


def show_locked():
    _q.put("lock")


def transcribing():
    _q.put("trns")


def saving():
    _q.put("save")


def casting():
    _q.put("cast")


def formatting():
    _q.put("form")


def improving():
    _q.put("impr")


def trigger_detected(word: str):
    _q.put(f"trigger:{word}")


def hide():
    _q.put("hide")


def error(msg: str):
    _q.put(f"error:{msg}")
