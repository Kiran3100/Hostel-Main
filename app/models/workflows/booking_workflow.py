# app.models/workflows/booking_workflow.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class BookingWorkflow(BaseItem):
    """Booking approval & lifecycle states."""
    __tablename__ = "wf_booking"

    booking_id: Mapped[UUID] = mapped_column(ForeignKey("txn_booking.id"), unique=True)

    current_status: Mapped[str] = mapped_column(String(50))  # pending, approved, rejected, checked_in, checked_out
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # optionally store JSON state history externally