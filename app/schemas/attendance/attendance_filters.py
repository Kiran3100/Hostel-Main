# --- File: app/schemas/attendance/attendance_filters.py ---
"""
Attendance filter schemas for querying and exporting.

Provides comprehensive filtering capabilities with validation
for Date ranges, status filters, and export configurations.
"""

from datetime import date as Date
from typing import List, Union
import re

from pydantic import Field, field_validator, model_validator
from pydantic.types import UUID4 as UUID

from app.schemas.common.base import BaseFilterSchema
from app.schemas.common.enums import AttendanceMode, AttendanceStatus
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "AttendanceFilterParams",
    "DateRangeRequest",
    "AttendanceExportRequest",
]


class AttendanceFilterParams(BaseFilterSchema):
    """
    Comprehensive attendance filter parameters.
    
    Supports multi-dimensional filtering by hostel, student, Date,
    status, and marking metadata.
    """

    # Hostel filters
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Filter by specific hostel",
    )
    hostel_ids: Union[List[UUID], None] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Filter by multiple hostels",
    )

    # Student filters
    student_id: Union[UUID, None] = Field(
        None,
        description="Filter by specific student",
    )
    student_ids: Union[List[UUID], None] = Field(
        None,
        min_length=1,
        max_length=500,
        description="Filter by multiple students",
    )
    room_id: Union[UUID, None] = Field(
        None,
        description="Filter by room",
    )
    room_ids: Union[List[UUID], None] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Filter by multiple rooms",
    )

    # Date range filters
    date_from: Union[Date, None] = Field(
        None,
        description="Start Date (inclusive)",
    )
    date_to: Union[Date, None] = Field(
        None,
        description="End Date (inclusive)",
    )
    specific_date: Union[Date, None] = Field(
        None,
        description="Filter by specific Date",
    )

    # Status filters
    status: Union[AttendanceStatus, None] = Field(
        None,
        description="Filter by specific status",
    )
    statuses: Union[List[AttendanceStatus], None] = Field(
        None,
        min_length=1,
        description="Filter by multiple statuses",
    )
    exclude_statuses: Union[List[AttendanceStatus], None] = Field(
        None,
        min_length=1,
        description="Exclude specific statuses",
    )

    # Late filter
    late_only: Union[bool, None] = Field(
        None,
        description="Filter only late arrivals (True) or exclude late (False)",
    )

    # Marking metadata
    marked_by: Union[UUID, None] = Field(
        None,
        description="Filter by user who marked attendance",
    )
    supervisor_id: Union[UUID, None] = Field(
        None,
        description="Filter by supervisor",
    )
    attendance_mode: Union[AttendanceMode, None] = Field(
        None,
        description="Filter by marking method",
    )

    # Advanced filters
    has_notes: Union[bool, None] = Field(
        None,
        description="Filter records with/without notes",
    )
    has_location: Union[bool, None] = Field(
        None,
        description="Filter records with/without location data",
    )

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v: Union[Date, None], info) -> Union[Date, None]:
        """Validate end Date is after or equal to start Date."""
        if v is not None and info.data.get("date_from"):
            date_from = info.data["date_from"]
            if date_from is not None and v < date_from:
                raise ValueError("date_to must be after or equal to date_from")
        return v

    @model_validator(mode="after")
    def validate_filter_consistency(self) -> "AttendanceFilterParams":
        """
        Validate filter parameter consistency.
        
        Ensures:
        - Date filters are logically consistent
        - List filters are not empty
        - Conflicting filters are not used together
        """
        # Validate specific_date doesn't conflict with range
        if self.specific_date is not None:
            if self.date_from is not None or self.date_to is not None:
                raise ValueError(
                    "Cannot use specific_date with date_from/date_to"
                )

        # Validate status filters
        if self.status is not None and self.statuses is not None:
            raise ValueError(
                "Cannot use both status and statuses filters"
            )

        if self.statuses is not None and self.exclude_statuses is not None:
            overlap = set(self.statuses) & set(self.exclude_statuses)
            if overlap:
                raise ValueError(
                    "Cannot include and exclude the same statuses"
                )

        # Validate student filters
        if self.student_id is not None and self.student_ids is not None:
            raise ValueError(
                "Cannot use both student_id and student_ids filters"
            )

        # Validate hostel filters
        if self.hostel_id is not None and self.hostel_ids is not None:
            raise ValueError(
                "Cannot use both hostel_id and hostel_ids filters"
            )

        return self


