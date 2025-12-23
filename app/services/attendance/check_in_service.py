"""
Check-in/out service for marking time and attendance mode.

Handles:
- Check-in operations with timestamp and device tracking
- Check-out operations
- Mode-based attendance (manual, biometric, RFID, geofence)
- Device metadata tracking
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
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
from app.repositories.attendance import AttendanceRecordRepository
from app.models.attendance.attendance_record import AttendanceRecord as AttendanceRecordModel
from app.models.base.enums import AttendanceMode, AttendanceStatus

logger = logging.getLogger(__name__)


class CheckInService(BaseService[AttendanceRecordModel, AttendanceRecordRepository]):
    """
    Service for check-in/check-out flows with device and mode metadata.
    
    Responsibilities:
    - Process check-in events with timestamp tracking
    - Process check-out events
    - Track attendance mode (manual, biometric, RFID, geofence)
    - Maintain device information for audit trails
    """

    def __init__(self, repository: AttendanceRecordRepository, db_session: Session):
        """
        Initialize check-in service.
        
        Args:
            repository: AttendanceRecordRepository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._operation_context = "CheckInService"

    def check_in(
        self,
        student_id: UUID,
        hostel_id: UUID,
        timestamp: Optional[datetime] = None,
        mode: AttendanceMode = AttendanceMode.MANUAL,
        device_info: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Mark check-in for student (creates or updates attendance record).
        
        Creates a new attendance record for the day if one doesn't exist,
        or updates existing record with check-in time.
        
        Args:
            student_id: UUID of student checking in
            hostel_id: UUID of hostel
            timestamp: Check-in timestamp (defaults to current UTC time)
            mode: Attendance mode (manual, biometric, RFID, geofence)
            device_info: Optional device metadata for audit trail
            notes: Optional notes for the check-in
            
        Returns:
            ServiceResult with check-in confirmation and record details
        """
        operation = "check_in"
        ts = timestamp or datetime.utcnow()
        
        logger.info(
            f"{operation}: student_id={student_id}, "
            f"hostel_id={hostel_id}, "
            f"timestamp={ts}, mode={mode.value}"
        )
        
        try:
            # Validate timestamp
            validation_result = self._validate_timestamp(ts, operation)
            if not validation_result.success:
                return validation_result
            
            # Sanitize device info
            sanitized_device_info = self._sanitize_device_info(device_info or {})
            
            # Execute check-in
            record = self.repository.mark_check_in(
                student_id=student_id,
                hostel_id=hostel_id,
                timestamp=ts,
                mode=mode.value,
                device_info=sanitized_device_info
            )
            
            self.db.commit()
            
            response_data = {
                "success": True,
                "record_id": str(record.id) if hasattr(record, 'id') else None,
                "student_id": str(student_id),
                "hostel_id": str(hostel_id),
                "check_in_time": ts.isoformat(),
                "mode": mode.value,
                "attendance_date": ts.date().isoformat(),
            }
            
            logger.info(
                f"{operation} successful: student_id={student_id}, "
                f"timestamp={ts}"
            )
            
            return ServiceResult.success(
                response_data,
                message="Check-in recorded successfully",
                metadata={
                    "operation": operation,
                    "mode": mode.value
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"{operation} database error for student {student_id}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error during check-in: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={
                        "student_id": str(student_id),
                        "hostel_id": str(hostel_id),
                        "timestamp": ts.isoformat()
                    }
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"{operation} unexpected error for student {student_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, operation, student_id)

    def check_out(
        self,
        student_id: UUID,
        hostel_id: UUID,
        timestamp: Optional[datetime] = None,
        mode: AttendanceMode = AttendanceMode.MANUAL,
        device_info: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Mark check-out for student (updates today's record).
        
        Updates the existing attendance record for the day with check-out time.
        
        Args:
            student_id: UUID of student checking out
            hostel_id: UUID of hostel
            timestamp: Check-out timestamp (defaults to current UTC time)
            mode: Attendance mode (manual, biometric, RFID, geofence)
            device_info: Optional device metadata for audit trail
            notes: Optional notes for the check-out
            
        Returns:
            ServiceResult with check-out confirmation and record details
        """
        operation = "check_out"
        ts = timestamp or datetime.utcnow()
        
        logger.info(
            f"{operation}: student_id={student_id}, "
            f"hostel_id={hostel_id}, "
            f"timestamp={ts}, mode={mode.value}"
        )
        
        try:
            # Validate timestamp
            validation_result = self._validate_timestamp(ts, operation)
            if not validation_result.success:
                return validation_result
            
            # Sanitize device info
            sanitized_device_info = self._sanitize_device_info(device_info or {})
            
            # Execute check-out
            record = self.repository.mark_check_out(
                student_id=student_id,
                hostel_id=hostel_id,
                timestamp=ts,
                mode=mode.value,
                device_info=sanitized_device_info
            )
            
            if not record:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No check-in record found for today",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "student_id": str(student_id),
                            "hostel_id": str(hostel_id),
                            "date": ts.date().isoformat()
                        }
                    )
                )
            
            self.db.commit()
            
            response_data = {
                "success": True,
                "record_id": str(record.id) if hasattr(record, 'id') else None,
                "student_id": str(student_id),
                "hostel_id": str(hostel_id),
                "check_out_time": ts.isoformat(),
                "mode": mode.value,
                "attendance_date": ts.date().isoformat(),
            }
            
            logger.info(
                f"{operation} successful: student_id={student_id}, "
                f"timestamp={ts}"
            )
            
            return ServiceResult.success(
                response_data,
                message="Check-out recorded successfully",
                metadata={
                    "operation": operation,
                    "mode": mode.value
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"{operation} database error for student {student_id}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error during check-out: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={
                        "student_id": str(student_id),
                        "hostel_id": str(hostel_id),
                        "timestamp": ts.isoformat()
                    }
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"{operation} unexpected error for student {student_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, operation, student_id)

    def get_check_in_status(
        self,
        student_id: UUID,
        hostel_id: UUID,
        check_date: Optional[date] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get current check-in/out status for a student.
        
        Args:
            student_id: UUID of student
            hostel_id: UUID of hostel
            check_date: Date to check (defaults to today)
            
        Returns:
            ServiceResult with check-in/out status details
        """
        operation = "get_check_in_status"
        check_date = check_date or date.today()
        
        logger.debug(
            f"{operation}: student_id={student_id}, "
            f"hostel_id={hostel_id}, date={check_date}"
        )
        
        try:
            status = self.repository.get_check_in_status(
                student_id=student_id,
                hostel_id=hostel_id,
                check_date=check_date
            )
            
            if not status:
                return ServiceResult.success(
                    {
                        "checked_in": False,
                        "checked_out": False,
                        "status": "no_record",
                        "date": check_date.isoformat()
                    },
                    message="No check-in record found for this date"
                )
            
            return ServiceResult.success(
                status,
                metadata={
                    "student_id": str(student_id),
                    "date": check_date.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"{operation} error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, student_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_timestamp(
        self,
        timestamp: datetime,
        operation: str
    ) -> ServiceResult[None]:
        """
        Validate check-in/out timestamp.
        
        Args:
            timestamp: Timestamp to validate
            operation: Operation name for error context
            
        Returns:
            ServiceResult indicating validation success/failure
        """
        now = datetime.utcnow()
        
        # Check if timestamp is in the future (with 5-minute tolerance for clock skew)
        if timestamp > now + timedelta(minutes=5):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Cannot {operation.replace('_', ' ')} with future timestamp",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "timestamp": timestamp.isoformat(),
                        "current_time": now.isoformat()
                    }
                )
            )
        
        # Check if timestamp is too old (e.g., more than 7 days)
        max_age_days = 7
        if timestamp < now - timedelta(days=max_age_days):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Timestamp is too old (max {max_age_days} days)",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "timestamp": timestamp.isoformat(),
                        "max_age_days": max_age_days
                    }
                )
            )
        
        return ServiceResult.success(None)

    def _sanitize_device_info(self, device_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize and validate device information.
        
        Args:
            device_info: Raw device information dictionary
            
        Returns:
            Sanitized device information dictionary
        """
        allowed_fields = {
            'device_id',
            'device_type',
            'device_model',
            'os_version',
            'app_version',
            'ip_address',
            'location',
            'user_agent',
        }
        
        sanitized = {
            k: v for k, v in device_info.items()
            if k in allowed_fields and v is not None
        }
        
        # Add timestamp
        sanitized['recorded_at'] = datetime.utcnow().isoformat()
        
        return sanitized