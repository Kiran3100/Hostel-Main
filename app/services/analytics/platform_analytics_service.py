# app/services/analytics/platform_analytics_service.py
from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.analytics import (
    PlatformMetricsRepository,
    GrowthMetricsRepository,
    PlatformUsageAnalyticsRepository,
)
from app.schemas.analytics.platform_analytics import (
    PlatformMetrics as PlatformMetricsSchema,
    GrowthMetrics as GrowthMetricsSchema,
    PlatformUsageAnalytics as PlatformUsageAnalyticsSchema,
    MonthlyMetric,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork


class PlatformAnalyticsService:
    """
    Platform-wide analytics facade.

    Wraps analytics_platform_metrics, analytics_growth_metrics,
    and analytics_platform_usage tables into the corresponding schemas.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_platform_repo(self, uow: UnitOfWork) -> PlatformMetricsRepository:
        return uow.get_repo(PlatformMetricsRepository)

    def _get_growth_repo(self, uow: UnitOfWork) -> GrowthMetricsRepository:
        return uow.get_repo(GrowthMetricsRepository)

    def _get_usage_repo(self, uow: UnitOfWork) -> PlatformUsageAnalyticsRepository:
        return uow.get_repo(PlatformUsageAnalyticsRepository)

    # ------------------------------------------------------------------ #
    # Platform metrics
    # ------------------------------------------------------------------ #
    def get_latest_platform_metrics(self) -> Optional[PlatformMetricsSchema]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_platform_repo(uow)
            rec = repo.get_latest()
            if not rec:
                return None

        return PlatformMetricsSchema(
            period=DateRangeFilter(start_date=rec.period_start, end_date=rec.period_end),
            generated_at=rec.generated_at,
            total_hostels=rec.total_hostels,
            active_hostels=rec.active_hostels,
            hostels_on_trial=rec.hostels_on_trial,
            total_users=rec.total_users,
            total_students=rec.total_students,
            total_supervisors=rec.total_supervisors,
            total_admins=rec.total_admins,
            total_visitors=rec.total_visitors,
            avg_daily_active_users=rec.avg_daily_active_users,
            peak_concurrent_sessions=rec.peak_concurrent_sessions,
        )

    def get_growth_metrics(
        self,
        period: DateRangeFilter,
    ) -> Optional[GrowthMetricsSchema]:
        if not (period.start_date and period.end_date):
            return None

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_growth_repo(uow)
            rec = repo.get_for_period(
                period_start=period.start_date,
                period_end=period.end_date,
            )
            if not rec:
                return None

        # monthly_* lists are not stored in the model; keep them empty for now.
        return GrowthMetricsSchema(
            period=period,
            new_hostels=rec.new_hostels,
            churned_hostels=rec.churned_hostels,
            net_hostel_growth=rec.net_hostel_growth,
            total_revenue=rec.total_revenue,
            revenue_growth_rate=rec.revenue_growth_rate,
            new_users=rec.new_users,
            user_growth_rate=rec.user_growth_rate,
            monthly_revenue=[],
            monthly_new_hostels=[],
            monthly_new_users=[],
        )

    def get_latest_usage_metrics(self) -> Optional[PlatformUsageAnalyticsSchema]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_usage_repo(uow)
            rec = repo.get_latest()
            if not rec:
                return None

        return PlatformUsageAnalyticsSchema(
            period=DateRangeFilter(start_date=rec.period_start, end_date=rec.period_end),
            generated_at=rec.generated_at,
            total_requests=rec.total_requests,
            avg_requests_per_minute=rec.avg_requests_per_minute,
            api_error_rate=rec.api_error_rate,
            requests_by_module={},
            avg_response_time_ms=rec.avg_response_time_ms,
            p95_response_time_ms=rec.p95_response_time_ms,
            p99_response_time_ms=rec.p99_response_time_ms,
            avg_cpu_usage_percent=None,
            avg_memory_usage_percent=None,
        )