class DateRangeRequest(BaseFilterSchema):
    """
    Simple Date range request with validation.
    
    Used for reports and queries requiring Date range specification.
    """

    start_date: Date = Field(
        ...,
        description="Start Date (inclusive)",
    )
    end_date: Date = Field(
        ...,
        description="End Date (inclusive)",
    )

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: Date) -> Date:
        """Ensure start Date is not too far in the past."""
        # Allow up to 5 years of historical data
        max_past_days = 365 * 5
        days_diff = (Date.today() - v).days
        
        if days_diff > max_past_days:
            raise ValueError(
                f"start_date cannot be more than {max_past_days} days in the past"
            )
        
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Date, info) -> Date:
        """
        Validate end Date constraints.
        
        Ensures:
        - End Date is after or equal to start Date
        - End Date is not in future
        - Date range is reasonable (not too large)
        """
        # Validate not in future
        if v > Date.today():
            raise ValueError("end_date cannot be in the future")

        # Validate against start Date
        if info.data.get("start_date"):
            start_date = info.data["start_date"]
            if v < start_date:
                raise ValueError("end_date must be after or equal to start_date")

            # Validate range is not too large (max 1 year)
            days_diff = (v - start_date).days
            if days_diff > 365:
                raise ValueError(
                    "Date range cannot exceed 365 days"
                )

        return v


class AttendanceExportRequest(BaseFilterSchema):
    """
    Export attendance data with format and options.
    
    Supports multiple export formats with customizable content
    and grouping options.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel to export data for",
    )
    date_range: DateRangeFilter = Field(
        ...,
        description="Date range for export",
    )

    # Student filters
    student_ids: Union[List[UUID], None] = Field(
        None,
        max_length=500,
        description="Export specific students only",
    )
    room_ids: Union[List[UUID], None] = Field(
        None,
        max_length=100,
        description="Export specific rooms only",
    )

    # Status filters
    statuses: Union[List[AttendanceStatus], None] = Field(
        None,
        description="Filter by attendance statuses",
    )
    include_late_only: bool = Field(
        False,
        description="Include only late arrivals",
    )

    # Format
    format: str = Field(
        "csv",
        pattern=r"^(csv|excel|pdf)$",
        description="Export format: csv, excel, or pdf",
    )

    # Content options
    include_summary: bool = Field(
        True,
        description="Include summary statistics",
    )
    include_percentage: bool = Field(
        True,
        description="Include attendance percentage calculations",
    )
    include_notes: bool = Field(
        False,
        description="Include notes column",
    )
    include_location: bool = Field(
        False,
        description="Include location data (if available)",
    )
    include_device_info: bool = Field(
        False,
        description="Include device information",
    )

    # Grouping and sorting
    group_by: str = Field(
        "student",
        pattern=r"^(student|Date|room|status)$",
        description="Group records by: student, Date, room, or status",
    )
    sort_by: str = Field(
        "Date",
        pattern=r"^(Date|student_name|room|status)$",
        description="Sort records by field",
    )
    sort_order: str = Field(
        "asc",
        pattern=r"^(asc|desc)$",
        description="Sort order: ascending or descending",
    )

    # Output options
    file_name: Union[str, None] = Field(
        None,
        max_length=255,
        description="Custom filename for export (without extension)",
    )
    include_timestamp: bool = Field(
        True,
        description="Include timestamp in filename",
    )

    @field_validator("file_name")
    @classmethod
    def validate_filename(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate and sanitize filename."""
        if v is not None:
            # Remove invalid characters
            v = re.sub(r'[<>:"/\\|?*]', '', v)
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_export_config(self) -> "AttendanceExportRequest":
        """
        Validate export configuration consistency.
        
        Ensures compatible options are selected based on format.
        """
        # PDF-specific validations
        if self.format == "pdf":
            if self.group_by not in ["student", "Date"]:
                raise ValueError(
                    "PDF format supports only 'student' or 'Date' grouping"
                )

        # Validate Date range
        if self.date_range.start_date and self.date_range.end_date:
            days_diff = (
                self.date_range.end_date - self.date_range.start_date
            ).days
            
            # Large exports might cause performance issues
            if days_diff > 365:
                raise ValueError(
                    "Export Date range cannot exceed 365 days"
                )

        return self