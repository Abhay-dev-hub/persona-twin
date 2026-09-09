# # """
# # Reads chunks.jsonl (produced by Step 1), runs each chunk through the
# # LLM extractor, and writes the results into the Neo4j persona graph.
# # """
# #
# # import json
# # import uuid
# # from pathlib import Path
# #
# # from app.graph.extractor import extract_from_chunk
# # from app.graph.neo4j_client import GraphClient
# #
# #
# # def load_chunks(jsonl_path: str | Path) -> list[dict]:
# #     jsonl_path = Path(jsonl_path)
# #     if not jsonl_path.exists():
# #         raise FileNotFoundError(f"No such file: {jsonl_path}")
# #     chunks = []
# #     with jsonl_path.open(encoding="utf-8") as f:
# #         for line in f:
# #             line = line.strip()
# #             if line:
# #                 chunks.append(json.loads(line))
# #     return chunks
# #
# #
# # def build_graph(
# #     jsonl_path: str | Path,
# #     persona_name: str,
# #     client: GraphClient,
# #     model: str | None = None,
# #     verbose: bool = True,
# # ) -> dict:
# #     """
# #     Process every chunk in `jsonl_path` and write extracted
# #     facts/opinions/events/relationships into the graph, attached to
# #     `persona_name`.
# #
# #     Returns a summary dict with counts of each type written.
# #     """
# #     chunks = load_chunks(jsonl_path)
# #     client.ensure_constraints()
# #     client.upsert_person(persona_name, is_persona=True)
# #
# #     totals = {"facts": 0, "opinions": 0, "events": 0, "relationships": 0, "chunks_failed": 0}
# #
# #     for i, chunk in enumerate(chunks):
# #         text = chunk.get("text", "")
# #         source_id = chunk.get("source_id", "")
# #         source_path = chunk.get("source_path", "")
# #
# #         if verbose:
# #             print(f"  [{i + 1}/{len(chunks)}] extracting from {source_path} (chunk {chunk.get('index')})")
# #
# #         try:
# #             extracted = extract_from_chunk(text, model=model)
# #         except Exception as e:
# #             print(f"    [skip] extraction failed: {e}")
# #             totals["chunks_failed"] += 1
# #             continue
# #
# #         for fact in extracted["facts"]:
# #             client.upsert_fact(
# #                 fact_id=str(uuid.uuid4()),
# #                 text=fact.get("text", ""),
# #                 category=fact.get("category", "other"),
# #                 source_id=source_id,
# #                 source_path=source_path,
# #                 persona_name=persona_name,
# #             )
# #             totals["facts"] += 1
# #
# #         for opinion in extracted["opinions"]:
# #             client.upsert_opinion(
# #                 opinion_id=str(uuid.uuid4()),
# #                 text=opinion.get("text", ""),
# #                 topic=opinion.get("topic", ""),
# #                 sentiment=opinion.get("sentiment", "neutral"),
# #                 source_id=source_id,
# #                 source_path=source_path,
# #                 persona_name=persona_name,
# #             )
# #             totals["opinions"] += 1
# #
# #         for event in extracted["events"]:
# #             client.upsert_event(
# #                 event_id=str(uuid.uuid4()),
# #                 text=event.get("text", ""),
# #                 date=event.get("date", ""),
# #                 location=event.get("location", ""),
# #                 source_id=source_id,
# #                 source_path=source_path,
# #                 persona_name=persona_name,
# #             )
# #             totals["events"] += 1
# #
# #         for rel in extracted["relationships"]:
# #             other = rel.get("person", "").strip()
# #             relation_type = rel.get("relation_type", "unknown").strip()
# #             if other:
# #                 client.upsert_relationship(persona_name, other, relation_type)
# #                 totals["relationships"] += 1
# #
# #     return totals
# """
# Reads chunks.jsonl (produced by Step 1), runs each chunk through the
# LLM extractor, and writes the results into the Neo4j persona graph.
# """
#
# import json
# import time
# import uuid
# from pathlib import Path
#
# from app.graph.extractor import extract_from_chunk
# from app.graph.neo4j_client import GraphClient
#
#
# def load_chunks(jsonl_path: str | Path) -> list[dict]:
#     jsonl_path = Path(jsonl_path)
#     if not jsonl_path.exists():
#         raise FileNotFoundError(f"No such file: {jsonl_path}")
#     chunks = []
#     with jsonl_path.open(encoding="utf-8") as f:
#         for line in f:
#             line = line.strip()
#             if line:
#                 chunks.append(json.loads(line))
#     return chunks
#
#
# def build_graph(
#     jsonl_path: str | Path,
#     persona_name: str,
#     client: GraphClient,
#     model: str | None = None,
#     verbose: bool = True,
# ) -> dict:
#     """
#     Process every chunk in `jsonl_path` and write extracted
#     facts/opinions/events/relationships into the graph, attached to
#     `persona_name`.
#
#     Returns a summary dict with counts of each type written.
#     """
#     chunks = load_chunks(jsonl_path)
#     client.ensure_constraints()
#     client.upsert_person(persona_name, is_persona=True)
#
#     totals = {"facts": 0, "opinions": 0, "events": 0, "relationships": 0, "chunks_failed": 0}
#
#     for i, chunk in enumerate(chunks):
#         text = chunk.get("text", "")
#         source_id = chunk.get("source_id", "")
#         source_path = chunk.get("source_path", "")
#
#         if verbose:
#             print(f"  [{i + 1}/{len(chunks)}] extracting from {source_path} (chunk {chunk.get('index')})")
#
#         extracted = None
#         last_error = None
#         for attempt in range(3):
#             try:
#                 extracted = extract_from_chunk(text, model=model)
#                 break
#             except Exception as e:
#                 last_error = e
#                 if attempt < 2:
#                     wait = 5 * (attempt + 1)  # 5s, then 10s
#                     print(f"    [retry] extraction failed ({e}), retrying in {wait}s ...")
#                     time.sleep(wait)
#
#         if extracted is None:
#             print(f"    [skip] extraction failed after 3 attempts: {last_error}")
#             totals["chunks_failed"] += 1
#             continue
#
#         # Defensive: extract_from_chunk should always return a well-formed
#         # dict, but guard anyway rather than crash the whole run on a
#         # single unexpected chunk.
#         if not isinstance(extracted, dict):
#             print(f"    [skip] extraction returned unexpected type: {type(extracted).__name__}")
#             totals["chunks_failed"] += 1
#             continue
#
#         for fact in extracted.get("facts") or []:
#             if not isinstance(fact, dict) or not fact.get("text"):
#                 continue
#             client.upsert_fact(
#                 fact_id=str(uuid.uuid4()),
#                 text=fact.get("text", ""),
#                 category=fact.get("category", "other"),
#                 source_id=source_id,
#                 source_path=source_path,
#                 persona_name=persona_name,
#             )
#             totals["facts"] += 1
#
#         for opinion in extracted.get("opinions") or []:
#             if not isinstance(opinion, dict) or not opinion.get("text"):
#                 continue
#             client.upsert_opinion(
#                 opinion_id=str(uuid.uuid4()),
#                 text=opinion.get("text", ""),
#                 topic=opinion.get("topic", ""),
#                 sentiment=opinion.get("sentiment", "neutral"),
#                 source_id=source_id,
#                 source_path=source_path,
#                 persona_name=persona_name,
#             )
#             totals["opinions"] += 1
#
#         for event in extracted.get("events") or []:
#             if not isinstance(event, dict) or not event.get("text"):
#                 continue
#             client.upsert_event(
#                 event_id=str(uuid.uuid4()),
#                 text=event.get("text", ""),
#                 date=event.get("date", ""),
#                 location=event.get("location", ""),
#                 source_id=source_id,
#                 source_path=source_path,
#                 persona_name=persona_name,
#             )
#             totals["events"] += 1
#
#         for rel in extracted.get("relationships") or []:
#             if not isinstance(rel, dict):
#                 continue
#             other = (rel.get("person") or "").strip()
#             relation_type = (rel.get("relation_type") or "unknown").strip()
#             if other:
#                 client.upsert_relationship(persona_name, other, relation_type)
#                 totals["relationships"] += 1
#
#     return totals

