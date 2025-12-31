"""
Payment ledger model.

Double-entry bookkeeping for payment transactions.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date as SQLDate,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.payment.payment import Payment
    from app.models.student.student import Student
    from app.models.user.user import User


class LedgerEntryType(str, Enum):
    """Ledger entry type enum."""
    
    DEBIT = "debit"
    CREDIT = "credit"
    ADJUSTMENT = "adjustment"
    WRITEOFF = "writeoff"
    REVERSAL = "reversal"


class TransactionType(str, Enum):
    """Transaction type enum."""
    
    PAYMENT = "payment"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    WRITEOFF = "writeoff"
    FEE_CHARGE = "fee_charge"
    LATE_FEE = "late_fee"
    DISCOUNT = "discount"
    WAIVER = "waiver"


class PaymentLedger(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Payment ledger model for double-entry bookkeeping.
    
    Records all financial transactions with proper accounting principles.
    """

    __tablename__ = "payment_ledgers"

    # ==================== Foreign Keys ====================
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    posted_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="User who posted this entry",
    )

    # ==================== Entry Details ====================
    entry_reference: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique ledger entry reference",
    )
    
    entry_type: Mapped[LedgerEntryType] = mapped_column(
        SQLEnum(LedgerEntryType, name="ledger_entry_type_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Type of ledger entry",
    )
    
    transaction_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType, name="transaction_type_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Specific transaction type",
    )

    # ==================== Amount Details ====================
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Transaction amount (positive for credit, negative for debit)",
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code",
    )

    # ==================== Balance Tracking ====================
    balance_before: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Account balance before this transaction",
    )
    
    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Account balance after this transaction",
    )

    # ==================== Transaction Details ====================
    transaction_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Date of transaction",
    )
    
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When entry was posted to ledger",
    )

    # ==================== References ====================
    payment_reference: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Associated payment reference",
    )
    
    external_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="External reference number",
    )

    # ==================== Description ====================
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Entry description",
    )
    
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes",
    )

    # ==================== Reconciliation ====================
    is_reconciled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether entry is reconciled",
    )
    
    reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When entry was reconciled",
    )
    
    reconciled_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who reconciled this entry",
    )

    # ==================== Reversal Tracking ====================
    is_reversed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this entry has been reversed",
    )
    
    reversed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When entry was reversed",
    )
    
    reversal_entry_id: Mapped[UUID | None] = mapped_column(
        UUID,
        nullable=True,
        comment="ID of reversal entry",
    )
    
    reversal_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for reversal",
    )

    # ==================== Additional Data ====================
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )

    # ==================== Relationships ====================
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="ledger_entries",
        lazy="selectin",
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="ledger_entries",
        lazy="selectin",
    )
    
    payment: Mapped["Payment | None"] = relationship(
        "Payment",
        back_populates="ledger_entries",
        lazy="selectin",
    )
    
    poster: Mapped["User"] = relationship(
        "User",
        foreign_keys=[posted_by],
        lazy="selectin",
    )
    
    reconciler: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reconciled_by],
        lazy="selectin",
    )

    # ==================== Indexes ====================
    __table_args__ = (
        Index("idx_ledger_student_date", "student_id", "transaction_date"),
        Index("idx_ledger_hostel_date", "hostel_id", "transaction_date"),
        Index("idx_ledger_payment_id", "payment_id"),
        Index("idx_ledger_entry_type", "entry_type"),
        Index("idx_ledger_transaction_type", "transaction_type"),
        Index("idx_ledger_posted_at", "posted_at"),
        Index("idx_ledger_reconciled", "is_reconciled"),
        Index("idx_ledger_reversed", "is_reversed"),
        Index("idx_ledger_reference_lower", func.lower(entry_reference)),
        {"comment": "Payment ledger for double-entry bookkeeping"},
    )

    # ==================== Properties ====================
    @property
    def is_debit(self) -> bool:
        """Check if this is a debit entry."""
        return self.entry_type == LedgerEntryType.DEBIT or self.amount < 0

    @property
    def is_credit(self) -> bool:
        """Check if this is a credit entry."""
        return self.entry_type == LedgerEntryType.CREDIT or self.amount > 0

    @property
    def absolute_amount(self) -> Decimal:
        """Get absolute value of amount."""
        return abs(self.amount)

    @property
    def balance_change(self) -> Decimal:
        """Calculate balance change from this entry."""
        return self.balance_after - self.balance_before

    # ==================== Methods ====================
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaymentLedger("
            f"id={self.id}, "
            f"reference={self.entry_reference}, "
            f"type={self.entry_type.value}, "
            f"amount={self.amount}"
            f")>"
        )