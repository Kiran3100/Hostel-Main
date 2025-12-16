# app.models/services/complaint.py
from datetime import datetime
from typing import Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import ComplaintCategory, ComplaintStatus, Priority
from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.core.hostel import Hostel
    from app.models.core.user import User
    from app.models.core.supervisor import Supervisor


class Complaint(BaseEntity):
    """Complaint tracking & resolution."""
    __tablename__ = "svc_complaint"

    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    raised_by_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"), index=True)
    student_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_student.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000))

    category: Mapped[ComplaintCategory] = mapped_column(SAEnum(ComplaintCategory, name="complaint_category"))
    sub_category: Mapped[Union[str, None]] = mapped_column(String(100))
    priority: Mapped[Priority] = mapped_column(SAEnum(Priority, name="priority"))

    room_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_room.id"), nullable=True)
    location_details: Mapped[Union[str, None]] = mapped_column(String(500))

    attachments: Mapped[list[str]] = mapped_column(JSON, default=list)

    status: Mapped[ComplaintStatus] = mapped_column(SAEnum(ComplaintStatus, name="complaint_status"))
    assigned_to_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_supervisor.id"), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    in_progress_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))

    sla_breach: Mapped[bool] = mapped_column(default=False)
    sla_breach_reason: Mapped[Union[str, None]] = mapped_column(String(500))

    # Relationships (light)
    hostel: Mapped["Hostel"] = relationship()
    raised_by: Mapped["User"] = relationship()
    assigned_to: Mapped[Union["Supervisor", None]] = relationship()