# app/services/attendance/attendance_policy_service.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, List, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository, StudentRepository
from app.schemas.attendance.attendance_policy import (
    AttendancePolicy,
    PolicyConfig,
    PolicyUpdate,
    PolicyViolation,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.analytics.attendance_analytics_service import AttendanceAnalyticsService
from app.services.common import UnitOfWork, errors


class PolicyStore(Protocol):
    """
    Abstract storage for attendance policy per hostel.
    """

    def get_policy(self, hostel_id: UUID) -> Optional[dict]: ...
    def save_policy(self, hostel_id: UUID, data: dict) -> None: ...


class AttendancePolicyService:
    """
    Attendance policy management:

    - Get/update AttendancePolicy for a hostel
    - Evaluate simple policy violations for a student over a period
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: PolicyStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store
        self._analytics = AttendanceAnalyticsService(session_factory)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Policy CRUD
    # ------------------------------------------------------------------ #
    def get_policy(self, hostel_id: UUID) -> AttendancePolicy:
        """
        Fetch policy for a hostel, creating a default if none exists.
        """
        record = self._store.get_policy(hostel_id)
        if record:
            return AttendancePolicy.model_validate(record)

        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")
            hostel_name = hostel.name

        now = self._now()
        policy = AttendancePolicy(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            minimum_attendance_percentage=Decimal("75.0"),
            late_entry_threshold_minutes=15,
            grace_days_per_month=3,
            consecutive_absence_alert_days=3,
            notify_guardian_on_absence=True,
            notify_admin_on_low_attendance=True,
            low_attendance_threshold=Decimal("75.0"),
            auto_mark_absent_after_time=None,
            is_active=True,
        )
        self._store.save_policy(hostel_id, policy.model_dump())
        return policy

    def update_policy(self, hostel_id: UUID, data: PolicyUpdate) -> AttendancePolicy:
        """
        Update fields on AttendancePolicy.
        """
        policy = self.get_policy(hostel_id)
        mapping = data.model_dump(exclude_unset=True)
        for field, value in mapping.items():
            if hasattr(policy, field):
                setattr(policy, field, value)
        policy.updated_at = self._now()
        self._store.save_policy(hostel_id, policy.model_dump())
        return policy

    # ------------------------------------------------------------------ #
    # Violations
    # ------------------------------------------------------------------ #
    def evaluate_violations_for_student(
        self,
        hostel_id: UUID,
        student_id: UUID,
        period: DateRangeFilter,
    ) -> List[PolicyViolation]:
        """
        Evaluate basic policy violations:

        - low_attendance
        - consecutive_absences
        - excessive_late_entries
        """
        if not (period.start_date and period.end_date):
            raise errors.ValidationError(
                "Both start_date and end_date are required to evaluate violations"
            )

        policy = self.get_policy(hostel_id)

        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            student = student_repo.get(student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(f"Student {student_id} not found")
            student_name = student.user.full_name

        # Use analytics service for detailed record
        report = self._analytics.get_student_report(student_id, period)
        summary = report.summary
        daily_records = report.daily_records

        violations: List[PolicyViolation] = []
        violation_date = period.end_date

        # Low attendance
        if summary.attendance_percentage < policy.minimum_attendance_percentage:
            violations.append(
                PolicyViolation(
                    student_id=student_id,
                    student_name=student_name,
                    hostel_id=hostel_id,
                    violation_type="low_attendance",
                    current_attendance_percentage=summary.attendance_percentage,
                    consecutive_absences=None,
                    late_entries_this_month=None,
                    violation_date=violation_date,
                    guardian_notified=False,
                    admin_notified=False,
                    warning_issued=False,
                    notes=None,
                )
            )

        # Consecutive absences
        max_streak = 0
        current = 0
        for rec in sorted(daily_records, key=lambda r: r.date):
            status_str = (rec.status or "").upper()
            if status_str == AttendanceStatus.ABSENT.value:
                current += 1
                if current > max_streak:
                    max_streak = current
            else:
                current = 0

        if max_streak >= policy.consecutive_absence_alert_days:
            violations.append(
                PolicyViolation(
                    student_id=student_id,
                    student_name=student_name,
                    hostel_id=hostel_id,
                    violation_type="consecutive_absences",
                    current_attendance_percentage=summary.attendance_percentage,
                    consecutive_absences=max_streak,
                    late_entries_this_month=None,
                    violation_date=violation_date,
                    guardian_notified=False,
                    admin_notified=False,
                    warning_issued=False,
                    notes=None,
                )
            )

        # Excessive late entries (beyond grace days)
        late_days = summary.total_late
        if late_days > policy.grace_days_per_month:
            violations.append(
                PolicyViolation(
                    student_id=student_id,
                    student_name=student_name,
                    hostel_id=hostel_id,
                    violation_type="excessive_late_entries",
                    current_attendance_percentage=summary.attendance_percentage,
                    consecutive_absences=None,
                    late_entries_this_month=late_days,
                    violation_date=violation_date,
                    guardian_notified=False,
                    admin_notified=False,
                    warning_issued=False,
                    notes=None,
                )
            )

        return violations