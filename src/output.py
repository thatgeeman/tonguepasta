import ctypes
import ctypes.wintypes
import os
import sys
import time

import pyperclip
from pynput.keyboard import Controller, Key

_kb = Controller()

# macOS uses Cmd+V to paste; Windows and Linux use Ctrl+V
_PASTE_MOD = Key.cmd if sys.platform == "darwin" else Key.ctrl

if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
else:
    _user32 = None
    _kernel32 = None

_log_path: str | None = None


def set_log_path(path: str):
    global _log_path
    _log_path = path


def _log(msg: str):
    if not _log_path:
        return
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")
    with open(_log_path, "a") as f:
        f.write(f"{ts} [output] {msg}\n")


def _focus(hwnd: int):
    if not _user32 or not hwnd:
        return

    fg = _user32.GetForegroundWindow()
    _log(f"_focus: target={hwnd} current_fg={fg}")

    if fg == hwnd:
        _log("_focus: already focused, skip")
        return

    fg_tid = _user32.GetWindowThreadProcessId(fg, None)
    cur_tid = _kernel32.GetCurrentThreadId()
    _log(f"_focus: fg_tid={fg_tid} cur_tid={cur_tid}")

    # Attach to foreground thread so Windows grants us permission to switch
    attached = fg_tid and fg_tid != cur_tid
    if attached:
        _user32.AttachThreadInput(cur_tid, fg_tid, True)

    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, 9)  # SW_RESTORE only if minimized
    result = _user32.SetForegroundWindow(hwnd)
    _user32.BringWindowToTop(hwnd)
    _log(f"_focus: SetForegroundWindow result={result} new_fg={_user32.GetForegroundWindow()}")

    if attached:
        _user32.AttachThreadInput(cur_tid, fg_tid, False)

    time.sleep(0.15)


def send_text(text: str, target_hwnd: int | None = None, return_hwnd: int | None = None):
    _log(f"send_text: target_hwnd={target_hwnd} return_hwnd={return_hwnd}")
    if target_hwnd:
        _focus(target_hwnd)
    pyperclip.copy(text)
    time.sleep(0.05)
    _kb.press(_PASTE_MOD)
    _kb.press('v')
    _kb.release('v')
    _kb.release(_PASTE_MOD)
    if return_hwnd:
        time.sleep(0.05)
        _focus(return_hwnd)
