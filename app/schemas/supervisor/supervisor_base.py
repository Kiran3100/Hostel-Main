# --- File: app/schemas/supervisor/supervisor_base.py ---
"""
Supervisor base schemas with enhanced validation and type safety.

Provides core supervisor management schemas including creation, updates,
status management, and hostel reassignment with comprehensive validation.
"""

from datetime import date as Date, timedelta
from decimal import Decimal
from typing import Dict, Union, Annotated

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import EmploymentType, SupervisorStatus

__all__ = [
    "SupervisorBase",
    "SupervisorCreate",
    "SupervisorUpdate",
    "SupervisorStatusUpdate",
    "SupervisorReassignment",
    "SupervisorTermination",
]


# Constants for validation
class SupervisorValidationConstants:
    """Centralized validation constants for supervisor operations."""
    
    MAX_FUTURE_JOIN_DAYS = 30
    MAX_PAST_JOIN_YEARS = 50
    MIN_HANDOVER_PERIOD_DAYS = 0
    MAX_HANDOVER_PERIOD_DAYS = 30
    MAX_FUTURE_EFFECTIVE_DAYS = 30
    MAX_PAST_EFFECTIVE_DAYS = 7
    MAX_FUTURE_REASSIGNMENT_DAYS = 90
    MAX_FUTURE_TERMINATION_DAYS = 90
    MAX_PAST_TERMINATION_DAYS = 30
    MIN_REASON_LENGTH = 10
    MAX_REASON_LENGTH = 500
    MAX_NOTES_LENGTH = 1000
    MAX_EMPLOYEE_ID_LENGTH = 100
    MAX_DESIGNATION_LENGTH = 100
    MAX_SHIFT_TIMING_LENGTH = 100
    MIN_SALARY = 0
    MAX_PROBATION_MONTHS = 3


# Define a custom type for Decimal with precision constraints
DecimalWithPrecision = Annotated[Decimal, Field(decimal_places=2)]


class SupervisorBase(BaseSchema):
    """
    Base supervisor schema with core attributes.
    
    Contains common fields shared across supervisor operations including
    employment details and assignment information.
    """

    user_id: str = Field(
        ...,
        description="Associated user account ID",
    )
    assigned_hostel_id: str = Field(
        ...,
        description="Currently assigned hostel ID",
    )

    # Employment details
    employee_id: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_EMPLOYEE_ID_LENGTH,
        description="Employee/Staff ID number",
        examples=["EMP001", "SUP-2024-001"],
    )
    join_date: Date = Field(
        ...,
        description="Joining/start Date",
    )
    employment_type: EmploymentType = Field(
        default=EmploymentType.FULL_TIME,
        description="Employment type/contract",
    )
    shift_timing: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_SHIFT_TIMING_LENGTH,
        description="Shift timing or working hours",
        examples=["9 AM - 6 PM", "Morning Shift", "24x7 Rotating"],
    )
    designation: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_DESIGNATION_LENGTH,
        description="Job designation/title",
        examples=["Hostel Supervisor", "Senior Supervisor", "Floor Supervisor"],
    )
    salary: Union[DecimalWithPrecision, None] = Field(
        default=None,
        ge=SupervisorValidationConstants.MIN_SALARY,
        description="Monthly salary (confidential)",
    )

    @field_validator("employee_id", "shift_timing", "designation")
    @classmethod
    def normalize_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """
        Normalize text fields by trimming and cleaning whitespace.
        
        Args:
            v: Input string value
            
        Returns:
            Normalized string or None if empty
        """
        if v is None:
            return None
        
        v = v.strip()
        if not v:
            return None
        
        # Remove excessive whitespace while preserving single spaces
        normalized = " ".join(v.split())
        
        return normalized

    @field_validator("join_date")
    @classmethod
    def validate_join_date(cls, v: Date) -> Date:
        """
        Validate join Date is within reasonable bounds.
        
        Args:
            v: Join Date to validate
            
        Returns:
            Validated join Date
            
        Raises:
            ValueError: If Date is outside acceptable range
        """
        today = Date.today()
        
        # Future Date validation
        max_future = today + timedelta(days=SupervisorValidationConstants.MAX_FUTURE_JOIN_DAYS)
        if v > max_future:
            raise ValueError(
                f"Join Date cannot be more than {SupervisorValidationConstants.MAX_FUTURE_JOIN_DAYS} days in the future"
            )
        
        # Past Date validation
        max_past = today - timedelta(days=365 * SupervisorValidationConstants.MAX_PAST_JOIN_YEARS)
        if v < max_past:
            raise ValueError(
                f"Join Date cannot be more than {SupervisorValidationConstants.MAX_PAST_JOIN_YEARS} years in the past"
            )
        
        return v

    @model_validator(mode="after")
    def validate_employment_consistency(self) -> "SupervisorBase":
        """
        Validate employment data consistency.
        
        Returns:
            Self with validated data
        """
        # Contract employees should have employee_id
        if self.employment_type == EmploymentType.CONTRACT and not self.employee_id:
            # Warning only - don't enforce
            pass
        
        return self


