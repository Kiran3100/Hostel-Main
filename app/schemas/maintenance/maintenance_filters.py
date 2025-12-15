# --- File: app/schemas/maintenance/maintenance_filters.py ---
"""
Maintenance filter schemas for querying and exporting.

Provides comprehensive filtering capabilities with validation
for searches, exports, and advanced queries.
"""

from __future__ import annotations

import re
from datetime import date as Date
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator
from uuid import UUID

from app.schemas.common.base import BaseFilterSchema
from app.schemas.common.enums import (
    MaintenanceCategory,
    MaintenanceIssueType,
    MaintenanceStatus,
    Priority,
)

__all__ = [
    "MaintenanceFilterParams",
    "SearchRequest",
    "MaintenanceExportRequest",
    "AdvancedFilterParams",
]


class MaintenanceFilterParams(BaseFilterSchema):
    """
    Comprehensive maintenance filter parameters.
    
    Supports multi-dimensional filtering for maintenance requests
    with text search, Date ranges, and status filters.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "search": "ceiling fan",
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "pending",
                "category": "electrical",
                "priority": "high"
            }
        }
    )

    # Text search
    search: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Search in title, description, request number",
    )
    search_fields: Optional[List[str]] = Field(
        None,
        description="Fields to search in (title, description, notes, etc.)",
    )
    
    # Hostel filters
    hostel_id: Optional[UUID] = Field(
        None,
        description="Filter by specific hostel",
    )
    hostel_ids: Optional[List[UUID]] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Filter by multiple hostels",
    )
    
    # User filters
    requested_by: Optional[UUID] = Field(
        None,
        description="Filter by requester",
    )
    requested_by_role: Optional[str] = Field(
        None,
        pattern=r"^(student|supervisor|admin)$",
        description="Filter by requester role",
    )
    
    # Assignment filters
    assigned_to: Optional[UUID] = Field(
        None,
        description="Filter by assignee",
    )
    assigned_to_role: Optional[str] = Field(
        None,
        pattern=r"^(staff|vendor|contractor)$",
        description="Filter by assignee role",
    )
    unassigned_only: Optional[bool] = Field(
        None,
        description="Show only unassigned requests",
    )
    
    # Room filters
    room_id: Optional[UUID] = Field(
        None,
        description="Filter by specific room",
    )
    room_ids: Optional[List[UUID]] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Filter by multiple rooms",
    )
    floor: Optional[int] = Field(
        None,
        ge=0,
        le=50,
        description="Filter by floor number",
    )
    
    # Category filters
    category: Optional[MaintenanceCategory] = Field(
        None,
        description="Filter by specific category",
    )
    categories: Optional[List[MaintenanceCategory]] = Field(
        None,
        min_length=1,
        description="Filter by multiple categories",
    )
    exclude_categories: Optional[List[MaintenanceCategory]] = Field(
        None,
        description="Exclude specific categories",
    )
    
    # Priority filters
    priority: Optional[Priority] = Field(
        None,
        description="Filter by specific priority",
    )
    priorities: Optional[List[Priority]] = Field(
        None,
        min_length=1,
        description="Filter by multiple priorities",
    )
    min_priority: Optional[Priority] = Field(
        None,
        description="Minimum priority level (inclusive)",
    )
    
    # Status filters
    status: Optional[MaintenanceStatus] = Field(
        None,
        description="Filter by specific status",
    )
    statuses: Optional[List[MaintenanceStatus]] = Field(
        None,
        min_length=1,
        description="Filter by multiple statuses",
    )
    exclude_statuses: Optional[List[MaintenanceStatus]] = Field(
        None,
        description="Exclude specific statuses",
    )
    
    # Issue type filter
    issue_type: Optional[MaintenanceIssueType] = Field(
        None,
        description="Filter by issue type",
    )
    
    # Date filters
    created_date_from: Optional[Date] = Field(
        None,
        description="Filter requests created from this Date",
    )
    created_date_to: Optional[Date] = Field(
        None,
        description="Filter requests created until this Date",
    )
    completion_date_from: Optional[Date] = Field(
        None,
        description="Filter by completion Date from",
    )
    completion_date_to: Optional[Date] = Field(
        None,
        description="Filter by completion Date to",
    )
    due_date_from: Optional[Date] = Field(
        None,
        description="Filter by due Date from",
    )
    due_date_to: Optional[Date] = Field(
        None,
        description="Filter by due Date to",
    )
    
    # Cost filters - Using Annotated for Decimal in v2
    estimated_cost_min: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Minimum estimated cost",
    )
    estimated_cost_max: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Maximum estimated cost",
    )
    actual_cost_min: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Minimum actual cost",
    )
    actual_cost_max: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Maximum actual cost",
    )
    
    # Special filters
    approval_pending: Optional[bool] = Field(
        None,
        description="Filter requests pending approval",
    )
    overdue_only: Optional[bool] = Field(
        None,
        description="Show only overdue requests",
    )
    is_preventive: Optional[bool] = Field(
        None,
        description="Filter preventive maintenance",
    )
    has_vendor: Optional[bool] = Field(
        None,
        description="Filter requests with vendor assignment",
    )
    quality_checked: Optional[bool] = Field(
        None,
        description="Filter by quality check status",
    )
    within_budget: Optional[bool] = Field(
        None,
        description="Filter requests within approved budget",
    )

    @field_validator("search")
    @classmethod
    def normalize_search(cls, v: Optional[str]) -> Optional[str]:
        """Normalize search query."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @field_validator(
        "estimated_cost_min",
        "estimated_cost_max",
        "actual_cost_min",
        "actual_cost_max",
    )
    @classmethod
    def round_costs(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round cost values to 2 decimal places."""
        return round(v, 2) if v is not None else None

    @model_validator(mode="after")
    def validate_filter_consistency(self) -> "MaintenanceFilterParams":
        """
        Validate filter parameter consistency.
        
        Ensures compatible filters are used together and
        no conflicting options are specified.
        """
        # Validate Date ranges
        if self.created_date_from and self.created_date_to:
            if self.created_date_to < self.created_date_from:
                raise ValueError(
                    "created_date_to must be after or equal to created_date_from"
                )
        
        if self.completion_date_from and self.completion_date_to:
            if self.completion_date_to < self.completion_date_from:
                raise ValueError(
                    "completion_date_to must be after or equal to completion_date_from"
                )
        
        # Validate cost ranges
        if self.estimated_cost_min and self.estimated_cost_max:
            if self.estimated_cost_max < self.estimated_cost_min:
                raise ValueError(
                    "estimated_cost_max must be greater than or equal to estimated_cost_min"
                )
        
        if self.actual_cost_min and self.actual_cost_max:
            if self.actual_cost_max < self.actual_cost_min:
                raise ValueError(
                    "actual_cost_max must be greater than or equal to actual_cost_min"
                )
        
        # Validate status filters
        if self.status and self.statuses:
            raise ValueError(
                "Cannot use both 'status' and 'statuses' filters"
            )
        
        if self.statuses and self.exclude_statuses:
            overlap = set(self.statuses) & set(self.exclude_statuses)
            if overlap:
                raise ValueError(
                    "Cannot include and exclude the same statuses"
                )
        
        # Validate category filters
        if self.category and self.categories:
            raise ValueError(
                "Cannot use both 'category' and 'categories' filters"
            )
        
        if self.categories and self.exclude_categories:
            overlap = set(self.categories) & set(self.exclude_categories)
            if overlap:
                raise ValueError(
                    "Cannot include and exclude the same categories"
                )
        
        # Validate priority filters
        if self.priority and self.priorities:
            raise ValueError(
                "Cannot use both 'priority' and 'priorities' filters"
            )
        
        # Validate hostel/room filters
        if self.hostel_id and self.hostel_ids:
            raise ValueError(
                "Cannot use both 'hostel_id' and 'hostel_ids' filters"
            )
        
        return self


class SearchRequest(BaseFilterSchema):
    """
    Maintenance search request with full-text capabilities.
    
    Optimized for text-based searches with field-specific targeting.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "ceiling fan not working",
                "search_in_title": True,
                "search_in_description": True,
                "status": "pending",
                "page": 1,
                "page_size": 20
            }
        }
    )

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query string",
    )
    hostel_id: Optional[UUID] = Field(
        None,
        description="Limit search to specific hostel",
    )
    search_in_title: bool = Field(
        True,
        description="Search in title field",
    )
    search_in_description: bool = Field(
        True,
        description="Search in description field",
    )
    search_in_number: bool = Field(
        True,
        description="Search in request number",
    )
    search_in_notes: bool = Field(
        False,
        description="Search in notes/comments",
    )
    status: Optional[MaintenanceStatus] = Field(
        None,
        description="Filter by status",
    )
    category: Optional[MaintenanceCategory] = Field(
        None,
        description="Filter by category",
    )
    priority: Optional[Priority] = Field(
        None,
        description="Filter by priority",
    )
    date_from: Optional[Date] = Field(
        None,
        description="Search from this Date",
    )
    date_to: Optional[Date] = Field(
        None,
        description="Search until this Date",
    )
    fuzzy_search: bool = Field(
        False,
        description="Enable fuzzy/approximate matching",
    )
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

    @field_validator("query")
    @classmethod
    def normalize_query(cls, v: str) -> str:
        """Normalize search query."""
        v = v.strip()
        
        if len(v) < 1:
            raise ValueError("Search query cannot be empty")
        
        return v

    @model_validator(mode="after")
    def validate_search_fields(self) -> "SearchRequest":
        """
        Validate at least one search field is selected.
        
        Ensures meaningful search configuration.
        """
        if not any([
            self.search_in_title,
            self.search_in_description,
            self.search_in_number,
            self.search_in_notes,
        ]):
            raise ValueError(
                "At least one search field must be enabled"
            )
        
        return self


