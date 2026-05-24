import sys
import threading
import time

import providers
import pystray
from PIL import Image, ImageDraw, ImageFont

_EMOJI_FONTS = {
    "win32":  ["C:\\Windows\\Fonts\\seguiemj.ttf"],
    "darwin": ["/System/Library/Fonts/Apple Color Emoji.ttc"],
    "linux":  [
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    ],
}

_BOLD_FONTS = {
    "win32":  ["arialbd.ttf", "arial.ttf"],
    "darwin": [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFCompact.ttf",
    ],
    "linux":  [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
}


def _load_emoji_font(size: int):
    for path in _EMOJI_FONTS.get(sys.platform, []):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return None


def _load_font(size: int):
    for path in _BOLD_FONTS.get(sys.platform, []):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

_IDLE_BG     = "#ffffff"
_IDLE_FG     = "#3a7bd5"
_RECORD_BGS  = ["#c02020", "#cc2828", "#d83030", "#e83838",
                 "#f04040", "#e83838", "#d83030", "#cc2828"]
_LOCK_BGS    = ["#6400a0", "#7000b4", "#7c00c8", "#8800dc",
                 "#9400f0", "#8800dc", "#7c00c8", "#7000b4"]

_icon: pystray.Icon | None = None
_stop_anim = threading.Event()
_mode = "normal"
_private = False
_lock_n_load_active = False
_on_lock_n_load_cb = None


def _draw_icon(bg: str, fg: str = "white", size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 6, fill=bg)
    emoji_font = _load_emoji_font(int(size * 0.62))
    if emoji_font:
        ch = "😛"
        bbox = d.textbbox((0, 0), ch, font=emoji_font, embedded_color=True)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (size - tw) // 2 - bbox[0]
        y = (size - th) // 2 - bbox[1]
        d.text((x, y), ch, font=emoji_font, embedded_color=True)
    else:
        font = _load_font(int(size * 0.42))
        bbox = d.textbbox((0, 0), "TP", font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((size - tw) // 2 - bbox[0], (size - th) // 2 - bbox[1]), "TP", font=font, fill=fg)
    return img


_IDLE_IMG    = _draw_icon(_IDLE_BG, _IDLE_FG)
_RECORD_IMGS = [_draw_icon(bg) for bg in _RECORD_BGS]
_LOCK_IMGS   = [_draw_icon(bg) for bg in _LOCK_BGS]

_MODE_LABEL = {
    "normal":               "Normal",
    "markdown":             "Markdown",
    "improve:grammar":      "Grammar",
    "improve:professional": "Professional",
    "improve:concise":      "Concise",
    "improve:casual":       "Casual",
    "improve:caveman":      "Caveman",
}


def get_mode() -> str:
    return _mode


def get_private() -> bool:
    return _private


def get_lock_n_load_active() -> bool:
    return _lock_n_load_active


def set_lock_n_load_active(active: bool):
    global _lock_n_load_active
    _lock_n_load_active = active


def _set_mode(m: str):
    global _mode
    _mode = m
    if _icon:
        _icon.title = _idle_title()


def _toggle_private(icon, _item):
    global _private
    _private = not _private
    if _icon:
        _icon.title = _idle_title()


def _idle_title() -> str:
    parts = []
    if _private:
        parts.append("Stealth")
    if _mode != "normal":
        parts.append(f"{_MODE_LABEL.get(_mode, _mode)} mode")
    suffix = f" [{', '.join(parts)}]" if parts else ""
    return f"tonguepasta{suffix} - hold Right Ctrl to record"


def _animate(lock_mode: bool = False):
    frames = _LOCK_IMGS if lock_mode else _RECORD_IMGS
    frame = 0
    while not _stop_anim.is_set():
        if _icon:
            _icon.icon = frames[frame % len(frames)]
            _icon.title = "tonguepasta - LOCK N LOAD recording..." if lock_mode else "tonguepasta - recording..."
        frame += 1
        time.sleep(0.12)
    if _icon:
        _icon.icon = _IDLE_IMG
        _icon.title = _idle_title()


def set_recording(active: bool, lock_mode: bool = False):
    if active:
        _stop_anim.clear()
        threading.Thread(target=_animate, args=(lock_mode,), daemon=True).start()
    else:
        _stop_anim.set()


_restore_focus = True


def get_restore_focus() -> bool:
    return _restore_focus


def start(on_quit, on_reload_env=None, on_lock_n_load=None, on_configure=None):
    global _icon, _on_lock_n_load_cb
    _on_lock_n_load_cb = on_lock_n_load

    def _quit(icon, _item):
        icon.stop()
        on_quit()

    def _reload(icon, _item):
        if on_reload_env:
            on_reload_env()

    def _configure(icon, _item):
        if on_configure:
            on_configure()

    def _toggle_focus(icon, _item):
        global _restore_focus
        _restore_focus = not _restore_focus

    def _lock_n_load_click(icon, _item):
        if _on_lock_n_load_cb:
            _on_lock_n_load_cb()

    def _mode_item(label, mode_val):
        def action(icon, item):
            _set_mode(mode_val)
        def is_checked(item):
            return _mode == mode_val
        return pystray.MenuItem(label, action, checked=is_checked, radio=True)

    def _provider_item(label, key):
        def action(icon, item):
            providers.set_provider(key)
        def is_checked(item):
            return providers.get_active_provider() == key
        return pystray.MenuItem(label, action, checked=is_checked, radio=True)

    improve_submenu = pystray.Menu(
        _mode_item("Grammar",       "improve:grammar"),
        _mode_item("Professional",  "improve:professional"),
        _mode_item("Concise",       "improve:concise"),
        _mode_item("Casual",        "improve:casual"),
        _mode_item("Caveman",       "improve:caveman"),
    )

    mode_submenu = pystray.Menu(
        _mode_item("Normal",    "normal"),
        _mode_item("Markdown",  "markdown"),
        pystray.MenuItem(
            "Improve",
            improve_submenu,
            checked=lambda item: _mode.startswith("improve:"),
        ),
    )

    provider_submenu = pystray.Menu(
        _provider_item("Azure OpenAI",   "azure"),
        _provider_item("OpenAI",         "openai"),
        _provider_item("Custom / Local", "custom"),
    )

    items = [
        pystray.MenuItem(
            "Lock n Load",
            _lock_n_load_click,
            checked=lambda item: _lock_n_load_active,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Mode", mode_submenu),
        pystray.MenuItem("Provider", provider_submenu),
        pystray.MenuItem(
            "Stealth mode",
            _toggle_private,
            checked=lambda item: _private,
        ),
        pystray.MenuItem(
            "Focus source window",
            _toggle_focus,
            checked=lambda _item: _restore_focus,
        ),
        pystray.Menu.SEPARATOR,
    ]
    if on_configure:
        items.append(pystray.MenuItem("Configure...", _configure))
    if on_reload_env:
        items.append(pystray.MenuItem("Reload config", _reload))
    items.append(pystray.MenuItem("Quit", _quit))

    menu = pystray.Menu(*items)
    _icon = pystray.Icon(
        "tonguepasta",
        _IDLE_IMG,
        _idle_title(),
        menu,
    )
    threading.Thread(target=_icon.run, daemon=True).start()
