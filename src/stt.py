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


def _log(msg: str):
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")
    with open(os.path.join(_base, "tonguepasta.log"), "a", encoding="utf-8") as f:
        f.write(f"{ts} [stt] {msg}\n")


def _filter_hallucination(result: str, vocab_prompt: str) -> str:
    if not result or not vocab_prompt:
        return result
    if vocab_prompt.startswith(result) or result.startswith(vocab_prompt[:40]):
        _log("hallucination detected - discarding result")
        return ""
    return result


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


def _transcribe_buf(buf: io.BytesIO, deployment: str, vocab_prompt: str) -> str:
    result = providers.get_client().audio.transcriptions.create(
        model=deployment, file=buf, prompt=vocab_prompt
    ).text.strip()
    return _filter_hallucination(result, vocab_prompt)


def transcribe(audio: np.ndarray, sample_rate: int = 16000) -> str:
    _log("getting client...")
    providers.get_client()
    _log("got client, calling whisper...")
    deployment = providers.get_stt_model()
    vocab_prompt = corrector.get_whisper_prompt()
    _log(f"vocab prompt: {repr(vocab_prompt[:80]) if vocab_prompt else 'EMPTY'}")

    duration_s = audio.size / sample_rate
    rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size > 0 else 0.0
    _log(f"audio: {duration_s:.2f}s, rms={rms:.5f}, samples={audio.size}")

    if audio.size <= _MAX_CHUNK_SAMPLES:
        buf = _audio_to_wav_buf(audio, sample_rate)
        try:
            result = _transcribe_buf(buf, deployment, vocab_prompt)
            _log(f"whisper done: {repr(result[:60])}")
            return result
        except AuthenticationError:
            _log("auth error, reloading .env and retrying...")
            load_dotenv(os.path.join(_base, ".env"), override=True)
            providers.reset_clients()
            buf.seek(0)
            result = _transcribe_buf(buf, providers.get_stt_model(), vocab_prompt)
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
            text = _transcribe_buf(buf, deployment, vocab_prompt)
            if text:
                parts.append(text)
            _log(f"chunk {i + 1} done: {repr(text[:60]) if text else 'empty'}")
        except Exception as e:
            _log(f"chunk {i + 1} failed: {e}")
    result = "\n\n".join(parts)
    _log(f"chunked transcription done: {n_chunks} chunks, {len(result)} chars")
    return result
