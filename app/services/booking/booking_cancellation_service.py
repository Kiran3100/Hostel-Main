"""
Booking cancellation & refund service.

Enhanced with:
- Policy validation
- Refund calculation accuracy
- Cancellation workflows
- Notification integration
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import logging
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingCancellationRepository
from app.models.booking.booking_cancellation import BookingCancellation as BookingCancellationModel
from app.schemas.booking.booking_cancellation import (
    CancellationRequest,
    RefundCalculation,
    CancellationResponse,
    CancellationPolicy,
    BulkCancellation,
)

logger = logging.getLogger(__name__)


class BookingCancellationService(BaseService[BookingCancellationModel, BookingCancellationRepository]):
    """
    Handle booking cancellations, policies, and refunds.
    
    Features:
    - Cancellation with reason tracking
    - Policy-based refund calculation
    - Bulk cancellation operations
    - Cancellation policy management
    """

    def __init__(self, repository: BookingCancellationRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_cancellation_request(self, request: CancellationRequest) -> Optional[ServiceError]:
        """Validate cancellation request."""
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
                    message="Cancellation reason must be at least 10 characters",
                    severity=ErrorSeverity.ERROR,
                    details={"reason_length": len(request.reason.strip())}
                )
        
        return None

    def _validate_bulk_cancellation(self, request: BulkCancellation) -> Optional[ServiceError]:
        """Validate bulk cancellation request."""
        if not request.booking_ids or len(request.booking_ids) == 0:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="At least one booking ID is required",
                severity=ErrorSeverity.ERROR
            )
        
        if len(request.booking_ids) > 100:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Cannot cancel more than 100 bookings at once",
                severity=ErrorSeverity.ERROR,
                details={"count": len(request.booking_ids)}
            )
        
        return None

    def _validate_cancellation_policy(self, policy: CancellationPolicy) -> Optional[ServiceError]:
        """Validate cancellation policy."""
        # Validate refund percentages
        if hasattr(policy, 'refund_percentage'):
            if policy.refund_percentage < 0 or policy.refund_percentage > 100:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Refund percentage must be between 0 and 100",
                    severity=ErrorSeverity.ERROR,
                    details={"refund_percentage": policy.refund_percentage}
                )
        
        # Validate notice periods
        if hasattr(policy, 'notice_period_days'):
            if policy.notice_period_days < 0:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Notice period cannot be negative",
                    severity=ErrorSeverity.ERROR,
                    details={"notice_period_days": policy.notice_period_days}
                )
        
        return None

    # -------------------------------------------------------------------------
    # Cancellation Operations
    # -------------------------------------------------------------------------

    def cancel(
        self,
        request: CancellationRequest,
    ) -> ServiceResult[CancellationResponse]:
        """
        Cancel a booking.
        
        Args:
            request: Cancellation request data
            
        Returns:
            ServiceResult containing CancellationResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_cancellation_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Cancelling booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "cancelled_by": str(request.cancelled_by) if hasattr(request, 'cancelled_by') else None,
                    "reason": request.reason if hasattr(request, 'reason') else None
                }
            )

            # Execute cancellation
            resp = self.repository.cancel(request)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully cancelled booking {request.booking_id}",
                extra={
                    "booking_id": str(request.booking_id),
                    "cancellation_id": str(resp.id) if hasattr(resp, 'id') else None,
                    "refund_amount": str(resp.refund_amount) if hasattr(resp, 'refund_amount') else None
                }
            )

            return ServiceResult.success(
                resp,
                message="Booking cancelled successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error cancelling booking: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Booking has already been cancelled",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(request.booking_id)}
                )
            )
        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error cancelling booking: {str(e)}", exc_info=True)
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
            self._logger.error(f"Error cancelling booking: {str(e)}", exc_info=True)
            return self._handle_exception(e, "cancel booking", request.booking_id)

    def bulk_cancel(
        self,
        request: BulkCancellation,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Cancel multiple bookings in bulk.
        
        Args:
            request: Bulk cancellation request
            
        Returns:
            ServiceResult containing summary dict or error
        """
        try:
            # Validate request
            validation_error = self._validate_bulk_cancellation(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Bulk cancelling {len(request.booking_ids)} bookings",
                extra={
                    "booking_count": len(request.booking_ids),
                    "cancelled_by": str(request.cancelled_by) if hasattr(request, 'cancelled_by') else None
                }
            )

            start_time = datetime.utcnow()

            # Execute bulk cancellation
            summary = self.repository.bulk_cancel(request)
            
            # Commit transaction
            self.db.commit()
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Bulk cancellation completed: {summary.get('cancelled', 0)} cancelled, "
                f"{summary.get('failed', 0)} failed in {duration_ms:.2f}ms",
                extra={
                    "cancelled": summary.get('cancelled', 0),
                    "failed": summary.get('failed', 0),
                    "total_refund": str(summary.get('total_refund_amount', 0)),
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                summary,
                message=f"Bulk cancellation completed: {summary.get('cancelled', 0)} cancelled, "
                        f"{summary.get('failed', 0)} failed",
                metadata={"duration_ms": duration_ms}
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during bulk cancellation: {str(e)}", exc_info=True)
            return self._handle_exception(e, "bulk cancel bookings")

    # -------------------------------------------------------------------------
    # Refund Calculation
    # -------------------------------------------------------------------------

    def calculate_refund(
        self,
        booking_id: UUID,
        cancellation_date: Optional[datetime] = None,
    ) -> ServiceResult[RefundCalculation]:
        """
        Calculate refund amount for a booking.
        
        Args:
            booking_id: UUID of booking
            cancellation_date: Optional cancellation date (defaults to now)
            
        Returns:
            ServiceResult containing RefundCalculation or error
        """
        try:
            if cancellation_date is None:
                cancellation_date = datetime.utcnow()

            self._logger.debug(
                f"Calculating refund for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "cancellation_date": cancellation_date.isoformat()
                }
            )

            # Calculate refund
            calc = self.repository.calculate_refund(booking_id, cancellation_date=cancellation_date)
            
            if not calc:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Booking not found or cannot be cancelled",
                        severity=ErrorSeverity.ERROR,
                        details={"booking_id": str(booking_id)}
                    )
                )

            self._logger.debug(
                f"Refund calculated for booking {booking_id}: {calc.refund_amount}",
                extra={
                    "booking_id": str(booking_id),
                    "refund_amount": str(calc.refund_amount),
                    "refund_percentage": calc.refund_percentage
                }
            )

            return ServiceResult.success(calc)

        except Exception as e:
            self._logger.error(f"Error calculating refund: {str(e)}", exc_info=True)
            return self._handle_exception(e, "calculate refund", booking_id)

    def preview_cancellation(
        self,
        booking_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Preview cancellation details without executing.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing preview details
        """
        try:
            self._logger.debug(f"Previewing cancellation for booking {booking_id}")

            preview = self.repository.preview_cancellation(booking_id)

            return ServiceResult.success(preview)

        except Exception as e:
            self._logger.error(f"Error previewing cancellation: {str(e)}", exc_info=True)
            return self._handle_exception(e, "preview cancellation", booking_id)

    # -------------------------------------------------------------------------
    # Policy Management
    # -------------------------------------------------------------------------

    def get_policy(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[CancellationPolicy]:
        """
        Get cancellation policy for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing CancellationPolicy or error
        """
        try:
            self._logger.debug(f"Fetching cancellation policy for hostel {hostel_id}")
            
            policy = self.repository.get_policy(hostel_id)
            
            if not policy:
                # Return default policy if none exists
                self._logger.info(f"No policy found for hostel {hostel_id}, returning default")
                policy = self._get_default_policy()

            return ServiceResult.success(policy)

        except Exception as e:
            self._logger.error(f"Error fetching cancellation policy: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get cancellation policy", hostel_id)

    def update_policy(
        self,
        hostel_id: UUID,
        policy: CancellationPolicy,
    ) -> ServiceResult[CancellationPolicy]:
        """
        Update cancellation policy for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            policy: New policy data
            
        Returns:
            ServiceResult containing updated CancellationPolicy or error
        """
        try:
            # Validate policy
            validation_error = self._validate_cancellation_policy(policy)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Updating cancellation policy for hostel {hostel_id}",
                extra={"hostel_id": str(hostel_id)}
            )

            # Update policy
            updated = self.repository.update_policy(hostel_id, policy)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully updated cancellation policy for hostel {hostel_id}",
                extra={"hostel_id": str(hostel_id)}
            )

            return ServiceResult.success(
                updated,
                message="Cancellation policy updated successfully"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error updating cancellation policy: {str(e)}", exc_info=True)
            return self._handle_exception(e, "update cancellation policy", hostel_id)

    def _get_default_policy(self) -> CancellationPolicy:
        """Get default cancellation policy."""
        return CancellationPolicy(
            refund_percentage=100,
            notice_period_days=7,
            description="Default policy: Full refund with 7 days notice"
        )

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_cancellation_statistics(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get cancellation statistics.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            ServiceResult containing statistics
        """
        try:
            self._logger.debug(
                f"Fetching cancellation statistics for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            )

            stats = self.repository.get_cancellation_statistics(
                hostel_id,
                start_date=start_date,
                end_date=end_date
            )

            return ServiceResult.success(stats)

        except Exception as e:
            self._logger.error(f"Error fetching cancellation statistics: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get cancellation statistics", hostel_id)

    def get_cancellation_history(
        self,
        booking_id: UUID,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get cancellation history for a booking.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing cancellation history
        """
        try:
            self._logger.debug(f"Fetching cancellation history for booking {booking_id}")

            history = self.repository.get_cancellation_history(booking_id)

            return ServiceResult.success(
                history,
                metadata={"count": len(history)}
            )

        except Exception as e:
            self._logger.error(f"Error fetching cancellation history: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get cancellation history", booking_id)