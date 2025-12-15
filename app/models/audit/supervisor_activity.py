# models/audit/supervisor_activity.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy import DateTime, JSON, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class SupervisorActivity(BaseItem):
    """Supervisor action logs."""
    __tablename__ = "audit_supervisor_activity"

    supervisor_id: Mapped[UUID] = mapped_column(ForeignKey("core_supervisor.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)

    action_type: Mapped[str] = mapped_column(String(100))
    action_category: Mapped[str] = mapped_column(String(50))  # complaint, attendance, maintenance, etc.

    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[UUID]] = mapped_column()

    action_description: Mapped[str] = mapped_column(String(2000))
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)