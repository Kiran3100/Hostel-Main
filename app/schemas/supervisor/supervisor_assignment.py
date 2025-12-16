# --- File: app/schemas/supervisor/supervisor_assignment.py ---
"""
Supervisor assignment schemas with enhanced validation.

Manages supervisor-hostel assignments with proper tracking,
permission management, and transfer handling.
"""

from datetime import datetime, timedelta, date as Date
from typing import Union
from decimal import Decimal

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import PermissionLevel

__all__ = [
    "SupervisorAssignment",
    "AssignmentRequest",
    "AssignmentUpdate",
    "RevokeAssignmentRequest",
    "AssignmentTransfer",
    "AssignmentSummary",
]


class SupervisorAssignment(BaseResponseSchema):
    """
    Supervisor-hostel assignment response.
    
    Complete assignment information with metadata.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    supervisor_email: str = Field(..., description="Supervisor email")
    
    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    assigned_by: str = Field(..., description="Admin who assigned")
    assigned_by_name: str = Field(..., description="Admin name")
    assigned_date: Date = Field(..., description="Assignment Date")
    
    is_active: bool = Field(..., description="Assignment is active")
    
    # Permission summary
    permission_level: str = Field(
        ...,
        description="Summary of permission level",
        examples=["Full Access", "Standard Access", "Limited Access"],
    )
    
    # Activity tracking
    last_active: Union[datetime, None] = Field(
        default=None,
        description="Last activity timestamp",
    )
    total_days_assigned: int = Field(
        default=0,
        ge=0,
        description="Total days in current assignment",
    )

    @computed_field
    @property
    def assignment_duration_months(self) -> int:
        """Calculate assignment duration in months."""
        return self.total_days_assigned // 30


class AssignmentRequest(BaseCreateSchema):
    """
    Request to assign supervisor to hostel.
    
    Creates new supervisor-hostel assignment with employment details.
    """

    user_id: str = Field(
        ...,
        description="User ID to assign as supervisor",
    )
    hostel_id: str = Field(
        ...,
        description="Hostel ID",
    )
    
    # Employment details
    employee_id: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Employee/Staff ID",
    )
    join_date: Date = Field(
        ...,
        description="Joining Date",
    )
    employment_type: str = Field(
        default="full_time",
        pattern=r"^(full_time|part_time|contract)$",
        description="Employment type",
    )
    shift_timing: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Shift timing",
    )
    
    # Permissions (optional, will use defaults)
    permissions: Union[dict, None] = Field(
        default=None,
        description="Custom permissions (uses template defaults if not provided)",
    )
    permission_template: Union[str, None] = Field(
        default="junior_supervisor",
        description="Permission template to apply",
    )

    @field_validator("join_date")
    @classmethod
    def validate_join_date(cls, v: Date) -> Date:
        """Validate join Date is reasonable."""
        today = Date.today()
        
        # Allow up to 30 days in future for scheduled assignments
        if v > today + timedelta(days=30):
            raise ValueError("Join Date cannot be more than 30 days in the future")
        
        # Allow up to 1 year in past for historical data entry
        if v < today - timedelta(days=365):
            raise ValueError("Join Date cannot be more than 1 year in the past")
        
        return v

    @field_validator("employment_type")
    @classmethod
    def normalize_employment_type(cls, v: str) -> str:
        """Normalize employment type to lowercase."""
        return v.lower().strip()


class AssignmentUpdate(BaseUpdateSchema):
    """
    Update supervisor assignment details.
    
    Allows modification of employment details and assignment status.
    """

    employee_id: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Employee ID",
    )
    employment_type: Union[str, None] = Field(
        default=None,
        pattern=r"^(full_time|part_time|contract)$",
        description="Employment type",
    )
    shift_timing: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Shift timing",
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Assignment active status",
    )
    
    # Permission updates
    permissions: Union[dict, None] = Field(
        default=None,
        description="Updated permissions",
    )

    @field_validator("employment_type")
    @classmethod
    def normalize_employment_type(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize employment type."""
        return v.lower().strip() if v else None


