"""
Reads chunks.jsonl (from Step 1), embeds each chunk, and writes the
resulting vectors + payloads into a Qdrant collection.
"""

import json
from pathlib import Path

from app.vector.embedder import VECTOR_SIZE, embed_texts
from app.vector.qdrant_client import VectorClient

BATCH_SIZE = 64  # texts per embedding call — keeps memory bounded on large chunk sets


def load_chunks(jsonl_path: str | Path) -> list[dict]:
    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        raise FileNotFoundError(f"No such file: {jsonl_path}")
    chunks = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def embed_and_store(
    jsonl_path: str | Path,
    collection_name: str,
    client: VectorClient,
    batch_size: int = BATCH_SIZE,
    verbose: bool = True,
) -> int:
    """
    Embed every chunk in `jsonl_path` and upsert into `collection_name`.
    Returns the number of chunks written.
    """
    chunks = load_chunks(jsonl_path)
    if not chunks:
        return 0

    client.ensure_collection(collection_name, vector_size=VECTOR_SIZE)

    total = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.get("text", "") for c in batch]

        if verbose:
            print(f"  embedding chunks {i + 1}-{i + len(batch)} of {len(chunks)} ...")

        vectors = embed_texts(texts)
        client.upsert_chunks(collection_name, batch, vectors)
        total += len(batch)

    return total
