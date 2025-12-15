# models/audit/audit_log.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import DateTime, Enum as SAEnum, JSON, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.schemas.common.enums import AuditActionCategory, UserRole
from app.models.base import BaseItem


class AuditLog(BaseItem):
    """General audit trail for actions."""
    __tablename__ = "audit_log"

    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_user.id"))
    user_role: Mapped[Optional[UserRole]] = mapped_column(SAEnum(UserRole, name="audit_user_role"))

    action_type: Mapped[str] = mapped_column(String(100))
    action_category: Mapped[AuditActionCategory] = mapped_column(
        SAEnum(AuditActionCategory, name="audit_category")
    )

    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[UUID]] = mapped_column()

    hostel_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_hostel.id"))

    description: Mapped[str] = mapped_column(String(2000))

    old_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    new_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    request_id: Mapped[Optional[str]] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)