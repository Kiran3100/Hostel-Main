# --- File: app/repositories/attendance/attendance_record_repository.py ---
"""
Attendance record repository with comprehensive tracking and analytics.

Provides CRUD operations, bulk operations, corrections management,
and advanced querying for attendance records.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case, distinct, extract
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.attendance.attendance_record import (
    AttendanceRecord,
    AttendanceCorrection,
    BulkAttendanceLog,
)
from app.models.base.enums import AttendanceStatus, AttendanceMode
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationManager
from app.core.exceptions import ValidationError, NotFoundError


class AttendanceRecordRepository(BaseRepository[AttendanceRecord]):
    """
    Repository for attendance record operations with advanced querying.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy database session
        """
        super().__init__(AttendanceRecord, session)

    # ==================== Core CRUD Operations ====================

    def create_attendance(
        self,
        hostel_id: UUID,
        student_id: UUID,
        attendance_date: date,
        status: AttendanceStatus,
        marked_by: UUID,
        check_in_time: Optional[time] = None,
        check_out_time: Optional[time] = None,
        is_late: bool = False,
        late_minutes: Optional[int] = None,
        attendance_mode: AttendanceMode = AttendanceMode.MANUAL,
        notes: Optional[str] = None,
        location_lat: Optional[Decimal] = None,
        location_lng: Optional[Decimal] = None,
        device_info: Optional[Dict[str, Any]] = None,
        supervisor_id: Optional[UUID] = None,
    ) -> AttendanceRecord:
        """
        Create new attendance record with validation.

        Args:
            hostel_id: Hostel identifier
            student_id: Student identifier
            attendance_date: Date of attendance
            status: Attendance status
            marked_by: User who marked attendance
            check_in_time: Check-in time (optional)
            check_out_time: Check-out time (optional)
            is_late: Late arrival flag
            late_minutes: Minutes late
            attendance_mode: Mode of attendance marking
            notes: Additional notes
            location_lat: Latitude for geolocation
            location_lng: Longitude for geolocation
            device_info: Device information for mobile check-ins
            supervisor_id: Supervisor identifier (optional)

        Returns:
            Created attendance record

        Raises:
            ValidationError: If duplicate record exists or validation fails
        """
        # Check for duplicate
        existing = self._check_duplicate_attendance(student_id, attendance_date)
        if existing:
            raise ValidationError(
                f"Attendance record already exists for student {student_id} "
                f"on {attendance_date}"
            )

        # Validate late minutes
        if is_late and late_minutes is None:
            raise ValidationError("Late minutes must be provided when is_late is True")

        # Create record
        record = AttendanceRecord(
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

        self.session.add(record)
        self.session.flush()
        return record

    def update_attendance(
        self,
        attendance_id: UUID,
        **update_data: Any,
    ) -> AttendanceRecord:
        """
        Update attendance record.

        Args:
            attendance_id: Attendance record identifier
            **update_data: Fields to update

        Returns:
            Updated attendance record

        Raises:
            NotFoundError: If record not found
        """
        record = self.get_by_id(attendance_id)
        if not record:
            raise NotFoundError(f"Attendance record {attendance_id} not found")

        for key, value in update_data.items():
            if hasattr(record, key):
                setattr(record, key, value)

        self.session.flush()
        return record

    def get_by_id(
        self,
        attendance_id: UUID,
        load_relationships: bool = False,
    ) -> Optional[AttendanceRecord]:
        """
        Get attendance record by ID.

        Args:
            attendance_id: Attendance record identifier
            load_relationships: Whether to eager load relationships

        Returns:
            Attendance record if found
        """
        query = self.session.query(AttendanceRecord).filter(
            AttendanceRecord.id == attendance_id
        )

        if load_relationships:
            query = query.options(
                joinedload(AttendanceRecord.hostel),
                joinedload(AttendanceRecord.student),
                joinedload(AttendanceRecord.marked_by_user),
                selectinload(AttendanceRecord.corrections),
            )

        return query.first()

    # ==================== Bulk Operations ====================

    def create_bulk_attendance(
        self,
        hostel_id: UUID,
        attendance_date: date,
        student_ids: List[UUID],
        status: AttendanceStatus,
        marked_by: UUID,
        attendance_mode: AttendanceMode = AttendanceMode.BULK,
        batch_size: int = 100,
    ) -> BulkAttendanceLog:
        """
        Create attendance records in bulk with logging.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance
            student_ids: List of student identifiers
            status: Attendance status to set
            marked_by: User marking attendance
            attendance_mode: Mode of attendance marking
            batch_size: Number of records per batch

        Returns:
            Bulk operation log

        Raises:
            ValidationError: If validation fails
        """
        started_at = datetime.utcnow()
        total_students = len(student_ids)
        successful_count = 0
        failed_count = 0
        errors = {}

        try:
            # Process in batches
            for i in range(0, total_students, batch_size):
                batch = student_ids[i:i + batch_size]
                
                for student_id in batch:
                    try:
                        # Check for existing record
                        existing = self._check_duplicate_attendance(
                            student_id, attendance_date
                        )
                        if existing:
                            failed_count += 1
                            errors[str(student_id)] = "Duplicate record"
                            continue

                        # Create record
                        record = AttendanceRecord(
                            hostel_id=hostel_id,
                            student_id=student_id,
                            attendance_date=attendance_date,
                            status=status,
                            marked_by=marked_by,
                            attendance_mode=attendance_mode,
                        )
                        self.session.add(record)
                        successful_count += 1

                    except Exception as e:
                        failed_count += 1
                        errors[str(student_id)] = str(e)

                # Commit batch
                self.session.flush()

            completed_at = datetime.utcnow()
            execution_time_ms = int(
                (completed_at - started_at).total_seconds() * 1000
            )

            # Create log
            log = BulkAttendanceLog(
                hostel_id=hostel_id,
                marked_by=marked_by,
                attendance_date=attendance_date,
                operation_type="bulk_create",
                total_students=total_students,
                successful_count=successful_count,
                failed_count=failed_count,
                errors=errors if errors else None,
                execution_time_ms=execution_time_ms,
                started_at=started_at,
                completed_at=completed_at,
            )
            self.session.add(log)
            self.session.flush()

            return log

        except Exception as e:
            self.session.rollback()
            raise ValidationError(f"Bulk attendance creation failed: {str(e)}")

    def update_bulk_attendance(
        self,
        hostel_id: UUID,
        attendance_date: date,
        student_ids: List[UUID],
        update_data: Dict[str, Any],
        marked_by: UUID,
    ) -> BulkAttendanceLog:
        """
        Update multiple attendance records.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance
            student_ids: List of student identifiers
            update_data: Data to update
            marked_by: User performing update

        Returns:
            Bulk operation log
        """
        started_at = datetime.utcnow()
        total_students = len(student_ids)
        successful_count = 0
        failed_count = 0
        errors = {}

        try:
            for student_id in student_ids:
                try:
                    record = self.get_by_student_and_date(
                        student_id, attendance_date
                    )
                    if not record:
                        failed_count += 1
                        errors[str(student_id)] = "Record not found"
                        continue

                    for key, value in update_data.items():
                        if hasattr(record, key):
                            setattr(record, key, value)

                    successful_count += 1

                except Exception as e:
                    failed_count += 1
                    errors[str(student_id)] = str(e)

            self.session.flush()

            completed_at = datetime.utcnow()
            execution_time_ms = int(
                (completed_at - started_at).total_seconds() * 1000
            )

            # Create log
            log = BulkAttendanceLog(
                hostel_id=hostel_id,
                marked_by=marked_by,
                attendance_date=attendance_date,
                operation_type="bulk_update",
                total_students=total_students,
                successful_count=successful_count,
                failed_count=failed_count,
                errors=errors if errors else None,
                execution_time_ms=execution_time_ms,
                started_at=started_at,
                completed_at=completed_at,
            )
            self.session.add(log)
            self.session.flush()

            return log

        except Exception as e:
            self.session.rollback()
            raise ValidationError(f"Bulk attendance update failed: {str(e)}")

    # ==================== Query Operations ====================

    def get_by_student_and_date(
        self,
        student_id: UUID,
        attendance_date: date,
    ) -> Optional[AttendanceRecord]:
        """
        Get attendance record for specific student and date.

        Args:
            student_id: Student identifier
            attendance_date: Date of attendance

        Returns:
            Attendance record if found
        """
        return self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date == attendance_date,
            )
        ).first()

    def get_by_hostel_and_date(
        self,
        hostel_id: UUID,
        attendance_date: date,
        status_filter: Optional[AttendanceStatus] = None,
        include_relationships: bool = False,
    ) -> List[AttendanceRecord]:
        """
        Get all attendance records for hostel on specific date.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance
            status_filter: Optional status filter
            include_relationships: Whether to load relationships

        Returns:
            List of attendance records
        """
        query = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_date == attendance_date,
            )
        )

        if status_filter:
            query = query.filter(AttendanceRecord.status == status_filter)

        if include_relationships:
            query = query.options(
                joinedload(AttendanceRecord.student),
                joinedload(AttendanceRecord.marked_by_user),
            )

        return query.order_by(AttendanceRecord.created_at.desc()).all()

    def get_student_attendance_range(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
        status_filter: Optional[List[AttendanceStatus]] = None,
    ) -> List[AttendanceRecord]:
        """
        Get student attendance records for date range.

        Args:
            student_id: Student identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            status_filter: Optional list of statuses to filter

        Returns:
            List of attendance records
        """
        query = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
        )

        if status_filter:
            query = query.filter(AttendanceRecord.status.in_(status_filter))

        return query.order_by(AttendanceRecord.attendance_date.asc()).all()

    def get_hostel_attendance_range(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AttendanceRecord], int]:
        """
        Get hostel attendance records for date range with pagination.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            page: Page number
            page_size: Records per page

        Returns:
            Tuple of (records, total_count)
        """
        query = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
        )

        total_count = query.count()

        records = query.order_by(
            AttendanceRecord.attendance_date.desc(),
            AttendanceRecord.created_at.desc(),
        ).limit(page_size).offset((page - 1) * page_size).all()

        return records, total_count

    def find_late_entries(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        min_late_minutes: int = 1,
    ) -> List[AttendanceRecord]:
        """
        Find all late entry records in date range.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            min_late_minutes: Minimum late minutes to include

        Returns:
            List of late attendance records
        """
        return self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
                AttendanceRecord.is_late == True,
                AttendanceRecord.late_minutes >= min_late_minutes,
            )
        ).order_by(
            AttendanceRecord.attendance_date.desc(),
            AttendanceRecord.late_minutes.desc(),
        ).all()

    def find_absent_students(
        self,
        hostel_id: UUID,
        attendance_date: date,
    ) -> List[AttendanceRecord]:
        """
        Find all absent students for specific date.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance

        Returns:
            List of absent attendance records
        """
        return self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_date == attendance_date,
                AttendanceRecord.status == AttendanceStatus.ABSENT,
            )
        ).options(joinedload(AttendanceRecord.student)).all()

    def find_consecutive_absences(
        self,
        student_id: UUID,
        min_consecutive_days: int = 3,
        end_date: Optional[date] = None,
    ) -> List[List[AttendanceRecord]]:
        """
        Find consecutive absence streaks for student.

        Args:
            student_id: Student identifier
            min_consecutive_days: Minimum consecutive days to report
            end_date: End date for search (default: today)

        Returns:
            List of absence streaks (each streak is a list of records)
        """
        if end_date is None:
            end_date = date.today()

        start_date = end_date - timedelta(days=90)  # Look back 90 days

        records = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
                AttendanceRecord.status == AttendanceStatus.ABSENT,
            )
        ).order_by(AttendanceRecord.attendance_date.asc()).all()

        # Group consecutive absences
        streaks = []
        current_streak = []

        for i, record in enumerate(records):
            if not current_streak:
                current_streak.append(record)
            else:
                last_date = current_streak[-1].attendance_date
                current_date = record.attendance_date
                
                # Check if consecutive
                if (current_date - last_date).days == 1:
                    current_streak.append(record)
                else:
                    # Save streak if meets minimum
                    if len(current_streak) >= min_consecutive_days:
                        streaks.append(current_streak)
                    current_streak = [record]

        # Add last streak if meets minimum
        if len(current_streak) >= min_consecutive_days:
            streaks.append(current_streak)

        return streaks

    def get_by_mode(
        self,
        hostel_id: UUID,
        attendance_mode: AttendanceMode,
        start_date: date,
        end_date: date,
    ) -> List[AttendanceRecord]:
        """
        Get attendance records by marking mode.

        Args:
            hostel_id: Hostel identifier
            attendance_mode: Mode of attendance marking
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of attendance records
        """
        return self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_mode == attendance_mode,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
        ).order_by(AttendanceRecord.attendance_date.desc()).all()

    def get_corrected_records(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[AttendanceRecord]:
        """
        Get all corrected attendance records in date range.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of corrected attendance records
        """
        return self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.is_corrected == True,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
        ).options(selectinload(AttendanceRecord.corrections)).order_by(
            AttendanceRecord.attendance_date.desc()
        ).all()

    # ==================== Statistics and Analytics ====================

    def calculate_attendance_percentage(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
        exclude_on_leave: bool = True,
    ) -> Decimal:
        """
        Calculate attendance percentage for student in date range.

        Args:
            student_id: Student identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            exclude_on_leave: Whether to exclude leave days from calculation

        Returns:
            Attendance percentage
        """
        query = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
        )

        if exclude_on_leave:
            query = query.filter(
                AttendanceRecord.status != AttendanceStatus.ON_LEAVE
            )

        total_days = query.count()
        if total_days == 0:
            return Decimal("0.00")

        present_days = query.filter(
            AttendanceRecord.status == AttendanceStatus.PRESENT
        ).count()

        percentage = (Decimal(present_days) / Decimal(total_days)) * Decimal("100")
        return round(percentage, 2)

    def get_attendance_summary(
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
            Dictionary containing attendance statistics
        """
        records = self.get_student_attendance_range(
            student_id, start_date, end_date
        )

        total_days = len(records)
        present_count = sum(
            1 for r in records if r.status == AttendanceStatus.PRESENT
        )
        absent_count = sum(
            1 for r in records if r.status == AttendanceStatus.ABSENT
        )
        late_count = sum(1 for r in records if r.is_late)
        on_leave_count = sum(
            1 for r in records if r.status == AttendanceStatus.ON_LEAVE
        )
        half_day_count = sum(
            1 for r in records if r.status == AttendanceStatus.HALF_DAY
        )

        # Calculate percentage
        working_days = total_days - on_leave_count
        percentage = Decimal("0.00")
        if working_days > 0:
            percentage = (Decimal(present_count) / Decimal(working_days)) * Decimal("100")
            percentage = round(percentage, 2)

        # Calculate streaks
        current_streak = self._calculate_current_streak(records)
        longest_present_streak = self._calculate_longest_streak(
            records, AttendanceStatus.PRESENT
        )
        longest_absent_streak = self._calculate_longest_streak(
            records, AttendanceStatus.ABSENT
        )

        return {
            "total_days": total_days,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "on_leave_count": on_leave_count,
            "half_day_count": half_day_count,
            "attendance_percentage": float(percentage),
            "current_streak": current_streak,
            "longest_present_streak": longest_present_streak,
            "longest_absent_streak": longest_absent_streak,
        }

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
            Dictionary containing daily statistics
        """
        records = self.get_by_hostel_and_date(hostel_id, attendance_date)

        total_marked = len(records)
        present_count = sum(
            1 for r in records if r.status == AttendanceStatus.PRESENT
        )
        absent_count = sum(
            1 for r in records if r.status == AttendanceStatus.ABSENT
        )
        late_count = sum(1 for r in records if r.is_late)
        on_leave_count = sum(
            1 for r in records if r.status == AttendanceStatus.ON_LEAVE
        )

        percentage = Decimal("0.00")
        if total_marked > 0:
            percentage = (Decimal(present_count) / Decimal(total_marked)) * Decimal("100")
            percentage = round(percentage, 2)

        return {
            "date": attendance_date,
            "total_marked": total_marked,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "on_leave_count": on_leave_count,
            "attendance_percentage": float(percentage),
        }

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
            Dictionary containing late entry statistics
        """
        late_records = self.find_late_entries(
            hostel_id, start_date, end_date, min_late_minutes=1
        )

        if not late_records:
            return {
                "total_late_entries": 0,
                "average_late_minutes": 0,
                "max_late_minutes": 0,
                "min_late_minutes": 0,
            }

        total_late = len(late_records)
        late_minutes = [r.late_minutes for r in late_records if r.late_minutes]
        
        avg_late = sum(late_minutes) / len(late_minutes) if late_minutes else 0
        max_late = max(late_minutes) if late_minutes else 0
        min_late = min(late_minutes) if late_minutes else 0

        return {
            "total_late_entries": total_late,
            "average_late_minutes": round(avg_late, 2),
            "max_late_minutes": max_late,
            "min_late_minutes": min_late,
        }

    # ==================== Correction Management ====================

    def create_correction(
        self,
        attendance_id: UUID,
        corrected_by: UUID,
        corrected_status: AttendanceStatus,
        correction_reason: str,
        corrected_check_in_time: Optional[time] = None,
        corrected_check_out_time: Optional[time] = None,
        corrected_is_late: bool = False,
        corrected_late_minutes: Optional[int] = None,
        approved_by: Optional[UUID] = None,
    ) -> AttendanceCorrection:
        """
        Create correction record for attendance.

        Args:
            attendance_id: Attendance record identifier
            corrected_by: User making correction
            corrected_status: Corrected status
            correction_reason: Reason for correction
            corrected_check_in_time: Corrected check-in time
            corrected_check_out_time: Corrected check-out time
            corrected_is_late: Corrected late flag
            corrected_late_minutes: Corrected late minutes
            approved_by: Approver identifier

        Returns:
            Created correction record

        Raises:
            NotFoundError: If attendance record not found
            ValidationError: If correction validation fails
        """
        # Get original record
        original = self.get_by_id(attendance_id)
        if not original:
            raise NotFoundError(f"Attendance record {attendance_id} not found")

        # Create correction record
        correction = AttendanceCorrection(
            attendance_id=attendance_id,
            corrected_by=corrected_by,
            original_status=original.status,
            original_check_in_time=original.check_in_time,
            original_check_out_time=original.check_out_time,
            original_is_late=original.is_late,
            original_late_minutes=original.late_minutes,
            corrected_status=corrected_status,
            corrected_check_in_time=corrected_check_in_time,
            corrected_check_out_time=corrected_check_out_time,
            corrected_is_late=corrected_is_late,
            corrected_late_minutes=corrected_late_minutes,
            correction_reason=correction_reason,
            correction_timestamp=datetime.utcnow(),
            approved_by=approved_by,
            approved_at=datetime.utcnow() if approved_by else None,
        )

        self.session.add(correction)

        # Update original record
        original.status = corrected_status
        original.check_in_time = corrected_check_in_time
        original.check_out_time = corrected_check_out_time
        original.is_late = corrected_is_late
        original.late_minutes = corrected_late_minutes
        original.is_corrected = True
        original.correction_count += 1

        self.session.flush()
        return correction

    def get_correction_history(
        self,
        attendance_id: UUID,
    ) -> List[AttendanceCorrection]:
        """
        Get all corrections for attendance record.

        Args:
            attendance_id: Attendance record identifier

        Returns:
            List of corrections ordered by timestamp
        """
        return self.session.query(AttendanceCorrection).filter(
            AttendanceCorrection.attendance_id == attendance_id
        ).order_by(AttendanceCorrection.correction_timestamp.desc()).all()

    # ==================== Bulk Operation Logs ====================

    def get_bulk_operation_logs(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        operation_type: Optional[str] = None,
    ) -> List[BulkAttendanceLog]:
        """
        Get bulk operation logs with optional filters.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            operation_type: Operation type filter (optional)

        Returns:
            List of bulk operation logs
        """
        query = self.session.query(BulkAttendanceLog).filter(
            BulkAttendanceLog.hostel_id == hostel_id
        )

        if start_date:
            query = query.filter(BulkAttendanceLog.attendance_date >= start_date)
        if end_date:
            query = query.filter(BulkAttendanceLog.attendance_date <= end_date)
        if operation_type:
            query = query.filter(BulkAttendanceLog.operation_type == operation_type)

        return query.order_by(BulkAttendanceLog.started_at.desc()).all()

    # ==================== Helper Methods ====================

    def _check_duplicate_attendance(
        self,
        student_id: UUID,
        attendance_date: date,
    ) -> Optional[AttendanceRecord]:
        """Check if attendance record already exists."""
        return self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date == attendance_date,
            )
        ).first()

    def _calculate_current_streak(
        self,
        records: List[AttendanceRecord],
    ) -> int:
        """Calculate current attendance streak."""
        if not records:
            return 0

        # Sort by date descending
        sorted_records = sorted(
            records, key=lambda x: x.attendance_date, reverse=True
        )

        streak = 0
        for i, record in enumerate(sorted_records):
            if record.status != AttendanceStatus.PRESENT:
                break

            if i > 0:
                # Check if consecutive
                prev_date = sorted_records[i - 1].attendance_date
                curr_date = record.attendance_date
                if (prev_date - curr_date).days != 1:
                    break

            streak += 1

        return streak

    def _calculate_longest_streak(
        self,
        records: List[AttendanceRecord],
        status: AttendanceStatus,
    ) -> int:
        """Calculate longest streak for given status."""
        if not records:
            return 0

        # Sort by date ascending
        sorted_records = sorted(records, key=lambda x: x.attendance_date)

        max_streak = 0
        current_streak = 0

        for i, record in enumerate(sorted_records):
            if record.status == status:
                if i == 0:
                    current_streak = 1
                else:
                    # Check if consecutive
                    prev_date = sorted_records[i - 1].attendance_date
                    curr_date = record.attendance_date
                    if (curr_date - prev_date).days == 1 and \
                       sorted_records[i - 1].status == status:
                        current_streak += 1
                    else:
                        current_streak = 1
                
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        return max_streak

    def count_unmarked_students(
        self,
        hostel_id: UUID,
        attendance_date: date,
        total_students: int,
    ) -> int:
        """
        Count students without attendance record for date.

        Args:
            hostel_id: Hostel identifier
            attendance_date: Date of attendance
            total_students: Total active students in hostel

        Returns:
            Count of unmarked students
        """
        marked_count = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_date == attendance_date,
            )
        ).count()

        return total_students - marked_count