# --- File: app/models/referral/referral.py ---
"""
Referral Model.

Tracks individual referrals from one user to another with complete
lifecycle management, conversion tracking, and reward processing.
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
from app.models.base.mixins import SoftDeleteMixin, TimestampMixin
from app.schemas.common.enums import ReferralStatus, RewardStatus

if TYPE_CHECKING:
    from app.models.booking.booking import Booking
    from app.models.referral.referral_code import ReferralCode
    from app.models.referral.referral_program import ReferralProgram
    from app.models.referral.referral_reward import ReferralReward
    from app.models.user.user import User

__all__ = ["Referral"]


class Referral(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Referral Model.
    
    Tracks individual referrals with complete lifecycle from creation
    through conversion to reward distribution.
    """

    __tablename__ = "referrals"

    # Program and Referrer
    program_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("referral_programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Referral program ID",
    )
    
    referrer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID of referrer",
    )

    # Referee Information
    referee_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Email of referred person",
    )
    
    referee_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Phone of referred person",
    )
    
    referee_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User ID of referee (after registration)",
    )
    
    referee_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Name of referred person",
    )

    # Referral Code
    referral_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Referral code used",
    )
    
    code_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("referral_codes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to referral code entity",
    )

    # Status Tracking
    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus, native_enum=False, length=50),
        nullable=False,
        default=ReferralStatus.PENDING,
        index=True,
        comment="Current referral status",
    )

    # Conversion Tracking
    booking_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Booking ID if converted",
    )
    
    booking_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Booking amount",
    )
    
    stay_duration_months: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Stay duration in months",
    )
    
    conversion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When referral converted",
    )

    # Reward Tracking
    referrer_reward_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Reward amount for referrer",
    )
    
    referee_reward_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Reward amount for referee",
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code",
    )

    # Reward Status
    referrer_reward_status: Mapped[RewardStatus] = mapped_column(
        Enum(RewardStatus, native_enum=False, length=50),
        nullable=False,
        default=RewardStatus.PENDING,
        index=True,
        comment="Status of referrer's reward",
    )
    
    referee_reward_status: Mapped[RewardStatus] = mapped_column(
        Enum(RewardStatus, native_enum=False, length=50),
        nullable=False,
        default=RewardStatus.PENDING,
        index=True,
        comment="Status of referee's reward",
    )

    # Source Tracking
    referral_source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Source of referral (whatsapp, email, social)",
    )
    
    campaign_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="Marketing campaign ID if applicable",
    )
    
    utm_parameters: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="UTM tracking parameters",
    )

    # Journey Tracking
    referee_registration_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When referee registered",
    )
    
    first_interaction_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="First interaction with referral link",
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

    # Status History (JSONB for flexibility)
    status_history: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="History of status changes",
    )

    # Relationships
    program: Mapped["ReferralProgram"] = relationship(
        "ReferralProgram",
        back_populates="referrals",
        lazy="joined",
    )
    
    referrer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[referrer_id],
        back_populates="referrals_made",
        lazy="joined",
    )
    
    referee: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[referee_user_id],
        back_populates="referrals_received",
        lazy="joined",
    )
    
    code: Mapped["ReferralCode | None"] = relationship(
        "ReferralCode",
        back_populates="referrals",
        lazy="joined",
    )
    
    booking: Mapped["Booking | None"] = relationship(
        "Booking",
        back_populates="referral",
        lazy="joined",
    )
    
    rewards: Mapped[list["ReferralReward"]] = relationship(
        "ReferralReward",
        back_populates="referral",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Table Constraints
    __table_args__ = (
        CheckConstraint(
            "referee_email IS NOT NULL OR referee_phone IS NOT NULL OR referee_user_id IS NOT NULL",
            name="ck_referral_referee_identifier_required",
        ),
        CheckConstraint(
            "referrer_reward_amount IS NULL OR referrer_reward_amount >= 0",
            name="ck_referral_referrer_reward_positive",
        ),
        CheckConstraint(
            "referee_reward_amount IS NULL OR referee_reward_amount >= 0",
            name="ck_referral_referee_reward_positive",
        ),
        CheckConstraint(
            "booking_amount IS NULL OR booking_amount >= 0",
            name="ck_referral_booking_amount_positive",
        ),
        CheckConstraint(
            "stay_duration_months IS NULL OR (stay_duration_months >= 1 AND stay_duration_months <= 24)",
            name="ck_referral_stay_duration_range",
        ),
        Index("ix_referral_program_referrer", "program_id", "referrer_id"),
        Index("ix_referral_status_conversion", "status", "conversion_date"),
        Index("ix_referral_reward_status", "referrer_reward_status", "referee_reward_status"),
        Index("ix_referral_referee_contact", "referee_email", "referee_phone"),
        Index("ix_referral_source_campaign", "referral_source", "campaign_id"),
        Index("ix_referral_dates", "created_at", "conversion_date"),
        {"comment": "Individual referral tracking with conversion and reward management"},
    )

    def __repr__(self) -> str:
        return (
            f"<Referral(id={self.id}, "
            f"code='{self.referral_code}', "
            f"referrer_id={self.referrer_id}, "
            f"status={self.status.value}, "
            f"converted={self.is_converted})>"
        )

    @property
    def is_converted(self) -> bool:
        """Check if referral has converted to booking."""
        return (
            self.status == ReferralStatus.COMPLETED
            and self.booking_id is not None
        )

    @property
    def total_reward_amount(self) -> Decimal:
        """Calculate total reward amount (referrer + referee)."""
        referrer = self.referrer_reward_amount or Decimal("0.00")
        referee = self.referee_reward_amount or Decimal("0.00")
        return referrer + referee

    @property
    def days_since_referral(self) -> int:
        """Calculate days since referral was created."""
        return (datetime.utcnow() - self.created_at).days

    @property
    def conversion_time_days(self) -> int | None:
        """Calculate days from referral to conversion."""
        if self.conversion_date:
            return (self.conversion_date - self.created_at).days
        return None

    @property
    def is_reward_fully_paid(self) -> bool:
        """Check if both rewards have been paid."""
        return (
            self.referrer_reward_status == RewardStatus.PAID
            and self.referee_reward_status == RewardStatus.PAID
        )

    def add_status_to_history(
        self,
        old_status: ReferralStatus,
        new_status: ReferralStatus,
        changed_by: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        """Add status change to history."""
        if self.status_history is None:
            self.status_history = []
        
        self.status_history.append({
            "old_status": old_status.value,
            "new_status": new_status.value,
            "changed_at": datetime.utcnow().isoformat(),
            "changed_by": str(changed_by) if changed_by else None,
            "reason": reason,
        })

    def mark_converted(
        self,
        booking_id: UUID,
        booking_amount: Decimal,
        stay_duration_months: int,
    ) -> None:
        """Mark referral as converted."""
        old_status = self.status
        self.status = ReferralStatus.COMPLETED
        self.booking_id = booking_id
        self.booking_amount = booking_amount
        self.stay_duration_months = stay_duration_months
        self.conversion_date = datetime.utcnow()
        
        self.add_status_to_history(
            old_status,
            ReferralStatus.COMPLETED,
            reason="Booking completed",
        )

    def cancel(self, reason: str | None = None) -> None:
        """Cancel the referral."""
        old_status = self.status
        self.status = ReferralStatus.CANCELLED
        
        self.add_status_to_history(
            old_status,
            ReferralStatus.CANCELLED,
            reason=reason or "Cancelled",
        )

    def expire(self) -> None:
        """Mark referral as expired."""
        old_status = self.status
        self.status = ReferralStatus.EXPIRED
        
        self.add_status_to_history(
            old_status,
            ReferralStatus.EXPIRED,
            reason="Referral expired",
        )