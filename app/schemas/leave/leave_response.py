"""
Leave response schemas for API responses.

Provides various response formats for leave data including
detailed, summary, and list views with computed fields.
"""

from datetime import date as Date, datetime
from typing import List, Union

from pydantic import ConfigDict, Field, computed_field
from uuid import UUID

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import LeaveStatus, LeaveType

__all__ = [
    "LeaveResponse",
    "LeaveDetail",
    "LeaveListItem",
    "LeaveSummary",
    "PaginatedLeaveResponse",
]


class LeaveResponse(BaseResponseSchema):
    """
    Standard leave response with essential information.
    
    Lightweight response schema for list views and basic queries.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "student_id": "123e4567-e89b-12d3-a456-426614174001",
                "student_name": "John Student",
                "hostel_name": "North Campus Hostel A",
                "leave_type": "casual",
                "from_date": "2024-02-01",
                "to_date": "2024-02-05",
                "total_days": 5,
                "status": "approved"
            }
        }
    )

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    leave_type: LeaveType = Field(
        ...,
        description="Type of leave",
    )
    from_date: Date = Field(
        ...,
        description="Leave start Date",
    )
    to_date: Date = Field(
        ...,
        description="Leave end Date",
    )
    total_days: int = Field(
        ...,
        description="Total leave days",
    )
    status: LeaveStatus = Field(
        ...,
        description="Current leave status",
    )
    applied_at: datetime = Field(
        ...,
        description="Application submission timestamp",
    )
    reason: Union[str, None] = Field(
        None,
        description="Leave reason (truncated for list view)",
    )

    @computed_field
    @property
    def status_display(self) -> str:
        """Human-readable status display."""
        status_map = {
            LeaveStatus.PENDING: "Pending Approval",
            LeaveStatus.APPROVED: "Approved",
            LeaveStatus.REJECTED: "Rejected",
            LeaveStatus.CANCELLED: "Cancelled",
        }
        return status_map.get(self.status, self.status.value)

    @computed_field
    @property
    def leave_type_display(self) -> str:
        """Human-readable leave type display."""
        type_map = {
            LeaveType.CASUAL: "Casual Leave",
            LeaveType.SICK: "Sick Leave",
            LeaveType.EMERGENCY: "Emergency Leave",
            LeaveType.VACATION: "Vacation",
            LeaveType.OTHER: "Other",
        }
        return type_map.get(self.leave_type, self.leave_type.value)

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if leave is currently active."""
        if self.status != LeaveStatus.APPROVED:
            return False
        
        today = Date.today()
        return self.from_date <= today <= self.to_date

    @computed_field
    @property
    def days_remaining(self) -> Union[int, None]:
        """Calculate remaining days for active leave."""
        if not self.is_active:
            return None
        
        return (self.to_date - Date.today()).days + 1


class LeaveDetail(BaseResponseSchema):
    """
    Detailed leave information with complete metadata.
    
    Comprehensive response including all leave details, approval workflow,
    and supporting information.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "student_id": "123e4567-e89b-12d3-a456-426614174001",
                "student_name": "John Student",
                "hostel_name": "North Campus Hostel A",
                "leave_type": "casual",
                "from_date": "2024-02-01",
                "to_date": "2024-02-05",
                "total_days": 5,
                "reason": "Family function - attending cousin's wedding ceremony",
                "status": "approved"
            }
        }
    )

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    student_email: Union[str, None] = Field(
        None,
        description="Student email address",
    )
    student_phone: Union[str, None] = Field(
        None,
        description="Student phone number",
    )
    student_room: Union[str, None] = Field(
        None,
        description="Student room number",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    # Leave details
    leave_type: LeaveType = Field(
        ...,
        description="Type of leave",
    )
    from_date: Date = Field(
        ...,
        description="Leave start Date",
    )
    to_date: Date = Field(
        ...,
        description="Leave end Date",
    )
    total_days: int = Field(
        ...,
        description="Total leave days",
    )
    reason: str = Field(
        ...,
        description="Detailed leave reason",
    )

    # Contact information
    contact_during_leave: Union[str, None] = Field(
        None,
        description="Contact number during leave",
    )
    emergency_contact: Union[str, None] = Field(
        None,
        description="Emergency contact number",
    )
    emergency_contact_relation: Union[str, None] = Field(
        None,
        description="Relation with emergency contact",
    )
    destination_address: Union[str, None] = Field(
        None,
        description="Destination address",
    )

    # Supporting documents
    supporting_document_url: Union[str, None] = Field(
        None,
        description="Supporting document URL",
    )

    # Status and workflow
    status: LeaveStatus = Field(
        ...,
        description="Current leave status",
    )
    applied_at: datetime = Field(
        ...,
        description="Application submission timestamp",
    )

    # Approval details
    approved_at: Union[datetime, None] = Field(
        None,
        description="Approval timestamp",
    )
    approved_by: Union[UUID, None] = Field(
        None,
        description="Approver user ID",
    )
    approved_by_name: Union[str, None] = Field(
        None,
        description="Approver name",
    )
    approval_notes: Union[str, None] = Field(
        None,
        description="Approval notes",
    )
    conditions: Union[str, None] = Field(
        None,
        description="Approval conditions",
    )

    # Rejection details
    rejected_at: Union[datetime, None] = Field(
        None,
        description="Rejection timestamp",
    )
    rejected_by: Union[UUID, None] = Field(
        None,
        description="Rejector user ID",
    )
    rejected_by_name: Union[str, None] = Field(
        None,
        description="Rejector name",
    )
    rejection_reason: Union[str, None] = Field(
        None,
        description="Rejection reason",
    )

    # Cancellation details
    cancelled_at: Union[datetime, None] = Field(
        None,
        description="Cancellation timestamp",
    )
    cancelled_by: Union[UUID, None] = Field(
        None,
        description="User who cancelled",
    )
    cancellation_reason: Union[str, None] = Field(
        None,
        description="Cancellation reason",
    )

    # Additional metadata
    last_modified_at: Union[datetime, None] = Field(
        None,
        description="Last modification timestamp",
    )
    last_modified_by: Union[UUID, None] = Field(
        None,
        description="Last modifier user ID",
    )

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if leave is currently active."""
        if self.status != LeaveStatus.APPROVED:
            return False
        
        today = Date.today()
        return self.from_date <= today <= self.to_date

    @computed_field
    @property
    def is_upcoming(self) -> bool:
        """Check if leave is upcoming."""
        if self.status != LeaveStatus.APPROVED:
            return False
        
        return self.from_date > Date.today()

    @computed_field
    @property
    def is_past(self) -> bool:
        """Check if leave is in the past."""
        return self.to_date < Date.today()

    @computed_field
    @property
    def can_be_cancelled(self) -> bool:
        """Check if leave can be cancelled by student."""
        # Can only cancel pending or approved (future/ongoing) leaves
        if self.status not in [LeaveStatus.PENDING, LeaveStatus.APPROVED]:
            return False
        
        # Can't cancel past leaves
        if self.is_past:
            return False
        
        return True


