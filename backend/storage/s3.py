"""S3 storage helpers for uploaded knowledge base files.

All S3 access in this project goes through this module — nothing else imports
boto3 directly.  Objects are stored under the key prefix ``uploads/`` inside
the bucket configured by S3_UPLOADS_BUCKET.

For local development, set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your
.env file.  On ECS Fargate, the task execution role provides credentials
automatically — no keys needed in the environment.
"""
import io
import os

import boto3

# Lazy singleton so the client is created after environment variables are loaded.
_client = None


def _s3():
    """Return (and lazily create) the shared boto3 S3 client."""
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return _client


# Bucket name — must be set before any upload/download is attempted.
BUCKET: str = os.environ.get("S3_UPLOADS_BUCKET", "")


def upload_fileobj(fileobj, key: str, content_type: str = "application/octet-stream") -> str:
    """Upload a file-like object to S3 and return the object key.

    Args:
        fileobj: Any readable file-like object (e.g. SpooledTemporaryFile from FastAPI).
        key: S3 object key (e.g. ``uploads/{batch_id}/{filename}``).
        content_type: MIME type stored with the object.

    Returns:
        The key that was stored.
    """
    _s3().upload_fileobj(
        fileobj,
        BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def download_bytes(key: str) -> bytes:
    """Download an S3 object and return its raw bytes.

    Args:
        key: S3 object key.

    Returns:
        Raw file bytes.
    """
    buf = io.BytesIO()
    _s3().download_fileobj(BUCKET, key, buf)
    return buf.getvalue()


def get_object_size(key: str) -> int:
    """Return the size in bytes of an S3 object via a HEAD request.

    Args:
        key: S3 object key.

    Returns:
        Content-Length in bytes.
    """
    response = _s3().head_object(Bucket=BUCKET, Key=key)
    return response["ContentLength"]


def delete_keys(keys: list[str]) -> None:
    """Batch-delete S3 objects.  No-op on empty list.

    Args:
        keys: List of S3 object keys to delete.
    """
    if not keys:
        return
    _s3().delete_objects(
        Bucket=BUCKET,
        Delete={"Objects": [{"Key": k} for k in keys]},
    )
