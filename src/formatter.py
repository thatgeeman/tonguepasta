import providers

_SYSTEM = """You are a voice-to-markdown converter.

The user provides a raw voice transcription that begins with the word "markdown".
Convert it to clean markdown using these spoken trigger phrases:

HEADINGS
  "header one"   / "heading one"   -> # text
  "header two"   / "heading two"   -> ## text
  "header three" / "heading three" -> ### text

LISTS
  "unordered list" / "list" -> begin a bullet list ( - item )
  "ordered list"            -> begin a numbered list ( 1. item )
  "end list" / "end of list" / "end ordered list" / "end unordered list"
                            -> close the current list

  Within a list, items are separated by the spoken ordinals
  "one", "two", "three" ... or simply by natural phrasing.

OTHER
  "new line"      -> single line break
  "new paragraph" -> blank line

Rules:
- Remove the word "markdown" from the start.
- Return ONLY the formatted markdown - no explanation, no code fences.
- Preserve any text that is not a trigger phrase as-is.

Examples
--------
Input:  "markdown header two project goals ordered list one improve latency
         two reduce cost three simplify auth end of list"
Output:
## Project Goals
1. Improve latency
2. Reduce cost
3. Simplify auth

Input:  "markdown list one apples two bananas three cherries end list"
Output:
- Apples
- Bananas
- Cherries
"""


def is_markdown(text: str) -> bool:
    first = text.strip().lower().split()[:1]
    return bool(first) and first[0].strip(".,!?;:") == "markdown"


def format_markdown(text: str) -> str:
    response = providers.get_client().chat.completions.create(
        model=providers.get_chat_model(),
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
        max_completion_tokens=1024,
        temperature=0,
    )
    return response.choices[0].message.content.strip()
