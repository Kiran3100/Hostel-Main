# app.models/associations/supervisor_hostel.py
from datetime import date
from typing import Union
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseEntity


class SupervisorHostel(BaseEntity):
    """Supervisor-to-hostel assignment (multi-hostel support)."""
    __tablename__ = "assoc_supervisor_hostel"

    supervisor_id: Mapped[UUID] = mapped_column(ForeignKey("core_supervisor.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)

    employee_id: Mapped[Union[str, None]] = mapped_column(String(100))
    join_date: Mapped[date] = mapped_column(Date)
    employment_type: Mapped[str] = mapped_column(String(50))  # full_time, part_time, contract

    shift_timing: Mapped[Union[str, None]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    permissions: Mapped[dict] = mapped_column(JSON, default=dict)