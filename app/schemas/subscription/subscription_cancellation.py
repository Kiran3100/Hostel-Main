"""
Subscription cancellation schemas.

Handles subscription cancellation requests, processing,
and response tracking.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Union, List, Annotated
from uuid import UUID

from pydantic import Field, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "CancellationRequest",
    "CancellationResponse",
    "CancellationPreview",
]


class CancellationRequest(BaseCreateSchema):
    """
    Request to cancel a subscription.

    Supports both immediate cancellation and end-of-term cancellation
    with required reason tracking.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(
        ..., description="Subscription ID to cancel"
    )
    hostel_id: UUID = Field(
        ..., description="Hostel ID for verification"
    )

    cancellation_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for cancellation",
    )
    cancellation_category: Union[str, None] = Field(
        None,
        max_length=50,
        description="Cancellation category (e.g., 'pricing', 'features', 'switching')",
    )

    cancel_immediately: bool = Field(
        default=False,
        description="Cancel immediately vs at end of current term",
    )

    # Optional feedback
    feedback: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Additional feedback for improvement",
    )
    would_recommend: Union[bool, None] = Field(
        None, description="Would recommend to others"
    )

    @model_validator(mode="after")
    def validate_cancellation_reason(self) -> "CancellationRequest":
        """Validate cancellation reason is meaningful."""
        reason_words = len(self.cancellation_reason.split())
        if reason_words < 3:
            raise ValueError(
                "cancellation_reason must contain at least 3 words"
            )
        return self


class CancellationPreview(BaseSchema):
    """
    Preview of cancellation impact.

    Shows what will happen if the cancellation proceeds,
    including refund calculations and effective dates.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(..., description="Subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")

    current_plan_name: str = Field(..., description="Current plan name")
    billing_cycle: str = Field(..., description="Current billing cycle")

    # Dates
    cancellation_effective_date: Date = Field(
        ..., description="When cancellation takes effect"
    )
    current_period_end: Date = Field(
        ..., description="Current billing period end Date"
    )
    days_remaining: int = Field(
        ...,
        ge=0,
        description="Days remaining in current period",
    )

    # Financial impact
    refund_eligible: bool = Field(
        ..., description="Whether eligible for refund"
    )
    refund_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Calculated refund amount",
    )]
    currency: str = Field(default="INR")

    # Warnings
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about cancellation impact",
    )

    # Access impact
    access_ends_at: datetime = Field(
        ..., description="When service access ends"
    )


class CancellationResponse(BaseSchema):
    """
    Cancellation confirmation response.

    Confirms the cancellation was processed and provides
    all relevant details about the cancellation.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(..., description="Cancelled subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")

    cancelled: bool = Field(
        ..., description="Whether cancellation was successful"
    )
    cancellation_effective_date: Date = Field(
        ..., description="Date when cancellation takes effect"
    )
    cancelled_at: datetime = Field(
        ..., description="Timestamp when cancellation was processed"
    )
    cancelled_by: UUID = Field(
        ..., description="User ID who initiated cancellation"
    )

    # Refund info
    refund_issued: bool = Field(
        default=False, description="Whether refund was issued"
    )
    refund_amount: Union[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Refund amount if applicable",
    )], None]
    refund_reference: Union[str, None] = Field(
        None,
        max_length=100,
        description="Refund transaction reference",
    )

    message: str = Field(..., description="Confirmation message")

    # Next steps
    reactivation_eligible: bool = Field(
        default=True,
        description="Whether subscription can be reactivated",
    )
    reactivation_deadline: Union[Date, None] = Field(
        None, description="Deadline to reactivate subscription"
    )

    @model_validator(mode="after")
    def validate_refund_fields(self) -> "CancellationResponse":
        """Validate refund fields consistency."""
        if self.refund_issued:
            if self.refund_amount is None or self.refund_amount <= Decimal("0"):
                raise ValueError(
                    "refund_amount must be positive when refund_issued is True"
                )
        return self