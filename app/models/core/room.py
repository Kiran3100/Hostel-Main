# models/core/room.py
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Integer, Numeric, JSON, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import RoomType, RoomStatus
from app.models.base import BaseEntity


class Room(BaseEntity):
    """Room model with pricing tiers."""
    __tablename__ = "core_room"

    hostel_id: Mapped[UUID] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    room_number: Mapped[str] = mapped_column(String(50), index=True)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer)
    wing: Mapped[Optional[str]] = mapped_column(String(50))

    room_type: Mapped[RoomType] = mapped_column(SAEnum(RoomType, name="room_type"))
    total_beds: Mapped[int] = mapped_column(Integer, default=1)

    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_quarterly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    price_half_yearly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    price_yearly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    room_size_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    is_ac: Mapped[bool] = mapped_column(Boolean, default=False)
    has_attached_bathroom: Mapped[bool] = mapped_column(Boolean, default=False)
    has_balcony: Mapped[bool] = mapped_column(Boolean, default=False)
    has_wifi: Mapped[bool] = mapped_column(Boolean, default=True)

    amenities: Mapped[List[str]] = mapped_column(JSON, default=list)
    furnishing: Mapped[List[str]] = mapped_column(JSON, default=list)

    is_available_for_booking: Mapped[bool] = mapped_column(Boolean, default=True)
    is_under_maintenance: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[RoomStatus] = mapped_column(SAEnum(RoomStatus, name="room_status"))

    room_images: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Relationships
    hostel: Mapped["Hostel"] = relationship(back_populates="rooms")
    beds: Mapped[List["Bed"]] = relationship(back_populates="room", cascade="all, delete-orphan")