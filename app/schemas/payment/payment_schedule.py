# --- File: app/schemas/payment/payment_schedule.py ---
"""
Payment schedule schemas for recurring payments.

This module defines schemas for managing payment schedules including
creation, updates, generation, and suspension of scheduled payments.
"""

from __future__ import annotations

from datetime import date as Date, timedelta
from decimal import Decimal
from typing import List, Optional
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
    end_date: Optional[Date] = Field(
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
    end_date: Optional[Date] = Field(
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

    amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Update amount per period",
    )
    next_due_date: Optional[Date] = Field(
        None,
        description="Update next due Date",
    )
    end_date: Optional[Date] = Field(
        None,
        description="Update end Date",
    )
    auto_generate_invoice: Optional[bool] = Field(
        None,
        description="Update auto-generation setting",
    )
    is_active: Optional[bool] = Field(
        None,
        description="Activate or deactivate schedule",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
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