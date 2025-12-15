# app.models/visitor/visitor.py
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.schemas.common.enums import RoomType
from app.models.base import BaseVisitorItem


class Visitor(BaseVisitorItem):
    """Visitor profile for public platform."""
    __tablename__ = "visitor"

    user_id: Mapped[UUID] = mapped_column(unique=True, index=True)

    preferred_room_type: Mapped[Optional[RoomType]] = mapped_column(
        nullable=True
    )
    budget_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    budget_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    preferred_cities: Mapped[List[str]] = mapped_column(JSON, default=list)
    preferred_amenities: Mapped[List[str]] = mapped_column(JSON, default=list)

    favorite_hostel_ids: Mapped[List[UUID]] = mapped_column(JSON, default=list)

    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    push_notifications: Mapped[bool] = mapped_column(Boolean, default=True)