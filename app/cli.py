# """
# CLI for Step 1: extract + chunk raw source material (files, images,
# URLs) into JSONL, ready for embedding in a later step.
#
# Usage:
#     python -m app.cli file path/to/doc.pdf
#     python -m app.cli file path/to/photo.jpg
#     python -m app.cli url https://example.com/article
#     python -m app.cli dir data/raw
#     python -m app.cli graph --persona "Jane Doe" data/output/chunks.jsonl
#     python -m app.cli embed --collection jane_doe data/output/chunks.jsonl
#     python -m app.cli search --collection jane_doe "what does she think about the ocean?"
#         python -m app.cli debug-prompt --persona "Jane Doe" --collection jane_doe "what do you think about the ocean?"
#
# All commands append to data/output/chunks.jsonl by default.
# """
#
# import argparse
# import sys
# from pathlib import Path
#
# from dotenv import load_dotenv
#
# from app.ingestion.pipeline import process_directory, process_file, process_url, write_jsonl
#
# # Load variables from a .env file in the current directory (if present)
# # before anything else reads os.environ. Real environment variables
# # already set take precedence over .env values.
# load_dotenv()
#
# DEFAULT_OUTPUT = "data/output/chunks.jsonl"
#
#
# def main() -> None:
#     parser = argparse.ArgumentParser(description="Persona Twin — data extraction tool")
#     parser.add_argument(
#         "--output", "-o", default=DEFAULT_OUTPUT, help=f"Output JSONL path (default: {DEFAULT_OUTPUT})"
#     )
#     parser.add_argument(
#         "--chunk-size", type=int, default=800, help="Target chunk size in characters (default: 800)"
#     )
#     parser.add_argument(
#         "--overlap", type=int, default=100, help="Overlap between chunks in characters (default: 100)"
#     )
#
#     subparsers = parser.add_subparsers(dest="command", required=True)
#
#     file_parser = subparsers.add_parser("file", help="Extract a single file (doc or image)")
#     file_parser.add_argument("path", help="Path to the file")
#
#     url_parser = subparsers.add_parser("url", help="Extract a single URL")
#     url_parser.add_argument("url", help="URL to fetch")
#
#     dir_parser = subparsers.add_parser("dir", help="Extract every supported file in a directory")
#     dir_parser.add_argument("path", help="Directory to scan")
#
#     graph_parser = subparsers.add_parser(
#         "graph", help="Build the persona knowledge graph from a chunks.jsonl file"
#     )
#     graph_parser.add_argument("jsonl_path", help="Path to chunks.jsonl (from Step 1)")
#     graph_parser.add_argument("--persona", required=True, help="Name of the persona these chunks belong to")
#     graph_parser.add_argument(
#         "--model", default=None, help="OpenRouter model slug to use for extraction (default: nvidia/nemotron-3.5-lightning:free, or $OPENROUTER_MODEL)"
#     )
#
#     embed_parser = subparsers.add_parser(
#         "embed", help="Embed chunks.jsonl and store vectors in Qdrant"
#     )
#     embed_parser.add_argument("jsonl_path", help="Path to chunks.jsonl (from Step 1)")
#     embed_parser.add_argument("--collection", required=True, help="Qdrant collection name to write into")
#
#     search_parser = subparsers.add_parser(
#         "search", help="Search a Qdrant collection for chunks similar to a query"
#     )
#     search_parser.add_argument("query", help="Search query text")
#     search_parser.add_argument("--collection", required=True, help="Qdrant collection name to search")
#     search_parser.add_argument("--top-k", type=int, default=5, help="Number of results to return (default: 5)")
#
#     debug_parser = subparsers.add_parser(
#         "debug-prompt",
#         help="Build and print the persona system prompt for a question, without calling the LLM",
#     )
#     debug_parser.add_argument("query", help="The question to build a persona prompt for")
#     debug_parser.add_argument("--persona", required=True, help="Persona name (must match what's in Neo4j)")
#     debug_parser.add_argument("--collection", required=True,
#                               help="Qdrant collection name (must match what's in Qdrant)")
#     debug_parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
#
#     args = parser.parse_args()
#
#     if args.command == "file":
#         print(f"Extracting {args.path} ...")
#         chunks = process_file(args.path, chunk_size=args.chunk_size, overlap=args.overlap)
#     elif args.command == "url":
#         print(f"Fetching {args.url} ...")
#         chunks = process_url(args.url, chunk_size=args.chunk_size, overlap=args.overlap)
#     elif args.command == "dir":
#         print(f"Scanning {args.path} ...")
#         chunks = process_directory(args.path, chunk_size=args.chunk_size, overlap=args.overlap)
#     elif args.command == "graph":
#         from app.graph.neo4j_client import GraphClient
#         from app.graph.pipeline import build_graph
#
#         print(f"Building persona graph for '{args.persona}' from {args.jsonl_path} ...")
#         with GraphClient() as client:
#             totals = build_graph(args.jsonl_path, args.persona, client, model=args.model)
#         print(
#             f"Done. Wrote {totals['facts']} facts, {totals['opinions']} opinions, "
#             f"{totals['events']} events, {totals['relationships']} relationships "
#             f"({totals['chunks_failed']} chunk(s) failed extraction)."
#         )
#         return
#     elif args.command == "embed":
#         from app.vector.pipeline import embed_and_store
#         from app.vector.qdrant_client import VectorClient
#
#         print(f"Embedding {args.jsonl_path} into collection '{args.collection}' ...")
#         with VectorClient() as client:
#             count = embed_and_store(args.jsonl_path, args.collection, client)
#         print(f"Done. Wrote {count} vector(s) to collection '{args.collection}'.")
#         return
#     elif args.command == "search":
#         from app.vector.embedder import embed_text
#         from app.vector.qdrant_client import VectorClient
#
#         print(f"Searching '{args.collection}' for: {args.query!r}")
#         query_vector = embed_text(args.query)
#         with VectorClient() as client:
#             hits = client.search(args.collection, query_vector, top_k=args.top_k)
#
#         if not hits:
#             print("No results.")
#             return
#
#             for i, hit in enumerate(hits, 1):
#                 print(f"\n[{i}] score={hit['score']:.4f}  source={hit.get('source_path')}")
#                 text = hit.get("text", "")
#                 print(f"    {text[:200]}{'...' if len(text) > 200 else ''}")
#             return
#         elif args.command == "debug-prompt":
#             from app.graph.neo4j_client import GraphClient
#             from app.persona.prompt_builder import build_persona_prompt
#             from app.persona.retrieval import retrieve_context
#             from app.vector.qdrant_client import VectorClient
#
#             graph_client = None
#             vector_client = None
#             try:
#                 graph_client = GraphClient()
#                 graph_client.verify_connectivity()
#             except Exception as e:
#                 print(f"[warning] Neo4j not reachable, graph context will be empty: {e}")
#
#             try:
#                 vector_client = VectorClient()
#                 vector_client.verify_connectivity()
#             except Exception as e:
#                 print(f"[warning] Qdrant not reachable, vector context will be empty: {e}")
#
#             context = retrieve_context(
#                 query=args.query,
#                 persona_name=args.persona,
#                 collection_name=args.collection,
#                 graph_client=graph_client,
#                 vector_client=vector_client,
#                 top_k=args.top_k,
#             )
#             prompt = build_persona_prompt(args.persona, context)
#
#             print("=" * 70)
#             print("SYSTEM PROMPT THAT WOULD BE SENT TO THE MODEL:")
#             print("=" * 70)
#             print(prompt)
#             print("=" * 70)
#
#             if graph_client:
#                 graph_client.close()
#             if vector_client:
#                 vector_client.close()
#             return
#     else:
#         parser.print_help()
#         sys.exit(1)
#
#     if not chunks:
#         print("No chunks produced.")
#         return
#
#     write_jsonl(chunks, args.output)
#     print(f"Wrote {len(chunks)} chunk(s) to {args.output}")
#
#
# if __name__ == "__main__":
#     main()

