from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from src.activity.router import router as activities_router
from src.exceptions import AppError, app_error_handler, validation_error_handler
from src.imports.router import router as imports_router
from src.room.router import router as rooms_router
from src.user.router import router as users_router

app = FastAPI(
    title="Пойдём? API",
    version="0.1.0",
    description="MVP поиска активностей и комнат для совместного посещения в Томске.",
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(users_router, prefix="/api/v1")
app.include_router(activities_router, prefix="/api/v1")
app.include_router(rooms_router, prefix="/api/v1")
app.include_router(imports_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}
