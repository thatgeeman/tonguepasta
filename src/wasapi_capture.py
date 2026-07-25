import sys

if sys.platform != "win32":
    raise ImportError("wasapi_capture is Windows-only")

import ctypes
import datetime
import os
import threading
import time
from ctypes import POINTER, c_void_p
from ctypes.wintypes import BOOL, DWORD, WORD

import comtypes
import numpy as np
from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

_base = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))


def _log(msg: str):
    try:
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")
        with open(os.path.join(_base, "tonguepasta.log"), "a", encoding="utf-8") as f:
            f.write(f"{ts} [wasapi] {msg}\n")
    except Exception:
        pass


# ---- constants ----

CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IMMDevice = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
IID_IAudioClient = GUID("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
IID_IAudioClient2 = GUID("{726778CD-F60A-4EDA-82DE-E47610CD78AA}")
IID_IAudioCaptureClient = GUID("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")

CLSCTX_ALL = 23

eCapture = 1
eConsole = 0

AUDCLNT_SHAREMODE_SHARED = 0
AudioCategory_Communications = 3

WAVE_FORMAT_PCM = 1
WAVE_FORMAT_IEEE_FLOAT = 3
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

AUDCLNT_BUFFERFLAGS_SILENT = 0x2

REFERENCE_TIME = ctypes.c_int64


# ---- structs ----

class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", WORD),
        ("nChannels", WORD),
        ("nSamplesPerSec", DWORD),
        ("nAvgBytesPerSec", DWORD),
        ("nBlockAlign", WORD),
        ("wBitsPerSample", WORD),
        ("cbSize", WORD),
    ]


class AudioClientProperties(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("bIsOffload", BOOL),
        ("eCategory", ctypes.c_int),
        ("Options", ctypes.c_uint32),
    ]


# ---- COM interfaces ----

class IAudioCaptureClient(IUnknown):
    _iid_ = IID_IAudioCaptureClient
    _methods_ = [
        COMMETHOD([], HRESULT, "GetBuffer",
            (['out'], POINTER(POINTER(ctypes.c_byte)), 'ppData'),
            (['out'], POINTER(ctypes.c_uint32), 'pNumFramesToRead'),
            (['out'], POINTER(DWORD), 'pdwFlags'),
            (['out'], POINTER(ctypes.c_uint64), 'pu64DevicePosition'),
            (['out'], POINTER(ctypes.c_uint64), 'pu64QPCPosition'),
        ),
        COMMETHOD([], HRESULT, "ReleaseBuffer",
            (['in'], ctypes.c_uint32, 'NumFramesRead'),
        ),
        COMMETHOD([], HRESULT, "GetNextPacketSize",
            (['out'], POINTER(ctypes.c_uint32), 'pNumFramesInNextPacket'),
        ),
    ]


class IAudioClient(IUnknown):
    _iid_ = IID_IAudioClient
    _methods_ = [
        COMMETHOD([], HRESULT, "Initialize",
            (['in'], ctypes.c_int, 'ShareMode'),
            (['in'], DWORD, 'StreamFlags'),
            (['in'], REFERENCE_TIME, 'hnsBufferDuration'),
            (['in'], REFERENCE_TIME, 'hnsPeriodicity'),
            (['in'], POINTER(WAVEFORMATEX), 'pFormat'),
            (['in'], c_void_p, 'AudioSessionGuid'),
        ),
        COMMETHOD([], HRESULT, "GetBufferSize",
            (['out'], POINTER(ctypes.c_uint32), 'pNumBufferFrames'),
        ),
        COMMETHOD([], HRESULT, "GetStreamLatency",
            (['out'], POINTER(REFERENCE_TIME), 'phnsLatency'),
        ),
        COMMETHOD([], HRESULT, "GetCurrentPadding",
            (['out'], POINTER(ctypes.c_uint32), 'pNumPaddingFrames'),
        ),
        COMMETHOD([], HRESULT, "IsFormatSupported",
            (['in'], ctypes.c_int, 'ShareMode'),
            (['in'], POINTER(WAVEFORMATEX), 'pFormat'),
            (['out'], POINTER(POINTER(WAVEFORMATEX)), 'ppClosestMatch'),
        ),
        COMMETHOD([], HRESULT, "GetMixFormat",
            (['out'], POINTER(POINTER(WAVEFORMATEX)), 'ppDeviceFormat'),
        ),
        COMMETHOD([], HRESULT, "GetDevicePeriod",
            (['out'], POINTER(REFERENCE_TIME), 'phnsDefaultDevicePeriod'),
            (['out'], POINTER(REFERENCE_TIME), 'phnsMinimumDevicePeriod'),
        ),
        COMMETHOD([], HRESULT, "Start"),
        COMMETHOD([], HRESULT, "Stop"),
        COMMETHOD([], HRESULT, "Reset"),
        COMMETHOD([], HRESULT, "SetEventHandle",
            (['in'], c_void_p, 'eventHandle'),
        ),
        COMMETHOD([], HRESULT, "GetService",
            (['in'], POINTER(GUID), 'riid'),
            (['out'], POINTER(POINTER(IAudioCaptureClient)), 'ppv'),
        ),
    ]


