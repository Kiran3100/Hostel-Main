# app/services/analytics/supervisor_analytics_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.analytics import SupervisorPerformanceMetricsRepository
from app.repositories.core import HostelRepository, SupervisorRepository
from app.schemas.analytics.supervisor_analytics import (
    SupervisorKPI,
    SupervisorDashboardAnalytics,
    SupervisorTrendPoint,
    SupervisorComparison,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork



class SupervisorAnalyticsService:
    """
    Supervisor performance analytics based on analytics_supervisor_performance.

    - Per-supervisor KPI & dashboard
    - Comparison between supervisors in a hostel or platform-wide
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> SupervisorPerformanceMetricsRepository:
        return uow.get_repo(SupervisorPerformanceMetricsRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    # ------------------------------------------------------------------ #
    # Individual dashboard
    # ------------------------------------------------------------------ #
    def get_dashboard(
        self,
        *,
        supervisor_id: UUID,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Optional[SupervisorDashboardAnalytics]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            metrics = repo.get_for_supervisor_period(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                period_start=period.start_date,
                period_end=period.end_date,
            )
            if not metrics:
                return None

            sup = sup_repo.get(supervisor_id)
            hostel = hostel_repo.get(hostel_id)
            sup_name = sup.user.full_name if sup and getattr(sup, "user", None) else ""
            hostel_name = hostel.name if hostel else ""

            kpi = self._to_kpi(metrics, supervisor_name=sup_name, hostel_name=hostel_name, period=period)

            # Trend: for now, we only return a single point for this period.
            trend = [
                SupervisorTrendPoint(
                    period_label=f"{period.start_date}–{period.end_date}",
                    complaints_resolved=metrics.complaints_resolved,
                    maintenance_completed=metrics.maintenance_requests_completed,
                    performance_score=metrics.overall_performance_score,
                )
            ]

            return SupervisorDashboardAnalytics(
                supervisor_id=supervisor_id,
                supervisor_name=sup_name,
                hostel_id=hostel_id,
                hostel_name=hostel_name,
                period=period,
                generated_at=datetime.utcnow(),
                kpi=kpi,
                trend=trend,
                complaints_by_category={},
                maintenance_by_category={},
            )

    # ------------------------------------------------------------------ #
    # Comparison
    # ------------------------------------------------------------------ #
    def get_comparison(
        self,
        *,
        scope_type: str,    # 'hostel' or 'platform'
        hostel_id: Optional[UUID],
        period: DateRangeFilter,
    ) -> SupervisorComparison:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            # Fetch all metrics for given period & scope
            filters: Dict[str, object] = {}
            if hostel_id:
                filters["hostel_id"] = hostel_id
            # BaseRepository.get_multi will apply equality filters
            metrics_list = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

            # Filter by period_start/end in Python to be safe
            filtered = [
                m
                for m in metrics_list
                if (not period.start_date or m.period_start >= period.start_date)
                and (not period.end_date or m.period_end <= period.end_date)
            ]

            kpis: List[SupervisorKPI] = []
            score_by_supervisor: Dict[UUID, Decimal] = {}
            speed_by_supervisor: Dict[UUID, Decimal] = {}

            for m in filtered:
                sup = sup_repo.get(m.supervisor_id)
                hostel = hostel_repo.get(m.hostel_id)
                sup_name = sup.user.full_name if sup and getattr(sup, "user", None) else ""
                hostel_name = hostel.name if hostel else ""

                kpi = self._to_kpi(m, supervisor_name=sup_name, hostel_name=hostel_name, period=period)
                kpis.append(kpi)
                score_by_supervisor[m.supervisor_id] = kpi.overall_performance_score
                speed_by_supervisor[m.supervisor_id] = kpi.avg_complaint_resolution_time_hours

            # Rankings
            ranked_by_performance = sorted(
                score_by_supervisor, key=lambda sid: score_by_supervisor[sid], reverse=True
            )
            ranked_by_resolution_speed = sorted(
                speed_by_supervisor, key=lambda sid: speed_by_supervisor[sid]
            )
            ranked_by_feedback_score: List[UUID] = []  # feedback not yet wired

            return SupervisorComparison(
                scope_type=scope_type,
                hostel_id=hostel_id,
                period=period,
                generated_at=datetime.utcnow(),
                supervisors=kpis,
                ranked_by_performance=ranked_by_performance,
                ranked_by_resolution_speed=ranked_by_resolution_speed,
                ranked_by_feedback_score=ranked_by_feedback_score,
            )

    # ------------------------------------------------------------------ #
    # Mapping helper
    # ------------------------------------------------------------------ #
    def _to_kpi(
        self,
        m,
        *,
        supervisor_name: str,
        hostel_name: str,
        period: DateRangeFilter,
    ) -> SupervisorKPI:
        return SupervisorKPI(
            supervisor_id=m.supervisor_id,
            supervisor_name=supervisor_name,
            hostel_id=m.hostel_id,
            hostel_name=hostel_name,
            period=period,
            complaints_assigned=m.complaints_assigned,
            complaints_resolved=m.complaints_resolved,
            maintenance_requests_created=m.maintenance_requests_created,
            maintenance_requests_completed=m.maintenance_requests_completed,
            attendance_records_marked=m.attendance_records_marked,
            avg_complaint_resolution_time_hours=m.avg_complaint_resolution_time_hours,
            avg_maintenance_completion_time_hours=m.avg_maintenance_completion_time_hours,
            complaint_sla_compliance_rate=Decimal("0"),
            maintenance_sla_compliance_rate=Decimal("0"),
            student_feedback_score=None,
            overall_performance_score=m.overall_performance_score,
        )