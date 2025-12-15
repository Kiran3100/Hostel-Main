# app/services/supervisor/supervisor_dashboard_service.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import (
    SupervisorRepository,
    HostelRepository,
    StudentRepository,
    BedRepository,
)
from app.repositories.services import (
    ComplaintRepository,
    MaintenanceRepository,
    AttendanceRepository,
    LeaveApplicationRepository,
)
from app.repositories.transactions import PaymentRepository
from app.schemas.common.enums import ComplaintStatus, MaintenanceStatus, AttendanceStatus, LeaveStatus, Priority
from app.schemas.supervisor import (
    SupervisorDashboard,
    DashboardMetrics,
    TaskSummary,
    RecentComplaintItem,
    RecentMaintenanceItem,
    PendingLeaveItem,
    TodaySchedule,
    ScheduledMaintenanceItem,
    ScheduledMeeting,
    DashboardAlert,
)
from app.services.common import UnitOfWork, errors


class SupervisorDashboardService:
    """
    Supervisor dashboard aggregation:

    - Quick metrics for students, occupancy, complaints, maintenance, attendance, payments.
    - Recent complaints/maintenance/leaves.
    - Simple schedule skeleton and alerts.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    def _get_complaint_repo(self, uow: UnitOfWork) -> ComplaintRepository:
        return uow.get_repo(ComplaintRepository)

    def _get_maintenance_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def _get_attendance_repo(self, uow: UnitOfWork) -> AttendanceRepository:
        return uow.get_repo(AttendanceRepository)

    def _get_leave_repo(self, uow: UnitOfWork) -> LeaveApplicationRepository:
        return uow.get_repo(LeaveApplicationRepository)

    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _today(self) -> date:
        return date.today()

    def _now(self) -> datetime:
        return datetime.utcnow()

    # Public API
    def get_dashboard(self, supervisor_id: UUID) -> SupervisorDashboard:
        today = self._today()

        with UnitOfWork(self._session_factory) as uow:
            sup_repo = self._get_supervisor_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            bed_repo = self._get_bed_repo(uow)
            complaint_repo = self._get_complaint_repo(uow)
            maintenance_repo = self._get_maintenance_repo(uow)
            attendance_repo = self._get_attendance_repo(uow)
            leave_repo = self._get_leave_repo(uow)
            payment_repo = self._get_payment_repo(uow)

            sup = sup_repo.get(supervisor_id)
            if sup is None or not getattr(sup, "user", None):
                raise errors.NotFoundError(f"Supervisor {supervisor_id} not found")

            hostel = hostel_repo.get(sup.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {sup.hostel_id} not found")

            hostel_name = hostel.name

            # Students & beds
            students = student_repo.list_for_hostel(hostel.id, status=None)
            total_students = len(students)
            active_students = sum(1 for s in students if s.student_status.name == "ACTIVE")

            beds = bed_repo.get_multi(filters={"hostel_id": hostel.id})
            total_beds = len(beds)
            occupied_beds = sum(1 for b in beds if b.current_student_id is not None)
            available_beds = max(0, total_beds - occupied_beds)
            occupancy_pct = (
                Decimal(str(occupied_beds)) / Decimal(str(total_beds)) * Decimal("100")
                if total_beds > 0
                else Decimal("0")
            )

            # Complaints
            open_complaints_list = complaint_repo.list_open_for_hostel(
                hostel.id,
                category=None,
                priority=None,
            )
            total_complaints = len(
                complaint_repo.get_multi(filters={"hostel_id": hostel.id})
            )
            assigned_to_me = len(
                [c for c in open_complaints_list if c.assigned_to_id == supervisor_id]
            )
            resolved_today = 0  # detailed tracking omitted

            # Maintenance
            open_maintenance_list = maintenance_repo.list_open_for_hostel(
                hostel.id,
                category=None,
                priority=None,
            )
            pending_maintenance = len(open_maintenance_list)
            in_progress_maintenance = len(
                [m for m in open_maintenance_list if m.status == MaintenanceStatus.IN_PROGRESS]
            )
            completed_today = 0  # placeholder

            # Attendance today
            todays_attendance = attendance_repo.list_for_hostel_date(hostel.id, today)
            attendance_marked_today = len(todays_attendance) > 0
            total_present_today = len(
                [a for a in todays_attendance if a.status == AttendanceStatus.PRESENT]
            ) + len(
                [a for a in todays_attendance if a.status == AttendanceStatus.LATE]
            )
            total_absent_today = len(
                [a for a in todays_attendance if a.status == AttendanceStatus.ABSENT]
            )
            students_on_leave = len(
                [a for a in todays_attendance if a.status == AttendanceStatus.ON_LEAVE]
            )

            # Payments overdue
            overdue_payments = payment_repo.list_due_for_hostel(
                hostel.id,
                on_or_before=today,
            )
            overdue_payments_count = len(overdue_payments)

            # DashboardMetrics
            metrics = DashboardMetrics(
                total_students=total_students,
                active_students=active_students,
                total_beds=total_beds,
                occupied_beds=occupied_beds,
                available_beds=available_beds,
                occupancy_percentage=occupancy_pct,
                total_complaints=total_complaints,
                open_complaints=len(open_complaints_list),
                assigned_to_me=assigned_to_me,
                resolved_today=resolved_today,
                average_resolution_time_hours=Decimal("0"),
                pending_maintenance=pending_maintenance,
                in_progress_maintenance=in_progress_maintenance,
                completed_today=completed_today,
                attendance_marked_today=attendance_marked_today,
                total_present_today=total_present_today,
                total_absent_today=total_absent_today,
                students_on_leave=students_on_leave,
                overdue_payments_count=overdue_payments_count,
                unread_admin_messages=0,
            )

            # TaskSummary (simple heuristic)
            urgent_complaints = len(
                [c for c in open_complaints_list if c.priority in (Priority.CRITICAL, Priority.URGENT)]
            )
            critical_maintenance = len(
                [m for m in open_maintenance_list if m.priority in (Priority.CRITICAL, Priority.URGENT)]
            )
            pending_leave_approvals = len(
                leave_repo.list_pending_for_hostel(hostel.id)
            )

            attendance_pending = not attendance_marked_today
            menu_published_today = True
            daily_inspection_done = False

            overdue_complaint_resolutions = 0
            overdue_maintenance = 0

            total_pending_tasks = (
                urgent_complaints
                + critical_maintenance
                + pending_leave_approvals
                + (1 if attendance_pending else 0)
            )

            tasks = TaskSummary(
                urgent_complaints=urgent_complaints,
                critical_maintenance=critical_maintenance,
                pending_leave_approvals=pending_leave_approvals,
                attendance_pending=attendance_pending,
                menu_published_today=menu_published_today,
                daily_inspection_done=daily_inspection_done,
                overdue_complaint_resolutions=overdue_complaint_resolutions,
                overdue_maintenance=overdue_maintenance,
                total_pending_tasks=total_pending_tasks,
            )

            # Recent complaints (assigned to supervisor)
            rec_complaints = complaint_repo.list_for_supervisor(
                supervisor_id,
                include_closed=True,
            )[:5]
            recent_complaints: List[RecentComplaintItem] = []
            for c in rec_complaints:
                age_hours = int((self._now() - c.created_at).total_seconds() // 3600)
                recent_complaints.append(
                    RecentComplaintItem(
                        complaint_id=c.id,
                        complaint_number=str(c.id),
                        title=c.title,
                        category=c.category.value if hasattr(c.category, "value") else str(c.category),
                        priority=c.priority.value if hasattr(c.priority, "value") else str(c.priority),
                        status=c.status.value if hasattr(c.status, "value") else str(c.status),
                        student_name="",
                        room_number="",
                        created_at=c.created_at,
                        age_hours=age_hours,
                    )
                )

            # Recent maintenance
            all_maint = maintenance_repo.list_open_for_hostel(hostel.id, category=None, priority=None)[:5]
            recent_maintenance: List[RecentMaintenanceItem] = []
            for m in all_maint:
                recent_maintenance.append(
                    RecentMaintenanceItem(
                        request_id=m.id,
                        request_number=str(m.id),
                        title=m.title,
                        category=m.category.value if hasattr(m.category, "value") else str(m.category),
                        priority=m.priority.value if hasattr(m.priority, "value") else str(m.priority),
                        status=m.status.value if hasattr(m.status, "value") else str(m.status),
                        room_number=None,
                        estimated_cost=m.estimated_cost,
                        created_at=m.created_at,
                    )
                )

            # Pending leave approvals
            pending_leaves = leave_repo.list_pending_for_hostel(hostel.id)[:5]
            pending_leaves_items: List[PendingLeaveItem] = []
            for l in pending_leaves:
                pending_leaves_items.append(
                    PendingLeaveItem(
                        leave_id=l.id,
                        student_name="",
                        room_number="",
                        leave_type=l.leave_type.value if hasattr(l.leave_type, "value") else str(l.leave_type),
                        from_date=l.from_date,
                        to_date=l.to_date,
                        total_days=l.total_days,
                        reason=l.reason,
                        applied_at=l.created_at,
                    )
                )

            # Today's schedule (simple defaults)
            today_schedule = TodaySchedule(
                date=today,
                attendance_marking_time="09:00",
                inspection_rounds=["Ground Floor", "First Floor"],
                scheduled_maintenance=[],
                scheduled_meetings=[],
                special_events=[],
            )

            # Alerts (placeholder)
            alerts: List[DashboardAlert] = []

            last_login = getattr(sup.user, "last_login_at", None)
            actions_today = 0

        return SupervisorDashboard(
            supervisor_id=supervisor_id,
            supervisor_name=sup.user.full_name,
            hostel_id=hostel.id,
            hostel_name=hostel_name,
            metrics=metrics,
            tasks=tasks,
            recent_complaints=recent_complaints,
            recent_maintenance=recent_maintenance,
            pending_leaves=pending_leaves_items,
            today_schedule=today_schedule,
            alerts=alerts,
            last_login=last_login,
            actions_today=actions_today,
        )