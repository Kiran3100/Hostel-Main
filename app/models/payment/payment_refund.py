"""
Payment refund model.

Handles payment refund requests, approvals, and processing.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.payment.payment import Payment
    from app.models.user.user import User


class RefundStatus(str, Enum):
    """Refund status enum."""
    
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentRefund(TimestampModel, UUIDMixin, SoftDeleteMixin, AuditMixin):
    """
    Payment refund model for handling refund requests and processing.
    
    Manages the complete refund lifecycle from request to completion.
    """

    __tablename__ = "payment_refunds"

    # ==================== Foreign Keys ====================
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    requested_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    processed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ==================== Refund Details ====================
    refund_reference: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique refund reference number",
    )
    
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Amount to be refunded",
    )
    
    original_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Original payment amount",
    )
    
    is_partial: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is a partial refund",
    )

    # ==================== Refund Reason ====================
    refund_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for refund request",
    )
    
    refund_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Category of refund (cancellation, overpayment, etc.)",
    )

    # ==================== Status ====================
    refund_status: Mapped[RefundStatus] = mapped_column(
        SQLEnum(RefundStatus, name="refund_status_enum", create_type=True),
        nullable=False,
        default=RefundStatus.PENDING,
        index=True,
    )

    # ==================== Approval Details ====================
    approval_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from approver",
    )
    
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection if applicable",
    )

    # ==================== Gateway Processing ====================
    gateway_refund_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="Refund ID from payment gateway",
    )
    
    gateway_response: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Gateway refund response data",
    )
    
    transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Refund transaction ID",
    )

    # ==================== Processing Details ====================
    processed_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Actually processed refund amount",
    )
    
    processing_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Processing fee deducted from refund",
    )

    # ==================== Timestamps ====================
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When refund was requested",
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When refund was approved",
    )
    
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When refund was rejected",
    )
    
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When refund processing started",
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When refund was completed",
    )
    
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When refund failed",
    )
    
    expected_completion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Expected refund completion time",
    )

    # ==================== Error Details ====================
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Error code if refund failed",
    )
    
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if refund failed",
    )

    # ==================== Additional Information ====================
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes",
    )
    
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )

    # ==================== Relationships ====================
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="refunds",
        lazy="selectin",
    )
    
    requester: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requested_by],
        lazy="selectin",
    )
    
    approver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="selectin",
    )
    
    processor: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[processed_by],
        lazy="selectin",
    )

    # ==================== Indexes ====================
    __table_args__ = (
        Index("idx_refund_payment_status", "payment_id", "refund_status"),
        Index("idx_refund_requested_at", "requested_at"),
        Index("idx_refund_status", "refund_status"),
        Index("idx_refund_reference_lower", func.lower(refund_reference)),
        {"comment": "Payment refund records and processing"},
    )

    # ==================== Properties ====================
    @property
    def is_pending(self) -> bool:
        """Check if refund is pending approval."""
        return self.refund_status == RefundStatus.PENDING

    @property
    def is_approved(self) -> bool:
        """Check if refund is approved."""
        return self.refund_status == RefundStatus.APPROVED

    @property
    def is_completed(self) -> bool:
        """Check if refund is completed."""
        return self.refund_status == RefundStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if refund failed."""
        return self.refund_status == RefundStatus.FAILED

    @property
    def refund_percentage(self) -> float:
        """Calculate refund percentage of original amount."""
        if self.original_amount == 0:
            return 0.0
        return float((self.refund_amount / self.original_amount) * 100)

    # ==================== Methods ====================
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaymentRefund("
            f"id={self.id}, "
            f"reference={self.refund_reference}, "
            f"amount={self.refund_amount}, "
            f"status={self.refund_status.value}"
            f")>"
        )