# # # """
# # # Orchestrates the full persona-creation pipeline (extract -> chunk ->
# # # graph -> embed) triggered from the UI, running in a background thread
# # # so the upload request returns immediately and the frontend can poll
# # # status instead of blocking on what might be a multi-minute job.
# # # """
# # #
# # # import re
# # # import threading
# # # import traceback
# # # import uuid
# # # from pathlib import Path
# # #
# # # from app.graph.neo4j_client import GraphClient
# # # from app.graph.pipeline import build_graph
# # # from app.ingestion.pipeline import process_directory, write_jsonl
# # # from app.storage import db
# # # from app.vector.pipeline import embed_and_store
# # # from app.vector.qdrant_client import VectorClient
# # #
# # # UPLOADS_ROOT = Path("data") / "personas"
# # # CHUNKS_ROOT = Path("data") / "output" / "personas"
# # #
# # #
# # # def slugify(name: str) -> str:
# # #     slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
# # #     return slug or "persona"
# # #
# # #
# # # def unique_collection_name(name: str) -> str:
# # #     """Qdrant collection names double as the persona's slug identity.
# # #     Append a short suffix if the slug is already taken."""
# # #     base = slugify(name)
# # #     existing = {p["collection_name"] for p in db.list_personas()}
# # #     if base not in existing:
# # #         return base
# # #     return f"{base}_{uuid.uuid4().hex[:6]}"
# # #
# # #
# # # def register_persona(name: str) -> dict:
# # #     """Creates the DB record only (status='pending'). Caller is
# # #     responsible for saving uploaded files to UPLOADS_ROOT / persona['id']
# # #     before calling start_background()."""
# # #     collection_name = unique_collection_name(name)
# # #     return db.create_persona(name, collection_name)
# # #
# # #
# # # def start_background(persona_id: str, name: str, collection_name: str) -> None:
# # #     """Kicks off the extract -> graph -> embed pipeline in a background
# # #     thread. Assumes source files already exist under
# # #     UPLOADS_ROOT / persona_id (see register_persona)."""
# # #     thread = threading.Thread(
# # #         target=_run_pipeline, args=(persona_id, name, collection_name), daemon=True
# # #     )
# # #     thread.start()
# # #
# # #
# # # def _run_pipeline(persona_id: str, name: str, collection_name: str) -> None:
# # #     try:
# # #         db.update_persona_status(persona_id, "processing")
# # #
# # #         raw_dir = UPLOADS_ROOT / persona_id
# # #         chunks_path = CHUNKS_ROOT / f"{persona_id}.jsonl"
# # #         chunks_path.parent.mkdir(parents=True, exist_ok=True)
# # #         if chunks_path.exists():
# # #             chunks_path.unlink()
# # #
# # #         chunks = process_directory(raw_dir)
# # #         if not chunks:
# # #             raise RuntimeError("No text could be extracted from the uploaded file(s).")
# # #         write_jsonl(chunks, chunks_path)
# # #
# # #         with GraphClient() as graph_client:
# # #             build_graph(chunks_path, name, graph_client, verbose=False)
# # #
# # #         with VectorClient() as vector_client:
# # #             embed_and_store(chunks_path, collection_name, vector_client, verbose=False)
# # #
# # #         db.update_persona_status(persona_id, "ready")
# # #
# # #     except Exception as e:
# # #         traceback.print_exc()
# # #         db.update_persona_status(persona_id, "error", error_message=str(e))
# #
# # """
# # Orchestrates the full persona-creation pipeline (extract -> chunk ->
# # graph -> embed) triggered from the UI.
# #
# # Jobs run through a single background worker thread pulling from a
# # queue — NOT one thread per persona. Running them one at a time avoids
# # several personas' extraction calls competing for the same OpenRouter
# # rate limit at once (which was silently causing some personas' graphs
# # to come out empty while still reporting "ready").
# # """
# #
# # import queue
# # import re
# # import threading
# # import traceback
# # import uuid
# # from pathlib import Path
# #
# # from app.graph.neo4j_client import GraphClient
# # from app.graph.pipeline import build_graph
# # from app.ingestion.pipeline import process_directory, process_url, write_jsonl
# # from app.storage import db
# # from app.vector.pipeline import embed_and_store
# # from app.vector.qdrant_client import VectorClient
# #
# # UPLOADS_ROOT = Path("data") / "personas"
# # CHUNKS_ROOT = Path("data") / "output" / "personas"
# #
# # _job_queue: "queue.Queue[tuple[str, str, str]]" = queue.Queue()
# # _worker_started = False
# # _worker_lock = threading.Lock()
# #
# #
# # def slugify(name: str) -> str:
# #     slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
# #     return slug or "persona"
# #
# #
# # def unique_collection_name(name: str) -> str:
# #     """Qdrant collection names double as the persona's slug identity.
# #     Append a short suffix if the slug is already taken."""
# #     base = slugify(name)
# #     existing = {p["collection_name"] for p in db.list_personas()}
# #     if base not in existing:
# #         return base
# #     return f"{base}_{uuid.uuid4().hex[:6]}"
# #
# #
# # def register_persona(name: str) -> dict:
# #     """Creates the DB record only (status='pending'). Caller is
# #     responsible for saving uploaded files to UPLOADS_ROOT / persona['id']
# #     before calling start_background()."""
# #     collection_name = unique_collection_name(name)
# #     return db.create_persona(name, collection_name)
# #
# #
# # def start_background(persona_id: str, name: str, collection_name: str, urls: list[str] | None = None) -> None:
# #     """Kicks off the extract -> graph -> embed pipeline in a background
# #     thread. Assumes source files already exist under
# #     UPLOADS_ROOT / persona_id (see register_persona)."""
# #     thread = threading.Thread(
# #         target=_run_pipeline, args=(persona_id, name, collection_name, urls or []), daemon=True
# #     )
# #     thread.start()
# #
# #
# # def _worker_loop() -> None:
# #     while True:
# #         persona_id, name, collection_name = _job_queue.get()
# #         try:
# #             _run_pipeline(persona_id, name, collection_name)
# #         except Exception:
# #             traceback.print_exc()
# #         finally:
# #             _job_queue.task_done()
# #
# #
# # def _run_pipeline(persona_id: str, name: str, collection_name: str, urls: list[str]) -> None:
# #     try:
# #         db.update_persona_status(persona_id, "processing")
# #
# #         raw_dir = UPLOADS_ROOT / persona_id
# #         chunks_path = CHUNKS_ROOT / f"{persona_id}.jsonl"
# #         chunks_path.parent.mkdir(parents=True, exist_ok=True)
# #         if chunks_path.exists():
# #             chunks_path.unlink()
# #
# #         chunks = process_directory(raw_dir) if raw_dir.exists() else []
# #
# #         for url in urls:
# #             url = url.strip()
# #             if not url:
# #                 continue
# #             try:
# #                 chunks.extend(process_url(url))
# #             except Exception as e:
# #                 print(f"  [skip] {url}: {e}")
# #
# #         if not chunks:
# #             raise RuntimeError("No text could be extracted from the uploaded file(s) or URL(s).")
# #         write_jsonl(chunks, chunks_path)
#
# """
# Orchestrates the full persona-creation pipeline (extract -> chunk ->
# graph -> embed) triggered from the UI.
#
# Jobs run through a single background worker thread pulling from a
# queue — NOT one thread per persona. Running them one at a time avoids
# several personas' extraction calls competing for the same OpenRouter
# rate limit at once.
# """
#
# import queue
# import re
# import threading
# import traceback
# import uuid
# from pathlib import Path
#
# from app.graph.neo4j_client import GraphClient
# from app.graph.pipeline import build_graph
# from app.ingestion.pipeline import process_directory, process_url, write_jsonl
# from app.storage import db
# from app.vector.pipeline import embed_and_store
# from app.vector.qdrant_client import VectorClient
#
# UPLOADS_ROOT = Path("data") / "personas"
# CHUNKS_ROOT = Path("data") / "output" / "personas"
#
# _job_queue: "queue.Queue[tuple[str, str, str, list[str]]]" = queue.Queue()
# _worker_started = False
# _worker_lock = threading.Lock()
#
#
# def slugify(name: str) -> str:
#     slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
#     return slug or "persona"
#
#
# def unique_collection_name(name: str) -> str:
#     """Qdrant collection names double as the persona's slug identity.
#     Append a short suffix if the slug is already taken."""
#     base = slugify(name)
#     existing = {p["collection_name"] for p in db.list_personas()}
#     if base not in existing:
#         return base
#     return f"{base}_{uuid.uuid4().hex[:6]}"
#
#
# def register_persona(name: str) -> dict:
#     """Creates the DB record only (status='pending'). Caller is
#     responsible for saving uploaded files to UPLOADS_ROOT / persona['id']
#     before calling start_background()."""
#     collection_name = unique_collection_name(name)
#     return db.create_persona(name, collection_name)
#
#
# def _ensure_worker_running() -> None:
#     global _worker_started
#     with _worker_lock:
#         if not _worker_started:
#             thread = threading.Thread(target=_worker_loop, daemon=True)
#             thread.start()
#             _worker_started = True
#
#
# def _worker_loop() -> None:
#     while True:
#         persona_id, name, collection_name, urls = _job_queue.get()
#         try:
#             _run_pipeline(persona_id, name, collection_name, urls)
#         except Exception:
#             traceback.print_exc()
#         finally:
#             _job_queue.task_done()
#
#
# def start_background(persona_id: str, name: str, collection_name: str, urls: list[str] | None = None) -> None:
#     """Queues the extract -> graph -> embed pipeline."""
#     _ensure_worker_running()
#     _job_queue.put((persona_id, name, collection_name, urls or []))
#
#
# def _run_pipeline(persona_id: str, name: str, collection_name: str, urls: list[str]) -> None:
#     try:
#         db.update_persona_status(persona_id, "processing")
#
#         raw_dir = UPLOADS_ROOT / persona_id
#         chunks_path = CHUNKS_ROOT / f"{persona_id}.jsonl"
#         chunks_path.parent.mkdir(parents=True, exist_ok=True)
#         if chunks_path.exists():
#             chunks_path.unlink()
#
#         chunks = process_directory(raw_dir) if raw_dir.exists() else []
#
#         for url in urls:
#             url = url.strip()
#             if not url:
#                 continue
#             try:
#                 chunks.extend(process_url(url))
#             except Exception as e:
#                 print(f"  [skip] {url}: {e}")
#
#         if not chunks:
#             raise RuntimeError("No text could be extracted from the uploaded file(s) or URL(s).")
#         write_jsonl(chunks, chunks_path)
#
#         with GraphClient() as graph_client:
#             build_graph(chunks_path, name, graph_client, verbose=False)
#
#         with VectorClient() as vector_client:
#             embed_and_store(chunks_path, collection_name, vector_client, verbose=False)
#
#         db.update_persona_status(persona_id, "ready")
#
#     except Exception as e:
#         traceback.print_exc()
#         db.update_persona_status(persona_id, "error", error_message=str(e))

