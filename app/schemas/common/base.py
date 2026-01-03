"""
Base schema classes with common fields and configurations.
"""

from datetime import datetime
from typing import Any, Union, List, TypeVar, Generic, Optional

from pydantic import BaseModel, ConfigDict, Field, EmailStr

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
    "PaginatedResponse",
    "User",
]

T = TypeVar('T')


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

    deleted_at: Union[datetime, None] = Field(
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


class PaginatedResponse(BaseSchema, Generic[T]):
    """
    Base schema for paginated API responses.
    
    This generic class provides standard pagination metadata along with
    the actual data items. Subclasses should specify the items type.
    """
    
    items: List[T] = Field(..., description="List of items in the current page")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of items per page")
    total_items: int = Field(..., ge=0, description="Total number of items across all pages")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")
    
    @property
    def is_first_page(self) -> bool:
        """Check if this is the first page."""
        return self.page == 1
    
    @property
    def is_last_page(self) -> bool:
        """Check if this is the last page."""
        return self.page >= self.total_pages


class User(BaseResponseSchema):
    """
    User schema for authentication and user information.
    
    This schema represents the authenticated user in the system.
    Used primarily in dependency injection for current_user.
    """
    
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    username: Optional[str] = Field(None, description="Username")
    role: str = Field(..., description="User role in the system")
    is_active: bool = Field(default=True, description="Whether the user account is active")
    is_verified: bool = Field(default=False, description="Whether the user email is verified")
    
    @property
    def full_name(self) -> str:
        """Get the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()