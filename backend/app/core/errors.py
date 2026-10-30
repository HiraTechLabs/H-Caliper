"""Typed API error handling."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class ApiError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, **(detail or {})},
        )


def bad_request(message: str, code: str = "bad_request", **detail: Any) -> ApiError:
    return ApiError(400, code, message, detail)


def unauthorized(message: str = "Authentication required") -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


def forbidden(message: str = "Not permitted") -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, "forbidden", message)


def not_found(entity: str = "Resource") -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"{entity} not found")


def conflict(message: str, code: str = "conflict", **detail: Any) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, code, message, detail)


def unprocessable(message: str, code: str = "validation_error", **detail: Any) -> ApiError:
    return ApiError(422, code, message, detail)
