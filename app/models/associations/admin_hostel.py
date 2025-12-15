# app.models/associations/admin_hostel.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.schemas.common.enums import PermissionLevel
from app.models.base import BaseEntity


class AdminHostel(BaseEntity):
    """Admin-to-hostel assignments (with permission level)."""
    __tablename__ = "assoc_admin_hostel"

    admin_id: Mapped[UUID] = mapped_column(ForeignKey("core_admin.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)

    permission_level: Mapped[PermissionLevel] = mapped_column(
        SAEnum(PermissionLevel, name="admin_permission_level")
    )
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    assigned_date: Mapped[date] = mapped_column(Date, default=date.today)
    revoked_date: Mapped[Optional[date]] = mapped_column(Date)
    revoke_reason: Mapped[Optional[str]] = mapped_column()
    last_active: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))