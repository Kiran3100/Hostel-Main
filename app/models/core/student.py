# models/core/student.py
from datetime import date
from decimal import Decimal
from typing import Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import StudentStatus, IDProofType, DietaryPreference
from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.core.user import User
    from app.models.core.hostel import Hostel
    from app.models.core.room import Room
    from app.models.core.bed import Bed


class Student(BaseEntity):
    """Student profile linked to User and Hostel."""
    __tablename__ = "core_student"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_user.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_hostel.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_room.id", ondelete="SET NULL"))
    bed_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_bed.id", ondelete="SET NULL"))

    # Identification
    id_proof_type: Mapped[Union[IDProofType, None]] = mapped_column(SAEnum(IDProofType, name="id_proof_type"))
    id_proof_number: Mapped[Union[str, None]] = mapped_column(String(50))

    # Guardian
    guardian_name: Mapped[str] = mapped_column(String(255))
    guardian_phone: Mapped[str] = mapped_column(String(20))
    guardian_email: Mapped[Union[str, None]] = mapped_column(String(255))
    guardian_relation: Mapped[Union[str, None]] = mapped_column(String(50))
    guardian_address: Mapped[Union[str, None]] = mapped_column(String(500))

    # Academic / employment (simplified)
    institution_name: Mapped[Union[str, None]] = mapped_column(String(255))
    course: Mapped[Union[str, None]] = mapped_column(String(255))
    year_of_study: Mapped[Union[str, None]] = mapped_column(String(50))

    company_name: Mapped[Union[str, None]] = mapped_column(String(255))
    designation: Mapped[Union[str, None]] = mapped_column(String(255))

    # Dates / financial
    check_in_date: Mapped[Union[date, None]] = mapped_column(Date)
    expected_checkout_date: Mapped[Union[date, None]] = mapped_column(Date)
    actual_checkout_date: Mapped[Union[date, None]] = mapped_column(Date)

    security_deposit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    monthly_rent_amount: Mapped[Union[Decimal, None]] = mapped_column(Numeric(10, 2))

    # Mess
    mess_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    dietary_preference: Mapped[Union[DietaryPreference, None]] = mapped_column(
        SAEnum(DietaryPreference, name="dietary_preference"),
        nullable=True,
    )
    food_allergies: Mapped[Union[str, None]] = mapped_column(String(500))

    # Status
    student_status: Mapped[StudentStatus] = mapped_column(SAEnum(StudentStatus, name="student_status"))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="student_profile")
    hostel: Mapped["Hostel"] = relationship(back_populates="students")
    room: Mapped[Union["Room", None]] = relationship()
    current_bed: Mapped[Union["Bed", None]] = relationship(back_populates="current_student", uselist=False)