# models/audit/admin_override.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy import DateTime, JSON, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class AdminOverride(BaseItem):
    """Admin override records (supervisor decisions)."""
    __tablename__ = "audit_admin_override"

    admin_id: Mapped[UUID] = mapped_column(ForeignKey("core_admin.id"))
    supervisor_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_supervisor.id"))
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"))

    override_type: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[UUID] = mapped_column()

    reason: Mapped[str] = mapped_column(String(2000))

    original_action: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    override_action: Mapped[Dict[str, Any]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)