import queue
import re
import threading
import traceback
import uuid
import shutil
from pathlib import Path

from app.graph.neo4j_client import GraphClient
from app.graph.pipeline import build_graph
from app.ingestion.pipeline import process_directory, process_url, process_file, write_jsonl
from app.storage import db
from app.vector.pipeline import embed_and_store
from app.vector.qdrant_client import VectorClient

UPLOADS_ROOT = Path("data") / "personas"
CHUNKS_ROOT = Path("data") / "output" / "personas"

_job_queue: "queue.Queue[tuple[str, str, str, list[str]]]" = queue.Queue()
_update_queue: "queue.Queue[tuple[str, str, str, list[str], list[Path]]]" = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
    return slug or "persona"


def unique_collection_name(name: str) -> str:
    base = slugify(name)
    existing = {p["collection_name"] for p in db.list_personas()}
    if base not in existing:
        return base
    return f"{base}_{uuid.uuid4().hex[:6]}"


def register_persona(name: str) -> dict:
    collection_name = unique_collection_name(name)
    return db.create_persona(name, collection_name)


def _ensure_worker_running() -> None:
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            thread = threading.Thread(target=_worker_loop, daemon=True)
            thread.start()
            _worker_started = True


def _worker_loop() -> None:
    while True:
        try:
            task = _update_queue.get_nowait()
            try:
                _run_update_pipeline(*task)
            except Exception:
                traceback.print_exc()
            finally:
                _update_queue.task_done()
            continue
        except queue.Empty:
            pass

        try:
            persona_id, name, collection_name, urls = _job_queue.get(timeout=1.0)
            try:
                _run_pipeline(persona_id, name, collection_name, urls)
            except Exception:
                traceback.print_exc()
            finally:
                _job_queue.task_done()
        except queue.Empty:
            pass


