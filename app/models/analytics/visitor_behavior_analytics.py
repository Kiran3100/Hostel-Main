# app.models/analytics/visitor_behavior_analytics.py
# (Move the previously defined VisitorBehaviorAnalytics here)
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class VisitorBehaviorAnalytics(BaseItem):
    """See previous definition; placed under analytics package."""
    __tablename__ = "analytics_visitor_behavior"

    visitor_id: Mapped[UUID] = mapped_column(index=True)

    total_sessions: Mapped[int] = mapped_column(Integer, default=0)
    total_page_views: Mapped[int] = mapped_column(Integer, default=0)
    avg_session_duration: Mapped[Optional[float]] = mapped_column(Float)
    bounce_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    total_searches: Mapped[int] = mapped_column(Integer, default=0)
    most_searched_locations: Mapped[List[str]] = mapped_column(JSON, default=list)
    preferred_price_range: Mapped[Optional[str]] = mapped_column()
    preferred_amenities: Mapped[List[str]] = mapped_column(JSON, default=list)

    hostels_viewed: Mapped[int] = mapped_column(Integer, default=0)
    favorites_added: Mapped[int] = mapped_column(Integer, default=0)
    comparisons_made: Mapped[int] = mapped_column(Integer, default=0)
    inquiries_sent: Mapped[int] = mapped_column(Integer, default=0)
    bookings_made: Mapped[int] = mapped_column(Integer, default=0)
    reviews_written: Mapped[int] = mapped_column(Integer, default=0)

    inquiry_to_booking_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    total_booking_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))

    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_search: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_booking: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))