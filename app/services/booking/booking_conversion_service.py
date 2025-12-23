"""
Booking conversion to student service.

Enhanced with:
- Pre-conversion validation
- Rollback safety
- Data migration integrity
- Audit trail
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingConversionRepository
from app.models.booking.booking_conversion import BookingConversion as BookingConversionModel
from app.schemas.booking.booking_conversion import (
    ConvertToStudentRequest,
    ConversionResponse,
    ConversionChecklist,
    ConversionRollback,
    ChecklistItem,
)

logger = logging.getLogger(__name__)


class BookingConversionService(BaseService[BookingConversionModel, BookingConversionRepository]):
    """
    Convert a confirmed booking into a student/resident profile and manage rollback.
    
    Features:
    - Pre-conversion validation checklist
    - Safe conversion with rollback capability
    - Data integrity verification
    - Audit trail maintenance
    """

    def __init__(self, repository: BookingConversionRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_conversion_request(self, request: ConvertToStudentRequest) -> Optional[ServiceError]:
        """Validate conversion request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )
        
        # Validate student information if provided
        if hasattr(request, 'student_info') and request.student_info:
            if hasattr(request.student_info, 'email'):
                email = request.student_info.email
                if not email or '@' not in email:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Valid email is required for student profile",
                        severity=ErrorSeverity.ERROR,
                        details={"email": email}
                    )
        
        return None

    def _validate_rollback_request(self, request: ConversionRollback) -> Optional[ServiceError]:
        """Validate rollback request."""
        if not request.student_profile_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Student profile ID is required",
                severity=ErrorSeverity.ERROR
            )
        
        if hasattr(request, 'reason') and request.reason:
            if len(request.reason.strip()) < 10:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Rollback reason must be at least 10 characters",
                    severity=ErrorSeverity.ERROR,
                    details={"reason_length": len(request.reason.strip())}
                )
        
        return None

    # -------------------------------------------------------------------------
    # Conversion Operations
    # -------------------------------------------------------------------------

    def convert(
        self,
        request: ConvertToStudentRequest,
    ) -> ServiceResult[ConversionResponse]:
        """
        Convert booking to student profile.
        
        Args:
            request: Conversion request data
            
        Returns:
            ServiceResult containing ConversionResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_conversion_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Converting booking {request.booking_id} to student profile",
                extra={
                    "booking_id": str(request.booking_id),
                    "converted_by": str(request.converted_by) if hasattr(request, 'converted_by') else None
                }
            )

            # Check conversion eligibility
            checklist_result = self.get_checklist(request.booking_id)
            if not checklist_result.success:
                return checklist_result

            checklist = checklist_result.data
            if not self._is_conversion_ready(checklist):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Booking is not ready for conversion",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "booking_id": str(request.booking_id),
                            "incomplete_items": self._get_incomplete_items(checklist)
                        }
                    )
                )

            start_time = datetime.utcnow()

            # Execute conversion
            response = self.repository.convert(request)
            
            # Commit transaction
            self.db.commit()
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Successfully converted booking {request.booking_id} to student profile",
                extra={
                    "booking_id": str(request.booking_id),
                    "student_profile_id": str(response.student_profile_id) if hasattr(response, 'student_profile_id') else None,
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                response,
                message="Booking converted to student profile successfully",
                metadata={"duration_ms": duration_ms}
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error during conversion: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Conversion conflicts with existing data",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(request.booking_id), "error": str(e)}
                )
            )
        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error during conversion: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(request.booking_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during conversion: {str(e)}", exc_info=True)
            return self._handle_exception(e, "convert booking", request.booking_id)

    # -------------------------------------------------------------------------
    # Checklist Operations
    # -------------------------------------------------------------------------

    def get_checklist(
        self,
        booking_id: UUID,
    ) -> ServiceResult[ConversionChecklist]:
        """
        Get conversion checklist for validation.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing ConversionChecklist or error
        """
        try:
            self._logger.debug(f"Fetching conversion checklist for booking {booking_id}")
            
            checklist = self.repository.get_checklist(booking_id)
            
            if not checklist:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Booking not found",
                        severity=ErrorSeverity.ERROR,
                        details={"booking_id": str(booking_id)}
                    )
                )

            # Add completion status
            total_items = len(checklist.items) if hasattr(checklist, 'items') else 0
            completed_items = sum(
                1 for item in checklist.items
                if hasattr(item, 'completed') and item.completed
            ) if hasattr(checklist, 'items') else 0

            return ServiceResult.success(
                checklist,
                metadata={
                    "total_items": total_items,
                    "completed_items": completed_items,
                    "ready_for_conversion": self._is_conversion_ready(checklist)
                }
            )

        except Exception as e:
            self._logger.error(f"Error fetching conversion checklist: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get conversion checklist", booking_id)

    def _is_conversion_ready(self, checklist: ConversionChecklist) -> bool:
        """Check if all required checklist items are completed."""
        if not hasattr(checklist, 'items') or not checklist.items:
            return False
        
        for item in checklist.items:
            if hasattr(item, 'required') and item.required:
                if not hasattr(item, 'completed') or not item.completed:
                    return False
        
        return True

    def _get_incomplete_items(self, checklist: ConversionChecklist) -> List[str]:
        """Get list of incomplete checklist items."""
        incomplete = []
        if hasattr(checklist, 'items') and checklist.items:
            for item in checklist.items:
                if hasattr(item, 'completed') and not item.completed:
                    item_name = item.name if hasattr(item, 'name') else "Unknown item"
                    incomplete.append(item_name)
        return incomplete

    def update_checklist_item(
        self,
        booking_id: UUID,
        item_id: UUID,
        completed: bool,
        notes: Optional[str] = None,
    ) -> ServiceResult[ConversionChecklist]:
        """
        Update a checklist item status.
        
        Args:
            booking_id: UUID of booking
            item_id: UUID of checklist item
            completed: Completion status
            notes: Optional notes
            
        Returns:
            ServiceResult containing updated ConversionChecklist
        """
        try:
            self._logger.info(
                f"Updating checklist item {item_id} for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "item_id": str(item_id),
                    "completed": completed
                }
            )

            updated_checklist = self.repository.update_checklist_item(
                booking_id,
                item_id,
                completed,
                notes=notes
            )

            self.db.commit()

            return ServiceResult.success(
                updated_checklist,
                message="Checklist item updated"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error updating checklist item: {str(e)}", exc_info=True)
            return self._handle_exception(e, "update checklist item", booking_id)

    # -------------------------------------------------------------------------
    # Rollback Operations
    # -------------------------------------------------------------------------

    def rollback(
        self,
        request: ConversionRollback,
    ) -> ServiceResult[bool]:
        """
        Rollback a conversion.
        
        Args:
            request: Rollback request data
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            # Validate request
            validation_error = self._validate_rollback_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.warning(
                f"Rolling back conversion for student profile {request.student_profile_id}",
                extra={
                    "student_profile_id": str(request.student_profile_id),
                    "reason": request.reason if hasattr(request, 'reason') else None,
                    "rolled_back_by": str(request.rolled_back_by) if hasattr(request, 'rolled_back_by') else None
                }
            )

            start_time = datetime.utcnow()

            # Execute rollback
            ok = self.repository.rollback(request)
            
            # Commit transaction
            self.db.commit()
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if ok:
                self._logger.info(
                    f"Successfully rolled back conversion for student profile {request.student_profile_id}",
                    extra={
                        "student_profile_id": str(request.student_profile_id),
                        "duration_ms": duration_ms
                    }
                )
            else:
                self._logger.warning(
                    f"Rollback returned false for student profile {request.student_profile_id}",
                    extra={"student_profile_id": str(request.student_profile_id)}
                )

            return ServiceResult.success(
                ok,
                message="Conversion rolled back successfully" if ok else "Rollback failed",
                metadata={"duration_ms": duration_ms}
            )

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error during rollback: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"student_profile_id": str(request.student_profile_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during rollback: {str(e)}", exc_info=True)
            return self._handle_exception(e, "rollback conversion", request.student_profile_id)

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_conversion_history(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get conversion history for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            ServiceResult containing conversion history
        """
        try:
            self._logger.debug(
                f"Fetching conversion history for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            )

            history = self.repository.get_conversion_history(
                hostel_id,
                start_date=start_date,
                end_date=end_date
            )

            return ServiceResult.success(
                history,
                metadata={"count": len(history)}
            )

        except Exception as e:
            self._logger.error(f"Error fetching conversion history: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get conversion history", hostel_id)

    def get_conversion_statistics(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get conversion statistics for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing statistics
        """
        try:
            self._logger.debug(f"Fetching conversion statistics for hostel {hostel_id}")

            stats = self.repository.get_conversion_statistics(hostel_id)

            return ServiceResult.success(stats)

        except Exception as e:
            self._logger.error(f"Error fetching conversion statistics: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get conversion statistics", hostel_id)