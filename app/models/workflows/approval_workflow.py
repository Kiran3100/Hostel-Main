# app.models/workflows/approval_workflow.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class ApprovalWorkflow(BaseItem):
    """
    Generic approval workflow for entities that need admin/supervisor approval
    (announcements, menus, large maintenance, etc.).
    """
    __tablename__ = "wf_approval"

    entity_type: Mapped[str] = mapped_column(String(50))  # complaint, maintenance, announcement, menu, etc.
    entity_id: Mapped[UUID] = mapped_column()

    status: Mapped[str] = mapped_column(String(50))  # pending, approved, rejected
    requested_by_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"))
    approver_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_user.id"))

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    reason: Mapped[Optional[str]] = mapped_column()
    decision_notes: Mapped[Optional[str]] = mapped_column()