def start_background(persona_id: str, name: str, collection_name: str, urls: list[str] | None = None) -> None:
    _ensure_worker_running()
    _job_queue.put((persona_id, name, collection_name, urls or []))


def queue_update(persona_id: str, name: str, collection_name: str, urls: list[str], new_files: list[Path]) -> None:
    _ensure_worker_running()
    _update_queue.put((persona_id, name, collection_name, urls, new_files))


def _run_pipeline(persona_id: str, name: str, collection_name: str, urls: list[str]) -> None:
    try:
        db.update_persona_status(persona_id, "processing")
        raw_dir = UPLOADS_ROOT / persona_id
        chunks_path = CHUNKS_ROOT / f"{persona_id}.jsonl"
        chunks_path.parent.mkdir(parents=True, exist_ok=True)
        if chunks_path.exists():
            chunks_path.unlink()

        chunks = process_directory(raw_dir) if raw_dir.exists() else []

        for url in urls:
            url = url.strip()
            if not url: continue
            try:
                chunks.extend(process_url(url))
            except Exception as e:
                print(f"  [skip] {url}: {e}")

        if not chunks:
            raise RuntimeError("No text could be extracted from the uploaded file(s) or URL(s).")
        write_jsonl(chunks, chunks_path)

        with GraphClient() as graph_client:
            graph_totals = build_graph(chunks_path, name, graph_client, verbose=True)

        # build_graph skips chunks that fail extraction rather than raising
        # (so one bad chunk doesn't sink the whole run) — but if EVERY chunk
        # failed (rate limit, bad API key, schema mismatch), nothing was
        # actually written to Neo4j even though nothing "crashed". Catch
        # that here instead of silently marking the persona ready with an
        # empty graph.
        chunks_total = graph_totals.get("chunks_total", 0)
        chunks_failed = graph_totals.get("chunks_failed", 0)

        # Only treat this as a real failure if every chunk actually errored
        # out during extraction (bad JSON, API error, schema mismatch).
        # A chunk that extracted successfully but legitimately found no
        # facts/opinions (e.g. thin source material like a bare GitHub
        # profile page) is NOT a failure — don't block persona creation
        # over it, just note it.
        if chunks_total > 0 and chunks_failed >= chunks_total:
            raise RuntimeError(
                f"Graph extraction failed for all {chunks_total} chunk(s) — "
                f"check server logs for the actual per-chunk error (rate limit, bad API "
                f"key, or model output not matching the expected schema)."
            )

        wrote_anything = any(
            graph_totals.get(k, 0) > 0
            for k in ("facts", "opinions", "events", "relationships", "traits")
        )
        if not wrote_anything:
            print(
                f"[{name}] Warning: extraction succeeded but found no facts/opinions/events "
                f"to write — source material may be too thin (e.g. mostly boilerplate/nav "
                f"text) rather than personal narrative content."
            )

        with VectorClient() as vector_client:
            embed_and_store(chunks_path, collection_name, vector_client, verbose=True)

        db.update_persona_status(persona_id, "ready")

    except Exception as e:
        traceback.print_exc()
        db.update_persona_status(persona_id, "error", error_message=str(e))


