import os
import queue
import sys
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd

SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
BLOCK_SIZE = 1024
PRE_ROLL_BLOCKS = 8  # ~500ms pre-roll to avoid missing opening words

_pre_roll: deque = deque(maxlen=PRE_ROLL_BLOCKS)
_record_queue: queue.Queue | None = None
_record_lock = threading.Lock()
_stream: sd.InputStream | None = None
_stream_lock = threading.Lock()

_wasapi_available = sys.platform == "win32"
_wasapi_fail_count = 0


def _log(msg: str):
    try:
        import datetime
        base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")
        with open(os.path.join(base, "tonguepasta.log"), "a", encoding="utf-8") as f:
            f.write(f"{ts} [audio] {msg}\n")
    except Exception:
        pass


def _callback(indata, frames, _time, status):
    chunk = indata.copy()
    _pre_roll.append(chunk)
    with _record_lock:
        q = _record_queue
    if q is not None:
        try:
            q.put_nowait(chunk)
        except queue.Full:
            pass


def _open_stream():
    global _wasapi_available, _wasapi_fail_count
    if _wasapi_available:
        try:
            import wasapi_capture
            stream = wasapi_capture.WasapiCaptureStream(
                callback=_callback, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
            )
            stream.start()
            _wasapi_fail_count = 0
            return stream
        except Exception as e:
            _log(f"wasapi capture failed, falling back to sounddevice: {e}")
            _wasapi_fail_count += 1
            if _wasapi_fail_count >= 3:
                _wasapi_available = False

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32",
        blocksize=BLOCK_SIZE, callback=_callback,
    )
    stream.start()
    return stream


def _watchdog():
    global _stream
    while True:
        time.sleep(3)
        with _stream_lock:
            alive = _stream is not None and _stream.active
        if not alive:
            try:
                with _stream_lock:
                    if _stream is not None:
                        try:
                            _stream.close()
                        except Exception:
                            pass
                    _stream = _open_stream()
            except Exception:
                pass


def _init():
    global _stream
    try:
        with _stream_lock:
            _stream = _open_stream()
    except Exception:
        pass
    threading.Thread(target=_watchdog, daemon=True).start()


threading.Thread(target=_init, daemon=True).start()


def record_while_held(stop_event: threading.Event) -> np.ndarray:
    global _record_queue
    import overlay

    chunks = list(_pre_roll)

    q: queue.Queue = queue.Queue()
    with _record_lock:
        _record_queue = q

    try:
        while not stop_event.is_set():
            try:
                chunk = q.get(timeout=0.05)
                chunks.append(chunk)
                overlay.push_audio(chunk.flatten())
            except queue.Empty:
                continue
        while True:
            try:
                chunks.append(q.get_nowait())
            except queue.Empty:
                break
    finally:
        with _record_lock:
            _record_queue = None

    if not chunks:
        return np.array([], dtype=np.float32)
    return np.concatenate(chunks, axis=0).flatten()
