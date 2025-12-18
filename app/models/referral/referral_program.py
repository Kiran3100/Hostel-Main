# --- File: app/models/referral/referral_program.py ---
"""
Referral Program Model.

Defines referral programs with reward structures, eligibility criteria,
and validity periods.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    Enum,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.referral.referral import Referral
    from app.models.referral.referral_code import ReferralCode

__all__ = ["ReferralProgram"]


class ReferralProgram(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Referral Program Model.
    
    Manages referral programs with comprehensive reward structures,
    eligibility criteria, and performance tracking.
    """

    __tablename__ = "referral_programs"

    # Program Identification
    program_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique program name",
    )
    
    program_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique program code",
    )
    
    program_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of referral program",
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Program description and benefits",
    )

    # Reward Configuration
    reward_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of reward offered",
    )
    
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
        comment="Currency code (ISO 4217)",
    )

    # Reward Caps
    max_referrer_rewards_per_month: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Maximum rewards referrer can earn per month",
    )
    
    max_total_reward_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Maximum total reward amount per referrer",
    )

    # Eligibility Criteria
    min_booking_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Minimum booking amount to qualify",
    )
    
    min_stay_months: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Minimum stay duration in months",
    )
    
    min_referrer_stay_months: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Minimum months referrer must have stayed",
    )

    # Referral Limitations
    max_referrals_per_user: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Maximum referrals allowed per user",
    )
    
    allowed_user_roles: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=["student", "alumni"],
        comment="User roles eligible to participate",
    )

    # Program Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether program is currently active",
    )
    
    valid_from: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Program start date",
    )
    
    valid_to: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Program end date",
    )

    # Terms and Conditions
    terms_and_conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed terms and conditions",
    )
    
    auto_approve_rewards: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Automatically approve rewards",
    )
    
    track_conversion: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Track conversion metrics",
    )

    # Statistics (Denormalized for performance)
    total_referrals: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total referrals made under this program",
    )
    
    successful_referrals: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Successfully converted referrals",
    )
    
    pending_referrals: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Pending referrals",
    )
    
    total_rewards_distributed: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total rewards paid out",
    )

    # Metadata
    metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional program metadata",
    )

    # Relationships
    referrals: Mapped[List["Referral"]] = relationship(
        "Referral",
        back_populates="program",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    
    referral_codes: Mapped[List["ReferralCode"]] = relationship(
        "ReferralCode",
        back_populates="program",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Table Constraints
    __table_args__ = (
        CheckConstraint(
            "referrer_reward_amount IS NULL OR referrer_reward_amount >= 0",
            name="ck_referral_program_referrer_reward_positive",
        ),
        CheckConstraint(
            "referee_reward_amount IS NULL OR referee_reward_amount >= 0",
            name="ck_referral_program_referee_reward_positive",
        ),
        CheckConstraint(
            "min_booking_amount IS NULL OR min_booking_amount >= 0",
            name="ck_referral_program_min_booking_positive",
        ),
        CheckConstraint(
            "min_stay_months IS NULL OR (min_stay_months >= 1 AND min_stay_months <= 24)",
            name="ck_referral_program_stay_months_range",
        ),
        CheckConstraint(
            "min_referrer_stay_months IS NULL OR (min_referrer_stay_months >= 0 AND min_referrer_stay_months <= 12)",
            name="ck_referral_program_referrer_stay_range",
        ),
        CheckConstraint(
            "max_referrals_per_user IS NULL OR (max_referrals_per_user >= 1 AND max_referrals_per_user <= 1000)",
            name="ck_referral_program_max_referrals_range",
        ),
        CheckConstraint(
            "max_referrer_rewards_per_month IS NULL OR (max_referrer_rewards_per_month >= 1 AND max_referrer_rewards_per_month <= 100)",
            name="ck_referral_program_max_rewards_month_range",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from",
            name="ck_referral_program_valid_date_range",
        ),
        CheckConstraint(
            "total_referrals >= 0",
            name="ck_referral_program_total_referrals_positive",
        ),
        CheckConstraint(
            "successful_referrals >= 0",
            name="ck_referral_program_successful_referrals_positive",
        ),
        CheckConstraint(
            "pending_referrals >= 0",
            name="ck_referral_program_pending_referrals_positive",
        ),
        CheckConstraint(
            "total_rewards_distributed >= 0",
            name="ck_referral_program_total_rewards_positive",
        ),
        Index("ix_referral_program_active_valid", "is_active", "valid_from", "valid_to"),
        Index("ix_referral_program_type_active", "program_type", "is_active"),
        Index("ix_referral_program_stats", "total_referrals", "successful_referrals"),
        {"comment": "Referral program definitions with reward structures and eligibility"},
    )

    def __repr__(self) -> str:
        return (
            f"<ReferralProgram(id={self.id}, "
            f"name='{self.program_name}', "
            f"code='{self.program_code}', "
            f"type='{self.program_type}', "
            f"active={self.is_active})>"
        )

    @property
    def conversion_rate(self) -> Decimal:
        """Calculate conversion rate percentage."""
        if self.total_referrals == 0:
            return Decimal("0.00")
        return Decimal(
            (self.successful_referrals / self.total_referrals * 100)
        ).quantize(Decimal("0.01"))

    @property
    def is_expired(self) -> bool:
        """Check if program has expired."""
        if self.valid_to is None:
            return False
        return Date.today() > self.valid_to

    @property
    def is_upcoming(self) -> bool:
        """Check if program hasn't started yet."""
        if self.valid_from is None:
            return False
        return Date.today() < self.valid_from

    @property
    def is_currently_valid(self) -> bool:
        """Check if program is currently valid and active."""
        if not self.is_active:
            return False
        
        today = Date.today()
        
        if self.valid_from and today < self.valid_from:
            return False
        
        if self.valid_to and today > self.valid_to:
            return False
        
        return True

    def increment_referral_count(self) -> None:
        """Increment total referral count."""
        self.total_referrals += 1

    def increment_successful_referrals(self) -> None:
        """Increment successful referral count and decrement pending."""
        self.successful_referrals += 1
        if self.pending_referrals > 0:
            self.pending_referrals -= 1

    def increment_pending_referrals(self) -> None:
        """Increment pending referral count."""
        self.pending_referrals += 1

    def add_reward_amount(self, amount: Decimal) -> None:
        """Add to total rewards distributed."""
        self.total_rewards_distributed += amount