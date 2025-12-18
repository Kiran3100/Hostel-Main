# --- File: app/models/referral/referral_reward.py ---
"""
Referral Reward Model.

Manages reward tracking, payout processing, and financial reconciliation
for referral programs.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin
from app.schemas.common.enums import PaymentMethod, RewardStatus

if TYPE_CHECKING:
    from app.models.referral.referral import Referral
    from app.models.user.user import User

__all__ = ["ReferralReward", "RewardPayout"]


class ReferralReward(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Referral Reward Model.
    
    Tracks individual reward entries for referrals with complete
    lifecycle from eligibility through payout.
    """

    __tablename__ = "referral_rewards"

    # Referral and User Association
    referral_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("referrals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated referral",
    )
    
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User receiving reward",
    )
    
    recipient_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Type of recipient (referrer or referee)",
    )

    # Reward Amount
    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Base reward amount",
    )
    
    bonus_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Bonus amount (if any)",
    )
    
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Total reward amount",
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code",
    )

    # Deductions
    tax_deduction: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Tax deduction amount",
    )
    
    processing_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Processing fee",
    )
    
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Net amount after deductions",
    )

    # Status and Approval
    status: Mapped[RewardStatus] = mapped_column(
        Enum(RewardStatus, native_enum=False, length=50),
        nullable=False,
        default=RewardStatus.PENDING,
        index=True,
        comment="Reward status",
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp",
    )
    
    approved_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who approved",
    )
    
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection (if rejected)",
    )

    # Payout Information
    payout_request_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Associated payout request",
    )
    
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Payment timestamp",
    )
    
    paid_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who processed payment",
    )
    
    payment_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Payment method used",
    )
    
    transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="External transaction ID",
    )

    # Eligibility Calculation
    eligibility_calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When eligibility was calculated",
    )
    
    eligibility_criteria_met: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Eligibility criteria that were met",
    )

    # Notes and Metadata
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes",
    )
    
    admin_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Admin-only notes",
    )
    
    metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )

    # Relationships
    referral: Mapped["Referral"] = relationship(
        "Referral",
        back_populates="rewards",
        lazy="joined",
    )
    
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="referral_rewards",
        lazy="joined",
    )
    
    approver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select",
    )
    
    payer: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[paid_by],
        lazy="select",
    )

    # Table Constraints
    __table_args__ = (
        CheckConstraint(
            "base_amount >= 0",
            name="ck_referral_reward_base_amount_positive",
        ),
        CheckConstraint(
            "bonus_amount >= 0",
            name="ck_referral_reward_bonus_amount_positive",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_referral_reward_total_amount_positive",
        ),
        CheckConstraint(
            "tax_deduction >= 0",
            name="ck_referral_reward_tax_deduction_positive",
        ),
        CheckConstraint(
            "processing_fee >= 0",
            name="ck_referral_reward_processing_fee_positive",
        ),
        CheckConstraint(
            "net_amount >= 0",
            name="ck_referral_reward_net_amount_positive",
        ),
        CheckConstraint(
            "recipient_type IN ('referrer', 'referee')",
            name="ck_referral_reward_recipient_type_valid",
        ),
        Index("ix_referral_reward_user_status", "user_id", "status"),
        Index("ix_referral_reward_payout", "payout_request_id", "status"),
        Index("ix_referral_reward_dates", "approved_at", "paid_at"),
        {"comment": "Referral reward tracking with payout management"},
    )

    def __repr__(self) -> str:
        return (
            f"<ReferralReward(id={self.id}, "
            f"user_id={self.user_id}, "
            f"type={self.recipient_type}, "
            f"amount={self.net_amount} {self.currency}, "
            f"status={self.status.value})>"
        )

    @property
    def is_approved(self) -> bool:
        """Check if reward is approved."""
        return self.status == RewardStatus.APPROVED

    @property
    def is_paid(self) -> bool:
        """Check if reward is paid."""
        return self.status == RewardStatus.PAID

    @property
    def is_pending(self) -> bool:
        """Check if reward is pending."""
        return self.status == RewardStatus.PENDING

    @property
    def days_since_approval(self) -> int | None:
        """Calculate days since approval."""
        if self.approved_at:
            return (datetime.utcnow() - self.approved_at).days
        return None

    def approve(self, approved_by: UUID) -> None:
        """Approve the reward."""
        self.status = RewardStatus.APPROVED
        self.approved_at = datetime.utcnow()
        self.approved_by = approved_by

    def reject(self, rejected_by: UUID, reason: str) -> None:
        """Reject the reward."""
        self.status = RewardStatus.REJECTED
        self.approved_by = rejected_by
        self.approved_at = datetime.utcnow()
        self.rejection_reason = reason

    def mark_paid(
        self,
        paid_by: UUID,
        transaction_id: str,
        payment_method: str,
    ) -> None:
        """Mark reward as paid."""
        self.status = RewardStatus.PAID
        self.paid_at = datetime.utcnow()
        self.paid_by = paid_by
        self.transaction_id = transaction_id
        self.payment_method = payment_method

    def cancel(self, reason: str | None = None) -> None:
        """Cancel the reward."""
        self.status = RewardStatus.CANCELLED
        if reason:
            self.admin_notes = (
                f"{self.admin_notes}\nCancellation reason: {reason}"
                if self.admin_notes
                else f"Cancellation reason: {reason}"
            )


