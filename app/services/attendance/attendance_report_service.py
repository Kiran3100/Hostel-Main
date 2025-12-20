# --- File: app/services/attendance/attendance_report_service.py ---
"""
Attendance report service with generation and caching.

Provides report generation, summary management, trend analysis,
and comprehensive analytics with intelligent caching.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import hashlib
import json

from sqlalchemy.orm import Session

from app.models.attendance.attendance_report import (
    AttendanceReport,
    AttendanceSummary,
    AttendanceTrend,
)
from app.models.base.enums import AttendanceStatus
from app.repositories.attendance.attendance_report_repository import (
    AttendanceReportRepository,
)
from app.repositories.attendance.attendance_record_repository import (
    AttendanceRecordRepository,
)
from app.repositories.attendance.attendance_policy_repository import (
    AttendancePolicyRepository,
)
from app.core.exceptions import ValidationError, NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AttendanceReportService:
    """
    Service for attendance report generation and management.
    """

    def __init__(self, session: Session):
        """
        Initialize service with database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.report_repo = AttendanceReportRepository(session)
        self.attendance_repo = AttendanceRecordRepository(session)
        self.policy_repo = AttendancePolicyRepository(session)

    # ==================== Report Generation ====================

    def generate_student_report(
        self,
        student_id: UUID,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
        generated_by: UUID,
        report_format: str = "json",
        use_cache: bool = True,
    ) -> AttendanceReport:
        """
        Generate comprehensive attendance report for student.

        Args:
            student_id: Student identifier
            hostel_id: Hostel identifier
            period_start: Report period start
            period_end: Report period end
            generated_by: User generating report
            report_format: Report format
            use_cache: Use cached report if available

        Returns:
            Generated or cached report

        Raises:
            ValidationError: If validation fails
        """
        try:
            if period_end < period_start:
                raise ValidationError("period_end must be >= period_start")

            # Generate cache key
            cache_key = self._generate_cache_key(
                report_type="student",
                student_id=student_id,
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
            )

            # Check cache
            if use_cache:
                cached = self.report_repo.get_by_cache_key(cache_key)
                if cached:
                    logger.info(f"Using cached report: {cache_key}")
                    return cached

            # Generate report data
            start_time = datetime.utcnow()

            summary_data = self._generate_student_summary(
                student_id=student_id,
                period_start=period_start,
                period_end=period_end,
            )

            detailed_data = self._generate_student_details(
                student_id=student_id,
                period_start=period_start,
                period_end=period_end,
            )

            analytics_data = self._generate_student_analytics(
                student_id=student_id,
                period_start=period_start,
                period_end=period_end,
            )

            generation_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Create report
            report = self.report_repo.create_report(
                hostel_id=hostel_id,
                student_id=student_id,
                generated_by=generated_by,
                report_type="student_attendance",
                report_title=f"Student Attendance Report - {period_start} to {period_end}",
                period_start=period_start,
                period_end=period_end,
                summary_data=summary_data,
                detailed_data=detailed_data,
                analytics_data=analytics_data,
                report_format=report_format,
                is_cached=True,
                cache_key=cache_key,
                cache_expires_at=datetime.utcnow() + timedelta(hours=24),
            )

            # Update generation time
            self.report_repo.update_report_generation_time(
                report_id=report.id,
                generation_time_ms=generation_time,
            )

            self.session.commit()
            logger.info(f"Student report generated in {generation_time}ms")

            return report

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error generating student report: {str(e)}")
            raise

    def generate_hostel_report(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
        generated_by: UUID,
        report_format: str = "json",
        use_cache: bool = True,
    ) -> AttendanceReport:
        """
        Generate comprehensive attendance report for hostel.

        Args:
            hostel_id: Hostel identifier
            period_start: Report period start
            period_end: Report period end
            generated_by: User generating report
            report_format: Report format
            use_cache: Use cached report if available

        Returns:
            Generated or cached report
        """
        try:
            if period_end < period_start:
                raise ValidationError("period_end must be >= period_start")

            # Generate cache key
            cache_key = self._generate_cache_key(
                report_type="hostel",
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
            )

            # Check cache
            if use_cache:
                cached = self.report_repo.get_by_cache_key(cache_key)
                if cached:
                    logger.info(f"Using cached report: {cache_key}")
                    return cached

            # Generate report data
            start_time = datetime.utcnow()

            summary_data = self._generate_hostel_summary(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
            )

            detailed_data = self._generate_hostel_details(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
            )

            analytics_data = self._generate_hostel_analytics(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
            )

            generation_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Create report
            report = self.report_repo.create_report(
                hostel_id=hostel_id,
                student_id=None,
                generated_by=generated_by,
                report_type="hostel_attendance",
                report_title=f"Hostel Attendance Report - {period_start} to {period_end}",
                period_start=period_start,
                period_end=period_end,
                summary_data=summary_data,
                detailed_data=detailed_data,
                analytics_data=analytics_data,
                report_format=report_format,
                is_cached=True,
                cache_key=cache_key,
                cache_expires_at=datetime.utcnow() + timedelta(hours=12),
            )

            # Update generation time
            self.report_repo.update_report_generation_time(
                report_id=report.id,
                generation_time_ms=generation_time,
            )

            self.session.commit()
            logger.info(f"Hostel report generated in {generation_time}ms")

            return report

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error generating hostel report: {str(e)}")
            raise

    def generate_comparative_report(
        self,
        hostel_id: UUID,
        current_period_start: date,
        current_period_end: date,
        previous_period_start: date,
        previous_period_end: date,
        generated_by: UUID,
    ) -> AttendanceReport:
        """
        Generate comparative attendance report for two periods.

        Args:
            hostel_id: Hostel identifier
            current_period_start: Current period start
            current_period_end: Current period end
            previous_period_start: Previous period start
            previous_period_end: Previous period end
            generated_by: User generating report

        Returns:
            Generated comparative report
        """
        try:
            # Get data for both periods
            current_summary = self._generate_hostel_summary(
                hostel_id=hostel_id,
                period_start=current_period_start,
                period_end=current_period_end,
            )

            previous_summary = self._generate_hostel_summary(
                hostel_id=hostel_id,
                period_start=previous_period_start,
                period_end=previous_period_end,
            )

            # Calculate comparisons
            comparison_data = self._calculate_period_comparison(
                current_summary=current_summary,
                previous_summary=previous_summary,
            )

            # Create combined summary
            summary_data = {
                "current_period": {
                    "start": current_period_start.isoformat(),
                    "end": current_period_end.isoformat(),
                    **current_summary,
                },
                "previous_period": {
                    "start": previous_period_start.isoformat(),
                    "end": previous_period_end.isoformat(),
                    **previous_summary,
                },
                "comparison": comparison_data,
            }

            # Create report
            report = self.report_repo.create_report(
                hostel_id=hostel_id,
                student_id=None,
                generated_by=generated_by,
                report_type="comparative_attendance",
                report_title=f"Comparative Attendance Report",
                period_start=previous_period_start,
                period_end=current_period_end,
                summary_data=summary_data,
                report_format="json",
                is_cached=False,  # Don't cache comparative reports
            )

            self.session.commit()
            logger.info("Comparative report generated")

            return report

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error generating comparative report: {str(e)}")
            raise

    # ==================== Summary Management ====================

    def create_or_update_summary(
        self,
        student_id: UUID,
        hostel_id: UUID,
        period_type: str,
        period_start: date,
        period_end: date,
        force_recalculate: bool = False,
    ) -> AttendanceSummary:
        """
        Create or update attendance summary for student.

        Args:
            student_id: Student identifier
            hostel_id: Hostel identifier
            period_type: Period type
            period_start: Period start date
            period_end: Period end date
            force_recalculate: Force recalculation even if exists

        Returns:
            Created or updated summary
        """
        try:
            # Check for existing summary
            existing = self.report_repo.get_student_summary(
                student_id=student_id,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
            )

            # Calculate metrics
            metrics = self._calculate_summary_metrics(
                student_id=student_id,
                period_start=period_start,
                period_end=period_end,
            )

            if existing and not force_recalculate:
                # Update existing
                summary = self.report_repo.update_summary(
                    summary_id=existing.id,
                    **metrics,
                )
            else:
                # Create new
                summary = self.report_repo.create_summary(
                    student_id=student_id,
                    hostel_id=hostel_id,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    **metrics,
                )

            self.session.commit()
            logger.info(f"Summary created/updated for student {student_id}")

            return summary

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating/updating summary: {str(e)}")
            raise

    def generate_monthly_summaries(
        self,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> List[AttendanceSummary]:
        """
        Generate monthly summaries for all students in hostel.

        Args:
            hostel_id: Hostel identifier
            year: Year
            month: Month

        Returns:
            List of generated summaries
        """
        try:
            # Calculate period dates
            period_start = date(year, month, 1)
            if month == 12:
                period_end = date(year, 12, 31)
            else:
                next_month = date(year, month + 1, 1)
                period_end = next_month - timedelta(days=1)

            # Get all students (simplified - would need student repository)
            # For now, we'll get unique student IDs from attendance records
            records = self.attendance_repo.get_hostel_attendance_range(
                hostel_id=hostel_id,
                start_date=period_start,
                end_date=period_end,
            )[0]

            student_ids = list(set(r.student_id for r in records))

            # Generate summaries
            summaries = []
            for student_id in student_ids:
                summary = self.create_or_update_summary(
                    student_id=student_id,
                    hostel_id=hostel_id,
                    period_type="monthly",
                    period_start=period_start,
                    period_end=period_end,
                )
                summaries.append(summary)

            logger.info(f"Generated {len(summaries)} monthly summaries for {year}-{month}")

            return summaries

        except Exception as e:
            logger.error(f"Error generating monthly summaries: {str(e)}")
            raise

    def get_student_summaries(
        self,
        student_id: UUID,
        period_type: Optional[str] = None,
        limit: int = 12,
    ) -> List[AttendanceSummary]:
        """
        Get attendance summaries for student.

        Args:
            student_id: Student identifier
            period_type: Optional period type filter
            limit: Maximum number of summaries

        Returns:
            List of summaries
        """
        summaries = self.report_repo.get_student_summaries(
            student_id=student_id,
            period_type=period_type,
        )
        return summaries[:limit]

    def get_low_attendance_students(
        self,
        hostel_id: UUID,
        threshold_percentage: Decimal = Decimal("75.00"),
        period_type: str = "monthly",
    ) -> List[AttendanceSummary]:
        """
        Get students with low attendance.

        Args:
            hostel_id: Hostel identifier
            threshold_percentage: Threshold percentage
            period_type: Period type

        Returns:
            List of low attendance summaries
        """
        return self.report_repo.get_low_attendance_summaries(
            hostel_id=hostel_id,
            threshold_percentage=threshold_percentage,
            period_type=period_type,
        )

    # ==================== Trend Analysis ====================

    def create_or_update_trend(
        self,
        hostel_id: UUID,
        trend_type: str,
        period_identifier: str,
        period_start: date,
        period_end: date,
        student_id: Optional[UUID] = None,
    ) -> AttendanceTrend:
        """
        Create or update attendance trend.

        Args:
            hostel_id: Hostel identifier
            trend_type: Trend type
            period_identifier: Period identifier
            period_start: Period start date
            period_end: Period end date
            student_id: Optional student identifier

        Returns:
            Created or updated trend
        """
        try:
            # Check for existing trend
            existing = self.report_repo.get_trend_by_period(
                hostel_id=hostel_id,
                trend_type=trend_type,
                period_identifier=period_identifier,
                student_id=student_id,
            )

            # Calculate trend metrics
            metrics = self._calculate_trend_metrics(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                student_id=student_id,
            )

            if existing:
                # Update existing
                trend = self.report_repo.update_trend(
                    trend_id=existing.id,
                    **metrics,
                )
            else:
                # Create new
                trend = self.report_repo.create_trend(
                    hostel_id=hostel_id,
                    student_id=student_id,
                    trend_type=trend_type,
                    period_identifier=period_identifier,
                    period_start=period_start,
                    period_end=period_end,
                    **metrics,
                )

            self.session.commit()
            logger.info(f"Trend created/updated: {trend_type} - {period_identifier}")

            return trend

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating/updating trend: {str(e)}")
            raise

    def generate_monthly_trends(
        self,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> AttendanceTrend:
        """
        Generate monthly trend for hostel.

        Args:
            hostel_id: Hostel identifier
            year: Year
            month: Month

        Returns:
            Generated trend
        """
        try:
            # Calculate period
            period_start = date(year, month, 1)
            if month == 12:
                period_end = date(year, 12, 31)
            else:
                next_month = date(year, month + 1, 1)
                period_end = next_month - timedelta(days=1)

            period_identifier = f"{year}-{month:02d}"

            trend = self.create_or_update_trend(
                hostel_id=hostel_id,
                trend_type="monthly",
                period_identifier=period_identifier,
                period_start=period_start,
                period_end=period_end,
            )

            return trend

        except Exception as e:
            logger.error(f"Error generating monthly trend: {str(e)}")
            raise

    def get_hostel_trends(
        self,
        hostel_id: UUID,
        trend_type: str = "monthly",
        limit: int = 12,
    ) -> List[AttendanceTrend]:
        """
        Get attendance trends for hostel.

        Args:
            hostel_id: Hostel identifier
            trend_type: Trend type
            limit: Maximum number of trends

        Returns:
            List of trends
        """
        return self.report_repo.get_hostel_trends(
            hostel_id=hostel_id,
            trend_type=trend_type,
            limit=limit,
        )

    def detect_anomalies(
        self,
        hostel_id: UUID,
        trend_type: str = "monthly",
    ) -> List[AttendanceTrend]:
        """
        Detect anomalies in attendance trends.

        Args:
            hostel_id: Hostel identifier
            trend_type: Trend type

        Returns:
            List of anomalous trends
        """
        return self.report_repo.get_anomaly_trends(
            hostel_id=hostel_id,
            trend_type=trend_type,
        )

    # ==================== Analytics ====================

    def get_hostel_overview(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """
        Get comprehensive hostel attendance overview.

        Args:
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date

        Returns:
            Overview statistics
        """
        return self.report_repo.get_hostel_overview(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )

    def get_top_performers(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ) -> List[AttendanceSummary]:
        """
        Get top performing students.

        Args:
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date
            limit: Number of students

        Returns:
            List of top performers
        """
        return self.report_repo.get_top_performers(
            hostel_id=hostel_id,
            period_type="monthly",
            period_start=period_start,
            period_end=period_end,
            limit=limit,
        )

    def get_bottom_performers(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ) -> List[AttendanceSummary]:
        """
        Get bottom performing students.

        Args:
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date
            limit: Number of students

        Returns:
            List of bottom performers
        """
        return self.report_repo.get_bottom_performers(
            hostel_id=hostel_id,
            period_type="monthly",
            period_start=period_start,
            period_end=period_end,
            limit=limit,
        )

    # ==================== Cache Management ====================

    def invalidate_cache(
        self,
        hostel_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
    ) -> int:
        """
        Invalidate cached reports.

        Args:
            hostel_id: Optional hostel filter
            student_id: Optional student filter

        Returns:
            Number of reports invalidated
        """
        try:
            # This would require additional repository method
            # For now, delete expired cache
            count = self.report_repo.delete_expired_cache()
            self.session.commit()
            logger.info(f"Invalidated {count} cached reports")
            return count

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error invalidating cache: {str(e)}")
            raise

    def cleanup_old_reports(
        self,
        days_old: int = 90,
    ) -> int:
        """
        Clean up old reports.

        Args:
            days_old: Delete reports older than this

        Returns:
            Number of reports deleted
        """
        # This would require additional repository method
        return 0

    # ==================== Private Helper Methods ====================

    def _generate_cache_key(
        self,
        report_type: str,
        **params: Any,
    ) -> str:
        """Generate unique cache key for report."""
        # Sort params for consistent key generation
        sorted_params = sorted(params.items())
        key_string = f"{report_type}:" + ":".join(
            f"{k}={v}" for k, v in sorted_params
        )
        return hashlib.md5(key_string.encode()).hexdigest()

    def _generate_student_summary(
        self,
        student_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Generate summary data for student report."""
        summary = self.attendance_repo.get_attendance_summary(
            student_id=student_id,
            start_date=period_start,
            end_date=period_end,
        )
        return summary

    def _generate_student_details(
        self,
        student_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Generate detailed data for student report."""
        records = self.attendance_repo.get_student_attendance_range(
            student_id=student_id,
            start_date=period_start,
            end_date=period_end,
        )

        return {
            "records": [
                {
                    "date": r.attendance_date.isoformat(),
                    "status": r.status.value,
                    "is_late": r.is_late,
                    "late_minutes": r.late_minutes,
                    "check_in_time": r.check_in_time.isoformat() if r.check_in_time else None,
                    "check_out_time": r.check_out_time.isoformat() if r.check_out_time else None,
                }
                for r in records
            ]
        }

    def _generate_student_analytics(
        self,
        student_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Generate analytics data for student report."""
        # Get consecutive absences
        absences = self.attendance_repo.find_consecutive_absences(
            student_id=student_id,
            min_consecutive_days=2,
        )

        return {
            "consecutive_absence_streaks": [
                {
                    "start_date": streak[0].attendance_date.isoformat(),
                    "end_date": streak[-1].attendance_date.isoformat(),
                    "days": len(streak),
                }
                for streak in absences
            ],
        }

    def _generate_hostel_summary(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Generate summary data for hostel report."""
        # Get all records for period
        records, _ = self.attendance_repo.get_hostel_attendance_range(
            hostel_id=hostel_id,
            start_date=period_start,
            end_date=period_end,
        )

        total_records = len(records)
        if total_records == 0:
            return {
                "total_records": 0,
                "average_attendance": 0.0,
            }

        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        late_count = sum(1 for r in records if r.is_late)

        avg_attendance = (present_count / total_records) * 100

        return {
            "total_records": total_records,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "average_attendance": round(avg_attendance, 2),
        }

    def _generate_hostel_details(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Generate detailed data for hostel report."""
        # Daily breakdown
        daily_summaries = []
        current_date = period_start

        while current_date <= period_end:
            daily_summary = self.attendance_repo.get_hostel_daily_summary(
                hostel_id=hostel_id,
                attendance_date=current_date,
            )
            daily_summaries.append(daily_summary)
            current_date += timedelta(days=1)

        return {
            "daily_breakdown": daily_summaries,
        }

    def _generate_hostel_analytics(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Generate analytics data for hostel report."""
        late_stats = self.attendance_repo.get_late_entry_statistics(
            hostel_id=hostel_id,
            start_date=period_start,
            end_date=period_end,
        )

        return {
            "late_entry_statistics": late_stats,
        }

    def _calculate_summary_metrics(
        self,
        student_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Calculate metrics for summary."""
        summary = self.attendance_repo.get_attendance_summary(
            student_id=student_id,
            start_date=period_start,
            end_date=period_end,
        )

        # Determine status
        percentage = Decimal(str(summary["attendance_percentage"]))
        if percentage >= 95:
            status = "excellent"
        elif percentage >= 85:
            status = "good"
        elif percentage >= 75:
            status = "warning"
        else:
            status = "critical"

        # Check policy requirement
        meets_requirement = percentage >= Decimal("75.00")  # Default threshold

        return {
            "total_days": summary["total_days"],
            "total_present": summary["present_count"],
            "total_absent": summary["absent_count"],
            "total_late": summary["late_count"],
            "total_on_leave": summary["on_leave_count"],
            "total_half_day": summary["half_day_count"],
            "attendance_percentage": percentage,
            "late_percentage": Decimal(str(
                (summary["late_count"] / summary["total_days"] * 100)
                if summary["total_days"] > 0 else 0
            )),
            "current_present_streak": summary["current_streak"],
            "longest_present_streak": summary["longest_present_streak"],
            "current_absent_streak": 0,  # Would need to calculate
            "longest_absent_streak": summary["longest_absent_streak"],
            "attendance_status": status,
            "meets_minimum_requirement": meets_requirement,
        }

    def _calculate_trend_metrics(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
        student_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Calculate metrics for trend."""
        if student_id:
            # Student-specific trend
            summary = self.attendance_repo.get_attendance_summary(
                student_id=student_id,
                start_date=period_start,
                end_date=period_end,
            )
            avg_attendance = Decimal(str(summary["attendance_percentage"]))
        else:
            # Hostel-level trend
            hostel_summary = self._generate_hostel_summary(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
            )
            avg_attendance = Decimal(str(hostel_summary["average_attendance"]))

        # Determine trend direction (would compare with previous period)
        trend_direction = "stable"
        change_percentage = None

        return {
            "average_attendance": avg_attendance,
            "trend_direction": trend_direction,
            "change_percentage": change_percentage,
            "average_present": Decimal("0.00"),
            "average_absent": Decimal("0.00"),
            "average_late": Decimal("0.00"),
        }

    def _calculate_period_comparison(
        self,
        current_summary: Dict[str, Any],
        previous_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate comparison between two periods."""
        current_avg = current_summary.get("average_attendance", 0)
        previous_avg = previous_summary.get("average_attendance", 0)

        change = current_avg - previous_avg
        change_pct = (change / previous_avg * 100) if previous_avg > 0 else 0

        return {
            "attendance_change": round(change, 2),
            "attendance_change_percentage": round(change_pct, 2),
            "trend": "improving" if change > 0 else "declining" if change < 0 else "stable",
        }