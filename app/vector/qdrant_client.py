# """
# Thin wrapper around the Qdrant client for storing and searching
# persona chunk embeddings.
#
# Expects these environment variables:
#     QDRANT_URL       (default: http://localhost:6333)
#     QDRANT_API_KEY   (only needed for Qdrant Cloud; omit for local Docker)
# """
#
# import os
# import uuid
#
#
# class VectorClient:
#     def __init__(self, url: str | None = None, api_key: str | None = None):
#         from qdrant_client import QdrantClient
#
#         self.url = url or os.environ.get("QDRANT_URL", "http://localhost:6333")
#         self.api_key = api_key or os.environ.get("QDRANT_API_KEY")  # optional (local Qdrant doesn't need one)
#
#         self._client = QdrantClient(url=self.url, api_key=self.api_key)
#
#     def close(self) -> None:
#         self._client.close()
#
#     def __enter__(self) -> "VectorClient":
#         return self
#
#     def __exit__(self, *exc_info) -> None:
#         self.close()
#
#     def verify_connectivity(self) -> None:
#         """
#         Unlike Neo4j's driver, qdrant-client connects lazily — construction
#         succeeds even with no server listening. This forces an actual
#         round-trip so callers can detect a dead connection at startup
#         instead of on the first real request.
#         """
#         self._client.get_collections()
#
#     def ensure_collection(self, collection_name: str, vector_size: int) -> None:
#         from qdrant_client.models import Distance, VectorParams
#
#         if not self._client.collection_exists(collection_name):
#             self._client.create_collection(
#                 collection_name=collection_name,
#                 vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
#             )
#
#     def upsert_chunks(self, collection_name: str, chunks: list[dict], vectors: list[list[float]]) -> None:
#         """
#         `chunks` are the same dicts written by Step 1 (chunk_text/index/
#         source_id/source_type/source_path/metadata) — used as the point
#         payload so search results carry provenance back to the original
#         source. `vectors` must be the same length and order as `chunks`.
#         """
#         from qdrant_client.models import PointStruct
#
#         if len(chunks) != len(vectors):
#             raise ValueError(f"chunks ({len(chunks)}) and vectors ({len(vectors)}) length mismatch")
#
#         points = [
#             PointStruct(id=str(uuid.uuid4()), vector=vector, payload=chunk)
#             for chunk, vector in zip(chunks, vectors)
#         ]
#         self._client.upsert(collection_name=collection_name, points=points)
#
#     def search(self, collection_name: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
#         """Returns the top_k most similar chunks, each with its similarity score attached."""
#         results = self._client.query_points(
#             collection_name=collection_name, query=query_vector, limit=top_k
#         ).points
#
#         hits = []
#         for point in results:
#             hit = dict(point.payload)
#             hit["score"] = point.score
#             hits.append(hit)
#         return hits
#
#     def delete_collection(self, collection_name: str) -> None:
#         if self._client.collection_exists(collection_name):
#             self._client.delete_collection(collection_name=collection_name)

"""
Thin wrapper around the Qdrant client for storing and searching
persona chunk embeddings.

Expects these environment variables:
    QDRANT_URL       (default: http://localhost:6333)
    QDRANT_API_KEY   (only needed for Qdrant Cloud; omit for local Docker)
"""

import os
import uuid


class VectorClient:
    def __init__(self, url: str | None = None, api_key: str | None = None, timeout: float = 60.0):
        from qdrant_client import QdrantClient

        self.url = url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or os.environ.get("QDRANT_API_KEY")  # optional (local Qdrant doesn't need one)
        self.timeout = timeout

        # timeout=60.0 prevents httpx.ReadTimeout on larger embedding uploads
        self._client = QdrantClient(url=self.url, api_key=self.api_key, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VectorClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def verify_connectivity(self) -> None:
        """
        Unlike Neo4j's driver, qdrant-client connects lazily — construction
        succeeds even with no server listening. This forces an actual
        round-trip so callers can detect a dead connection at startup
        instead of on the first real request.
        """
        self._client.get_collections()

    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        if not self._client.collection_exists(collection_name):
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def upsert_chunks(
        self,
        collection_name: str,
        chunks: list[dict],
        vectors: list[list[float]],
        batch_size: int = 64,
    ) -> None:
        """
        `chunks` are the same dicts written by Step 1 (chunk_text/index/
        source_id/source_type/source_path/metadata) — used as the point
        payload so search results carry provenance back to the original
        source. `vectors` must be the same length and order as `chunks`.
        """
        from qdrant_client.models import PointStruct

        if len(chunks) != len(vectors):
            raise ValueError(f"chunks ({len(chunks)}) and vectors ({len(vectors)}) length mismatch")

        points = [
            PointStruct(id=str(uuid.uuid4()), vector=vector, payload=chunk)
            for chunk, vector in zip(chunks, vectors)
        ]

        # Chunk the upsert calls into smaller batches to prevent network drops
        for i in range(0, len(points), batch_size):
            sub_batch = points[i : i + batch_size]
            self._client.upsert(collection_name=collection_name, points=sub_batch)

    def search(self, collection_name: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
        """Returns the top_k most similar chunks, each with its similarity score attached."""
        results = self._client.query_points(
            collection_name=collection_name, query=query_vector, limit=top_k
        ).points

        hits = []
        for point in results:
            hit = dict(point.payload)
            hit["score"] = point.score
            hits.append(hit)
        return hits

    def delete_collection(self, collection_name: str) -> None:
        if self._client.collection_exists(collection_name):
            self._client.delete_collection(collection_name=collection_name)