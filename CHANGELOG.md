# Changelog

## Unreleased

### Fixed
- **Overlay no longer steals keyboard focus** (`overlay.py`): Added `WS_EX_NOACTIVATE` extended
  window style to the tkinter root on Windows. Previously, each `deiconify()` call during the
  pipeline (REC, TRNS, CAST states) would activate the overlay and pull keyboard focus away from
  the source window, causing "Focus source window" paste to fail silently.
- **Audio too quiet threshold configurable** (`stt.py`): `_RMS_THRESHOLD` now reads from the
  `STT_RMS_THRESHOLD` env var (default `0.01`, down from hardcoded `0.02`). Recordings with
  low-gain microphones (RMS 0.015-0.017) were silently skipped. Document the knob in
  `.env.example`.
