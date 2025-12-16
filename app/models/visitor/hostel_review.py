# app.models/visitor/hostel_review.py
from datetime import datetime
from decimal import Decimal
from typing import List, Union
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseVisitorItem


class HostelReview(BaseVisitorItem):
    """Visitor review of a hostel (public side)."""
    __tablename__ = "visitor_hostel_review"

    visitor_id: Mapped[UUID] = mapped_column(index=True)
    hostel_id: Mapped[UUID] = mapped_column(index=True)
    booking_id: Mapped[Union[UUID, None]] = mapped_column(index=True)

    overall_rating: Mapped[float] = mapped_column(Float)
    cleanliness_rating: Mapped[Union[float, None]] = mapped_column(Float)
    food_rating: Mapped[Union[float, None]] = mapped_column(Float)
    staff_rating: Mapped[Union[float, None]] = mapped_column(Float)
    location_rating: Mapped[Union[float, None]] = mapped_column(Float)

    review_title: Mapped[str] = mapped_column(String(255))
    review_text: Mapped[str] = mapped_column(String(5000))

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)

    photos: Mapped[List[str]] = mapped_column(JSON, default=list)
    hostel_response: Mapped[Union[str, None]] = mapped_column(String(5000))
    response_date: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))