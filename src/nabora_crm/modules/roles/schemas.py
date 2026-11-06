import uuid

from pydantic import BaseModel


class PermissionOut(BaseModel):
    id: uuid.UUID
    name: str


class RoleBase(BaseModel):
    name: str
    description: str | None = None


class RoleCreate(RoleBase):
    permission_names: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_names: list[str] | None = None


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[PermissionOut]
