"""
Complaint filtering and search schemas.

Provides comprehensive filtering, searching, and sorting
capabilities for complaint queries.
"""
from datetime import date as Date
from typing import List, Union

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import BaseFilterSchema
from app.schemas.common.enums import ComplaintCategory, ComplaintStatus, Priority

__all__ = [
    "ComplaintFilterParams",
    "ComplaintSearchRequest",
    "ComplaintSortOptions",
    "ComplaintExportRequest",
]


class ComplaintFilterParams(BaseFilterSchema):
    """
    Comprehensive complaint filter parameters.
    
    Supports filtering by multiple dimensions for flexible queries.
    """
    model_config = ConfigDict(from_attributes=True)

    # Text search
    search: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Search in title, description, complaint number",
    )

    # Hostel filters
    hostel_id: Union[str, None] = Field(
        default=None,
        description="Filter by single hostel",
    )
    hostel_ids: Union[List[str], None] = Field(
        default=None,
        max_length=50,
        description="Filter by multiple hostels (max 50)",
    )

    # User filters
    raised_by: Union[str, None] = Field(
        default=None,
        description="Filter by complainant user ID",
    )
    student_id: Union[str, None] = Field(
        default=None,
        description="Filter by student ID",
    )

    # Assignment filters
    assigned_to: Union[str, None] = Field(
        default=None,
        description="Filter by assigned staff member",
    )
    unassigned_only: Union[bool, None] = Field(
        default=None,
        description="Show only unassigned complaints",
    )

    # Category filters
    category: Union[ComplaintCategory, None] = Field(
        default=None,
        description="Filter by single category",
    )
    categories: Union[List[ComplaintCategory], None] = Field(
        default=None,
        max_length=20,
        description="Filter by multiple categories",
    )

    # Priority filters
    priority: Union[Priority, None] = Field(
        default=None,
        description="Filter by single priority",
    )
    priorities: Union[List[Priority], None] = Field(
        default=None,
        max_length=10,
        description="Filter by multiple priorities",
    )

    # Status filters
    status: Union[ComplaintStatus, None] = Field(
        default=None,
        description="Filter by single status",
    )
    statuses: Union[List[ComplaintStatus], None] = Field(
        default=None,
        max_length=10,
        description="Filter by multiple statuses",
    )

    # Date range filters
    opened_date_from: Union[Date, None] = Field(
        default=None,
        description="Opened Date range start (inclusive)",
    )
    opened_date_to: Union[Date, None] = Field(
        default=None,
        description="Opened Date range end (inclusive)",
    )
    resolved_date_from: Union[Date, None] = Field(
        default=None,
        description="Resolved Date range start",
    )
    resolved_date_to: Union[Date, None] = Field(
        default=None,
        description="Resolved Date range end",
    )

    # Special filters
    sla_breached_only: Union[bool, None] = Field(
        default=None,
        description="Show only SLA breached complaints",
    )
    escalated_only: Union[bool, None] = Field(
        default=None,
        description="Show only escalated complaints",
    )

    # Location filters
    room_id: Union[str, None] = Field(
        default=None,
        description="Filter by specific room",
    )

    # Age filters
    age_hours_min: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Minimum complaint age in hours",
    )
    age_hours_max: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Maximum complaint age in hours",
    )

    @field_validator("search")
    @classmethod
    def validate_search(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize search query."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("hostel_ids", "categories", "priorities", "statuses")
    @classmethod
    def validate_list_length(cls, v: Union[List, None]) -> Union[List, None]:
        """Ensure filter lists don't exceed reasonable limits."""
        if v is not None and len(v) > 50:
            raise ValueError("Too many items in filter list (max 50)")
        return v

    @model_validator(mode="after")
    def validate_date_and_age_ranges(self):
        """Validate Date and age ranges are logical."""
        # Validate opened Date range
        if self.opened_date_to is not None and self.opened_date_from is not None:
            if self.opened_date_to < self.opened_date_from:
                raise ValueError("opened_date_to must be >= opened_date_from")
        
        # Validate resolved Date range
        if self.resolved_date_to is not None and self.resolved_date_from is not None:
            if self.resolved_date_to < self.resolved_date_from:
                raise ValueError("resolved_date_to must be >= resolved_date_from")
        
        # Validate age range
        if self.age_hours_max is not None and self.age_hours_min is not None:
            if self.age_hours_max < self.age_hours_min:
                raise ValueError("age_hours_max must be >= age_hours_min")
        
        return self


class ComplaintSearchRequest(BaseFilterSchema):
    """
    Full-text search request for complaints.
    
    Supports configurable search fields and filters.
    """
    model_config = ConfigDict(from_attributes=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query string",
    )
    hostel_id: Union[str, None] = Field(
        default=None,
        description="Limit search to specific hostel",
    )

    # Search scope configuration
    search_in_title: bool = Field(
        default=True,
        description="Include title in search",
    )
    search_in_description: bool = Field(
        default=True,
        description="Include description in search",
    )
    search_in_number: bool = Field(
        default=True,
        description="Include complaint number in search",
    )

    # Optional filters
    status: Union[ComplaintStatus, None] = Field(
        default=None,
        description="Filter by status",
    )
    priority: Union[Priority, None] = Field(
        default=None,
        description="Filter by priority",
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
        description="Results per page (1-100)",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Normalize search query."""
        v = v.strip()
        if not v:
            raise ValueError("Search query cannot be empty")
        return v


class ComplaintSortOptions(BaseFilterSchema):
    """
    Sorting options for complaint queries.
    
    Defines available sort fields and order.
    """
    model_config = ConfigDict(from_attributes=True)

    sort_by: str = Field(
        default="opened_at",
        pattern=r"^(opened_at|priority|status|category|age|updated_at|resolved_at)$",
        description="Field to sort by",
    )
    sort_order: str = Field(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Sort order: ascending or descending",
    )

    @field_validator("sort_by", "sort_order")
    @classmethod
    def normalize_sort_params(cls, v: str) -> str:
        """Normalize sort parameters to lowercase."""
        return v.lower().strip()


class ComplaintExportRequest(BaseFilterSchema):
    """
    Export complaints to various formats.
    
    Supports CSV, Excel, and PDF exports with configurable fields.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: Union[str, None] = Field(
        default=None,
        description="Limit export to specific hostel",
    )
    filters: Union[ComplaintFilterParams, None] = Field(
        default=None,
        description="Apply filters to export",
    )

    format: str = Field(
        default="csv",
        pattern=r"^(csv|excel|pdf)$",
        description="Export format: csv, excel, or pdf",
    )

    # Export options
    include_comments: bool = Field(
        default=False,
        description="Include comments in export",
    )
    include_resolution_details: bool = Field(
        default=True,
        description="Include resolution details",
    )
    include_feedback: bool = Field(
        default=True,
        description="Include student feedback",
    )

    @field_validator("format")
    @classmethod
    def normalize_format(cls, v: str) -> str:
        """Normalize export format to lowercase."""
        return v.lower().strip()