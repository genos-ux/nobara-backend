import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI
from sqlalchemy import text
from sqladmin import Admin, ModelView

from nabora_crm.auth import router as auth_router
from nabora_crm.auth import seed_users
from nabora_crm.database import engine
from nabora_crm.models import Activity, Base, Person, User

logger = logging.getLogger("nabora_crm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Test database connection on startup
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Successfully connected to PostgreSQL database!")
    except Exception as exc:
        logger.error("Failed to connect to the database: %s", exc)
        raise

    # Create all database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")

    # Seed admin account
    seed_users()

    yield


app = FastAPI(
    title="Nabora CRM API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)

# SQLAdmin dashboard
admin = Admin(app=app, engine=engine, base_url="/admin", title="Nabora CRM Admin")


class UserAdmin(ModelView, model=User):
    category = "Users"
    column_list = [User.id, User.email, User.role, User.is_active]


class PersonAdmin(ModelView, model=Person):
    category = "CRM"
    column_list = [Person.id, Person.name, Person.email, Person.stage, Person.subscribed]


class ActivityAdmin(ModelView, model=Activity):
    category = "CRM"
    column_list = [Activity.id, Activity.person_id, Activity.staff_name, Activity.activity_type, Activity.created_at]


admin.add_view(UserAdmin)
admin.add_view(PersonAdmin)
admin.add_view(ActivityAdmin)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Welcome to Nabora CRM API",
        "status": "success",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
    }
