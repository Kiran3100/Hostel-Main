# app/services/admin/multi_hostel_dashboard_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.associations import AdminHostelRepository
from app.repositories.core import AdminRepository, HostelRepository, StudentRepository
from app.repositories.transactions import PaymentRepository
from app.repositories.services import ComplaintRepository, MaintenanceRepository
from app.schemas.admin import (
    MultiHostelDashboard,
    AggregatedStats,
    HostelQuickStats,
    CrossHostelComparison,
)
from app.schemas.admin.multi_hostel_dashboard import (
    TopPerformer,
    BottomPerformer,
    HostelMetricComparison,
    HostelTaskSummary,
)
from app.schemas.common.enums import (
    PaymentStatus,
    ComplaintStatus,
    Priority,
    StudentStatus,
)
from app.services.common import UnitOfWork, errors


class MultiHostelDashboardService:
    """
    Build a consolidated dashboard for admins who manage multiple hostels.

    This service uses existing core/transactions/service repositories to
    assemble a high-level view; it focuses on correctness and simplicity,
    not heavy optimization.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_admin_repo(self, uow: UnitOfWork) -> AdminRepository:
        return uow.get_repo(AdminRepository)

    def _get_admin_hostel_repo(self, uow: UnitOfWork) -> AdminHostelRepository:
        return uow.get_repo(AdminHostelRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_complaint_repo(self, uow: UnitOfWork) -> ComplaintRepository:
        return uow.get_repo(ComplaintRepository)

    def _get_maintenance_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def _today(self) -> date:
        return date.today()

    # ------------------------------------------------------------------ #
    # Main API
    # ------------------------------------------------------------------ #
    def get_dashboard_for_admin(self, admin_user_id: UUID) -> MultiHostelDashboard:
        """
        Build a multi-hostel dashboard for a given admin (by core_user.id).

        Steps:
        - Resolve Admin profile (core_admin) by user_id
        - Get all hostels assigned to that admin via AdminHostel
        - For each hostel, compute quick stats using existing repositories
        - Aggregate overall statistics and comparisons
        """
        today = self._today()

        with UnitOfWork(self._session_factory) as uow:
            admin_repo = self._get_admin_repo(uow)
            admin_hostel_repo = self._get_admin_hostel_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            payment_repo = self._get_payment_repo(uow)
            complaint_repo = self._get_complaint_repo(uow)
            maintenance_repo = self._get_maintenance_repo(uow)

            admin_profile = admin_repo.get_by_user_id(admin_user_id)
            if admin_profile is None:
                raise errors.NotFoundError(
                    f"No Admin profile found for user {admin_user_id}"
                )

            admin_user = (
                admin_profile.user
                if getattr(admin_profile, "user", None)
                else None
            )
            admin_name = admin_user.full_name if admin_user else ""

            # All active hostels for this admin
            hostels = admin_hostel_repo.get_hostels_for_admin(
                admin_id=admin_profile.id,
                only_active=True,
            )

            total_hostels_managed = len(hostels)
            hostel_quick_stats: List[HostelQuickStats] = []
            tasks_by_hostel: Dict[UUID, HostelTaskSummary] = {}

            # Aggregation accumulators
            agg_total_beds = 0
            agg_occupied_beds = 0
            agg_total_students = 0
            agg_active_students = 0
            agg_total_revenue_this_month = Decimal("0")
            agg_total_outstanding = Decimal("0")
            agg_total_overdue = Decimal("0")
            agg_pending_bookings = 0  # bookings service not wired; left 0
            agg_open_complaints = 0
            agg_pending_maintenance = 0
            agg_total_reviews = 0
            sum_ratings = Decimal("0")

            # Per-hostel metric caches for comparisons
            occupancy_metrics: Dict[UUID, Decimal] = {}
            revenue_metrics: Dict[UUID, Decimal] = {}
            complaint_metrics: Dict[UUID, Decimal] = {}

            for h in hostels:
                # Capacity
                total_beds = h.total_beds or 0
                occupied_beds = h.occupied_beds or 0
                available_beds = max(0, total_beds - occupied_beds)
                occupancy_pct = (
                    Decimal(str(occupied_beds / total_beds * 100))
                    if total_beds > 0
                    else Decimal("0")
                )

                # Students
                students = student_repo.list_for_hostel(h.id, status=None)
                total_students = len(students)
                active_students = sum(
                    1
                    for s in students
                    if s.student_status == StudentStatus.ACTIVE
                )

                # Payments (very simple hostel-monthly snapshot)
                payments = payment_repo.get_multi(filters={"hostel_id": h.id})
                revenue_this_month = Decimal("0")
                outstanding_amount = Decimal("0")
                overdue_amount = Decimal("0")
                overdue_payments_count = 0

                for p in payments:
                    if (
                        p.payment_status == PaymentStatus.COMPLETED
                        and p.paid_at
                    ):
                        if (
                            p.paid_at.date().year == today.year
                            and p.paid_at.date().month == today.month
                        ):
                            revenue_this_month += p.amount
                    if p.payment_status == PaymentStatus.PENDING:
                        outstanding_amount += p.amount
                        if p.due_date and p.due_date < today:
                            overdue_amount += p.amount
                            overdue_payments_count += 1

                # Complaints / maintenance
                open_complaints_list = complaint_repo.list_open_for_hostel(
                    h.id,
                    category=None,
                    priority=None,
                )
                open_complaints = len(open_complaints_list)

                open_maintenance_list = maintenance_repo.list_open_for_hostel(
                    h.id,
                    category=None,
                    priority=None,
                )
                pending_maintenance = len(open_maintenance_list)

                # Reviews from core_hostel (aggregated)
                avg_rating = Decimal(str(h.average_rating or 0.0))
                total_reviews = h.total_reviews or 0

                # Hostels' quick stats
                hostel_quick_stats.append(
                    HostelQuickStats(
                        hostel_id=h.id,
                        hostel_name=h.name,
                        hostel_city=h.city,
                        occupancy_percentage=occupancy_pct,
                        available_beds=available_beds,
                        revenue_this_month=revenue_this_month,
                        outstanding_amount=outstanding_amount,
                        pending_bookings=0,  # booking service not wired here
                        open_complaints=open_complaints,
                        pending_maintenance=pending_maintenance,
                        overdue_payments_count=overdue_payments_count,
                        status_color="green",  # simple heuristic
                        last_supervisor_activity=None,
                    )
                )

                # Hostels' task summary
                urgent_tasks = sum(
                    1
                    for c in open_complaints_list
                    if c.priority in (Priority.URGENT, Priority.CRITICAL)
                ) + sum(
                    1
                    for m in open_maintenance_list
                    if m.priority in (Priority.URGENT, Priority.CRITICAL)
                )
                high_priority_tasks = sum(
                    1 for c in open_complaints_list if c.priority == Priority.HIGH
                ) + sum(
                    1 for m in open_maintenance_list if m.priority == Priority.HIGH
                )
                medium_priority_tasks = sum(
                    1
                    for c in open_complaints_list
                    if c.priority == Priority.MEDIUM
                ) + sum(
                    1
                    for m in open_maintenance_list
                    if m.priority == Priority.MEDIUM
                )
                low_priority_tasks = sum(
                    1 for c in open_complaints_list if c.priority == Priority.LOW
                ) + sum(
                    1 for m in open_maintenance_list if m.priority == Priority.LOW
                )
                total_tasks = (
                    urgent_tasks
                    + high_priority_tasks
                    + medium_priority_tasks
                    + low_priority_tasks
                )

                tasks_by_hostel[h.id] = HostelTaskSummary(
                    hostel_id=h.id,
                    urgent_tasks=urgent_tasks,
                    high_priority_tasks=high_priority_tasks,
                    medium_priority_tasks=medium_priority_tasks,
                    low_priority_tasks=low_priority_tasks,
                    total_tasks=total_tasks,
                )

                # Aggregation
                agg_total_beds += total_beds
                agg_occupied_beds += occupied_beds
                agg_total_students += total_students
                agg_active_students += active_students
                agg_total_revenue_this_month += revenue_this_month
                agg_total_outstanding += outstanding_amount
                agg_total_overdue += overdue_amount
                agg_pending_bookings += 0
                agg_open_complaints += open_complaints
                agg_pending_maintenance += pending_maintenance
                agg_total_reviews += total_reviews
                sum_ratings += avg_rating

                occupancy_metrics[h.id] = occupancy_pct
                revenue_metrics[h.id] = revenue_this_month
                complaint_metrics[h.id] = Decimal(str(open_complaints))

            average_occupancy_percentage = (
                Decimal(str(agg_occupied_beds / agg_total_beds * 100))
                if agg_total_beds > 0
                else Decimal("0")
            )
            average_rating_across_hostels = (
                (sum_ratings / total_hostels_managed)
                if total_hostels_managed > 0
                else Decimal("0")
            )

            aggregated_stats = AggregatedStats(
                total_beds=agg_total_beds,
                total_occupied=agg_occupied_beds,
                total_available=max(0, agg_total_beds - agg_occupied_beds),
                average_occupancy_percentage=average_occupancy_percentage,
                total_students=agg_total_students,
                active_students=agg_active_students,
                total_revenue_this_month=agg_total_revenue_this_month,
                total_outstanding=agg_total_outstanding,
                total_overdue=agg_total_overdue,
                total_pending_bookings=agg_pending_bookings,
                total_confirmed_bookings=0,
                booking_conversion_rate=Decimal("0"),
                total_open_complaints=agg_open_complaints,
                total_resolved_this_month=Decimal("0"),
                average_resolution_time_hours=Decimal("0"),
                total_pending_maintenance=agg_pending_maintenance,
                total_completed_this_month=0,
                average_rating_across_hostels=average_rating_across_hostels,
                total_reviews=agg_total_reviews,
            )

            # Comparisons
            def _top_id(metric: Dict[UUID, Decimal]) -> Optional[UUID]:
                return max(metric, key=lambda k: metric[k]) if metric else None

            def _bottom_id(metric: Dict[UUID, Decimal]) -> Optional[UUID]:
                return min(metric, key=lambda k: metric[k]) if metric else None

            highest_occ_id = _top_id(occupancy_metrics)
            highest_rev_id = _top_id(revenue_metrics)
            highest_rating_id = _top_id(
                {h.id: Decimal(str(h.average_rating or 0.0)) for h in hostels}
            )
            lowest_occ_id = _bottom_id(occupancy_metrics)
            most_complaints_id = _top_id(complaint_metrics)
            # For "most overdue payments", reuse complaint_metrics as a placeholder
            most_overdue_payments_id = most_complaints_id

            def _get_hostel_name(hid: Optional[UUID]) -> str:
                if hid is None:
                    return ""
                hh = hostel_repo.get(hid)
                return hh.name if hh else ""

            top_occ = (
                TopPerformer(
                    hostel_id=highest_occ_id or UUID(int=0),
                    hostel_name=_get_hostel_name(highest_occ_id),
                    metric_value=occupancy_metrics.get(
                        highest_occ_id, Decimal("0")
                    ),
                    metric_name="occupancy_percentage",
                )
                if highest_occ_id
                else TopPerformer(
                    hostel_id=UUID(int=0),
                    hostel_name="",
                    metric_value=Decimal("0"),
                    metric_name="occupancy_percentage",
                )
            )

            top_rev = (
                TopPerformer(
                    hostel_id=highest_rev_id or UUID(int=0),
                    hostel_name=_get_hostel_name(highest_rev_id),
                    metric_value=revenue_metrics.get(
                        highest_rev_id, Decimal("0")
                    ),
                    metric_name="revenue_this_month",
                )
                if highest_rev_id
                else TopPerformer(
                    hostel_id=UUID(int=0),
                    hostel_name="",
                    metric_value=Decimal("0"),
                    metric_name="revenue_this_month",
                )
            )

            top_rating_val = Decimal("0")
            if highest_rating_id:
                h_rec = hostel_repo.get(highest_rating_id)
                if h_rec:
                    top_rating_val = Decimal(str(h_rec.average_rating or 0.0))

            top_rating = (
                TopPerformer(
                    hostel_id=highest_rating_id or UUID(int=0),
                    hostel_name=_get_hostel_name(highest_rating_id),
                    metric_value=top_rating_val,
                    metric_name="average_rating",
                )
                if highest_rating_id
                else TopPerformer(
                    hostel_id=UUID(int=0),
                    hostel_name="",
                    metric_value=Decimal("0"),
                    metric_name="average_rating",
                )
            )

            bottom_occ = (
                BottomPerformer(
                    hostel_id=lowest_occ_id or UUID(int=0),
                    hostel_name=_get_hostel_name(lowest_occ_id),
                    metric_value=occupancy_metrics.get(
                        lowest_occ_id, Decimal("0")
                    ),
                    metric_name="occupancy_percentage",
                    issue_severity="medium",
                )
                if lowest_occ_id
                else BottomPerformer(
                    hostel_id=UUID(int=0),
                    hostel_name="",
                    metric_value=Decimal("0"),
                    metric_name="occupancy_percentage",
                    issue_severity="low",
                )
            )

            bottom_complaints = (
                BottomPerformer(
                    hostel_id=most_complaints_id or UUID(int=0),
                    hostel_name=_get_hostel_name(most_complaints_id),
                    metric_value=complaint_metrics.get(
                        most_complaints_id, Decimal("0")
                    ),
                    metric_name="open_complaints",
                    issue_severity="high",
                )
                if most_complaints_id
                else BottomPerformer(
                    hostel_id=UUID(int=0),
                    hostel_name="",
                    metric_value=Decimal("0"),
                    metric_name="open_complaints",
                    issue_severity="low",
                )
            )

            bottom_overdue = (
                BottomPerformer(
                    hostel_id=most_overdue_payments_id or UUID(int=0),
                    hostel_name=_get_hostel_name(most_overdue_payments_id),
                    metric_value=complaint_metrics.get(
                        most_overdue_payments_id, Decimal("0")
                    ),
                    metric_name="overdue_payments",
                    issue_severity="high",
                )
                if most_overdue_payments_id
                else BottomPerformer(
                    hostel_id=UUID(int=0),
                    hostel_name="",
                    metric_value=Decimal("0"),
                    metric_name="overdue_payments",
                    issue_severity="low",
                )
            )

            # Simple comparison lists (occupancy, revenue, complaints)
            def _build_metric_list(
                metric: Dict[UUID, Decimal], metric_name: str
            ) -> List[HostelMetricComparison]:
                if not metric:
                    return []
                max_val = max(metric.values())
                if max_val <= 0:
                    max_val = Decimal("1")
                results: List[HostelMetricComparison] = []
                for hid, val in metric.items():
                    results.append(
                        HostelMetricComparison(
                            hostel_id=hid,
                            hostel_name=_get_hostel_name(hid),
                            metric_value=val,
                            percentage_of_best=(val / max_val * 100),
                            trend="stable",
                        )
                    )
                return results

            occupancy_comparison = _build_metric_list(
                occupancy_metrics, "occupancy_percentage"
            )
            revenue_comparison = _build_metric_list(
                revenue_metrics, "revenue_this_month"
            )
            complaint_rate_comparison = _build_metric_list(
                complaint_metrics, "open_complaints"
            )

            comparisons = CrossHostelComparison(
                highest_occupancy_hostel=top_occ,
                highest_revenue_hostel=top_rev,
                highest_rated_hostel=top_rating,
                lowest_occupancy_hostel=bottom_occ,
                most_complaints_hostel=bottom_complaints,
                most_overdue_payments_hostel=bottom_overdue,
                occupancy_comparison=occupancy_comparison,
                revenue_comparison=revenue_comparison,
                complaint_rate_comparison=complaint_rate_comparison,
            )

            # Notifications not yet wired; return zeros
            total_notifications = 0
            notifications_by_hostel: Dict[UUID, int] = {h.id: 0 for h in hostels}

            total_pending_tasks = sum(
                ts.total_tasks for ts in tasks_by_hostel.values()
            )

            return MultiHostelDashboard(
                admin_id=admin_user_id,
                admin_name=admin_name,
                total_hostels_managed=total_hostels_managed,
                aggregated_stats=aggregated_stats,
                hostel_stats=hostel_quick_stats,
                comparisons=comparisons,
                total_notifications=total_notifications,
                notifications_by_hostel=notifications_by_hostel,
                total_pending_tasks=total_pending_tasks,
                tasks_by_hostel=tasks_by_hostel,
            )