class SupervisorCreate(SupervisorBase, BaseCreateSchema):
    """
    Schema for creating a new supervisor.
    
    Used when assigning a user as supervisor to a hostel.
    Includes assignment tracking and initial permission configuration.
    """

    user_id: str = Field(
        ...,
        description="User ID to assign as supervisor (required)",
    )
    assigned_hostel_id: str = Field(
        ...,
        description="Hostel ID to assign supervisor to (required)",
    )
    join_date: Date = Field(
        ...,
        description="Joining Date (required)",
    )
    assigned_by: str = Field(
        ...,
        description="Admin user ID who is assigning the supervisor",
    )

    # Initial permissions (optional, defaults will be applied)
    permissions: Union[Dict[str, Union[bool, int, Decimal]], None] = Field(
        default=None,
        description="Initial permission settings (uses defaults if not provided)",
    )
    
    # Assignment metadata
    assignment_notes: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_NOTES_LENGTH,
        description="Notes about the assignment",
    )

    @field_validator("permissions")
    @classmethod
    def validate_permissions_structure(
        cls, 
        v: Union[Dict[str, Union[bool, int, Decimal]], None]
    ) -> Union[Dict[str, Union[bool, int, Decimal]], None]:
        """
        Validate permissions dictionary structure.
        
        Args:
            v: Permissions dictionary
            
        Returns:
            Validated permissions
        """
        if v is None:
            return None
        
        # Ensure all values are of correct types
        for key, value in v.items():
            if not isinstance(value, (bool, int, float, Decimal)):
                raise ValueError(
                    f"Permission '{key}' has invalid value type. "
                    f"Expected bool, int, or Decimal, got {type(value).__name__}"
                )
        
        return v


class SupervisorUpdate(BaseUpdateSchema):
    """
    Schema for updating supervisor information.
    
    All fields are optional for partial updates.
    Includes permission updates and status changes.
    """

    # Employment details
    employee_id: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_EMPLOYEE_ID_LENGTH,
        description="Employee ID",
    )
    employment_type: Union[EmploymentType, None] = Field(
        default=None,
        description="Employment type",
    )
    shift_timing: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_SHIFT_TIMING_LENGTH,
        description="Shift timing",
    )
    designation: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_DESIGNATION_LENGTH,
        description="Designation",
    )
    salary: Union[DecimalWithPrecision, None] = Field(
        default=None,
        ge=SupervisorValidationConstants.MIN_SALARY,
        description="Monthly salary",
    )

    # Status
    status: Union[SupervisorStatus, None] = Field(
        default=None,
        description="Supervisor status",
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Active status",
    )

    # Permissions
    permissions: Union[Dict[str, Union[bool, int, Decimal]], None] = Field(
        default=None,
        description="Updated permission settings",
    )

    # Notes
    notes: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_NOTES_LENGTH,
        description="Additional notes",
    )

    @field_validator("employee_id", "shift_timing", "designation")
    @classmethod
    def normalize_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is None:
            return None
        
        v = v.strip()
        if not v:
            return None
        
        return " ".join(v.split())

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "SupervisorUpdate":
        """
        Validate status and is_active consistency.
        
        Returns:
            Self with validated data
        """
        # If setting to inactive status, ensure is_active is False
        if self.status in [SupervisorStatus.TERMINATED, SupervisorStatus.SUSPENDED]:
            if self.is_active is True:
                raise ValueError(
                    f"Cannot set is_active=True when status is {self.status.value}"
                )
        
        return self


