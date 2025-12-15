# app/services/analytics/attendance_analytics_service.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, List, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import AttendanceRepository
from app.schemas.attendance.attendance_report import (
    AttendanceReport,
    AttendanceSummary,
    DailyAttendanceRecord,
    TrendAnalysis,
    WeeklyAttendance,
    MonthlyComparison,
)
from app.schemas.common.enums import AttendanceStatus
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork


class AttendanceAnalyticsService:
    """
    Attendance analytics from svc_attendance:

    - Student-level attendance report (summary + daily + trend)
    - Can be extended later for hostel-level analytics
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> AttendanceRepository:
        return uow.get_repo(AttendanceRepository)

    def _today(self) -> date:
        return date.today()

    # ------------------------------------------------------------------ #
    # Student-level report
    # ------------------------------------------------------------------ #
    def get_student_report(
        self,
        student_id: UUID,
        period: DateRangeFilter,
    ) -> AttendanceReport:
        """
        Build an AttendanceReport for a single student over a period.

        If period.start_date / end_date are omitted, defaults to last 30 days.
        """
        # Determine period bounds
        end = period.end_date or self._today()
        start = period.start_date or (end - timedelta(days=29))
        if start > end:
            start, end = end, start

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            records = repo.list_for_student_range(student_id, start_date=start, end_date=end)

        # Index by date for easy lookup
        by_date: Dict[date, List] = {}
        for r in records:
            by_date.setdefault(r.attendance_date, []).append(r)

        total_days = (end - start).days + 1
        total_present = total_absent = total_late = total_on_leave = total_half_day = 0

        daily_records: List[DailyAttendanceRecord] = []

        cur = start
        while cur <= end:
            recs = by_date.get(cur, [])
            # If multiple records exist for same day (edge cases), pick the one
            # with latest check_in_time; otherwise the first.
            rec = None
            if recs:
                rec = sorted(
                    recs,
                    key=lambda x: (x.check_in_time or datetime.min.time()),
                    reverse=True,
                )[0]

            if rec is None:
                # No record; treat as ABSENT (or leave as None if you prefer)
                status_str = AttendanceStatus.ABSENT.value
                status_enum = AttendanceStatus.ABSENT
                is_late = False
                late_minutes = None
                notes = None
                check_in = None
                check_out = None
            else:
                status_enum = rec.status
                status_str = status_enum.value if hasattr(status_enum, "value") else str(status_enum)
                is_late = rec.is_late
                late_minutes = rec.late_minutes
                notes = rec.notes
                check_in = rec.check_in_time
                check_out = rec.check_out_time

            if status_enum == AttendanceStatus.PRESENT:
                total_present += 1
            elif status_enum == AttendanceStatus.ABSENT:
                total_absent += 1
            elif status_enum == AttendanceStatus.LATE:
                total_late += 1
            elif status_enum == AttendanceStatus.ON_LEAVE:
                total_on_leave += 1
            elif status_enum == AttendanceStatus.HALF_DAY:
                total_half_day += 1

            daily_records.append(
                DailyAttendanceRecord(
                    date=cur,
                    day_of_week=cur.strftime("%A"),
                    status=status_str,
                    check_in_time=check_in,
                    check_out_time=check_out,
                    is_late=is_late,
                    late_minutes=late_minutes,
                    notes=notes,
                )
            )
            cur += timedelta(days=1)

        attendance_percentage = (
            (Decimal(str(total_present + total_half_day * 0.5)) / Decimal(str(total_days)) * 100)
            if total_days > 0
            else Decimal("0")
        )
        late_percentage = (
            (Decimal(str(total_late)) / Decimal(str(total_days)) * 100)
            if total_days > 0
            else Decimal("0")
        )

        # Streaks (simple forward pass using daily_records)
        current_present_streak = 0
        longest_present_streak = 0
        current_absent_streak = 0

        for day in daily_records:
            if day.status in (
                AttendanceStatus.PRESENT.value,
                AttendanceStatus.LATE.value,
                AttendanceStatus.HALF_DAY.value,
            ):
                current_present_streak += 1
                longest_present_streak = max(longest_present_streak, current_present_streak)
                current_absent_streak = 0
            elif day.status == AttendanceStatus.ABSENT.value:
                current_absent_streak += 1
                current_present_streak = 0
            else:
                current_present_streak = 0
                current_absent_streak = 0

        # Attendance status classification
        if attendance_percentage >= Decimal("90"):
            status_label = "excellent"
        elif attendance_percentage >= Decimal("75"):
            status_label = "good"
        elif attendance_percentage >= Decimal("60"):
            status_label = "warning"
        else:
            status_label = "critical"

        summary = AttendanceSummary(
            total_days=total_days,
            total_present=total_present,
            total_absent=total_absent,
            total_late=total_late,
            total_on_leave=total_on_leave,
            total_half_day=total_half_day,
            attendance_percentage=attendance_percentage,
            late_percentage=late_percentage,
            current_present_streak=current_present_streak,
            longest_present_streak=longest_present_streak,
            current_absent_streak=current_absent_streak,
            attendance_status=status_label,
            meets_minimum_requirement=attendance_percentage >= Decimal("75"),
        )

        trend = self._build_trend_analysis(start, end, daily_records)

        return AttendanceReport(
            hostel_id=None,
            student_id=student_id,
            report_period=DateRangeFilter(start_date=start, end_date=end),
            generated_at=datetime.utcnow(),
            summary=summary,
            daily_records=daily_records,
            trend_analysis=trend,
        )

    # ------------------------------------------------------------------ #
    # Trend helpers
    # ------------------------------------------------------------------ #
    def _build_trend_analysis(
        self,
        start: date,
        end: date,
        daily_records: List[DailyAttendanceRecord],
    ) -> TrendAnalysis:
        # Weekly rollup
        weekly_map: Dict[int, Dict[str, int]] = {}
        for rec in daily_records:
            week_num = rec.date.isocalendar()[1]
            bucket = weekly_map.setdefault(
                week_num,
                {"start": rec.date, "end": rec.date, "present": 0, "absent": 0, "total": 0},
            )
            bucket["start"] = min(bucket["start"], rec.date)
            bucket["end"] = max(bucket["end"], rec.date)
            bucket["total"] += 1
            if rec.status in (
                AttendanceStatus.PRESENT.value,
                AttendanceStatus.LATE.value,
                AttendanceStatus.HALF_DAY.value,
            ):
                bucket["present"] += 1
            elif rec.status == AttendanceStatus.ABSENT.value:
                bucket["absent"] += 1

        weekly_attendance: List[WeeklyAttendance] = []
        for week, vals in sorted(weekly_map.items(), key=lambda kv: kv[0]):
            total = vals["total"] or 1
            pct = (Decimal(str(vals["present"])) / Decimal(str(total)) * 100)
            weekly_attendance.append(
                WeeklyAttendance(
                    week_number=week,
                    week_start_date=vals["start"],
                    week_end_date=vals["end"],
                    total_days=vals["total"],
                    present_days=vals["present"],
                    absent_days=vals["absent"],
                    attendance_percentage=pct,
                )
            )

        # Monthly comparison (simple: group by YYYY-MM)
        monthly_map: Dict[str, Dict[str, int]] = {}
        for rec in daily_records:
            key = rec.date.strftime("%Y-%m")
            bucket = monthly_map.setdefault(key, {"present": 0, "absent": 0, "total": 0})
            bucket["total"] += 1
            if rec.status in (
                AttendanceStatus.PRESENT.value,
                AttendanceStatus.LATE.value,
                AttendanceStatus.HALF_DAY.value,
            ):
                bucket["present"] += 1
            elif rec.status == AttendanceStatus.ABSENT.value:
                bucket["absent"] += 1

        monthly_comparison: List[MonthlyComparison] = []
        for month, vals in sorted(monthly_map.items()):
            total = vals["total"] or 1
            pct = Decimal(str(vals["present"])) / Decimal(str(total)) * 100
            monthly_comparison.append(
                MonthlyComparison(
                    month=month,
                    attendance_percentage=pct,
                    total_present=vals["present"],
                    total_absent=vals["absent"],
                )
            )

        # Simple trend direction based on first vs last month
        trend_direction = "stable"
        improvement_rate: Optional[Decimal] = None
        if len(monthly_comparison) >= 2:
            first = monthly_comparison[0].attendance_percentage
            last = monthly_comparison[-1].attendance_percentage
            if first > 0:
                change = (last - first) / first * 100
                improvement_rate = change
                if change > Decimal("5"):
                    trend_direction = "attendance_improving"
                elif change < Decimal("-5"):
                    trend_direction = "attendance_declining"
                else:
                    trend_direction = "attendance_stable"
            else:
                trend_direction = "attendance_stable"

        # Map into expected pattern (improving|declining|stable)
        mapped_trend = "stable"
        if trend_direction == "attendance_improving":
            mapped_trend = "improving"
        elif trend_direction == "attendance_declining":
            mapped_trend = "declining"

        return TrendAnalysis(
            period_start=start,
            period_end=end,
            weekly_attendance=weekly_attendance,
            monthly_comparison=monthly_comparison or None,
            most_absent_day=None,
            attendance_improving=(mapped_trend == "improving"),
            improvement_rate=improvement_rate,
        )