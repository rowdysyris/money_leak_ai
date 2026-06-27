"""Shared API response schemas and builders."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Structured API error body."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Consistent API error response envelope."""

    success: bool = False
    error: ErrorBody


class SuccessResponse(BaseModel):
    """Consistent API success response envelope."""

    success: bool = True
    data: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


def success_response(data: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    """Build a consistent success response dictionary."""
    return {"success": True, "data": data, "warnings": warnings or []}


def error_response(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a consistent error response dictionary."""
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
