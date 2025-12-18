"""
Subscription Billing Models.

Manages billing cycles, schedules, and billing-related
information for subscriptions.
"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.subscription.subscription import Subscription

__all__ = [
    "SubscriptionBillingCycle",
]


class SubscriptionBillingCycle(UUIDMixin, TimestampModel):
    """
    Billing cycle information for subscription.

    Tracks individual billing periods with dates, amounts,
    and billing status.
    """

    __tablename__ = "subscription_billing_cycles"
    __table_args__ = (
        CheckConstraint(
            "cycle_end >= cycle_start",
            name="ck_billing_cycle_end_after_start",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_billing_cycle_amount_positive",
        ),
        CheckConstraint(
            "days_until_billing >= 0",
            name="ck_billing_cycle_days_positive",
        ),
        Index(
            "ix_billing_cycle_subscription_start",
            "subscription_id",
            "cycle_start",
        ),
        Index(
            "ix_billing_cycle_next_billing",
            "next_billing_date",
        ),
        {"schema": "public"},
    )

    # Subscription Reference
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Subscription ID",
    )

    # Hostel Reference (denormalized for query performance)
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Hostel ID",
    )

    # Plan Information (denormalized)
    plan_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Subscription plan name",
    )
    plan_display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Plan display name for UI",
    )

    # Cycle Period
    cycle_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Current cycle start date",
    )
    cycle_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Current cycle end date",
    )
    billing_cycle: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Billing cycle type (monthly/yearly)",
    )

    # Billing Amount
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Billing amount for this cycle",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="ISO 4217 currency code",
    )

    # Next Billing
    next_billing_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Next billing date",
    )
    days_until_billing: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Days until next billing",
    )
    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Auto-renewal status",
    )

    # Trial Information
    is_in_trial: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether currently in trial period",
    )
    trial_days_remaining: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Days remaining in trial",
    )

    # Billing Status
    is_billed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether billing has been processed",
    )
    billing_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Actual billing date",
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="billing_cycles",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionBillingCycle(id={self.id}, subscription_id={self.subscription_id}, cycle_start={self.cycle_start})>"

    @property
    def is_current_cycle(self) -> bool:
        """Check if this is the current active billing cycle."""
        today = date.today()
        return self.cycle_start <= today <= self.cycle_end

    @property
    def is_upcoming_cycle(self) -> bool:
        """Check if this is an upcoming billing cycle."""
        today = date.today()
        return self.cycle_start > today

    @property
    def is_past_cycle(self) -> bool:
        """Check if this is a past billing cycle."""
        today = date.today()
        return self.cycle_end < today