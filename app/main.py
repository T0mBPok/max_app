from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api import router
from app.errors import AppError, app_error_handler, validation_error_handler

app = FastAPI(
    title="Пойдём? API", version="0.1.0",
    description="MVP поиска активностей и комнат для совместного посещения в Томске.",
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(router)


@app.get("/health", tags=["system"])
async def health(): return {"status": "ok"}
