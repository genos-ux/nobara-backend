from pydantic import BaseModel


class UploadResponse(BaseModel):
    url: str
    secure_url: str
    public_id: str
    resource_type: str
    format: str | None = None
    bytes: int | None = None
