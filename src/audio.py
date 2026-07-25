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
STALE_STREAM_SECONDS = 8.0
DEFAULT_INPUT_DEVICE_ID = "default"

_pre_roll: deque = deque(maxlen=PRE_ROLL_BLOCKS)
_record_queue: queue.Queue | None = None
_record_lock = threading.Lock()
_stream: sd.InputStream | None = None
_stream_lock = threading.Lock()
_last_chunk_at = 0.0

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
    global _last_chunk_at
    _last_chunk_at = time.monotonic()
    chunk = indata.copy()
    _pre_roll.append(chunk)
    with _record_lock:
        q = _record_queue
    if q is not None:
        try:
            q.put_nowait(chunk)
        except queue.Full:
            pass


def _selected_input_device_id() -> str:
    device_id = os.getenv("AUDIO_INPUT_DEVICE", DEFAULT_INPUT_DEVICE_ID).strip()
    return device_id or DEFAULT_INPUT_DEVICE_ID


def get_input_device_id() -> str:
    return _selected_input_device_id()


def _sounddevice_default_input_index():
    try:
        device_index = sd.default.device[0]
        if device_index is None or device_index < 0:
            for hostapi in sd.query_hostapis():
                device_index = hostapi.get("default_input_device", -1)
                if device_index is not None and device_index >= 0:
                    break
        if device_index is None or device_index < 0:
            return None
        return int(device_index)
    except Exception as e:
        _log(f"sounddevice default input lookup failed: {e}")
        return None


def _sounddevice_signature(device_index=None):
    try:
        if device_index is None:
            device_index = _sounddevice_default_input_index()
        if device_index is None:
            return None
        device = sd.query_devices(device_index, "input")
        return (
            "sounddevice",
            int(device_index),
            str(device.get("name", "")),
            int(device.get("hostapi", -1)),
            int(device.get("max_input_channels", 0)),
        )
    except Exception as e:
        _log(f"sounddevice signature failed: {e}")
        return None


def _selected_sounddevice_index():
    device_id = _selected_input_device_id()
    if device_id == DEFAULT_INPUT_DEVICE_ID:
        return None
    try:
        device_index = int(device_id)
        device = sd.query_devices(device_index, "input")
        if int(device.get("max_input_channels", 0)) <= 0:
            raise ValueError("device has no input channels")
        return device_index
    except Exception as e:
        _log(f"selected input device {device_id!r} is unavailable: {e}")
        return None


def _default_capture_signature():
    selected_index = _selected_sounddevice_index()
    if selected_index is not None:
        return _sounddevice_signature(selected_index)
    if _selected_input_device_id() != DEFAULT_INPUT_DEVICE_ID:
        return _sounddevice_signature()

    if _wasapi_available:
        try:
            import wasapi_capture
            signature = wasapi_capture.get_default_capture_signature()
            if signature is not None:
                return signature
        except Exception as e:
            _log(f"wasapi default signature failed: {e}")
    return _sounddevice_signature()


def _stream_signature(stream):
    return getattr(stream, "device_signature", getattr(stream, "_tonguepasta_device_signature", None))


def _close_stream(stream):
    if stream is None:
        return
    try:
        stream.close()
    except Exception:
        pass


def _open_stream(expected_signature=None):
    global _wasapi_available, _wasapi_fail_count
    selected_index = _selected_sounddevice_index()
    if selected_index is None and _selected_input_device_id() != DEFAULT_INPUT_DEVICE_ID:
        _log("selected input unavailable, falling back to default input")

    if selected_index is None and _selected_input_device_id() == DEFAULT_INPUT_DEVICE_ID and _wasapi_available:
        try:
            import wasapi_capture
            stream = wasapi_capture.WasapiCaptureStream(
                callback=_callback, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
            )
            stream.start()
            _wasapi_fail_count = 0
            _log(f"stream opened via wasapi, device={_stream_signature(stream)}")
            return stream
        except Exception as e:
            _log(f"wasapi capture failed, falling back to sounddevice: {e}")
            _wasapi_fail_count += 1
            if _wasapi_fail_count >= 3:
                _wasapi_available = False

    signature = expected_signature or _sounddevice_signature(selected_index)
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32",
        blocksize=BLOCK_SIZE, callback=_callback, device=selected_index,
    )
    stream.start()
    stream._tonguepasta_device_signature = signature
    _log(f"stream opened via sounddevice, device={signature}")
    return stream