class IAudioClient2(IAudioClient):
    _iid_ = IID_IAudioClient2
    _methods_ = [
        COMMETHOD([], HRESULT, "IsOffloadCapable",
            (['in'], DWORD, 'Category'),
            (['out'], POINTER(BOOL), 'pbOffloadCapable'),
        ),
        COMMETHOD([], HRESULT, "SetClientProperties",
            (['in'], POINTER(AudioClientProperties), 'pProperties'),
        ),
        COMMETHOD([], HRESULT, "GetBufferSizeLimits",
            (['in'], POINTER(WAVEFORMATEX), 'pFormat'),
            (['in'], BOOL, 'bEventDriven'),
            (['out'], POINTER(REFERENCE_TIME), 'phnsMinBufferDuration'),
            (['out'], POINTER(REFERENCE_TIME), 'phnsMaxBufferDuration'),
        ),
    ]


class IMMDevice(IUnknown):
    _iid_ = IID_IMMDevice
    _methods_ = [
        COMMETHOD([], HRESULT, "Activate",
            (['in'], POINTER(GUID), 'iid'),
            (['in'], DWORD, 'dwClsCtx'),
            (['in'], c_void_p, 'pActivationParams'),
            (['out'], POINTER(POINTER(IAudioClient2)), 'ppInterface'),
        ),
        COMMETHOD([], HRESULT, "OpenPropertyStore",
            (['in'], DWORD, 'stgmAccess'),
            (['out'], POINTER(c_void_p), 'ppProperties'),
        ),
        COMMETHOD([], HRESULT, "GetId",
            (['out'], POINTER(ctypes.c_wchar_p), 'ppstrId'),
        ),
        COMMETHOD([], HRESULT, "GetState",
            (['out'], POINTER(DWORD), 'pdwState'),
        ),
    ]


class IMMDeviceEnumerator(IUnknown):
    _iid_ = IID_IMMDeviceEnumerator
    _methods_ = [
        COMMETHOD([], HRESULT, "EnumAudioEndpoints",
            (['in'], DWORD, 'dataFlow'),
            (['in'], DWORD, 'dwStateMask'),
            (['out'], POINTER(c_void_p), 'ppDevices'),
        ),
        COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
            (['in'], DWORD, 'dataFlow'),
            (['in'], DWORD, 'role'),
            (['out'], POINTER(POINTER(IMMDevice)), 'ppEndpoint'),
        ),
    ]


# ---- streaming resample + blockize (no extra deps) ----

class _Resampler:
    """Streaming linear-interpolation resampler; avoids clicks/discontinuities
    across packet boundaries by tracking a persistent fractional read position."""

    def __init__(self, native_rate: int, target_rate: int):
        self.ratio = native_rate / target_rate
        self._carry = np.zeros(0, dtype=np.float32)
        self._carry_base = 0.0
        self._next_out_pos = 0.0

    def push(self, mono: np.ndarray) -> np.ndarray:
        self._carry = np.concatenate([self._carry, mono])
        out = []
        while True:
            rel = self._next_out_pos - self._carry_base
            i0 = int(np.floor(rel))
            if i0 + 1 >= len(self._carry):
                break
            frac = rel - i0
            sample = self._carry[i0] * (1.0 - frac) + self._carry[i0 + 1] * frac
            out.append(sample)
            self._next_out_pos += self.ratio

        consumed = int(np.floor(self._next_out_pos - self._carry_base))
        if consumed > 0:
            drop = min(consumed, len(self._carry) - 1) if len(self._carry) > 0 else 0
            if drop > 0:
                self._carry = self._carry[drop:]
                self._carry_base += drop

        if out:
            return np.array(out, dtype=np.float32)
        return np.zeros(0, dtype=np.float32)


class _Blockizer:
    """Accumulates samples and yields fixed-size blocks, holding any remainder."""

    def __init__(self, blocksize: int):
        self.blocksize = blocksize
        self._leftover = np.zeros(0, dtype=np.float32)

    def push(self, samples: np.ndarray):
        buf = np.concatenate([self._leftover, samples])
        n_full = len(buf) // self.blocksize
        blocks = [buf[i * self.blocksize:(i + 1) * self.blocksize] for i in range(n_full)]
        self._leftover = buf[n_full * self.blocksize:]
        return blocks


# ---- public capture stream ----

