# app.models/analytics/performance_metrics.py
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class SupervisorPerformanceMetrics(BaseItem):
    """
    High-level performance metrics per supervisor (for analytics).
    """
    __tablename__ = "analytics_supervisor_performance"

    supervisor_id: Mapped[UUID] = mapped_column(index=True)
    hostel_id: Mapped[UUID] = mapped_column(index=True)

    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    # Workload/performance (simplified subset)
    complaints_assigned: Mapped[int] = mapped_column(Integer, default=0)
    complaints_resolved: Mapped[int] = mapped_column(Integer, default=0)

    maintenance_requests_created: Mapped[int] = mapped_column(Integer, default=0)
    maintenance_requests_completed: Mapped[int] = mapped_column(Integer, default=0)

    attendance_records_marked: Mapped[int] = mapped_column(Integer, default=0)

    avg_complaint_resolution_time_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    avg_maintenance_completion_time_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    overall_performance_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)