class LeaveListItem(BaseSchema):
    """
    Minimal leave list item for efficient list rendering.
    
    Optimized for pagination and list views with minimal data transfer.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "student_id": "123e4567-e89b-12d3-a456-426614174001",
                "student_name": "John Student",
                "room_number": "101",
                "leave_type": "casual",
                "from_date": "2024-02-01",
                "to_date": "2024-02-05",
                "total_days": 5,
                "status": "pending"
            }
        }
    )

    id: UUID = Field(
        ...,
        description="Leave application unique identifier",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student name",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Room number",
    )
    leave_type: LeaveType = Field(
        ...,
        description="Leave type",
    )
    from_date: Date = Field(
        ...,
        description="Start Date",
    )
    to_date: Date = Field(
        ...,
        description="End Date",
    )
    total_days: int = Field(
        ...,
        description="Total days",
    )
    status: LeaveStatus = Field(
        ...,
        description="Leave status",
    )
    applied_at: datetime = Field(
        ...,
        description="Application Date",
    )

    @computed_field
    @property
    def status_badge_color(self) -> str:
        """Get color code for status badge (for UI rendering)."""
        color_map = {
            LeaveStatus.PENDING: "yellow",
            LeaveStatus.APPROVED: "green",
            LeaveStatus.REJECTED: "red",
            LeaveStatus.CANCELLED: "gray",
        }
        return color_map.get(self.status, "gray")

    @computed_field
    @property
    def is_urgent(self) -> bool:
        """Check if leave requires urgent attention."""
        # Pending leaves starting soon are urgent
        if self.status == LeaveStatus.PENDING:
            days_until_start = (self.from_date - Date.today()).days
            return days_until_start <= 2
        return False


class LeaveSummary(BaseSchema):
    """
    Leave summary statistics for dashboard.
    
    Provides aggregated view of leave status for reporting.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
                "total_applications": 150,
                "pending_count": 10,
                "approved_count": 120,
                "rejected_count": 15,
                "cancelled_count": 5,
                "total_days_requested": 500,
                "total_days_approved": 400
            }
        }
    )

    student_id: Union[UUID, None] = Field(
        None,
        description="Student ID (if student-specific summary)",
    )
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel ID (if hostel-specific summary)",
    )
    period_start: Date = Field(
        ...,
        description="Summary period start Date",
    )
    period_end: Date = Field(
        ...,
        description="Summary period end Date",
    )

    # Count by status
    total_applications: int = Field(
        ...,
        ge=0,
        description="Total leave applications",
    )
    pending_count: int = Field(
        ...,
        ge=0,
        description="Pending applications",
    )
    approved_count: int = Field(
        ...,
        ge=0,
        description="Approved applications",
    )
    rejected_count: int = Field(
        ...,
        ge=0,
        description="Rejected applications",
    )
    cancelled_count: int = Field(
        ...,
        ge=0,
        description="Cancelled applications",
    )

    # Count by type
    casual_count: int = Field(
        default=0,
        ge=0,
        description="Casual leave count",
    )
    sick_count: int = Field(
        default=0,
        ge=0,
        description="Sick leave count",
    )
    emergency_count: int = Field(
        default=0,
        ge=0,
        description="Emergency leave count",
    )
    vacation_count: int = Field(
        default=0,
        ge=0,
        description="Vacation count",
    )

    # Day statistics
    total_days_requested: int = Field(
        ...,
        ge=0,
        description="Total days requested across all applications",
    )
    total_days_approved: int = Field(
        ...,
        ge=0,
        description="Total days approved",
    )
    active_leaves: int = Field(
        default=0,
        ge=0,
        description="Currently active leaves",
    )

    @computed_field
    @property
    def approval_rate(self) -> float:
        """Calculate approval rate percentage."""
        total_decided = self.approved_count + self.rejected_count
        if total_decided == 0:
            return 0.0
        return round((self.approved_count / total_decided) * 100, 2)


class PaginatedLeaveResponse(BaseSchema):
    """
    Paginated response for leave application listings.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 150,
                "page": 1,
                "page_size": 20,
                "total_pages": 8,
                "has_next": True,
                "has_prev": False
            }
        }
    )

    items: List[LeaveListItem] = Field(..., description="Leave applications for current page")
    total: int = Field(..., description="Total number of applications")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    filters_applied: Union[dict, None] = Field(None, description="Applied filters")