class SupervisorStatusUpdate(BaseUpdateSchema):
    """
    Schema for updating supervisor status.
    
    Handles status transitions with proper documentation and validation.
    Supports termination, suspension, and leave management.
    """

    status: SupervisorStatus = Field(
        ...,
        description="New supervisor status",
    )
    is_active: bool = Field(
        ...,
        description="Active status (false for terminated/suspended)",
    )
    effective_date: Date = Field(
        ...,
        description="Status change effective Date",
    )
    reason: str = Field(
        ...,
        min_length=SupervisorValidationConstants.MIN_REASON_LENGTH,
        max_length=SupervisorValidationConstants.MAX_REASON_LENGTH,
        description="Reason for status change",
    )

    # Termination-specific fields
    termination_date: Union[Date, None] = Field(
        default=None,
        description="Termination Date (required if status is TERMINATED)",
    )
    termination_reason: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_REASON_LENGTH,
        description="Detailed termination reason",
    )
    eligible_for_rehire: Union[bool, None] = Field(
        default=None,
        description="Eligible for rehire in future",
    )

    # Suspension-specific fields
    suspension_start_date: Union[Date, None] = Field(
        default=None,
        description="Suspension start Date (required if SUSPENDED)",
    )
    suspension_end_date: Union[Date, None] = Field(
        default=None,
        description="Expected suspension end Date (required if SUSPENDED)",
    )
    suspension_reason: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_REASON_LENGTH,
        description="Detailed suspension reason",
    )

    # Leave-specific fields
    leave_start_date: Union[Date, None] = Field(
        default=None,
        description="Leave start Date (required if ON_LEAVE)",
    )
    leave_end_date: Union[Date, None] = Field(
        default=None,
        description="Expected return Date from leave (required if ON_LEAVE)",
    )
    leave_type: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Type of leave (sick, vacation, etc.)",
    )

    # Handover details
    handover_to: Union[str, None] = Field(
        default=None,
        description="Supervisor ID for responsibility handover",
    )
    handover_notes: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_NOTES_LENGTH,
        description="Handover instructions",
    )

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: Date) -> Date:
        """Validate effective Date is within acceptable range."""
        today = Date.today()
        
        min_date = today - timedelta(days=SupervisorValidationConstants.MAX_PAST_EFFECTIVE_DAYS)
        max_date = today + timedelta(days=SupervisorValidationConstants.MAX_FUTURE_EFFECTIVE_DAYS)
        
        if v < min_date:
            raise ValueError(
                f"Effective Date cannot be more than {SupervisorValidationConstants.MAX_PAST_EFFECTIVE_DAYS} days in the past"
            )
        
        if v > max_date:
            raise ValueError(
                f"Effective Date cannot be more than {SupervisorValidationConstants.MAX_FUTURE_EFFECTIVE_DAYS} days in the future"
            )
        
        return v

    @model_validator(mode="after")
    def validate_status_specific_requirements(self) -> "SupervisorStatusUpdate":
        """
        Validate status-specific required fields and constraints.
        
        Returns:
            Self with validated data
            
        Raises:
            ValueError: If required fields are missing for specific statuses
        """
        # Termination validation
        if self.status == SupervisorStatus.TERMINATED:
            if not self.termination_date:
                raise ValueError("termination_date is required for TERMINATED status")
            if not self.termination_reason:
                raise ValueError("termination_reason is required for TERMINATED status")
            if self.is_active:
                raise ValueError("is_active must be False for TERMINATED status")
        
        # Suspension validation
        if self.status == SupervisorStatus.SUSPENDED:
            if not self.suspension_start_date:
                raise ValueError("suspension_start_date is required for SUSPENDED status")
            if not self.suspension_end_date:
                raise ValueError("suspension_end_date is required for SUSPENDED status")
            if not self.suspension_reason:
                raise ValueError("suspension_reason is required for SUSPENDED status")
            if self.is_active:
                raise ValueError("is_active must be False for SUSPENDED status")
        
        # Leave validation
        if self.status == SupervisorStatus.ON_LEAVE:
            if not self.leave_start_date:
                raise ValueError("leave_start_date is required for ON_LEAVE status")
            if not self.leave_end_date:
                raise ValueError("leave_end_date is required for ON_LEAVE status")
        
        return self

    @model_validator(mode="after")
    def validate_date_ranges(self) -> "SupervisorStatusUpdate":
        """
        Validate Date range consistency for suspension and leave.
        
        Returns:
            Self with validated dates
            
        Raises:
            ValueError: If end dates are before start dates
        """
        # Suspension Date range
        if self.suspension_start_date and self.suspension_end_date:
            if self.suspension_end_date <= self.suspension_start_date:
                raise ValueError("suspension_end_date must be after suspension_start_date")
        
        # Leave Date range
        if self.leave_start_date and self.leave_end_date:
            if self.leave_end_date <= self.leave_start_date:
                raise ValueError("leave_end_date must be after leave_start_date")
        
        return self


