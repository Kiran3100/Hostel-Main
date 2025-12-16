# app.models/services/leave_application.py
from datetime import date
from typing import Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import LeaveType, LeaveStatus
from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.core.student import Student


class LeaveApplication(BaseEntity):
    """Student leave requests."""
    __tablename__ = "svc_leave_application"

    student_id: Mapped[UUID] = mapped_column(ForeignKey("core_student.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)

    leave_type: Mapped[LeaveType] = mapped_column(SAEnum(LeaveType, name="leave_type"))
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    total_days: Mapped[int] = mapped_column(Integer)

    reason: Mapped[str] = mapped_column(String(1000))

    contact_during_leave: Mapped[Union[str, None]] = mapped_column(String(20))
    emergency_contact: Mapped[Union[str, None]] = mapped_column(String(20))

    supporting_document_url: Mapped[Union[str, None]] = mapped_column(String(500))

    status: Mapped[LeaveStatus] = mapped_column(SAEnum(LeaveStatus, name="leave_status"))

    approved_by_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_supervisor.id"))
    rejected_by_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_supervisor.id"))

    rejection_reason: Mapped[Union[str, None]] = mapped_column(String(500))
    cancellation_reason: Mapped[Union[str, None]] = mapped_column(String(500))

    # Relationships
    student: Mapped["Student"] = relationship()