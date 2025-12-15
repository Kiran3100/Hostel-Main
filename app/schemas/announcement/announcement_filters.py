# --- File: app/schemas/announcement/announcement_filters.py ---
"""
Announcement filter and search schemas.

This module defines schemas for filtering, searching,
and exporting announcements.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseFilterSchema
from app.schemas.common.enums import AnnouncementCategory, Priority

__all__ = [
    "ExportFormat",
    "AnnouncementSortField",
    "AnnouncementFilterParams",
    "SearchRequest",
    "ArchiveRequest",
    "AnnouncementExportRequest",
    "BulkDeleteRequest",
    "AnnouncementStatsRequest",
]


class ExportFormat(str, Enum):
    """Export format enumeration."""
    
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class AnnouncementSortField(str, Enum):
    """Sort field enumeration."""
    
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PUBLISHED_AT = "published_at"
    TITLE = "title"
    PRIORITY = "priority"
    ENGAGEMENT_RATE = "engagement_rate"
    READ_COUNT = "read_count"


class AnnouncementFilterParams(BaseFilterSchema):
    """
    Comprehensive announcement filter parameters.
    
    Supports filtering by various criteria for announcement lists.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    # Text search
    search: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Search in title and content",
    )
    
    # Hostel filter
    hostel_id: Optional[UUID] = Field(
        None,
        description="Filter by single hostel",
    )
    hostel_ids: Optional[list[UUID]] = Field(
        None,
        max_length=50,
        description="Filter by multiple hostels",
    )
    
    # Category filter
    category: Optional[AnnouncementCategory] = Field(
        None,
        description="Filter by single category",
    )
    categories: Optional[list[AnnouncementCategory]] = Field(
        None,
        description="Filter by multiple categories",
    )
    exclude_categories: Optional[list[AnnouncementCategory]] = Field(
        None,
        description="Exclude specific categories",
    )
    
    # Priority filter
    priority: Optional[Priority] = Field(
        None,
        description="Filter by single priority",
    )
    priorities: Optional[list[Priority]] = Field(
        None,
        description="Filter by multiple priorities",
    )
    min_priority: Optional[Priority] = Field(
        None,
        description="Minimum priority level",
    )
    
    # Status filters
    is_published: Optional[bool] = Field(
        None,
        description="Filter by publication status",
    )
    is_urgent: Optional[bool] = Field(
        None,
        description="Filter by urgent flag",
    )
    is_pinned: Optional[bool] = Field(
        None,
        description="Filter by pinned flag",
    )
    requires_acknowledgment: Optional[bool] = Field(
        None,
        description="Filter by acknowledgment requirement",
    )
    
    # Creator filters
    created_by: Optional[UUID] = Field(
        None,
        description="Filter by creator UUID",
    )
    created_by_role: Optional[str] = Field(
        None,
        pattern=r"^(admin|supervisor|super_admin)$",
        description="Filter by creator role",
    )
    
    # Date filters
    published_date_from: Optional[Date] = Field(
        None,
        description="Published on or after this Date",
    )
    published_date_to: Optional[Date] = Field(
        None,
        description="Published on or before this Date",
    )
    created_date_from: Optional[Date] = Field(
        None,
        description="Created on or after this Date",
    )
    created_date_to: Optional[Date] = Field(
        None,
        description="Created on or before this Date",
    )
    
    # Expiry filters
    active_only: Optional[bool] = Field(
        None,
        description="Only non-expired announcements",
    )
    expired_only: Optional[bool] = Field(
        None,
        description="Only expired announcements",
    )
    expires_before: Optional[Date] = Field(
        None,
        description="Expires before this Date",
    )
    expires_after: Optional[Date] = Field(
        None,
        description="Expires after this Date",
    )
    
    # Approval filters
    approval_pending: Optional[bool] = Field(
        None,
        description="Filter by pending approval status",
    )
    approved_by: Optional[UUID] = Field(
        None,
        description="Filter by approver UUID",
    )
    
    # Engagement filters
    min_read_rate: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Minimum read rate percentage",
    )
    min_engagement_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Minimum engagement score",
    )
    
    # Sorting
    sort_by: AnnouncementSortField = Field(
        AnnouncementSortField.CREATED_AT,
        description="Field to sort by",
    )
    sort_order: str = Field(
        "desc",
        pattern=r"^(asc|desc)$",
        description="Sort order",
    )
    
    # Pagination
    page: int = Field(
        1,
        ge=1,
        description="Page number",
    )
    page_size: int = Field(
        20,
        ge=1,
        le=100,
        description="Items per page",
    )
    
    @field_validator("hostel_ids")
    @classmethod
    def validate_hostel_ids(cls, v: Optional[list[UUID]]) -> Optional[list[UUID]]:
        """Ensure unique hostel IDs."""
        if v and len(v) != len(set(v)):
            raise ValueError("Duplicate hostel IDs not allowed")
        return v
    
    @field_validator("published_date_to")
    @classmethod
    def validate_published_date_range(
        cls, v: Optional[Date], info
    ) -> Optional[Date]:
        """Validate Date range."""
        from_date = info.data.get("published_date_from")
        if v and from_date and v < from_date:
            raise ValueError("published_date_to must be after published_date_from")
        return v
    
    @field_validator("created_date_to")
    @classmethod
    def validate_created_date_range(
        cls, v: Optional[Date], info
    ) -> Optional[Date]:
        """Validate Date range."""
        from_date = info.data.get("created_date_from")
        if v and from_date and v < from_date:
            raise ValueError("created_date_to must be after created_date_from")
        return v
    
    @model_validator(mode="after")
    def validate_conflicting_filters(self) -> "AnnouncementFilterParams":
        """Check for conflicting filter combinations."""
        if self.active_only and self.expired_only:
            raise ValueError("Cannot use both active_only and expired_only")
        
        if self.hostel_id and self.hostel_ids:
            raise ValueError("Use either hostel_id or hostel_ids, not both")
        
        if self.category and self.categories:
            raise ValueError("Use either category or categories, not both")
        
        return self


