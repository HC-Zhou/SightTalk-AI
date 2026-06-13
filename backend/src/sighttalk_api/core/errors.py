"""Application-level error types and HTTP error serialization."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Exception carrying a stable API error code and HTTP status."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Serialize AppError instances using the repository-wide error contract."""
    if not isinstance(exc, AppError):
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request.headers.get("x-request-id"),
            }
        },
    )
