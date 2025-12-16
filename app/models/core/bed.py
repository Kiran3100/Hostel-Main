# models/core/bed.py
from datetime import date
from typing import Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import BedStatus
from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.core.hostel import Hostel
    from app.models.core.room import Room
    from app.models.core.student import Student


class Bed(BaseEntity):
    """Individual bed tracking."""
    __tablename__ = "core_bed"

    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_hostel.id", ondelete="CASCADE"),
        nullable=False,
    )
    room_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_room.id", ondelete="CASCADE"),
        nullable=False,
    )

    bed_number: Mapped[str] = mapped_column(String(10))
    status: Mapped[BedStatus] = mapped_column(SAEnum(BedStatus, name="bed_status"))

    occupied_from: Mapped[Union[date, None]] = mapped_column(Date)
    current_student_id: Mapped[Union[UUID, None]] = mapped_column(
        ForeignKey("core_student.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(back_populates="beds")
    room: Mapped["Room"] = relationship(back_populates="beds")
    current_student: Mapped[Union["Student", None]] = relationship(back_populates="current_bed", uselist=False)