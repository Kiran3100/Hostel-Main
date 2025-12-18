# --- File: app/models/referral/referral_code.py ---
"""
Referral Code Model.

Manages unique referral codes for users with usage tracking,
expiration, and analytics.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.referral.referral import Referral
    from app.models.referral.referral_program import ReferralProgram
    from app.models.user.user import User

__all__ = ["ReferralCode"]


class ReferralCode(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Referral Code Model.
    
    Manages unique referral codes with usage tracking, analytics,
    and intelligent recommendation features.
    """

    __tablename__ = "referral_codes"

    # User and Program Association
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Code owner user ID",
    )
    
    program_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("referral_programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated referral program",
    )

    # Code Details
    referral_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique referral code",
    )
    
    code_prefix: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="HOSTEL",
        comment="Code prefix",
    )
    
    custom_suffix: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Custom suffix (if any)",
    )

    # Sharing and Distribution
    share_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Shareable URL with embedded code",
    )
    
    qr_code_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="QR code image URL",
    )

    # Usage Tracking
    times_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times code has been used",
    )
    
    max_uses: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="Maximum allowed uses",
    )
    
    times_shared: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times code was shared",
    )
    
    times_clicked: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of clicks on referral link",
    )

    # Status and Validity
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether code is currently active",
    )
    
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Code expiration timestamp",
    )
    
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last usage timestamp",
    )

    # Analytics
    total_registrations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total registrations from this code",
    )
    
    total_bookings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total bookings from this code",
    )

    # Metadata
    source_channels: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Channels where code was shared (social, email, etc.)",
    )
    
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes",
    )
    
    metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="referral_codes",
        lazy="joined",
    )
    
    program: Mapped["ReferralProgram"] = relationship(
        "ReferralProgram",
        back_populates="referral_codes",
        lazy="joined",
    )
    
    referrals: Mapped[List["Referral"]] = relationship(
        "Referral",
        back_populates="code",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Table Constraints
    __table_args__ = (
        CheckConstraint(
            "times_used >= 0",
            name="ck_referral_code_times_used_positive",
        ),
        CheckConstraint(
            "max_uses >= 1 AND max_uses <= 1000",
            name="ck_referral_code_max_uses_range",
        ),
        CheckConstraint(
            "times_used <= max_uses",
            name="ck_referral_code_usage_within_limit",
        ),
        CheckConstraint(
            "times_shared >= 0",
            name="ck_referral_code_times_shared_positive",
        ),
        CheckConstraint(
            "times_clicked >= 0",
            name="ck_referral_code_times_clicked_positive",
        ),
        CheckConstraint(
            "total_registrations >= 0",
            name="ck_referral_code_registrations_positive",
        ),
        CheckConstraint(
            "total_bookings >= 0",
            name="ck_referral_code_bookings_positive",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="ck_referral_code_expiry_after_creation",
        ),
        Index("ix_referral_code_user_program", "user_id", "program_id"),
        Index("ix_referral_code_active_expiry", "is_active", "expires_at"),
        Index("ix_referral_code_usage", "times_used", "max_uses"),
        Index("ix_referral_code_stats", "total_registrations", "total_bookings"),
        {"comment": "Unique referral codes with usage tracking and analytics"},
    )

    def __repr__(self) -> str:
        return (
            f"<ReferralCode(id={self.id}, "
            f"code='{self.referral_code}', "
            f"user_id={self.user_id}, "
            f"uses={self.times_used}/{self.max_uses}, "
            f"active={self.is_active})>"
        )

    @property
    def remaining_uses(self) -> int:
        """Calculate remaining uses available."""
        return max(0, self.max_uses - self.times_used)

    @property
    def is_expired(self) -> bool:
        """Check if code has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_exhausted(self) -> bool:
        """Check if code has reached maximum uses."""
        return self.times_used >= self.max_uses

    @property
    def is_valid(self) -> bool:
        """Check if code is valid for use."""
        return (
            self.is_active
            and not self.is_expired
            and not self.is_exhausted
            and not self.is_deleted
        )

    @property
    def conversion_rate(self) -> float:
        """Calculate click-to-booking conversion rate."""
        if self.times_clicked == 0:
            return 0.0
        return round((self.total_bookings / self.times_clicked) * 100, 2)

    @property
    def registration_rate(self) -> float:
        """Calculate click-to-registration rate."""
        if self.times_clicked == 0:
            return 0.0
        return round((self.total_registrations / self.times_clicked) * 100, 2)

    def increment_usage(self) -> bool:
        """
        Increment usage count.
        
        Returns:
            bool: True if incremented successfully, False if limit reached
        """
        if self.times_used >= self.max_uses:
            return False
        
        self.times_used += 1
        self.last_used_at = datetime.utcnow()
        return True

    def increment_shares(self) -> None:
        """Increment share count."""
        self.times_shared += 1

    def increment_clicks(self) -> None:
        """Increment click count."""
        self.times_clicked += 1

    def increment_registrations(self) -> None:
        """Increment registration count."""
        self.total_registrations += 1

    def increment_bookings(self) -> None:
        """Increment booking count."""
        self.total_bookings += 1

    def deactivate(self) -> None:
        """Deactivate the referral code."""
        self.is_active = False