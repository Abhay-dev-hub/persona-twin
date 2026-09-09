"""
Thin wrapper around the OpenRouter chat-completions API
(https://openrouter.ai/docs). OpenRouter is OpenAI-compatible, so this
is a plain REST call — no extra SDK dependency needed beyond `requests`,
which the project already uses.

Requires OPENROUTER_API_KEY in the environment.

Model defaults to a vision-capable Claude model since both callers
(image captioning + graph extraction) need to work with the same
model, and image captioning specifically requires vision support.
Override with OPENROUTER_MODEL or the `model` argument if you'd
rather use something else (any vision-capable model on OpenRouter
works — GPT-4o, Gemini, etc.).
"""

import base64
import os
from pathlib import Path

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nex-agi/nex-n2.5-pro:free"

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _get_api_key() -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Export it before running, "
            "e.g. `export OPENROUTER_API_KEY=sk-or-...`"
        )
    return api_key


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
        # OpenRouter uses these purely for their own leaderboard/analytics;
        # harmless to include, safe to omit.
        "HTTP-Referer": "https://github.com/persona-twin",
        "X-Title": "Persona Twin",
    }


def chat_completion(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 1500,
    timeout: int = 60,
    exclude_reasoning: bool = False,
) -> str:
    """
    Send a chat-completion request to OpenRouter and return the
    assistant's text response.

    `messages` follows the standard OpenAI chat format, e.g.:
        [{"role": "user", "content": "hello"}]
    or, for vision:
        [{"role": "user", "content": [
            {"type": "text", "text": "..."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        ]}]

    `exclude_reasoning=True` tells OpenRouter to strip chain-of-thought
    from the response for models that expose one (e.g. reasoning/
    "thinking" models like Nemotron). Without this, some models dump
    their full reasoning trace into the response content, which can
    both bloat output and break callers expecting clean text (e.g.
    JSON parsing in the graph extractor).
    """
    payload = {
        "model": model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if exclude_reasoning:
        payload["reasoning"] = {"exclude": True}

    response = requests.post(OPENROUTER_URL, headers=_headers(), json=payload, timeout=timeout)

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter request failed ({response.status_code}): {response.text}"
        )

    data = response.json()

    try:
        content = data["choices"][0]["message"].get("content")
        if content is None:
            # Some models return None if blocked by safety filters or other issues
            raise RuntimeError(f"OpenRouter returned empty content. Response: {data}")
        return content
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected OpenRouter response shape: {data!r}") from e


def image_to_data_url(path: str | Path) -> str:
    """Encode a local image file as a base64 data: URL for vision messages."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    media_type = _MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ValueError(
            f"Unsupported image type '{path.suffix}'. Supported: {sorted(_MEDIA_TYPES)}"
        )

    encoded = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{media_type};base64,{encoded}"
