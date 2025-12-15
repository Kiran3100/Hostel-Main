# --- File: app/schemas/analytics/custom_reports.py ---
"""
Custom report builder schemas with advanced filtering and aggregation.

Provides flexible report generation capabilities allowing users to:
- Define custom fields and aggregations
- Apply complex filters
- Group and sort data
- Generate reports in multiple formats
- Share and save report definitions
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Annotated
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator, computed_field
from uuid import UUID

from app.schemas.common.base import BaseSchema, BaseCreateSchema, BaseResponseSchema
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "FilterOperator",
    "AggregationType",
    "ReportFormat",
    "ReportModule",
    "CustomReportFilter",
    "CustomReportField",
    "CustomReportRequest",
    "CustomReportDefinition",
    "CustomReportResult",
    "ReportExportRequest",
    "ReportSchedule",
]


class FilterOperator(str, Enum):
    """Supported filter operators for custom reports."""
    
    # Comparison
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    
    # Set operations
    IN = "in"
    NOT_IN = "not_in"
    
    # String operations
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    
    # Range operations
    BETWEEN = "between"
    
    # Null checks
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    
    # Date operations
    DATE_EQUALS = "date_eq"
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"


class AggregationType(str, Enum):
    """Supported aggregation types."""
    
    SUM = "sum"
    AVERAGE = "avg"
    MINIMUM = "min"
    MAXIMUM = "max"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    NONE = "none"  # No aggregation


class ReportFormat(str, Enum):
    """Output format for reports."""
    
    TABLE = "table"
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PDF = "pdf"


class ReportModule(str, Enum):
    """Available modules for custom reports."""
    
    BOOKINGS = "bookings"
    PAYMENTS = "payments"
    COMPLAINTS = "complaints"
    MAINTENANCE = "maintenance"
    ATTENDANCE = "attendance"
    STUDENTS = "students"
    HOSTELS = "hostels"
    ROOMS = "rooms"
    USERS = "users"
    ANNOUNCEMENTS = "announcements"
    REVIEWS = "reviews"


class CustomReportFilter(BaseSchema):
    """
    Filter definition for custom reports.
    
    Defines a single filter condition that can be applied
    to narrow down report data.
    """
    
    field_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Field name to filter on"
    )
    operator: FilterOperator = Field(
        ...,
        description="Filter operator"
    )
    value: Union[str, int, float, bool, List[Any], None] = Field(
        ...,
        description="Filter value"
    )
    value_to: Optional[Union[str, int, float, None]] = Field(
        None,
        description="Second value for BETWEEN operator"
    )
    case_sensitive: bool = Field(
        False,
        description="Whether string comparison is case-sensitive"
    )
    
    @model_validator(mode="after")
    def validate_operator_value_compatibility(self) -> "CustomReportFilter":
        """Validate that operator and value are compatible."""
        
        # BETWEEN requires value_to
        if self.operator == FilterOperator.BETWEEN and self.value_to is None:
            raise ValueError("BETWEEN operator requires value_to")
        
        # IN/NOT_IN require list values
        if self.operator in [FilterOperator.IN, FilterOperator.NOT_IN]:
            if not isinstance(self.value, list):
                raise ValueError(f"{self.operator} requires a list value")
        
        # NULL checks don't need values
        if self.operator in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]:
            if self.value is not None:
                raise ValueError(f"{self.operator} should not have a value")
        
        return self
    
    @computed_field  # type: ignore[misc]
    @property
    def filter_display(self) -> str:
        """Generate human-readable filter description."""
        if self.operator == FilterOperator.BETWEEN:
            return f"{self.field_name} between {self.value} and {self.value_to}"
        elif self.operator in [FilterOperator.IN, FilterOperator.NOT_IN]:
            if isinstance(self.value, list):
                return f"{self.field_name} {self.operator.value} ({len(self.value)} items)"
            return f"{self.field_name} {self.operator.value}"
        elif self.operator in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]:
            return f"{self.field_name} {self.operator.value}"
        else:
            return f"{self.field_name} {self.operator.value} {self.value}"


class CustomReportField(BaseSchema):
    """
    Field definition for custom reports.
    
    Defines a field to include in the report with optional
    aggregation and custom display label.
    """
    
    field_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Database field name"
    )
    display_label: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Custom display label for the field"
    )
    aggregation: AggregationType = Field(
        AggregationType.NONE,
        description="Aggregation function to apply"
    )
    format_string: Optional[str] = Field(
        None,
        max_length=50,
        description="Format string for display (e.g., '%.2f' for decimals)"
    )
    
    @field_validator("display_label")
    @classmethod
    def set_default_label(cls, v: Optional[str], info) -> Optional[str]:
        """Set default display label from field name if not provided."""
        if v is None and "field_name" in info.data:
            # Convert snake_case to Title Case
            return info.data["field_name"].replace("_", " ").title()
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def effective_label(self) -> str:
        """Get the effective display label."""
        if self.display_label:
            return self.display_label
        return self.field_name.replace("_", " ").title()


class CustomReportRequest(BaseCreateSchema):
    """
    Request schema for generating a custom report.
    
    Defines all parameters needed to generate a custom report
    including fields, filters, grouping, and output format.
    """
    
    report_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Descriptive name for the report"
    )
    module: ReportModule = Field(
        ...,
        description="Module/entity to report on"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional report description"
    )
    
    # Time period
    period: Optional[DateRangeFilter] = Field(
        None,
        description="Optional date range filter"
    )
    
    # Fields to include
    fields: List[CustomReportField] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Fields to include in the report"
    )
    
    # Filters
    filters: List[CustomReportFilter] = Field(
        default_factory=list,
        max_length=20,
        description="Filter conditions to apply"
    )
    
    # Grouping and aggregation
    group_by: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Field names to group by"
    )
    
    # Sorting
    sort_by: Optional[str] = Field(
        None,
        max_length=100,
        description="Field name to sort by"
    )
    sort_order: str = Field(
        "asc",
        pattern="^(asc|desc)$",
        description="Sort order: asc or desc"
    )
    
    # Pagination
    limit: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Maximum number of rows to return"
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of rows to skip"
    )
    
    # Output options
    format: ReportFormat = Field(
        ReportFormat.TABLE,
        description="Output format"
    )
    include_summary: bool = Field(
        True,
        description="Include summary statistics"
    )
    include_charts: bool = Field(
        False,
        description="Include chart data/recommendations"
    )
    include_totals: bool = Field(
        True,
        description="Include column totals where applicable"
    )
    
    @field_validator("sort_order")
    @classmethod
    def normalize_sort_order(cls, v: str) -> str:
        """Normalize sort order to lowercase."""
        return v.lower()
    
    @model_validator(mode="after")
    def validate_grouping_and_aggregation(self) -> "CustomReportRequest":
        """Validate that grouping is compatible with aggregations."""
        
        if self.group_by:
            # When grouping, at least one field should have aggregation
            has_aggregation = any(
                field.aggregation != AggregationType.NONE
                for field in self.fields
            )
            
            # All non-aggregated fields should be in group_by
            for field in self.fields:
                if field.aggregation == AggregationType.NONE:
                    if field.field_name not in self.group_by:
                        raise ValueError(
                            f"Field '{field.field_name}' must be in group_by "
                            "or have an aggregation when grouping is used"
                        )
        
        return self
    
    @model_validator(mode="after")
    def validate_sort_field(self) -> "CustomReportRequest":
        """Validate sort field exists in selected fields."""
        
        if self.sort_by:
            field_names = [f.field_name for f in self.fields]
            if self.sort_by not in field_names:
                raise ValueError(
                    f"sort_by field '{self.sort_by}' must be included in fields"
                )
        
        return self
    
    def to_sql_hint(self) -> str:
        """
        Generate a SQL-like representation for debugging.
        
        Returns:
            SQL-like string representation of the report query.
        """
        field_str = ", ".join(
            f"{f.aggregation.value}({f.field_name})" if f.aggregation != AggregationType.NONE
            else f.field_name
            for f in self.fields
        )
        
        sql = f"SELECT {field_str} FROM {self.module.value}"
        
        if self.filters:
            filter_str = " AND ".join(f.filter_display for f in self.filters)
            sql += f" WHERE {filter_str}"
        
        if self.group_by:
            sql += f" GROUP BY {', '.join(self.group_by)}"
        
        if self.sort_by:
            sql += f" ORDER BY {self.sort_by} {self.sort_order.upper()}"
        
        if self.limit:
            sql += f" LIMIT {self.limit}"
        
        if self.offset:
            sql += f" OFFSET {self.offset}"
        
        return sql


class CustomReportDefinition(BaseResponseSchema):
    """
    Saved custom report definition.
    
    Represents a stored report configuration that can be
    reused and shared among users.
    """
    
    id: UUID = Field(
        ...,
        description="Report definition unique identifier"
    )
    owner_id: UUID = Field(
        ...,
        description="User who created the report"
    )
    report_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Report name"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Report description"
    )
    module: ReportModule = Field(
        ...,
        description="Report module"
    )
    
    # Report configuration
    period: Optional[DateRangeFilter] = None
    fields: List[CustomReportField] = Field(..., min_length=1)
    filters: List[CustomReportFilter] = Field(default_factory=list)
    group_by: Optional[List[str]] = None
    sort_by: Optional[str] = None
    sort_order: str = Field("asc", pattern="^(asc|desc)$")
    
    # Sharing and permissions
    is_public: bool = Field(
        False,
        description="Whether report is publicly accessible"
    )
    is_template: bool = Field(
        False,
        description="Whether this is a system template"
    )
    shared_with_user_ids: List[UUID] = Field(
        default_factory=list,
        description="User IDs with access to this report"
    )
    shared_with_role: Optional[str] = Field(
        None,
        description="Role with access to this report"
    )
    
    # Usage tracking
    run_count: int = Field(
        0,
        ge=0,
        description="Number of times this report has been run"
    )
    last_run_at: Optional[datetime] = Field(
        None,
        description="Timestamp of last execution"
    )
    
    # Timestamps
    created_at: datetime = Field(
        ...,
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def is_shared(self) -> bool:
        """Check if report is shared with anyone."""
        return (
            self.is_public or
            bool(self.shared_with_user_ids) or
            self.shared_with_role is not None
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def complexity_score(self) -> int:
        """
        Calculate report complexity score (0-100).
        
        Based on number of fields, filters, grouping, etc.
        """
        score = 0
        score += min(len(self.fields) * 5, 25)  # Fields: max 25
        score += min(len(self.filters) * 10, 30)  # Filters: max 30
        score += 20 if self.group_by else 0  # Grouping: 20
        score += min(len(self.group_by or []) * 5, 15)  # Group fields: max 15
        score += 10 if any(f.aggregation != AggregationType.NONE for f in self.fields) else 0
        
        return min(score, 100)


class CustomReportResult(BaseSchema):
    """
    Result of executing a custom report.
    
    Contains the generated data, summary statistics,
    and optional chart data.
    """
    
    report_id: Optional[UUID] = Field(
        None,
        description="Report definition ID if using saved report"
    )
    report_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Report name"
    )
    module: ReportModule = Field(
        ...,
        description="Report module"
    )
    
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    execution_time_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Query execution time in milliseconds"
    )
    
    # Result data
    rows: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Report data rows"
    )
    total_rows: int = Field(
        ...,
        ge=0,
        description="Total number of rows (may exceed returned rows if paginated)"
    )
    returned_rows: int = Field(
        ...,
        ge=0,
        description="Number of rows actually returned"
    )
    
    # Column metadata
    columns: List[CustomReportField] = Field(
        default_factory=list,
        description="Column definitions"
    )
    
    # Summary statistics
    summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Aggregated summary statistics"
    )
    column_totals: Optional[Dict[str, Any]] = Field(
        None,
        description="Column-wise totals"
    )
    
    # Chart data
    charts: Optional[Dict[str, Any]] = Field(
        None,
        description="Suggested chart configurations and data"
    )
    
    # Metadata
    filters_applied: List[CustomReportFilter] = Field(
        default_factory=list,
        description="Filters that were applied"
    )
    grouping_applied: Optional[List[str]] = Field(
        None,
        description="Grouping fields that were applied"
    )
    
    @field_validator("returned_rows")
    @classmethod
    def validate_returned_rows(cls, v: int, info) -> int:
        """Validate returned_rows matches actual row count."""
        if "rows" in info.data and v != len(info.data["rows"]):
            raise ValueError(
                f"returned_rows ({v}) must match length of rows ({len(info.data['rows'])})"
            )
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def is_paginated(self) -> bool:
        """Check if results are paginated."""
        return self.total_rows > self.returned_rows
    
    @computed_field  # type: ignore[misc]
    @property
    def has_data(self) -> bool:
        """Check if report returned any data."""
        return self.returned_rows > 0
    
    def get_export_filename(self, format: ReportFormat) -> str:
        """
        Generate appropriate filename for export.
        
        Args:
            format: Export format
            
        Returns:
            Suggested filename with appropriate extension
        """
        # Sanitize report name
        safe_name = "".join(
            c if c.isalnum() or c in ('-', '_') else '_'
            for c in self.report_name
        )
        
        timestamp = self.generated_at.strftime("%Y%m%d_%H%M%S")
        extension = format.value
        
        return f"{safe_name}_{timestamp}.{extension}"


class ReportExportRequest(BaseSchema):
    """Request to export a report in specific format."""
    
    report_result_id: Optional[UUID] = Field(
        None,
        description="ID of cached report result to export"
    )
    format: ReportFormat = Field(
        ...,
        description="Export format"
    )
    include_metadata: bool = Field(
        True,
        description="Include report metadata in export"
    )
    include_filters: bool = Field(
        True,
        description="Include applied filters in export"
    )
    include_summary: bool = Field(
        True,
        description="Include summary in export"
    )


class ReportSchedule(BaseSchema):
    """Schedule configuration for recurring report generation."""
    
    report_id: UUID = Field(
        ...,
        description="Report definition to run"
    )
    schedule_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Schedule name"
    )
    
    # Schedule configuration
    frequency: str = Field(
        ...,
        pattern="^(daily|weekly|monthly|quarterly)$",
        description="Report frequency"
    )
    time_of_day: str = Field(
        ...,
        pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Time to run (HH:MM format, 24-hour)"
    )
    day_of_week: Optional[int] = Field(
        None,
        ge=0,
        le=6,
        description="Day of week for weekly reports (0=Monday)"
    )
    day_of_month: Optional[int] = Field(
        None,
        ge=1,
        le=31,
        description="Day of month for monthly reports"
    )
    
    # Delivery configuration
    recipients: List[str] = Field(
        ...,
        min_length=1,
        description="Email addresses to send report to"
    )
    format: ReportFormat = Field(
        ReportFormat.PDF,
        description="Report format for delivery"
    )
    
    # Status
    is_active: bool = Field(
        True,
        description="Whether schedule is active"
    )
    last_run_at: Optional[datetime] = Field(
        None,
        description="Last execution timestamp"
    )
    next_run_at: Optional[datetime] = Field(
        None,
        description="Next scheduled execution"
    )
    
    @field_validator("recipients")
    @classmethod
    def validate_email_format(cls, v: List[str]) -> List[str]:
        """Basic email format validation."""
        import re
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        for email in v:
            if not email_pattern.match(email):
                raise ValueError(f"Invalid email format: {email}")
        
        return v