import uuid

from sqladmin import Admin, ModelView
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from nabora_crm.admin.auth import admin_auth
from nabora_crm.db.session import SessionLocal, engine
from nabora_crm.modules.crm.models import Activity, Person
from nabora_crm.modules.notifications.models import NotificationType
from nabora_crm.modules.notifications.service import (
    ensure_welcome_notification,
    notify_role_members,
    notify_user,
)
from nabora_crm.modules.roles.models import Permission, Role
from nabora_crm.modules.roles.repository import get_role_by_id
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import get_user_by_id


class UserAdmin(ModelView, model=User):
    category = "Users"
    column_list = [User.id, User.email, User.role, User.is_active, User.is_email_pending]

    async def after_model_change(
        self,
        data: dict,
        model: User,
        is_created: bool,
        request: Request,
    ) -> None:
        """Notify users edited through the SQLAdmin dashboard."""
        await run_in_threadpool(self._notify_user_change, model.id, is_created)

    @staticmethod
    def _notify_user_change(user_id: uuid.UUID, is_created: bool) -> None:
        db = SessionLocal()
        try:
            user = get_user_by_id(db, user_id)
            if user is None:
                return
            if is_created:
                ensure_welcome_notification(db, user)
            else:
                notify_user(
                    db,
                    user.id,
                    notification_type=NotificationType.USER_UPDATED,
                    title="Account updated",
                    message="Your account was updated by an administrator.",
                )
        finally:
            db.close()


class RoleAdmin(ModelView, model=Role):
    category = "Access Control"
    column_list = [Role.id, Role.name, Role.description, Role.is_system, Role.permissions]

    async def after_model_change(
        self,
        data: dict,
        model: Role,
        is_created: bool,
        request: Request,
    ) -> None:
        """Notify role members when a role is edited in SQLAdmin."""
        if not is_created:
            await run_in_threadpool(self._notify_role_change, model.id)

    @staticmethod
    def _notify_role_change(role_id: uuid.UUID) -> None:
        db = SessionLocal()
        try:
            role = get_role_by_id(db, role_id)
            if role is None:
                return
            notify_role_members(db, role.id, role.name)
        finally:
            db.close()


class PermissionAdmin(ModelView, model=Permission):
    category = "Access Control"
    column_list = [Permission.id, Permission.name, Permission.roles]


class PersonAdmin(ModelView, model=Person):
    category = "CRM"
    column_list = [Person.id, Person.name, Person.email, Person.stage, Person.subscribed]


class ActivityAdmin(ModelView, model=Activity):
    category = "CRM"
    column_list = [
        Activity.id,
        Activity.person_id,
        Activity.staff_name,
        Activity.activity_type,
        Activity.subject,
        Activity.created_at,
    ]


def create_admin(app, templates_dir: str) -> Admin:
    """Create and configure the SQLAdmin instance, registering all views."""
    admin = Admin(
        app=app,
        engine=engine,
        base_url="/admin",
        title="Nabora CRM Admin",
        authentication_backend=admin_auth,
        templates_dir=templates_dir,
    )
    admin.add_view(UserAdmin)
    admin.add_view(RoleAdmin)
    admin.add_view(PermissionAdmin)
    admin.add_view(PersonAdmin)
    admin.add_view(ActivityAdmin)
    return admin