def _capture_device_id(device) -> str:
    device_id = device.GetId()
    try:
        if isinstance(device_id, str):
            return device_id
        if hasattr(device_id, "value"):
            return str(device_id.value)
        return ctypes.wstring_at(device_id)
    finally:
        if device_id and not isinstance(device_id, str):
            try:
                ctypes.windll.ole32.CoTaskMemFree(device_id)
            except Exception:
                pass


def get_default_capture_signature() -> tuple[str, str] | None:
    """Return a stable signature for the current default Windows input device."""
    try:
        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    except Exception:
        pass

    try:
        enumerator = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator, clsctx=CLSCTX_ALL,
        )
        device = enumerator.GetDefaultAudioEndpoint(eCapture, eConsole)
        return ("wasapi", _capture_device_id(device))
    except Exception as e:
        _log(f"default capture signature failed: {e}")
        return None
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass


class WasapiCaptureStream:
    """Duck-typed against the sounddevice.InputStream surface audio.py uses:
    .start(), .active, .close()."""

    def __init__(self, callback, samplerate: int, blocksize: int):
        self._callback = callback
        self._samplerate = samplerate
        self._blocksize = blocksize
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._init_error = None
        self._active = False
        self._thread = None
        self.device_signature: tuple[str, str] | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=5.0)
        if self._init_error is not None:
            raise self._init_error
        if not self._active:
            raise RuntimeError("wasapi capture failed to start (timeout)")

    @property
    def active(self) -> bool:
        return self._active

    def close(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self):
        try:
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        except Exception:
            pass

        client2 = None
        capture_client = None
        try:
            enumerator = comtypes.CoCreateInstance(
                CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator, clsctx=CLSCTX_ALL,
            )
            device = enumerator.GetDefaultAudioEndpoint(eCapture, eConsole)
            self.device_signature = ("wasapi", _capture_device_id(device))
            client2 = device.Activate(IID_IAudioClient2, CLSCTX_ALL, None)

            # NOTE: previously tagged eCategory=AudioCategory_Communications here to test
            # a mic-throttle-bypass hypothesis. That tag makes Windows route this app to
            # the "default communications device" role instead of the regular default
            # device, which can silently point capture at unrelated hardware (e.g. a
            # headset) when the two roles differ. Left untagged until the throttle
            # hypothesis is confirmed some other way.

            fmt_ptr = client2.GetMixFormat()
            fmt = fmt_ptr.contents
            native_rate = fmt.nSamplesPerSec
            channels = fmt.nChannels
            bits = fmt.wBitsPerSample
            tag = fmt.wFormatTag
            block_align = fmt.nBlockAlign

            is_float = bits == 32 and tag in (WAVE_FORMAT_IEEE_FLOAT, WAVE_FORMAT_EXTENSIBLE)
            is_pcm16 = bits == 16 and tag == WAVE_FORMAT_PCM
            if not (is_float or is_pcm16):
                ctypes.windll.ole32.CoTaskMemFree(fmt_ptr)
                raise RuntimeError(f"unsupported mix format tag={tag} bits={bits}")

            client2.Initialize(AUDCLNT_SHAREMODE_SHARED, 0, 10_000_000, 0, fmt_ptr, None)
            ctypes.windll.ole32.CoTaskMemFree(fmt_ptr)

            capture_client = client2.GetService(IID_IAudioCaptureClient)
            client2.Start()

            _log(
                "capture started (default console device, "
                f"rate={native_rate}->{self._samplerate}, ch={channels}->1)"
            )

            self._active = True
            self._ready_event.set()

            resampler = _Resampler(native_rate, self._samplerate)
            blockizer = _Blockizer(self._blocksize)

            while not self._stop_event.is_set():
                n = capture_client.GetNextPacketSize()
                if n == 0:
                    time.sleep(0.01)
                    continue

                data_ptr, num_frames, flags, _dev_pos, _qpc_pos = capture_client.GetBuffer()
                if num_frames > 0:
                    if (flags & AUDCLNT_BUFFERFLAGS_SILENT) or not data_ptr:
                        mono = np.zeros(num_frames, dtype=np.float32)
                    else:
                        raw = ctypes.string_at(data_ptr, num_frames * block_align)
                        if is_float:
                            samples = np.frombuffer(raw, dtype=np.float32)
                        else:
                            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                        mono = samples.reshape(-1, channels).mean(axis=1) if channels > 1 else samples
                    capture_client.ReleaseBuffer(num_frames)

                    resampled = resampler.push(mono)
                    if resampled.size:
                        for block in blockizer.push(resampled):
                            chunk = block.reshape(-1, 1).astype(np.float32, copy=False)
                            self._callback(chunk, len(block), None, None)
                else:
                    capture_client.ReleaseBuffer(0)

            client2.Stop()
        except Exception as e:
            self._init_error = e
            _log(f"capture thread error: {e}")
        finally:
            self._active = False
            self._ready_event.set()
            capture_client = None
            client2 = None
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass
