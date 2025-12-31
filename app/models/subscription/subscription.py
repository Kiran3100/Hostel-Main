"""
Subscription Models.

Manages hostel subscription lifecycle including creation,
activation, renewal, and cancellation.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, UUIDMixin
from app.schemas.common.enums import BillingCycle, SubscriptionStatus

if TYPE_CHECKING:
    from app.models.subscription.subscription_billing import SubscriptionBillingCycle
    from app.models.subscription.subscription_invoice import SubscriptionInvoice
    from app.models.subscription.subscription_plan import SubscriptionPlan
    from app.models.subscription.booking_commission import BookingCommission

__all__ = [
    "Subscription",
    "SubscriptionHistory",
    "SubscriptionCancellation",
]


class Subscription(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Active hostel subscription.

    Tracks subscription relationship between a hostel and a plan,
    including billing, renewal, and lifecycle management.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "subscription_reference",
            name="uq_subscription_reference",
        ),
        Index(
            "uq_subscription_hostel_active",
            "hostel_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        CheckConstraint(
            "end_date >= start_date",
            name="ck_subscription_end_after_start",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_subscription_amount_positive",
        ),
        CheckConstraint(
            "trial_end_date IS NULL OR trial_end_date >= start_date",
            name="ck_subscription_trial_after_start",
        ),
        Index(
            "ix_subscription_hostel_status",
            "hostel_id",
            "status",
        ),
        Index(
            "ix_subscription_status_end_date",
            "status",
            "end_date",
        ),
        {"schema": "public"},
    )

    # Hostel Reference
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Hostel ID",
    )

    # Plan Reference
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Subscription plan ID",
    )

    # Subscription Details
    subscription_reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique subscription reference (e.g., SUB-2024-001)",
    )

    # Billing Configuration
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        nullable=False,
        comment="Billing cycle (monthly/yearly)",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Amount per billing period",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="ISO 4217 currency code",
    )

    # Subscription Period
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Subscription start date",
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Subscription end date",
    )

    # Renewal Configuration
    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Auto-renew subscription on expiry",
    )
    next_billing_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Next scheduled billing date",
    )

    # Status
    status: Mapped[SubscriptionStatus] = mapped_column(
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
        index=True,
        comment="Current subscription status",
    )

    # Trial Period
    trial_end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Trial period end date",
    )
    is_trial: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Currently in trial period",
    )

    # Payment Tracking
    last_payment_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Last successful payment date",
    )
    last_payment_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Last payment amount",
    )

    # Cancellation Info
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Cancellation timestamp",
    )
    cancelled_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who cancelled subscription",
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for cancellation",
    )
    cancellation_effective_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date when cancellation takes effect",
    )

    # Relationships
    plan: Mapped["SubscriptionPlan"] = relationship(
        "SubscriptionPlan",
        back_populates="subscriptions",
        lazy="joined",
    )
    billing_cycles: Mapped[List["SubscriptionBillingCycle"]] = relationship(
        "SubscriptionBillingCycle",
        back_populates="subscription",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    invoices: Mapped[List["SubscriptionInvoice"]] = relationship(
        "SubscriptionInvoice",
        back_populates="subscription",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    history: Mapped[List["SubscriptionHistory"]] = relationship(
        "SubscriptionHistory",
        back_populates="subscription",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    commissions: Mapped[List["BookingCommission"]] = relationship(
        "BookingCommission",
        back_populates="subscription",
        lazy="dynamic",
    )
    cancellation_record: Mapped[Optional["SubscriptionCancellation"]] = relationship(
        "SubscriptionCancellation",
        back_populates="subscription",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, reference={self.subscription_reference}, status={self.status})>"

    @property
    def days_until_expiry(self) -> int:
        """Calculate days until subscription expires."""
        today = date.today()
        if self.end_date < today:
            return 0
        return (self.end_date - today).days

    @property
    def days_until_billing(self) -> Optional[int]:
        """Calculate days until next billing."""
        if self.next_billing_date is None:
            return None
        today = date.today()
        if self.next_billing_date < today:
            return 0
        return (self.next_billing_date - today).days

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status == SubscriptionStatus.ACTIVE and not self.is_deleted

    @property
    def is_expiring_soon(self) -> bool:
        """Check if subscription expires within 7 days."""
        return 0 < self.days_until_expiry <= 7

    @property
    def is_in_trial_period(self) -> bool:
        """Check if currently in trial period."""
        if self.trial_end_date is None:
            return False
        return date.today() <= self.trial_end_date

    def can_renew(self) -> bool:
        """Check if subscription can be renewed."""
        return (
            self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED)
            and not self.is_deleted
        )

    def can_cancel(self) -> bool:
        """Check if subscription can be cancelled."""
        return (
            self.status == SubscriptionStatus.ACTIVE
            and self.cancelled_at is None
            and not self.is_deleted
        )

    def can_upgrade(self) -> bool:
        """Check if subscription can be upgraded."""
        return self.status == SubscriptionStatus.ACTIVE and not self.is_deleted


class SubscriptionHistory(UUIDMixin, TimestampModel):
    """
    Subscription change history.

    Tracks all significant changes to subscription including
    status changes, plan changes, and modifications.
    """

    __tablename__ = "subscription_history"
    __table_args__ = (
        Index(
            "ix_subscription_history_subscription_timestamp",
            "subscription_id",
            "changed_at",
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

    # Change Information
    change_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of change (status, plan, billing, etc.)",
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Timestamp of change",
    )
    changed_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who made the change",
    )

    # Change Details
    old_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Previous value (JSON string)",
    )
    new_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="New value (JSON string)",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for change",
    )

    # Metadata
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of change initiator",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User agent of change initiator",
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="history",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionHistory(id={self.id}, subscription_id={self.subscription_id}, change_type={self.change_type})>"


class SubscriptionCancellation(UUIDMixin, TimestampModel):
    """
    Subscription cancellation record.

    Stores detailed cancellation information including
    reason, feedback, and refund details.
    """

    __tablename__ = "subscription_cancellations"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            name="uq_subscription_cancellation_subscription",
        ),
        {"schema": "public"},
    )

    # Subscription Reference
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Cancelled subscription ID",
    )

    # Cancellation Details
    cancelled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Cancellation timestamp",
    )
    cancelled_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="User who initiated cancellation",
    )
    cancellation_effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date when cancellation takes effect",
    )

    # Reason and Feedback
    cancellation_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed reason for cancellation",
    )
    cancellation_category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Cancellation category",
    )
    feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional feedback for improvement",
    )
    would_recommend: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Would recommend to others",
    )

    # Cancellation Type
    cancel_immediately: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Cancelled immediately vs at end of term",
    )

    # Refund Information
    refund_issued: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether refund was issued",
    )
    refund_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Refund amount if applicable",
    )
    refund_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Refund transaction reference",
    )

    # Reactivation
    reactivation_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether subscription can be reactivated",
    )
    reactivation_deadline: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Deadline to reactivate subscription",
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="cancellation_record",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionCancellation(id={self.id}, subscription_id={self.subscription_id}, cancelled_at={self.cancelled_at})>"