from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self, code: str, message: str, status_code: int = 400, details: dict[str, Any] | None = None
    ):
        self.code, self.message, self.status_code, self.details = (
            code,
            message,
            status_code,
            details or {},
        )


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {key: value for key, value in error.items() if key not in {"url", "ctx"}}
        for error in exc.errors()
    ]
    details = {"errors": jsonable_encoder(errors)}
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Некорректные параметры запроса",
                "details": details,
            }
        },
    )


def not_found(code: str, message: str) -> AppError:
    return AppError(code, message, 404)
