# --- File: C:\Hostel-Main\app\services\hostel\hostel_amenity_service.py ---
"""
Hostel amenities service (CRUD, booking, maintenance).

Manages hostel amenities including availability tracking, booking/reservation
system, and maintenance scheduling.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.services.base import (
    BaseService, 
    ServiceResult, 
    ServiceError, 
    ErrorCode, 
    ErrorSeverity
)
from app.repositories.hostel import HostelAmenityRepository
from app.models.hostel.hostel_amenity import (
    HostelAmenity as HostelAmenityModel,
    AmenityBooking as AmenityBookingModel
)
from app.schemas.hostel.hostel_amenity import (
    AmenityCreate,
    AmenityUpdate,
    AmenityBookingCreate,
)
from app.services.hostel.constants import (
    ERROR_AMENITY_NOT_FOUND,
    ERROR_BOOKING_NOT_FOUND,
    SUCCESS_AMENITY_CREATED,
    SUCCESS_AMENITY_UPDATED,
    SUCCESS_AMENITY_DELETED,
    SUCCESS_AMENITY_BOOKED,
    SUCCESS_BOOKING_CANCELLED,
)

logger = logging.getLogger(__name__)


class HostelAmenityService(BaseService[HostelAmenityModel, HostelAmenityRepository]):
    """
    Manage amenities within a hostel including bookings and reservations.
    
    Provides functionality for:
    - Amenity CRUD operations
    - Booking and reservation management
    - Availability tracking
    - Maintenance scheduling
    """

    def __init__(self, repository: HostelAmenityRepository, db_session: Session):
        """
        Initialize hostel amenity service.
        
        Args:
            repository: Hostel amenity repository instance
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self._amenity_cache: Dict[UUID, HostelAmenityModel] = {}

    # =========================================================================
    # Amenity CRUD Operations
    # =========================================================================

    def create_amenity(
        self,
        request: AmenityCreate,
        created_by: Optional[UUID] = None,
        validate_uniqueness: bool = True,
    ) -> ServiceResult[HostelAmenityModel]:
        """
        Create a new amenity with validation.
        
        Args:
            request: Amenity creation request
            created_by: UUID of the user creating the amenity
            validate_uniqueness: Whether to check for duplicate amenities
            
        Returns:
            ServiceResult containing created amenity or error
        """
        try:
            logger.info(f"Creating amenity: {request.name} for hostel {request.hostel_id}")
            
            # Validate request
            validation_error = self._validate_amenity_create(request, validate_uniqueness)
            if validation_error:
                return validation_error
            
            # Create amenity
            amenity = self.repository.create_amenity(request, created_by=created_by)
            self.db.flush()
            
            self.db.commit()
            
            logger.info(f"Amenity created successfully: {amenity.id}")
            return ServiceResult.success(amenity, message=SUCCESS_AMENITY_CREATED)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating amenity: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Amenity with this name already exists for this hostel",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create amenity")

    def update_amenity(
        self,
        amenity_id: UUID,
        request: AmenityUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelAmenityModel]:
        """
        Update existing amenity information.
        
        Args:
            amenity_id: UUID of the amenity to update
            request: Update request with fields to modify
            updated_by: UUID of the user performing the update
            
        Returns:
            ServiceResult containing updated amenity or error
        """
        try:
            logger.info(f"Updating amenity: {amenity_id}")
            
            # Check existence
            existing = self.repository.get_by_id(amenity_id)
            if not existing:
                return self._not_found_error(ERROR_AMENITY_NOT_FOUND, amenity_id)
            
            # Validate update
            validation_error = self._validate_amenity_update(request, existing)
            if validation_error:
                return validation_error
            
            # Perform update
            amenity = self.repository.update_amenity(
                amenity_id, 
                request, 
                updated_by=updated_by
            )
            self.db.flush()
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_amenity_cache(amenity_id)
            
            logger.info(f"Amenity updated successfully: {amenity_id}")
            return ServiceResult.success(amenity, message=SUCCESS_AMENITY_UPDATED)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error updating amenity: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Update would violate data constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update amenity", amenity_id)

    def delete_amenity(
        self,
        amenity_id: UUID,
        soft_delete: bool = True,
        force: bool = False,
    ) -> ServiceResult[bool]:
        """
        Delete an amenity with optional soft delete.
        
        Args:
            amenity_id: UUID of the amenity to delete
            soft_delete: Whether to perform soft delete (mark as inactive)
            force: Force delete even if there are active bookings
            
        Returns:
            ServiceResult containing success status or error
        """
        try:
            logger.info(f"Deleting amenity: {amenity_id} (soft={soft_delete})")
            
            # Check for active bookings if not forcing
            if not force:
                has_active = self._has_active_bookings(amenity_id)
                if has_active:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="Cannot delete amenity with active bookings",
                            severity=ErrorSeverity.WARNING,
                            details={"amenity_id": str(amenity_id)}
                        )
                    )
            
            # Perform deletion
            self.repository.delete_amenity(amenity_id, soft_delete=soft_delete)
            self.db.flush()
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_amenity_cache(amenity_id)
            
            logger.info(f"Amenity deleted successfully: {amenity_id}")
            return ServiceResult.success(True, message=SUCCESS_AMENITY_DELETED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete amenity", amenity_id)

    def list_amenities(
        self,
        hostel_id: UUID,
        active_only: bool = True,
        available_only: bool = False,
        category: Optional[str] = None,
    ) -> ServiceResult[List[HostelAmenityModel]]:
        """
        List amenities for a hostel with filtering options.
        
        Args:
            hostel_id: UUID of the hostel
            active_only: Only return active amenities
            available_only: Only return currently available amenities
            category: Filter by amenity category
            
        Returns:
            ServiceResult containing list of amenities with metadata
        """
        try:
            logger.info(
                f"Listing amenities for hostel {hostel_id}: "
                f"active={active_only}, available={available_only}, category={category}"
            )
            
            # Fetch amenities
            items = self.repository.list_amenities(
                hostel_id,
                active_only=active_only,
                available_only=available_only,
                category=category
            )
            
            # Prepare metadata
            metadata = {
                "count": len(items),
                "hostel_id": str(hostel_id),
                "active_only": active_only,
                "available_only": available_only,
            }
            
            if category:
                metadata["category"] = category
            
            return ServiceResult.success(items, metadata=metadata)
            
        except Exception as e:
            return self._handle_exception(e, "list amenities", hostel_id)

    # =========================================================================
    # Booking Operations
    # =========================================================================

    def book_amenity(
        self,
        request: AmenityBookingCreate,
        booked_by: Optional[UUID] = None,
        auto_confirm: bool = False,
    ) -> ServiceResult[AmenityBookingModel]:
        """
        Create a new amenity booking with availability check.
        
        Args:
            request: Booking creation request
            booked_by: UUID of the user making the booking
            auto_confirm: Whether to automatically confirm the booking
            
        Returns:
            ServiceResult containing created booking or error
        """
        try:
            logger.info(
                f"Booking amenity {request.amenity_id} "
                f"from {request.start_time} to {request.end_time}"
            )
            
            # Validate booking request
            validation_error = self._validate_booking(request)
            if validation_error:
                return validation_error
            
            # Check availability
            is_available = self._check_availability(
                request.amenity_id,
                request.start_time,
                request.end_time
            )
            
            if not is_available:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Amenity is not available for the requested time slot",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "amenity_id": str(request.amenity_id),
                            "start_time": request.start_time.isoformat(),
                            "end_time": request.end_time.isoformat(),
                        }
                    )
                )
            
            # Create booking
            booking = self.repository.book_amenity(request, booked_by=booked_by)
            self.db.flush()
            
            # Auto-confirm if requested
            if auto_confirm:
                booking.status = "confirmed"
                booking.confirmed_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Amenity booking created successfully: {booking.id}")
            return ServiceResult.success(booking, message=SUCCESS_AMENITY_BOOKED)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating booking: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Failed to create booking due to data constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "book amenity")

    def cancel_booking(
        self,
        booking_id: UUID,
        cancellation_reason: Optional[str] = None,
        cancelled_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Cancel an amenity booking.
        
        Args:
            booking_id: UUID of the booking to cancel
            cancellation_reason: Reason for cancellation
            cancelled_by: UUID of the user cancelling the booking
            
        Returns:
            ServiceResult containing success status or error
        """
        try:
            logger.info(f"Cancelling booking: {booking_id}")
            
            # Check if booking exists and can be cancelled
            booking = self._get_booking(booking_id)
            if not booking:
                return self._not_found_error(ERROR_BOOKING_NOT_FOUND, booking_id)
            
            # Check if already cancelled
            if booking.status == "cancelled":
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Booking is already cancelled",
                        severity=ErrorSeverity.WARNING,
                        details={"booking_id": str(booking_id)}
                    )
                )
            
            # Check if booking has already passed
            if booking.end_time < datetime.utcnow():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Cannot cancel past bookings",
                        severity=ErrorSeverity.WARNING,
                        details={"booking_id": str(booking_id)}
                    )
                )
            
            # Perform cancellation
            success = self.repository.cancel_booking(
                booking_id,
                reason=cancellation_reason,
                cancelled_by=cancelled_by
            )
            self.db.flush()
            
            self.db.commit()
            
            logger.info(f"Booking cancelled successfully: {booking_id}")
            return ServiceResult.success(success, message=SUCCESS_BOOKING_CANCELLED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "cancel amenity booking", booking_id)

    def get_bookings(
        self,
        amenity_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> ServiceResult[List[AmenityBookingModel]]:
        """
        Retrieve bookings with flexible filtering.
        
        Args:
            amenity_id: Filter by amenity
            user_id: Filter by user who made the booking
            start_date: Filter bookings starting after this date
            end_date: Filter bookings ending before this date
            status: Filter by booking status
            
        Returns:
            ServiceResult containing list of bookings with metadata
        """
        try:
            logger.info(
                f"Fetching bookings: amenity={amenity_id}, user={user_id}, "
                f"dates={start_date} to {end_date}, status={status}"
            )
            
            bookings = self.repository.get_bookings(
                amenity_id=amenity_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                status=status
            )
            
            metadata = {
                "count": len(bookings),
                "filters": {
                    "amenity_id": str(amenity_id) if amenity_id else None,
                    "user_id": str(user_id) if user_id else None,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "status": status,
                }
            }
            
            return ServiceResult.success(bookings, metadata=metadata)
            
        except Exception as e:
            return self._handle_exception(e, "get amenity bookings")

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_amenity_create(
        self,
        request: AmenityCreate,
        check_uniqueness: bool
    ) -> Optional[ServiceResult[HostelAmenityModel]]:
        """
        Validate amenity creation request.
        
        Args:
            request: Amenity creation request
            check_uniqueness: Whether to check for duplicates
            
        Returns:
            ServiceResult with error if validation fails, None otherwise
        """
        if not request.name or len(request.name.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Amenity name is required",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        if hasattr(request, 'capacity') and request.capacity is not None:
            if request.capacity < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Amenity capacity cannot be negative",
                        severity=ErrorSeverity.ERROR
                    )
                )
        
        return None

    def _validate_amenity_update(
        self,
        request: AmenityUpdate,
        existing: HostelAmenityModel
    ) -> Optional[ServiceResult[HostelAmenityModel]]:
        """
        Validate amenity update request.
        
        Args:
            request: Amenity update request
            existing: Existing amenity model
            
        Returns:
            ServiceResult with error if validation fails, None otherwise
        """
        if request.name is not None and len(request.name.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Amenity name cannot be empty",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        if hasattr(request, 'capacity') and request.capacity is not None:
            if request.capacity < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Amenity capacity cannot be negative",
                        severity=ErrorSeverity.ERROR
                    )
                )
        
        return None

    def _validate_booking(
        self,
        request: AmenityBookingCreate
    ) -> Optional[ServiceResult[AmenityBookingModel]]:
        """
        Validate booking request.
        
        Args:
            request: Booking creation request
            
        Returns:
            ServiceResult with error if validation fails, None otherwise
        """
        # Check time range
        if request.start_time >= request.end_time:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start time must be before end time",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        # Check if booking is in the past
        if request.start_time < datetime.utcnow():
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Cannot book amenities in the past",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        # Check booking duration (example: max 24 hours)
        duration = request.end_time - request.start_time
        if duration > timedelta(hours=24):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Booking duration cannot exceed 24 hours",
                    severity=ErrorSeverity.WARNING
                )
            )
        
        return None

    def _check_availability(
        self,
        amenity_id: UUID,
        start_time: datetime,
        end_time: datetime
    ) -> bool:
        """
        Check if amenity is available for the requested time slot.
        
        Args:
            amenity_id: UUID of the amenity
            start_time: Requested start time
            end_time: Requested end time
            
        Returns:
            True if available, False otherwise
        """
        try:
            return self.repository.check_availability(
                amenity_id,
                start_time,
                end_time
            )
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return False

    def _has_active_bookings(self, amenity_id: UUID) -> bool:
        """
        Check if amenity has any active bookings.
        
        Args:
            amenity_id: UUID of the amenity
            
        Returns:
            True if there are active bookings, False otherwise
        """
        try:
            bookings = self.repository.get_bookings(
                amenity_id=amenity_id,
                status="confirmed",
                start_date=datetime.utcnow()
            )
            return len(bookings) > 0
        except Exception as e:
            logger.error(f"Error checking active bookings: {str(e)}")
            return False

    def _get_booking(self, booking_id: UUID) -> Optional[AmenityBookingModel]:
        """
        Retrieve a booking by ID.
        
        Args:
            booking_id: UUID of the booking
            
        Returns:
            Booking model or None if not found
        """
        try:
            return self.repository.get_booking_by_id(booking_id)
        except Exception as e:
            logger.error(f"Error retrieving booking: {str(e)}")
            return None

    def _not_found_error(
        self,
        message: str,
        entity_id: UUID
    ) -> ServiceResult:
        """
        Create a standardized not found error response.
        
        Args:
            message: Error message
            entity_id: ID of the entity not found
            
        Returns:
            ServiceResult with not found error
        """
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.NOT_FOUND,
                message=message,
                severity=ErrorSeverity.ERROR,
                details={"entity_id": str(entity_id)}
            )
        )

    def _invalidate_amenity_cache(self, amenity_id: UUID) -> None:
        """
        Clear cached data for a specific amenity.
        
        Args:
            amenity_id: UUID of the amenity
        """
        if amenity_id in self._amenity_cache:
            del self._amenity_cache[amenity_id]
            logger.debug(f"Amenity cache invalidated: {amenity_id}")

    def clear_cache(self) -> None:
        """Clear all cached amenity data."""
        self._amenity_cache.clear()
        logger.info("All amenity cache cleared")