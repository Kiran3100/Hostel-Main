# app/services/supervisor/supervisor_performance_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository, SupervisorRepository
from app.repositories.analytics import SupervisorPerformanceMetricsRepository
from app.schemas.common.filters import DateRangeFilter
from app.schemas.supervisor import (
    PerformanceMetrics,
    PerformanceReport,
    ComplaintPerformance,
    AttendancePerformance,
    MaintenancePerformance,
)
from app.services.analytics import SupervisorAnalyticsService
from app.services.common import UnitOfWork, errors


class SupervisorPerformanceService:
    """
    Supervisor performance service:

    - Map analytics_supervisor_performance into PerformanceMetrics.
    - Provide a basic PerformanceReport wrapper.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._analytics = SupervisorAnalyticsService(session_factory)

    # Helpers
    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_metrics_repo(self, uow: UnitOfWork) -> SupervisorPerformanceMetricsRepository:
        return uow.get_repo(SupervisorPerformanceMetricsRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # Mapping
    def _to_performance_metrics(self, m, *, supervisor_name: str) -> PerformanceMetrics:
        total_complaints = m.complaints_assigned
        complaints_resolved = m.complaints_resolved
        complaint_resolution_rate = (
            Decimal(str(complaints_resolved)) / Decimal(str(total_complaints)) * Decimal("100")
            if total_complaints > 0
            else Decimal("0")
        )

        return PerformanceMetrics(
            supervisor_id=m.supervisor_id,
            supervisor_name=supervisor_name,
            hostel_id=m.hostel_id,
            period_start=m.period_start,
            period_end=m.period_end,
            complaints_handled=m.complaints_assigned,
            complaints_resolved=m.complaints_resolved,
            complaint_resolution_rate=complaint_resolution_rate,
            average_resolution_time_hours=m.avg_complaint_resolution_time_hours,
            sla_compliance_rate=Decimal("0"),
            attendance_records_created=m.attendance_records_marked,
            attendance_accuracy=Decimal("0"),
            leaves_approved=0,
            leaves_rejected=0,
            maintenance_requests_created=m.maintenance_requests_created,
            maintenance_completed=m.maintenance_requests_completed,
            maintenance_completion_rate=Decimal("0"),
            average_maintenance_time_hours=m.avg_maintenance_completion_time_hours,
            announcements_created=0,
            announcement_reach=0,
            average_first_response_time_minutes=Decimal("0"),
            availability_percentage=Decimal("0"),
            student_feedback_score=None,
            overall_performance_score=m.overall_performance_score,
        )

    # Public API
    def get_performance_metrics(
        self,
        supervisor_id: UUID,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Optional[PerformanceMetrics]:
        with UnitOfWork(self._session_factory) as uow:
            metrics_repo = self._get_metrics_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            m = metrics_repo.get_for_supervisor_period(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                period_start=period.start_date,
                period_end=period.end_date,
            )
            if not m:
                return None

            sup = sup_repo.get(supervisor_id)
            sup_name = sup.user.full_name if sup and getattr(sup, "user", None) else ""

        return self._to_performance_metrics(m, supervisor_name=sup_name)

    def get_performance_report(
        self,
        supervisor_id: UUID,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Optional[PerformanceReport]:
        with UnitOfWork(self._session_factory) as uow:
            metrics_repo = self._get_metrics_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            m = metrics_repo.get_for_supervisor_period(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                period_start=period.start_date,
                period_end=period.end_date,
            )
            if not m:
                return None

            sup = sup_repo.get(supervisor_id)
            hostel = hostel_repo.get(hostel_id)
            sup_name = sup.user.full_name if sup and getattr(sup, "user", None) else ""
            hostel_name = hostel.name if hostel else ""

        metrics = self._to_performance_metrics(m, supervisor_name=sup_name)

        # Very simple placeholders for detailed sections
        complaint_perf = ComplaintPerformance(
            total_complaints=m.complaints_assigned,
            resolved_complaints=m.complaints_resolved,
            pending_complaints=m.complaints_assigned - m.complaints_resolved,
            complaints_by_category={},
            complaints_by_priority={},
            average_resolution_time_hours=m.avg_complaint_resolution_time_hours,
            fastest_resolution_hours=m.avg_complaint_resolution_time_hours,
            slowest_resolution_hours=m.avg_complaint_resolution_time_hours,
            within_sla=0,
            breached_sla=0,
            sla_compliance_rate=Decimal("0"),
            average_complaint_rating=None,
        )

        attendance_perf = AttendancePerformance(
            total_attendance_records=m.attendance_records_marked,
            days_attendance_marked=0,
            days_attendance_missed=0,
            on_time_marking_rate=Decimal("0"),
            average_marking_delay_minutes=Decimal("0"),
            corrections_made=0,
            accuracy_rate=Decimal("0"),
            leaves_processed=0,
            average_leave_approval_time_hours=Decimal("0"),
        )

        maintenance_perf = MaintenancePerformance(
            requests_created=m.maintenance_requests_created,
            requests_completed=m.maintenance_requests_completed,
            requests_pending=m.maintenance_requests_created - m.maintenance_requests_completed,
            requests_by_category={},
            average_completion_time_hours=m.avg_maintenance_completion_time_hours,
            total_maintenance_cost=Decimal("0"),
            average_cost_per_request=Decimal("0"),
            within_budget_rate=Decimal("0"),
            preventive_tasks_completed=0,
            preventive_compliance_rate=Decimal("0"),
        )

        return PerformanceReport(
            supervisor_id=supervisor_id,
            supervisor_name=sup_name,
            hostel_name=hostel_name,
            report_period=period,
            generated_at=self._now(),
            summary=metrics,
            complaint_performance=complaint_perf,
            attendance_performance=attendance_perf,
            maintenance_performance=maintenance_perf,
            performance_trends=[],
            comparison_with_peers=None,
            comparison_with_previous_period=None,
            strengths=[],
            areas_for_improvement=[],
            recommendations=[],
        )