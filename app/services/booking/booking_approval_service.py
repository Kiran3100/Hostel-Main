"""
Booking approval workflow service.

Enhanced with:
- Workflow state validation
- Audit trail logging
- Bulk operation optimization
- Notification integration hooks
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingApprovalRepository
from app.models.booking.booking_approval import BookingApproval as BookingApprovalModel
from app.schemas.booking.booking_approval import (
    BookingApprovalRequest,
    ApprovalResponse,
    RejectionRequest,
    BulkApprovalRequest,
    ApprovalSettings,
)

logger = logging.getLogger(__name__)


class BookingApprovalService(BaseService[BookingApprovalModel, BookingApprovalRepository]):
    """
    Handle booking approvals, rejections, bulk approvals, and settings.
    
    Features:
    - Approval workflow management
    - Rejection with reason tracking
    - Bulk approval operations
    - Configurable approval settings
    - Audit trail logging
    """

    def __init__(self, repository: BookingApprovalRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_approval_request(self, request: BookingApprovalRequest) -> Optional[ServiceError]:
        """Validate approval request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )
        
        # Add additional business rule validations as needed
        return None

    def _validate_rejection_request(self, request: RejectionRequest) -> Optional[ServiceError]:
        """Validate rejection request."""
        if not request.booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )
        
        if not request.reason or len(request.reason.strip()) < 10:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Rejection reason must be at least 10 characters",
                severity=ErrorSeverity.ERROR,
                details={"reason_length": len(request.reason) if request.reason else 0}
            )
        
        return None

    def _validate_bulk_approval_request(self, request: BulkApprovalRequest) -> Optional[ServiceError]:
        """Validate bulk approval request."""
        if not request.booking_ids or len(request.booking_ids) == 0:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="At least one booking ID is required",
                severity=ErrorSeverity.ERROR
            )
        
        if len(request.booking_ids) > 100:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Cannot approve more than 100 bookings at once",
                severity=ErrorSeverity.ERROR,
                details={"count": len(request.booking_ids)}
            )
        
        return None

    # -------------------------------------------------------------------------
    # Approval Operations
    # -------------------------------------------------------------------------

    def approve(
        self,
        request: BookingApprovalRequest,
    ) -> ServiceResult[ApprovalResponse]:
        """
        Approve a booking.
        
        Args:
            request: Approval request data
            
        Returns:
            ServiceResult containing ApprovalResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_approval_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Approving booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "approved_by": str(request.approved_by) if hasattr(request, 'approved_by') else None
                }
            )

            # Execute approval
            response = self.repository.approve(request)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully approved booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "approval_id": str(response.id) if hasattr(response, 'id') else None
                }
            )

            return ServiceResult.success(
                response,
                message="Booking approved successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error approving booking: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Booking has already been processed",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(request.booking_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error approving booking: {str(e)}", exc_info=True)
            return self._handle_exception(e, "approve booking", request.booking_id)

    def reject(
        self,
        request: RejectionRequest,
    ) -> ServiceResult[ApprovalResponse]:
        """
        Reject a booking with reason.
        
        Args:
            request: Rejection request data
            
        Returns:
            ServiceResult containing ApprovalResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_rejection_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Rejecting booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "rejected_by": str(request.rejected_by) if hasattr(request, 'rejected_by') else None,
                    "reason": request.reason
                }
            )

            # Execute rejection
            response = self.repository.reject(request)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully rejected booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "rejection_id": str(response.id) if hasattr(response, 'id') else None
                }
            )

            return ServiceResult.success(
                response,
                message="Booking rejected"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error rejecting booking: {str(e)}", exc_info=True)
            return self._handle_exception(e, "reject booking", request.booking_id)

    def bulk_approve(
        self,
        request: BulkApprovalRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Approve multiple bookings in bulk.
        
        Args:
            request: Bulk approval request
            
        Returns:
            ServiceResult containing summary dict or error
        """
        try:
            # Validate request
            validation_error = self._validate_bulk_approval_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Bulk approving {len(request.booking_ids)} bookings",
                extra={
                    "booking_count": len(request.booking_ids),
                    "approved_by": str(request.approved_by) if hasattr(request, 'approved_by') else None
                }
            )

            start_time = datetime.utcnow()

            # Execute bulk approval
            summary = self.repository.bulk_approve(request)
            
            # Commit transaction
            self.db.commit()
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Bulk approval completed: {summary.get('approved', 0)} approved, "
                f"{summary.get('failed', 0)} failed in {duration_ms:.2f}ms",
                extra={
                    "approved": summary.get('approved', 0),
                    "failed": summary.get('failed', 0),
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                summary,
                message=f"Bulk approval completed: {summary.get('approved', 0)} approved, "
                        f"{summary.get('failed', 0)} failed",
                metadata={"duration_ms": duration_ms}
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during bulk approval: {str(e)}", exc_info=True)
            return self._handle_exception(e, "bulk approve bookings")

    # -------------------------------------------------------------------------
    # Settings Management
    # -------------------------------------------------------------------------

    def get_settings(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[ApprovalSettings]:
        """
        Get approval settings for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing ApprovalSettings or error
        """
        try:
            self._logger.debug(f"Fetching approval settings for hostel {hostel_id}")
            
            settings = self.repository.get_settings(hostel_id)
            
            return ServiceResult.success(settings)

        except Exception as e:
            self._logger.error(f"Error fetching approval settings: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get approval settings", hostel_id)

    def update_settings(
        self,
        hostel_id: UUID,
        settings: ApprovalSettings,
    ) -> ServiceResult[ApprovalSettings]:
        """
        Update approval settings for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            settings: New settings
            
        Returns:
            ServiceResult containing updated ApprovalSettings or error
        """
        try:
            self._logger.info(
                f"Updating approval settings for hostel {hostel_id}",
                extra={"hostel_id": str(hostel_id)}
            )

            # Update settings
            updated = self.repository.update_settings(hostel_id, settings)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully updated approval settings for hostel {hostel_id}",
                extra={"hostel_id": str(hostel_id)}
            )

            return ServiceResult.success(
                updated,
                message="Approval settings updated successfully"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error updating approval settings: {str(e)}", exc_info=True)
            return self._handle_exception(e, "update approval settings", hostel_id)

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_pending_approvals(
        self,
        hostel_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get pending approval requests for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            page: Page number
            page_size: Items per page
            
        Returns:
            ServiceResult containing list of pending approvals or error
        """
        try:
            self._logger.debug(f"Fetching pending approvals for hostel {hostel_id}")
            
            pending = self.repository.get_pending_approvals(hostel_id, page=page, page_size=page_size)
            
            return ServiceResult.success(
                pending,
                metadata={
                    "count": len(pending),
                    "page": page,
                    "page_size": page_size
                }
            )

        except Exception as e:
            self._logger.error(f"Error fetching pending approvals: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get pending approvals", hostel_id)

    def get_approval_history(
        self,
        booking_id: UUID,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get approval history for a booking.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing approval history or error
        """
        try:
            self._logger.debug(f"Fetching approval history for booking {booking_id}")
            
            history = self.repository.get_approval_history(booking_id)
            
            return ServiceResult.success(
                history,
                metadata={"count": len(history)}
            )

        except Exception as e:
            self._logger.error(f"Error fetching approval history: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get approval history", booking_id)