class SearchRequest(BaseFilterSchema):
    """
    Full-text search request for announcements.
    
    Provides advanced search capabilities.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    query: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Search query string",
    )
    hostel_id: Optional[UUID] = Field(
        None,
        description="Limit search to specific hostel",
    )
    
    # Search scope
    search_in_title: bool = Field(
        True,
        description="Search in announcement titles",
    )
    search_in_content: bool = Field(
        True,
        description="Search in announcement content",
    )
    search_in_attachments: bool = Field(
        False,
        description="Search in attachment names",
    )
    
    # Filters
    category: Optional[AnnouncementCategory] = Field(
        None,
        description="Filter by category",
    )
    published_only: bool = Field(
        True,
        description="Only search published announcements",
    )
    
    # Date range
    date_from: Optional[Date] = Field(
        None,
        description="Search from this Date",
    )
    date_to: Optional[Date] = Field(
        None,
        description="Search until this Date",
    )
    
    # Pagination
    page: int = Field(
        1,
        ge=1,
        description="Page number",
    )
    page_size: int = Field(
        20,
        ge=1,
        le=100,
        description="Results per page",
    )
    
    # Result options
    highlight_matches: bool = Field(
        True,
        description="Highlight matching text in results",
    )
    
    @model_validator(mode="after")
    def validate_search_scope(self) -> "SearchRequest":
        """Ensure at least one search field is enabled."""
        if not any([
            self.search_in_title,
            self.search_in_content,
            self.search_in_attachments
        ]):
            raise ValueError("At least one search field must be enabled")
        return self


class ArchiveRequest(BaseCreateSchema):
    """
    Archive old announcements.
    
    Moves old announcements to archive storage.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel UUID",
    )
    archived_by: UUID = Field(
        ...,
        description="User performing the archive",
    )
    
    # Archive criteria
    archive_before_date: Date = Field(
        ...,
        description="Archive announcements published before this Date",
    )
    
    # Options
    archive_expired_only: bool = Field(
        True,
        description="Only archive expired announcements",
    )
    archive_read_only: bool = Field(
        False,
        description="Only archive fully-read announcements (100% read rate)",
    )
    archive_acknowledged_only: bool = Field(
        False,
        description="Only archive fully-acknowledged announcements",
    )
    
    # Exclusions
    exclude_pinned: bool = Field(
        True,
        description="Don't archive pinned announcements",
    )
    exclude_urgent: bool = Field(
        False,
        description="Don't archive urgent announcements",
    )
    exclude_categories: Optional[list[AnnouncementCategory]] = Field(
        None,
        description="Categories to exclude from archiving",
    )
    
    # Preview mode
    dry_run: bool = Field(
        False,
        description="Preview what would be archived without archiving",
    )
    
    @field_validator("archive_before_date")
    @classmethod
    def validate_archive_date(cls, v: Date) -> Date:
        """Ensure archive Date is in the past."""
        if v >= Date.today():
            raise ValueError("Archive Date must be in the past")
        return v