class SupervisorReassignment(BaseCreateSchema):
    """
    Schema for reassigning supervisor to different hostel.
    
    Handles supervisor transfer between hostels with proper tracking,
    permission handling, and optional salary adjustments.
    """

    supervisor_id: str = Field(
        ...,
        description="Supervisor ID to reassign",
    )
    from_hostel_id: str = Field(
        ...,
        description="Current hostel ID",
    )
    new_hostel_id: str = Field(
        ...,
        description="New hostel ID to assign",
    )
    effective_date: Date = Field(
        ...,
        description="Reassignment effective Date",
    )
    reason: str = Field(
        ...,
        min_length=SupervisorValidationConstants.MIN_REASON_LENGTH,
        max_length=SupervisorValidationConstants.MAX_REASON_LENGTH,
        description="Reason for reassignment",
        examples=[
            "Staff shortage at new hostel",
            "Performance-based transfer",
            "Personal request",
            "Organizational restructuring",
        ],
    )

    # Permission handling
    retain_permissions: bool = Field(
        default=True,
        description="Retain same permission set at new hostel",
    )
    new_permissions: Union[Dict[str, Union[bool, int, Decimal]], None] = Field(
        default=None,
        description="New permission set (required if not retaining)",
    )

    # Salary adjustment
    salary_adjustment: Union[DecimalWithPrecision, None] = Field(
        default=None,
        description="Salary adjustment amount (positive or negative)",
    )
    salary_adjustment_reason: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Reason for salary adjustment",
    )

    # Handover configuration
    handover_period_days: int = Field(
        default=7,
        ge=SupervisorValidationConstants.MIN_HANDOVER_PERIOD_DAYS,
        le=SupervisorValidationConstants.MAX_HANDOVER_PERIOD_DAYS,
        description="Handover period in days",
    )
    handover_to: Union[str, None] = Field(
        default=None,
        description="Supervisor ID for handover at current hostel",
    )

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: Date) -> Date:
        """Validate effective Date is in acceptable future range."""
        today = Date.today()
        
        if v < today:
            raise ValueError("Effective Date cannot be in the past")
        
        max_date = today + timedelta(days=SupervisorValidationConstants.MAX_FUTURE_REASSIGNMENT_DAYS)
        if v > max_date:
            raise ValueError(
                f"Effective Date cannot be more than {SupervisorValidationConstants.MAX_FUTURE_REASSIGNMENT_DAYS} days in the future"
            )
        
        return v

    @model_validator(mode="after")
    def validate_reassignment_logic(self) -> "SupervisorReassignment":
        """
        Validate reassignment business logic.
        
        Returns:
            Self with validated data
            
        Raises:
            ValueError: If reassignment logic is invalid
        """
        # Different hostel validation
        if self.from_hostel_id == self.new_hostel_id:
            raise ValueError("New hostel must be different from current hostel")
        
        # Permission configuration validation
        if not self.retain_permissions and not self.new_permissions:
            raise ValueError(
                "new_permissions must be provided when retain_permissions is False"
            )
        
        # Salary adjustment validation
        if self.salary_adjustment is not None and self.salary_adjustment != 0:
            if not self.salary_adjustment_reason:
                raise ValueError(
                    "salary_adjustment_reason is required when adjusting salary"
                )
        
        return self


