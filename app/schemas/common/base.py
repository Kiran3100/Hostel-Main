# --- File: app/schemas/common/base.py ---
"""
Base schema classes with common fields and configurations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BaseSchema",
    "TimestampMixin",
    "SoftDeleteMixin",
    "UUIDMixin",
    "BaseDBSchema",
    "BaseCreateSchema",
    "BaseUpdateSchema",
    "BaseResponseSchema",
    "BaseFilterSchema",
]


class BaseSchema(BaseModel):
    """
    Base schema with common Pydantic configuration.

    All application-facing schemas should ideally inherit from this to ensure
    consistent behaviour (e.g. JSON encoders, validation, etc.).
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        # Keep enums as Enum instances to retain full type information;
        # callers can still access `.value` if needed.
        use_enum_values=False,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        # Pydantic v2: json_encoders is deprecated.
        # Use custom serializers via @field_serializer or @model_serializer
        # if custom JSON encoding is needed.
        # Datetime fields are serialized to ISO format by default in v2.
    )


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class SoftDeleteMixin(BaseModel):
    """Mixin for soft delete support."""

    deleted_at: Optional[datetime] = Field(
        default=None,
        description="Deletion timestamp",
    )
    is_deleted: bool = Field(
        default=False,
        description="Soft delete flag",
    )


class UUIDMixin(BaseModel):
    """Mixin for UUID primary key."""

    id: str = Field(..., description="Unique identifier")


class BaseDBSchema(BaseSchema, UUIDMixin, TimestampMixin):
    """Base schema for database entities with ID and timestamps."""
    pass


class BaseCreateSchema(BaseSchema):
    """Base schema for create operations."""
    pass


class BaseUpdateSchema(BaseSchema):
    """
    Base schema for update operations.

    Note:
        This base class does not itself make fields optional. Subclasses
        intended for partial updates should declare their fields as
        Optional[...] / with defaults as appropriate.
    """
    pass


class BaseResponseSchema(BaseDBSchema):
    """Base schema for API responses."""
    pass


class BaseFilterSchema(BaseSchema):
    """Base schema for filter parameters."""
    pass