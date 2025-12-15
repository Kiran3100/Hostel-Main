# app.models/transactions/booking.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import BookingStatus, RoomType, BookingSource
from app.models.base import BaseEntity


class Booking(BaseEntity):
    """
    Internal booking requests (from visitor or admin).
    """
    __tablename__ = "txn_booking"

    visitor_id: Mapped[UUID] = mapped_column(ForeignKey("visitor.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)

    room_type_requested: Mapped[RoomType] = mapped_column(SAEnum(RoomType, name="room_type"))
    preferred_check_in_date: Mapped[date] = mapped_column(Date)
    stay_duration_months: Mapped[int] = mapped_column(Integer)

    quoted_rent_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    security_deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    advance_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    booking_status: Mapped[BookingStatus] = mapped_column(SAEnum(BookingStatus, name="booking_status"))

    source: Mapped[BookingSource] = mapped_column(SAEnum(BookingSource, name="booking_source"))
    referral_code: Mapped[Optional[str]] = mapped_column(String(50))

    booking_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Guest summary
    guest_name: Mapped[str] = mapped_column(String(255))
    guest_email: Mapped[str] = mapped_column(String(255))
    guest_phone: Mapped[str] = mapped_column(String(20))

    # Assignment (optional)
    room_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_room.id"))
    bed_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_bed.id"))

    # Relationships
    payments: Mapped[List["Payment"]] = relationship(back_populates="booking")