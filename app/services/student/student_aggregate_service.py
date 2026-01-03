# app/services/student/student_aggregate_service.py
"""
Student Aggregate Service

Provides aggregated dashboard data and statistics for student views.
Orchestrates multiple services to create comprehensive dashboard information.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, date, timedelta
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.student import (
    StudentRepository,
    StudentAggregateRepository,
)
from app.schemas.student.student_dashboard import (
    StudentDashboard,
    DashboardPeriod,
    QuickStats,
    AttendanceSummary,
    PaymentSummary,
    ComplaintsSummary,
    LeaveSummary,
    RoomInfo,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.core1.result import Result

logger = logging.getLogger(__name__)


@dataclass
class PeriodDates:
    """Helper class to calculate date ranges for dashboard periods."""
    start_date: date
    end_date: date


class StudentAggregateService:
    """
    High-level service for student dashboard aggregations.

    Responsibilities:
    - Aggregate dashboard statistics across multiple domains
    - Provide period-based filtering for statistics
    - Optimize queries for dashboard performance
    - Orchestrate multiple repositories for comprehensive data
    """

    def __init__(
        self,
        student_repo: StudentRepository,
        aggregate_repo: StudentAggregateRepository,
    ) -> None:
        """
        Initialize service with required repositories.

        Args:
            student_repo: Repository for student operations
            aggregate_repo: Repository for aggregate queries
        """
        self.student_repo = student_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # Dashboard Methods
    # -------------------------------------------------------------------------

    def get_student_dashboard_stats(
        self,
        db: Session,
        student_id: UUID,
        period: DashboardPeriod = DashboardPeriod.CURRENT_MONTH,
    ) -> Result[StudentDashboard, str]:
        """
        Get comprehensive dashboard statistics for a student.

        Args:
            db: Database session
            student_id: UUID of student
            period: Time period for statistics

        Returns:
            Result containing StudentDashboard or error message
        """
        try:
            # Verify student exists
            student = self.student_repo.get_by_id(db, student_id)
            if not student:
                return Result.failure(f"Student not found: {student_id}")

            # Calculate date range for the period
            period_dates = self._calculate_period_dates(period)

            # Gather all dashboard components
            attendance_summary = self._get_attendance_summary(
                db, student_id, period_dates
            )
            payment_summary = self._get_payment_summary(
                db, student_id, period_dates
            )
            complaints_summary = self._get_complaints_summary(
                db, student_id, period_dates
            )
            leave_summary = self._get_leave_summary(
                db, student_id, period_dates
            )
            room_info = self._get_room_info(db, student_id)
            recent_notifications = self._get_recent_notifications(
                db, student_id, limit=5
            )

            dashboard = StudentDashboard(
                student_id=student_id,
                student_name=student.user.full_name if student.user else None,
                hostel_name=student.hostel.name if student.hostel else None,
                period=period,
                period_start=period_dates.start_date,
                period_end=period_dates.end_date,
                attendance=attendance_summary,
                payments=payment_summary,
                complaints=complaints_summary,
                leave=leave_summary,
                room_info=room_info,
                recent_notifications=recent_notifications,
                generated_at=datetime.utcnow(),
            )

            logger.info(
                f"Dashboard stats generated for student {student_id}, "
                f"period: {period}"
            )

            return Result.success(dashboard)

        except Exception as e:
            logger.error(
                f"Error generating dashboard stats for student {student_id}: {e}",
                exc_info=True
            )
            return Result.failure(f"Failed to generate dashboard: {str(e)}")

    def get_quick_stats(
        self,
        db: Session,
        student_id: UUID,
    ) -> Result[Dict[str, Any], str]:
        """
        Get lightweight statistics for quick dashboard loading.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            Result containing quick stats dictionary or error message
        """
        try:
            # Verify student exists
            student = self.student_repo.get_by_id(db, student_id)
            if not student:
                return Result.failure(f"Student not found: {student_id}")

            # Get quick stats from optimized queries
            stats = self.aggregate_repo.get_quick_dashboard_stats(db, student_id)

            quick_stats = {
                "student_id": str(student_id),
                "unread_notifications": stats.get("unread_notifications", 0),
                "pending_dues_amount": stats.get("pending_dues_amount", 0.0),
                "today_attendance_status": stats.get("today_attendance_status", "unknown"),
                "pending_leave_applications": stats.get("pending_leave_applications", 0),
                "active_complaints": stats.get("active_complaints", 0),
                "last_updated": datetime.utcnow().isoformat(),
            }

            return Result.success(quick_stats)

        except Exception as e:
            logger.error(
                f"Error generating quick stats for student {student_id}: {e}",
                exc_info=True
            )
            return Result.failure(f"Failed to generate quick stats: {str(e)}")

    # -------------------------------------------------------------------------
    # Helper Methods for Dashboard Components
    # -------------------------------------------------------------------------

    def _get_attendance_summary(
        self,
        db: Session,
        student_id: UUID,
        period_dates: PeriodDates,
    ) -> AttendanceSummary:
        """Get attendance summary for the period."""
        try:
            data = self.aggregate_repo.get_attendance_summary(
                db, student_id, period_dates.start_date, period_dates.end_date
            )
            
            return AttendanceSummary(
                total_days=data.get("total_days", 0),
                present_days=data.get("present_days", 0),
                absent_days=data.get("absent_days", 0),
                late_arrivals=data.get("late_arrivals", 0),
                attendance_percentage=data.get("attendance_percentage", 0.0),
                recent_records=data.get("recent_records", []),
            )
        except Exception as e:
            logger.warning(f"Error fetching attendance summary: {e}")
            return AttendanceSummary()

    def _get_payment_summary(
        self,
        db: Session,
        student_id: UUID,
        period_dates: PeriodDates,
    ) -> PaymentSummary:
        """Get payment summary for the period."""
        try:
            data = self.aggregate_repo.get_payment_summary(
                db, student_id, period_dates.start_date, period_dates.end_date
            )
            
            return PaymentSummary(
                total_due=data.get("total_due", 0.0),
                paid_amount=data.get("paid_amount", 0.0),
                pending_amount=data.get("pending_amount", 0.0),
                overdue_amount=data.get("overdue_amount", 0.0),
                next_due_date=data.get("next_due_date"),
                payment_status=data.get("payment_status", "unknown"),
                recent_payments=data.get("recent_payments", []),
            )
        except Exception as e:
            logger.warning(f"Error fetching payment summary: {e}")
            return PaymentSummary()

    def _get_complaints_summary(
        self,
        db: Session,
        student_id: UUID,
        period_dates: PeriodDates,
    ) -> ComplaintsSummary:
        """Get complaints summary for the period."""
        try:
            data = self.aggregate_repo.get_complaints_summary(
                db, student_id, period_dates.start_date, period_dates.end_date
            )
            
            return ComplaintsSummary(
                total_complaints=data.get("total_complaints", 0),
                resolved_complaints=data.get("resolved_complaints", 0),
                pending_complaints=data.get("pending_complaints", 0),
                recent_complaints=data.get("recent_complaints", []),
            )
        except Exception as e:
            logger.warning(f"Error fetching complaints summary: {e}")
            return ComplaintsSummary()

    def _get_leave_summary(
        self,
        db: Session,
        student_id: UUID,
        period_dates: PeriodDates,
    ) -> LeaveSummary:
        """Get leave summary for the period."""
        try:
            data = self.aggregate_repo.get_leave_summary(
                db, student_id, period_dates.start_date, period_dates.end_date
            )
            
            return LeaveSummary(
                available_balance=data.get("available_balance", 0),
                used_days=data.get("used_days", 0),
                pending_applications=data.get("pending_applications", 0),
                recent_applications=data.get("recent_applications", []),
            )
        except Exception as e:
            logger.warning(f"Error fetching leave summary: {e}")
            return LeaveSummary()

    def _get_room_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[RoomInfo]:
        """Get current room information."""
        try:
            student = self.student_repo.get_full_student(db, student_id)
            if not student or not student.room:
                return None
                
            return RoomInfo(
                room_number=student.room.number,
                room_type=student.room.room_type,
                bed_number=student.bed.number if student.bed else None,
                floor=student.room.floor,
                wing=student.room.wing,
                amenities=student.room.amenities or [],
                roommates=self._get_roommate_info(db, student.room_id, student_id),
            )
        except Exception as e:
            logger.warning(f"Error fetching room info: {e}")
            return None

    def _get_recent_notifications(
        self,
        db: Session,
        student_id: UUID,
        limit: int = 5,
    ) -> list:
        """Get recent notifications."""
        try:
            # This would typically query a notifications table
            # Placeholder implementation
            return []
        except Exception as e:
            logger.warning(f"Error fetching recent notifications: {e}")
            return []

    def _get_roommate_info(
        self,
        db: Session,
        room_id: UUID,
        exclude_student_id: UUID,
    ) -> list:
        """Get information about roommates."""
        try:
            roommates = self.student_repo.get_roommates(
                db, room_id, exclude_student_id
            )
            return [
                {
                    "name": rm.user.full_name if rm.user else "Unknown",
                    "student_id": str(rm.id),
                    "bed_number": rm.bed.number if rm.bed else None,
                }
                for rm in roommates
            ]
        except Exception as e:
            logger.warning(f"Error fetching roommate info: {e}")
            return []

    # -------------------------------------------------------------------------
    # Date Calculation Helpers
    # -------------------------------------------------------------------------

    def _calculate_period_dates(self, period: DashboardPeriod) -> PeriodDates:
        """Calculate start and end dates for the given period."""
        today = date.today()
        
        if period == DashboardPeriod.TODAY:
            return PeriodDates(start_date=today, end_date=today)
        
        elif period == DashboardPeriod.CURRENT_WEEK:
            # Start of current week (Monday)
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return PeriodDates(start_date=start, end_date=end)
        
        elif period == DashboardPeriod.CURRENT_MONTH:
            # Start of current month
            start = today.replace(day=1)
            # Last day of current month
            if today.month == 12:
                end = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(today.year, today.month + 1, 1) - timedelta(days=1)
            return PeriodDates(start_date=start, end_date=end)
        
        elif period == DashboardPeriod.LAST_30_DAYS:
            start = today - timedelta(days=30)
            return PeriodDates(start_date=start, end_date=today)
        
        elif period == DashboardPeriod.CURRENT_SEMESTER:
            # This would need semester configuration
            # Placeholder: assume 6-month semester
            start = today.replace(month=1 if today.month <= 6 else 7, day=1)
            return PeriodDates(start_date=start, end_date=today)
        
        else:
            # Default to current month
            start = today.replace(day=1)
            return PeriodDates(start_date=start, end_date=today)