class RevokeAssignmentRequest(BaseCreateSchema):
    """
    Revoke supervisor assignment.
    
    Handles assignment revocation with handover support.
    """

    supervisor_id: str = Field(
        ...,
        description="Supervisor ID",
    )
    revoke_date: Date = Field(
        ...,
        description="Effective revocation Date",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for revocation",
    )
    
    # Handover
    handover_to_supervisor_id: Union[str, None] = Field(
        default=None,
        description="Transfer responsibilities to another supervisor",
    )
    handover_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Handover instructions",
    )
    handover_period_days: int = Field(
        default=7,
        ge=0,
        le=30,
        description="Handover period in days",
    )

    @field_validator("revoke_date")
    @classmethod
    def validate_revoke_date(cls, v: Date) -> Date:
        """Validate revocation Date."""
        today = Date.today()
        
        # Can't revoke in past (except today)
        if v < today:
            raise ValueError("Revoke Date cannot be in the past")
        
        # Limit future revocation
        if v > today + timedelta(days=90):
            raise ValueError("Revoke Date cannot be more than 90 days in future")
        
        return v

    @model_validator(mode="after")
    def validate_handover_consistency(self) -> "RevokeAssignmentRequest":
        """Validate handover requirements."""
        if self.handover_to_supervisor_id:
            if not self.handover_notes:
                raise ValueError(
                    "handover_notes required when transferring to another supervisor"
                )
        
        return self


class AssignmentTransfer(BaseCreateSchema):
    """
    Transfer supervisor to different hostel.
    
    Manages supervisor reassignment between hostels with permission handling.
    """

    supervisor_id: str = Field(
        ...,
        description="Supervisor ID",
    )
    from_hostel_id: str = Field(
        ...,
        description="Current hostel",
    )
    to_hostel_id: str = Field(
        ...,
        description="New hostel",
    )
    transfer_date: Date = Field(
        ...,
        description="Transfer effective Date",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Transfer reason",
    )
    
    # Permission handling
    retain_permissions: bool = Field(
        default=True,
        description="Keep same permission set",
    )
    new_permissions: Union[dict, None] = Field(
        default=None,
        description="New permissions if not retaining",
    )
    permission_template: Union[str, None] = Field(
        default=None,
        description="Permission template to apply at new hostel",
    )

    @field_validator("transfer_date")
    @classmethod
    def validate_transfer_date(cls, v: Date) -> Date:
        """Validate transfer Date."""
        today = Date.today()
        
        if v < today:
            raise ValueError("Transfer Date cannot be in the past")
        
        if v > today + timedelta(days=90):
            raise ValueError("Transfer Date cannot be more than 90 days in future")
        
        return v

    @model_validator(mode="after")
    def validate_transfer_logic(self) -> "AssignmentTransfer":
        """Validate transfer business logic."""
        # Different hostels required
        if self.from_hostel_id == self.to_hostel_id:
            raise ValueError("from_hostel_id and to_hostel_id must be different")
        
        # Permission configuration
        if not self.retain_permissions:
            if not self.new_permissions and not self.permission_template:
                raise ValueError(
                    "Must provide new_permissions or permission_template "
                    "when not retaining permissions"
                )
        
        return self


class AssignmentSummary(BaseSchema):
    """
    Assignment summary for reporting.
    
    Aggregated assignment information for dashboards and reports.
    """

    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Assignment counts
    total_supervisors: int = Field(
        default=0,
        ge=0,
        description="Total assigned supervisors",
    )
    active_supervisors: int = Field(
        default=0,
        ge=0,
        description="Currently active supervisors",
    )
    on_leave_supervisors: int = Field(
        default=0,
        ge=0,
        description="Supervisors on leave",
    )
    
    # Activity metrics
    supervisors_online_now: int = Field(
        default=0,
        ge=0,
        description="Currently online",
    )
    supervisors_active_today: int = Field(
        default=0,
        ge=0,
        description="Active today",
    )
    
    # Performance summary
    average_performance_rating: Union[Decimal, None] = Field(
        default=None,
        ge=0,
        le=5,
        description="Average performance rating",
    )
    
    # Coverage
    shift_coverage: dict = Field(
        default_factory=dict,
        description="Coverage by shift",
    )

    @computed_field
    @property
    def active_percentage(self) -> Decimal:
        """Calculate percentage of active supervisors."""
        if self.total_supervisors == 0:
            return Decimal("100.00")
        
        rate = (self.active_supervisors / self.total_supervisors * 100)
        return Decimal(str(rate)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def needs_coverage(self) -> bool:
        """Check if hostel needs more supervisor coverage."""
        return self.active_supervisors < 1