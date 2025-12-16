# models/core/admin.py
from datetime import datetime
from typing import Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseItem

if TYPE_CHECKING:
    from app.models.core.user import User


class Admin(BaseItem):
    """
    Admin model (management users).
    Stored separately to support multi-hostel administration,
    advanced permissions, etc.
    """
    __tablename__ = "core_admin"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_user.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(String(50), default="hostel_admin")
    status: Mapped[str] = mapped_column(String(50), default="active")

    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    last_login: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="admin_profile")