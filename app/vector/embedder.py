"""
Turns text into embedding vectors using `fastembed` — a lightweight,
CPU-friendly local embedding library (no API key, no per-call cost,
no network round-trip once the model is downloaded).

Default model: BAAI/bge-small-en-v1.5 (384 dimensions, good quality
for its size, fast on CPU). Swap via EMBEDDING_MODEL env var if you
want something else from fastembed's supported list.
"""

import os
from functools import lru_cache

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384  # must match the output dimension of DEFAULT_MODEL


@lru_cache(maxsize=1)
def _get_model():
    """
    Lazily load the embedding model once and cache it — loading is the
    slow part (downloads on first use, then loads into memory), so we
    don't want to repeat it per call.
    """
    from fastembed import TextEmbedding

    model_name = os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
    return TextEmbedding(model_name=model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns one vector (list of floats) per input text."""
    if not texts:
        return []
    model = _get_model()
    return [vec.tolist() for vec in model.embed(texts)]


def embed_text(text: str) -> list[float]:
    """Embed a single piece of text (e.g. a search query)."""
    return embed_texts([text])[0]
