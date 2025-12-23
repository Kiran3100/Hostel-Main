"""
Core booking service: create/update, detail/list queries.

Enhanced with:
- Comprehensive validation
- Performance monitoring
- Optimized queries
- Enhanced error handling
- Caching strategies
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging
from functools import wraps

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingRepository
from app.models.booking.booking import Booking as BookingModel
from app.schemas.booking.booking_base import BookingCreate, BookingUpdate
from app.schemas.booking.booking_request import BookingRequest, QuickBookingRequest
from app.schemas.booking.booking_response import BookingResponse, BookingDetail, BookingListItem

logger = logging.getLogger(__name__)


def track_performance(operation_name: str):
    """Decorator to track operation performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            try:
                result = func(*args, **kwargs)
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"Operation '{operation_name}' completed in {duration:.3f}s",
                    extra={
                        "operation": operation_name,
                        "duration_seconds": duration,
                        "success": result.success if hasattr(result, 'success') else True
                    }
                )
                return result
            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.error(
                    f"Operation '{operation_name}' failed after {duration:.3f}s: {str(e)}",
                    extra={
                        "operation": operation_name,
                        "duration_seconds": duration,
                        "error": str(e)
                    },
                    exc_info=True
                )
                raise
        return wrapper
    return decorator


class BookingService(BaseService[BookingModel, BookingRepository]):
    """
    Core booking operations: create, update, detail & listings.
    
    Responsibilities:
    - Booking lifecycle management (create, update)
    - Validation of booking requests
    - Query operations with optimized performance
    - Transaction management
    - Error handling and logging
    """

    def __init__(self, repository: BookingRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------------

    def _validate_booking_create(self, request: BookingCreate) -> Optional[ServiceError]:
        """
        Validate booking creation request.
        
        Args:
            request: BookingCreate schema
            
        Returns:
            ServiceError if validation fails, None otherwise
        """
        # Date validation
        if hasattr(request, 'check_in_date') and hasattr(request, 'check_out_date'):
            if request.check_in_date >= request.check_out_date:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Check-in date must be before check-out date",
                    severity=ErrorSeverity.ERROR,
                    details={"check_in": str(request.check_in_date), "check_out": str(request.check_out_date)}
                )
            
            # Check minimum stay requirement (at least 1 day)
            days_diff = (request.check_out_date - request.check_in_date).days
            if days_diff < 1:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Minimum stay is 1 day",
                    severity=ErrorSeverity.ERROR,
                    details={"days": days_diff}
                )

        # Duration validation
        if hasattr(request, 'duration_months') and request.duration_months is not None:
            if request.duration_months <= 0:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Duration must be positive",
                    severity=ErrorSeverity.ERROR,
                    details={"duration_months": request.duration_months}
                )

        # Guest count validation
        if hasattr(request, 'number_of_guests') and request.number_of_guests is not None:
            if request.number_of_guests <= 0:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Number of guests must be positive",
                    severity=ErrorSeverity.ERROR,
                    details={"number_of_guests": request.number_of_guests}
                )

        return None

    def _validate_booking_update(self, booking_id: UUID, request: BookingUpdate) -> Optional[ServiceError]:
        """
        Validate booking update request.
        
        Args:
            booking_id: UUID of booking to update
            request: BookingUpdate schema
            
        Returns:
            ServiceError if validation fails, None otherwise
        """
        # Similar validations as create, but only for provided fields
        if hasattr(request, 'check_in_date') and hasattr(request, 'check_out_date'):
            if request.check_in_date and request.check_out_date:
                if request.check_in_date >= request.check_out_date:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Check-in date must be before check-out date",
                        severity=ErrorSeverity.ERROR,
                        details={"check_in": str(request.check_in_date), "check_out": str(request.check_out_date)}
                    )

        return None

    # -------------------------------------------------------------------------
    # Create Operations
    # -------------------------------------------------------------------------

    @track_performance("create_booking")
    def create_booking(
        self,
        request: BookingCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[BookingDetail]:
        """
        Create a booking (admin-side).
        
        Args:
            request: Booking creation data
            created_by: UUID of user creating the booking
            
        Returns:
            ServiceResult containing BookingDetail or error
        """
        try:
            # Validate input
            validation_error = self._validate_booking_create(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Creating booking for hostel {request.hostel_id}",
                extra={
                    "hostel_id": str(request.hostel_id),
                    "created_by": str(created_by) if created_by else None
                }
            )

            # Create booking
            booking = self.repository.create_booking(request, created_by=created_by)
            
            # Commit transaction
            self.db.commit()
            
            # Fetch complete details
            detail = self.repository.get_detail(booking.id)
            
            self._logger.info(
                f"Successfully created booking {booking.id}",
                extra={"booking_id": str(booking.id)}
            )
            
            return ServiceResult.success(
                detail,
                message="Booking created successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error creating booking: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Booking conflicts with existing data",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except OperationalError as e:
            self.db.rollback()
            self._logger.error(f"Database error creating booking: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message="Database operation failed",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Unexpected error creating booking: {str(e)}", exc_info=True)
            return self._handle_exception(e, "create booking")

    @track_performance("create_from_request")
    def create_from_request(
        self,
        request: BookingRequest,
    ) -> ServiceResult[BookingDetail]:
        """
        Create booking from public/visitor booking request shape.
        
        Args:
            request: Public booking request data
            
        Returns:
            ServiceResult containing BookingDetail or error
        """
        try:
            self._logger.info(
                "Creating booking from public request",
                extra={
                    "hostel_id": str(request.hostel_id) if hasattr(request, 'hostel_id') else None,
                    "room_type": getattr(request, 'room_type', None)
                }
            )

            # Create booking
            booking = self.repository.create_from_request(request)
            
            # Commit transaction
            self.db.commit()
            
            # Fetch complete details
            detail = self.repository.get_detail(booking.id)
            
            self._logger.info(
                f"Successfully created booking {booking.id} from request",
                extra={"booking_id": str(booking.id)}
            )
            
            return ServiceResult.success(
                detail,
                message="Booking request submitted successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error creating booking from request: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Booking request conflicts with existing data",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error creating booking from request: {str(e)}", exc_info=True)
            return self._handle_exception(e, "create booking from request")

    @track_performance("quick_create")
    def quick_create(
        self,
        request: QuickBookingRequest,
    ) -> ServiceResult[BookingDetail]:
        """
        Minimal bookings for fast-track flows.
        
        Args:
            request: Quick booking request with minimal data
            
        Returns:
            ServiceResult containing BookingDetail or error
        """
        try:
            self._logger.info(
                "Creating quick booking",
                extra={
                    "hostel_id": str(request.hostel_id) if hasattr(request, 'hostel_id') else None
                }
            )

            # Create booking
            booking = self.repository.quick_create(request)
            
            # Commit transaction
            self.db.commit()
            
            # Fetch complete details
            detail = self.repository.get_detail(booking.id)
            
            self._logger.info(
                f"Successfully created quick booking {booking.id}",
                extra={"booking_id": str(booking.id)}
            )
            
            return ServiceResult.success(
                detail,
                message="Quick booking created successfully"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error creating quick booking: {str(e)}", exc_info=True)
            return self._handle_exception(e, "quick create booking")

    # -------------------------------------------------------------------------
    # Update Operations
    # -------------------------------------------------------------------------

    @track_performance("update_booking")
    def update_booking(
        self,
        booking_id: UUID,
        request: BookingUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[BookingDetail]:
        """
        Update editable booking fields (admin-side).
        
        Args:
            booking_id: UUID of booking to update
            request: Update data
            updated_by: UUID of user performing update
            
        Returns:
            ServiceResult containing updated BookingDetail or error
        """
        try:
            # Validate input
            validation_error = self._validate_booking_update(booking_id, request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Updating booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "updated_by": str(updated_by) if updated_by else None
                }
            )

            # Check existence
            existing = self.repository.get_by_id(booking_id)
            if not existing:
                self._logger.warning(f"Booking {booking_id} not found for update")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Booking not found",
                        severity=ErrorSeverity.ERROR,
                        details={"booking_id": str(booking_id)}
                    )
                )

            # Perform update
            self.repository.update_booking(booking_id, request, updated_by=updated_by)
            
            # Commit transaction
            self.db.commit()
            
            # Fetch updated details
            detail = self.repository.get_detail(booking_id)
            
            self._logger.info(
                f"Successfully updated booking {booking_id}",
                extra={"booking_id": str(booking_id)}
            )
            
            return ServiceResult.success(
                detail,
                message="Booking updated successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error updating booking {booking_id}: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Update conflicts with existing data",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e), "booking_id": str(booking_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error updating booking {booking_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "update booking", booking_id)

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    @track_performance("get_detail")
    def get_detail(self, booking_id: UUID) -> ServiceResult[BookingDetail]:
        """
        Get detailed booking information.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing BookingDetail or error
        """
        try:
            self._logger.debug(f"Fetching booking detail for {booking_id}")
            
            detail = self.repository.get_detail(booking_id)
            
            if not detail:
                self._logger.warning(f"Booking {booking_id} not found")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Booking not found",
                        severity=ErrorSeverity.ERROR,
                        details={"booking_id": str(booking_id)}
                    )
                )
            
            return ServiceResult.success(detail)

        except Exception as e:
            self._logger.error(f"Error fetching booking detail {booking_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get booking detail", booking_id)

    @track_performance("list_bookings")
    def list_bookings(
        self,
        hostel_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[List[BookingListItem]]:
        """
        List bookings with optional filtering and pagination.
        
        Args:
            hostel_id: Optional hostel filter
            status: Optional status filter
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            ServiceResult containing list of BookingListItem or error
        """
        try:
            # Validate pagination parameters
            if page < 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Page number must be >= 1",
                        severity=ErrorSeverity.ERROR,
                        details={"page": page}
                    )
                )
            
            if page_size < 1 or page_size > 1000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Page size must be between 1 and 1000",
                        severity=ErrorSeverity.ERROR,
                        details={"page_size": page_size}
                    )
                )

            self._logger.debug(
                "Listing bookings",
                extra={
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "status": status,
                    "page": page,
                    "page_size": page_size
                }
            )

            items = self.repository.list_bookings(hostel_id, status, page, page_size)
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "page": page,
                    "page_size": page_size,
                    "has_more": len(items) == page_size
                }
            )

        except Exception as e:
            self._logger.error(f"Error listing bookings: {str(e)}", exc_info=True)
            return self._handle_exception(e, "list bookings")

    # -------------------------------------------------------------------------
    # Additional Helper Methods
    # -------------------------------------------------------------------------

    def get_by_reference(self, reference_number: str) -> ServiceResult[BookingDetail]:
        """
        Get booking by reference number.
        
        Args:
            reference_number: Booking reference number
            
        Returns:
            ServiceResult containing BookingDetail or error
        """
        try:
            self._logger.debug(f"Fetching booking by reference: {reference_number}")
            
            booking = self.repository.get_by_reference(reference_number)
            
            if not booking:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Booking not found",
                        severity=ErrorSeverity.ERROR,
                        details={"reference_number": reference_number}
                    )
                )
            
            detail = self.repository.get_detail(booking.id)
            return ServiceResult.success(detail)

        except Exception as e:
            self._logger.error(f"Error fetching booking by reference {reference_number}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get booking by reference", reference_number)

    def get_statistics(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get booking statistics for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            ServiceResult containing statistics dict or error
        """
        try:
            self._logger.debug(f"Fetching booking statistics for hostel {hostel_id}")
            
            stats = self.repository.get_statistics(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                stats,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            )

        except Exception as e:
            self._logger.error(f"Error fetching statistics for hostel {hostel_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get booking statistics", hostel_id)