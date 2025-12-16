# app.models/workflows/complaint_workflow.py
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class ComplaintWorkflow(BaseItem):
    """Complaint resolution workflow state."""
    __tablename__ = "wf_complaint"

    complaint_id: Mapped[UUID] = mapped_column(ForeignKey("svc_complaint.id"), unique=True)

    current_status: Mapped[str] = mapped_column(String(50))  # open, in_progress, resolved, closed, escalated
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)