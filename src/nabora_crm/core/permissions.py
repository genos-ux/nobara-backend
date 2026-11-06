"""Canonical permission definitions for the RBAC system.

Each constant is a permission string used in the database and access checks.
New permissions can be added here as the application grows. When adding a new
permission, also add it to the DEFAULT_ROLE_PERMISSIONS mapping in db/init_db.py
for any roles that should have it by default.
"""

# User management
USERS_READ = "users:read"
USERS_WRITE = "users:write"
USERS_DELETE = "users:delete"

# CRM (persons, activities)
CRM_READ = "crm:read"
CRM_WRITE = "crm:write"
CRM_DELETE = "crm:delete"

# Role management
ROLES_READ = "roles:read"
ROLES_WRITE = "roles:write"
ROLES_DELETE = "roles:delete"

# Admin panel access
ADMIN_ACCESS = "admin:access"

ALL_PERMISSIONS: frozenset[str] = frozenset(
    {
        USERS_READ,
        USERS_WRITE,
        USERS_DELETE,
        CRM_READ,
        CRM_WRITE,
        CRM_DELETE,
        ROLES_READ,
        ROLES_WRITE,
        ROLES_DELETE,
        ADMIN_ACCESS,
    }
)
