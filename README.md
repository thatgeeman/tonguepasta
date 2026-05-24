# tonguepasta

Hold **Right Ctrl** to record your voice, release to transcribe and paste - works in any Windows application.

## Prerequisites

- Windows 10/11, macOS 12+, or Linux (X11)
- An API key for your chosen provider (OpenAI, Azure OpenAI, or a local model via Ollama/LM Studio)

### Platform notes

**macOS**
- Grant Accessibility permission after first launch: System Settings > Privacy & Security > Accessibility > tonguepasta
- Right Ctrl is the hotkey — if your keyboard lacks it, remap a key via Karabiner-Elements

**Linux (X11 only)**
- Wayland is not supported; run under X11 or XWayland (`DISPLAY=:0 ./tonguepasta`)
- Install system packages before running from source:
  ```
  sudo apt install libayatana-appindicator3-1 libportaudio2
  ```

## Setup

1. Place `tonguepasta.exe`, `.env`, and `vocabulary.txt` in the same folder.
2. Copy `.env.example` to `.env` and fill in your API key and provider.
3. Double-click `tonguepasta.exe` to run.

## Usage

The app runs silently in the system tray (no console window).

| Action | Result |
|--------|--------|
| Hold Right Ctrl + speak + release | Transcribed text is pasted at the cursor |
| Shift + Right Ctrl | Lock n Load - toggle recording on/off |

Right-click the tray icon to access settings and switch providers.

## Provider configuration

Edit `.env` and set `PROVIDER` to one of:

| Provider | `PROVIDER=` | Notes |
|----------|-------------|-------|
| OpenAI | `openai` | Needs `OPENAI_API_KEY` |
| Azure OpenAI | `azure` | Needs `AZURE_OPENAI_API_KEY` + `AZURE_ENDPOINT` |
| Local / Ollama | `custom` | Set `OPENAI_BASE_URL` and `OPENAI_API_KEY` |

You can also switch providers live from the tray icon without restarting.

## Improve mode

Prefix your speech with `improve <mode>` to rewrite the text instead of just transcribing it.

| What you say | What happens |
|---|---|
| `improve grammar <text>` | Fixes grammar only |
| `improve clarity <text>` | Improves clarity |
| `improve clarity avoid repetitions <text>` | Clarity with a style instruction |
| `improve tone make it professional <text>` | Adjusts tone |
| `improve caveman <text>` | Extreme compression - drops filler, cuts >=70% words |

## Auto-start on login (optional)

Copy `tonguepasta.exe`, `.env`, and `vocabulary.txt` to your Windows Startup folder:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

## Vocabulary

Edit `vocabulary.txt` (next to the exe) to add domain-specific terms. No restart needed - changes take effect on the next recording.

**Plain terms** - Whisper is biased toward these spellings:
```
Kubernetes
PyInstaller
```

**Mishearing aliases** - hard-substituted by the corrector:
```
CorrectWord = mishearing1, mishearing2
TensorFlow = tensor flow, tenser flow
```

Lines starting with `#` are comments.

## Configuration

All settings live in `.env`:

| Key | Description | Default |
|-----|-------------|---------|
| `PROVIDER` | Active provider: `azure`, `openai`, `custom` | `openai` |
| `OPENAI_API_KEY` | API key for OpenAI / custom providers | |
| `OPENAI_BASE_URL` | Base URL for custom/local providers | |
| `STT_MODEL` | Override STT model name | Provider default |
| `CHAT_MODEL` | Override chat model name | Provider default |
| `AZURE_OPENAI_API_KEY` | API key for Azure OpenAI | |
| `AZURE_ENDPOINT` | Azure OpenAI endpoint URL | |
| `AZURE_API_VERSION` | Azure API version | `2025-01-01-preview` |
| `AZURE_DEPLOYMENT` | Azure STT model name | `whisper` |
| `AZURE_CORRECT_DEPLOYMENT` | Azure chat model name | `gpt-4o-mini` |
| `AUDIO_SAMPLE_RATE` | Microphone sample rate (Hz) | `16000` |
| `AUDIO_SILENCE_THRESHOLD` | RMS threshold for silence detection | `0.01` |
| `AUDIO_SILENCE_DURATION` | Seconds of silence before auto-stop | `1.5` |

## Troubleshooting

**Nothing happens when I hold Right Ctrl**
- Check that `tonguepasta.exe` is running (system tray or Task Manager).
- Make sure a text field is focused when you release the key.

**Authentication error**
- Verify your API key in `.env` is correct and has not expired.
- Use "Reload .env" from the tray icon after updating the key.

**Microphone not detected**
- Check Windows microphone access: Settings > Privacy > Microphone.
