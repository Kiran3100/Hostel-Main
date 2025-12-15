# app.models/visitor/visitor_hostel.py
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Float, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseVisitorItem


class VisitorHostel(BaseVisitorItem):
    """
    Public-facing hostel representation used by search/visitor side.
    Often denormalized from core_hostel.
    """
    __tablename__ = "visitor_hostel"

    hostel_id: Mapped[UUID] = mapped_column(index=True)

    hostel_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(2000))
    location: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    area: Mapped[Optional[str]] = mapped_column(String(100))
    pincode: Mapped[str] = mapped_column(String(6))

    price_range: Mapped[str] = mapped_column(String(50))
    min_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    max_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    room_types: Mapped[List[str]] = mapped_column(JSON, default=list)
    gender_type: Mapped[str] = mapped_column(String(20))

    availability: Mapped[int] = mapped_column(Integer)
    total_capacity: Mapped[int] = mapped_column(Integer)

    rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)

    amenities: Mapped[List[str]] = mapped_column(JSON, default=list)
    photos: Mapped[List[str]] = mapped_column(JSON, default=list)

    contact_number: Mapped[str] = mapped_column(String(20))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))

    nearby_landmarks: Mapped[Optional[str]] = mapped_column(String(1000))
    availability_status: Mapped[str] = mapped_column(String(50))