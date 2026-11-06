from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from nabora_crm.core.config import settings
from nabora_crm.core.security import verify_password
from nabora_crm.db.session import SessionLocal
from nabora_crm.modules.users.models import Role
from nabora_crm.modules.users.repository import get_user_by_email


class AdminAuth(AuthenticationBackend):
    """Secure sqladmin authentication backend.

    Only active admin users can access the admin panel.
    """

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("email") or form.get("username")
        password = form.get("password")

        if not email or not password:
            return False

        db = SessionLocal()
        try:
            user = get_user_by_email(db, email)
            if (
                not user
                or not verify_password(password, user.hashed_password)
                or user.role != Role.admin
                or not user.is_active
            ):
                return False

            request.session.update({"admin_user": user.email})
            return True
        finally:
            db.close()

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return False

        db = SessionLocal()
        try:
            user = get_user_by_email(db, admin_user)
            if not user or not user.is_active or user.role != Role.admin:
                request.session.clear()
                return False
            return True
        finally:
            db.close()


admin_auth = AdminAuth(secret_key=settings.SECRET_KEY)
