"""
Student filter and search schemas with advanced filtering options.

Provides comprehensive filtering, searching, sorting, and bulk operation
schemas for student management.
"""

from __future__ import annotations

from datetime import date as Date
from typing import List, Optional, Annotated

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseFilterSchema, BaseCreateSchema
from app.schemas.common.enums import StudentStatus

__all__ = [
    "StudentFilterParams",
    "StudentSearchRequest",
    "StudentSortOptions",
    "StudentExportRequest",
    "StudentBulkActionRequest",
    "AdvancedStudentFilters",
]


class StudentFilterParams(BaseFilterSchema):
    """
    Student filter parameters.
    
    Comprehensive filtering options for student queries.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Text search
    search: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Search in name, email, phone, room number",
    )

    # Hostel filter
    hostel_id: Optional[str] = Field(
        default=None,
        description="Filter by single hostel ID",
    )
    hostel_ids: Optional[List[str]] = Field(
        default=None,
        min_length=1,
        max_length=10,
        description="Filter by multiple hostel IDs",
    )

    # Room filter
    room_id: Optional[str] = Field(
        default=None,
        description="Filter by specific room",
    )
    room_number: Optional[str] = Field(
        default=None,
        description="Filter by room number",
    )
    room_type: Optional[str] = Field(
        default=None,
        description="Filter by room type",
    )
    floor_number: Optional[int] = Field(
        default=None,
        ge=0,
        le=50,
        description="Filter by floor number",
    )
    wing: Optional[str] = Field(
        default=None,
        description="Filter by wing/block",
    )

    # Status filter
    status: Optional[StudentStatus] = Field(
        default=None,
        description="Filter by single status",
    )
    statuses: Optional[List[StudentStatus]] = Field(
        default=None,
        min_length=1,
        description="Filter by multiple statuses",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Filter by active status",
    )
    is_checked_in: Optional[bool] = Field(
        default=None,
        description="Filter by check-in status",
    )

    # Date filters
    checked_in_after: Optional[Date] = Field(
        default=None,
        description="Checked in after this Date",
    )
    checked_in_before: Optional[Date] = Field(
        default=None,
        description="Checked in before this Date",
    )
    expected_checkout_after: Optional[Date] = Field(
        default=None,
        description="Expected checkout after this Date",
    )
    expected_checkout_before: Optional[Date] = Field(
        default=None,
        description="Expected checkout before this Date",
    )

    # Financial filters
    has_overdue_payments: Optional[bool] = Field(
        default=None,
        description="Has overdue payments",
    )
    has_advance_balance: Optional[bool] = Field(
        default=None,
        description="Has advance payment balance",
    )
    security_deposit_paid: Optional[bool] = Field(
        default=None,
        description="Security deposit paid status",
    )

    # Meal filter
    mess_subscribed: Optional[bool] = Field(
        default=None,
        description="Subscribed to mess facility",
    )

    # Institutional filters
    institution_name: Optional[str] = Field(
        default=None,
        description="Filter by institution name (partial match)",
    )
    course: Optional[str] = Field(
        default=None,
        description="Filter by course (partial match)",
    )

    # Company filter
    company_name: Optional[str] = Field(
        default=None,
        description="Filter by company name (partial match)",
    )

    # Gender filter
    gender: Optional[str] = Field(
        default=None,
        pattern=r"^(male|female|other)$",
        description="Filter by gender",
    )

    @field_validator("hostel_ids")
    @classmethod
    def validate_unique_hostel_ids(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Ensure hostel IDs are unique."""
        if v is not None and len(v) != len(set(v)):
            raise ValueError("Hostel IDs must be unique")
        return v

    @field_validator("statuses")
    @classmethod
    def validate_unique_statuses(
        cls, v: Optional[List[StudentStatus]]
    ) -> Optional[List[StudentStatus]]:
        """Ensure statuses are unique."""
        if v is not None and len(v) != len(set(v)):
            raise ValueError("Statuses must be unique")
        return v


