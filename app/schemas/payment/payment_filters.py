# --- File: app/schemas/payment/payment_filters.py ---
"""
Payment filter and search schemas.

This module defines schemas for filtering, searching, sorting,
and exporting payment data.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import PaymentMethod, PaymentStatus, PaymentType

__all__ = [
    "PaymentFilterParams",
    "PaymentSearchRequest",
    "PaymentSortOptions",
    "PaymentReportRequest",
    "PaymentExportRequest",
    "PaymentAnalyticsRequest",
]


class PaymentSortField(str, Enum):
    """Payment sort field options."""
    
    CREATED_AT = "created_at"
    PAID_AT = "paid_at"
    AMOUNT = "amount"
    DUE_DATE = "due_date"
    PAYMENT_REFERENCE = "payment_reference"
    PAYER_NAME = "payer_name"
    HOSTEL_NAME = "hostel_name"


class SortOrder(str, Enum):
    """Sort order options."""
    
    ASC = "asc"
    DESC = "desc"


class ExportFormat(str, Enum):
    """Export format options."""
    
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"


class PaymentFilterParams(BaseSchema):
    """
    Payment filter parameters.
    
    Used to filter payment lists based on various criteria.
    """

    # Entity Filters
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Filter by hostel",
    )
    student_id: Union[UUID, None] = Field(
        None,
        description="Filter by student",
    )
    payer_id: Union[UUID, None] = Field(
        None,
        description="Filter by payer",
    )
    booking_id: Union[UUID, None] = Field(
        None,
        description="Filter by booking",
    )

    # Payment Attributes
    payment_type: Union[PaymentType, None] = Field(
        None,
        description="Filter by payment type",
    )
    payment_status: Union[List[PaymentStatus], None] = Field(
        None,
        description="Filter by payment status (multiple allowed)",
    )
    payment_method: Union[PaymentMethod, None] = Field(
        None,
        description="Filter by payment method",
    )

    # Amount Range
    min_amount: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Minimum amount",
    )
    max_amount: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Maximum amount",
    )

    # Date Ranges
    created_after: Union[datetime, None] = Field(
        None,
        description="Created after this timestamp",
    )
    created_before: Union[datetime, None] = Field(
        None,
        description="Created before this timestamp",
    )
    paid_after: Union[datetime, None] = Field(
        None,
        description="Paid after this timestamp",
    )
    paid_before: Union[datetime, None] = Field(
        None,
        description="Paid before this timestamp",
    )
    due_date_from: Union[Date, None] = Field(
        None,
        description="Due Date from",
    )
    due_date_to: Union[Date, None] = Field(
        None,
        description="Due Date to",
    )

    # Boolean Filters
    is_overdue: Union[bool, None] = Field(
        None,
        description="Filter overdue payments",
    )
    has_receipt: Union[bool, None] = Field(
        None,
        description="Filter payments with receipts",
    )
    is_refunded: Union[bool, None] = Field(
        None,
        description="Filter refunded payments",
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

    @model_validator(mode="after")
    def validate_amount_range(self) -> "PaymentFilterParams":
        """Validate amount range."""
        if self.min_amount is not None and self.max_amount is not None:
            if self.min_amount > self.max_amount:
                raise ValueError(
                    f"min_amount ({self.min_amount}) cannot be greater than "
                    f"max_amount ({self.max_amount})"
                )
        return self

    @model_validator(mode="after")
    def validate_date_ranges(self) -> "PaymentFilterParams":
        """Validate Date ranges."""
        # Created Date range
        if self.created_after and self.created_before:
            if self.created_after > self.created_before:
                raise ValueError("created_after cannot be after created_before")
        
        # Paid Date range
        if self.paid_after and self.paid_before:
            if self.paid_after > self.paid_before:
                raise ValueError("paid_after cannot be after paid_before")
        
        # Due Date range
        if self.due_date_from and self.due_date_to:
            if self.due_date_from > self.due_date_to:
                raise ValueError("due_date_from cannot be after due_date_to")
        
        return self


class PaymentSearchRequest(BaseSchema):
    """
    Payment search request.
    
    Used for text-based search across payment records.
    """

    query: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Search query",
    )
    search_fields: List[str] = Field(
        default_factory=lambda: [
            "payment_reference",
            "transaction_id",
            "payer_name",
            "student_name",
            "notes",
        ],
        description="Fields to search in",
    )
    filters: Union[PaymentFilterParams, None] = Field(
        None,
        description="Additional filters to apply",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate search query."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Search query must be at least 2 characters")
        return v

    @field_validator("search_fields")
    @classmethod
    def validate_search_fields(cls, v: List[str]) -> List[str]:
        """Validate search fields."""
        if not v:
            raise ValueError("At least one search field is required")
        
        allowed_fields = {
            "payment_reference",
            "transaction_id",
            "payer_name",
            "student_name",
            "hostel_name",
            "notes",
            "receipt_number",
        }
        
        invalid_fields = set(v) - allowed_fields
        if invalid_fields:
            raise ValueError(
                f"Invalid search fields: {', '.join(invalid_fields)}. "
                f"Allowed: {', '.join(allowed_fields)}"
            )
        
        return v


class PaymentSortOptions(BaseSchema):
    """
    Payment sorting options.
    
    Defines how to sort payment results.
    """

    sort_by: PaymentSortField = Field(
        PaymentSortField.CREATED_AT,
        description="Field to sort by",
    )
    sort_order: SortOrder = Field(
        SortOrder.DESC,
        description="Sort order (ascending or descending)",
    )

    # Secondary sort (optional)
    secondary_sort_by: Union[PaymentSortField, None] = Field(
        None,
        description="Secondary sort field",
    )
    secondary_sort_order: Union[SortOrder, None] = Field(
        None,
        description="Secondary sort order",
    )

    @model_validator(mode="after")
    def validate_secondary_sort(self) -> "PaymentSortOptions":
        """Validate secondary sort configuration."""
        # If secondary_sort_by is provided, secondary_sort_order must also be provided
        if self.secondary_sort_by and not self.secondary_sort_order:
            self.secondary_sort_order = self.sort_order
        
        # Prevent sorting by same field twice
        if self.secondary_sort_by and self.secondary_sort_by == self.sort_by:
            raise ValueError(
                "Secondary sort field must be different from primary sort field"
            )
        
        return self


class PaymentReportRequest(BaseSchema):
    """
    Payment report generation request.
    
    Used to generate payment reports for specific periods or criteria.
    """

    # Report Period
    period_start: Date = Field(
        ...,
        description="Report period start Date",
    )
    period_end: Date = Field(
        ...,
        description="Report period end Date",
    )

    # Filters
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Generate report for specific hostel",
    )
    payment_type: Union[PaymentType, None] = Field(
        None,
        description="Filter by payment type",
    )
    payment_status: Union[List[PaymentStatus], None] = Field(
        None,
        description="Filter by payment status",
    )

    # Report Options
    include_summary: bool = Field(
        True,
        description="Include summary statistics",
    )
    include_analytics: bool = Field(
        True,
        description="Include analytics and insights",
    )
    include_charts: bool = Field(
        False,
        description="Include chart data",
    )
    group_by: Union[str, None] = Field(
        None,
        pattern=r"^(day|week|month|payment_type|payment_method|hostel)$",
        description="Group results by this field",
    )

    @model_validator(mode="after")
    def validate_period(self) -> "PaymentReportRequest":
        """Validate report period."""
        if self.period_end < self.period_start:
            raise ValueError(
                f"period_end ({self.period_end}) must be after "
                f"period_start ({self.period_start})"
            )
        
        # Limit report period to prevent performance issues
        days_diff = (self.period_end - self.period_start).days
        if days_diff > 365:
            raise ValueError(
                f"Report period cannot exceed 365 days (got {days_diff} days)"
            )
        
        return self


class PaymentExportRequest(BaseSchema):
    """
    Payment export request.
    
    Used to export payment data in various formats.
    """

    # Export Format
    format: ExportFormat = Field(
        ExportFormat.CSV,
        description="Export format",
    )

    # Filters
    filters: PaymentFilterParams = Field(
        default_factory=PaymentFilterParams,
        description="Filters to apply before export",
    )

    # Sorting
    sort_options: Union[PaymentSortOptions, None] = Field(
        None,
        description="Sorting options",
    )

    # Export Options
    include_headers: bool = Field(
        True,
        description="Include column headers (CSV/Excel)",
    )
    include_summary: bool = Field(
        False,
        description="Include summary sheet (Excel) or section (PDF)",
    )
    fields: Union[List[str], None] = Field(
        None,
        description="Specific fields to include (null = all fields)",
    )

    # Limit
    max_records: int = Field(
        10000,
        ge=1,
        le=50000,
        description="Maximum records to export",
    )

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: Union[List[str], None]) -> Union[List[str], None]:
        """Validate export fields."""
        if v is None:
            return v
        
        if not v:
            raise ValueError("If fields are specified, at least one is required")
        
        # Define allowed fields
        allowed_fields = {
            "payment_reference",
            "transaction_id",
            "payer_name",
            "student_name",
            "hostel_name",
            "payment_type",
            "amount",
            "currency",
            "payment_method",
            "payment_status",
            "paid_at",
            "due_date",
            "created_at",
            "receipt_number",
            "notes",
        }
        
        invalid_fields = set(v) - allowed_fields
        if invalid_fields:
            raise ValueError(
                f"Invalid export fields: {', '.join(invalid_fields)}"
            )
        
        return v


class PaymentAnalyticsRequest(BaseSchema):
    """
    Payment analytics request.
    
    Used to request detailed analytics and insights on payment data.
    """

    # Analysis Period
    period_start: Date = Field(
        ...,
        description="Analysis period start",
    )
    period_end: Date = Field(
        ...,
        description="Analysis period end",
    )

    # Filters
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Analyze specific hostel",
    )
    payment_types: Union[List[PaymentType], None] = Field(
        None,
        description="Filter by payment types",
    )

    # Analytics Options
    include_trends: bool = Field(
        True,
        description="Include trend analysis",
    )
    include_comparisons: bool = Field(
        True,
        description="Include period-over-period comparisons",
    )
    include_forecasts: bool = Field(
        False,
        description="Include forecast projections",
    )
    include_breakdowns: bool = Field(
        True,
        description="Include detailed breakdowns by method/type",
    )

    # Grouping
    granularity: str = Field(
        "day",
        pattern=r"^(day|week|month)$",
        description="Time granularity for trends",
    )

    @model_validator(mode="after")
    def validate_period(self) -> "PaymentAnalyticsRequest":
        """Validate analysis period."""
        if self.period_end < self.period_start:
            raise ValueError(
                f"period_end ({self.period_end}) must be after "
                f"period_start ({self.period_start})"
            )
        
        # Analytics work best with reasonable time periods
        days_diff = (self.period_end - self.period_start).days
        
        if days_diff > 730:  # 2 years
            raise ValueError(
                f"Analysis period cannot exceed 730 days (got {days_diff} days)"
            )
        
        if days_diff < 1:
            raise ValueError("Analysis period must be at least 1 day")
        
        return self