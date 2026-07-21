"""
tonguepasta - hold Right Ctrl to record, release to transcribe and paste.
Shift + Right Ctrl = Lock n Load (toggle recording, saves audio file).
"""
import os
import subprocess
import sys
import threading
import wave

# Suppress console windows spawned by subprocesses
if sys.platform == "win32":
    _orig_popen = subprocess.Popen.__init__
    def _popen_no_window(self, *args, **kwargs):
        kwargs.setdefault("creationflags", 0)
        kwargs["creationflags"] |= subprocess.CREATE_NO_WINDOW
        _orig_popen(self, *args, **kwargs)
    subprocess.Popen.__init__ = _popen_no_window

from dotenv import load_dotenv
from pynput import keyboard

_base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
load_dotenv(os.path.join(_base, ".env"))

import ctypes
import numpy as np

import config_editor
import corrector
import improver
import output
import overlay
import providers
import stt
import tray
from audio import record_while_held
from formatter import format_markdown, is_markdown
from output import send_text
from stt import transcribe

output.set_log_path(os.path.join(_base, "tonguepasta.log"))

HOTKEY = keyboard.Key.ctrl_r
_SHIFT_KEYS = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}

_recording = False
_is_locked = False
_shift_held = False
_stop_event: threading.Event | None = None
_record_thread: threading.Thread | None = None
_listener: keyboard.Listener | None = None
_start_lock = threading.Lock()


def _log_write(msg: str):
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")
    with open(os.path.join(_base, "tonguepasta.log"), "a", encoding="utf-8") as f:
        f.write(f"{ts} {msg}\n")


def _save_audio_file(audio: np.ndarray, sample_rate: int = 16000) -> str:
    """Save audio to logs/mp3/ as WAV; try ffmpeg conversion to MP3."""
    import datetime
    logs_dir = os.path.join(_base, "logs", "mp3")
    os.makedirs(logs_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = os.path.join(logs_dir, f"{ts}.wav")

    pcm = (audio * 32767).astype(np.int16)
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    mp3_path = wav_path.replace(".wav", ".mp3")
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame",
             "-b:a", "32k", "-ac", "1", mp3_path],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0:
            os.unlink(wav_path)
            return mp3_path
    except Exception:
        pass

    return wav_path


