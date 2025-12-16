# models/mixins/audit_mixin.py
from typing import Union
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """Basic audit trail fields (creator / updater)."""
    created_by_id: Mapped[Union[UUID, None]] = mapped_column(
        ForeignKey("core_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[Union[UUID, None]] = mapped_column(
        ForeignKey("core_user.id", ondelete="SET NULL"),
        nullable=True,
    )