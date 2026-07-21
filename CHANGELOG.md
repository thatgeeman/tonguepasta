# Changelog

## Unreleased

### Added
- **Rebindable record hotkey** (`hotkeys.py`, `main.py`, `tray.py`, `overlay.py`, `config_editor.py`):
  Right-click the tray icon → "Set Hotkey..." to rebind the hold-to-record key on all platforms.
  The new binding persists to `.env` (`HOTKEY=`) and is picked up automatically on the next launch.
  Lock n Load stays `Shift + <hotkey>`, following the new binding. Press `Esc` or wait 10s to
  cancel a capture without changing anything.

### Fixed
- **Tray icon clicks (including menu open) could silently fail, most consistently on Linux**
  (`tray.py`, `main.py`): pystray's `Icon.run()` was started on a background thread while the
  main thread ran the keyboard listener. pystray requires `run()` on the main thread — its GTK
  backend depends on the main-thread GLib loop to dispatch clicks. Restructured so `tray.start()`
  blocks the main thread and the keyboard listener now runs inside pystray's `setup` callback
  instead.
- **Quiet recordings are amplified before transcription** (`stt.py`, `overlay.py`): Audio above
  the silence threshold but below the target RMS is now boosted with clipping protection before
  STT, and the overlay briefly shows `AMPG` when this happens.
- **Overlay no longer steals keyboard focus** (`overlay.py`): Added `WS_EX_NOACTIVATE` extended
  window style to the tkinter root on Windows. Previously, each `deiconify()` call during the
  pipeline (REC, TRNS, CAST states) would activate the overlay and pull keyboard focus away from
  the source window, causing "Focus source window" paste to fail silently.
- **Audio too quiet threshold configurable** (`stt.py`): `_RMS_THRESHOLD` now reads from the
  `STT_RMS_THRESHOLD` env var (default `0.01`, down from hardcoded `0.02`). Recordings with
  low-gain microphones (RMS 0.015-0.017) were silently skipped. Document the knob in
  `.env.example`.
