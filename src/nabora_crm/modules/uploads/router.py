from fastapi import APIRouter, Depends, File, UploadFile

from nabora_crm.modules.auth.dependencies import get_current_user
from nabora_crm.modules.uploads.schemas import UploadResponse
from nabora_crm.modules.uploads.service import upload_file
from nabora_crm.modules.users.models import User

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse, status_code=201)
def upload(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
) -> UploadResponse:
    """Upload a file to Cloudinary and return its public URL.

    Accepts images, videos, and raw files (PDF, docs, etc.) via
    ``multipart/form-data``. Requires authentication.
    """
    data = file.file.read()
    result = upload_file(
        data=data,
        filename=file.filename or "upload",
        content_type=file.content_type,
    )
    return UploadResponse(
        url=result["url"],
        secure_url=result["secure_url"],
        public_id=result["public_id"],
        resource_type=result["resource_type"],
        format=result.get("format"),
        bytes=result.get("bytes"),
    )
