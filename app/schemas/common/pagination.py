# --- File: app/schemas/common/pagination.py ---
"""
Pagination schemas for page-based and cursor-based responses.
"""

from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import Field, field_validator, computed_field

from app.schemas.common.base import BaseSchema

T = TypeVar("T")

__all__ = [
    "PaginationParams",
    "PaginationMeta",
    "PaginatedResponse",
    "CursorPaginationParams",
    "CursorPaginationMeta",
    "CursorPaginatedResponse",
]


class PaginationParams(BaseSchema):
    """Pagination query parameters."""

    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per page",
    )

    @field_validator("page")
    @classmethod
    def validate_page(cls, v: int) -> int:
        """Validate page number."""
        if v < 1:
            raise ValueError("Page number must be >= 1")
        return v

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        """Validate page size."""
        if v < 1 or v > 100:
            raise ValueError("Page size must be between 1 and 100")
        return v

    @computed_field  # type: ignore[misc]
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size

    @computed_field  # type: ignore[misc]
    @property
    def limit(self) -> int:
        """Get limit for database queries."""
        return self.page_size


class PaginationMeta(BaseSchema):
    """Pagination metadata."""

    total_items: int = Field(
        ...,
        ge=0,
        description="Total number of items",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )
    current_page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        ...,
        ge=1,
        description="Items per page",
    )
    has_next: bool = Field(..., description="Has next page")
    has_previous: bool = Field(..., description="Has previous page")


class PaginatedResponse(BaseSchema, Generic[T]):
    """Generic paginated response."""

    items: List[T] = Field(..., description="List of items")
    meta: PaginationMeta = Field(..., description="Pagination metadata")

    @classmethod
    def create(
        cls,
        items: List[T],
        total_items: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """
        Create paginated response with calculated metadata.

        Args:
            items: List of items for current page.
            total_items: Total number of items across all pages.
            page: Current page number.
            page_size: Number of items per page.

        Returns:
            PaginatedResponse with items and metadata.
        """
        # Calculate total pages (handle division by zero)
        total_pages = (
            (total_items + page_size - 1) // page_size if page_size > 0 else 0
        )

        # Ensure total_pages is at least 1 if there are items
        if total_items > 0 and total_pages == 0:
            total_pages = 1

        meta = PaginationMeta(
            total_items=total_items,
            total_pages=total_pages,
            current_page=page,
            page_size=page_size,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

        return cls(items=items, meta=meta)


class CursorPaginationParams(BaseSchema):
    """Cursor-based pagination parameters (for infinite scroll)."""

    cursor: Optional[str] = Field(
        default=None,
        description="Cursor for next page",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items to fetch",
    )


class CursorPaginationMeta(BaseSchema):
    """Cursor pagination metadata."""

    next_cursor: Optional[str] = Field(
        default=None,
        description="Cursor for next page",
    )
    has_more: bool = Field(
        ...,
        description="Whether more items exist",
    )


class CursorPaginatedResponse(BaseSchema, Generic[T]):
    """Generic cursor-based paginated response."""

    items: List[T] = Field(..., description="List of items")
    meta: CursorPaginationMeta = Field(
        ...,
        description="Cursor pagination metadata",
    )