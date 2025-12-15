# app/services/student/student_dashboard_service.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import (
    StudentRepository,
    HostelRepository,
    RoomRepository,
    BedRepository,
)
from app.repositories.transactions import PaymentRepository
from app.repositories.services import ComplaintRepository, LeaveApplicationRepository
from app.repositories.content import AnnouncementRepository, MessMenuRepository
from app.schemas.common.enums import LeaveStatus
from app.schemas.common.filters import DateRangeFilter
from app.schemas.student.student_dashboard import (
    StudentDashboard,
    StudentStats,
    StudentFinancialSummary,
    RecentPayment,
    RecentComplaint,
    PendingLeave,
    RecentAnnouncement,
    TodayMessMenu,
)
from app.services.analytics.attendance_analytics_service import AttendanceAnalyticsService
from app.services.common import UnitOfWork, errors


class StudentDashboardService:
    """
    Aggregated student dashboard:

    - Basic hostel/room/bed info
    - Financial summary (payments)
    - Attendance summary via AttendanceAnalyticsService
    - Recent payments/complaints/leaves/announcements
    - Today's mess menu
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._attendance_analytics = AttendanceAnalyticsService(session_factory)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_complaint_repo(self, uow: UnitOfWork) -> ComplaintRepository:
        return uow.get_repo(ComplaintRepository)

    def _get_leave_repo(self, uow: UnitOfWork) -> LeaveApplicationRepository:
        return uow.get_repo(LeaveApplicationRepository)

    def _get_announcement_repo(self, uow: UnitOfWork) -> AnnouncementRepository:
        return uow.get_repo(AnnouncementRepository)

    def _get_menu_repo(self, uow: UnitOfWork) -> MessMenuRepository:
        return uow.get_repo(MessMenuRepository)

    def _today(self) -> date:
        return date.today()

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_dashboard(self, student_id: UUID) -> StudentDashboard:
        today = self._today()

        with UnitOfWork(self._session_factory) as uow:
            student_repo = self._get_student_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)
            payment_repo = self._get_payment_repo(uow)
            complaint_repo = self._get_complaint_repo(uow)
            leave_repo = self._get_leave_repo(uow)
            announcement_repo = self._get_announcement_repo(uow)
            menu_repo = self._get_menu_repo(uow)

            s = student_repo.get(student_id)
            if s is None or not getattr(s, "user", None):
                raise errors.NotFoundError(f"Student {student_id} not found")

            user = s.user
            hostel = hostel_repo.get(s.hostel_id)
            hostel_name = hostel.name if hostel else ""

            room_number = bed_number = ""
            if s.room_id:
                room = room_repo.get(s.room_id)
                room_number = room.room_number if room else ""
            if s.bed_id:
                bed = bed_repo.get(s.bed_id)
                bed_number = bed.bed_number if bed else ""

            # Financial summary
            payments = payment_repo.list_for_student(s.id)
            (
                fin_summary,
                recent_payments,
            ) = self._build_financial_summary_and_recent(payments, s)

            # Attendance summary via analytics service
            period = DateRangeFilter(
                start_date=today.replace(day=1),
                end_date=today,
            )
            attendance_report = self._attendance_analytics.get_student_report(
                student_id, period
            )
            att_summary = attendance_report.summary

            # Recent complaints
            complaints = complaint_repo.list_for_student(s.id)[:5]
            recent_complaints: List[RecentComplaint] = []
            for c in complaints:
                recent_complaints.append(
                    RecentComplaint(
                        complaint_id=c.id,
                        title=c.title,
                        category=c.category.value if hasattr(c.category, "value") else str(c.category),
                        status=c.status.value if hasattr(c.status, "value") else str(c.status),
                        priority=c.priority.value if hasattr(c.priority, "value") else str(c.priority),
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                    )
                )

            # Pending leaves
            leaves_all = leave_repo.list_for_student(s.id)
            pending_leaves = [
                l for l in leaves_all if l.status == LeaveStatus.PENDING
            ]
            pending_leave_items: List[PendingLeave] = []
            for l in pending_leaves:
                pending_leave_items.append(
                    PendingLeave(
                        leave_id=l.id,
                        leave_type=l.leave_type.value if hasattr(l.leave_type, "value") else str(l.leave_type),
                        from_date=l.from_date,
                        to_date=l.to_date,
                        total_days=l.total_days,
                        status=l.status.value if hasattr(l.status, "value") else str(l.status),
                        applied_at=l.created_at,
                    )
                )

            # Announcements (recent, hostel-level)
            ann_list = announcement_repo.list_published_for_hostel(
                hostel_id=s.hostel_id,
                now=self._now(),
                audience=None,
            )[:5]
            recent_anns: List[RecentAnnouncement] = []
            for a in ann_list:
                recent_anns.append(
                    RecentAnnouncement(
                        announcement_id=a.id,
                        title=a.title,
                        category=a.category.value if hasattr(a.category, "value") else str(a.category),
                        priority=a.priority.value if hasattr(a.priority, "value") else str(a.priority),
                        published_at=a.published_at or a.created_at,
                        is_read=False,
                    )
                )

            # Today's mess menu
            today_menu = None
            menus_today = menu_repo.get_for_date(s.hostel_id, today)
            if menus_today:
                m = menus_today[0]
                today_menu = TodayMessMenu(
                    date=m.menu_date,
                    breakfast=m.breakfast_items or [],
                    lunch=m.lunch_items or [],
                    snacks=m.snacks_items or [],
                    dinner=m.dinner_items or [],
                    is_special=m.is_special_menu,
                )

            # Student stats (simple)
            stats = StudentStats(
                days_in_hostel=(
                    (today - s.check_in_date).days
                    if s.check_in_date
                    else 0
                ),
                total_payments_made=len(
                    [p for p in payments if p.paid_at]
                ),
                total_amount_paid=sum(
                    (p.amount for p in payments if p.paid_at), Decimal("0")
                ),
                complaints_raised=len(complaints),
                complaints_resolved=len(
                    [c for c in complaints if str(c.status).lower().endswith("closed") or str(c.status).lower() == "resolved"]  # type: ignore[str-bytes-safe]
                ),
                current_attendance_percentage=att_summary.attendance_percentage,
            )

        attendance_summary = attendance_report.summary

        return StudentDashboard(
            student_id=s.id,
            student_name=user.full_name,
            hostel_name=hostel_name,
            room_number=room_number,
            bed_number=bed_number,
            financial_summary=fin_summary,
            attendance_summary=attendance_summary,
            recent_payments=recent_payments,
            recent_complaints=recent_complaints,
            pending_leave_applications=pending_leave_items,
            recent_announcements=recent_anns,
            today_mess_menu=today_menu,
            stats=stats,
        )

    # ------------------------------------------------------------------ #
    # Helpers (financial)
    # ------------------------------------------------------------------ #
    def _build_financial_summary_and_recent(
        self,
        payments,
        student,
    ) -> tuple[StudentFinancialSummary, List[RecentPayment]]:
        today = self._today()

        amount_due = Decimal("0")
        amount_overdue = Decimal("0")
        next_due_date: Optional[date] = None

        for p in payments:
            if p.payment_status.name == "PENDING":  # PaymentStatus.PENDING
                amount_due += p.amount
                if p.due_date and p.due_date < today:
                    amount_overdue += p.amount
                if p.due_date:
                    if not next_due_date or p.due_date < next_due_date:
                        next_due_date = p.due_date

        days_until_due = (
            (next_due_date - today).days if next_due_date else None
        )

        payment_status_str = "current"
        if amount_overdue > 0:
            payment_status_str = "overdue"
        elif amount_due > 0:
            payment_status_str = "due_soon"

        # Mess details are placeholders; not modeled in payments yet.
        fin_summary = StudentFinancialSummary(
            monthly_rent=student.monthly_rent_amount or Decimal("0"),
            next_due_date=next_due_date or today,
            amount_due=amount_due,
            amount_overdue=amount_overdue,
            advance_balance=Decimal("0"),
            security_deposit=student.security_deposit_amount or Decimal("0"),
            mess_charges=Decimal("0"),
            mess_balance=Decimal("0"),
            payment_status=payment_status_str,
            days_until_due=days_until_due,
        )

        # Recent payments
        recent_payments: List[RecentPayment] = []
        for p in sorted(payments, key=lambda x: x.paid_at or x.created_at, reverse=True)[:5]:
            recent_payments.append(
                RecentPayment(
                    payment_id=p.id,
                    amount=p.amount,
                    payment_type=p.payment_type.value if hasattr(p.payment_type, "value") else str(p.payment_type),
                    payment_date=(p.paid_at or p.created_at).date(),
                    status=p.payment_status.value if hasattr(p.payment_status, "value") else str(p.payment_status),
                    receipt_url=p.receipt_url,
                )
            )

        return fin_summary, recent_payments