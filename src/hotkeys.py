"""Serialize pynput key objects to/from the string stored in HOTKEY= in .env."""
from pynput import keyboard


def key_to_str(key) -> str:
    if isinstance(key, keyboard.KeyCode):
        if key.char is not None:
            return f"char:{key.char}"
        return f"vk:{key.vk}"
    return key.name


def str_to_key(spec: str):
    spec = spec.strip()
    if spec.startswith("char:"):
        return keyboard.KeyCode.from_char(spec[len("char:"):])
    if spec.startswith("vk:"):
        return keyboard.KeyCode.from_vk(int(spec[len("vk:"):]))
    try:
        return keyboard.Key[spec]
    except KeyError:
        raise ValueError(f"unknown hotkey spec: {spec!r}")


def display_name(key) -> str:
    if isinstance(key, keyboard.KeyCode):
        if key.char is not None:
            return key.char.upper()
        return f"VK{key.vk}"
    return key.name.replace("_", " ").title()
