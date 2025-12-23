"""
Core attendance service for marking and listing attendance.

Handles:
- Single and bulk attendance marking
- Quick mark-all operations
- Attendance record updates
- Querying and filtering
- Daily summaries and student history
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime
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
from app.schemas.attendance.attendance_record import (
    AttendanceRecordRequest,
    StudentAttendanceRecord,
    BulkAttendanceRequest,
    AttendanceCorrection,
    QuickAttendanceMarkAll,
)
from app.schemas.attendance.attendance_response import (
    AttendanceResponse,
    AttendanceDetail,
    AttendanceListItem,
    DailyAttendanceSummary,
)
from app.schemas.attendance.attendance_filters import AttendanceFilterParams
from app.models.base.enums import AttendanceStatus, AttendanceMode

logger = logging.getLogger(__name__)


class AttendanceService(BaseService[AttendanceRecordModel, AttendanceRecordRepository]):
    """
    Service for marking attendance (single/bulk/quick) and listing/summaries.
    
    Responsibilities:
    - Create and update attendance records
    - Bulk operations with transaction safety
    - Query attendance with flexible filters
    - Generate daily and student-specific summaries
    """

    def __init__(self, repository: AttendanceRecordRepository, db_session: Session):
        """
        Initialize attendance service.
        
        Args:
            repository: AttendanceRecordRepository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._operation_context = "AttendanceService"

    # =========================================================================
    # Marking Operations
    # =========================================================================

    def mark_attendance(
        self,
        request: AttendanceRecordRequest,
    ) -> ServiceResult[AttendanceResponse]:
        """
        Mark attendance for a single student on a specific date.
        
        Args:
            request: Attendance record request with student, date, and status
            
        Returns:
            ServiceResult containing AttendanceResponse or error
            
        Raises:
            Handles all exceptions and returns ServiceResult.failure
        """
        operation = "mark_attendance"
        logger.info(
            f"{operation}: student_id={request.student_id}, "
            f"date={request.attendance_date}, status={request.status}"
        )
        
        try:
            # Validate request data
            validation_result = self._validate_attendance_request(request)
            if not validation_result.success:
                return validation_result
            
            # Create attendance record
            record = self.repository.create_record(request)
            self.db.commit()
            
            # Convert to response schema
            resp = self.repository.to_response(record.id)
            
            logger.info(
                f"{operation} successful: record_id={record.id}, "
                f"student_id={request.student_id}"
            )
            
            return ServiceResult.success(
                resp,
                message="Attendance marked successfully",
                metadata={
                    "record_id": str(record.id),
                    "student_id": str(request.student_id),
                    "attendance_date": str(request.attendance_date)
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while marking attendance: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"student_id": str(request.student_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, request.student_id)

    def bulk_mark_attendance(
        self,
        request: BulkAttendanceRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Mark attendance for multiple students with defaults and overrides.
        
        Uses transaction management to ensure atomicity or partial rollback
        depending on configuration.
        
        Args:
            request: Bulk attendance request with student list and defaults
            
        Returns:
            ServiceResult with success/failure counts and error details
        """
        operation = "bulk_mark_attendance"
        logger.info(
            f"{operation}: hostel_id={request.hostel_id}, "
            f"date={request.attendance_date}, "
            f"student_count={len(request.students)}"
        )
        
        try:
            # Validate bulk request
            if not request.students:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="No students provided for bulk marking",
                        severity=ErrorSeverity.WARNING,
                        details={"hostel_id": str(request.hostel_id)}
                    )
                )
            
            # Execute bulk marking
            result = self.repository.bulk_mark(request)
            self.db.commit()
            
            response_data = {
                "total": result.total,
                "successful": result.successful,
                "failed": result.failed,
                "errors": result.errors,
                "success_rate": (
                    (result.successful / result.total * 100) 
                    if result.total > 0 else 0
                )
            }
            
            logger.info(
                f"{operation} completed: total={result.total}, "
                f"successful={result.successful}, failed={result.failed}"
            )
            
            # Determine success/warning based on failure rate
            if result.failed == 0:
                return ServiceResult.success(
                    response_data,
                    message="All attendance records marked successfully"
                )
            elif result.successful > 0:
                return ServiceResult.success(
                    response_data,
                    message=f"Bulk attendance processed with {result.failed} failures",
                    metadata={"partial_success": True}
                )
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="All bulk attendance marking failed",
                        severity=ErrorSeverity.ERROR,
                        details=response_data
                    )
                )
                
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error during bulk marking: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(request.hostel_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, request.hostel_id)

    def quick_mark_all(
        self,
        request: QuickAttendanceMarkAll,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Quickly mark all students present with exceptions for absent/late students.
        
        Optimized operation for hostel-wide attendance marking.
        
        Args:
            request: Quick mark request with default status and exceptions
            
        Returns:
            ServiceResult with summary of marking operation
        """
        operation = "quick_mark_all"
        logger.info(
            f"{operation}: hostel_id={request.hostel_id}, "
            f"date={request.attendance_date}, "
            f"default_status={request.default_status}, "
            f"exceptions_count={len(request.exceptions) if request.exceptions else 0}"
        )
        
        try:
            # Execute quick mark all
            summary = self.repository.quick_mark_all(request)
            self.db.commit()
            
            logger.info(
                f"{operation} completed: marked={summary.get('total_marked', 0)}, "
                f"exceptions={summary.get('exceptions_applied', 0)}"
            )
            
            return ServiceResult.success(
                summary,
                message="Quick mark all completed successfully",
                metadata={
                    "hostel_id": str(request.hostel_id),
                    "attendance_date": str(request.attendance_date)
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error during quick mark all: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(request.hostel_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, request.hostel_id)

    # =========================================================================
    # Update Operations
    # =========================================================================

    def update_record_status(
        self,
        record_id: UUID,
        status: AttendanceStatus,
        notes: Optional[str] = None,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[AttendanceResponse]:
        """
        Update the status and notes of an existing attendance record.
        
        Typically used for administrative corrections or updates.
        
        Args:
            record_id: UUID of attendance record to update
            status: New attendance status
            notes: Optional notes explaining the update
            updated_by: UUID of user making the update
            
        Returns:
            ServiceResult containing updated AttendanceResponse
        """
        operation = "update_record_status"
        logger.info(
            f"{operation}: record_id={record_id}, "
            f"new_status={status}, updated_by={updated_by}"
        )
        
        try:
            # Build update data
            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow()
            }
            
            if notes is not None:
                update_data["notes"] = notes
                
            if updated_by is not None:
                update_data["updated_by"] = updated_by
            
            # Update record
            updated = self.repository.update(record_id, update_data)
            
            if not updated:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Attendance record not found: {record_id}",
                        severity=ErrorSeverity.WARNING,
                        details={"record_id": str(record_id)}
                    )
                )
            
            self.db.commit()
            
            # Convert to response
            resp = self.repository.to_response(record_id)
            
            logger.info(f"{operation} successful: record_id={record_id}")
            
            return ServiceResult.success(
                resp,
                message="Attendance record updated successfully",
                metadata={"record_id": str(record_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while updating record: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"record_id": str(record_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, record_id)

    # =========================================================================
    # Query Operations
    # =========================================================================

    def list_attendance(
        self,
        filters: AttendanceFilterParams,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[List[AttendanceListItem]]:
        """
        List attendance records with flexible filtering and pagination.
        
        Args:
            filters: Filter parameters (hostel, student, date range, status, etc.)
            page: Page number (1-indexed)
            page_size: Number of records per page
            
        Returns:
            ServiceResult containing list of AttendanceListItem
        """
        operation = "list_attendance"
        logger.debug(
            f"{operation}: page={page}, page_size={page_size}, "
            f"filters={filters.dict(exclude_none=True)}"
        )
        
        try:
            # Validate pagination
            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 50
            if page_size > 1000:
                page_size = 1000  # Prevent excessive data retrieval
            
            # Query with filters
            items = self.repository.list_by_filters(
                filters,
                page=page,
                page_size=page_size
            )
            
            logger.debug(f"{operation} returned {len(items)} items")
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "page": page,
                    "page_size": page_size,
                    "has_more": len(items) == page_size
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while listing attendance: {str(e)}",
                    severity=ErrorSeverity.ERROR
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation)

    def get_daily_summary(
        self,
        hostel_id: UUID,
        attendance_date: date,
    ) -> ServiceResult[DailyAttendanceSummary]:
        """
        Get hostel-level daily attendance summary.
        
        Includes totals, percentages, and completion status.
        
        Args:
            hostel_id: UUID of hostel
            attendance_date: Date for summary
            
        Returns:
            ServiceResult containing DailyAttendanceSummary
        """
        operation = "get_daily_summary"
        logger.debug(
            f"{operation}: hostel_id={hostel_id}, "
            f"attendance_date={attendance_date}"
        )
        
        try:
            summary = self.repository.get_daily_summary(hostel_id, attendance_date)
            
            if not summary:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No attendance data found for {attendance_date}",
                        severity=ErrorSeverity.INFO,
                        details={
                            "hostel_id": str(hostel_id),
                            "attendance_date": str(attendance_date)
                        }
                    )
                )
            
            logger.debug(
                f"{operation} successful: total={summary.total_students}, "
                f"present={summary.present_count}"
            )
            
            return ServiceResult.success(
                summary,
                metadata={
                    "hostel_id": str(hostel_id),
                    "attendance_date": str(attendance_date)
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while fetching daily summary: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def get_student_attendance(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[List[AttendanceDetail]]:
        """
        Get detailed attendance history for a specific student.
        
        Args:
            student_id: UUID of student
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            ServiceResult containing list of AttendanceDetail
        """
        operation = "get_student_attendance"
        logger.debug(
            f"{operation}: student_id={student_id}, "
            f"start_date={start_date}, end_date={end_date}"
        )
        
        try:
            # Validate date range
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
            
            # Query student attendance
            result = self.repository.get_student_attendance(
                student_id,
                start_date,
                end_date
            )
            
            logger.debug(
                f"{operation} returned {len(result)} records for student {student_id}"
            )
            
            return ServiceResult.success(
                result,
                metadata={
                    "count": len(result),
                    "student_id": str(student_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date)
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while fetching student attendance: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"student_id": str(student_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, student_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_attendance_request(
        self,
        request: AttendanceRecordRequest
    ) -> ServiceResult[None]:
        """
        Validate attendance record request.
        
        Args:
            request: AttendanceRecordRequest to validate
            
        Returns:
            ServiceResult indicating validation success/failure
        """
        # Check if attendance date is in the future
        if request.attendance_date > date.today():
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Cannot mark attendance for future dates",
                    severity=ErrorSeverity.WARNING,
                    details={"attendance_date": str(request.attendance_date)}
                )
            )
        
        # Additional business rule validations can be added here
        
        return ServiceResult.success(None)