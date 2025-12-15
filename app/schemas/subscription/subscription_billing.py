"""
Subscription billing schemas.

Handles billing cycle information, invoice generation,
and invoice tracking for subscriptions.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Annotated
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator, computed_field, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "InvoiceStatus",
    "BillingCycleInfo",
    "GenerateInvoiceRequest",
    "InvoiceInfo",
]


class InvoiceStatus(str, Enum):
    """Invoice status enumeration."""

    DRAFT = "draft"
    ISSUED = "issued"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class BillingCycleInfo(BaseSchema):
    """
    Information about current billing cycle for subscription.

    Provides a comprehensive view of the current billing period,
    including dates, amounts, and renewal information.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(..., description="Subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")
    plan_name: str = Field(..., description="Subscription plan name")
    plan_display_name: str = Field(
        ..., description="Plan display name for UI"
    )

    cycle_start: Date = Field(..., description="Current cycle start Date")
    cycle_end: Date = Field(..., description="Current cycle end Date")
    billing_cycle: str = Field(
        ...,
        pattern=r"^(monthly|yearly)$",
        description="Billing cycle type",
    )

    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Billing amount for this cycle",
    )]
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )

    next_billing_date: Date = Field(..., description="Next billing Date")
    days_until_billing: int = Field(
        ...,
        description="Days until next billing",
    )
    auto_renew: bool = Field(..., description="Auto-renewal status")

    # Calculated fields
    is_in_trial: bool = Field(
        default=False, description="Whether currently in trial period"
    )
    trial_days_remaining: Optional[int] = Field(
        None, description="Days remaining in trial"
    )

    @model_validator(mode="after")
    def validate_cycle_dates(self) -> "BillingCycleInfo":
        """Validate billing cycle Date relationships."""
        if self.cycle_end < self.cycle_start:
            raise ValueError("cycle_end must be after cycle_start")
        return self


class GenerateInvoiceRequest(BaseCreateSchema):
    """
    Request to generate invoice for subscription cycle.

    Allows specifying the billing Date and optionally overriding
    the standard billing amount.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(
        ..., description="Subscription to invoice"
    )
    billing_date: Date = Field(
        ..., description="Invoice billing Date"
    )

    # Optional overrides
    amount_override: Optional[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Override standard billing amount",
    )]]
    due_date_override: Optional[Date] = Field(
        None, description="Override standard due Date"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional invoice notes",
    )

    # Line item adjustments
    discount_amount: Optional[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Discount amount to apply",
    )]]
    discount_reason: Optional[str] = Field(
        None,
        max_length=200,
        description="Reason for discount",
    )

    @model_validator(mode="after")
    def validate_discount(self) -> "GenerateInvoiceRequest":
        """Validate discount fields."""
        if self.discount_amount is not None and self.discount_amount > Decimal("0"):
            if not self.discount_reason:
                raise ValueError(
                    "discount_reason is required when discount_amount is provided"
                )
        return self


class InvoiceInfo(BaseSchema):
    """
    Generated invoice information.

    Contains all details of a generated invoice including
    status, amounts, and access URLs.
    """
    model_config = ConfigDict(populate_by_name=True)

    invoice_id: UUID = Field(..., description="Invoice unique ID")
    subscription_id: UUID = Field(..., description="Associated subscription")
    hostel_id: UUID = Field(..., description="Hostel ID")

    invoice_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^INV-\d{4}-\d{6,}$",
        description="Invoice number (e.g., INV-2024-000001)",
    )
    invoice_date: Date = Field(..., description="Invoice issue Date")
    due_date: Date = Field(..., description="Payment due Date")

    # Amounts
    subtotal: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Subtotal before adjustments",
    )]
    discount_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Total discount applied",
    )]
    tax_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Tax amount",
    )]
    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total invoice amount",
    )]
    amount_paid: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Amount already paid",
    )]
    amount_due: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Remaining amount due",
    )]
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )

    status: InvoiceStatus = Field(
        default=InvoiceStatus.DRAFT,
        description="Invoice status",
    )

    # Access URLs
    invoice_url: Optional[HttpUrl] = Field(
        None, description="URL to view/download invoice"
    )
    payment_url: Optional[HttpUrl] = Field(
        None, description="URL to pay invoice online"
    )

    # Metadata
    notes: Optional[str] = Field(None, description="Invoice notes")

    @model_validator(mode="after")
    def validate_invoice_dates_and_amounts(self) -> "InvoiceInfo":
        """Validate invoice Date relationships and amount calculations."""
        if self.due_date < self.invoice_date:
            raise ValueError("due_date cannot be before invoice_date")

        # Validate amount calculation
        expected_amount = self.subtotal - self.discount_amount + self.tax_amount
        if abs(self.amount - expected_amount) > Decimal("0.01"):
            raise ValueError(
                f"amount ({self.amount}) does not match calculated total ({expected_amount})"
            )

        # Validate amount_due
        expected_due = self.amount - self.amount_paid
        if abs(self.amount_due - expected_due) > Decimal("0.01"):
            raise ValueError(
                f"amount_due ({self.amount_due}) does not match outstanding ({expected_due})"
            )

        return self

    @computed_field
    def is_overdue(self) -> bool:
        """Check if invoice is overdue based on current Date."""
        return (
            self.status not in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED)
            and Date.today() > self.due_date
        )

    @computed_field
    def is_fully_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.amount_due <= Decimal("0")