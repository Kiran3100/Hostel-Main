# app.models/services/inquiry.py
from __future__ import annotations

from datetime import datetime, date
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import InquiryStatus, RoomType
from app.models.base import BaseEntity


class Inquiry(BaseEntity):
    """Visitor inquiries about hostels."""
    __tablename__ = "svc_inquiry"

    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)

    visitor_name: Mapped[str] = mapped_column(String(255))
    visitor_email: Mapped[str] = mapped_column(String(255))
    visitor_phone: Mapped[str] = mapped_column(String(20))

    preferred_check_in_date: Mapped[Optional[date]] = mapped_column(Date)
    stay_duration_months: Mapped[Optional[int]]
    room_type_preference: Mapped[Optional[RoomType]] = mapped_column(
        SAEnum(RoomType, name="inquiry_room_type"),
        nullable=True,
    )

    message: Mapped[Optional[str]] = mapped_column(String(2000))

    inquiry_source: Mapped[str] = mapped_column(String(50))
    status: Mapped[InquiryStatus] = mapped_column(SAEnum(InquiryStatus, name="inquiry_status"))

    contacted_by_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_admin.id"))
    contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    notes: Mapped[Optional[str]] = mapped_column(String(1000))

    hostel: Mapped["Hostel"] = relationship()