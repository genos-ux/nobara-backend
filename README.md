# Nabora CRM API

A modular FastAPI backend for nutritionist/fitness practice management, featuring JWT authentication, an SQLAdmin dashboard, and PostgreSQL persistence. Deployed on Render.

## Project Structure

```
nobara-backend/
├── src/nabora_crm/
│   ├── main.py              # App factory: lifespan, middleware, router registration, admin setup
│   │
│   ├── core/                # Cross-cutting concerns
│   │   ├── config.py        # Pydantic Settings (environment variables)
│   │   ├── security.py      # Password hashing (bcrypt) + JWT create/decode
│   │   ├── exceptions.py     # Domain exception hierarchy
│   │   ├── permissions.py    # RBAC permission constants
│   │   └── logging.py       # Centralized logging setup
│   │
│   ├── db/                  # Database layer
│   │   ├── base.py          # SQLAlchemy DeclarativeBase
│   │   ├── session.py       # Engine, SessionLocal, get_db() dependency
│   │   └── init_db.py       # Table creation + RBAC seeding + admin user seeding
│   │
│   ├── api/                 # API versioning
│   │   └── v1/
│   │       └── router.py    # Aggregates all v1 module routers
│   │
│   ├── modules/             # Feature modules (domain-driven)
│   │   ├── auth/             # Authentication feature
│   │   │   ├── router.py          # 4 endpoints: login, logout, refresh, me
│   │   │   ├── schemas.py         # Pydantic request/response models
│   │   │   ├── service.py          # Business logic (authenticate, token creation)
│   │   │   └── dependencies.py    # get_current_user, require_permission()
│   │   │
│   │   ├── users/           # User domain
│   │   │   ├── models.py          # User ORM model (role_id FK)
│   │   │   └── repository.py      # Database queries (get_user_by_email, create_user)
│   │   │
│   │   ├── roles/           # RBAC domain
│   │   │   ├── models.py          # Role, Permission, RolePermission junction
│   │   │   ├── schemas.py         # Pydantic schemas for role/permission CRUD
│   │   │   ├── repository.py      # CRUD for roles and permissions
│   │   │   ├── service.py         # Business logic (create, update, delete roles)
│   │   │   └── router.py          # Admin-only endpoints to manage roles/permissions
│   │   │
│   │   └── crm/             # CRM domain
│   │       └── models.py          # Person, Activity ORM models, Stage enum
│   │
│   └── admin/               # SQLAdmin dashboard
│       ├── auth.py          # AdminAuth authentication backend
│       ├── views.py         # ModelView classes + create_admin() factory
│       └── templates/       # Custom admin login template
│
├── tests/                   # Test suite
│   ├── conftest.py          # TestClient fixture, SQLite test DB
│   └── test_health.py       # Endpoint, OpenAPI, import, and model registration tests
│
├── migrations/              # Alembic migrations
│   ├── env.py               # Migration environment (reads config from settings)
│   ├── script.py.mako       # Migration template
│   └── versions/            # Generated migration scripts
│
├── alembic.ini              # Alembic configuration
├── .env.example             # Environment variable template
├── pyproject.toml           # Project config + dependencies (uv)
└── uv.lock                  # Locked dependency versions
```

## Architecture

### Layers

- **Routers** — Handle HTTP requests/responses, delegate to services. No business logic.
- **Services** — Contain business logic, coordinate repositories. No HTTP-specific concerns.
- **Repositories** — Handle database queries. Shared across services to avoid duplication.
- **Schemas** — Pydantic models for request validation and response serialization.
- **Models** — SQLAlchemy ORM models, separate from schemas.
- **Core** — Centralized config, security, and logging.
- **DB** — Engine, session lifecycle, and initialization.

### Dependency Flow

```
Router → Service → Repository → Models
                                → DB Session
Dependencies (get_current_user) → Security → Config
Admin → Auth Backend → Users Repository
```

No circular dependencies exist. Each layer depends only on layers below it.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Welcome message |
| GET | `/health` | None | Health check |
| POST | `/v1/auth/login` | None | Authenticate, return access + refresh tokens |
| POST | `/v1/auth/logout` | Bearer | Logout (client discards tokens) |
| POST | `/v1/auth/refresh` | Refresh token | Issue new access token |
| GET | `/v1/auth/me` | Bearer | Current user profile (role + permissions) |
| GET | `/v1/roles` | `roles:read` | List all roles with permissions |
| POST | `/v1/roles` | `roles:write` | Create a new role |
| PUT | `/v1/roles/{id}` | `roles:write` | Update a role (name, description, permissions) |
| DELETE | `/v1/roles/{id}` | `roles:delete` | Delete a non-system role |
| GET | `/v1/roles/permissions` | `roles:read` | List all available permissions |
| * | `/admin/*` | Session (admin) | SQLAdmin dashboard |

Interactive API docs available at `/docs` (Swagger) and `/redoc` (ReDoc) when running.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT access token signing key |
| `REFRESH_SECRET_KEY` | JWT refresh token signing key |
| `ALGORITHM` | JWT algorithm (default: HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL |
| `ADMIN_EMAIL` | Initial admin account email |
| `ADMIN_PASSWORD` | Initial admin account password |
| `CORS_ORIGINS` | Comma-separated allowed origins |

## Setup

### Prerequisites

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL database

### Install

```bash
uv sync
```

### Run locally

```bash
uv run uvicorn nabora_crm.main:app --reload
```

The app starts on `http://localhost:8000`.

### Run tests

```bash
uv run pytest
```

Tests use an in-process SQLite database — no PostgreSQL required.

### Database migrations

Migrations are managed with Alembic. The initial migration captures the current schema (users, persons, activities).

**Apply migrations** (run before starting the app in production):
```bash
uv run alembic upgrade head
```

**Create a new migration** after model changes:
```bash
uv run alembic revision --autogenerate -m "description of change"
```

**Rollback one migration:**
```bash
uv run alembic downgrade -1
```

> **Note:** The application lifespan still calls `Base.metadata.create_all()` as a safety net for fresh databases. Once you run `alembic upgrade head` in production, the tables already exist and `create_all` is a no-op. You can optionally remove the `create_all` call from `db/init_db.py` once all environments are migrated.

## Render Deployment

The application is deployed on Render via Git auto-deploy from the `main` branch.

**Build command:**
```
uv sync
```

**Start command (configured in Render dashboard):**
```
uv run alembic upgrade head && uvicorn nabora_crm.main:app --host 0.0.0.0 --port $PORT
```

The start command now runs migrations before starting the server. All environment variables and database connections remain compatible.

> **Note:** API endpoints are now prefixed with `/v1` (e.g. `/v1/auth/login` instead of `/auth/login`). The root (`/`), health (`/health`), and admin (`/admin/*`) paths are unversioned. Update any frontend clients to use the new paths.

## Technical Debt & Recommendations

- **CRM API endpoints** — The CRM module has models but no API endpoints yet. When needed, add `router.py`, `schemas.py`, `service.py`, and `repository.py` following the auth module pattern.
