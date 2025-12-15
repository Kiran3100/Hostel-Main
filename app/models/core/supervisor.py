# models/core/supervisor.py
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import SupervisorStatus, EmploymentType
from app.models.base import BaseEntity


class Supervisor(BaseEntity):
    """Supervisor model with permissions and employment details."""
    __tablename__ = "core_supervisor"

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

    employee_id: Mapped[Optional[str]] = mapped_column(String(100))
    join_date: Mapped[date] = mapped_column(Date)
    employment_type: Mapped[EmploymentType] = mapped_column(SAEnum(EmploymentType, name="employment_type"))
    shift_timing: Mapped[Optional[str]] = mapped_column(String(100))

    status: Mapped[SupervisorStatus] = mapped_column(SAEnum(SupervisorStatus, name="supervisor_status"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    permissions: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship(back_populates="supervisor_profile")
    hostel: Mapped["Hostel"] = relationship(back_populates="supervisors")