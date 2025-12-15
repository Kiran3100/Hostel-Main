# app/core/pagination.py
from __future__ import annotations

"""
Core pagination helpers.

This module provides:
- `normalize_pagination` to clean up page/page_size inputs using defaults
  and clamping.
- `paginate_items` to map and wrap results in a `PaginatedResponse` schema.

These helpers unify pagination semantics across the project.
"""

from typing import Sequence, Callable, TypeVar, List

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.common.base import BaseSchema

TModel = TypeVar("TModel")
TSchema = TypeVar("TSchema", bound=BaseSchema)


def normalize_pagination(
    page: int | None,
    page_size: int | None,
) -> PaginationParams:
    """
    Normalize raw page & page_size inputs into a PaginationParams object
    with sane defaults and a clamped max page size.

    Rules:
        - page < 1 or None -> DEFAULT_PAGE
        - page_size < 1 or None -> DEFAULT_PAGE_SIZE
        - page_size > MAX_PAGE_SIZE -> MAX_PAGE_SIZE
    """
    if page is None or page < 1:
        page = DEFAULT_PAGE

    if page_size is None or page_size < 1:
        page_size = DEFAULT_PAGE_SIZE

    if page_size > MAX_PAGE_SIZE:
        page_size = MAX_PAGE_SIZE

    return PaginationParams(page=page, page_size=page_size)


def paginate_items(
    *,
    items: Sequence[TModel],
    total_items: int,
    params: PaginationParams,
    mapper: Callable[[TModel], TSchema],
) -> PaginatedResponse[TSchema]:
    """
    Map and wrap items into a PaginatedResponse using the same semantics
    as app.services.common.pagination, but exposed from core.

    Args:
        items: Sequence of model instances (DB objects, domain objects, etc.).
        total_items: Total number of items across all pages (for metadata).
        params: Pagination parameters (page, page_size).
        mapper: Function to convert each model instance into a schema instance.

    Returns:
        A `PaginatedResponse[TSchema]` populated with mapped items and metadata.
    """
    mapped: List[TSchema] = [mapper(obj) for obj in items]
    return PaginatedResponse[TSchema].create(
        items=mapped,
        total_items=total_items,
        page=params.page,
        page_size=params.page_size,
    )