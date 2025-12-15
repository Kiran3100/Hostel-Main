# app.models/content/review.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseEntity


class Review(BaseEntity):
    """
    Internal review system (students/users reviewing hostels).
    This complements the public HostelReview on visitor side.
    """
    __tablename__ = "content_review"

    hostel_id: Mapped[UUID] = mapped_column(index=True)
    reviewer_id: Mapped[UUID] = mapped_column(index=True)
    student_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    booking_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)

    overall_rating: Mapped[Decimal] = mapped_column(Numeric(3, 1))

    title: Mapped[str] = mapped_column(String(255))
    review_text: Mapped[str] = mapped_column(String(5000))

    cleanliness_rating: Mapped[Optional[int]] = mapped_column()
    food_quality_rating: Mapped[Optional[int]] = mapped_column()
    staff_behavior_rating: Mapped[Optional[int]] = mapped_column()
    security_rating: Mapped[Optional[int]] = mapped_column()
    value_for_money_rating: Mapped[Optional[int]] = mapped_column()
    amenities_rating: Mapped[Optional[int]] = mapped_column()

    photos: Mapped[List[str]] = mapped_column(JSON, default=list)

    is_verified_stay: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)

    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    not_helpful_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at_override: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)