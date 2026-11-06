import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from nabora_crm.config import settings
from nabora_crm.database import SessionLocal
from nabora_crm.models import Role, User
from nabora_crm.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger("nabora_crm")

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the JWT token and return the current authenticated user."""
    token = credentials.credentials
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if email is None or token_type != "access":
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exc
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user has the admin role."""
    if current_user.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool


@router.post("/login")
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Authenticate a user and return access and refresh tokens."""
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    token_data = {"sub": user.email, "role": user.role.value}

    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
    }


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
) -> dict[str, str]:
    """Logout the current user. Client should discard both tokens."""
    return {
        "message": "Successfully logged out",
    }


@router.get("/me", response_model=UserProfile)
def get_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfile:
    """Return the current authenticated user's profile."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed_users() -> None:
    """Create the admin account if it doesn't already exist."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not existing:
            user = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role=Role.admin,
                is_active=True,
            )
            db.add(user)
            db.commit()
            logger.info("Seeded admin user: %s", user.email)
        else:
            logger.info("Admin user already exists, skipping seed.")
    except Exception as exc:
        db.rollback()
        logger.error("Error seeding admin user: %s", exc)
        raise
    finally:
        db.close()
