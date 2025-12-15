# app.models/analytics/dashboard_metrics.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, Numeric, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class DashboardMetrics(BaseItem):
    """
    Aggregated dashboard metrics (hostel/platform/admin scope).
    Mirrors DashboardMetrics schema.
    """
    __tablename__ = "analytics_dashboard_metrics"

    scope_type: Mapped[str] = mapped_column(
        String(20)
    )  # hostel | platform | admin
    scope_id: Mapped[UUID | None] = mapped_column(nullable=True)

    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Quick stats (simplified)
    total_hostels: Mapped[int] = mapped_column(Integer, default=0)
    active_hostels: Mapped[int] = mapped_column(Integer, default=0)
    total_students: Mapped[int] = mapped_column(Integer, default=0)
    active_students: Mapped[int] = mapped_column(Integer, default=0)
    total_visitors: Mapped[int] = mapped_column(Integer, default=0)

    todays_check_ins: Mapped[int] = mapped_column(Integer, default=0)
    todays_check_outs: Mapped[int] = mapped_column(Integer, default=0)

    open_complaints: Mapped[int] = mapped_column(Integer, default=0)
    pending_maintenance: Mapped[int] = mapped_column(Integer, default=0)

    todays_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    monthly_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    outstanding_payments: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)