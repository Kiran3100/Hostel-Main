"""
Attendance reporting & analytics service.

Handles:
- Hostel-level attendance reports
- Monthly summaries and comparisons
- Student-specific reports
- Trend analysis
- Comparative analytics
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, timedelta, datetime
from calendar import monthrange
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.attendance import (
    AttendanceReportRepository,
    AttendanceAggregateRepository
)
from app.models.attendance.attendance_report import AttendanceReport as AttendanceReportModel
from app.schemas.attendance.attendance_report import (
    AttendanceSummary,
    DailyAttendanceRecord,
    WeeklyAttendance,
    MonthlyComparison,
    TrendAnalysis,
    AttendanceReport,
    StudentMonthlySummary,
    MonthlyReport,
    ComparisonItem,
    AttendanceComparison,
)

logger = logging.getLogger(__name__)


class AttendanceReportService(
    BaseService[AttendanceReportModel, AttendanceReportRepository]
):
    """
    Service for generating attendance summaries/reports and trends.
    
    Responsibilities:
    - Generate comprehensive attendance reports
    - Provide monthly and weekly summaries
    - Calculate attendance trends
    - Support comparative analysis
    - Aggregate attendance data for dashboards
    """

    def __init__(
        self,
        repository: AttendanceReportRepository,
        aggregate_repository: AttendanceAggregateRepository,
        db_session: Session,
    ):
        """
        Initialize report service.
        
        Args:
            repository: AttendanceReportRepository instance
            aggregate_repository: AttendanceAggregateRepository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self.aggregate_repository = aggregate_repository
        self._operation_context = "AttendanceReportService"

    def generate_hostel_report(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        include_trend: bool = True,
        include_students: bool = True,
    ) -> ServiceResult[AttendanceReport]:
        """
        Build a comprehensive attendance report for a hostel within a period.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start of reporting period
            end_date: End of reporting period
            include_trend: Whether to include trend analysis
            include_students: Whether to include per-student breakdowns
            
        Returns:
            ServiceResult containing AttendanceReport
        """
        operation = "generate_hostel_report"
        logger.info(
            f"{operation}: hostel_id={hostel_id}, "
            f"date_range={start_date} to {end_date}, "
            f"include_trend={include_trend}"
        )
        
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date, max_days=365)
            if not validation_result.success:
                return validation_result
            
            # Generate report
            report = self.repository.generate_hostel_report(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
                include_trend=include_trend,
                include_students=include_students
            )
            
            logger.info(
                f"{operation} successful: hostel_id={hostel_id}, "
                f"period={start_date} to {end_date}"
            )
            
            return ServiceResult.success(
                report,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "days": (end_date - start_date).days + 1
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while generating report: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def generate_monthly_report(
        self,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> ServiceResult[MonthlyReport]:
        """
        Generate hostel-wide monthly report with student summaries.
        
        Args:
            hostel_id: UUID of hostel
            year: Year (e.g., 2024)
            month: Month (1-12)
            
        Returns:
            ServiceResult containing MonthlyReport
        """
        operation = "generate_monthly_report"
        logger.info(
            f"{operation}: hostel_id={hostel_id}, year={year}, month={month}"
        )
        
        try:
            # Validate month and year
            if month < 1 or month > 12:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Month must be between 1 and 12",
                        severity=ErrorSeverity.WARNING,
                        details={"month": month}
                    )
                )
            
            if year < 2000 or year > 2100:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Year must be between 2000 and 2100",
                        severity=ErrorSeverity.WARNING,
                        details={"year": year}
                    )
                )
            
            # Generate monthly report
            monthly = self.repository.generate_monthly_report(
                hostel_id=hostel_id,
                year=year,
                month=month
            )
            
            logger.info(
                f"{operation} successful: hostel_id={hostel_id}, "
                f"period={year}-{month:02d}"
            )
            
            return ServiceResult.success(
                monthly,
                metadata={
                    "hostel_id": str(hostel_id),
                    "year": year,
                    "month": month,
                    "month_name": date(year, month, 1).strftime("%B %Y")
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while generating monthly report: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def generate_student_report(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Generate detailed attendance report for a specific student.
        
        Args:
            student_id: UUID of student
            start_date: Start of reporting period
            end_date: End of reporting period
            
        Returns:
            ServiceResult containing student attendance report
        """
        operation = "generate_student_report"
        logger.info(
            f"{operation}: student_id={student_id}, "
            f"date_range={start_date} to {end_date}"
        )
        
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date, max_days=365)
            if not validation_result.success:
                return validation_result
            
            # Generate student report
            report = self.repository.generate_student_report(
                student_id=student_id,
                start_date=start_date,
                end_date=end_date
            )
            
            logger.info(
                f"{operation} successful: student_id={student_id}"
            )
            
            return ServiceResult.success(
                report,
                metadata={
                    "student_id": str(student_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date)
                }
            )
            
        except Exception as e:
            logger.error(f"{operation} error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, student_id)

    def compare_attendance(
        self,
        comparison_type: str,
        start_date: date,
        end_date: date,
        hostel_id: Optional[UUID] = None,
        limit: int = 10,
    ) -> ServiceResult[AttendanceComparison]:
        """
        Compare attendance across students/hostels/rooms.
        
        Args:
            comparison_type: Type of comparison (students, hostels, rooms)
            start_date: Start of comparison period
            end_date: End of comparison period
            hostel_id: Optional hostel filter for student/room comparisons
            limit: Maximum number of items to return
            
        Returns:
            ServiceResult containing AttendanceComparison
        """
        operation = "compare_attendance"
        logger.info(
            f"{operation}: type={comparison_type}, "
            f"date_range={start_date} to {end_date}, "
            f"hostel_id={hostel_id}"
        )
        
        try:
            # Validate comparison type
            valid_types = {'students', 'hostels', 'rooms', 'floors'}
            if comparison_type.lower() not in valid_types:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid comparison type: {comparison_type}",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "comparison_type": comparison_type,
                            "valid_types": list(valid_types)
                        }
                    )
                )
            
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date, max_days=180)
            if not validation_result.success:
                return validation_result
            
            # Validate limit
            if limit < 1:
                limit = 10
            if limit > 100:
                limit = 100
            
            # Generate comparison
            comparison = self.repository.generate_comparison(
                comparison_type=comparison_type,
                start_date=start_date,
                end_date=end_date,
                hostel_id=hostel_id,
                limit=limit
            )
            
            logger.info(
                f"{operation} successful: type={comparison_type}, "
                f"items={len(comparison.items)}"
            )
            
            return ServiceResult.success(
                comparison,
                metadata={
                    "comparison_type": comparison_type,
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "item_count": len(comparison.items)
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while generating comparison: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"comparison_type": comparison_type}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, comparison_type)

    def get_weekly_summary(
        self,
        hostel_id: UUID,
        start_date: date,
    ) -> ServiceResult[WeeklyAttendance]:
        """
        Get weekly attendance summary starting from given date.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start of week
            
        Returns:
            ServiceResult containing WeeklyAttendance
        """
        operation = "get_weekly_summary"
        logger.debug(
            f"{operation}: hostel_id={hostel_id}, start_date={start_date}"
        )
        
        try:
            # Calculate week end date
            end_date = start_date + timedelta(days=6)
            
            # Get weekly summary
            summary = self.repository.get_weekly_summary(
                hostel_id=hostel_id,
                start_date=start_date
            )
            
            return ServiceResult.success(
                summary,
                metadata={
                    "hostel_id": str(hostel_id),
                    "week_start": str(start_date),
                    "week_end": str(end_date)
                }
            )
            
        except Exception as e:
            logger.error(f"{operation} error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def get_trend_analysis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        interval: str = "daily",
    ) -> ServiceResult[TrendAnalysis]:
        """
        Get attendance trend analysis for visualization.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start of analysis period
            end_date: End of analysis period
            interval: Aggregation interval (daily, weekly, monthly)
            
        Returns:
            ServiceResult containing TrendAnalysis
        """
        operation = "get_trend_analysis"
        logger.info(
            f"{operation}: hostel_id={hostel_id}, "
            f"date_range={start_date} to {end_date}, "
            f"interval={interval}"
        )
        
        try:
            # Validate interval
            valid_intervals = {'daily', 'weekly', 'monthly'}
            if interval.lower() not in valid_intervals:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid interval: {interval}",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "interval": interval,
                            "valid_intervals": list(valid_intervals)
                        }
                    )
                )
            
            # Validate date range based on interval
            max_days = {"daily": 90, "weekly": 365, "monthly": 730}
            validation_result = self._validate_date_range(
                start_date,
                end_date,
                max_days=max_days[interval.lower()]
            )
            if not validation_result.success:
                return validation_result
            
            # Get trend analysis
            trend = self.repository.get_trend_analysis(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
                interval=interval
            )
            
            logger.info(
                f"{operation} successful: hostel_id={hostel_id}, "
                f"data_points={len(trend.data_points) if trend else 0}"
            )
            
            return ServiceResult.success(
                trend,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "interval": interval
                }
            )
            
        except Exception as e:
            logger.error(f"{operation} error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def export_report(
        self,
        report_id: UUID,
        format: str = "pdf",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Export a generated report in specified format.
        
        Args:
            report_id: UUID of report to export
            format: Export format (pdf, excel, csv)
            
        Returns:
            ServiceResult with export details (file path, download URL, etc.)
        """
        operation = "export_report"
        logger.info(f"{operation}: report_id={report_id}, format={format}")
        
        try:
            # Validate format
            valid_formats = {'pdf', 'excel', 'csv', 'json'}
            if format.lower() not in valid_formats:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid export format: {format}",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "format": format,
                            "valid_formats": list(valid_formats)
                        }
                    )
                )
            
            # Export report
            export_result = self.repository.export_report(
                report_id=report_id,
                format=format
            )
            
            if not export_result:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Report not found: {report_id}",
                        severity=ErrorSeverity.WARNING,
                        details={"report_id": str(report_id)}
                    )
                )
            
            logger.info(
                f"{operation} successful: report_id={report_id}, format={format}"
            )
            
            return ServiceResult.success(
                export_result,
                message="Report exported successfully",
                metadata={
                    "report_id": str(report_id),
                    "format": format
                }
            )
            
        except Exception as e:
            logger.error(f"{operation} error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, report_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_date_range(
        self,
        start_date: date,
        end_date: date,
        max_days: int = 365
    ) -> ServiceResult[None]:
        """
        Validate date range for reports.
        
        Args:
            start_date: Start date
            end_date: End date
            max_days: Maximum allowed days in range
            
        Returns:
            ServiceResult indicating validation success/failure
        """
        # Check start date is before end date
        if start_date > end_date:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date must be before or equal to end date",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "start_date": str(start_date),
                        "end_date": str(end_date)
                    }
                )
            )
        
        # Check date range is not too large
        days_diff = (end_date - start_date).days + 1
        if days_diff > max_days:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Date range cannot exceed {max_days} days",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "days": days_diff,
                        "max_days": max_days
                    }
                )
            )
        
        # Check dates are not in the future
        today = date.today()
        if start_date > today:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date cannot be in the future",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "start_date": str(start_date),
                        "today": str(today)
                    }
                )
            )
        
        return ServiceResult.success(None)