class AdvancedFilterParams(MaintenanceFilterParams):
    """
    Advanced filter parameters with additional criteria.
    
    Extends basic filters with complex queries and analytics filters.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "search": "electrical",
                "created_in_last_days": 30,
                "over_budget": True,
                "sort_by": "created_at",
                "sort_order": "desc"
            }
        }
    )

    # Time-based filters
    created_in_last_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Created in last N days",
    )
    completed_in_last_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Completed in last N days",
    )
    pending_for_days: Optional[int] = Field(
        None,
        ge=1,
        description="Pending for more than N days",
    )
    
    # Performance filters
    completion_time_min_days: Optional[int] = Field(
        None,
        ge=0,
        description="Minimum completion time in days",
    )
    completion_time_max_days: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum completion time in days",
    )
    
    # Quality filters
    quality_rating_min: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Minimum quality rating",
    )
    quality_check_failed: Optional[bool] = Field(
        None,
        description="Filter failed quality checks",
    )
    rework_required: Optional[bool] = Field(
        None,
        description="Filter requests requiring rework",
    )
    
    # Cost variance filters
    over_budget: Optional[bool] = Field(
        None,
        description="Filter requests over budget",
    )
    cost_variance_min_percentage: Optional[Annotated[Decimal, Field(decimal_places=2)]] = Field(
        None,
        description="Minimum cost variance percentage",
    )
    cost_variance_max_percentage: Optional[Annotated[Decimal, Field(decimal_places=2)]] = Field(
        None,
        description="Maximum cost variance percentage",
    )
    
    # Vendor filters
    vendor_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Filter by vendor name (partial match)",
    )
    vendor_id: Optional[UUID] = Field(
        None,
        description="Filter by vendor ID",
    )
    
    # Warranty filters
    has_warranty: Optional[bool] = Field(
        None,
        description="Filter by warranty applicability",
    )
    warranty_active: Optional[bool] = Field(
        None,
        description="Filter by active warranty status",
    )
    
    # Grouping for analytics
    group_by: Optional[str] = Field(
        None,
        pattern=r"^(category|priority|status|month|assignee|vendor)$",
        description="Group results by field",
    )
    
    # Sorting
    sort_by: str = Field(
        "created_at",
        pattern=r"^(created_at|priority|estimated_cost|actual_cost|completion_date|status)$",
        description="Sort results by field",
    )
    sort_order: str = Field(
        "desc",
        pattern=r"^(asc|desc)$",
        description="Sort order",
    )

    @field_validator("vendor_name")
    @classmethod
    def normalize_vendor_name(cls, v: Optional[str]) -> Optional[str]:
        """Normalize vendor name."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_advanced_filters(self) -> "AdvancedFilterParams":
        """Validate advanced filter combinations."""
        # Validate completion time range
        if self.completion_time_min_days and self.completion_time_max_days:
            if self.completion_time_max_days < self.completion_time_min_days:
                raise ValueError(
                    "completion_time_max_days must be >= completion_time_min_days"
                )
        
        return self


