"""
Room/bed assignment service for bookings.

Enhanced with:
- Assignment conflict detection
- Assignment history tracking
- Bulk assignment optimization
- Capacity validation
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingAssignmentRepository
from app.models.booking.booking_assignment import BookingAssignment as BookingAssignmentModel
from app.schemas.booking.booking_assignment import (
    AssignmentRequest,
    AssignmentResponse,
    ReassignmentRequest,
    BulkAssignmentRequest,
    SingleAssignment,
)

logger = logging.getLogger(__name__)


class BookingAssignmentService(BaseService[BookingAssignmentModel, BookingAssignmentRepository]):
    """
    Handle booking room/bed assignments and history.
    
    Features:
    - Room/bed assignment
    - Assignment validation and conflict detection
    - Reassignment with history tracking
    - Bulk assignment operations
    """

    def __init__(self, repository: BookingAssignmentRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_assignment_request(self, request: AssignmentRequest) -> Optional[ServiceError]:
        """Validate assignment request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )
        
        # Validate that either room_id or bed_id is provided
        if hasattr(request, 'room_id') and hasattr(request, 'bed_id'):
            if not request.room_id and not request.bed_id:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Either room_id or bed_id must be provided",
                    severity=ErrorSeverity.ERROR
                )
        
        return None

    def _validate_reassignment_request(self, request: ReassignmentRequest) -> Optional[ServiceError]:
        """Validate reassignment request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )
        
        if not hasattr(request, 'reason') or not request.reason:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Reassignment reason is required",
                severity=ErrorSeverity.ERROR
            )
        
        if len(request.reason.strip()) < 10:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Reassignment reason must be at least 10 characters",
                severity=ErrorSeverity.ERROR
            )
        
        return None

    def _validate_bulk_assignment_request(self, request: BulkAssignmentRequest) -> Optional[ServiceError]:
        """Validate bulk assignment request."""
        if not request.assignments or len(request.assignments) == 0:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="At least one assignment is required",
                severity=ErrorSeverity.ERROR
            )
        
        if len(request.assignments) > 100:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Cannot assign more than 100 bookings at once",
                severity=ErrorSeverity.ERROR,
                details={"count": len(request.assignments)}
            )
        
        # Validate each assignment
        for idx, assignment in enumerate(request.assignments):
            if not assignment.booking_id:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Assignment {idx}: Booking ID is required",
                    severity=ErrorSeverity.ERROR
                )
        
        return None

    # -------------------------------------------------------------------------
    # Assignment Operations
    # -------------------------------------------------------------------------

    def assign(
        self,
        request: AssignmentRequest,
        assigned_by: Optional[UUID] = None,
    ) -> ServiceResult[AssignmentResponse]:
        """
        Assign room/bed to booking.
        
        Args:
            request: Assignment request data
            assigned_by: UUID of user performing assignment
            
        Returns:
            ServiceResult containing AssignmentResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_assignment_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Assigning room/bed to booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "room_id": str(request.room_id) if hasattr(request, 'room_id') and request.room_id else None,
                    "bed_id": str(request.bed_id) if hasattr(request, 'bed_id') and request.bed_id else None,
                    "assigned_by": str(assigned_by) if assigned_by else None
                }
            )

            # Execute assignment
            result = self.repository.assign(request, assigned_by=assigned_by)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully assigned room/bed to booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "assignment_id": str(result.id) if hasattr(result, 'id') else None
                }
            )

            return ServiceResult.success(
                result,
                message="Room/bed assigned successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error during assignment: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Assignment conflicts with existing allocation",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(request.booking_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during assignment: {str(e)}", exc_info=True)
            return self._handle_exception(e, "assign room/bed", request.booking_id)

    def reassign(
        self,
        request: ReassignmentRequest,
    ) -> ServiceResult[AssignmentResponse]:
        """
        Reassign booking to different room/bed.
        
        Args:
            request: Reassignment request data
            
        Returns:
            ServiceResult containing AssignmentResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_reassignment_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Reassigning booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "reason": request.reason,
                    "reassigned_by": str(request.reassigned_by) if hasattr(request, 'reassigned_by') else None
                }
            )

            # Execute reassignment
            result = self.repository.reassign(request)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully reassigned booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "new_assignment_id": str(result.id) if hasattr(result, 'id') else None
                }
            )

            return ServiceResult.success(
                result,
                message="Reassignment completed successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error during reassignment: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Reassignment conflicts with existing allocation",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(request.booking_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during reassignment: {str(e)}", exc_info=True)
            return self._handle_exception(e, "reassign room/bed", request.booking_id)

    def bulk_assign(
        self,
        request: BulkAssignmentRequest,
        assigned_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Assign multiple bookings in bulk.
        
        Args:
            request: Bulk assignment request
            assigned_by: UUID of user performing assignments
            
        Returns:
            ServiceResult containing summary dict or error
        """
        try:
            # Validate request
            validation_error = self._validate_bulk_assignment_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Bulk assigning {len(request.assignments)} bookings",
                extra={
                    "assignment_count": len(request.assignments),
                    "assigned_by": str(assigned_by) if assigned_by else None
                }
            )

            start_time = datetime.utcnow()

            # Execute bulk assignment
            summary = self.repository.bulk_assign(request, assigned_by=assigned_by)
            
            # Commit transaction
            self.db.commit()
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Bulk assignment completed: {summary.get('assigned', 0)} assigned, "
                f"{summary.get('failed', 0)} failed in {duration_ms:.2f}ms",
                extra={
                    "assigned": summary.get('assigned', 0),
                    "failed": summary.get('failed', 0),
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                summary,
                message=f"Bulk assignment completed: {summary.get('assigned', 0)} assigned, "
                        f"{summary.get('failed', 0)} failed",
                metadata={"duration_ms": duration_ms}
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during bulk assignment: {str(e)}", exc_info=True)
            return self._handle_exception(e, "bulk assign rooms")

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_assignment_history(
        self,
        booking_id: UUID,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get assignment history for a booking.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing assignment history or error
        """
        try:
            self._logger.debug(f"Fetching assignment history for booking {booking_id}")
            
            history = self.repository.get_assignment_history(booking_id)
            
            return ServiceResult.success(
                history,
                metadata={"count": len(history)}
            )

        except Exception as e:
            self._logger.error(f"Error fetching assignment history: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get assignment history", booking_id)

    def get_current_assignment(
        self,
        booking_id: UUID,
    ) -> ServiceResult[Optional[AssignmentResponse]]:
        """
        Get current assignment for a booking.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing current AssignmentResponse or None
        """
        try:
            self._logger.debug(f"Fetching current assignment for booking {booking_id}")
            
            assignment = self.repository.get_current_assignment(booking_id)
            
            return ServiceResult.success(assignment)

        except Exception as e:
            self._logger.error(f"Error fetching current assignment: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get current assignment", booking_id)

    def check_availability(
        self,
        room_id: Optional[UUID] = None,
        bed_id: Optional[UUID] = None,
        check_in_date: Optional[datetime] = None,
        check_out_date: Optional[datetime] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Check room/bed availability for given dates.
        
        Args:
            room_id: Optional room UUID
            bed_id: Optional bed UUID
            check_in_date: Check-in date
            check_out_date: Check-out date
            
        Returns:
            ServiceResult containing availability information
        """
        try:
            if not room_id and not bed_id:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Either room_id or bed_id must be provided",
                        severity=ErrorSeverity.ERROR
                    )
                )

            self._logger.debug(
                "Checking availability",
                extra={
                    "room_id": str(room_id) if room_id else None,
                    "bed_id": str(bed_id) if bed_id else None
                }
            )
            
            availability = self.repository.check_availability(
                room_id=room_id,
                bed_id=bed_id,
                check_in_date=check_in_date,
                check_out_date=check_out_date
            )
            
            return ServiceResult.success(availability)

        except Exception as e:
            self._logger.error(f"Error checking availability: {str(e)}", exc_info=True)
            return self._handle_exception(e, "check availability")