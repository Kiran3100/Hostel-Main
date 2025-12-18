"""
Booking Commission Models.

Tracks commission owed to the platform for bookings
made through the subscription system.
"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin
from app.schemas.subscription.commission import CommissionStatus

if TYPE_CHECKING:
    from app.models.subscription.subscription import Subscription

__all__ = [
    "BookingCommission",
]


class BookingCommission(UUIDMixin, TimestampModel):
    """
    Commission record for a booking.

    Tracks the commission owed to the platform for a specific booking,
    including calculation details and payment status.
    """

    __tablename__ = "booking_commissions"
    __table_args__ = (
        CheckConstraint(
            "booking_amount >= 0",
            name="ck_commission_booking_amount_positive",
        ),
        CheckConstraint(
            "commission_percentage >= 0 AND commission_percentage <= 100",
            name="ck_commission_percentage_range",
        ),
        CheckConstraint(
            "commission_amount >= 0",
            name="ck_commission_amount_positive",
        ),
        CheckConstraint(
            "commission_amount = booking_amount * commission_percentage / 100",
            name="ck_commission_amount_calculation",
        ),
        Index(
            "ix_commission_booking_id",
            "booking_id",
        ),
        Index(
            "ix_commission_hostel_status",
            "hostel_id",
            "status",
        ),
        Index(
            "ix_commission_status_due_date",
            "status",
            "due_date",
        ),
        {"schema": "public"},
    )

    # Booking Reference
    booking_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Associated booking ID",
    )

    # Hostel Reference
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Hostel ID",
    )

    # Subscription Reference
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Active subscription ID",
    )

    # Commission Calculation
    booking_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Total booking amount",
    )
    commission_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Applied commission percentage",
    )
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Calculated commission amount",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="ISO 4217 currency code",
    )

    # Payment Status
    status: Mapped[CommissionStatus] = mapped_column(
        nullable=False,
        default=CommissionStatus.PENDING,
        index=True,
        comment="Commission payment status",
    )
    due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Commission payment due date",
    )
    paid_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Actual payment date",
    )
    payment_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Payment transaction reference",
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="commissions",
    )

    def __repr__(self) -> str:
        return f"<BookingCommission(id={self.id}, booking_id={self.booking_id}, amount={self.commission_amount}, status={self.status})>"

    @property
    def is_paid(self) -> bool:
        """Check if commission has been paid."""
        return self.status == CommissionStatus.PAID

    @property
    def is_overdue(self) -> bool:
        """Check if commission payment is overdue."""
        if self.due_date is None or self.status == CommissionStatus.PAID:
            return False
        return date.today() > self.due_date

    @property
    def days_overdue(self) -> int:
        """Calculate days overdue."""
        if not self.is_overdue:
            return 0
        return (date.today() - self.due_date).days

    @property
    def days_until_due(self) -> int:
        """Calculate days until due date."""
        if self.due_date is None:
            return 0
        today = date.today()
        if self.due_date < today:
            return 0
        return (self.due_date - today).days