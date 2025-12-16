# app.models/visitor/hostel_booking.py
from datetime import date, datetime
from decimal import Decimal
from typing import Union
from uuid import UUID

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseVisitorItem


class HostelBooking(BaseVisitorItem):
    """Visitor booking for a hostel."""
    __tablename__ = "visitor_hostel_booking"

    visitor_id: Mapped[UUID] = mapped_column(index=True)
    hostel_id: Mapped[UUID] = mapped_column(index=True)

    check_in_date: Mapped[date] = mapped_column(Date)
    check_out_date: Mapped[date] = mapped_column(Date)
    duration: Mapped[str] = mapped_column(String(50))

    room_type: Mapped[str] = mapped_column(String(50))
    number_of_beds: Mapped[int] = mapped_column(Integer)

    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    security_deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    booking_status: Mapped[str] = mapped_column(String(50), index=True)

    confirmed_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    checked_in_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    checked_out_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[Union[str, None]] = mapped_column(String(500))

    special_requests: Mapped[Union[str, None]] = mapped_column(String(1000))
    guest_count: Mapped[int] = mapped_column(Integer, default=1)