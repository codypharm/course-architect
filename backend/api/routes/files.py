"""File upload endpoint.

Clients call POST /files before POST /courses to upload knowledge base documents.
The response returns S3 object keys that are passed to the course creation request.

Supported formats: .pdf, .txt, .md
"""
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.dependencies.auth import get_current_user_id
from api.schemas.files import FileUploadResponse
from storage.s3 import get_object_size, upload_fileobj
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["files"])

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


@router.post("/files", response_model=list[FileUploadResponse], status_code=201)
async def upload_files(
    files: list[UploadFile] = File(..., description="Knowledge base documents (.pdf, .txt, .md)"),
    _user_id: str = Depends(get_current_user_id),
) -> list[FileUploadResponse]:
    """Upload one or more knowledge base documents to S3.

    Files are stored at ``uploads/{batch_id}/{filename}`` in the configured
    S3 bucket.  The S3 key for each file is returned in the ``path`` field and
    must be passed in ``uploaded_file_paths`` when calling POST /courses.

    Rejects any file whose extension is not .pdf, .txt, or .md.
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one file is required.")

    # Validate extensions before touching S3
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported file type '{suffix}' for '{upload.filename}'. "
                       f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}",
            )

    batch_id = str(uuid4())
    results: list[FileUploadResponse] = []

    for upload in files:
        file_id  = str(uuid4())
        filename = upload.filename or file_id
        key      = f"uploads/{batch_id}/{filename}"
        content_type = upload.content_type or "application/octet-stream"

        # Reset stream position in case Starlette already read headers
        await upload.seek(0)
        upload_fileobj(upload.file, key, content_type=content_type)

        # Starlette sets .size after the file is fully read; fall back to HeadObject
        size = upload.size if upload.size is not None else get_object_size(key)

        logger.info("Uploaded file to S3 — key=%s size=%d", key, size)
        results.append(FileUploadResponse(
            file_id=file_id,
            filename=filename,
            path=key,
            size_bytes=size,
        ))

    return results