def _run_update_pipeline(persona_id: str, name: str, collection_name: str, urls: list[str],
                         new_files: list[Path]) -> None:
    try:
        db.update_persona_status(persona_id, "processing")

        chunks = []
        for path in new_files:
            try:
                chunks.extend(process_file(path))
            except Exception as e:
                print(f"  [skip] {path}: {e}")

        for url in urls:
            url = url.strip()
            if not url: continue
            try:
                chunks.extend(process_url(url))
            except Exception as e:
                print(f"  [skip] {url}: {e}")

        if not chunks:
            db.update_persona_status(persona_id, "ready")
            return

        temp_chunks_path = CHUNKS_ROOT / f"{persona_id}_temp_{uuid.uuid4().hex[:6]}.jsonl"
        write_jsonl(chunks, temp_chunks_path)

        with GraphClient() as graph_client:
            graph_totals = build_graph(temp_chunks_path, name, graph_client, verbose=True)

        chunks_total = graph_totals.get("chunks_total", 0)
        chunks_failed = graph_totals.get("chunks_failed", 0)

        if chunks_total > 0 and chunks_failed >= chunks_total:
            raise RuntimeError(
                f"Graph extraction failed for all {chunks_total} new chunk(s) — "
                f"check server logs for the actual per-chunk error."
            )

        wrote_anything = any(
            graph_totals.get(k, 0) > 0
            for k in ("facts", "opinions", "events", "relationships", "traits")
        )
        if not wrote_anything:
            print(f"[{name}] Warning: extraction succeeded but found no new facts/opinions to add.")

        with VectorClient() as vector_client:
            embed_and_store(temp_chunks_path, collection_name, vector_client, verbose=True)

        main_chunks_path = CHUNKS_ROOT / f"{persona_id}.jsonl"
        with main_chunks_path.open("a", encoding="utf-8") as main_f:
            with temp_chunks_path.open("r", encoding="utf-8") as temp_f:
                shutil.copyfileobj(temp_f, main_f)

        temp_chunks_path.unlink()
        db.update_persona_status(persona_id, "ready")

    except Exception as e:
        traceback.print_exc()
        db.update_persona_status(persona_id, "error", error_message=str(e))