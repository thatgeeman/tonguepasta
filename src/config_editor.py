"""
Open the .env config file in the system text editor and auto-reload when saved.
"""
import os
import subprocess
import sys
import threading
import time

_WATCH_INTERVAL = 2      # seconds between mtime polls
_WATCH_TIMEOUT  = 600    # stop watching after 10 min of no changes

_ENV_TEMPLATE = """\
# tonguepasta configuration
# Edit this file, save it, and the app will reload automatically.

# ── Provider ────────────────────────────────────────────────────────────────
# Which AI backend to use: azure | openai | custom
PROVIDER=openai

# ── OpenAI ──────────────────────────────────────────────────────────────────
# PROVIDER=openai
OPENAI_API_KEY=sk-...

# ── Custom / Local (Ollama, LM Studio, etc.) ────────────────────────────────
# PROVIDER=custom
# OPENAI_API_KEY=ollama
# OPENAI_BASE_URL=http://localhost:11434/v1
# STT_MODEL=whisper        # model name for transcription
# CHAT_MODEL=llama3.2      # model name for correction / improve / format

# ── Azure OpenAI ────────────────────────────────────────────────────────────
# PROVIDER=azure
# AZURE_OPENAI_API_KEY=
# AZURE_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_API_VERSION=2025-01-01-preview
# AZURE_DEPLOYMENT=whisper              # STT model deployment name
# AZURE_CORRECT_DEPLOYMENT=gpt-4o-mini  # chat model deployment name

# ── Model overrides (leave blank to use provider defaults) ──────────────────
# STT_MODEL=
# CHAT_MODEL=

# ── Audio ────────────────────────────────────────────────────────────────────
AUDIO_SAMPLE_RATE=16000
AUDIO_SILENCE_THRESHOLD=0.01
AUDIO_SILENCE_DURATION=1.5
# Minimum RMS level to attempt transcription.
# STT_RMS_THRESHOLD=0.01
# Quiet recordings above STT_RMS_THRESHOLD are amplified toward this RMS before STT.
STT_NORMALIZE_TARGET_RMS=0.1
# Maximum amplification multiplier. Peak headroom may reduce this further.
STT_MAX_GAIN=8.0
"""


def _ensure_env(env_path: str):
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(_ENV_TEMPLATE)


def _open_editor(path: str):
    if sys.platform == "win32":
        subprocess.Popen(["notepad.exe", path])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-t", path])
    else:
        for editor in ("gedit", "mousepad", "kate", "xed", "pluma", "xdg-open"):
            try:
                subprocess.Popen([editor, path])
                return
            except FileNotFoundError:
                continue


def _watch(env_path: str, on_change):
    try:
        last_mtime = os.path.getmtime(env_path)
    except OSError:
        return

    deadline = time.monotonic() + _WATCH_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(_WATCH_INTERVAL)
        try:
            mtime = os.path.getmtime(env_path)
        except OSError:
            continue
        if mtime != last_mtime:
            last_mtime = mtime
            deadline = time.monotonic() + _WATCH_TIMEOUT
            on_change()


def open_config(env_path: str, on_reload):
    _ensure_env(env_path)
    _open_editor(env_path)
    threading.Thread(target=_watch, args=(env_path, on_reload), daemon=True).start()
