# app.models/services/attendance.py
from __future__ import annotations

from datetime import date, time
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, String, Time, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import AttendanceStatus, AttendanceMode
from app.models.base import BaseEntity


class Attendance(BaseEntity):
    """Attendance tracking."""
    __tablename__ = "svc_attendance"

    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("core_student.id"), index=True)

    attendance_date: Mapped[date] = mapped_column(Date, index=True)

    check_in_time: Mapped[Optional[time]] = mapped_column(Time)
    check_out_time: Mapped[Optional[time]] = mapped_column(Time)

    status: Mapped[AttendanceStatus] = mapped_column(SAEnum(AttendanceStatus, name="attendance_status"))

    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    late_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    attendance_mode: Mapped[AttendanceMode] = mapped_column(SAEnum(AttendanceMode, name="attendance_mode"))

    marked_by_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"))
    supervisor_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_supervisor.id"), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships (light)
    student: Mapped["Student"] = relationship()