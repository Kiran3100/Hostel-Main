# models/core/student.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import StudentStatus, IDProofType, DietaryPreference
from app.models.base import BaseEntity


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
    room_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_room.id", ondelete="SET NULL"))
    bed_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_bed.id", ondelete="SET NULL"))

    # Identification
    id_proof_type: Mapped[Optional[IDProofType]] = mapped_column(SAEnum(IDProofType, name="id_proof_type"))
    id_proof_number: Mapped[Optional[str]] = mapped_column(String(50))

    # Guardian
    guardian_name: Mapped[str] = mapped_column(String(255))
    guardian_phone: Mapped[str] = mapped_column(String(20))
    guardian_email: Mapped[Optional[str]] = mapped_column(String(255))
    guardian_relation: Mapped[Optional[str]] = mapped_column(String(50))
    guardian_address: Mapped[Optional[str]] = mapped_column(String(500))

    # Academic / employment (simplified)
    institution_name: Mapped[Optional[str]] = mapped_column(String(255))
    course: Mapped[Optional[str]] = mapped_column(String(255))
    year_of_study: Mapped[Optional[str]] = mapped_column(String(50))

    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    designation: Mapped[Optional[str]] = mapped_column(String(255))

    # Dates / financial
    check_in_date: Mapped[Optional[date]] = mapped_column(Date)
    expected_checkout_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_checkout_date: Mapped[Optional[date]] = mapped_column(Date)

    security_deposit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    monthly_rent_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Mess
    mess_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    dietary_preference: Mapped[Optional[DietaryPreference]] = mapped_column(
        SAEnum(DietaryPreference, name="dietary_preference"),
        nullable=True,
    )
    food_allergies: Mapped[Optional[str]] = mapped_column(String(500))

    # Status
    student_status: Mapped[StudentStatus] = mapped_column(SAEnum(StudentStatus, name="student_status"))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="student_profile")
    hostel: Mapped["Hostel"] = relationship(back_populates="students")
    room: Mapped[Optional["Room"]] = relationship()
    current_bed: Mapped[Optional["Bed"]] = relationship(back_populates="current_student", uselist=False)