class SupervisorTermination(BaseCreateSchema):
    """
    Schema for comprehensive supervisor termination.
    
    Handles complete termination process including exit interview,
    clearance verification, asset return, and final settlement.
    """

    supervisor_id: str = Field(
        ...,
        description="Supervisor ID to terminate",
    )
    termination_date: Date = Field(
        ...,
        description="Termination effective Date",
    )
    termination_type: str = Field(
        ...,
        pattern=r"^(voluntary|involuntary|retirement|end_of_contract)$",
        description="Type of termination",
        examples=["voluntary", "involuntary", "retirement", "end_of_contract"],
    )
    reason: str = Field(
        ...,
        min_length=20,
        max_length=SupervisorValidationConstants.MAX_NOTES_LENGTH,
        description="Detailed termination reason",
    )

    # Notice period
    notice_period_served: bool = Field(
        ...,
        description="Whether notice period was served",
    )
    notice_period_days: Union[int, None] = Field(
        default=None,
        ge=0,
        le=90,
        description="Notice period served in days",
    )

    # Clearance checklist
    hostel_clearance_obtained: bool = Field(
        default=False,
        description="Hostel clearance completed",
    )
    finance_clearance_obtained: bool = Field(
        default=False,
        description="Finance clearance completed",
    )
    admin_clearance_obtained: bool = Field(
        default=False,
        description="Admin clearance completed",
    )

    # Asset management
    assets_returned: bool = Field(
        default=False,
        description="All hostel assets returned",
    )
    asset_list: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="List of assets returned",
    )

    # Exit interview
    exit_interview_conducted: bool = Field(
        default=False,
        description="Exit interview completed",
    )
    exit_interview_notes: Union[str, None] = Field(
        default=None,
        max_length=2000,
        description="Exit interview notes",
    )

    # Rehire eligibility
    eligible_for_rehire: bool = Field(
        ...,
        description="Eligible for future rehire",
    )
    rehire_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Notes on rehire eligibility",
    )

    # Final settlement
    final_settlement_amount: Union[DecimalWithPrecision, None] = Field(
        default=None,
        ge=0,
        description="Final settlement amount",
    )
    settlement_date: Union[Date, None] = Field(
        default=None,
        description="Settlement payment Date",
    )

    # Handover
    responsibilities_handover_to: Union[str, None] = Field(
        default=None,
        description="Supervisor ID for handover",
    )
    handover_completed: bool = Field(
        default=False,
        description="Handover completion status",
    )
    handover_notes: Union[str, None] = Field(
        default=None,
        max_length=SupervisorValidationConstants.MAX_NOTES_LENGTH,
        description="Handover notes",
    )

    @field_validator("termination_date")
    @classmethod
    def validate_termination_date(cls, v: Date) -> Date:
        """Validate termination Date is within acceptable range."""
        today = Date.today()
        
        min_date = today - timedelta(days=SupervisorValidationConstants.MAX_PAST_TERMINATION_DAYS)
        max_date = today + timedelta(days=SupervisorValidationConstants.MAX_FUTURE_TERMINATION_DAYS)
        
        if v < min_date:
            raise ValueError(
                f"Termination Date cannot be more than {SupervisorValidationConstants.MAX_PAST_TERMINATION_DAYS} days in the past"
            )
        
        if v > max_date:
            raise ValueError(
                f"Termination Date cannot be more than {SupervisorValidationConstants.MAX_FUTURE_TERMINATION_DAYS} days in the future"
            )
        
        return v

    @field_validator("termination_type")
    @classmethod
    def normalize_termination_type(cls, v: str) -> str:
        """Normalize termination type to lowercase."""
        return v.lower().strip()

    @model_validator(mode="after")
    def validate_termination_requirements(self) -> "SupervisorTermination":
        """
        Validate termination-specific business logic.
        
        Returns:
            Self with validated data
        """
        # Settlement validation
        if self.final_settlement_amount and self.final_settlement_amount > 0:
            if not self.settlement_date:
                raise ValueError(
                    "settlement_date is required when final_settlement_amount is provided"
                )
        
        # Notice period validation for voluntary termination
        if self.termination_type == "voluntary" and not self.notice_period_served:
            if self.notice_period_days is None or self.notice_period_days == 0:
                # Warning only - don't enforce strictly
                pass
        
        return self

    @model_validator(mode="after")
    def validate_clearance_completeness(self) -> "SupervisorTermination":
        """
        Validate clearance requirements for past terminations.
        
        Returns:
            Self with validation warnings (non-blocking)
        """
        # For past terminations, all clearances should ideally be complete
        if self.termination_date <= Date.today():
            incomplete_clearances = []
            
            if not self.hostel_clearance_obtained:
                incomplete_clearances.append("hostel")
            if not self.finance_clearance_obtained:
                incomplete_clearances.append("finance")
            if not self.admin_clearance_obtained:
                incomplete_clearances.append("admin")
            
            # Log warning but don't block (can be handled at service layer)
            if incomplete_clearances:
                # This would typically trigger a warning in logs
                pass
        
        return self