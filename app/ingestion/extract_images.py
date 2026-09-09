"""
Caption images using a vision-capable model via OpenRouter, so the
caption can be treated like any other text chunk downstream.

Requires OPENROUTER_API_KEY in the environment.
"""

from pathlib import Path

from app.llm.openrouter_client import chat_completion, image_to_data_url

DEFAULT_PROMPT = (
    "Describe this image factually and in detail: what it shows, any text "
    "visible in it, and any context clues about when/where it's from. "
    "This description will stand in for the image in a text-only knowledge "
    "base, so be thorough rather than brief."
)


def caption_image(path: str | Path, prompt: str = DEFAULT_PROMPT, model: str | None = None) -> str:
    path = Path(path)
    data_url = image_to_data_url(path)  # raises if missing/unsupported type

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]

    return chat_completion(messages, model=model, max_tokens=500)
