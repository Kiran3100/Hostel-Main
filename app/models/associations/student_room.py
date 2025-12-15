# app.models/associations/student_room.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseEntity


class StudentRoomAssignment(BaseEntity):
    """Student-to-room assignment history."""
    __tablename__ = "assoc_student_room"

    student_id: Mapped[UUID] = mapped_column(ForeignKey("core_student.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    room_id: Mapped[UUID] = mapped_column(ForeignKey("core_room.id"), index=True)
    bed_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_bed.id"))

    move_in_date: Mapped[date] = mapped_column(Date)
    move_out_date: Mapped[Optional[date]] = mapped_column(Date)

    rent_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    reason: Mapped[Optional[str]] = mapped_column(String(500))