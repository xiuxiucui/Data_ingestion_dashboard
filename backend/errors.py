"""Application errors and Pydantic error formatting helpers."""

from __future__ import annotations

from typing import Any, Iterable

from pydantic import ValidationError


class ApiError(Exception):
    """An expected API failure that can be safely returned to a client."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


def format_validation_errors(
    error: ValidationError,
    location_prefix: Iterable[str | int] = (),
) -> list[dict[str, Any]]:
    """Convert Pydantic errors into the stable public error representation."""

    prefix = list(location_prefix)
    return [
        {
            "location": prefix + list(item["loc"]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]

