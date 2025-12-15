# app/services/admin/super_admin_dashboard_service.py
from __future__ import annotations

from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.repositories.analytics import (
    PlatformMetricsRepository,
    GrowthMetricsRepository,
    PlatformUsageAnalyticsRepository,
)
from app.schemas.analytics import (
    PlatformMetrics as PlatformMetricsSchema,
    GrowthMetrics as GrowthMetricsSchema,
    PlatformUsageAnalytics as PlatformUsageAnalyticsSchema,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork, mapping


class SuperAdminDashboardService:
    """
    High-level platform-wide analytics for super admins.

    This service is a thin facade over the analytics.* repositories and
    corresponding Pydantic schemas.
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
    # Metrics
    # ------------------------------------------------------------------ #
    def get_platform_metrics(self) -> Optional[PlatformMetricsSchema]:
        """
        Get the latest snapshot of platform-wide metrics, if any.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_platform_repo(uow)
            rec = repo.get_latest()
            if not rec:
                return None
            return mapping.to_schema(rec, PlatformMetricsSchema)

    def get_growth_metrics(self, period: DateRangeFilter) -> Optional[GrowthMetricsSchema]:
        """
        Fetch GrowthMetrics for a specific period, if present.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_growth_repo(uow)
            if not (period.start_date and period.end_date):
                return None
            rec = repo.get_for_period(
                period_start=period.start_date,
                period_end=period.end_date,
            )
            if not rec:
                return None
            return mapping.to_schema(rec, GrowthMetricsSchema)

    def get_usage_metrics(self) -> Optional[PlatformUsageAnalyticsSchema]:
        """
        Get latest platform usage & latency metrics.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_usage_repo(uow)
            rec = repo.get_latest()
            if not rec:
                return None
            return mapping.to_schema(rec, PlatformUsageAnalyticsSchema)