# app/services/common/pagination.py
"""
Pagination utilities for service layer.

Provides helpers to build paginated responses with type safety
and performance optimizations.
"""
from __future__ import annotations

from typing import Callable, Generic, Iterable, Optional, Sequence, TypeVar

from app.schemas.common.base import BaseSchema
from app.schemas.common.pagination import PaginatedResponse, PaginationParams

from .errors import ValidationError

TModel = TypeVar("TModel")
TSchema = TypeVar("TSchema", bound=BaseSchema)


class PaginationError(ValidationError):
    """Raised when pagination parameters are invalid."""


def validate_pagination_params(params: PaginationParams) -> None:
    """
    Validate pagination parameters.

    Args:
        params: Pagination parameters to validate

    Raises:
        PaginationError: If parameters are invalid
    """
    if params.page < 1:
        raise PaginationError(
            "Page number must be >= 1",
            field="page",
            details={"page": params.page},
        )

    if params.page_size < 1:
        raise PaginationError(
            "Page size must be >= 1",
            field="page_size",
            details={"page_size": params.page_size},
        )

    if params.page_size > 1000:
        raise PaginationError(
            "Page size cannot exceed 1000",
            field="page_size",
            details={"page_size": params.page_size, "max": 1000},
        )


def paginate(
    *,
    items: Sequence[TModel],
    total_items: int,
    params: PaginationParams,
    mapper: Callable[[TModel], TSchema],
) -> PaginatedResponse[TSchema]:
    """
    Build a paginated response from models.

    Args:
        items: Current page of ORM model instances
        total_items: Total count across all pages
        params: Pagination parameters (page, page_size)
        mapper: Function to convert model to schema

    Returns:
        PaginatedResponse containing schemas and metadata

    Raises:
        PaginationError: If pagination parameters are invalid

    Example:
        >>> response = paginate(
        ...     items=db_users,
        ...     total_items=total_count,
        ...     params=pagination_params,
        ...     mapper=lambda u: to_schema(u, UserSchema),
        ... )
    """
    validate_pagination_params(params)

    # Convert models to schemas efficiently
    schema_items: list[TSchema] = [mapper(item) for item in items]

    return PaginatedResponse[TSchema].create(
        items=schema_items,
        total_items=total_items,
        page=params.page,
        page_size=params.page_size,
    )


def paginate_direct(
    *,
    items: Sequence[TSchema],
    total_items: int,
    params: PaginationParams,
) -> PaginatedResponse[TSchema]:
    """
    Build a paginated response from already-converted schemas.

    Args:
        items: Current page of schema instances
        total_items: Total count across all pages
        params: Pagination parameters

    Returns:
        PaginatedResponse containing schemas and metadata

    Raises:
        PaginationError: If pagination parameters are invalid

    Example:
        >>> response = paginate_direct(
        ...     items=user_schemas,
        ...     total_items=100,
        ...     params=pagination_params,
        ... )
    """
    validate_pagination_params(params)

    return PaginatedResponse[TSchema].create(
        items=list(items),
        total_items=total_items,
        page=params.page,
        page_size=params.page_size,
    )


def calculate_offset(params: PaginationParams) -> int:
    """
    Calculate database query offset from pagination params.

    Args:
        params: Pagination parameters

    Returns:
        Offset value for database query

    Example:
        >>> offset = calculate_offset(PaginationParams(page=3, page_size=20))
        >>> # offset = 40
    """
    return (params.page - 1) * params.page_size


def calculate_total_pages(total_items: int, page_size: int) -> int:
    """
    Calculate total number of pages.

    Args:
        total_items: Total number of items
        page_size: Items per page

    Returns:
        Total number of pages

    Example:
        >>> total_pages = calculate_total_pages(total_items=95, page_size=20)
        >>> # total_pages = 5
    """
    if page_size <= 0:
        return 0
    return (total_items + page_size - 1) // page_size


class PaginationHelper(Generic[TModel, TSchema]):
    """
    Reusable pagination helper for consistent pagination across services.

    Example:
        >>> helper = PaginationHelper(
        ...     mapper=lambda u: to_schema(u, UserSchema)
        ... )
        >>> response = helper.paginate(
        ...     items=db_users,
        ...     total_items=total,
        ...     params=params,
        ... )
    """

    def __init__(self, mapper: Callable[[TModel], TSchema]) -> None:
        """
        Initialize pagination helper.

        Args:
            mapper: Function to convert model to schema
        """
        self.mapper = mapper

    def paginate(
        self,
        items: Sequence[TModel],
        total_items: int,
        params: PaginationParams,
    ) -> PaginatedResponse[TSchema]:
        """Paginate items using the configured mapper."""
        return paginate(
            items=items,
            total_items=total_items,
            params=params,
            mapper=self.mapper,
        )

    @staticmethod
    def get_offset(params: PaginationParams) -> int:
        """Get database offset for params."""
        return calculate_offset(params)

    @staticmethod
    def get_total_pages(total_items: int, page_size: int) -> int:
        """Calculate total pages."""
        return calculate_total_pages(total_items, page_size)