class StudentSearchRequest(BaseFilterSchema):
    """
    Student search request.
    
    Full-text search with field selection and filters.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    query: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Search query",
    )
    hostel_id: Optional[str] = Field(
        default=None,
        description="Limit search to specific hostel",
    )

    # Search field selection
    search_in_name: bool = Field(
        default=True,
        description="Search in student name",
    )
    search_in_email: bool = Field(
        default=True,
        description="Search in email address",
    )
    search_in_phone: bool = Field(
        default=True,
        description="Search in phone number",
    )
    search_in_room: bool = Field(
        default=True,
        description="Search in room number",
    )
    search_in_institution: bool = Field(
        default=True,
        description="Search in institution name",
    )
    search_in_company: bool = Field(
        default=False,
        description="Search in company name",
    )
    search_in_guardian: bool = Field(
        default=False,
        description="Search in guardian name",
    )

    # Additional filters
    status: Optional[StudentStatus] = Field(
        default=None,
        description="Filter by status",
    )
    only_active: bool = Field(
        default=True,
        description="Only include active students",
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
        description="Results per page",
    )


class StudentSortOptions(BaseFilterSchema):
    """
    Student sorting options.
    
    Defines available sort criteria and order.
    """

    sort_by: str = Field(
        default="created_at",
        pattern=r"^(name|email|room_number|check_in_date|created_at|monthly_rent|status)$",
        description="Field to sort by",
    )
    sort_order: str = Field(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Sort order (ascending/descending)",
    )

    @field_validator("sort_order")
    @classmethod
    def normalize_sort_order(cls, v: str) -> str:
        """Normalize sort order to lowercase."""
        return v.lower()


class AdvancedStudentFilters(BaseFilterSchema):
    """
    Advanced filtering options.
    
    Additional complex filters for detailed queries.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Attendance filters
    min_attendance_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum attendance percentage",
    )
    max_attendance_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Maximum attendance percentage",
    )
    attendance_below_required: Optional[bool] = Field(
        default=None,
        description="Attendance below minimum requirement",
    )

    # Payment behavior
    payment_history: Optional[str] = Field(
        default=None,
        pattern=r"^(good|irregular|poor)$",
        description="Payment history pattern",
    )
    has_pending_complaints: Optional[bool] = Field(
        default=None,
        description="Has open complaints",
    )

    # Duration filters
    min_stay_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum stay duration in days",
    )
    max_stay_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum stay duration in days",
    )

    # Age filters
    min_age: Optional[int] = Field(
        default=None,
        ge=16,
        le=100,
        description="Minimum age",
    )
    max_age: Optional[int] = Field(
        default=None,
        ge=16,
        le=100,
        description="Maximum age",
    )

    # Document verification
    documents_verified: Optional[bool] = Field(
        default=None,
        description="All documents verified",
    )

    @field_validator("max_attendance_percentage")
    @classmethod
    def validate_attendance_range(cls, v: Optional[float], info) -> Optional[float]:
        """Validate attendance percentage range."""
        if v is not None:
            min_att = info.data.get("min_attendance_percentage")
            if min_att is not None and v < min_att:
                raise ValueError(
                    "max_attendance_percentage must be >= min_attendance_percentage"
                )
        return v


class StudentExportRequest(BaseFilterSchema):
    """
    Export students request.
    
    Configures student data export with format and field selection.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    hostel_id: Optional[str] = Field(
        default=None,
        description="Export students from specific hostel",
    )
    filters: Optional[StudentFilterParams] = Field(
        default=None,
        description="Apply filters to export",
    )

    # Export format
    format: str = Field(
        default="csv",
        pattern=r"^(csv|excel|pdf)$",
        description="Export file format",
    )

    # Field selection
    include_financial_data: bool = Field(
        default=False,
        description="Include payment and financial information",
    )
    include_attendance_data: bool = Field(
        default=False,
        description="Include attendance statistics",
    )
    include_guardian_info: bool = Field(
        default=True,
        description="Include guardian information",
    )
    include_institutional_info: bool = Field(
        default=True,
        description="Include college/company information",
    )
    include_contact_details: bool = Field(
        default=True,
        description="Include phone and email",
    )
    include_room_assignment: bool = Field(
        default=True,
        description="Include room and bed details",
    )

    # Additional options
    include_inactive: bool = Field(
        default=False,
        description="Include inactive students",
    )
    include_checkout_students: bool = Field(
        default=False,
        description="Include checked-out students",
    )

    @field_validator("format")
    @classmethod
    def normalize_format(cls, v: str) -> str:
        """Normalize format to lowercase."""
        return v.lower()


class StudentBulkActionRequest(BaseCreateSchema):
    """
    Bulk action on students.
    
    Performs bulk operations on multiple students.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Student IDs (max 100)",
    )
    action: str = Field(
        ...,
        pattern=r"^(activate|deactivate|send_notification|export|change_status|assign_room|update_rent)$",
        description="Action to perform",
    )

    # Action-specific parameters
    new_status: Optional[StudentStatus] = Field(
        default=None,
        description="New status (for change_status action)",
    )
    notification_message: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notification message (for send_notification)",
    )
    notification_title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Notification title",
    )
    new_rent_amount: Optional[float] = Field(
        default=None,
        ge=0,
        description="New rent amount (for update_rent)",
    )
    effective_date: Optional[Date] = Field(
        default=None,
        description="Effective Date for changes",
    )

    # Confirmation
    confirm_action: bool = Field(
        default=False,
        description="Explicit confirmation for bulk action",
    )

    @field_validator("student_ids")
    @classmethod
    def validate_unique_ids(cls, v: List[str]) -> List[str]:
        """Ensure student IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Student IDs must be unique")
        return v

    @field_validator("action")
    @classmethod
    def normalize_action(cls, v: str) -> str:
        """Normalize action to lowercase."""
        return v.lower()

    @model_validator(mode="after")
    def validate_action_parameters(self) -> "StudentBulkActionRequest":
        """Validate action-specific required parameters."""
        if self.action == "change_status" and not self.new_status:
            raise ValueError("new_status is required for change_status action")

        if self.action == "send_notification":
            if not self.notification_message:
                raise ValueError(
                    "notification_message is required for send_notification action"
                )
            if not self.notification_title:
                raise ValueError(
                    "notification_title is required for send_notification action"
                )

        if self.action == "update_rent" and self.new_rent_amount is None:
            raise ValueError("new_rent_amount is required for update_rent action")

        return self