"""
Leave balance and quota management schemas.

Provides schemas for tracking leave entitlements, usage,
and remaining balance with validation.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Union

from pydantic import ConfigDict, Field, computed_field, field_validator
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import LeaveType

__all__ = [
    "LeaveBalance",
    "LeaveBalanceSummary",
    "LeaveQuota",
    "LeaveUsageDetail",
    "LeaveBalanceDetail",
    "LeaveAdjustment",
    "LeaveUsageHistory",
]


class LeaveBalance(BaseSchema):
    """
    Leave balance for a single leave type.
    
    Tracks allocation, usage, and remaining balance for
    a specific leave type.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leave_type": "casual",
                "allocated_per_year": 15,
                "used_days": 5,
                "pending_days": 2,
                "remaining_days": 8,
                "requires_approval": True
            }
        }
    )

    leave_type: LeaveType = Field(
        ...,
        description="Type of leave",
    )
    allocated_per_year: int = Field(
        ...,
        ge=0,
        le=365,
        description="Total days allocated per year",
    )
    allocated_per_semester: Union[int, None] = Field(
        None,
        ge=0,
        le=180,
        description="Days allocated per semester (if applicable)",
    )
    used_days: int = Field(
        ...,
        ge=0,
        description="Days already used/approved",
    )
    pending_days: int = Field(
        default=0,
        ge=0,
        description="Days in pending applications",
    )
    remaining_days: int = Field(
        ...,
        ge=0,
        description="Days remaining available",
    )
    carry_forward_days: int = Field(
        default=0,
        ge=0,
        description="Days carried forward from previous period",
    )
    max_consecutive_days: Union[int, None] = Field(
        None,
        ge=1,
        description="Maximum consecutive days allowed for this leave type",
    )
    requires_approval: bool = Field(
        default=True,
        description="Whether this leave type requires approval",
    )

    @field_validator("remaining_days")
    @classmethod
    def validate_remaining_days(cls, v: int, info) -> int:
        """
        Validate remaining days calculation.
        
        Ensures remaining = allocated + carry_forward - used - pending.
        """
        if "allocated_per_year" in info.data and "used_days" in info.data:
            allocated = info.data["allocated_per_year"]
            used = info.data["used_days"]
            pending = info.data.get("pending_days", 0)
            carry_forward = info.data.get("carry_forward_days", 0)
            
            expected_remaining = allocated + carry_forward - used - pending
            
            # Allow small discrepancies due to rounding
            if abs(expected_remaining - v) > 1:
                raise ValueError(
                    f"remaining_days ({v}) doesn't match calculation "
                    f"({expected_remaining})"
                )
        
        return v

    @computed_field
    @property
    def usage_percentage(self) -> Decimal:
        """Calculate usage percentage."""
        total_available = self.allocated_per_year + self.carry_forward_days
        if total_available == 0:
            return Decimal("0.00")
        
        return round(
            Decimal(self.used_days) / Decimal(total_available) * 100,
            2,
        )

    @computed_field
    @property
    def is_exhausted(self) -> bool:
        """Check if leave balance is exhausted."""
        return self.remaining_days <= 0

    @computed_field
    @property
    def utilization_status(self) -> str:
        """Get utilization status indicator."""
        usage_pct = float(self.usage_percentage)
        
        if usage_pct >= 90:
            return "critical"
        elif usage_pct >= 75:
            return "high"
        elif usage_pct >= 50:
            return "moderate"
        elif usage_pct >= 25:
            return "low"
        else:
            return "minimal"


