# app.models/services/maintenance.py
from datetime import date, datetime
from decimal import Decimal
from typing import Union
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, JSON, Numeric, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import (
    MaintenanceCategory,
    MaintenanceStatus,
    MaintenanceIssueType,
    Priority,
)
from app.models.base import BaseEntity


class Maintenance(BaseEntity):
    """Maintenance requests & work orders."""
    __tablename__ = "svc_maintenance"

    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    requested_by_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"))
    room_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_room.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000))

    category: Mapped[MaintenanceCategory] = mapped_column(SAEnum(MaintenanceCategory, name="maintenance_category"))
    priority: Mapped[Priority] = mapped_column(SAEnum(Priority, name="maintenance_priority"))
    issue_type: Mapped[MaintenanceIssueType] = mapped_column(
        SAEnum(MaintenanceIssueType, name="maintenance_issue_type")
    )

    location: Mapped[Union[str, None]] = mapped_column(String(500))
    floor: Mapped[Union[int, None]] = mapped_column()
    specific_area: Mapped[Union[str, None]] = mapped_column(String(255))

    issue_photos: Mapped[list[str]] = mapped_column(JSON, default=list)

    status: Mapped[MaintenanceStatus] = mapped_column(SAEnum(MaintenanceStatus, name="maintenance_status"))
    assigned_to_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_supervisor.id"), nullable=True)

    estimated_cost: Mapped[Union[Decimal, None]] = mapped_column(Numeric(10, 2))
    actual_cost: Mapped[Union[Decimal, None]] = mapped_column(Numeric(10, 2))

    estimated_completion_date: Mapped[Union[date, None]] = mapped_column(Date)
    actual_completion_date: Mapped[Union[date, None]] = mapped_column(Date)

    cost_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_threshold_exceeded: Mapped[bool] = mapped_column(Boolean, default=False)

    started_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))