"""
CLI for Persona Twin.

Usage:
    python -m app.cli file path/to/doc.pdf
    python -m app.cli file path/to/photo.jpg
    python -m app.cli url https://example.com/article
    python -m app.cli dir data/raw
    python -m app.cli graph --persona "Jane Doe" data/output/chunks.jsonl
    python -m app.cli embed --collection jane_doe data/output/chunks.jsonl
    python -m app.cli search --collection jane_doe "what does she think about the ocean?"
    python -m app.cli debug-prompt --persona "Jane Doe" --collection jane_doe "what do you think about the ocean?"

All commands append to data/output/chunks.jsonl by default.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.ingestion.pipeline import process_directory, process_file, process_url, write_jsonl

# Load variables from a .env file in the current directory (if present)
# before anything else reads os.environ. Real environment variables
# already set take precedence over .env values.
load_dotenv()

DEFAULT_OUTPUT = "data/output/chunks.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description="Persona Twin — data extraction tool")
    parser.add_argument(
        "--output", "-o", default=DEFAULT_OUTPUT, help=f"Output JSONL path (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=800, help="Target chunk size in characters (default: 800)"
    )
    parser.add_argument(
        "--overlap", type=int, default=100, help="Overlap between chunks in characters (default: 100)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    file_parser = subparsers.add_parser("file", help="Extract a single file (doc or image)")
    file_parser.add_argument("path", help="Path to the file")

    url_parser = subparsers.add_parser("url", help="Extract a single URL")
    url_parser.add_argument("url", help="URL to fetch")

    dir_parser = subparsers.add_parser("dir", help="Extract every supported file in a directory")
    dir_parser.add_argument("path", help="Directory to scan")

    graph_parser = subparsers.add_parser(
        "graph", help="Build the persona knowledge graph from a chunks.jsonl file"
    )
    graph_parser.add_argument("jsonl_path", help="Path to chunks.jsonl (from Step 1)")
    graph_parser.add_argument("--persona", required=True, help="Name of the persona these chunks belong to")
    graph_parser.add_argument(
        "--model", default=None,
        help="OpenRouter model slug to use for extraction (default: nvidia/nemotron-3.5-lightning:free, or $OPENROUTER_MODEL)"
    )

    embed_parser = subparsers.add_parser(
        "embed", help="Embed chunks.jsonl and store vectors in Qdrant"
    )
    embed_parser.add_argument("jsonl_path", help="Path to chunks.jsonl (from Step 1)")
    embed_parser.add_argument("--collection", required=True, help="Qdrant collection name to write into")

    search_parser = subparsers.add_parser(
        "search", help="Search a Qdrant collection for chunks similar to a query"
    )
    search_parser.add_argument("query", help="Search query text")
    search_parser.add_argument("--collection", required=True, help="Qdrant collection name to search")
    search_parser.add_argument("--top-k", type=int, default=5, help="Number of results to return (default: 5)")

    debug_parser = subparsers.add_parser(
        "debug-prompt",
        help="Build and print the persona system prompt for a question, without calling the LLM",
    )
    debug_parser.add_argument("query", help="The question to build a persona prompt for")
    debug_parser.add_argument("--persona", required=True, help="Persona name (must match what's in Neo4j)")
    debug_parser.add_argument("--collection", required=True, help="Qdrant collection name (must match what's in Qdrant)")
    debug_parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")

    args = parser.parse_args()

    if args.command == "file":
        print(f"Extracting {args.path} ...")
        chunks = process_file(args.path, chunk_size=args.chunk_size, overlap=args.overlap)
    elif args.command == "url":
        print(f"Fetching {args.url} ...")
        chunks = process_url(args.url, chunk_size=args.chunk_size, overlap=args.overlap)
    elif args.command == "dir":
        print(f"Scanning {args.path} ...")
        chunks = process_directory(args.path, chunk_size=args.chunk_size, overlap=args.overlap)
    elif args.command == "graph":
        from app.graph.neo4j_client import GraphClient
        from app.graph.pipeline import build_graph

        print(f"Building persona graph for '{args.persona}' from {args.jsonl_path} ...")
        with GraphClient() as client:
            totals = build_graph(args.jsonl_path, args.persona, client, model=args.model)
        print(
            f"Done. Wrote {totals['facts']} facts, {totals['opinions']} opinions, "
            f"{totals['events']} events, {totals['relationships']} relationships "
            f"({totals['chunks_failed']} chunk(s) failed extraction)."
        )
        return
    elif args.command == "embed":
        from app.vector.pipeline import embed_and_store
        from app.vector.qdrant_client import VectorClient

        print(f"Embedding {args.jsonl_path} into collection '{args.collection}' ...")
        with VectorClient() as client:
            count = embed_and_store(args.jsonl_path, args.collection, client)
        print(f"Done. Wrote {count} vector(s) to collection '{args.collection}'.")
        return
    elif args.command == "search":
        from app.vector.embedder import embed_text
        from app.vector.qdrant_client import VectorClient

        print(f"Searching '{args.collection}' for: {args.query!r}")
        query_vector = embed_text(args.query)
        with VectorClient() as client:
            hits = client.search(args.collection, query_vector, top_k=args.top_k)

        if not hits:
            print("No results.")
            return

        for i, hit in enumerate(hits, 1):
            print(f"\n[{i}] score={hit['score']:.4f}  source={hit.get('source_path')}")
            text = hit.get("text", "")
            print(f"    {text[:200]}{'...' if len(text) > 200 else ''}")
        return
    elif args.command == "debug-prompt":
        from app.graph.neo4j_client import GraphClient
        from app.persona.prompt_builder import build_persona_prompt
        from app.persona.retrieval import retrieve_context
        from app.vector.qdrant_client import VectorClient

        graph_client = None
        vector_client = None
        try:
            graph_client = GraphClient()
            graph_client.verify_connectivity()
        except Exception as e:
            print(f"[warning] Neo4j not reachable, graph context will be empty: {e}")
            graph_client = None

        try:
            vector_client = VectorClient()
            vector_client.verify_connectivity()
        except Exception as e:
            print(f"[warning] Qdrant not reachable, vector context will be empty: {e}")
            vector_client = None

        context = retrieve_context(
            query=args.query,
            persona_name=args.persona,
            collection_name=args.collection,
            graph_client=graph_client,
            vector_client=vector_client,
            top_k=args.top_k,
        )
        prompt = build_persona_prompt(args.persona, context)

        print("=" * 70)
        print("SYSTEM PROMPT THAT WOULD BE SENT TO THE MODEL:")
        print("=" * 70)
        print(prompt)
        print("=" * 70)

        if graph_client:
            graph_client.close()
        if vector_client:
            vector_client.close()
        return
    else:
        parser.print_help()
        sys.exit(1)

    if not chunks:
        print("No chunks produced.")
        return

    write_jsonl(chunks, args.output)
    print(f"Wrote {len(chunks)} chunk(s) to {args.output}")


if __name__ == "__main__":
    main()