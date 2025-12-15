# app/services/analytics/dashboard_analytics_service.py
from __future__ import annotations

from datetime import datetime
from typing import Callable, List, Optional, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.analytics import DashboardMetricsRepository
from app.schemas.analytics.dashboard_analytics import (
    DashboardMetrics as DashboardMetricsSchema,
    QuickStats,
    KPIResponse,
    TimeseriesPoint,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork


class DashboardAnalyticsService:
    """
    DashboardMetrics service backed by analytics_dashboard_metrics table.

    - Fetch dashboard metrics for a scope (hostel|platform|admin)
    - If no exact period match, fall back to latest snapshot for scope
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> DashboardMetricsRepository:
        return uow.get_repo(DashboardMetricsRepository)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_dashboard_metrics(
        self,
        *,
        scope_type: str,
        scope_id: Optional[UUID],
        period: Optional[DateRangeFilter] = None,
    ) -> Optional[DashboardMetricsSchema]:
        """
        Fetch DashboardMetrics for given scope+period, or latest if period not supplied.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            rec = None
            if period and period.start_date and period.end_date:
                rec = repo.get_for_scope_and_period(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    period_start=period.start_date,
                    period_end=period.end_date,
                )
            if rec is None:
                rec = repo.get_latest_for_scope(scope_type=scope_type, scope_id=scope_id)
            if rec is None:
                return None

        # Map DB row -> QuickStats
        quick = QuickStats(
            total_hostels=rec.total_hostels,
            active_hostels=rec.active_hostels,
            total_students=rec.total_students,
            active_students=rec.active_students,
            total_visitors=rec.total_visitors,
            todays_check_ins=rec.todays_check_ins,
            todays_check_outs=rec.todays_check_outs,
            open_complaints=rec.open_complaints,
            pending_maintenance=rec.pending_maintenance,
            todays_revenue=rec.todays_revenue,
            monthly_revenue=rec.monthly_revenue,
            outstanding_payments=rec.outstanding_payments,
        )

        # Simple example KPIs: you can extend this with more meaningful KPIs
        kpis: List[KPIResponse] = [
            KPIResponse(
                name="Monthly Revenue",
                value=rec.monthly_revenue,
                unit="INR",
                trend_direction=None,
                trend_percentage=None,
                target_value=None,
                good_when="higher_is_better",
            ),
            KPIResponse(
                name="Occupancy (approx)",
                value=rec.active_students,
                unit="students",
                trend_direction=None,
                trend_percentage=None,
                target_value=None,
                good_when="higher_is_better",
            ),
        ]

        # No timeseries is stored in this snapshot table; return empty lists
        period_filter = DateRangeFilter(
            start_date=rec.period_start,
            end_date=rec.period_end,
        )

        return DashboardMetricsSchema(
            scope_type=scope_type,
            scope_id=scope_id,
            period=period_filter,
            generated_at=rec.generated_at,
            kpis=kpis,
            quick_stats=quick,
            revenue_timeseries=[],
            occupancy_timeseries=[],
            booking_timeseries=[],
            complaint_timeseries=[],
        )