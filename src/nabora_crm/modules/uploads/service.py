import logging

import cloudinary
import cloudinary.uploader

from nabora_crm.core.config import settings
from nabora_crm.core.exceptions import UploadError

logger = logging.getLogger("nabora_crm")


def _ensure_configured() -> None:
    """Validate Cloudinary settings and configure the SDK."""
    if not (
        settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    ):
        raise UploadError(
            "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET in your environment."
        )

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


def upload_file(
    *,
    data: bytes,
    filename: str,
    content_type: str | None = None,
    folder: str | None = None,
) -> dict:
    """Upload raw file bytes to Cloudinary and return the upload result.

    Raises:
        UploadError: If storage is not configured, the file is empty or too
                     large, or Cloudinary rejects the upload.
    """
    _ensure_configured()

    if not data:
        raise UploadError("Uploaded file is empty")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadError(
            f"File exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB"
        )

    try:
        result = cloudinary.uploader.upload(
            data,
            folder=folder or settings.CLOUDINARY_FOLDER,
            resource_type="auto",
            use_filename=True,
            unique_filename=True,
        )
    except Exception as exc:
        logger.error("Cloudinary upload failed for %s: %s", filename, exc)
        raise UploadError(f"Failed to upload file: {exc}") from exc

    logger.info("Uploaded %s to Cloudinary as %s", filename, result.get("public_id"))
    return result
