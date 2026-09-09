"""
Orchestrates extraction + chunking for files, images, and URLs, and
writes the resulting chunks out as JSONL — one chunk per line, ready
to be picked up by the embedding/vector-store step later.
"""

import json
import uuid
from pathlib import Path

from app.ingestion.chunker import chunk_text
from app.ingestion.extract_files import SUPPORTED_EXTENSIONS as FILE_EXTS
from app.ingestion.extract_files import extract_file
from app.ingestion.extract_images import caption_image
from app.ingestion.extract_urls import extract_url
from app.llm.openrouter_client import _MEDIA_TYPES as IMAGE_EXTS


def process_file(path: str | Path, chunk_size: int = 800, overlap: int = 100) -> list[dict]:
    path = Path(path)
    ext = path.suffix.lower()
    source_id = str(uuid.uuid4())

    if ext in IMAGE_EXTS:
        text = caption_image(path)
        source_type = "image"
    elif ext in FILE_EXTS:
        text = extract_file(path)
        source_type = "file"
    else:
        raise ValueError(f"Unsupported extension '{ext}' for {path}")

    chunks = chunk_text(
        text,
        source_id=source_id,
        source_type=source_type,
        source_path=str(path),
        chunk_size=chunk_size,
        overlap=overlap,
    )
    return [c.to_dict() for c in chunks]


def process_url(url: str, chunk_size: int = 800, overlap: int = 100) -> list[dict]:
    text = extract_url(url)
    source_id = str(uuid.uuid4())
    chunks = chunk_text(
        text,
        source_id=source_id,
        source_type="url",
        source_path=url,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    return [c.to_dict() for c in chunks]


def process_directory(
    directory: str | Path, chunk_size: int = 800, overlap: int = 100
) -> list[dict]:
    """Process every supported file (docs + images) found under `directory`."""
    directory = Path(directory)
    supported = FILE_EXTS | set(IMAGE_EXTS.keys())
    all_chunks: list[dict] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in supported:
            try:
                all_chunks.extend(
                    process_file(path, chunk_size=chunk_size, overlap=overlap)
                )
            except Exception as e:
                print(f"  [skip] {path}: {e}")
    return all_chunks


def write_jsonl(chunks: list[dict], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
