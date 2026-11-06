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
│   │   └── logging.py       # Centralized logging setup
│   │
│   ├── db/                  # Database layer
│   │   ├── base.py          # SQLAlchemy DeclarativeBase
│   │   ├── session.py       # Engine, SessionLocal, get_db() dependency
│   │   └── init_db.py       # Table creation + admin user seeding
│   │
│   ├── modules/             # Feature modules (domain-driven)
│   │   ├── auth/             # Authentication feature
│   │   │   ├── router.py          # 4 endpoints: login, logout, refresh, me
│   │   │   ├── schemas.py         # Pydantic request/response models
│   │   │   ├── service.py          # Business logic (authenticate, token creation)
│   │   │   └── dependencies.py    # get_current_user, get_current_admin_user
│   │   │
│   │   ├── users/           # User domain
│   │   │   ├── models.py          # User ORM model, Role enum
│   │   │   └── repository.py      # Database queries (get_user_by_email, create_user)
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
| POST | `/auth/login` | None | Authenticate, return access + refresh tokens |
| POST | `/auth/logout` | Bearer | Logout (client discards tokens) |
| POST | `/auth/refresh` | Refresh token | Issue new access token |
| GET | `/auth/me` | Bearer | Current user profile |
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

## Render Deployment

The application is deployed on Render via Git auto-deploy from the `main` branch.

**Start command (configured in Render dashboard):**
```
uvicorn nabora_crm.main:app --host 0.0.0.0 --port $PORT
```

The start command is unchanged by this refactor. All environment variables, database connections, and endpoint URLs remain compatible.

## Technical Debt & Recommendations

- **Alembic migrations** — The project uses `Base.metadata.create_all()` for schema management. Consider adding Alembic for production-safe schema migrations.
- **CRM API endpoints** — The CRM module has models but no API endpoints yet. When needed, add `router.py`, `schemas.py`, `service.py`, and `repository.py` following the auth module pattern.
- **Domain exceptions** — Services currently raise `HTTPException` directly. For stricter layer separation, introduce domain exceptions in services and map them to HTTP responses in a FastAPI exception handler.
- **API versioning** — No `/v1/` prefix is used. If breaking changes are anticipated, consider introducing versioned routers.
