# --- File: app/schemas/inquiry/inquiry_filters.py ---
"""
Inquiry filter and search schemas.

This module defines schemas for filtering, searching, and sorting
inquiry data.
"""

from __future__ import annotations

from datetime import date as Date
from typing import List, Optional
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common.base import BaseFilterSchema
from app.schemas.common.enums import InquirySource, InquiryStatus, RoomType

__all__ = [
    "InquiryFilterParams",
    "InquirySearchRequest",
    "InquirySortOptions",
    "InquiryExportRequest",
]


class InquiryFilterParams(BaseFilterSchema):
    """
    Comprehensive inquiry filter parameters.
    
    Supports filtering by status, dates, hostel, source, and more.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "search": "John",
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "new",
                "source": "website",
                "created_from": "2024-01-01",
                "created_to": "2024-12-31"
            }
        }
    )

    # Text Search
    search: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Search in visitor name, email, or phone",
    )

    # Hostel Filter
    hostel_id: Optional[UUID] = Field(
        default=None,
        description="Filter by specific hostel",
    )
    hostel_ids: Optional[List[UUID]] = Field(
        default=None,
        max_length=20,
        description="Filter by multiple hostels",
    )

    # Status Filter
    status: Optional[InquiryStatus] = Field(
        default=None,
        description="Filter by specific status",
    )
    statuses: Optional[List[InquiryStatus]] = Field(
        default=None,
        max_length=10,
        description="Filter by multiple statuses",
    )

    # Source Filter
    source: Optional[InquirySource] = Field(
        default=None,
        description="Filter by inquiry source",
    )
    sources: Optional[List[InquirySource]] = Field(
        default=None,
        max_length=10,
        description="Filter by multiple sources",
    )

    # Date Filters
    created_from: Optional[Date] = Field(
        default=None,
        description="Filter inquiries created from this Date",
    )
    created_to: Optional[Date] = Field(
        default=None,
        description="Filter inquiries created until this Date",
    )

    # Check-in Date Filter
    check_in_from: Optional[Date] = Field(
        default=None,
        description="Filter by preferred check-in Date from",
    )
    check_in_to: Optional[Date] = Field(
        default=None,
        description="Filter by preferred check-in Date to",
    )

    # Room Type Filter
    room_type: Optional[RoomType] = Field(
        default=None,
        description="Filter by room type preference",
    )

    # Assignment Filters
    assigned_to: Optional[UUID] = Field(
        default=None,
        description="Filter by assigned admin",
    )
    is_assigned: Optional[bool] = Field(
        default=None,
        description="Filter by assignment status",
    )

    # Contact Status
    is_contacted: Optional[bool] = Field(
        default=None,
        description="Filter by whether inquiry has been contacted",
    )

    # Urgency Filters
    is_urgent: Optional[bool] = Field(
        default=None,
        description="Show only urgent inquiries (new and recent)",
    )
    is_stale: Optional[bool] = Field(
        default=None,
        description="Show only stale inquiries (old without contact)",
    )

    @field_validator("created_to")
    @classmethod
    def validate_created_date_range(cls, v: Optional[Date], info) -> Optional[Date]:
        """Validate created Date range."""
        created_from = info.data.get("created_from")
        if v is not None and created_from is not None:
            if v < created_from:
                raise ValueError("created_to must be after or equal to created_from")
        return v

    @field_validator("check_in_to")
    @classmethod
    def validate_check_in_date_range(cls, v: Optional[Date], info) -> Optional[Date]:
        """Validate check-in Date range."""
        check_in_from = info.data.get("check_in_from")
        if v is not None and check_in_from is not None:
            if v < check_in_from:
                raise ValueError("check_in_to must be after or equal to check_in_from")
        return v


class InquirySearchRequest(BaseFilterSchema):
    """
    Inquiry search request with pagination.
    
    Supports full-text search across inquiry fields.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "query": "john smith",
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "search_in_name": True,
                "search_in_email": True,
                "status": "new",
                "page": 1,
                "page_size": 20
            }
        }
    )

    query: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Search query string",
    )
    hostel_id: Optional[UUID] = Field(
        default=None,
        description="Limit search to specific hostel",
    )

    # Search Fields
    search_in_name: bool = Field(
        default=True,
        description="Search in visitor name",
    )
    search_in_email: bool = Field(
        default=True,
        description="Search in email address",
    )
    search_in_phone: bool = Field(
        default=True,
        description="Search in phone number",
    )
    search_in_message: bool = Field(
        default=False,
        description="Search in inquiry message",
    )

    # Status Filter
    status: Optional[InquiryStatus] = Field(
        default=None,
        description="Limit search to specific status",
    )

    # Pagination
    page: int = Field(
        default=1,
        ge=1,
        description="Page number",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per page",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate search query."""
        v = v.strip()
        if len(v) == 0:
            raise ValueError("Search query cannot be empty")
        return v


class InquirySortOptions(BaseFilterSchema):
    """
    Inquiry sorting options.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "sort_by": "created_at",
                "sort_order": "desc"
            }
        }
    )

    sort_by: str = Field(
        default="created_at",
        pattern=r"^(created_at|visitor_name|status|check_in_date)$",
        description="Field to sort by",
    )
    sort_order: str = Field(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Sort order",
    )

    @field_validator("sort_by", "sort_order")
    @classmethod
    def normalize_sort_fields(cls, v: str) -> str:
        """Normalize sort fields."""
        return v.lower()


class InquiryExportRequest(BaseFilterSchema):
    """
    Request to export inquiries data.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "format": "csv",
                "include_message": True,
                "include_notes": False,
                "include_timeline": False
            }
        }
    )

    hostel_id: Optional[UUID] = Field(
        default=None,
        description="Export inquiries for specific hostel",
    )
    filters: Optional[InquiryFilterParams] = Field(
        default=None,
        description="Apply filters to export",
    )

    # Export Format
    format: str = Field(
        default="csv",
        pattern=r"^(csv|excel|pdf)$",
        description="Export format",
    )

    # Fields to Include
    include_message: bool = Field(
        default=True,
        description="Include inquiry message",
    )
    include_notes: bool = Field(
        default=False,
        description="Include internal notes",
    )
    include_timeline: bool = Field(
        default=False,
        description="Include timeline/history",
    )

    @field_validator("format")
    @classmethod
    def normalize_format(cls, v: str) -> str:
        """Normalize format."""
        return v.lower()