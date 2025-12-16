# models/audit/user_activity.py
from datetime import datetime
from typing import Union
from uuid import UUID

from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class UserActivity(BaseItem):
    """Simplified user activity tracking (logins, important actions)."""
    __tablename__ = "audit_user_activity"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"), index=True)
    activity_type: Mapped[str] = mapped_column(String(100))  # login, logout, booking_created, etc.
    description: Mapped[Union[str, None]] = mapped_column(String(1000))

    ip_address: Mapped[Union[str, None]] = mapped_column(String(50))
    user_agent: Mapped[Union[str, None]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)