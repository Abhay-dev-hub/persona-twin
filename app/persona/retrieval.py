"""
Combines the two knowledge sources built in Steps 2 and 4 into a
single retrieval call: for a given user question, pull the most
relevant source chunks (vector search) and the persona's full
fact/opinion/event/relationship profile (graph), so Step 5's prompt
builder has everything it needs.

Each source is fetched independently and failures are isolated —
if Qdrant is unreachable but Neo4j works (or vice versa), retrieval
still returns whatever succeeded rather than failing the whole chat
turn. This keeps the persona usable even if one backing store is
temporarily down.
"""

import logging

from app.graph.neo4j_client import GraphClient
from app.vector.embedder import embed_text
from app.vector.qdrant_client import VectorClient

logger = logging.getLogger(__name__)

_EMPTY_PROFILE = {"facts": [], "opinions": [], "events": [], "relationships": []}


def retrieve_context(
    query: str,
    persona_name: str,
    collection_name: str,
    graph_client: GraphClient | None,
    vector_client: VectorClient | None,
    top_k: int = 5,
) -> dict:
    """
    Returns:
        {
            "chunks": [...],    # top_k relevant source chunks from Qdrant, each with a "score"
            "profile": {...},   # facts/opinions/events/relationships from Neo4j
        }

    `graph_client`/`vector_client` may be None (e.g. not configured),
    in which case that source is simply skipped and returns empty.
    """
    chunks: list[dict] = []
    profile = dict(_EMPTY_PROFILE)

    if vector_client is not None:
        try:
            query_vector = embed_text(query)
            chunks = vector_client.search(collection_name, query_vector, top_k=top_k)
        except Exception:
            logger.warning("Vector retrieval failed for query %r", query, exc_info=True)

    if graph_client is not None:
        try:
            profile = graph_client.get_persona_profile(persona_name)
        except Exception:
            logger.warning("Graph retrieval failed for persona %r", persona_name, exc_info=True)

    return {"chunks": chunks, "profile": profile}
