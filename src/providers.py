"""
Central provider factory for tonguepasta.

All AI clients (STT + chat) are built here. Other modules import from this
module instead of constructing their own clients.
"""
import os
import sys

import httpx
from dotenv import load_dotenv
from openai import AzureOpenAI, OpenAI

_base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))

_client = None

PROVIDER_INFO = {
    "azure": {
        "display": "Azure OpenAI",
        "base_url": None,
        "stt_default": "whisper",
        "chat_default": "gpt-4o-mini",
    },
    "openai": {
        "display": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "stt_default": "whisper-1",
        "chat_default": "gpt-4o-mini",
    },
    "custom": {
        "display": "Custom / Local",
        "base_url": None,
        "stt_default": None,
        "chat_default": None,
    },
}


def get_active_provider() -> str:
    return os.getenv("PROVIDER", "azure").lower()


def get_client():
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def _build_client():
    provider = get_active_provider()
    if provider == "azure":
        return AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_ENDPOINT", ""),
            api_version=os.getenv("AZURE_API_VERSION", "2025-01-01-preview"),
            http_client=httpx.Client(timeout=120.0),
        )
    info = PROVIDER_INFO.get(provider, PROVIDER_INFO["custom"])
    base_url = info["base_url"] or os.getenv("OPENAI_BASE_URL", "")
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=base_url,
        http_client=httpx.Client(timeout=120.0),
    )


def get_stt_model() -> str:
    override = os.getenv("STT_MODEL", "").strip()
    if override:
        return override
    provider = get_active_provider()
    if provider == "azure":
        return os.getenv("AZURE_DEPLOYMENT", PROVIDER_INFO["azure"]["stt_default"])
    return PROVIDER_INFO.get(provider, PROVIDER_INFO["custom"])["stt_default"] or ""


def get_chat_model() -> str:
    override = os.getenv("CHAT_MODEL", "").strip()
    if override:
        return override
    provider = get_active_provider()
    if provider == "azure":
        return os.getenv(
            "AZURE_CORRECT_DEPLOYMENT",
            os.getenv("AZURE_FORMAT_DEPLOYMENT", PROVIDER_INFO["azure"]["chat_default"]),
        )
    return PROVIDER_INFO.get(provider, PROVIDER_INFO["custom"])["chat_default"] or ""


def reset_clients():
    global _client
    _client = None


def set_provider(name: str):
    """Write PROVIDER=<name> to .env and reset cached client."""
    env_path = os.path.join(_base, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.readlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith("PROVIDER="):
                new_lines.append(f"PROVIDER={name}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.insert(0, f"PROVIDER={name}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    load_dotenv(env_path, override=True)
    reset_clients()