def _start_recording(locked: bool = False):
    global _recording, _is_locked, _stop_event, _record_thread
    with _start_lock:
        if _recording:
            return
        _recording = True
    _is_locked = locked
    _stop_event = threading.Event()
    # Lock n Load: paste into whatever window is active at transcription time (not the original)
    target_hwnd = None if locked else (
        ctypes.windll.user32.GetForegroundWindow() if sys.platform == "win32" else None
    )

    private = tray.get_private()
    if not private:
        tray.set_recording(True, lock_mode=locked)
        if locked:
            overlay.show_locked()
        else:
            overlay.show()

    if locked:
        tray.set_lock_n_load_active(True)

    def run():
        try:
            _log_write("recording started" + (" [LOCK N LOAD]" if locked else ""))
            audio = record_while_held(_stop_event)
            tray.set_recording(False)
            if locked:
                tray.set_lock_n_load_active(False)
            _log_write(f"recording done, samples={audio.size}")
            if audio.size < 1600:
                overlay.hide()
                return

            # Save audio file for locked recordings
            if locked:
                if not private:
                    overlay.saving()
                duration_s = audio.size / 16000
                _log_write(f"saving audio ({duration_s:.0f}s)...")
                audio_path = _save_audio_file(audio)
                _log_write(f"saved: {audio_path}")

            _log_write("transcribing...")

            def _on_stt_status(status: str):
                if private:
                    return
                if status == "ampg":
                    overlay.amplifying()
                elif status == "trns":
                    overlay.transcribing()

            if not private:
                overlay.transcribing()
            text = transcribe(audio, on_status=_on_stt_status)
            _log_write(f"transcribe done: {repr(text[:60]) if text else 'empty'}")

            mode = tray.get_mode()
            improve_payload = improver.parse(text) if text else None
            if not improve_payload and text and mode.startswith("improve:"):
                instruction = mode.split(":", 1)[1]
                improve_payload = f"{instruction} {text}"

            if improve_payload:
                if not private:
                    overlay.trigger_detected("improve")
                    overlay.improving()
                _log_write(f"improving: {repr(improve_payload[:60])}")
                text = improver.improve(improve_payload)
                _log_write(f"improved: {repr(text[:60])}")
            else:
                if text:
                    try:
                        text = corrector.correct(text)
                        _log_write(f"corrected: {repr(text[:60])}")
                    except Exception as e:
                        _log_write(f"corrector error (using raw): {e}")
                force_markdown = mode == "markdown"
                if text and (force_markdown or is_markdown(text)):
                    if not private:
                        overlay.trigger_detected("markdown")
                        overlay.formatting()
                    _log_write("formatting markdown...")
                    text = format_markdown(text)
                    _log_write("format done")

            if text:
                text = text.replace("—", " - ").replace("–", " - ").replace("‑", "-")

            if not private:
                overlay.casting()
            _log_write("overlay: casting")

            if text:
                current_hwnd = ctypes.windll.user32.GetForegroundWindow() if sys.platform == "win32" else None
                return_hwnd = current_hwnd if not tray.get_restore_focus() else None
                send_text(text + " ", target_hwnd=target_hwnd, return_hwnd=return_hwnd)
            _log_write("send done")

            overlay.hide()

        except Exception as e:
            import traceback
            overlay.hide()
            overlay.error(f"{type(e).__name__}: {e}")
            if locked:
                tray.set_lock_n_load_active(False)
            with open(os.path.join(_base, "tonguepasta.log"), "a", encoding="utf-8") as f:
                f.write("EXCEPTION:\n")
                traceback.print_exc(file=f)

    _record_thread = threading.Thread(target=run, daemon=True)
    _record_thread.start()


def _stop_locked_recording():
    global _recording, _is_locked, _stop_event
    _recording = False
    _is_locked = False
    if _stop_event:
        _stop_event.set()


def on_lock_n_load_tray():
    if not _recording:
        _start_recording(locked=True)
    elif _is_locked:
        _stop_locked_recording()


def on_press(key):
    global _shift_held

    if key in _SHIFT_KEYS:
        _shift_held = True
        return

    if key == HOTKEY:
        if _shift_held:
            # Shift + RCtrl = Lock n Load toggle
            if not _recording:
                _start_recording(locked=True)
            elif _is_locked:
                _stop_locked_recording()
        else:
            # Normal hold-to-record
            if not _recording:
                _start_recording(locked=False)


def on_release(key):
    global _recording, _shift_held

    if key in _SHIFT_KEYS:
        _shift_held = False
        return

    # Only stop on key release for normal (non-locked) mode
    if key == HOTKEY and _recording and not _is_locked:
        _recording = False
        if _stop_event:
            _stop_event.set()


def reload_env():
    def _do_reload():
        _log_write("reload_env: reloading .env...")
        load_dotenv(os.path.join(_base, ".env"), override=True)
        providers.reset_clients()
        _log_write("reload_env: done")
    threading.Thread(target=_do_reload, daemon=True).start()


def main():
    global _listener

    def on_quit():
        if _listener:
            _listener.stop()

    env_path = os.path.join(_base, ".env")

    overlay.start()
    overlay.startup()
    tray.start(
        on_quit,
        on_reload_env=reload_env,
        on_lock_n_load=on_lock_n_load_tray,
        on_configure=lambda: config_editor.open_config(env_path, reload_env),
    )

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        _listener = listener
        listener.join()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log = os.path.join(_base, "tonguepasta.log")
        with open(log, "w") as f:
            traceback.print_exc(file=f)
        raise
