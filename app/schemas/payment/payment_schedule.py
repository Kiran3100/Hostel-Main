# --- File: app/schemas/payment/payment_schedule.py ---
"""
Payment schedule schemas for recurring payments.

This module defines schemas for managing payment schedules including
creation, updates, generation, and suspension of scheduled payments.
"""

from datetime import date as Date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import FeeType, PaymentType

__all__ = [
    "PaymentSchedule",
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleGeneration",
    "ScheduledPaymentGenerated",
    "BulkScheduleCreate",
    "ScheduleSuspension",
    "ScheduleListItem",
    "ScheduleGenerationResponse",
]


class PaymentSchedule(BaseResponseSchema):
    """
    Payment schedule schema.
    
    Represents a recurring payment schedule for a student.
    """

    student_id: UUID = Field(
        ...,
        description="Student ID",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    # Schedule Details
    fee_type: FeeType = Field(
        ...,
        description="Fee type (monthly, quarterly, etc.)",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount per period",
    )

    # Schedule Period
    start_date: Date = Field(
        ...,
        description="Schedule start Date",
    )
    end_date: Union[Date, None] = Field(
        None,
        description="Schedule end Date (null for indefinite)",
    )
    next_due_date: Date = Field(
        ...,
        description="Next payment due Date",
    )

    # Settings
    auto_generate_invoice: bool = Field(
        ...,
        description="Automatically generate invoices",
    )
    is_active: bool = Field(
        ...,
        description="Whether schedule is currently active",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_indefinite(self) -> bool:
        """Check if schedule has no end Date."""
        return self.end_date is None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_until_next_payment(self) -> int:
        """Calculate days until next payment."""
        return (self.next_due_date - Date.today()).days

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_overdue(self) -> bool:
        """Check if next payment is overdue."""
        return self.next_due_date < Date.today()


class ScheduleCreate(BaseCreateSchema):
    """
    Create payment schedule schema.
    
    Used to set up a new recurring payment schedule for a student.
    """

    student_id: UUID = Field(
        ...,
        description="Student ID",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )

    # Schedule Configuration
    fee_type: FeeType = Field(
        ...,
        description="Fee type (monthly, quarterly, half-yearly, yearly)",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount to charge per period",
    )

    # Schedule Period
    start_date: Date = Field(
        ...,
        description="When schedule should start",
    )
    end_date: Union[Date, None] = Field(
        None,
        description="When schedule should end (null for indefinite)",
    )

    # First Payment
    first_due_date: Date = Field(
        ...,
        description="Due Date for first payment",
    )

    # Settings
    auto_generate_invoice: bool = Field(
        True,
        description="Automatically generate invoices on due dates",
    )
    send_reminders: bool = Field(
        True,
        description="Send payment reminders",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount is positive."""
        if v <= 0:
            raise ValueError("Schedule amount must be greater than zero")
        
        # Sanity check
        max_amount = Decimal("100000.00")
        if v > max_amount:
            raise ValueError(
                f"Schedule amount (₹{v}) exceeds maximum (₹{max_amount})"
            )
        
        return v.quantize(Decimal("0.01"))

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: Date) -> Date:
        """Validate start Date is reasonable."""
        # Allow past dates for backdated schedules, but warn
        days_ago = (Date.today() - v).days
        if days_ago > 365:
            # Log warning - might be data migration
            # In production, use proper logging
            pass
        
        return v

    @model_validator(mode="after")
    def validate_date_range(self) -> "ScheduleCreate":
        """Validate schedule Date range."""
        if self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError(
                    f"End Date ({self.end_date}) must be after "
                    f"start Date ({self.start_date})"
                )
            
            # Check if end Date is reasonable
            days_diff = (self.end_date - self.start_date).days
            if days_diff > 1825:  # 5 years
                # Log warning - very long schedule
                pass
        
        return self

    @model_validator(mode="after")
    def validate_first_due_date(self) -> "ScheduleCreate":
        """Validate first due Date is within schedule period."""
        if self.first_due_date < self.start_date:
            raise ValueError(
                f"First due Date ({self.first_due_date}) cannot be "
                f"before start Date ({self.start_date})"
            )
        
        if self.end_date is not None and self.first_due_date > self.end_date:
            raise ValueError(
                f"First due Date ({self.first_due_date}) cannot be "
                f"after end Date ({self.end_date})"
            )
        
        return self


class ScheduleUpdate(BaseUpdateSchema):
    """
    Update payment schedule schema.
    
    Allows modification of schedule parameters.
    """

    amount: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Update amount per period",
    )
    next_due_date: Union[Date, None] = Field(
        None,
        description="Update next due Date",
    )
    end_date: Union[Date, None] = Field(
        None,
        description="Update end Date",
    )
    auto_generate_invoice: Union[bool, None] = Field(
        None,
        description="Update auto-generation setting",
    )
    is_active: Union[bool, None] = Field(
        None,
        description="Activate or deactivate schedule",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Validate amount if provided."""
        if v is not None:
            if v <= 0:
                raise ValueError("Amount must be greater than zero")
            return v.quantize(Decimal("0.01"))
        return v


class ScheduleGeneration(BaseSchema):
    """
    Generate scheduled payments schema.
    
    Used to manually trigger generation of scheduled payments
    for a specific period.
    """

    schedule_id: UUID = Field(
        ...,
        description="Schedule ID",
    )

    # Generation Period
    generate_from_date: Date = Field(
        ...,
        description="Start Date for payment generation",
    )
    generate_to_date: Date = Field(
        ...,
        description="End Date for payment generation",
    )

    # Options
    skip_if_already_paid: bool = Field(
        True,
        description="Skip generation if payment already exists and is paid",
    )
    send_notifications: bool = Field(
        True,
        description="Send notifications for generated payments",
    )

    @model_validator(mode="after")
    def validate_generation_period(self) -> "ScheduleGeneration":
        """Validate generation period."""
        if self.generate_to_date < self.generate_from_date:
            raise ValueError(
                f"End Date ({self.generate_to_date}) must be after "
                f"start Date ({self.generate_from_date})"
            )
        
        # Limit generation period to 1 year
        days_diff = (self.generate_to_date - self.generate_from_date).days
        if days_diff > 365:
            raise ValueError(
                f"Generation period cannot exceed 365 days (got {days_diff} days)"
            )
        
        return self


class ScheduledPaymentGenerated(BaseSchema):
    """
    Result of scheduled payment generation.
    
    Contains information about payments generated from schedule.
    """

    schedule_id: UUID = Field(
        ...,
        description="Schedule ID",
    )

    # Generation Results
    payments_generated: int = Field(
        ...,
        ge=0,
        description="Number of payments generated",
    )
    payments_skipped: int = Field(
        ...,
        ge=0,
        description="Number of payments skipped",
    )

    # Generated Payment IDs
    generated_payment_ids: List[UUID] = Field(
        default_factory=list,
        description="IDs of generated payments",
    )

    # Next Generation
    next_generation_date: Date = Field(
        ...,
        description="When next generation should occur",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_processed(self) -> int:
        """Calculate total payments processed."""
        return self.payments_generated + self.payments_skipped

    @computed_field  # type: ignore[prop-decorator]
    @property
    def generation_success_rate(self) -> float:
        """Calculate percentage of successful generations."""
        if self.total_processed == 0:
            return 0.0
        return round((self.payments_generated / self.total_processed) * 100, 2)


class BulkScheduleCreate(BaseCreateSchema):
    """
    Create schedules for multiple students.
    
    Used for batch creation of payment schedules.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID for all schedules",
    )
    student_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of student IDs (max 100)",
    )

    # Common Schedule Configuration
    fee_type: FeeType = Field(
        ...,
        description="Fee type for all schedules",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount per period for all schedules",
    )

    # Common Schedule Period
    start_date: Date = Field(
        ...,
        description="Start Date for all schedules",
    )
    first_due_date: Date = Field(
        ...,
        description="First due Date for all schedules",
    )

    @field_validator("student_ids")
    @classmethod
    def validate_student_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate student IDs list."""
        if len(v) == 0:
            raise ValueError("At least one student ID is required")
        
        if len(v) > 100:
            raise ValueError("Maximum 100 students allowed per bulk operation")
        
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate student IDs found")
        
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount."""
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_dates(self) -> "BulkScheduleCreate":
        """Validate Date consistency."""
        if self.first_due_date < self.start_date:
            raise ValueError(
                f"First due Date ({self.first_due_date}) cannot be "
                f"before start Date ({self.start_date})"
            )
        return self


class ScheduleSuspension(BaseCreateSchema):
    """
    Suspend payment schedule temporarily.
    
    Used to pause schedule for a specific period (e.g., vacation).
    """

    schedule_id: UUID = Field(
        ...,
        description="Schedule ID to suspend",
    )
    suspension_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for suspension",
    )

    # Suspension Period
    suspend_from_date: Date = Field(
        ...,
        description="Suspension start Date",
    )
    suspend_to_date: Date = Field(
        ...,
        description="Suspension end Date",
    )

    # Handling Options
    skip_dues_during_suspension: bool = Field(
        True,
        description="Skip generating payment dues during suspension period",
    )

    @field_validator("suspension_reason")
    @classmethod
    def validate_suspension_reason(cls, v: str) -> str:
        """Validate suspension reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Suspension reason must be at least 10 characters")
        return v

    @model_validator(mode="after")
    def validate_suspension_period(self) -> "ScheduleSuspension":
        """Validate suspension period."""
        if self.suspend_to_date <= self.suspend_from_date:
            raise ValueError(
                f"Suspension end Date ({self.suspend_to_date}) must be "
                f"after start Date ({self.suspend_from_date})"
            )
        
        # Limit suspension to 1 year
        days_diff = (self.suspend_to_date - self.suspend_from_date).days
        if days_diff > 365:
            raise ValueError(
                f"Suspension period cannot exceed 365 days (got {days_diff} days)"
            )
        
        # Warn if suspension starts in the past
        if self.suspend_from_date < Date.today():
            # Log warning - in production, use proper logging
            pass
        
        return self


class ScheduleListItem(BaseSchema):
    """
    Schedule list item for summary views.
    
    Optimized schema for displaying multiple schedules.
    """

    id: UUID = Field(..., description="Schedule ID")
    
    # Student Information
    student_id: UUID = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    student_email: Union[str, None] = Field(None, description="Student email")

    # Hostel Information
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")

    # Schedule Details
    fee_type: FeeType = Field(..., description="Fee type")
    amount: Decimal = Field(..., ge=0, description="Amount per period")
    currency: str = Field(default="INR", description="Currency code")

    # Timing
    start_date: Date = Field(..., description="Schedule start date")
    end_date: Union[Date, None] = Field(None, description="Schedule end date")
    next_due_date: Date = Field(..., description="Next payment due date")

    # Status
    is_active: bool = Field(..., description="Whether schedule is active")
    is_suspended: bool = Field(default=False, description="Whether schedule is suspended")
    
    # Metadata
    total_payments_generated: int = Field(
        default=0,
        ge=0,
        description="Total payments generated from this schedule",
    )
    payments_completed: int = Field(
        default=0,
        ge=0,
        description="Number of completed payments",
    )
    payments_pending: int = Field(
        default=0,
        ge=0,
        description="Number of pending payments",
    )

    # Timestamps
    created_at: datetime = Field(..., description="When schedule was created")
    updated_at: datetime = Field(..., description="When schedule was last updated")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_display(self) -> str:
        """Get user-friendly status."""
        if not self.is_active:
            return "Inactive"
        elif self.is_suspended:
            return "Suspended"
        else:
            return "Active"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_until_next_payment(self) -> int:
        """Calculate days until next payment."""
        return (self.next_due_date - Date.today()).days

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completion_rate(self) -> float:
        """Calculate payment completion rate."""
        if self.total_payments_generated == 0:
            return 0.0
        return round(
            (self.payments_completed / self.total_payments_generated) * 100,
            2
        )


class ScheduleGenerationResponse(BaseSchema):
    """
    Schedule generation response schema.
    
    Contains results after generating payments from a schedule.
    """

    schedule_id: UUID = Field(
        ...,
        description="Schedule ID",
    )
    schedule_name: str = Field(
        ...,
        description="Schedule identifier/name",
    )

    # Generation Results
    payments_generated: int = Field(
        ...,
        ge=0,
        description="Number of payments generated",
    )
    payments_skipped: int = Field(
        ...,
        ge=0,
        description="Number of payments skipped",
    )
    payments_failed: int = Field(
        ...,
        ge=0,
        description="Number of generation failures",
    )

    # Financial Summary
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total amount of generated payments",
    )
    currency: str = Field(
        default="INR",
        description="Currency code",
    )

    # Generated Payment Details
    generated_payment_ids: List[UUID] = Field(
        default_factory=list,
        description="IDs of successfully generated payments",
    )
    skipped_payment_ids: List[UUID] = Field(
        default_factory=list,
        description="IDs of skipped payments",
    )

    # Next Generation
    next_generation_date: Date = Field(
        ...,
        description="When next generation should occur",
    )
    next_payment_amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount for next scheduled payment",
    )

    # Generation Summary
    generation_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed generation summary",
    )

    # Timing
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When generation occurred",
    )
    generation_period_start: Union[Date, None] = Field(
        None,
        description="Start of generation period",
    )
    generation_period_end: Union[Date, None] = Field(
        None,
        description="End of generation period",
    )

    # Error Information
    errors: Union[List[str], None] = Field(
        None,
        description="List of errors encountered",
    )
    warnings: Union[List[str], None] = Field(
        None,
        description="List of warnings",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_processed(self) -> int:
        """Calculate total payments processed."""
        return self.payments_generated + self.payments_skipped + self.payments_failed

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success_rate(self) -> float:
        """Calculate generation success rate."""
        if self.total_processed == 0:
            return 0.0
        return round((self.payments_generated / self.total_processed) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def average_payment_amount(self) -> Decimal:
        """Calculate average payment amount."""
        if self.payments_generated == 0:
            return Decimal("0.00")
        return (self.total_amount / self.payments_generated).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_errors(self) -> bool:
        """Check if generation had errors."""
        return self.payments_failed > 0 or (self.errors is not None and len(self.errors) > 0)