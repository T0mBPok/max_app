from fastapi import APIRouter

from app.api import activities, admin, rooms, users

router = APIRouter(prefix="/api/v1")
router.include_router(users.router); router.include_router(activities.router)
router.include_router(rooms.router); router.include_router(admin.router)

