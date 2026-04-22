"""AWS S3 Vectors helper for the RAG pipeline.

Provides three public functions used by rag/ingest.py and rag/retrieval.py:
  put_vectors(thread_id, chunks)        — store embeddings under a thread namespace
  query_vectors(thread_id, embedding, top_k)  — similarity search scoped to a thread
  delete_thread_vectors(thread_id)      — clean up all vectors for a finished run

Thread isolation is achieved by prefixing every vector key with "{thread_id}#",
so cleanup can be done by key-prefix match without a metadata scan.

The index is created lazily on first put_vectors call (idempotent).
"""
import os
import uuid

import boto3
from botocore.exceptions import ClientError

from utils.logging import get_logger

logger = get_logger(__name__)

VECTOR_BUCKET: str = os.environ.get("S3_VECTORS_BUCKET", "")
INDEX_NAME: str    = os.environ.get("S3_VECTORS_INDEX", "course-chunks")
EMBEDDING_DIM: int = 1536   # text-embedding-3-small output dimension
DISTANCE_METRIC    = "cosine"

_client = None
_index_ready: bool = False   # ensures ensure_index() runs once per process


def _s3v():
    """Return a lazy-initialised boto3 S3 Vectors client."""
    global _client
    if _client is None:
        _client = boto3.client(
            "s3vectors",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return _client


def _check_bucket() -> bool:
    """Return True if VECTOR_BUCKET is configured; log a warning and return False otherwise."""
    if not VECTOR_BUCKET:
        logger.warning(
            "S3_VECTORS_BUCKET is not set — S3 Vectors operations are no-ops. "
            "Set S3_VECTORS_BUCKET and S3_VECTORS_INDEX in your environment."
        )
        return False
    return True


def ensure_index() -> None:
    """Create the vector index if it does not already exist (idempotent).

    Safe to call multiple times — ConflictException (index already exists)
    is silently ignored. Other errors are logged but NOT re-raised so a
    transient S3 Vectors outage does not block app startup.
    """
    if not _check_bucket():
        return
    try:
        _s3v().create_index(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDEX_NAME,
            dataType="float32",
            dimension=EMBEDDING_DIM,
            distanceMetric=DISTANCE_METRIC,
        )
        logger.info(
            "S3 Vectors index created — bucket=%s index=%s dim=%d",
            VECTOR_BUCKET, INDEX_NAME, EMBEDDING_DIM,
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConflictException":
            logger.debug("S3 Vectors index already exists — bucket=%s index=%s", VECTOR_BUCKET, INDEX_NAME)
        else:
            # Non-fatal: log and continue; index is also created lazily on first put_vectors call.
            logger.error("Failed to create S3 Vectors index (ClientError) — RAG writes will retry lazily", exc_info=True)
    except Exception:
        # Catches UnknownServiceError if boto3 doesn't recognise "s3vectors" in this region,
        # or any other unexpected error — must not crash the app startup.
        logger.error("Failed to create S3 Vectors index (unexpected) — RAG writes will retry lazily", exc_info=True)


def _ensure_index_once() -> None:
    """Call ensure_index() at most once per process to avoid redundant API calls."""
    global _index_ready
    if not _index_ready:
        ensure_index()
        _index_ready = True


def put_vectors(thread_id: str, chunks: list[dict]) -> int:
    """Upsert embedding vectors for a pipeline run into the shared index.

    Args:
        thread_id: Pipeline run identifier. Used as a key prefix for isolation.
        chunks: List of dicts with keys:
            id (str)           — unique chunk ID within this run
            embedding (list)   — float embedding vector
            text (str)         — original chunk text (stored as filterable metadata)
            source (str)       — source filename or URL
            chunk_index (int)  — position of this chunk in its source document

    Returns:
        Number of vectors stored.
    """
    if not _check_bucket():
        return 0
    _ensure_index_once()

    if not chunks:
        return 0

    vectors = [
        {
            "key": f"{thread_id}#{c['id']}",
            "data": {"float32": [float(x) for x in c["embedding"]]},
            "metadata": {
                "thread_id": thread_id,
                "text": c["text"],
                "source": c["source"],
                "chunk_index": c["chunk_index"],
            },
        }
        for c in chunks
    ]

    # S3 Vectors does not document a hard per-request limit; batch at 500 to be safe
    batch_size = 500
    for i in range(0, len(vectors), batch_size):
        _s3v().put_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDEX_NAME,
            vectors=vectors[i : i + batch_size],
        )

    logger.debug("put_vectors — thread_id=%s count=%d", thread_id, len(vectors))
    return len(vectors)


def query_vectors(
    thread_id: str,
    query_embedding: list[float],
    top_k: int = 10,
) -> list[dict]:
    """Similarity search scoped to a single pipeline run.

    Args:
        thread_id: Limits results to vectors ingested for this run.
        query_embedding: Embedded query vector.
        top_k: Maximum number of results to return.

    Returns:
        List of result dicts, each containing at least 'key' and 'metadata'.
        Empty list if the bucket is unconfigured or no results are found.
    """
    if not _check_bucket():
        return []

    try:
        resp = _s3v().query_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDEX_NAME,
            queryVector={"float32": [float(x) for x in query_embedding]},
            topK=top_k,
            filter={"thread_id": thread_id},
            returnMetadata=True,
        )
        return resp.get("vectors", [])
    except ClientError:
        logger.error(
            "query_vectors failed — thread_id=%s", thread_id, exc_info=True
        )
        return []


def delete_thread_vectors(thread_id: str) -> None:
    """Delete all vectors for a pipeline run (called at terminal pipeline state).

    Uses key-prefix matching (all keys are "{thread_id}#...") to avoid a full
    metadata scan — list_vectors does not support metadata filtering, so we
    list all keys and filter by prefix client-side.
    """
    if not _check_bucket():
        return

    prefix = f"{thread_id}#"
    keys: list[str] = []
    kwargs: dict = {
        "vectorBucketName": VECTOR_BUCKET,
        "indexName": INDEX_NAME,
    }

    try:
        while True:
            resp = _s3v().list_vectors(**kwargs)
            keys.extend(
                v["key"] for v in resp.get("vectors", [])
                if v["key"].startswith(prefix)
            )
            next_token = resp.get("nextToken")
            if not next_token:
                break
            kwargs["nextToken"] = next_token
    except ClientError:
        logger.error(
            "list_vectors failed during cleanup — thread_id=%s", thread_id, exc_info=True
        )
        return

    if not keys:
        logger.debug("delete_thread_vectors — no vectors found for thread_id=%s", thread_id)
        return

    try:
        for i in range(0, len(keys), 500):
            _s3v().delete_vectors(
                vectorBucketName=VECTOR_BUCKET,
                indexName=INDEX_NAME,
                keys=keys[i : i + 500],
            )
        logger.info(
            "Deleted %d S3 Vectors for thread_id=%s", len(keys), thread_id
        )
    except ClientError:
        logger.error(
            "delete_vectors failed — thread_id=%s", thread_id, exc_info=True
        )
