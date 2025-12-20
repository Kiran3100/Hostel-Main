# --- File: app/services/attendance/attendance_service.py ---
"""
Core attendance service with comprehensive business logic.

Provides attendance marking, querying, bulk operations, and validation
with integration to policy enforcement and alert generation.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.attendance.attendance_record import AttendanceRecord
from app.models.base.enums import AttendanceStatus, AttendanceMode
from app.repositories.attendance.attendance_record_repository import (
    AttendanceRecordRepository,
)
from app.repositories.attendance.attendance_policy_repository import (
    AttendancePolicyRepository,
)
from app.repositories.attendance.attendance_alert_repository import (
    AttendanceAlertRepository,
)
from app.core.exceptions import ValidationError, NotFoundError, BusinessLogicError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AttendanceService:
    """
    Service for attendance management with business logic.
    """

    def __init__(self, session: Session):
        """
        Initialize service with database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.attendance_repo = AttendanceRecordRepository(session)
        self.policy_repo = AttendancePolicyRepository(session)
        self.alert_repo = AttendanceAlertRepository(session)

    # ==================== Attendance Marking ====================

    def mark_attendance(
        self,
        hostel_id: UUID,
        student_id: UUID,
        attendance_date: date,
        status: AttendanceStatus,
        marked_by: UUID,
        check_in_time: Optional[time] = None,
        check_out_time: Optional[time] = None,
        notes: Optional[str] = None,
        attendance_mode: AttendanceMode = AttendanceMode.MANUAL,
        location_lat: Optional[Decimal] = None,
        location_lng: Optional[Decimal] = None,
        device_info: Optional[Dict[str, Any]] = None,
        supervisor_id: Optional[UUID] = None,
        auto_calculate_late: bool = True,
    ) -> AttendanceRecord:
        """
        Mark attendance for student with policy validation.

        Args:
            hostel_id: Hostel identifier
            student_id: Student identifier
            attendance_date: Date of attendance
            status: Attendance status
            marked_by: User marking attendance
            check_in_time: Check-in time
            check_out_time: Check-out time
            notes: Additional notes
            attendance_mode: Mode of marking
            location_lat: Latitude for geolocation
            location_lng: Longitude for geolocation
            device_info: Device information
            supervisor_id: Supervisor identifier
            auto_calculate_late: Auto-calculate late status

        Returns:
            Created attendance record

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules violated
        """
        try:
            # Validate date not in future
            if attendance_date > date.today():
                raise ValidationError("Cannot mark attendance for future dates")

            # Get policy for hostel
            policy = self.policy_repo.get_by_hostel(hostel_id)

            # Calculate late status if present and auto-calculate enabled
            is_late = False
            late_minutes = None

            if status == AttendanceStatus.PRESENT and check_in_time and auto_calculate_late and policy:
                late_result = self._calculate_late_status(
                    check_in_time=check_in_time,
                    policy=policy,
                    attendance_date=attendance_date,
                )
                is_late = late_result["is_late"]
                late_minutes = late_result["late_minutes"]

            # Create attendance record
            record = self.attendance_repo.create_attendance(
                hostel_id=hostel_id,
                student_id=student_id,
                attendance_date=attendance_date,
                status=status,
                marked_by=marked_by,
                check_in_time=check_in_time,
                check_out_time=check_out_time,
                is_late=is_late,
                late_minutes=late_minutes,
                attendance_mode=attendance_mode,
                notes=notes,
                location_lat=location_lat,
                location_lng=location_lng,
                device_info=device_info,
                supervisor_id=supervisor_id,
            )

            # Check policy violations and generate alerts if needed
            if policy:
                self._check_policy_violations_and_alert(
                    student_id=student_id,
                    hostel_id=hostel_id,
                    attendance_record=record,
                    policy=policy,
                )

            self.session.commit()
            logger.info(
                f"Attendance marked for student {student_id} on {attendance_date}: {status.value}"
            )

            return record

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error marking attendance: {str(e)}")
            raise

    def mark_bulk_attendance(
        self,
        hostel_id: UUID,
        attendance_date: date,
        student_ids: List[UUID],
        status: AttendanceStatus,
        marked_by: UUID,
        notes: Optional[str] = None,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Mark attendance for multiple students.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance
            student_ids: List of student identifiers
            status: Attendance status to set
            marked_by: User marking attendance
            notes: Optional notes
            batch_size: Batch size for processing

        Returns:
            Dictionary with operation results

        Raises:
            ValidationError: If validation fails
        """
        try:
            if attendance_date > date.today():
                raise ValidationError("Cannot mark attendance for future dates")

            if not student_ids:
                raise ValidationError("Student list cannot be empty")

            # Create bulk attendance records
            log = self.attendance_repo.create_bulk_attendance(
                hostel_id=hostel_id,
                attendance_date=attendance_date,
                student_ids=student_ids,
                status=status,
                marked_by=marked_by,
                attendance_mode=AttendanceMode.BULK,
                batch_size=batch_size,
            )

            self.session.commit()

            logger.info(
                f"Bulk attendance marked for {log.successful_count}/{log.total_students} "
                f"students on {attendance_date}"
            )

            return {
                "total_students": log.total_students,
                "successful_count": log.successful_count,
                "failed_count": log.failed_count,
                "errors": log.errors,
                "execution_time_ms": log.execution_time_ms,
                "log_id": log.id,
            }

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in bulk attendance marking: {str(e)}")
            raise

    def update_attendance(
        self,
        attendance_id: UUID,
        status: Optional[AttendanceStatus] = None,
        check_in_time: Optional[time] = None,
        check_out_time: Optional[time] = None,
        notes: Optional[str] = None,
        recalculate_late: bool = True,
    ) -> AttendanceRecord:
        """
        Update existing attendance record.

        Args:
            attendance_id: Attendance record identifier
            status: New status
            check_in_time: New check-in time
            check_out_time: New check-out time
            notes: Updated notes
            recalculate_late: Whether to recalculate late status

        Returns:
            Updated attendance record

        Raises:
            NotFoundError: If record not found
        """
        try:
            record = self.attendance_repo.get_by_id(attendance_id)
            if not record:
                raise NotFoundError(f"Attendance record {attendance_id} not found")

            update_data = {}
            if status is not None:
                update_data["status"] = status
            if check_in_time is not None:
                update_data["check_in_time"] = check_in_time
            if check_out_time is not None:
                update_data["check_out_time"] = check_out_time
            if notes is not None:
                update_data["notes"] = notes

            # Recalculate late status if needed
            if recalculate_late and check_in_time is not None:
                policy = self.policy_repo.get_by_hostel(record.hostel_id)
                if policy:
                    late_result = self._calculate_late_status(
                        check_in_time=check_in_time,
                        policy=policy,
                        attendance_date=record.attendance_date,
                    )
                    update_data["is_late"] = late_result["is_late"]
                    update_data["late_minutes"] = late_result["late_minutes"]

            updated_record = self.attendance_repo.update_attendance(
                attendance_id=attendance_id,
                **update_data,
            )

            self.session.commit()
            logger.info(f"Attendance record {attendance_id} updated")

            return updated_record

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating attendance: {str(e)}")
            raise

    # ==================== Attendance Querying ====================

    def get_attendance_by_id(
        self,
        attendance_id: UUID,
        include_relationships: bool = True,
    ) -> Optional[AttendanceRecord]:
        """
        Get attendance record by ID.

        Args:
            attendance_id: Attendance record identifier
            include_relationships: Load related entities

        Returns:
            Attendance record if found
        """
        return self.attendance_repo.get_by_id(
            attendance_id=attendance_id,
            load_relationships=include_relationships,
        )

    def get_student_attendance(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
        status_filter: Optional[List[AttendanceStatus]] = None,
    ) -> List[AttendanceRecord]:
        """
        Get attendance records for student in date range.

        Args:
            student_id: Student identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            status_filter: Optional status filters

        Returns:
            List of attendance records
        """
        return self.attendance_repo.get_student_attendance_range(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            status_filter=status_filter,
        )

    def get_hostel_daily_attendance(
        self,
        hostel_id: UUID,
        attendance_date: date,
        status_filter: Optional[AttendanceStatus] = None,
        include_students: bool = True,
    ) -> List[AttendanceRecord]:
        """
        Get all attendance records for hostel on specific date.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance
            status_filter: Optional status filter
            include_students: Load student relationships

        Returns:
            List of attendance records
        """
        return self.attendance_repo.get_by_hostel_and_date(
            hostel_id=hostel_id,
            attendance_date=attendance_date,
            status_filter=status_filter,
            include_relationships=include_students,
        )

    def get_absent_students(
        self,
        hostel_id: UUID,
        attendance_date: date,
    ) -> List[AttendanceRecord]:
        """
        Get all absent students for specific date.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance

        Returns:
            List of absent attendance records
        """
        return self.attendance_repo.find_absent_students(
            hostel_id=hostel_id,
            attendance_date=attendance_date,
        )

    def get_late_entries(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        min_late_minutes: int = 1,
    ) -> List[AttendanceRecord]:
        """
        Get late entry records in date range.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            min_late_minutes: Minimum late minutes

        Returns:
            List of late attendance records
        """
        return self.attendance_repo.find_late_entries(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            min_late_minutes=min_late_minutes,
        )

    # ==================== Statistics and Analytics ====================

    def calculate_student_attendance_percentage(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
        exclude_on_leave: bool = True,
    ) -> Decimal:
        """
        Calculate attendance percentage for student.

        Args:
            student_id: Student identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            exclude_on_leave: Exclude leave days from calculation

        Returns:
            Attendance percentage
        """
        return self.attendance_repo.calculate_attendance_percentage(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            exclude_on_leave=exclude_on_leave,
        )

    def get_student_attendance_summary(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get comprehensive attendance summary for student.

        Args:
            student_id: Student identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Dictionary with attendance statistics
        """
        summary = self.attendance_repo.get_attendance_summary(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Add policy compliance check
        policy = self.policy_repo.get_by_hostel(hostel_id=None)  # Get from student
        if policy:
            summary["meets_minimum_requirement"] = (
                summary["attendance_percentage"] >= float(policy.minimum_attendance_percentage)
            )
            summary["required_percentage"] = float(policy.minimum_attendance_percentage)
        else:
            summary["meets_minimum_requirement"] = None
            summary["required_percentage"] = None

        return summary

    def get_hostel_daily_summary(
        self,
        hostel_id: UUID,
        attendance_date: date,
    ) -> Dict[str, Any]:
        """
        Get daily attendance summary for hostel.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance

        Returns:
            Dictionary with daily statistics
        """
        return self.attendance_repo.get_hostel_daily_summary(
            hostel_id=hostel_id,
            attendance_date=attendance_date,
        )

    def get_late_entry_statistics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get late entry statistics for hostel.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Dictionary with late entry statistics
        """
        return self.attendance_repo.get_late_entry_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    def find_consecutive_absences(
        self,
        student_id: UUID,
        min_consecutive_days: int = 3,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find consecutive absence streaks for student.

        Args:
            student_id: Student identifier
            min_consecutive_days: Minimum consecutive days
            end_date: End date for search

        Returns:
            List of absence streaks with details
        """
        streaks = self.attendance_repo.find_consecutive_absences(
            student_id=student_id,
            min_consecutive_days=min_consecutive_days,
            end_date=end_date,
        )

        return [
            {
                "start_date": streak[0].attendance_date,
                "end_date": streak[-1].attendance_date,
                "consecutive_days": len(streak),
                "dates": [r.attendance_date for r in streak],
            }
            for streak in streaks
        ]

    # ==================== Auto-Marking ====================

    def auto_mark_absent(
        self,
        hostel_id: UUID,
        attendance_date: date,
        marked_by: UUID,
        cutoff_time: Optional[time] = None,
    ) -> Dict[str, Any]:
        """
        Auto-mark students as absent after cutoff time.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance
            marked_by: User performing auto-mark
            cutoff_time: Cutoff time for auto-marking

        Returns:
            Dictionary with operation results
        """
        try:
            policy = self.policy_repo.get_by_hostel(hostel_id)
            
            # Check if auto-marking is enabled
            if not policy or not policy.auto_mark_absent_enabled:
                raise BusinessLogicError("Auto-marking is not enabled for this hostel")

            # Use policy cutoff time if not provided
            if cutoff_time is None:
                if not policy.auto_mark_absent_after_time:
                    raise BusinessLogicError("No cutoff time configured for auto-marking")
                cutoff_time = policy.auto_mark_absent_after_time

            # Check if current time has passed cutoff
            current_time = datetime.now().time()
            if current_time < cutoff_time:
                raise BusinessLogicError(
                    f"Auto-marking can only be done after {cutoff_time}"
                )

            # Get all students who don't have attendance marked
            # This would require a student repository - simplified here
            # In practice, you'd fetch all active students and check against marked attendance
            
            logger.info(
                f"Auto-marking absent for hostel {hostel_id} on {attendance_date} "
                f"after cutoff time {cutoff_time}"
            )

            # Placeholder - actual implementation would mark unmarked students as absent
            return {
                "hostel_id": str(hostel_id),
                "attendance_date": attendance_date,
                "cutoff_time": str(cutoff_time),
                "auto_marked_count": 0,
                "message": "Auto-marking feature requires student roster integration",
            }

        except Exception as e:
            logger.error(f"Error in auto-marking: {str(e)}")
            raise

    # ==================== Validation Helpers ====================

    def validate_attendance_date(
        self,
        attendance_date: date,
        hostel_id: UUID,
        allow_future: bool = False,
        allow_weekends: Optional[bool] = None,
        allow_holidays: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Validate if attendance can be marked for given date.

        Args:
            attendance_date: Date to validate
            hostel_id: Hostel identifier
            allow_future: Allow future dates
            allow_weekends: Override weekend policy
            allow_holidays: Override holiday policy

        Returns:
            Validation result dictionary
        """
        policy = self.policy_repo.get_by_hostel(hostel_id)
        
        validation = {
            "valid": True,
            "warnings": [],
            "errors": [],
        }

        # Check future date
        if not allow_future and attendance_date > date.today():
            validation["valid"] = False
            validation["errors"].append("Cannot mark attendance for future dates")

        # Check weekend
        is_weekend = attendance_date.weekday() >= 5  # Saturday=5, Sunday=6
        if is_weekend:
            track_weekends = allow_weekends if allow_weekends is not None else (
                policy.track_weekend_attendance if policy else False
            )
            if not track_weekends:
                validation["warnings"].append("Weekend attendance tracking is disabled")

        # Check holiday (would require holiday calendar integration)
        # Simplified here
        if policy and not policy.track_holiday_attendance:
            validation["warnings"].append("Holiday attendance tracking may be disabled")

        return validation

    # ==================== Private Helper Methods ====================

    def _calculate_late_status(
        self,
        check_in_time: time,
        policy: Any,
        attendance_date: date,
    ) -> Dict[str, Any]:
        """
        Calculate late status based on policy.

        Args:
            check_in_time: Check-in time
            policy: Attendance policy
            attendance_date: Date of attendance

        Returns:
            Dictionary with late status and minutes
        """
        # This would typically use hostel's configured start time
        # Simplified to use a default of 9:00 AM
        standard_start_time = time(9, 0)

        # Calculate minutes difference
        check_in_datetime = datetime.combine(attendance_date, check_in_time)
        standard_datetime = datetime.combine(attendance_date, standard_start_time)
        
        time_diff = check_in_datetime - standard_datetime
        late_minutes = int(time_diff.total_seconds() / 60)

        # Apply grace period
        effective_late_minutes = max(0, late_minutes - policy.grace_period_minutes)

        is_late = effective_late_minutes >= policy.late_entry_threshold_minutes

        return {
            "is_late": is_late,
            "late_minutes": effective_late_minutes if is_late else None,
            "raw_late_minutes": late_minutes,
            "grace_period_applied": policy.grace_period_minutes,
        }

    def _check_policy_violations_and_alert(
        self,
        student_id: UUID,
        hostel_id: UUID,
        attendance_record: AttendanceRecord,
        policy: Any,
    ) -> None:
        """
        Check for policy violations and generate alerts.

        Args:
            student_id: Student identifier
            hostel_id: Hostel identifier
            attendance_record: Attendance record
            policy: Attendance policy
        """
        try:
            # Check consecutive absences
            if attendance_record.status == AttendanceStatus.ABSENT:
                self._check_consecutive_absence_violation(
                    student_id=student_id,
                    hostel_id=hostel_id,
                    policy=policy,
                )

            # Check late entries
            if attendance_record.is_late:
                self._check_late_entry_violation(
                    student_id=student_id,
                    hostel_id=hostel_id,
                    policy=policy,
                    attendance_date=attendance_record.attendance_date,
                )

            # Check overall attendance percentage
            self._check_attendance_percentage_violation(
                student_id=student_id,
                hostel_id=hostel_id,
                policy=policy,
            )

        except Exception as e:
            logger.error(f"Error checking policy violations: {str(e)}")
            # Don't fail the main operation if alert generation fails

    def _check_consecutive_absence_violation(
        self,
        student_id: UUID,
        hostel_id: UUID,
        policy: Any,
    ) -> None:
        """Check and create violation for consecutive absences."""
        streaks = self.attendance_repo.find_consecutive_absences(
            student_id=student_id,
            min_consecutive_days=policy.consecutive_absence_alert_days,
        )

        if streaks:
            current_streak = streaks[0]  # Most recent streak
            consecutive_days = len(current_streak)

            # Create policy violation
            violation_check = self.policy_repo.check_consecutive_absence_violation(
                hostel_id=hostel_id,
                consecutive_days=consecutive_days,
            )

            if violation_check["violation"]:
                self.policy_repo.create_violation(
                    policy_id=policy.id,
                    student_id=student_id,
                    violation_type="consecutive_absence",
                    severity="high" if consecutive_days >= 5 else "medium",
                    violation_date=date.today(),
                    consecutive_absences=consecutive_days,
                )

    def _check_late_entry_violation(
        self,
        student_id: UUID,
        hostel_id: UUID,
        policy: Any,
        attendance_date: date,
    ) -> None:
        """Check and create violation for late entries."""
        # Count late entries this month
        month_start = attendance_date.replace(day=1)
        month_end = attendance_date

        late_entries = self.attendance_repo.find_late_entries(
            hostel_id=hostel_id,
            start_date=month_start,
            end_date=month_end,
        )

        student_late_count = sum(
            1 for entry in late_entries if entry.student_id == student_id
        )

        if student_late_count >= policy.grace_days_per_month:
            self.policy_repo.create_violation(
                policy_id=policy.id,
                student_id=student_id,
                violation_type="excessive_late_entries",
                severity="medium",
                violation_date=attendance_date,
                late_entries_this_month=student_late_count,
            )

    def _check_attendance_percentage_violation(
        self,
        student_id: UUID,
        hostel_id: UUID,
        policy: Any,
    ) -> None:
        """Check and create violation for low attendance percentage."""
        # Calculate current month attendance
        today = date.today()
        month_start = today.replace(day=1)

        percentage = self.attendance_repo.calculate_attendance_percentage(
            student_id=student_id,
            start_date=month_start,
            end_date=today,
        )

        if percentage < policy.minimum_attendance_percentage:
            self.policy_repo.create_violation(
                policy_id=policy.id,
                student_id=student_id,
                violation_type="low_attendance",
                severity="critical" if percentage < 60 else "high",
                violation_date=today,
                current_attendance_percentage=percentage,
                required_attendance_percentage=policy.minimum_attendance_percentage,
            )