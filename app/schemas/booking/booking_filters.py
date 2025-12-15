# --- File: app/schemas/booking/booking_filters.py ---
"""
Booking filter and search schemas.

This module defines schemas for filtering, searching, sorting,
and exporting booking data.
"""

from __future__ import annotations

from datetime import date as Date
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseFilterSchema
from app.schemas.common.enums import BookingSource, BookingStatus, RoomType

__all__ = [
    "BookingFilterParams",
    "BookingSearchRequest",
    "BookingSortOptions",
    "BookingExportRequest",
    "BookingAnalyticsRequest",
]


class BookingFilterParams(BaseFilterSchema):
    """
    Comprehensive booking filter parameters.
    
    Supports filtering by various criteria including status,
    dates, hostel, room type, and more.
    """

    # Text Search
    search: Optional[str] = Field(
        None,
        max_length=255,
        description="Search in booking reference, guest name, email, or phone",
    )

    # Hostel Filters
    hostel_id: Optional[UUID] = Field(
        None,
        description="Filter by specific hostel",
    )
    hostel_ids: Optional[List[UUID]] = Field(
        None,
        max_length=20,
        description="Filter by multiple hostels (max 20)",
    )

    # Status Filters
    status: Optional[BookingStatus] = Field(
        None,
        description="Filter by specific status",
    )
    statuses: Optional[List[BookingStatus]] = Field(
        None,
        max_length=10,
        description="Filter by multiple statuses",
    )

    # Date Filters
    booking_date_from: Optional[Date] = Field(
        None,
        description="Filter bookings created from this Date",
    )
    booking_date_to: Optional[Date] = Field(
        None,
        description="Filter bookings created until this Date",
    )
    check_in_date_from: Optional[Date] = Field(
        None,
        description="Filter by check-in Date from",
    )
    check_in_date_to: Optional[Date] = Field(
        None,
        description="Filter by check-in Date until",
    )

    # Room Type Filter
    room_type: Optional[RoomType] = Field(
        None,
        description="Filter by room type",
    )

    # Source Filter
    source: Optional[BookingSource] = Field(
        None,
        description="Filter by booking source",
    )

    # Payment Status
    advance_paid: Optional[bool] = Field(
        None,
        description="Filter by advance payment status",
    )

    # Conversion Status
    converted_to_student: Optional[bool] = Field(
        None,
        description="Filter by student conversion status",
    )

    # Urgency Filters
    expiring_soon: Optional[bool] = Field(
        None,
        description="Show only bookings expiring in next 24 hours",
    )
    expired: Optional[bool] = Field(
        None,
        description="Show only expired bookings",
    )

    @field_validator("booking_date_to")
    @classmethod
    def validate_booking_date_range(cls, v: Optional[Date], info) -> Optional[Date]:
        """Validate booking Date range."""
        booking_date_from = info.data.get("booking_date_from")
        if v is not None and booking_date_from is not None:
            if v < booking_date_from:
                raise ValueError(
                    "booking_date_to must be after or equal to booking_date_from"
                )
        return v

    @field_validator("check_in_date_to")
    @classmethod
    def validate_check_in_date_range(cls, v: Optional[Date], info) -> Optional[Date]:
        """Validate check-in Date range."""
        check_in_date_from = info.data.get("check_in_date_from")
        if v is not None and check_in_date_from is not None:
            if v < check_in_date_from:
                raise ValueError(
                    "check_in_date_to must be after or equal to check_in_date_from"
                )
        return v


class BookingSearchRequest(BaseFilterSchema):
    """
    Booking search request with pagination.
    
    Supports full-text search across booking fields.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Search query string",
    )
    hostel_id: Optional[UUID] = Field(
        None,
        description="Limit search to specific hostel",
    )

    # Search Fields (which fields to search in)
    search_in_reference: bool = Field(
        True,
        description="Search in booking reference",
    )
    search_in_guest_name: bool = Field(
        True,
        description="Search in guest name",
    )
    search_in_email: bool = Field(
        True,
        description="Search in email address",
    )
    search_in_phone: bool = Field(
        True,
        description="Search in phone number",
    )

    # Status Filter
    status: Optional[BookingStatus] = Field(
        None,
        description="Limit search to specific status",
    )

    # Pagination
    page: int = Field(
        1,
        ge=1,
        description="Page number (1-indexed)",
    )
    page_size: int = Field(
        20,
        ge=1,
        le=100,
        description="Items per page (max 100)",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and clean search query."""
        v = v.strip()
        if len(v) == 0:
            raise ValueError("Search query cannot be empty")
        return v


class BookingSortOptions(BaseFilterSchema):
    """
    Booking sorting options.
    
    Defines how to sort booking results.
    """

    sort_by: str = Field(
        "booking_date",
        pattern=r"^(booking_date|check_in_date|guest_name|status|total_amount)$",
        description="Field to sort by",
    )
    sort_order: str = Field(
        "desc",
        pattern=r"^(asc|desc)$",
        description="Sort order: ascending or descending",
    )

    @field_validator("sort_by", "sort_order")
    @classmethod
    def normalize_sort_fields(cls, v: str) -> str:
        """Normalize sort field values."""
        return v.lower()


class BookingExportRequest(BaseFilterSchema):
    """
    Request to export bookings data.
    
    Supports multiple export formats with customizable fields.
    """

    hostel_id: Optional[UUID] = Field(
        None,
        description="Export bookings for specific hostel",
    )
    filters: Optional[BookingFilterParams] = Field(
        None,
        description="Apply filters to export",
    )

    # Export Format
    format: str = Field(
        "csv",
        pattern=r"^(csv|excel|pdf)$",
        description="Export format: csv, excel, or pdf",
    )

    # Fields to Include
    include_guest_details: bool = Field(
        True,
        description="Include guest personal details",
    )
    include_payment_details: bool = Field(
        True,
        description="Include payment information",
    )
    include_assignment_details: bool = Field(
        True,
        description="Include room/bed assignment details",
    )

    @field_validator("format")
    @classmethod
    def normalize_format(cls, v: str) -> str:
        """Normalize export format."""
        return v.lower()


class BookingAnalyticsRequest(BaseFilterSchema):
    """
    Request for booking analytics data.
    
    Generate analytics and reports for bookings within
    a specified Date range.
    """

    hostel_id: Optional[UUID] = Field(
        None,
        description="Generate analytics for specific hostel (or all)",
    )
    date_from: Date = Field(
        ...,
        description="Analytics start Date",
    )
    date_to: Date = Field(
        ...,
        description="Analytics end Date",
    )

    # Grouping
    group_by: str = Field(
        "day",
        pattern=r"^(day|week|month)$",
        description="Group analytics by: day, week, or month",
    )

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v: Date, info) -> Date:
        """Validate Date range."""
        date_from = info.data.get("date_from")
        if date_from is not None:
            if v < date_from:
                raise ValueError("date_to must be after or equal to date_from")
            
            # Limit to reasonable range (e.g., max 1 year)
            days_diff = (v - date_from).days
            if days_diff > 365:
                raise ValueError(
                    "Date range cannot exceed 365 days for analytics"
                )
        
        return v

    @field_validator("group_by")
    @classmethod
    def normalize_group_by(cls, v: str) -> str:
        """Normalize group_by value."""
        return v.lower()