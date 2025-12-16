# models/base.py
from datetime import datetime
from uuid import UUID, uuid4
from typing import Union

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .mixins.timestamp_mixin import TimestampMixin
from .mixins.soft_delete_mixin import SoftDeleteMixin
from .mixins.audit_mixin import AuditMixin
from .mixins.backend_sync_mixin import BackendSyncMixin
from .mixins.validation_mixin import ValidationMixin


class Base(DeclarativeBase):
    """Root SQLAlchemy base class."""
    pass


class BaseEntity(
    Base,
    TimestampMixin,
    SoftDeleteMixin,
    AuditMixin,
    ValidationMixin,
):
    """
    Base for most internal entities.

    - UUID primary key
    - 'type' discriminator (optional usage)
    - created_at / updated_at
    - soft delete
    - audit fields
    """
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        unique=True,
    )
    type: Mapped[str] = mapped_column(String(50), default=lambda: "entity")

    # TimestampMixin & others supply remaining columns


class BaseItem(
    BaseEntity,
    BackendSyncMixin,
):
    """
    Base for items that have a backing record in an external system.

    Adds:
    - backend_id: str (for sync)
    """
    __abstract__ = True


class BaseVisitorItem(
    Base,
    TimestampMixin,
    ValidationMixin,
):
    """
    Base for visitor-facing models (public side, not tied to internal audit/soft delete).
    """
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        unique=True,
    )
    type: Mapped[str] = mapped_column(String(50), default=lambda: "visitor_item")

    def to_dict(self) -> dict:
        return {c.key: getattr(self, c.key) for c in self.__table__.columns}