# import json
# import time
# from pathlib import Path
# from typing import Any
# from app.graph.extractor import extract_from_chunk
# from app.graph.neo4j_client import GraphClient
#
#
# def build_graph(chunks_jsonl: Path, name: str, client: GraphClient, verbose: bool = False) -> None:
#     if not chunks_jsonl.exists():
#         if verbose:
#             print(f"Skipping graph build: {chunks_jsonl} not found.")
#         return
#
#     with chunks_jsonl.open("r", encoding="utf-8") as f:
#         lines = f.readlines()
#
#     for i, line in enumerate(lines):
#         line = line.strip()
#         if not line:
#             continue
#         try:
#             chunk_data = json.loads(line)
#         except json.JSONDecodeError:
#             continue
#
#         text = chunk_data.get("text", "")
#         if not text:
#             continue
#
#         if verbose:
#             print(f"[{name}] Extracting graph entities from chunk {i + 1}/{len(lines)}...")
#
#         # Add a retry loop for LLM extraction
#         max_retries = 3
#         extraction = None
#         for attempt in range(max_retries):
#             try:
#                 extraction = extract_from_chunk(text)
#                 break
#             except Exception as e:
#                 if verbose:
#                     print(f"  Extraction failed (attempt {attempt + 1}/{max_retries}): {e}")
#                 time.sleep(2)
#
#         if not extraction:
#             continue
#
#         try:
#             if hasattr(extraction, "facts") and extraction.facts:
#                 for fact in extraction.facts:
#                     client.upsert_fact(name, fact.model_dump())
#
#             if hasattr(extraction, "opinions") and extraction.opinions:
#                 for op in extraction.opinions:
#                     client.upsert_opinion(name, op.model_dump())
#
#             if hasattr(extraction, "events") and extraction.events:
#                 for ev in extraction.events:
#                     client.upsert_event(name, ev.model_dump())
#
#             if hasattr(extraction, "relationships") and extraction.relationships:
#                 for rel in extraction.relationships:
#                     client.upsert_relationship(name, rel.model_dump())
#
#             if hasattr(extraction, "personality_traits") and extraction.personality_traits:
#                 for trait in extraction.personality_traits:
#                     client.upsert_trait(name, trait.model_dump())
#
#         except Exception as e:
#             if verbose:
#                 print(f"  Error inserting entities to Neo4j: {e}")

