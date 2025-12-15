# models/mixins/audit_mixin.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """Basic audit trail fields (creator / updater)."""
    created_by_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("core_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("core_user.id", ondelete="SET NULL"),
        nullable=True,
    )