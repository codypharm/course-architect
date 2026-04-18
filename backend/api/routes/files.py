"""File upload endpoint.

Clients call POST /files before POST /courses to upload knowledge base documents.
The response returns absolute file paths that are passed to the course creation request.

Supported formats: .pdf, .txt, .md
"""
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas.files import FileUploadResponse
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["files"])

UPLOAD_DIR = Path("uploads")
ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


@router.post("/files", response_model=list[FileUploadResponse], status_code=201)
async def upload_files(
    files: list[UploadFile] = File(..., description="Knowledge base documents (.pdf, .txt, .md)"),
) -> list[FileUploadResponse]:
    """Upload one or more knowledge base documents.

    Files are saved to uploads/{batch_id}/ on disk. The absolute path for each
    file is returned and must be passed in `uploaded_file_paths` when calling
    POST /courses.

    Rejects any file whose extension is not .pdf, .txt, or .md.
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one file is required.")

    # Validate extensions before touching disk
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported file type '{suffix}' for '{upload.filename}'. "
                       f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}",
            )

    batch_id = str(uuid4())
    batch_dir = UPLOAD_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    results: list[FileUploadResponse] = []
    for upload in files:
        file_id = str(uuid4())
        filename = upload.filename or file_id
        dest = batch_dir / filename

        with dest.open("wb") as fh:
            shutil.copyfileobj(upload.file, fh)

        size = dest.stat().st_size
        abs_path = str(dest.resolve())

        logger.info("Uploaded file — batch=%s file=%s size=%d", batch_id, filename, size)
        results.append(FileUploadResponse(
            file_id=file_id,
            filename=filename,
            path=abs_path,
            size_bytes=size,
        ))

    return results
