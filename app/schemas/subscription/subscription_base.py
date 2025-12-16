"""
Hostel subscription base schemas.

Defines the core subscription data structures for creating,
updating, and managing hostel subscriptions.
"""

from datetime import date as Date
from decimal import Decimal
from typing import Union, Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import BillingCycle, SubscriptionStatus

__all__ = [
    "SubscriptionBase",
    "SubscriptionCreate",
    "SubscriptionUpdate",
]


class SubscriptionBase(BaseSchema):
    """
    Base subscription schema for a hostel.

    Contains all core fields that define a subscription relationship
    between a hostel and a subscription plan.
    """
    model_config = ConfigDict(populate_by_name=True)

    hostel_id: UUID = Field(..., description="Hostel ID")
    plan_id: UUID = Field(..., description="Subscription plan ID")

    subscription_reference: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z0-9\-]+$",
        description="Unique subscription reference (e.g., SUB-2024-001)",
    )

    billing_cycle: BillingCycle = Field(
        ..., description="Billing cycle (monthly/yearly)"
    )
    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Amount per billing period",
    )]
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )

    start_date: Date = Field(..., description="Subscription start Date")
    end_date: Date = Field(..., description="Subscription end Date")

    auto_renew: bool = Field(
        default=True, description="Auto-renew subscription on expiry"
    )
    next_billing_date: Union[Date, None] = Field(
        None, description="Next scheduled billing Date"
    )

    status: SubscriptionStatus = Field(
        default=SubscriptionStatus.ACTIVE,
        description="Current subscription status",
    )

    @model_validator(mode="after")
    def validate_dates(self) -> "SubscriptionBase":
        """Validate subscription Date relationships."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after or equal to start_date")

        if self.next_billing_date is not None:
            if self.next_billing_date < self.start_date:
                raise ValueError(
                    "next_billing_date cannot be before start_date"
                )
            if self.next_billing_date > self.end_date and self.auto_renew:
                # Allow next billing after end_date only if auto_renew is True
                pass
            elif self.next_billing_date > self.end_date:
                raise ValueError(
                    "next_billing_date cannot be after end_date when auto_renew is False"
                )

        return self

    @field_validator("subscription_reference")
    @classmethod
    def normalize_reference(cls, v: str) -> str:
        """Normalize subscription reference to uppercase."""
        return v.upper().strip()


class SubscriptionCreate(BaseCreateSchema):
    """
    Create new hostel subscription.

    Extends base subscription with trial period support.
    """
    model_config = ConfigDict(populate_by_name=True)

    hostel_id: UUID = Field(..., description="Hostel ID")
    plan_id: UUID = Field(..., description="Subscription plan ID")

    subscription_reference: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique subscription reference",
    )

    billing_cycle: BillingCycle = Field(
        ..., description="Billing cycle (monthly/yearly)"
    )
    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Amount per billing period",
    )]
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )

    start_date: Date = Field(..., description="Subscription start Date")
    end_date: Date = Field(..., description="Subscription end Date")

    auto_renew: bool = Field(default=True)
    next_billing_date: Union[Date, None] = Field(None)

    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)

    trial_end_date: Union[Date, None] = Field(
        None,
        description="Trial period end Date (if applicable)",
    )

    @model_validator(mode="after")
    def validate_create_dates(self) -> "SubscriptionCreate":
        """Validate all Date relationships for creation."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after or equal to start_date")

        if self.trial_end_date is not None:
            if self.trial_end_date < self.start_date:
                raise ValueError("trial_end_date cannot be before start_date")
            if self.trial_end_date > self.end_date:
                raise ValueError("trial_end_date cannot be after end_date")

        if self.next_billing_date is not None:
            if self.next_billing_date < self.start_date:
                raise ValueError("next_billing_date cannot be before start_date")

        return self

    @field_validator("subscription_reference")
    @classmethod
    def normalize_reference(cls, v: str) -> str:
        """Normalize subscription reference to uppercase."""
        return v.upper().strip()


class SubscriptionUpdate(BaseUpdateSchema):
    """
    Update subscription.

    Allows partial updates to subscription status, dates, and renewal settings.
    """
    model_config = ConfigDict(populate_by_name=True)

    status: Union[SubscriptionStatus, None] = Field(
        None, description="New subscription status"
    )
    end_date: Union[Date, None] = Field(
        None, description="New subscription end Date"
    )
    auto_renew: Union[bool, None] = Field(
        None, description="Update auto-renewal setting"
    )
    next_billing_date: Union[Date, None] = Field(
        None, description="Update next billing Date"
    )

    # Additional updatable fields
    amount: Union[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Updated billing amount",
    )], None]
    billing_cycle: Union[BillingCycle, None] = Field(
        None, description="Updated billing cycle"
    )

    @model_validator(mode="after")
    def validate_update_consistency(self) -> "SubscriptionUpdate":
        """Validate update field consistency."""
        # If setting to cancelled/expired, auto_renew should be False
        if self.status in (
            SubscriptionStatus.CANCELLED,
            SubscriptionStatus.EXPIRED,
        ):
            if self.auto_renew is True:
                raise ValueError(
                    f"auto_renew cannot be True when status is {self.status.value}"
                )
        return self