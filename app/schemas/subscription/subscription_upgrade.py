"""
Subscription upgrade/downgrade schemas.

Handles plan change requests, previews, and confirmations
for subscription modifications.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Union, Annotated
from uuid import UUID

from pydantic import Field, model_validator, computed_field, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import BillingCycle

__all__ = [
    "PlanChangeType",
    "PlanChangeRequest",
    "PlanChangePreview",
    "PlanChangeConfirmation",
]


class PlanChangeType(str, Enum):
    """Type of plan change."""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    LATERAL = "lateral"  # Same tier, different billing cycle


class PlanChangeRequest(BaseCreateSchema):
    """
    Request to change subscription plan.

    Supports upgrades, downgrades, and billing cycle changes
    with configurable timing and proration.
    """
    model_config = ConfigDict(populate_by_name=True)

    hostel_id: UUID = Field(..., description="Hostel ID")
    current_plan_id: UUID = Field(
        ..., description="Current subscription plan ID"
    )
    new_plan_id: UUID = Field(..., description="Target plan ID")
    billing_cycle: BillingCycle = Field(
        ..., description="Billing cycle for new plan"
    )

    # Timing
    effective_from: Date = Field(
        ..., description="When new plan takes effect"
    )
    prorate: bool = Field(
        default=True,
        description="Apply proration for partial periods",
    )

    # Options
    apply_credit: bool = Field(
        default=True,
        description="Apply unused balance as credit",
    )
    preserve_trial: bool = Field(
        default=False,
        description="Preserve remaining trial days if applicable",
    )

    # Reason tracking
    change_reason: Union[str, None] = Field(
        None,
        max_length=500,
        description="Reason for plan change",
    )

    @model_validator(mode="after")
    def validate_plan_change(self) -> "PlanChangeRequest":
        """Validate plan change request."""
        if self.current_plan_id == self.new_plan_id:
            raise ValueError(
                "new_plan_id must be different from current_plan_id"
            )

        today = Date.today()
        if self.effective_from < today:
            raise ValueError("effective_from cannot be in the past")

        return self


class PlanChangePreview(BaseSchema):
    """
    Preview cost impact of plan change.

    Shows detailed financial impact including prorations,
    credits, and final amounts before confirming the change.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Plan info
    current_plan_id: UUID = Field(..., description="Current plan ID")
    current_plan_name: str = Field(..., description="Current plan name")
    current_plan_display: str = Field(
        ..., description="Current plan display name"
    )

    new_plan_id: UUID = Field(..., description="New plan ID")
    new_plan_name: str = Field(..., description="New plan name")
    new_plan_display: str = Field(..., description="New plan display name")

    # Change type
    change_type: PlanChangeType = Field(
        ..., description="Type of plan change"
    )

    # Pricing
    current_amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Current plan amount",
    )]
    new_amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="New plan amount",
    )]
    currency: str = Field(default="INR", description="Currency code")

    # Current period info
    current_period_start: Date = Field(
        ..., description="Current billing period start"
    )
    current_period_end: Date = Field(
        ..., description="Current billing period end"
    )
    days_remaining: int = Field(
        ...,
        ge=0,
        description="Days remaining in current period",
    )

    # Proration calculations
    prorated_credit: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Credit for unused portion of current plan",
    )]
    prorated_charge: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Charge for new plan (prorated if applicable)",
    )]

    # Final amounts
    amount_due_now: Annotated[Decimal, Field(
        ...,
        description="Net amount due now (can be negative for credit)",
    )]
    next_billing_amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Amount on next regular billing",
    )]

    # Dates
    effective_from: Date = Field(
        ..., description="When change takes effect"
    )
    next_billing_date: Date = Field(
        ..., description="Next billing Date after change"
    )

    # Additional info
    message: str = Field(..., description="Summary message")
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about the plan change",
    )
    benefits: List[str] = Field(
        default_factory=list,
        description="Benefits of the new plan",
    )

    @computed_field  # type: ignore[misc]
    @property
    def is_upgrade(self) -> bool:
        """Check if this is an upgrade."""
        return self.change_type == PlanChangeType.UPGRADE

    @computed_field  # type: ignore[misc]
    @property
    def is_downgrade(self) -> bool:
        """Check if this is a downgrade."""
        return self.change_type == PlanChangeType.DOWNGRADE

    @computed_field  # type: ignore[misc]
    @property
    def monthly_difference(self) -> Decimal:
        """Calculate monthly price difference."""
        return (self.new_amount - self.current_amount).quantize(
            Decimal("0.01")
        )

    @computed_field  # type: ignore[misc]
    @property
    def savings_or_increase(self) -> str:
        """Format savings or increase message."""
        diff = self.monthly_difference
        if diff > Decimal("0"):
            return f"+{self.currency} {diff:,.2f}/period"
        elif diff < Decimal("0"):
            return f"-{self.currency} {abs(diff):,.2f}/period"
        return "No change"


class PlanChangeConfirmation(BaseSchema):
    """
    Confirmation of completed plan change.

    Returned after a plan change is successfully processed.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(..., description="Updated subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")

    # Change details
    previous_plan_id: UUID = Field(..., description="Previous plan ID")
    previous_plan_name: str = Field(..., description="Previous plan name")
    new_plan_id: UUID = Field(..., description="New plan ID")
    new_plan_name: str = Field(..., description="New plan name")
    change_type: PlanChangeType = Field(..., description="Type of change")

    # Financial
    amount_charged: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        description="Amount charged for the change",
    )]
    credit_applied: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Credit applied from previous plan",
    )]
    currency: str = Field(default="INR")

    # Dates
    effective_from: Date = Field(
        ..., description="When change took effect"
    )
    next_billing_date: Date = Field(..., description="Next billing Date")
    new_billing_amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="New regular billing amount",
    )]

    # Confirmation
    processed_at: datetime = Field(
        ..., description="When change was processed"
    )
    confirmation_number: str = Field(
        ..., description="Change confirmation reference"
    )
    message: str = Field(..., description="Confirmation message")