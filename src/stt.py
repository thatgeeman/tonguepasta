import io
import math
import os
import sys
import wave

import numpy as np
from dotenv import load_dotenv
from openai import AuthenticationError
import corrector
import providers

_base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))

# 10-min chunks keep WAV under ~20MB (well within the 25MB Whisper limit)
_MAX_CHUNK_SAMPLES = 10 * 60 * 16000
_PEAK_LIMIT = 0.98


def _log(msg: str):
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")
    with open(os.path.join(_base, "tonguepasta.log"), "a", encoding="utf-8") as f:
        f.write(f"{ts} [stt] {msg}\n")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        _log(f"invalid {name}={raw!r}, using {default}")
        return default


# Common Whisper hallucinations on quiet/ambiguous audio (an artifact of its
# YouTube-caption training data). Only checked when we amplified the audio
# ourselves, since that's when noise gets loud enough to trigger them.
_KNOWN_HALLUCINATIONS = {
    "thank you for watching",
    "thank you for watching this video",
    "thanks for watching",
    "thanks for watching this video",
    "please subscribe",
    "don't forget to subscribe",
    "like and subscribe",
    "subscribe to my channel",
    "see you in the next video",
    "see you next time",
    "thanks for listening",
    "bye bye",
}


def _filter_hallucination(result: str, vocab_prompt: str, amplified: bool = False) -> str:
    if not result:
        return result
    if vocab_prompt and (vocab_prompt.startswith(result) or result.startswith(vocab_prompt[:40])):
        _log("hallucination detected (vocab prompt echo) - discarding result")
        return ""
    if amplified and result.strip().strip(".!?,;:").lower() in _KNOWN_HALLUCINATIONS:
        _log(f"hallucination detected (known phrase on amplified audio) - discarding {result!r}")
        return ""
    return result


def _normalize_audio(audio: np.ndarray, rms: float, on_status=None) -> tuple[np.ndarray, bool]:
    target_rms = _env_float("STT_NORMALIZE_TARGET_RMS", 0.1)
    max_gain = _env_float("STT_MAX_GAIN", 8.0)
    peak = float(np.max(np.abs(audio))) if audio.size > 0 else 0.0

    if (
        rms <= 0.0
        or peak <= 0.0
        or target_rms <= 0.0
        or max_gain <= 1.0
        or rms >= target_rms
    ):
        _log(f"normalization skipped: peak={peak:.5f}, target_rms={target_rms:.5f}")
        return audio, False

    rms_gain = target_rms / rms
    peak_gain = _PEAK_LIMIT / peak
    gain = min(rms_gain, peak_gain, max_gain)

    if gain <= 1.0:
        _log(
            "normalization skipped: "
            f"peak={peak:.5f}, rms_gain={rms_gain:.2f}, peak_gain={peak_gain:.2f}, max_gain={max_gain:.2f}"
        )
        return audio, False

    if on_status:
        on_status("ampg")

    normalized = np.clip(audio * gain, -1.0, 1.0).astype(np.float32, copy=False)
    final_rms = float(np.sqrt(np.mean(normalized ** 2))) if normalized.size > 0 else 0.0
    final_peak = float(np.max(np.abs(normalized))) if normalized.size > 0 else 0.0
    _log(
        "amplified audio: "
        f"gain={gain:.2f}, rms={rms:.5f}->{final_rms:.5f}, "
        f"peak={peak:.5f}->{final_peak:.5f}, target_rms={target_rms:.5f}, "
        f"max_gain={max_gain:.2f}"
    )
    return normalized, True


def _audio_to_wav_buf(audio: np.ndarray, sample_rate: int) -> io.BytesIO:
    pcm = (audio * 32767).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    buf.seek(0)
    buf.name = "audio.wav"
    return buf


def _transcribe_buf(buf: io.BytesIO, deployment: str, vocab_prompt: str, amplified: bool = False) -> str:
    result = providers.get_client().audio.transcriptions.create(
        model=deployment, file=buf, prompt=vocab_prompt
    ).text.strip()
    return _filter_hallucination(result, vocab_prompt, amplified=amplified)


def transcribe(audio: np.ndarray, sample_rate: int = 16000, on_status=None) -> str:
    _log("getting client...")
    providers.get_client()
    _log("got client, calling whisper...")
    deployment = providers.get_stt_model()
    vocab_prompt = corrector.get_whisper_prompt()
    _log(f"vocab prompt: {repr(vocab_prompt[:80]) if vocab_prompt else 'EMPTY'}")

    duration_s = audio.size / sample_rate
    rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size > 0 else 0.0
    _log(f"audio: {duration_s:.2f}s, rms={rms:.5f}, samples={audio.size}")

    # USB headset microphones commonly produce speech around 0.004-0.008 RMS.
    # Keep rejecting near-silence while allowing normalization to handle low gain.
    rms_threshold = _env_float("STT_RMS_THRESHOLD", 0.003)
    if rms < rms_threshold:
        _log(f"audio too quiet (rms={rms:.5f} < {rms_threshold}), skipping")
        return ""

    audio, amplified = _normalize_audio(audio, rms, on_status=on_status)

    if on_status:
        on_status("trns")

    if audio.size <= _MAX_CHUNK_SAMPLES:
        buf = _audio_to_wav_buf(audio, sample_rate)
        try:
            result = _transcribe_buf(buf, deployment, vocab_prompt, amplified=amplified)
            _log(f"whisper done: {repr(result[:60])}")
            return result
        except AuthenticationError:
            _log("auth error, reloading .env and retrying...")
            load_dotenv(os.path.join(_base, ".env"), override=True)
            providers.reset_clients()
            buf.seek(0)
            result = _transcribe_buf(buf, providers.get_stt_model(), vocab_prompt, amplified=amplified)
            _log(f"whisper retry done: {repr(result[:60])}")
            return result

    # Long recording: chunk into 10-min segments
    total_mins = audio.size / sample_rate / 60
    n_chunks = math.ceil(len(audio) / _MAX_CHUNK_SAMPLES)
    _log(f"long audio: {total_mins:.1f} min - splitting into {n_chunks} chunks")
    parts = []
    for i in range(n_chunks):
        start = i * _MAX_CHUNK_SAMPLES
        chunk = audio[start:start + _MAX_CHUNK_SAMPLES]
        _log(f"transcribing chunk {i + 1}/{n_chunks} ({len(chunk) / sample_rate / 60:.1f} min)")
        try:
            buf = _audio_to_wav_buf(chunk, sample_rate)
            text = _transcribe_buf(buf, deployment, vocab_prompt, amplified=amplified)
            if text:
                parts.append(text)
            _log(f"chunk {i + 1} done: {repr(text[:60]) if text else 'empty'}")
        except Exception as e:
            _log(f"chunk {i + 1} failed: {e}")
    result = "\n\n".join(parts)
    _log(f"chunked transcription done: {n_chunks} chunks, {len(result)} chars")
    return result
