import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


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
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the JWT token and return the current authenticated user."""
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
        "refresh_token": create_refresh_token(token_data)
    }


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

DEMO_USERS = [
    {"email": "admin@nabora.example", "role": Role.admin, "is_active": True},
    {"email": "nutritionist@nabora.example", "role": Role.nutritionist, "is_active": True},
    {"email": "trainer@nabora.example", "role": Role.fitness, "is_active": True},
    {"email": "writer@nabora.example", "role": Role.nutritionist, "is_active": False},
]

DEMO_PASSWORD = "demo1234"


def seed_users() -> None:
    """Create demo accounts if they don't already exist."""
    db = SessionLocal()
    try:
        for user_data in DEMO_USERS:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if existing:
                continue
            user = User(
                email=user_data["email"],
                hashed_password=hash_password(DEMO_PASSWORD),
                role=user_data["role"],
                is_active=user_data["is_active"],
            )
            db.add(user)
            logger.info("Seeded user: %s (%s)", user.email, user.role.value)
        db.commit()
        logger.info("User seeding complete.")
    except Exception as exc:
        db.rollback()
        logger.error("Error seeding users: %s", exc)
        raise
    finally:
        db.close()
