# app.models/workflows/maintenance_workflow.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class MaintenanceWorkflow(BaseItem):
    """Maintenance approval & execution workflow."""
    __tablename__ = "wf_maintenance"

    maintenance_id: Mapped[UUID] = mapped_column(ForeignKey("svc_maintenance.id"), unique=True)

    current_status: Mapped[str] = mapped_column(String(50))  # pending_approval, approved, in_progress, completed
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)