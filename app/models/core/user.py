# models/core/user.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import UserRole, Gender
from app.models.base import BaseEntity


class User(BaseEntity):
    """
    Unified User model (admin, supervisor, student, visitor, etc.).
    """
    __tablename__ = "core_user"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    user_role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"))
    gender: Mapped[Optional[Gender]] = mapped_column(SAEnum(Gender, name="gender"), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    student_profile: Mapped["Student"] = relationship(back_populates="user", uselist=False)
    supervisor_profile: Mapped["Supervisor"] = relationship(back_populates="user", uselist=False)
    admin_profile: Mapped["Admin"] = relationship(back_populates="user", uselist=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.user_role.value}>"