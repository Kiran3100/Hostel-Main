"""
Booking modification service (dates, duration, room type; request & approve).

Enhanced with:
- Modification request validation
- Price difference calculation
- Approval workflow integration
- Modification history tracking
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, date
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingModificationRepository
from app.models.booking.booking_modification import BookingModification as BookingModificationModel
from app.schemas.booking.booking_modification import (
    ModificationRequest,
    ModificationResponse,
    DateChangeRequest,
    DurationChangeRequest,
    RoomTypeChangeRequest,
    ModificationApproval,
)

logger = logging.getLogger(__name__)


class BookingModificationService(BaseService[BookingModificationModel, BookingModificationRepository]):
    """
    Manage booking modification requests and approvals.
    
    Features:
    - Date change requests
    - Duration modification
    - Room type changes
    - Approval workflow
    - Price adjustment calculation
    """

    def __init__(self, repository: BookingModificationRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_modification_request(self, request: ModificationRequest) -> Optional[ServiceError]:
        """Validate general modification request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )

        if hasattr(request, 'reason') and request.reason:
            if len(request.reason.strip()) < 10:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Modification reason must be at least 10 characters",
                    severity=ErrorSeverity.ERROR,
                    details={"reason_length": len(request.reason.strip())}
                )

        return None

    def _validate_date_change_request(self, request: DateChangeRequest) -> Optional[ServiceError]:
        """Validate date change request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )

        # Validate new dates
        if hasattr(request, 'new_check_in_date') and hasattr(request, 'new_check_out_date'):
            if request.new_check_in_date and request.new_check_out_date:
                if request.new_check_in_date >= request.new_check_out_date:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Check-in date must be before check-out date",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "new_check_in": str(request.new_check_in_date),
                            "new_check_out": str(request.new_check_out_date)
                        }
                    )

                # Check minimum stay
                days_diff = (request.new_check_out_date - request.new_check_in_date).days
                if days_diff < 1:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Minimum stay is 1 day",
                        severity=ErrorSeverity.ERROR,
                        details={"days": days_diff}
                    )

        return None

    def _validate_duration_change_request(self, request: DurationChangeRequest) -> Optional[ServiceError]:
        """Validate duration change request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )

        if hasattr(request, 'new_duration_months') and request.new_duration_months is not None:
            if request.new_duration_months <= 0:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Duration must be positive",
                    severity=ErrorSeverity.ERROR,
                    details={"new_duration_months": request.new_duration_months}
                )

            if request.new_duration_months > 24:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Maximum duration is 24 months",
                    severity=ErrorSeverity.ERROR,
                    details={"new_duration_months": request.new_duration_months}
                )

        return None

    def _validate_room_type_change_request(self, request: RoomTypeChangeRequest) -> Optional[ServiceError]:
        """Validate room type change request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )

        if not hasattr(request, 'new_room_type') or not request.new_room_type:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="New room type is required",
                severity=ErrorSeverity.ERROR
            )

        return None

    def _validate_modification_approval(self, request: ModificationApproval) -> Optional[ServiceError]:
        """Validate modification approval request."""
        if not request.modification_request_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Modification request ID is required",
                severity=ErrorSeverity.ERROR
            )

        if hasattr(request, 'approved') and request.approved is None:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Approval decision is required",
                severity=ErrorSeverity.ERROR
            )

        # If rejected, require reason
        if hasattr(request, 'approved') and not request.approved:
            if not hasattr(request, 'rejection_reason') or not request.rejection_reason:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Rejection reason is required when rejecting modification",
                    severity=ErrorSeverity.ERROR
                )

        return None

    # -------------------------------------------------------------------------
    # Modification Request Operations
    # -------------------------------------------------------------------------

    def request_modification(
        self,
        request: ModificationRequest,
    ) -> ServiceResult[ModificationResponse]:
        """
        Request a general booking modification.
        
        Args:
            request: Modification request data
            
        Returns:
            ServiceResult containing ModificationResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_modification_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Requesting modification for booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "requested_by": str(request.requested_by) if hasattr(request, 'requested_by') else None
                }
            )

            # Execute modification request
            resp = self.repository.request_modification(request)

            # Commit transaction
            self.db.commit()

            self._logger.info(
                f"Successfully created modification request for booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "modification_id": str(resp.id) if hasattr(resp, 'id') else None
                }
            )

            return ServiceResult.success(
                resp,
                message="Modification request submitted successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error requesting modification: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Modification request conflicts with existing data",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(request.booking_id)}
                )
            )
        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error requesting modification: {str(e)}", exc_info=True)
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
            self._logger.error(f"Error requesting modification: {str(e)}", exc_info=True)
            return self._handle_exception(e, "request modification", request.booking_id)

    def change_date(
        self,
        request: DateChangeRequest,
    ) -> ServiceResult[ModificationResponse]:
        """
        Request a date change for a booking.
        
        Args:
            request: Date change request data
            
        Returns:
            ServiceResult containing ModificationResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_date_change_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Requesting date change for booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "new_check_in": str(request.new_check_in_date) if hasattr(request, 'new_check_in_date') else None,
                    "new_check_out": str(request.new_check_out_date) if hasattr(request, 'new_check_out_date') else None
                }
            )

            # Execute date change request
            resp = self.repository.request_date_change(request)

            # Commit transaction
            self.db.commit()

            self._logger.info(
                f"Successfully created date change request for booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "modification_id": str(resp.id) if hasattr(resp, 'id') else None
                }
            )

            return ServiceResult.success(
                resp,
                message="Date change request submitted successfully"
            )

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error requesting date change: {str(e)}", exc_info=True)
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
            self._logger.error(f"Error requesting date change: {str(e)}", exc_info=True)
            return self._handle_exception(e, "request date change", request.booking_id)

    def change_duration(
        self,
        request: DurationChangeRequest,
    ) -> ServiceResult[ModificationResponse]:
        """
        Request a duration change for a booking.
        
        Args:
            request: Duration change request data
            
        Returns:
            ServiceResult containing ModificationResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_duration_change_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Requesting duration change for booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "new_duration_months": request.new_duration_months if hasattr(request, 'new_duration_months') else None
                }
            )

            # Execute duration change request
            resp = self.repository.request_duration_change(request)

            # Commit transaction
            self.db.commit()

            self._logger.info(
                f"Successfully created duration change request for booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "modification_id": str(resp.id) if hasattr(resp, 'id') else None
                }
            )

            return ServiceResult.success(
                resp,
                message="Duration change request submitted successfully"
            )

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error requesting duration change: {str(e)}", exc_info=True)
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
            self._logger.error(f"Error requesting duration change: {str(e)}", exc_info=True)
            return self._handle_exception(e, "request duration change", request.booking_id)

    def change_room_type(
        self,
        request: RoomTypeChangeRequest,
    ) -> ServiceResult[ModificationResponse]:
        """
        Request a room type change for a booking.
        
        Args:
            request: Room type change request data
            
        Returns:
            ServiceResult containing ModificationResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_room_type_change_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Requesting room type change for booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "new_room_type": request.new_room_type if hasattr(request, 'new_room_type') else None
                }
            )

            # Execute room type change request
            resp = self.repository.request_room_type_change(request)

            # Commit transaction
            self.db.commit()

            self._logger.info(
                f"Successfully created room type change request for booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "modification_id": str(resp.id) if hasattr(resp, 'id') else None
                }
            )

            return ServiceResult.success(
                resp,
                message="Room type change request submitted successfully"
            )

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error requesting room type change: {str(e)}", exc_info=True)
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
            self._logger.error(f"Error requesting room type change: {str(e)}", exc_info=True)
            return self._handle_exception(e, "request room type change", request.booking_id)

    # -------------------------------------------------------------------------
    # Approval Operations
    # -------------------------------------------------------------------------

    def approve_modification(
        self,
        request: ModificationApproval,
    ) -> ServiceResult[ModificationResponse]:
        """
        Approve or reject a modification request.
        
        Args:
            request: Approval decision data
            
        Returns:
            ServiceResult containing ModificationResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_modification_approval(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            action = "Approving" if request.approved else "Rejecting"
            self._logger.info(
                f"{action} modification request {request.modification_request_id}",
                extra={
                    "modification_request_id": str(request.modification_request_id),
                    "approved": request.approved,
                    "approved_by": str(request.approved_by) if hasattr(request, 'approved_by') else None
                }
            )

            # Execute approval decision
            resp = self.repository.approve_modification(request)

            # Commit transaction
            self.db.commit()

            self._logger.info(
                f"Successfully {action.lower()} modification request {request.modification_request_id}",
                extra={
                    "modification_request_id": str(request.modification_request_id),
                    "approved": request.approved
                }
            )

            message = "Modification approved" if request.approved else "Modification rejected"
            return ServiceResult.success(resp, message=message)

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error approving modification: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"modification_request_id": str(request.modification_request_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error approving modification: {str(e)}", exc_info=True)
            return self._handle_exception(e, "approve modification", request.modification_request_id)

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_pending_modifications(
        self,
        hostel_id: Optional[UUID] = None,
        booking_id: Optional[UUID] = None,
    ) -> ServiceResult[List[ModificationResponse]]:
        """
        Get pending modification requests.
        
        Args:
            hostel_id: Optional hostel filter
            booking_id: Optional booking filter
            
        Returns:
            ServiceResult containing list of pending modifications
        """
        try:
            self._logger.debug(
                "Fetching pending modifications",
                extra={
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "booking_id": str(booking_id) if booking_id else None
                }
            )

            pending = self.repository.get_pending_modifications(
                hostel_id=hostel_id,
                booking_id=booking_id
            )

            return ServiceResult.success(
                pending,
                metadata={"count": len(pending)}
            )

        except Exception as e:
            self._logger.error(f"Error fetching pending modifications: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get pending modifications")

    def get_modification_history(
        self,
        booking_id: UUID,
    ) -> ServiceResult[List[ModificationResponse]]:
        """
        Get modification history for a booking.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing modification history
        """
        try:
            self._logger.debug(f"Fetching modification history for booking {booking_id}")

            history = self.repository.get_modification_history(booking_id)

            return ServiceResult.success(
                history,
                metadata={"count": len(history)}
            )

        except Exception as e:
            self._logger.error(f"Error fetching modification history: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get modification history", booking_id)

    def calculate_price_difference(
        self,
        modification_request_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Calculate price difference for a modification request.
        
        Args:
            modification_request_id: UUID of modification request
            
        Returns:
            ServiceResult containing price difference details
        """
        try:
            self._logger.debug(f"Calculating price difference for modification {modification_request_id}")

            price_diff = self.repository.calculate_price_difference(modification_request_id)

            return ServiceResult.success(price_diff)

        except Exception as e:
            self._logger.error(f"Error calculating price difference: {str(e)}", exc_info=True)
            return self._handle_exception(e, "calculate price difference", modification_request_id)