class LeaveBalanceSummary(BaseSchema):
    """
    Comprehensive leave balance summary for a student.
    
    Aggregates balance information across all leave types
    for a specific academic period.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_name": "John Student",
                "hostel_name": "North Campus Hostel A",
                "total_allocated": 60,
                "total_used": 15,
                "total_remaining": 45,
                "last_updated": "2024-01-15"
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
    room_number: Union[str, None] = Field(
        None,
        description="Room number",
    )

    # Academic period
    academic_year_start: Date = Field(
        ...,
        description="Academic year start Date",
    )
    academic_year_end: Date = Field(
        ...,
        description="Academic year end Date",
    )
    current_semester: Union[str, None] = Field(
        None,
        description="Current semester (if applicable)",
    )

    # Balance breakdown
    balances: List[LeaveBalance] = Field(
        ...,
        min_length=1,
        description="Balance for each leave type",
    )

    # Overall statistics
    total_allocated: int = Field(
        ...,
        ge=0,
        description="Total days allocated across all types",
    )
    total_used: int = Field(
        ...,
        ge=0,
        description="Total days used across all types",
    )
    total_pending: int = Field(
        default=0,
        ge=0,
        description="Total days in pending applications",
    )
    total_remaining: int = Field(
        ...,
        ge=0,
        description="Total days remaining",
    )

    # Last updated
    last_updated: Date = Field(
        ...,
        description="Last balance update Date",
    )

    @field_validator("academic_year_end")
    @classmethod
    def validate_academic_year(cls, v: Date, info) -> Date:
        """Validate academic year dates are logical."""
        if "academic_year_start" in info.data:
            if v <= info.data["academic_year_start"]:
                raise ValueError(
                    "academic_year_end must be after academic_year_start"
                )
        return v

    @computed_field
    @property
    def overall_usage_percentage(self) -> Decimal:
        """Calculate overall usage percentage."""
        if self.total_allocated == 0:
            return Decimal("0.00")
        
        return round(
            Decimal(self.total_used) / Decimal(self.total_allocated) * 100,
            2,
        )

    @computed_field
    @property
    def days_until_year_end(self) -> int:
        """Calculate days remaining in academic year."""
        today = Date.today()
        if today > self.academic_year_end:
            return 0
        return (self.academic_year_end - today).days

    @computed_field
    @property
    def has_pending_applications(self) -> bool:
        """Check if there are pending applications."""
        return self.total_pending > 0


class LeaveQuota(BaseSchema):
    """
    Leave quota configuration for hostel/policy.
    
    Defines leave entitlements and rules for different
    leave types within a hostel.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "leave_type": "casual",
                "annual_quota": 15,
                "max_consecutive_days": 5,
                "min_notice_days": 2,
                "allow_carry_forward": False,
                "is_active": True
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    leave_type: LeaveType = Field(
        ...,
        description="Leave type",
    )
    annual_quota: int = Field(
        ...,
        ge=0,
        le=365,
        description="Annual leave quota in days",
    )
    semester_quota: Union[int, None] = Field(
        None,
        ge=0,
        le=180,
        description="Semester quota (if applicable)",
    )
    monthly_quota: Union[int, None] = Field(
        None,
        ge=0,
        le=31,
        description="Monthly quota (if applicable)",
    )
    max_consecutive_days: int = Field(
        ...,
        ge=1,
        le=90,
        description="Maximum consecutive days allowed",
    )
    min_notice_days: int = Field(
        default=0,
        ge=0,
        le=30,
        description="Minimum advance notice required (days)",
    )
    requires_document_after_days: Union[int, None] = Field(
        None,
        ge=1,
        description="Requires supporting document after N days",
    )
    allow_carry_forward: bool = Field(
        default=False,
        description="Allow unused quota to carry forward",
    )
    carry_forward_max_days: Union[int, None] = Field(
        None,
        ge=0,
        description="Maximum days that can be carried forward",
    )
    carry_forward_expiry_months: Union[int, None] = Field(
        None,
        ge=1,
        le=12,
        description="Months after which carried forward days expire",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this quota is currently active",
    )

    @field_validator("carry_forward_max_days")
    @classmethod
    def validate_carry_forward(cls, v: Union[int, None], info) -> Union[int, None]:
        """Validate carry forward configuration."""
        if v is not None:
            if not info.data.get("allow_carry_forward"):
                raise ValueError(
                    "carry_forward_max_days should only be set when allow_carry_forward is True"
                )
        return v


