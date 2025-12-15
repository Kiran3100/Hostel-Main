# --- File: app/schemas/payment/payment_base.py ---
"""
Base payment schemas.

This module defines the core payment schemas that serve as foundation
for other payment-related schemas.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import PaymentMethod, PaymentStatus, PaymentType

__all__ = [
    "PaymentBase",
    "PaymentCreate",
    "PaymentUpdate",
]


class PaymentBase(BaseSchema):
    """
    Base payment schema with common fields.
    
    This schema contains fields that are common across all payment operations.
    """

    payment_type: PaymentType = Field(
        ...,
        description="Type of payment",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Payment amount",
    )
    currency: str = Field(
        "INR",
        min_length=3,
        max_length=3,
        description="Currency code (ISO 4217)",
    )
    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method used",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate and normalize amount."""
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v.quantize(Decimal("0.01"))

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency code."""
        v = v.upper().strip()
        if len(v) != 3:
            raise ValueError("Currency code must be exactly 3 characters")
        return v


class PaymentCreate(BaseCreateSchema):
    """
    Create payment schema.
    
    Used for creating new payment records in the system.
    """

    # Entity References
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    student_id: Optional[UUID] = Field(
        None,
        description="Student ID (for student-related payments)",
    )
    booking_id: Optional[UUID] = Field(
        None,
        description="Booking ID (for booking-related payments)",
    )
    payer_id: UUID = Field(
        ...,
        description="Payer user ID",
    )

    # Payment Details
    payment_type: PaymentType = Field(
        ...,
        description="Type of payment",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Payment amount",
    )
    currency: str = Field(
        "INR",
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Payment Method
    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method",
    )
    payment_gateway: Optional[str] = Field(
        None,
        max_length=50,
        description="Payment gateway identifier",
    )

    # Transaction Details
    transaction_id: Optional[str] = Field(
        None,
        max_length=100,
        description="External transaction ID",
    )
    gateway_order_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Gateway order ID",
    )

    # Payment Period (for recurring fees)
    payment_period_start: Optional[Date] = Field(
        None,
        description="Payment period start date",
    )
    payment_period_end: Optional[Date] = Field(
        None,
        description="Payment period end date",
    )

    # Due Date
    due_date: Optional[Date] = Field(
        None,
        description="Payment due date",
    )

    # Status
    payment_status: PaymentStatus = Field(
        PaymentStatus.PENDING,
        description="Initial payment status",
    )

    # Additional Information
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes about the payment",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate and normalize amount."""
        if v <= 0:
            raise ValueError("Payment amount must be greater than zero")
        return v.quantize(Decimal("0.01"))

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate and normalize currency code."""
        v = v.upper().strip()
        if len(v) != 3:
            raise ValueError("Currency code must be exactly 3 characters")
        return v


class PaymentUpdate(BaseUpdateSchema):
    """
    Update payment schema.
    
    Used for updating existing payment records.
    Only modifiable fields are included.
    """

    payment_status: Optional[PaymentStatus] = Field(
        None,
        description="Update payment status",
    )
    transaction_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Update transaction ID",
    )
    paid_at: Optional[datetime] = Field(
        None,
        description="Payment completion timestamp",
    )
    failed_at: Optional[datetime] = Field(
        None,
        description="Payment failure timestamp",
    )
    failure_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for payment failure",
    )
    gateway_response: Optional[dict] = Field(
        None,
        description="Gateway response data",
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Update payment notes",
    )

    @field_validator("failure_reason")
    @classmethod
    def validate_failure_reason(cls, v: Optional[str]) -> Optional[str]:
        """Validate failure reason."""
        if v is not None:
            v = v.strip()
            if len(v) < 5:
                raise ValueError("Failure reason must be at least 5 characters")
        return v