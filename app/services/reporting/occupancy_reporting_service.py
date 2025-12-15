# app/services/reporting/occupancy_reporting_service.py
from __future__ import annotations

from typing import Callable, List, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository
from app.schemas.common.filters import DateRangeFilter
from app.schemas.analytics.occupancy_analytics import (
    OccupancyReport,
    OccupancyKPI,
)
from app.services.analytics import OccupancyAnalyticsService
from app.services.common import UnitOfWork, errors


class OccupancyReportingService:
    """
    Occupancy reporting:

    - Per-hostel OccupancyReport (daily trend, KPIs, by room type).
    - Convenience multi-hostel KPI snapshot for admins.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._occupancy_analytics = OccupancyAnalyticsService(session_factory)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Per-hostel
    # ------------------------------------------------------------------ #
    def get_hostel_occupancy_report(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> OccupancyReport:
        """
        Direct wrapper over OccupancyAnalyticsService.get_occupancy_report.
        """
        return self._occupancy_analytics.get_occupancy_report(
            hostel_id=hostel_id,
            period=period,
        )

    # ------------------------------------------------------------------ #
    # Multi-hostel snapshot
    # ------------------------------------------------------------------ #
    def get_multi_hostel_kpis(
        self,
        hostel_ids: List[UUID],
        period: DateRangeFilter,
    ) -> Dict[UUID, OccupancyKPI]:
        """
        Build a simple map of hostel_id -> OccupancyKPI for the given hostels.
        """
        results: Dict[UUID, OccupancyKPI] = {}
        for hid in hostel_ids:
            report = self._occupancy_analytics.get_occupancy_report(
                hostel_id=hid,
                period=period,
            )
            results[hid] = report.kpi
        return results

    def get_all_active_hostels_kpis(
        self,
        period: DateRangeFilter,
        *,
        limit: Optional[int] = None,
    ) -> Dict[UUID, OccupancyKPI]:
        """
        Convenience method: fetch KPIs for all active hostels (optionally limited).

        This uses core_hostel via HostelRepository to discover hostels and then
        calls occupancy analytics per hostel.
        """
        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            hostels = hostel_repo.list_public(limit=limit or 0)

        hostel_ids = [h.id for h in hostels]
        return self.get_multi_hostel_kpis(hostel_ids, period)