class LeaveUsageDetail(BaseSchema):
    """
    Detailed leave usage record for reporting.
    
    Provides granular information about leave consumption
    for analytics and reporting.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "leave_id": "123e4567-e89b-12d3-a456-426614174001",
                "leave_type": "casual",
                "from_date": "2024-01-10",
                "to_date": "2024-01-12",
                "total_days": 3,
                "days_notice": 5,
                "was_backdated": False
            }
        }
    )

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    leave_id: UUID = Field(
        ...,
        description="Leave application unique identifier",
    )
    leave_type: LeaveType = Field(
        ...,
        description="Leave type",
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
        ge=1,
        description="Total leave days",
    )
    applied_at: Date = Field(
        ...,
        description="Application Date",
    )
    approved_at: Union[Date, None] = Field(
        None,
        description="Approval Date",
    )
    days_notice: int = Field(
        ...,
        ge=0,
        description="Days notice given before leave start",
    )
    was_backdated: bool = Field(
        default=False,
        description="Whether application was backdated",
    )
    had_supporting_document: bool = Field(
        default=False,
        description="Whether supporting document was provided",
    )

    @computed_field
    @property
    def approval_turnaround_days(self) -> Union[int, None]:
        """Calculate days taken for approval."""
        if self.approved_at is None:
            return None
        return (self.approved_at - self.applied_at).days


class LeaveBalanceDetail(BaseSchema):
    """
    Detailed balance information for a specific leave type.
    
    Comprehensive view of balance, usage, and policies for one leave type.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "leave_type": "casual",
                "allocated_days": 15,
                "used_days": 5,
                "pending_days": 2,
                "remaining_days": 8,
                "expires_at": "2024-12-31"
            }
        }
    )

    student_id: UUID = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    leave_type: LeaveType = Field(..., description="Leave type")
    allocated_days: int = Field(..., description="Total allocated days")
    used_days: int = Field(..., description="Days used")
    pending_days: int = Field(..., description="Days in pending applications")
    remaining_days: int = Field(..., description="Days remaining")
    carry_forward_days: int = Field(default=0, description="Carried forward from previous year")
    expires_at: Union[datetime, None] = Field(None, description="Balance expiry date")
    last_used_date: Union[datetime, None] = Field(None, description="Last leave date")
    next_allocation_date: Union[datetime, None] = Field(None, description="Next allocation date")


class LeaveAdjustment(BaseSchema):
    """
    Manual balance adjustment record for audit trail.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "adjustment_id": "123e4567-e89b-12d3-a456-426614174000",
                "student_id": "123e4567-e89b-12d3-a456-426614174001",
                "leave_type": "casual",
                "adjustment_days": 5,
                "reason": "Special allocation for project work",
                "performed_by": "Admin User",
                "performed_at": "2024-01-15T14:30:00Z"
            }
        }
    )

    adjustment_id: UUID = Field(..., description="Adjustment record ID")
    student_id: UUID = Field(..., description="Student ID")
    leave_type: LeaveType = Field(..., description="Leave type adjusted")
    adjustment_days: int = Field(..., description="Days adjusted (positive or negative)")
    reason: str = Field(..., description="Reason for adjustment")
    reference: Union[str, None] = Field(None, description="Reference document/number")
    previous_balance: int = Field(..., description="Balance before adjustment")
    new_balance: int = Field(..., description="Balance after adjustment")
    performed_by: str = Field(..., description="User who made adjustment")
    performed_by_id: UUID = Field(..., description="User ID who made adjustment")
    performed_at: datetime = Field(..., description="Adjustment timestamp")


class LeaveUsageHistory(BaseSchema):
    """
    Paginated leave usage history with metadata.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "usage_records": [],
                "total_count": 25,
                "page": 1,
                "page_size": 10
            }
        }
    )

    student_id: UUID = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    usage_records: List[LeaveUsageDetail] = Field(..., description="Usage details")
    total_count: int = Field(..., description="Total usage records")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Records per page")
    total_pages: int = Field(..., description="Total pages")
    period_start: Union[datetime, None] = Field(None, description="Query period start")
    period_end: Union[datetime, None] = Field(None, description="Query period end")