"""
Splits raw text into overlapping chunks suitable for embedding.

Strategy: split on paragraph boundaries first, then greedily pack
paragraphs into chunks up to `chunk_size` characters. If a single
paragraph is longer than `chunk_size`, it gets split on sentence
boundaries as a fallback. Adjacent chunks share `overlap` characters
of trailing/leading context so retrieval doesn't lose meaning at the
edges of a split.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chunk:
    text: str
    index: int
    source_id: str
    source_type: str  # "file" | "image" | "url"
    source_path: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "index": self.index,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "metadata": self.metadata,
        }


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    """Fallback splitter for a single paragraph longer than chunk_size."""
    sentences = _SENTENCE_SPLIT_RE.split(paragraph)
    pieces, current = [], ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                pieces.append(current)
            # sentence itself might exceed chunk_size (rare) - hard cut
            if len(sentence) > chunk_size:
                for i in range(0, len(sentence), chunk_size):
                    pieces.append(sentence[i : i + chunk_size])
                current = ""
            else:
                current = sentence
    if current:
        pieces.append(current)
    return pieces


def chunk_text(
    text: str,
    source_id: str,
    source_type: str,
    source_path: str,
    chunk_size: int = 800,
    overlap: int = 100,
    metadata: Optional[dict] = None,
) -> list[Chunk]:
    """Chunk `text` into a list of Chunk objects."""
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    raw_pieces: list[str] = []
    buffer = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if buffer:
                raw_pieces.append(buffer)
                buffer = ""
            raw_pieces.extend(_split_paragraph(para, chunk_size))
            continue
        candidate = f"{buffer}\n\n{para}".strip()
        if len(candidate) <= chunk_size:
            buffer = candidate
        else:
            if buffer:
                raw_pieces.append(buffer)
            buffer = para
    if buffer:
        raw_pieces.append(buffer)

    # apply overlap by prepending the tail of the previous piece
    chunks: list[Chunk] = []
    for i, piece in enumerate(raw_pieces):
        if i > 0 and overlap > 0:
            prev_tail = raw_pieces[i - 1][-overlap:]
            piece = f"{prev_tail} {piece}".strip()
        chunks.append(
            Chunk(
                text=piece,
                index=i,
                source_id=source_id,
                source_type=source_type,
                source_path=source_path,
                metadata=metadata or {},
            )
        )
    return chunks
