# --- File: app/repositories/attendance/attendance_report_repository.py ---
"""
Attendance report repository with caching and analytics.

Provides report generation, caching, retrieval, and summary
operations for attendance analytics and reporting.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case, distinct
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.attendance.attendance_report import (
    AttendanceReport,
    AttendanceSummary,
    AttendanceTrend,
)
from app.models.base.enums import AttendanceStatus
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import ValidationError, NotFoundError


class AttendanceReportRepository(BaseRepository[AttendanceReport]):
    """
    Repository for attendance report operations with caching.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy database session
        """
        super().__init__(AttendanceReport, session)

    # ==================== Report CRUD Operations ====================

    def create_report(
        self,
        hostel_id: Optional[UUID],
        generated_by: UUID,
        report_type: str,
        report_title: str,
        period_start: date,
        period_end: date,
        summary_data: Dict[str, Any],
        student_id: Optional[UUID] = None,
        report_format: str = "json",
        detailed_data: Optional[Dict[str, Any]] = None,
        analytics_data: Optional[Dict[str, Any]] = None,
        is_cached: bool = True,
        cache_expires_at: Optional[datetime] = None,
        cache_key: Optional[str] = None,
        file_path: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
    ) -> AttendanceReport:
        """
        Create attendance report.

        Args:
            hostel_id: Optional hostel identifier
            generated_by: User who generated report
            report_type: Type of report
            report_title: Report title
            period_start: Report period start date
            period_end: Report period end date
            summary_data: Summary data as JSON
            student_id: Optional student identifier
            report_format: Report format (json, pdf, excel, csv)
            detailed_data: Detailed data as JSON
            analytics_data: Analytics data as JSON
            is_cached: Whether report is cached
            cache_expires_at: Cache expiration datetime
            cache_key: Unique cache key
            file_path: Path to generated file
            file_size_bytes: File size in bytes

        Returns:
            Created report

        Raises:
            ValidationError: If validation fails
        """
        if period_end < period_start:
            raise ValidationError("period_end must be >= period_start")

        valid_formats = ["json", "pdf", "excel", "csv", "html"]
        if report_format not in valid_formats:
            raise ValidationError(f"Invalid report format. Must be one of: {valid_formats}")

        # Set default cache expiration if caching enabled
        if is_cached and cache_expires_at is None:
            cache_expires_at = datetime.utcnow() + timedelta(hours=24)

        report = AttendanceReport(
            hostel_id=hostel_id,
            student_id=student_id,
            generated_by=generated_by,
            report_type=report_type,
            report_title=report_title,
            report_format=report_format,
            period_start=period_start,
            period_end=period_end,
            summary_data=summary_data,
            detailed_data=detailed_data,
            analytics_data=analytics_data,
            generated_at=datetime.utcnow(),
            is_cached=is_cached,
            cache_expires_at=cache_expires_at,
            cache_key=cache_key,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
        )

        self.session.add(report)
        self.session.flush()
        return report

    def get_by_id(
        self,
        report_id: UUID,
        increment_view_count: bool = True,
    ) -> Optional[AttendanceReport]:
        """
        Get report by ID.

        Args:
            report_id: Report identifier
            increment_view_count: Whether to increment view count

        Returns:
            Report if found
        """
        report = self.session.query(AttendanceReport).filter(
            AttendanceReport.id == report_id
        ).first()

        if report and increment_view_count:
            report.view_count += 1
            report.last_viewed_at = datetime.utcnow()
            self.session.flush()

        return report

    def get_by_cache_key(
        self,
        cache_key: str,
    ) -> Optional[AttendanceReport]:
        """
        Get report by cache key.

        Args:
            cache_key: Cache key

        Returns:
            Report if found and not expired
        """
        now = datetime.utcnow()
        
        return self.session.query(AttendanceReport).filter(
            and_(
                AttendanceReport.cache_key == cache_key,
                AttendanceReport.is_cached == True,
                or_(
                    AttendanceReport.cache_expires_at.is_(None),
                    AttendanceReport.cache_expires_at > now,
                ),
            )
        ).first()

    def get_reports(
        self,
        hostel_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        report_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AttendanceReport], int]:
        """
        Get reports with filters and pagination.

        Args:
            hostel_id: Optional hostel filter
            student_id: Optional student filter
            report_type: Optional report type filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            page: Page number
            page_size: Records per page

        Returns:
            Tuple of (reports, total_count)
        """
        query = self.session.query(AttendanceReport)

        if hostel_id:
            query = query.filter(AttendanceReport.hostel_id == hostel_id)
        if student_id:
            query = query.filter(AttendanceReport.student_id == student_id)
        if report_type:
            query = query.filter(AttendanceReport.report_type == report_type)
        if start_date:
            query = query.filter(AttendanceReport.generated_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(AttendanceReport.generated_at <= datetime.combine(end_date, datetime.max.time()))

        total_count = query.count()

        reports = query.order_by(
            AttendanceReport.generated_at.desc()
        ).limit(page_size).offset((page - 1) * page_size).all()

        return reports, total_count

    def delete_expired_cache(self) -> int:
        """
        Delete expired cached reports.

        Returns:
            Number of reports deleted
        """
        now = datetime.utcnow()

        count = self.session.query(AttendanceReport).filter(
            and_(
                AttendanceReport.is_cached == True,
                AttendanceReport.cache_expires_at.isnot(None),
                AttendanceReport.cache_expires_at <= now,
            )
        ).delete(synchronize_session=False)

        self.session.flush()
        return count

    def update_report_generation_time(
        self,
        report_id: UUID,
        generation_time_ms: int,
    ) -> AttendanceReport:
        """
        Update report generation time.

        Args:
            report_id: Report identifier
            generation_time_ms: Generation time in milliseconds

        Returns:
            Updated report

        Raises:
            NotFoundError: If report not found
        """
        report = self.get_by_id(report_id, increment_view_count=False)
        if not report:
            raise NotFoundError(f"Attendance report {report_id} not found")

        report.generation_time_ms = generation_time_ms
        self.session.flush()
        return report

    # ==================== Summary Operations ====================

    def create_summary(
        self,
        student_id: UUID,
        hostel_id: UUID,
        period_type: str,
        period_start: date,
        period_end: date,
        total_days: int,
        total_present: int,
        total_absent: int,
        total_late: int,
        total_on_leave: int,
        total_half_day: int,
        attendance_percentage: Decimal,
        late_percentage: Decimal,
        current_present_streak: int = 0,
        longest_present_streak: int = 0,
        current_absent_streak: int = 0,
        longest_absent_streak: int = 0,
        attendance_status: str = "good",
        meets_minimum_requirement: bool = True,
    ) -> AttendanceSummary:
        """
        Create attendance summary.

        Args:
            student_id: Student identifier
            hostel_id: Hostel identifier
            period_type: Period type (daily, weekly, monthly, quarterly, yearly)
            period_start: Period start date
            period_end: Period end date
            total_days: Total days in period
            total_present: Total present days
            total_absent: Total absent days
            total_late: Total late entries
            total_on_leave: Total leave days
            total_half_day: Total half days
            attendance_percentage: Attendance percentage
            late_percentage: Late percentage
            current_present_streak: Current present streak
            longest_present_streak: Longest present streak
            current_absent_streak: Current absent streak
            longest_absent_streak: Longest absent streak
            attendance_status: Status (excellent, good, warning, critical)
            meets_minimum_requirement: Meets minimum requirement flag

        Returns:
            Created summary

        Raises:
            ValidationError: If validation fails
        """
        if period_end < period_start:
            raise ValidationError("period_end must be >= period_start")

        valid_types = ["daily", "weekly", "monthly", "quarterly", "yearly", "custom"]
        if period_type not in valid_types:
            raise ValidationError(f"Invalid period type. Must be one of: {valid_types}")

        valid_statuses = ["excellent", "good", "warning", "critical"]
        if attendance_status not in valid_statuses:
            raise ValidationError(f"Invalid status. Must be one of: {valid_statuses}")

        summary = AttendanceSummary(
            student_id=student_id,
            hostel_id=hostel_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
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
            longest_absent_streak=longest_absent_streak,
            attendance_status=attendance_status,
            meets_minimum_requirement=meets_minimum_requirement,
            last_calculated_at=datetime.utcnow(),
        )

        self.session.add(summary)
        self.session.flush()
        return summary

    def get_summary_by_id(
        self,
        summary_id: UUID,
    ) -> Optional[AttendanceSummary]:
        """
        Get summary by ID.

        Args:
            summary_id: Summary identifier

        Returns:
            Summary if found
        """
        return self.session.query(AttendanceSummary).filter(
            AttendanceSummary.id == summary_id
        ).options(joinedload(AttendanceSummary.student)).first()

    def get_student_summary(
        self,
        student_id: UUID,
        period_type: str,
        period_start: date,
        period_end: date,
    ) -> Optional[AttendanceSummary]:
        """
        Get summary for student and period.

        Args:
            student_id: Student identifier
            period_type: Period type
            period_start: Period start date
            period_end: Period end date

        Returns:
            Summary if found
        """
        return self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.student_id == student_id,
                AttendanceSummary.period_type == period_type,
                AttendanceSummary.period_start == period_start,
                AttendanceSummary.period_end == period_end,
            )
        ).first()

    def get_student_summaries(
        self,
        student_id: UUID,
        period_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[AttendanceSummary]:
        """
        Get all summaries for student.

        Args:
            student_id: Student identifier
            period_type: Optional period type filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of summaries
        """
        query = self.session.query(AttendanceSummary).filter(
            AttendanceSummary.student_id == student_id
        )

        if period_type:
            query = query.filter(AttendanceSummary.period_type == period_type)
        if start_date:
            query = query.filter(AttendanceSummary.period_start >= start_date)
        if end_date:
            query = query.filter(AttendanceSummary.period_end <= end_date)

        return query.order_by(AttendanceSummary.period_start.desc()).all()

    def get_hostel_summaries(
        self,
        hostel_id: UUID,
        period_type: str,
        period_start: date,
        period_end: date,
        status_filter: Optional[str] = None,
    ) -> List[AttendanceSummary]:
        """
        Get all summaries for hostel in period.

        Args:
            hostel_id: Hostel identifier
            period_type: Period type
            period_start: Period start date
            period_end: Period end date
            status_filter: Optional status filter

        Returns:
            List of summaries
        """
        query = self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.hostel_id == hostel_id,
                AttendanceSummary.period_type == period_type,
                AttendanceSummary.period_start == period_start,
                AttendanceSummary.period_end == period_end,
            )
        ).options(joinedload(AttendanceSummary.student))

        if status_filter:
            query = query.filter(AttendanceSummary.attendance_status == status_filter)

        return query.order_by(AttendanceSummary.attendance_percentage.desc()).all()

    def get_low_attendance_summaries(
        self,
        hostel_id: UUID,
        threshold_percentage: Decimal,
        period_type: str = "monthly",
    ) -> List[AttendanceSummary]:
        """
        Get summaries with low attendance.

        Args:
            hostel_id: Hostel identifier
            threshold_percentage: Threshold percentage
            period_type: Period type

        Returns:
            List of low attendance summaries
        """
        return self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.hostel_id == hostel_id,
                AttendanceSummary.period_type == period_type,
                AttendanceSummary.attendance_percentage < threshold_percentage,
            )
        ).options(joinedload(AttendanceSummary.student)).order_by(
            AttendanceSummary.attendance_percentage.asc()
        ).all()

    def update_summary(
        self,
        summary_id: UUID,
        **update_data: Any,
    ) -> AttendanceSummary:
        """
        Update summary.

        Args:
            summary_id: Summary identifier
            **update_data: Fields to update

        Returns:
            Updated summary

        Raises:
            NotFoundError: If summary not found
        """
        summary = self.get_summary_by_id(summary_id)
        if not summary:
            raise NotFoundError(f"Attendance summary {summary_id} not found")

        for key, value in update_data.items():
            if hasattr(summary, key):
                setattr(summary, key, value)

        summary.last_calculated_at = datetime.utcnow()
        summary.calculation_version += 1

        self.session.flush()
        return summary

    def recalculate_summary(
        self,
        summary_id: UUID,
        new_metrics: Dict[str, Any],
    ) -> AttendanceSummary:
        """
        Recalculate summary with new metrics.

        Args:
            summary_id: Summary identifier
            new_metrics: New metric values

        Returns:
            Updated summary

        Raises:
            NotFoundError: If summary not found
        """
        return self.update_summary(summary_id, **new_metrics)

    # ==================== Trend Operations ====================

    def create_trend(
        self,
        hostel_id: UUID,
        trend_type: str,
        period_identifier: str,
        period_start: date,
        period_end: date,
        average_attendance: Decimal,
        trend_direction: str = "stable",
        change_percentage: Optional[Decimal] = None,
        student_id: Optional[UUID] = None,
        total_students: Optional[int] = None,
        average_present: Decimal = Decimal("0.00"),
        average_absent: Decimal = Decimal("0.00"),
        average_late: Decimal = Decimal("0.00"),
        forecasted_attendance: Optional[Decimal] = None,
        confidence_score: Optional[Decimal] = None,
        anomaly_detected: bool = False,
        anomaly_details: Optional[Dict[str, Any]] = None,
    ) -> AttendanceTrend:
        """
        Create attendance trend.

        Args:
            hostel_id: Hostel identifier
            trend_type: Trend type (daily, weekly, monthly, quarterly)
            period_identifier: Period identifier (e.g., "2024-01", "2024-W01")
            period_start: Period start date
            period_end: Period end date
            average_attendance: Average attendance percentage
            trend_direction: Trend direction (improving, declining, stable)
            change_percentage: Percentage change from previous period
            student_id: Optional student identifier
            total_students: Total students in calculation
            average_present: Average present count
            average_absent: Average absent count
            average_late: Average late count
            forecasted_attendance: Forecasted attendance
            confidence_score: Forecast confidence score
            anomaly_detected: Anomaly detection flag
            anomaly_details: Anomaly details

        Returns:
            Created trend

        Raises:
            ValidationError: If validation fails
        """
        if period_end < period_start:
            raise ValidationError("period_end must be >= period_start")

        valid_types = ["daily", "weekly", "monthly", "quarterly", "yearly"]
        if trend_type not in valid_types:
            raise ValidationError(f"Invalid trend type. Must be one of: {valid_types}")

        valid_directions = ["improving", "declining", "stable"]
        if trend_direction not in valid_directions:
            raise ValidationError(f"Invalid trend direction. Must be one of: {valid_directions}")

        trend = AttendanceTrend(
            hostel_id=hostel_id,
            student_id=student_id,
            trend_type=trend_type,
            period_identifier=period_identifier,
            period_start=period_start,
            period_end=period_end,
            average_attendance=average_attendance,
            trend_direction=trend_direction,
            change_percentage=change_percentage,
            total_students=total_students,
            average_present=average_present,
            average_absent=average_absent,
            average_late=average_late,
            forecasted_attendance=forecasted_attendance,
            confidence_score=confidence_score,
            anomaly_detected=anomaly_detected,
            anomaly_details=anomaly_details,
            calculated_at=datetime.utcnow(),
        )

        self.session.add(trend)
        self.session.flush()
        return trend

    def get_trend_by_id(
        self,
        trend_id: UUID,
    ) -> Optional[AttendanceTrend]:
        """
        Get trend by ID.

        Args:
            trend_id: Trend identifier

        Returns:
            Trend if found
        """
        return self.session.query(AttendanceTrend).filter(
            AttendanceTrend.id == trend_id
        ).first()

    def get_hostel_trends(
        self,
        hostel_id: UUID,
        trend_type: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 12,
    ) -> List[AttendanceTrend]:
        """
        Get hostel trends.

        Args:
            hostel_id: Hostel identifier
            trend_type: Trend type
            start_date: Optional start date
            end_date: Optional end date
            limit: Maximum number of trends to return

        Returns:
            List of trends
        """
        query = self.session.query(AttendanceTrend).filter(
            and_(
                AttendanceTrend.hostel_id == hostel_id,
                AttendanceTrend.trend_type == trend_type,
                AttendanceTrend.student_id.is_(None),  # Hostel-level trends
            )
        )

        if start_date:
            query = query.filter(AttendanceTrend.period_start >= start_date)
        if end_date:
            query = query.filter(AttendanceTrend.period_end <= end_date)

        return query.order_by(
            AttendanceTrend.period_start.desc()
        ).limit(limit).all()

    def get_student_trends(
        self,
        student_id: UUID,
        trend_type: str,
        limit: int = 12,
    ) -> List[AttendanceTrend]:
        """
        Get student trends.

        Args:
            student_id: Student identifier
            trend_type: Trend type
            limit: Maximum number of trends to return

        Returns:
            List of trends
        """
        return self.session.query(AttendanceTrend).filter(
            and_(
                AttendanceTrend.student_id == student_id,
                AttendanceTrend.trend_type == trend_type,
            )
        ).order_by(
            AttendanceTrend.period_start.desc()
        ).limit(limit).all()

    def get_trend_by_period(
        self,
        hostel_id: UUID,
        trend_type: str,
        period_identifier: str,
        student_id: Optional[UUID] = None,
    ) -> Optional[AttendanceTrend]:
        """
        Get trend for specific period.

        Args:
            hostel_id: Hostel identifier
            trend_type: Trend type
            period_identifier: Period identifier
            student_id: Optional student identifier

        Returns:
            Trend if found
        """
        query = self.session.query(AttendanceTrend).filter(
            and_(
                AttendanceTrend.hostel_id == hostel_id,
                AttendanceTrend.trend_type == trend_type,
                AttendanceTrend.period_identifier == period_identifier,
            )
        )

        if student_id:
            query = query.filter(AttendanceTrend.student_id == student_id)
        else:
            query = query.filter(AttendanceTrend.student_id.is_(None))

        return query.first()

    def get_anomaly_trends(
        self,
        hostel_id: UUID,
        trend_type: Optional[str] = None,
    ) -> List[AttendanceTrend]:
        """
        Get trends with detected anomalies.

        Args:
            hostel_id: Hostel identifier
            trend_type: Optional trend type filter

        Returns:
            List of anomalous trends
        """
        query = self.session.query(AttendanceTrend).filter(
            and_(
                AttendanceTrend.hostel_id == hostel_id,
                AttendanceTrend.anomaly_detected == True,
            )
        )

        if trend_type:
            query = query.filter(AttendanceTrend.trend_type == trend_type)

        return query.order_by(AttendanceTrend.calculated_at.desc()).all()

    def update_trend(
        self,
        trend_id: UUID,
        **update_data: Any,
    ) -> AttendanceTrend:
        """
        Update trend.

        Args:
            trend_id: Trend identifier
            **update_data: Fields to update

        Returns:
            Updated trend

        Raises:
            NotFoundError: If trend not found
        """
        trend = self.get_trend_by_id(trend_id)
        if not trend:
            raise NotFoundError(f"Attendance trend {trend_id} not found")

        for key, value in update_data.items():
            if hasattr(trend, key):
                setattr(trend, key, value)

        trend.calculated_at = datetime.utcnow()
        self.session.flush()
        return trend

    # ==================== Analytics and Statistics ====================

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
            Dictionary with overview statistics
        """
        summaries = self.get_hostel_summaries(
            hostel_id=hostel_id,
            period_type="monthly",
            period_start=period_start,
            period_end=period_end,
        )

        if not summaries:
            return {
                "total_students": 0,
                "average_attendance": 0.0,
                "excellent_count": 0,
                "good_count": 0,
                "warning_count": 0,
                "critical_count": 0,
            }

        total_students = len(summaries)
        avg_attendance = sum(s.attendance_percentage for s in summaries) / total_students

        status_counts = {
            "excellent": sum(1 for s in summaries if s.attendance_status == "excellent"),
            "good": sum(1 for s in summaries if s.attendance_status == "good"),
            "warning": sum(1 for s in summaries if s.attendance_status == "warning"),
            "critical": sum(1 for s in summaries if s.attendance_status == "critical"),
        }

        return {
            "total_students": total_students,
            "average_attendance": float(round(avg_attendance, 2)),
            "excellent_count": status_counts["excellent"],
            "good_count": status_counts["good"],
            "warning_count": status_counts["warning"],
            "critical_count": status_counts["critical"],
            "meets_requirement_count": sum(1 for s in summaries if s.meets_minimum_requirement),
            "below_requirement_count": sum(1 for s in summaries if not s.meets_minimum_requirement),
        }

    def get_comparative_analysis(
        self,
        hostel_id: UUID,
        current_period_start: date,
        current_period_end: date,
        previous_period_start: date,
        previous_period_end: date,
    ) -> Dict[str, Any]:
        """
        Get comparative analysis between two periods.

        Args:
            hostel_id: Hostel identifier
            current_period_start: Current period start
            current_period_end: Current period end
            previous_period_start: Previous period start
            previous_period_end: Previous period end

        Returns:
            Dictionary with comparative statistics
        """
        current_summaries = self.get_hostel_summaries(
            hostel_id=hostel_id,
            period_type="monthly",
            period_start=current_period_start,
            period_end=current_period_end,
        )

        previous_summaries = self.get_hostel_summaries(
            hostel_id=hostel_id,
            period_type="monthly",
            period_start=previous_period_start,
            period_end=previous_period_end,
        )

        current_avg = 0.0
        if current_summaries:
            current_avg = sum(s.attendance_percentage for s in current_summaries) / len(current_summaries)

        previous_avg = 0.0
        if previous_summaries:
            previous_avg = sum(s.attendance_percentage for s in previous_summaries) / len(previous_summaries)

        change = current_avg - previous_avg
        change_percentage = (change / previous_avg * 100) if previous_avg > 0 else 0

        return {
            "current_period": {
                "start": current_period_start,
                "end": current_period_end,
                "average_attendance": float(round(current_avg, 2)),
                "total_students": len(current_summaries),
            },
            "previous_period": {
                "start": previous_period_start,
                "end": previous_period_end,
                "average_attendance": float(round(previous_avg, 2)),
                "total_students": len(previous_summaries),
            },
            "change": {
                "absolute": float(round(change, 2)),
                "percentage": float(round(change_percentage, 2)),
                "trend": "improving" if change > 0 else "declining" if change < 0 else "stable",
            },
        }

    def get_top_performers(
        self,
        hostel_id: UUID,
        period_type: str,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ) -> List[AttendanceSummary]:
        """
        Get top performing students by attendance.

        Args:
            hostel_id: Hostel identifier
            period_type: Period type
            period_start: Period start date
            period_end: Period end date
            limit: Number of top performers to return

        Returns:
            List of top performer summaries
        """
        return self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.hostel_id == hostel_id,
                AttendanceSummary.period_type == period_type,
                AttendanceSummary.period_start == period_start,
                AttendanceSummary.period_end == period_end,
            )
        ).options(joinedload(AttendanceSummary.student)).order_by(
            AttendanceSummary.attendance_percentage.desc(),
            AttendanceSummary.longest_present_streak.desc(),
        ).limit(limit).all()

    def get_bottom_performers(
        self,
        hostel_id: UUID,
        period_type: str,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ) -> List[AttendanceSummary]:
        """
        Get bottom performing students by attendance.

        Args:
            hostel_id: Hostel identifier
            period_type: Period type
            period_start: Period start date
            period_end: Period end date
            limit: Number of bottom performers to return

        Returns:
            List of bottom performer summaries
        """
        return self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.hostel_id == hostel_id,
                AttendanceSummary.period_type == period_type,
                AttendanceSummary.period_start == period_start,
                AttendanceSummary.period_end == period_end,
            )
        ).options(joinedload(AttendanceSummary.student)).order_by(
            AttendanceSummary.attendance_percentage.asc(),
            AttendanceSummary.longest_absent_streak.desc(),
        ).limit(limit).all()


