"""
Subscription response schemas.

Provides comprehensive response structures for subscription
data, billing history, and subscription summaries.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Annotated
from uuid import UUID

from pydantic import Field, HttpUrl, computed_field, model_validator, ConfigDict

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import (
    BillingCycle,
    SubscriptionPlan,
    SubscriptionStatus,
)

__all__ = [
    "SubscriptionResponse",
    "SubscriptionSummary",
    "BillingHistoryItem",
    "BillingHistory",
]


class SubscriptionResponse(BaseResponseSchema):
    """
    Complete hostel subscription response.

    Returns all subscription details including plan information,
    billing details, and current status.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Hostel info
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")

    # Plan info
    plan_id: UUID = Field(..., description="Subscription plan ID")
    plan_name: str = Field(..., description="Plan internal name")
    display_name: str = Field(..., description="Plan display name")
    plan_type: SubscriptionPlan = Field(..., description="Plan tier")

    # Subscription details
    subscription_reference: str = Field(
        ..., description="Unique subscription reference"
    )
    billing_cycle: BillingCycle = Field(..., description="Billing cycle")
    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Billing amount",
    )]
    currency: str = Field(default="INR", description="Currency code")

    # Dates
    start_date: Date = Field(..., description="Subscription start Date")
    end_date: Date = Field(..., description="Subscription end Date")
    auto_renew: bool = Field(..., description="Auto-renewal enabled")
    next_billing_date: Optional[Date] = Field(
        None, description="Next billing Date"
    )
    status: SubscriptionStatus = Field(..., description="Current status")

    # Trial info
    trial_end_date: Optional[Date] = Field(
        None, description="Trial period end Date"
    )
    is_in_trial: bool = Field(
        default=False, description="Currently in trial period"
    )

    # Payment info
    last_payment_date: Optional[Date] = Field(
        None, description="Last payment Date"
    )
    last_payment_amount: Optional[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Last payment amount",
    )]]

    # Cancellation info (if applicable)
    cancelled_at: Optional[datetime] = Field(
        None, description="Cancellation timestamp"
    )
    cancellation_effective_date: Optional[Date] = Field(
        None, description="When cancellation takes effect"
    )

    @computed_field
    def days_until_expiry(self) -> int:
        """Calculate days until subscription expires."""
        today = Date.today()
        if self.end_date < today:
            return 0
        return (self.end_date - today).days

    @computed_field
    def days_until_billing(self) -> Optional[int]:
        """Calculate days until next billing."""
        if self.next_billing_date is None:
            return None
        today = Date.today()
        if self.next_billing_date < today:
            return 0
        return (self.next_billing_date - today).days

    @computed_field
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status == SubscriptionStatus.ACTIVE

    @computed_field
    def is_expiring_soon(self) -> bool:
        """Check if subscription expires within 7 days."""
        return 0 < self.days_until_expiry <= 7

    @computed_field
    def amount_formatted(self) -> str:
        """Format amount with currency."""
        cycle_label = "mo" if self.billing_cycle == BillingCycle.MONTHLY else "yr"
        return f"{self.currency} {self.amount:,.2f}/{cycle_label}"


class SubscriptionSummary(BaseSchema):
    """
    Condensed subscription summary for listings.

    Provides essential subscription information for dashboards
    and list views.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")

    plan_name: str = Field(..., description="Plan name")
    plan_type: SubscriptionPlan = Field(..., description="Plan tier")
    status: SubscriptionStatus = Field(..., description="Status")

    billing_cycle: BillingCycle = Field(..., description="Billing cycle")
    amount: Annotated[Decimal, Field(..., description="Billing amount")]
    currency: str = Field(default="INR")

    end_date: Date = Field(..., description="Expiry Date")
    auto_renew: bool = Field(..., description="Auto-renewal status")

    is_in_trial: bool = Field(default=False)
    days_until_expiry: int = Field(..., description="Days until expiry")


class BillingHistoryItem(BaseSchema):
    """
    Single billing event in history.

    Represents one billing transaction with all relevant details.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[UUID] = Field(None, description="Transaction ID")
    billing_date: Date = Field(..., description="Billing Date")

    # Amounts
    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Billed amount",
    )]
    currency: str = Field(default="INR", description="Currency code")

    # Status and references
    status: str = Field(
        ...,
        description="Payment status (pending, paid, failed, refunded)",
    )
    payment_reference: Optional[str] = Field(
        None,
        max_length=100,
        description="Payment transaction reference",
    )
    payment_method: Optional[str] = Field(
        None, description="Payment method used"
    )

    # Invoice
    invoice_number: Optional[str] = Field(
        None, description="Associated invoice number"
    )
    invoice_url: Optional[HttpUrl] = Field(
        None, description="Invoice download URL"
    )

    # Description
    description: Optional[str] = Field(
        None,
        max_length=255,
        description="Billing description",
    )

    # Period covered
    period_start: Optional[Date] = Field(
        None, description="Billing period start"
    )
    period_end: Optional[Date] = Field(
        None, description="Billing period end"
    )

    @computed_field
    def is_paid(self) -> bool:
        """Check if billing item is paid."""
        return self.status.lower() == "paid"


class BillingHistory(BaseSchema):
    """
    Complete subscription billing history.

    Aggregates all billing events with summary statistics.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(..., description="Subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: Optional[str] = Field(None, description="Hostel name")

    # Billing items
    items: List[BillingHistoryItem] = Field(
        default_factory=list,
        description="List of billing events",
    )

    # Summary totals
    total_billed: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total amount billed",
    )]
    total_paid: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total amount paid",
    )]
    total_outstanding: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Outstanding amount",
    )]
    total_refunded: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Total refunded amount",
    )]

    currency: str = Field(default="INR", description="Currency code")

    # Pagination info
    total_count: int = Field(
        default=0, ge=0, description="Total billing events"
    )
    page: int = Field(default=1, ge=1, description="Current page")
    page_size: int = Field(default=20, ge=1, description="Page size")

    @model_validator(mode="after")
    def validate_totals(self) -> "BillingHistory":
        """Validate total calculations."""
        expected_outstanding = self.total_billed - self.total_paid - self.total_refunded
        if expected_outstanding < Decimal("0"):
            expected_outstanding = Decimal("0")

        # Allow small floating point differences
        if abs(self.total_outstanding - expected_outstanding) > Decimal("0.01"):
            raise ValueError(
                f"total_outstanding ({self.total_outstanding}) does not match "
                f"calculated value ({expected_outstanding})"
            )
        return self

    @computed_field
    def has_outstanding(self) -> bool:
        """Check if there's outstanding balance."""
        return self.total_outstanding > Decimal("0")

    @computed_field
    def payment_rate(self) -> Decimal:
        """Calculate payment collection rate percentage."""
        if self.total_billed == Decimal("0"):
            return Decimal("100.00")
        return (
            (self.total_paid + self.total_refunded) / self.total_billed * 100
        ).quantize(Decimal("0.01"))