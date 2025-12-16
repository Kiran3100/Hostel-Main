# --- File: app/schemas/common/response.py ---
"""
Standard API response wrappers for success, error, and bulk operations.
"""

from typing import Any, Dict, Generic, List, Union, TypeVar

from pydantic import Field

from app.schemas.common.base import BaseSchema

T = TypeVar("T")

__all__ = [
    "SuccessResponse",
    "ErrorDetail",
    "ErrorResponse",
    "MessageResponse",
    "BulkOperationResponse",
    "ValidationErrorResponse",
    "NotFoundResponse",
    "UnauthorizedResponse",
    "ForbiddenResponse",
    "ConflictResponse",
    "RateLimitResponse",
]


class SuccessResponse(BaseSchema, Generic[T]):
    """Standard success response."""

    success: bool = Field(default=True, description="Success flag")
    message: str = Field(..., description="Response message")
    data: Union[T, None] = Field(default=None, description="Response data")

    @classmethod
    def create(
        cls,
        message: str,
        data: Union[T, None] = None,
    ):
        """Create success response."""
        return cls(success=True, message=message, data=data)


class ErrorDetail(BaseSchema):
    """Error detail information."""

    field: Union[str, None] = Field(
        default=None,
        description="Field name causing error",
    )
    message: str = Field(..., description="Error message")
    code: Union[str, None] = Field(
        default=None,
        description="Error code",
    )
    location: Union[List[str], None] = Field(
        default=None,
        description="Error location in nested structure",
    )


class ErrorResponse(BaseSchema):
    """Standard error response."""

    success: bool = Field(default=False, description="Success flag")
    message: str = Field(..., description="Error message")
    errors: Union[List[ErrorDetail], None] = Field(
        default=None,
        description="Detailed errors",
    )
    error_code: Union[str, None] = Field(
        default=None,
        description="Application error code",
    )
    timestamp: Union[str, None] = Field(
        default=None,
        description="Error timestamp",
    )
    path: Union[str, None] = Field(
        default=None,
        description="Request path that caused error",
    )

    @classmethod
    def create(
        cls,
        message: str,
        errors: Union[List[ErrorDetail], None] = None,
        error_code: Union[str, None] = None,
    ):
        """Create error response."""
        return cls(
            success=False,
            message=message,
            errors=errors,
            error_code=error_code,
        )


class MessageResponse(BaseSchema):
    """Simple message response."""

    message: str = Field(..., description="Response message")

    @classmethod
    def create(cls, message: str):
        """Create message response."""
        return cls(message=message)


class BulkOperationResponse(BaseSchema):
    """Response for bulk operations."""

    total: int = Field(
        ...,
        ge=0,
        description="Total items processed",
    )
    successful: int = Field(
        ...,
        ge=0,
        description="Successfully processed items",
    )
    failed: int = Field(
        ...,
        ge=0,
        description="Failed items",
    )
    errors: Union[List[Dict[str, Any]], None] = Field(
        default=None,
        description="Errors for failed items",
    )
    details: Union[Dict[str, Any], None] = Field(
        default=None,
        description="Additional operation details",
    )

    @classmethod
    def create(
        cls,
        total: int,
        successful: int,
        failed: int,
        errors: Union[List[Dict[str, Any]], None] = None,
        details: Union[Dict[str, Any], None] = None,
    ):
        """Create bulk operation response."""
        return cls(
            total=total,
            successful=successful,
            failed=failed,
            errors=errors,
            details=details,
        )


class ValidationErrorResponse(ErrorResponse):
    """Validation error response (422)."""

    validation_errors: List[ErrorDetail] = Field(
        ...,
        description="Validation error details",
    )


class NotFoundResponse(ErrorResponse):
    """Not found error response (404)."""

    resource_type: Union[str, None] = Field(
        default=None,
        description="Type of resource not found",
    )
    resource_id: Union[str, None] = Field(
        default=None,
        description="ID of resource not found",
    )


class UnauthorizedResponse(ErrorResponse):
    """Unauthorized error response (401)."""

    auth_scheme: Union[str, None] = Field(
        default=None,
        description="Authentication scheme required",
    )


class ForbiddenResponse(ErrorResponse):
    """Forbidden error response (403)."""

    required_permission: Union[str, None] = Field(
        default=None,
        description="Required permission",
    )
    user_permissions: Union[List[str], None] = Field(
        default=None,
        description="User's current permissions",
    )


class ConflictResponse(ErrorResponse):
    """Conflict error response (409)."""

    conflicting_resource: Union[str, None] = Field(
        default=None,
        description="Conflicting resource identifier",
    )


class RateLimitResponse(ErrorResponse):
    """Rate limit exceeded response (429)."""

    retry_after: Union[int, None] = Field(
        default=None,
        description="Seconds to wait before retry",
    )
    limit: Union[int, None] = Field(
        default=None,
        description="Rate limit",
    )
    window: Union[int, None] = Field(
        default=None,
        description="Time window in seconds",
    )