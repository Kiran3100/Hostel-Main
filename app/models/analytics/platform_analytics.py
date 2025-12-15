# app.models/analytics/platform_analytics.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class PlatformMetrics(BaseItem):
    """Platform-wide metrics (tenants, users, load)."""
    __tablename__ = "analytics_platform_metrics"

    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    total_hostels: Mapped[int] = mapped_column(Integer, default=0)
    active_hostels: Mapped[int] = mapped_column(Integer, default=0)
    hostels_on_trial: Mapped[int] = mapped_column(Integer, default=0)

    total_users: Mapped[int] = mapped_column(Integer, default=0)
    total_students: Mapped[int] = mapped_column(Integer, default=0)
    total_supervisors: Mapped[int] = mapped_column(Integer, default=0)
    total_admins: Mapped[int] = mapped_column(Integer, default=0)
    total_visitors: Mapped[int] = mapped_column(Integer, default=0)

    avg_daily_active_users: Mapped[int] = mapped_column(Integer, default=0)
    peak_concurrent_sessions: Mapped[int] = mapped_column(Integer, default=0)


class GrowthMetrics(BaseItem):
    """Growth over time for hostels, revenue, users."""
    __tablename__ = "analytics_growth_metrics"

    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    new_hostels: Mapped[int] = mapped_column(Integer, default=0)
    churned_hostels: Mapped[int] = mapped_column(Integer, default=0)
    net_hostel_growth: Mapped[int] = mapped_column(Integer, default=0)

    total_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    revenue_growth_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)

    new_users: Mapped[int] = mapped_column(Integer, default=0)
    user_growth_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)


class PlatformUsageAnalytics(BaseItem):
    """API / platform usage metrics."""
    __tablename__ = "analytics_platform_usage"

    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    avg_requests_per_minute: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    api_error_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)

    avg_response_time_ms: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    p95_response_time_ms: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    p99_response_time_ms: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)