"""
Subscription Invoice Models.

Manages invoice generation, tracking, and payment
for subscription billing.
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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin
from app.schemas.subscription.subscription_billing import InvoiceStatus

if TYPE_CHECKING:
    from app.models.subscription.subscription import Subscription

__all__ = [
    "SubscriptionInvoice",
]


class SubscriptionInvoice(UUIDMixin, TimestampModel):
    """
    Subscription invoice record.

    Stores invoice details including amounts, status,
    and payment information.
    """

    __tablename__ = "subscription_invoices"
    __table_args__ = (
        UniqueConstraint(
            "invoice_number",
            name="uq_subscription_invoice_number",
        ),
        CheckConstraint(
            "due_date >= invoice_date",
            name="ck_invoice_due_after_issue",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="ck_invoice_subtotal_positive",
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="ck_invoice_discount_positive",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_invoice_tax_positive",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_invoice_amount_positive",
        ),
        CheckConstraint(
            "amount_paid >= 0",
            name="ck_invoice_amount_paid_positive",
        ),
        CheckConstraint(
            "amount_due >= 0",
            name="ck_invoice_amount_due_positive",
        ),
        CheckConstraint(
            "amount = subtotal - discount_amount + tax_amount",
            name="ck_invoice_amount_calculation",
        ),
        CheckConstraint(
            "amount_due = amount - amount_paid",
            name="ck_invoice_amount_due_calculation",
        ),
        Index(
            "ix_invoice_subscription_date",
            "subscription_id",
            "invoice_date",
        ),
        Index(
            "ix_invoice_status_due_date",
            "status",
            "due_date",
        ),
        {"schema": "public"},
    )

    # Subscription Reference
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Associated subscription ID",
    )

    # Hostel Reference (denormalized)
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Hostel ID",
    )

    # Invoice Identification
    invoice_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Invoice number (e.g., INV-2024-000001)",
    )

    # Invoice Dates
    invoice_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Invoice issue date",
    )
    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Payment due date",
    )

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Subtotal before adjustments",
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total discount applied",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Tax amount",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Total invoice amount",
    )
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Amount already paid",
    )
    amount_due: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Remaining amount due",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="ISO 4217 currency code",
    )

    # Status
    status: Mapped[InvoiceStatus] = mapped_column(
        nullable=False,
        default=InvoiceStatus.DRAFT,
        index=True,
        comment="Invoice status",
    )

    # Access URLs
    invoice_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to view/download invoice",
    )
    payment_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to pay invoice online",
    )

    # Additional Information
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Invoice notes",
    )
    discount_reason: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Reason for discount",
    )

    # Billing Period
    billing_period_start: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Billing period start date",
    )
    billing_period_end: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Billing period end date",
    )

    # Payment Information
    payment_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Payment transaction reference",
    )
    payment_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Actual payment date",
    )
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Payment method used",
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="invoices",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionInvoice(id={self.id}, invoice_number={self.invoice_number}, status={self.status})>"

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue based on current date."""
        return (
            self.status not in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED)
            and date.today() > self.due_date
        )

    @property
    def is_fully_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.amount_due <= Decimal("0")

    @property
    def is_partially_paid(self) -> bool:
        """Check if invoice is partially paid."""
        return Decimal("0") < self.amount_paid < self.amount

    @property
    def days_overdue(self) -> int:
        """Calculate days overdue."""
        if not self.is_overdue:
            return 0
        return (date.today() - self.due_date).days

    @property
    def days_until_due(self) -> int:
        """Calculate days until due date."""
        today = date.today()
        if self.due_date < today:
            return 0
        return (self.due_date - today).days