# app/services/attendance/attendance_report_service.py
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository, StudentRepository, RoomRepository
from app.schemas.attendance.attendance_report import (
    AttendanceReport,
    MonthlyReport,
    StudentMonthlySummary,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.analytics.attendance_analytics_service import AttendanceAnalyticsService
from app.services.common import UnitOfWork, errors


class AttendanceReportService:
    """
    Higher-level attendance reporting facade:

    - Student-level report (delegates to AttendanceAnalyticsService)
    - Monthly hostel report (StudentMonthlySummary)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._analytics = AttendanceAnalyticsService(session_factory)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    # ------------------------------------------------------------------ #
    # Student report
    # ------------------------------------------------------------------ #
    def get_student_report(
        self,
        student_id: UUID,
        period: DateRangeFilter,
    ) -> AttendanceReport:
        return self._analytics.get_student_report(student_id, period)

    # ------------------------------------------------------------------ #
    # Monthly hostel report
    # ------------------------------------------------------------------ #
    def get_monthly_report(self, hostel_id: UUID, month: str) -> MonthlyReport:
        """
        Build a MonthlyReport (per-hostel) for given YYYY-MM.

        Uses AttendanceAnalyticsService per student under that hostel.
        """
        try:
            year, m = map(int, month.split("-"))
        except ValueError:
            raise errors.ValidationError("month must be in 'YYYY-MM' format")

        start = date(year, m, 1)
        end = date(year, m, monthrange(year, m)[1])
        period = DateRangeFilter(start_date=start, end_date=end)

        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            room_repo = self._get_room_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            students = student_repo.list_for_hostel(hostel_id, status=None)

            room_cache: dict[UUID, str] = {}
            summaries: List[StudentMonthlySummary] = []
            total_pct = Decimal("0")
            meets_count = 0

            for st in students:
                rep = self._analytics.get_student_report(st.id, period)
                s = rep.summary

                if st.room_id and st.room_id not in room_cache:
                    r = room_repo.get(st.room_id)
                    room_cache[st.room_id] = r.room_number if r else ""

                room_number = (
                    room_cache[st.room_id]
                    if getattr(st, "room_id", None) in room_cache
                    else None
                )
                student_name = st.user.full_name if getattr(st, "user", None) else ""

                summaries.append(
                    StudentMonthlySummary(
                        student_id=st.id,
                        student_name=student_name,
                        room_number=room_number,
                        total_days=s.total_days,
                        present_days=s.total_present,
                        absent_days=s.total_absent,
                        late_days=s.total_late,
                        on_leave_days=s.total_on_leave,
                        attendance_percentage=s.attendance_percentage,
                        meets_requirement=s.meets_minimum_requirement,
                        requires_attention=not s.meets_minimum_requirement,
                        action_required=(
                            "Discuss with student/guardian"
                            if not s.meets_minimum_requirement
                            else None
                        ),
                    )
                )

                total_pct += s.attendance_percentage
                if s.meets_minimum_requirement:
                    meets_count += 1

            total_students = len(students)
            hostel_avg = (
                total_pct / Decimal(str(total_students))
                if total_students > 0
                else Decimal("0")
            )
            below_req = total_students - meets_count

            return MonthlyReport(
                hostel_id=hostel_id,
                month=month,
                student_summaries=summaries,
                hostel_average_attendance=hostel_avg,
                total_students=total_students,
                students_meeting_requirement=meets_count,
                students_below_requirement=below_req,
            )