def _refresh_stream(reason: str):
    global _stream, _last_chunk_at
    old_stream = _stream
    if old_stream is not None:
        _log(f"refreshing capture stream: {reason}")
    signature = _default_capture_signature()
    # Open the replacement first. Some drivers reject an input stream at the
    # requested format, and a bad tray-menu choice must not silence capture.
    replacement_stream = _open_stream(expected_signature=signature)
    _stream = replacement_stream
    _close_stream(old_stream)
    _pre_roll.clear()
    _last_chunk_at = time.monotonic()


def refresh_stream(reason: str = "input device changed"):
    with _stream_lock:
        _refresh_stream(reason)


def _hostapi_priority(hostapi_name: str) -> int:
    """Prefer one stable backend when an input is exposed more than once."""
    preferences = {
        "win32": ["MME", "Windows WASAPI", "Windows DirectSound", "Windows WDM-KS"],
        "darwin": ["Core Audio"],
        "linux": ["PipeWire", "PulseAudio", "ALSA", "JACK"],
    }
    try:
        return preferences.get(sys.platform, []).index(hostapi_name)
    except ValueError:
        return len(preferences.get(sys.platform, []))


def list_input_devices() -> list[dict[str, object]]:
    selected_id = _selected_input_device_id()
    devices: list[dict[str, object]] = [
        {
            "id": DEFAULT_INPUT_DEVICE_ID,
            "label": "Default input",
            "selected": selected_id == DEFAULT_INPUT_DEVICE_ID,
        }
    ]
    try:
        hostapis = sd.query_hostapis()
        default_index = _sounddevice_default_input_index()
        candidates: dict[str, tuple[int, int, str, str, bool]] = {}
        for index, device in enumerate(sd.query_devices()):
            if int(device.get("max_input_channels", 0)) <= 0:
                continue
            try:
                sd.check_input_settings(
                    device=index, channels=1, samplerate=SAMPLE_RATE,
                )
            except Exception as e:
                _log(f"skipping unsupported input device {index}: {e}")
                continue
            hostapi_index = int(device.get("hostapi", -1))
            hostapi_name = (
                hostapis[hostapi_index].get("name", "Unknown")
                if 0 <= hostapi_index < len(hostapis)
                else "Unknown"
            )
            name = str(device.get("name", f"Input {index}"))
            # Windows' Sound Mapper is only an alias for the Default input item.
            if sys.platform == "win32" and name.casefold().startswith("microsoft sound mapper"):
                continue
            key = name.casefold()
            candidate = (
                _hostapi_priority(hostapi_name), index, name, hostapi_name,
                index == default_index,
            )
            existing = candidates.get(key)
            if existing is None or candidate[0] < existing[0]:
                candidates[key] = candidate

        for _priority, index, name, hostapi_name, is_default in sorted(
            candidates.values(), key=lambda candidate: (not candidate[4], candidate[2].casefold()),
        ):
            suffix = " (default)" if is_default else ""
            device_id = str(index)
            devices.append({
                "id": device_id,
                "label": f"{name} [{hostapi_name}]{suffix}",
                "selected": selected_id == device_id,
            })
    except Exception as e:
        _log(f"input device list failed: {e}")
    return devices


def _watchdog():
    global _stream
    while True:
        time.sleep(3)
        with _stream_lock:
            stream = _stream
            alive = stream is not None and stream.active
            opened_signature = _stream_signature(stream) if stream is not None else None
            current_signature = _default_capture_signature() if alive else None
            stale = (
                alive
                and _last_chunk_at > 0
                and time.monotonic() - _last_chunk_at > STALE_STREAM_SECONDS
            )
            device_changed = (
                alive
                and opened_signature is not None
                and current_signature is not None
                and opened_signature != current_signature
            )
        if not alive or stale or device_changed:
            try:
                with _stream_lock:
                    if _stream is not stream and stream is not None:
                        continue
                    if not alive:
                        reason = "stream inactive"
                    elif device_changed:
                        reason = f"default input changed {opened_signature!r} -> {current_signature!r}"
                    else:
                        reason = f"no audio callbacks for {STALE_STREAM_SECONDS:.0f}s"
                    _refresh_stream(reason)
            except Exception as e:
                _log(f"stream refresh failed: {e}")


def _init():
    global _stream
    try:
        with _stream_lock:
            _refresh_stream("startup")
    except Exception as e:
        _log(f"initial stream open failed: {e}")
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