import json
import time
from pathlib import Path
from app.graph.extractor import extract_from_chunk
from app.graph.neo4j_client import GraphClient


def build_graph(chunks_jsonl: Path, name: str, client: GraphClient, verbose: bool = False) -> dict:
    """
    Returns a totals dict: {"facts": n, "opinions": n, "events": n,
    "relationships": n, "traits": n, "chunks_failed": n, "chunks_total": n}
    so callers can detect a fully-failed run (e.g. every chunk hit a rate
    limit) even when verbose=False.
    """
    totals = {
        "facts": 0, "opinions": 0, "events": 0,
        "relationships": 0, "traits": 0,
        "chunks_failed": 0, "chunks_total": 0,
    }

    if not chunks_jsonl.exists():
        print(f"[{name}] Skipping graph build: {chunks_jsonl} not found.")
        return totals

    with chunks_jsonl.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            chunk_data = json.loads(line)
        except json.JSONDecodeError:
            continue

        text = chunk_data.get("text", "")
        if not text:
            continue

        totals["chunks_total"] += 1

        if verbose:
            print(f"[{name}] Extracting graph entities from chunk {i + 1}/{len(lines)}...")

        max_retries = 3
        extraction = None
        last_error = None
        for attempt in range(max_retries):
            try:
                extraction = extract_from_chunk(text)
                break
            except Exception as e:
                last_error = e
                # Always print this, regardless of verbose — a fully-silent
                # extraction pipeline is exactly what made the last failure
                # invisible (zero Neo4j writes, no error anywhere).
                print(f"[{name}] Extraction failed on chunk {i + 1} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(3 * (attempt + 1))

        if not extraction:
            print(f"[{name}] [skip] chunk {i + 1} failed after {max_retries} attempts: {last_error}")
            totals["chunks_failed"] += 1
            continue

        try:
            for fact in extraction.facts:
                client.upsert_fact(name, fact.model_dump())
                totals["facts"] += 1

            for op in extraction.opinions:
                client.upsert_opinion(name, op.model_dump())
                totals["opinions"] += 1

            for ev in extraction.events:
                client.upsert_event(name, ev.model_dump())
                totals["events"] += 1

            for rel in extraction.relationships:
                client.upsert_relationship(name, rel.model_dump())
                totals["relationships"] += 1

            for trait in extraction.personality_traits:
                client.upsert_trait(name, trait.model_dump())
                totals["traits"] += 1

        except Exception as e:
            print(f"[{name}] Error inserting entities to Neo4j for chunk {i + 1}: {e}")

    print(
        f"[{name}] Graph build done: {totals['facts']} facts, {totals['opinions']} opinions, "
        f"{totals['events']} events, {totals['relationships']} relationships, "
        f"{totals['traits']} traits ({totals['chunks_failed']}/{totals['chunks_total']} chunks failed)."
    )
    return totals