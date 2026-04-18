"""Response schema for the file upload endpoint."""
from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    """Metadata for a single successfully uploaded file.

    The `path` field is the absolute path on disk.
    Pass it in `uploaded_file_paths` when calling POST /courses.
    """
    file_id: str     # UUID identifying this upload
    filename: str
    path: str        # absolute path — reference this in POST /courses
    size_bytes: int
