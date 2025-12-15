# app.models/transactions/referral.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.schemas.common.enums import ReferralStatus, RewardStatus
from app.models.base import BaseItem


class ReferralProgram(BaseItem):
    """Referral program definition."""
    __tablename__ = "ref_program"

    program_name: Mapped[str] = mapped_column(String(100))
    program_type: Mapped[str] = mapped_column(String(50))  # student_referral, visitor_referral, etc.

    reward_type: Mapped[str] = mapped_column(String(50))   # cash, discount, etc.
    referrer_reward_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    referee_reward_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    min_booking_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    min_stay_months: Mapped[Optional[int]] = mapped_column()

    terms_and_conditions: Mapped[Optional[str]] = mapped_column(String(5000))

    is_active: Mapped[bool] = mapped_column(default=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)


class Referral(BaseItem):
    """Individual referral record."""
    __tablename__ = "ref_referral"

    program_id: Mapped[UUID] = mapped_column(ForeignKey("ref_program.id"), index=True)
    referrer_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"), index=True)

    referee_email: Mapped[Optional[str]] = mapped_column(String(255))
    referee_phone: Mapped[Optional[str]] = mapped_column(String(20))
    referee_user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_user.id"))

    referral_code: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[ReferralStatus] = mapped_column(SAEnum(ReferralStatus, name="referral_status"))

    booking_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("txn_booking.id"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    referrer_reward_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    referee_reward_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    referrer_reward_status: Mapped[RewardStatus] = mapped_column(SAEnum(RewardStatus, name="reward_status"))
    referee_reward_status: Mapped[RewardStatus] = mapped_column(SAEnum(RewardStatus, name="reward_status_ref"))