class AnnouncementExportRequest(BaseFilterSchema):
    """
    Export announcements to file.
    
    Generate downloadable exports in various formats.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel UUID",
    )
    exported_by: UUID = Field(
        ...,
        description="User requesting export",
    )
    
    # Filters
    filters: Optional[AnnouncementFilterParams] = Field(
        None,
        description="Filter parameters for export",
    )
    
    # Format
    format: ExportFormat = Field(
        ExportFormat.PDF,
        description="Export file format",
    )
    
    # Content options
    include_content: bool = Field(
        True,
        description="Include full announcement content",
    )
    include_engagement_metrics: bool = Field(
        True,
        description="Include engagement metrics",
    )
    include_recipient_list: bool = Field(
        False,
        description="Include list of recipients",
    )
    include_read_receipts: bool = Field(
        False,
        description="Include read receipt details",
    )
    include_acknowledgments: bool = Field(
        False,
        description="Include acknowledgment details",
    )
    
    # Date range
    date_from: Optional[Date] = Field(
        None,
        description="Export from this Date",
    )
    date_to: Optional[Date] = Field(
        None,
        description="Export until this Date",
    )
    
    # Delivery
    send_to_email: Optional[str] = Field(
        None,
        description="Email address to send export (optional)",
    )
    
    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v: Optional[Date], info) -> Optional[Date]:
        """Validate Date range."""
        date_from = info.data.get("date_from")
        if v and date_from and v < date_from:
            raise ValueError("date_to must be after date_from")
        return v


class BulkDeleteRequest(BaseCreateSchema):
    """
    Bulk delete announcements.
    
    Permanently remove multiple announcements.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Announcement UUIDs to delete (1-100)",
    )
    deleted_by: UUID = Field(
        ...,
        description="User performing the deletion",
    )
    
    # Confirmation
    confirm_permanent: bool = Field(
        False,
        description="Confirm permanent deletion (required)",
    )
    
    # Options
    force_delete_published: bool = Field(
        False,
        description="Allow deletion of published announcements",
    )
    
    @field_validator("announcement_ids")
    @classmethod
    def validate_unique_ids(cls, v: list[UUID]) -> list[UUID]:
        """Ensure unique IDs."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate announcement IDs not allowed")
        return v
    
    @model_validator(mode="after")
    def validate_confirmation(self) -> "BulkDeleteRequest":
        """Require confirmation for bulk delete."""
        if not self.confirm_permanent:
            raise ValueError(
                "confirm_permanent must be True to proceed with deletion"
            )
        return self


class AnnouncementStatsRequest(BaseFilterSchema):
    """
    Request announcement statistics.
    
    Parameters for generating announcement analytics.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel UUID (None for all hostels)",
    )
    
    # Time range
    period_start: Date = Field(
        ...,
        description="Statistics period start Date",
    )
    period_end: Date = Field(
        ...,
        description="Statistics period end Date",
    )
    
    # Grouping
    group_by: str = Field(
        "day",
        pattern=r"^(hour|day|week|month)$",
        description="Time grouping for trends",
    )
    
    # Metrics to include
    include_category_breakdown: bool = Field(
        True,
        description="Include breakdown by category",
    )
    include_engagement_trends: bool = Field(
        True,
        description="Include engagement trends over time",
    )
    include_creator_stats: bool = Field(
        False,
        description="Include statistics by creator",
    )
    include_comparison: bool = Field(
        False,
        description="Include comparison with previous period",
    )
    
    @field_validator("period_end")
    @classmethod
    def validate_period(cls, v: Date, info) -> Date:
        """Validate period range."""
        period_start = info.data.get("period_start")
        if period_start and v < period_start:
            raise ValueError("period_end must be after period_start")
        
        # Limit to 1 year
        if period_start:
            days_diff = (v - period_start).days
            if days_diff > 365:
                raise ValueError("Period cannot exceed 1 year")
        
        return v