class RewardPayout(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Reward Payout Request Model.
    
    Manages payout requests for accumulated referral rewards.
    """

    __tablename__ = "reward_payouts"

    # User and Amount
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User requesting payout",
    )
    
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Requested payout amount",
    )
    
    processing_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Processing fee",
    )
    
    tax_deduction: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Tax deduction",
    )
    
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Net payout amount",
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code",
    )

    # Payment Details
    payout_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=50),
        nullable=False,
        comment="Payout method",
    )
    
    payout_details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Encrypted payout details (account info, UPI, etc.)",
    )
    
    urgent_payout: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Request urgent processing",
    )

    # Status Tracking
    status: Mapped[RewardStatus] = mapped_column(
        Enum(RewardStatus, native_enum=False, length=50),
        nullable=False,
        default=RewardStatus.PENDING,
        index=True,
        comment="Payout status",
    )
    
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Request timestamp",
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp",
    )
    
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Processing timestamp",
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Completion timestamp",
    )

    # Processing Information
    transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="External transaction ID",
    )
    
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Failure reason if applicable",
    )
    
    estimated_completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Estimated completion date",
    )

    # Approval and Processing
    approved_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who approved",
    )
    
    processed_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who processed",
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="User notes",
    )
    
    admin_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Admin notes",
    )
    
    metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="reward_payouts",
        lazy="joined",
    )
    
    approver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select",
    )
    
    processor: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[processed_by],
        lazy="select",
    )

    # Table Constraints
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_reward_payout_amount_positive",
        ),
        CheckConstraint(
            "processing_fee >= 0",
            name="ck_reward_payout_fee_positive",
        ),
        CheckConstraint(
            "tax_deduction >= 0",
            name="ck_reward_payout_tax_positive",
        ),
        CheckConstraint(
            "net_amount > 0",
            name="ck_reward_payout_net_amount_positive",
        ),
        Index("ix_reward_payout_user_status", "user_id", "status"),
        Index("ix_reward_payout_dates", "requested_at", "completed_at"),
        {"comment": "Reward payout request tracking and processing"},
    )

    def __repr__(self) -> str:
        return (
            f"<RewardPayout(id={self.id}, "
            f"user_id={self.user_id}, "
            f"amount={self.net_amount} {self.currency}, "
            f"method={self.payout_method.value}, "
            f"status={self.status.value})>"
        )

    @property
    def is_pending(self) -> bool:
        """Check if payout is pending."""
        return self.status == RewardStatus.PENDING

    @property
    def is_completed(self) -> bool:
        """Check if payout is completed."""
        return self.status == RewardStatus.PAID

    @property
    def processing_time_days(self) -> int | None:
        """Calculate processing time in days."""
        if self.completed_at:
            return (self.completed_at - self.requested_at).days
        return None

    def approve(self, approved_by: UUID, estimated_days: int = 7) -> None:
        """Approve payout request."""
        self.status = RewardStatus.APPROVED
        self.approved_at = datetime.utcnow()
        self.approved_by = approved_by
        
        # Set estimated completion date
        from datetime import timedelta
        self.estimated_completion_date = datetime.utcnow() + timedelta(days=estimated_days)

    def mark_processing(self, processed_by: UUID) -> None:
        """Mark payout as processing."""
        self.status = RewardStatus.PROCESSING
        self.processed_at = datetime.utcnow()
        self.processed_by = processed_by

    def mark_completed(self, transaction_id: str) -> None:
        """Mark payout as completed."""
        self.status = RewardStatus.PAID
        self.completed_at = datetime.utcnow()
        self.transaction_id = transaction_id

    def mark_failed(self, reason: str) -> None:
        """Mark payout as failed."""
        self.status = RewardStatus.FAILED
        self.failure_reason = reason