class MaintenanceExportRequest(BaseFilterSchema):
    """
    Export maintenance data with format and options.
    
    Supports multiple export formats with customizable content
    and field selection.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "csv",
                "include_cost_details": True,
                "include_summary": True,
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
                "max_records": 1000
            }
        }
    )

    hostel_id: Optional[UUID] = Field(
        None,
        description="Export data for specific hostel",
    )
    filters: Optional[MaintenanceFilterParams] = Field(
        None,
        description="Apply filters to export",
    )
    format: str = Field(
        "csv",
        pattern=r"^(csv|excel|pdf|json)$",
        description="Export format",
    )
    
    # Content options
    include_cost_details: bool = Field(
        True,
        description="Include cost breakdown",
    )
    include_assignment_details: bool = Field(
        True,
        description="Include assignment information",
    )
    include_completion_details: bool = Field(
        True,
        description="Include completion details",
    )
    include_quality_check: bool = Field(
        False,
        description="Include quality check results",
    )
    include_materials: bool = Field(
        False,
        description="Include materials used",
    )
    include_photos: bool = Field(
        False,
        description="Include photo URLs",
    )
    include_vendor_details: bool = Field(
        False,
        description="Include vendor information",
    )
    include_notes: bool = Field(
        False,
        description="Include notes and comments",
    )
    
    # Field selection
    selected_fields: Optional[List[str]] = Field(
        None,
        max_length=50,
        description="Specific fields to include (overrides include_* options)",
    )
    
    # Grouping and summary
    include_summary: bool = Field(
        True,
        description="Include summary statistics",
    )
    include_charts: bool = Field(
        False,
        description="Include charts/graphs (PDF only)",
    )
    group_by: Optional[str] = Field(
        None,
        pattern=r"^(category|priority|status|month|assignee)$",
        description="Group export by field",
    )
    
    # Sorting
    sort_by: str = Field(
        "created_at",
        description="Sort export by field",
    )
    sort_order: str = Field(
        "desc",
        pattern=r"^(asc|desc)$",
        description="Sort order",
    )
    
    # Output options
    file_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Custom filename (without extension)",
    )
    include_timestamp: bool = Field(
        True,
        description="Include timestamp in filename",
    )
    compress: bool = Field(
        False,
        description="Compress export file (zip)",
    )
    
    # Date range for export
    date_from: Optional[Date] = Field(
        None,
        description="Export data from this Date",
    )
    date_to: Optional[Date] = Field(
        None,
        description="Export data until this Date",
    )
    
    # Limits
    max_records: int = Field(
        10000,
        ge=1,
        le=100000,
        description="Maximum records to export",
    )

    @field_validator("file_name")
    @classmethod
    def validate_filename(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize filename."""
        if v is not None:
            # Remove invalid characters
            v = re.sub(r'[<>:"/\\|?*]', '', v)
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_export_config(self) -> "MaintenanceExportRequest":
        """
        Validate export configuration.
        
        Ensures valid combinations and format-specific requirements.
        """
        # PDF-specific validations
        if self.format == "pdf":
            if self.max_records > 5000:
                raise ValueError(
                    "PDF exports are limited to 5000 records"
                )
            
            if self.include_charts and not self.include_summary:
                raise ValueError(
                    "Charts require summary to be included"
                )
        
        # JSON format validations
        if self.format == "json":
            if self.include_charts:
                raise ValueError(
                    "Charts are not supported in JSON format"
                )
        
        # Validate Date range
        if self.date_from and self.date_to:
            if self.date_to < self.date_from:
                raise ValueError(
                    "date_to must be after or equal to date_from"
                )
            
            # Warn for large Date ranges
            days_diff = (self.date_to - self.date_from).days
            if days_diff > 365 and self.format == "pdf":
                raise ValueError(
                    "PDF exports cannot exceed 365 days of data"
                )
        
        return self