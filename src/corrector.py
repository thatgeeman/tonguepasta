import os
import sys

from dotenv import load_dotenv
from openai import AuthenticationError
import providers

_base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))

_SYSTEM = """\
You are a transcription corrector for a voice-to-text tool.

You receive a raw Whisper transcription. Whisper may have misheard domain-specific terms.
Below is a vocabulary of correct spellings the speaker commonly uses.

Fix any word or phrase in the transcription that is clearly a Whisper mishearing of a vocabulary term.
Use context to decide - only substitute when you are confident.
Do NOT rephrase, restructure, or modify anything else.
Return ONLY the corrected transcription text, with no commentary.

Vocabulary:
{vocab}

{aliases_section}"""

_ALIASES_HEADER = """\
The following are known mishearings - always substitute these regardless of context:
{rules}"""


def _parse_vocab() -> tuple[list[str], dict[str, list[str]]]:
    path = os.path.join(_base, "vocabulary.txt")
    terms: list[str] = []
    aliases: dict[str, list[str]] = {}
    if not os.path.exists(path):
        return terms, aliases
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                correct, _, raw_aliases = line.partition("=")
                correct = correct.strip()
                mishearings = [a.strip() for a in raw_aliases.split(",") if a.strip()]
                if correct and mishearings:
                    aliases[correct] = mishearings
                    terms.append(correct)
            else:
                terms.append(line)
    return terms, aliases


def get_whisper_prompt() -> str:
    terms, _ = _parse_vocab()
    return ", ".join(terms[:200]) if terms else ""


def correct(text: str) -> str:
    terms, aliases = _parse_vocab()
    if not text:
        return text

    aliases_section = ""
    if aliases:
        rules = "\n".join(
            f'  - {", ".join(m for m in mishearings)} -> "{correct_term}"'
            for correct_term, mishearings in aliases.items()
        )
        aliases_section = _ALIASES_HEADER.format(rules=rules)

    if not terms and not aliases:
        return text

    vocab_str = ", ".join(terms) if terms else "(none)"
    deployment = providers.get_chat_model()
    try:
        response = providers.get_client().chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": _SYSTEM.format(vocab=vocab_str, aliases_section=aliases_section)},
                {"role": "user", "content": text},
            ],
            max_completion_tokens=512,
            temperature=0,
        )
    except AuthenticationError:
        load_dotenv(os.path.join(_base, ".env"), override=True)
        providers.reset_clients()
        response = providers.get_client().chat.completions.create(
            model=providers.get_chat_model(),
            messages=[
                {"role": "system", "content": _SYSTEM.format(vocab=vocab_str, aliases_section=aliases_section)},
                {"role": "user", "content": text},
            ],
            max_completion_tokens=512,
            temperature=0,
        )
    return response.choices[0].message.content.strip()
