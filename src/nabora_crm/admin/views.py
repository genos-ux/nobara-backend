from sqladmin import Admin, ModelView

from nabora_crm.admin.auth import admin_auth
from nabora_crm.db.session import engine
from nabora_crm.modules.crm.models import Activity, Person
from nabora_crm.modules.roles.models import Permission, Role
from nabora_crm.modules.users.models import User


class UserAdmin(ModelView, model=User):
    category = "Users"
    column_list = [User.id, User.email, User.role, User.is_active]


class RoleAdmin(ModelView, model=Role):
    category = "Access Control"
    column_list = [Role.id, Role.name, Role.description, Role.is_system, Role.permissions]


class PermissionAdmin(ModelView, model=Permission):
    category = "Access Control"
    column_list = [Permission.id, Permission.name, Permission.roles]


class PersonAdmin(ModelView, model=Person):
    category = "CRM"
    column_list = [Person.id, Person.name, Person.email, Person.stage, Person.subscribed]


class ActivityAdmin(ModelView, model=Activity):
    category = "CRM"
    column_list = [Activity.id, Activity.person_id, Activity.staff_name, Activity.activity_type, Activity.created_at]


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
