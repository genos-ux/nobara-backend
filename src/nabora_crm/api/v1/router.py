from fastapi import APIRouter

from nabora_crm.modules.auth.router import router as auth_router
from nabora_crm.modules.invitations.router import router as invitations_router
from nabora_crm.modules.posts.router import router as posts_router
from nabora_crm.modules.roles.router import router as roles_router
from nabora_crm.modules.uploads.router import router as uploads_router
from nabora_crm.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(invitations_router)
api_router.include_router(posts_router)
api_router.include_router(roles_router)
api_router.include_router(uploads_router)
api_router.include_router(users_router)
