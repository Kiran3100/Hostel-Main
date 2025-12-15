# app.models/analytics/analytics_data.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Numeric, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class AnalyticsData(BaseItem):
    """
    High-level platform analytics (visitors, conversion, retention).
    """
    __tablename__ = "analytics_data"

    # Scope (platform-wide)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    total_visitors: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    avg_session_time_seconds: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total_bookings: Mapped[int] = mapped_column(Integer, default=0)
    avg_booking_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cancellation_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    retention_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    avg_stay_duration_days: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    repeat_bookings_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)