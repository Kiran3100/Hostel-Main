# --- File: C:\Hostel-Main\app\services\hostel\hostel_amenity_service.py ---
"""
Hostel amenity service for comprehensive amenity and booking management.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hostel.hostel_amenity import HostelAmenity, AmenityCategory, AmenityBooking
from app.repositories.hostel.hostel_amenity_repository import (
    HostelAmenityRepository,
    AmenityCategoryRepository,
    AmenityBookingRepository
)
from app.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    BusinessRuleViolationError,
    ConflictError
)
from app.services.base.base_service import BaseService


class HostelAmenityService(BaseService):
    """
    Hostel amenity service with comprehensive amenity and booking management.
    
    Handles amenity CRUD, availability checking, booking management,
    maintenance tracking, and usage analytics.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.amenity_repo = HostelAmenityRepository(session)
        self.category_repo = AmenityCategoryRepository(session)
        self.booking_repo = AmenityBookingRepository(session)

    # ===== Amenity Management =====

    async def create_amenity(
        self,
        hostel_id: UUID,
        amenity_data: Dict[str, Any],
        created_by: Optional[UUID] = None
    ) -> HostelAmenity:
        """
        Create a new amenity for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            amenity_data: Amenity information
            created_by: User ID creating the amenity
            
        Returns:
            Created HostelAmenity instance
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        required_fields = ['name', 'category']
        for field in required_fields:
            if field not in amenity_data:
                raise ValidationError(f"'{field}' is required")
        
        # Validate category
        category = await self.category_repo.find_one_by_criteria({
            'name': amenity_data['category'],
            'is_active': True
        })
        
        if not category:
            raise ValidationError(
                f"Invalid or inactive category: {amenity_data['category']}"
            )
        
        # Validate capacity if bookable
        if amenity_data.get('is_bookable', False):
            if not amenity_data.get('capacity'):
                raise ValidationError(
                    "Capacity is required for bookable amenities"
                )
            if amenity_data['capacity'] < 1:
                raise ValidationError("Capacity must be at least 1")
        
        # Set default values
        amenity_data['hostel_id'] = hostel_id
        amenity_data.setdefault('is_available', True)
        amenity_data.setdefault('is_bookable', False)
        amenity_data.setdefault('is_chargeable', False)
        amenity_data.setdefault('condition_status', 'good')
        amenity_data.setdefault('current_usage', 0)
        amenity_data.setdefault('display_order', 0)
        amenity_data.setdefault('is_featured', False)
        
        # Create amenity
        amenity = await self.amenity_repo.create(amenity_data)
        
        # Log event
        await self._log_event('amenity_created', {
            'amenity_id': amenity.id,
            'hostel_id': hostel_id,
            'name': amenity.name,
            'category': amenity.category,
            'created_by': created_by
        })
        
        return amenity

    async def get_amenity_by_id(self, amenity_id: UUID) -> HostelAmenity:
        """
        Get amenity by ID.
        
        Args:
            amenity_id: Amenity UUID
            
        Returns:
            HostelAmenity instance
            
        Raises:
            ResourceNotFoundError: If amenity not found
        """
        amenity = await self.amenity_repo.get_by_id(amenity_id)
        if not amenity:
            raise ResourceNotFoundError(f"Amenity {amenity_id} not found")
        
        return amenity

    async def update_amenity(
        self,
        amenity_id: UUID,
        update_data: Dict[str, Any],
        updated_by: Optional[UUID] = None
    ) -> HostelAmenity:
        """
        Update amenity information.
        
        Args:
            amenity_id: Amenity UUID
            update_data: Fields to update
            updated_by: User ID performing update
            
        Returns:
            Updated HostelAmenity instance
        """
        amenity = await self.get_amenity_by_id(amenity_id)
        
        # Validate capacity changes if bookable
        if amenity.is_bookable and 'capacity' in update_data:
            new_capacity = update_data['capacity']
            if new_capacity < amenity.current_usage:
                raise BusinessRuleViolationError(
                    f"Cannot reduce capacity below current usage ({amenity.current_usage})"
                )
        
        # Update amenity
        updated_amenity = await self.amenity_repo.update(amenity_id, update_data)
        
        # Log event
        await self._log_event('amenity_updated', {
            'amenity_id': amenity_id,
            'updated_fields': list(update_data.keys()),
            'updated_by': updated_by
        })
        
        return updated_amenity

    async def delete_amenity(
        self,
        amenity_id: UUID,
        deleted_by: Optional[UUID] = None
    ) -> bool:
        """
        Delete an amenity.
        
        Args:
            amenity_id: Amenity UUID
            deleted_by: User ID performing deletion
            
        Returns:
            True if successful
            
        Raises:
            BusinessRuleViolationError: If amenity has active bookings
        """
        amenity = await self.get_amenity_by_id(amenity_id)
        
        # Check for active bookings
        if amenity.is_bookable:
            active_bookings = await self.booking_repo.find_amenity_bookings(
                amenity_id,
                status='confirmed'
            )
            
            if active_bookings:
                raise BusinessRuleViolationError(
                    f"Cannot delete amenity with {len(active_bookings)} active bookings"
                )
        
        # Delete amenity
        await self.amenity_repo.delete(amenity_id)
        
        # Log event
        await self._log_event('amenity_deleted', {
            'amenity_id': amenity_id,
            'deleted_by': deleted_by
        })
        
        return True

    # ===== Amenity Queries =====

    async def get_hostel_amenities(
        self,
        hostel_id: UUID,
        category: Optional[str] = None,
        only_available: bool = True,
        only_bookable: bool = False
    ) -> List[HostelAmenity]:
        """
        Get amenities for a hostel with filtering.
        
        Args:
            hostel_id: Hostel UUID
            category: Filter by category
            only_available: Show only available amenities
            only_bookable: Show only bookable amenities
            
        Returns:
            List of amenities
        """
        if category:
            amenities = await self.amenity_repo.find_by_category(
                hostel_id,
                category,
                only_available
            )
        elif only_bookable:
            amenities = await self.amenity_repo.find_bookable_amenities(hostel_id)
        elif only_available:
            amenities = await self.amenity_repo.find_available_amenities(hostel_id)
        else:
            amenities = await self.amenity_repo.find_by_hostel(
                hostel_id,
                include_inactive=not only_available
            )
        
        return amenities

    async def get_amenities_by_category(
        self,
        hostel_id: UUID
    ) -> Dict[str, List[HostelAmenity]]:
        """
        Get amenities grouped by category.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary mapping category to amenities
        """
        amenities = await self.amenity_repo.find_by_hostel(
            hostel_id,
            include_inactive=False
        )
        
        categorized = {}
        for amenity in amenities:
            if amenity.category not in categorized:
                categorized[amenity.category] = []
            categorized[amenity.category].append(amenity)
        
        return categorized

    # ===== Booking Management =====

    async def book_amenity(
        self,
        amenity_id: UUID,
        student_id: UUID,
        start_time: datetime,
        end_time: datetime,
        participants_count: int = 1,
        notes: Optional[str] = None
    ) -> AmenityBooking:
        """
        Create an amenity booking.
        
        Args:
            amenity_id: Amenity UUID
            student_id: Student UUID
            start_time: Booking start time
            end_time: Booking end time
            participants_count: Number of participants
            notes: Optional booking notes
            
        Returns:
            Created AmenityBooking instance
            
        Raises:
            ValidationError: If validation fails
            ConflictError: If time slot is not available
        """
        amenity = await self.get_amenity_by_id(amenity_id)
        
        # Validate amenity is bookable
        if not amenity.is_bookable:
            raise BusinessRuleViolationError(
                f"Amenity '{amenity.name}' is not bookable"
            )
        
        # Validate amenity is available
        if not amenity.is_available:
            raise BusinessRuleViolationError(
                f"Amenity '{amenity.name}' is currently unavailable"
            )
        
        # Validate time range
        if end_time <= start_time:
            raise ValidationError("End time must be after start time")
        
        if start_time < datetime.utcnow():
            raise ValidationError("Cannot book in the past")
        
        # Validate participants
        if participants_count < 1:
            raise ValidationError("Participants count must be at least 1")
        
        if amenity.capacity and participants_count > amenity.capacity:
            raise ValidationError(
                f"Participants ({participants_count}) exceeds capacity ({amenity.capacity})"
            )
        
        # Check availability for time slot
        is_available = await self.amenity_repo.check_availability_for_booking(
            amenity_id,
            start_time,
            end_time,
            participants_count
        )
        
        if not is_available:
            raise ConflictError(
                "Amenity is not available for the requested time slot"
            )
        
        # Create booking
        booking = await self.booking_repo.create_booking(
            amenity_id,
            student_id,
            start_time,
            end_time,
            participants_count,
            notes
        )
        
        # Log event
        await self._log_event('amenity_booked', {
            'booking_id': booking.id,
            'amenity_id': amenity_id,
            'student_id': student_id,
            'start_time': start_time,
            'end_time': end_time
        })
        
        return booking

    async def confirm_booking(
        self,
        booking_id: UUID,
        confirmed_by: Optional[UUID] = None
    ) -> AmenityBooking:
        """
        Confirm a pending booking.
        
        Args:
            booking_id: Booking UUID
            confirmed_by: User ID confirming the booking
            
        Returns:
            Updated AmenityBooking instance
        """
        booking = await self.booking_repo.confirm_booking(booking_id)
        
        # Log event
        await self._log_event('booking_confirmed', {
            'booking_id': booking_id,
            'confirmed_by': confirmed_by
        })
        
        return booking

    async def cancel_booking(
        self,
        booking_id: UUID,
        reason: Optional[str] = None,
        cancelled_by: Optional[UUID] = None
    ) -> AmenityBooking:
        """
        Cancel a booking.
        
        Args:
            booking_id: Booking UUID
            reason: Cancellation reason
            cancelled_by: User ID cancelling the booking
            
        Returns:
            Updated AmenityBooking instance
        """
        booking = await self.booking_repo.cancel_booking(booking_id, reason)
        
        # Log event
        await self._log_event('booking_cancelled', {
            'booking_id': booking_id,
            'reason': reason,
            'cancelled_by': cancelled_by
        })
        
        return booking

    async def get_student_bookings(
        self,
        student_id: UUID,
        include_past: bool = False
    ) -> List[AmenityBooking]:
        """
        Get bookings for a student.
        
        Args:
            student_id: Student UUID
            include_past: Include past bookings
            
        Returns:
            List of bookings
        """
        if include_past:
            bookings = await self.booking_repo.find_student_bookings(student_id)
        else:
            now = datetime.utcnow()
            bookings = await self.booking_repo.find_student_bookings(
                student_id,
                start_date=now
            )
        
        return bookings

    async def get_amenity_schedule(
        self,
        amenity_id: UUID,
        days_ahead: int = 7
    ) -> List[AmenityBooking]:
        """
        Get booking schedule for an amenity.
        
        Args:
            amenity_id: Amenity UUID
            days_ahead: Number of days to look ahead
            
        Returns:
            List of bookings in schedule
        """
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days_ahead)
        
        return await self.amenity_repo.get_amenity_schedule(
            amenity_id,
            start_date,
            end_date
        )

    # ===== Maintenance Management =====

    async def update_maintenance_status(
        self,
        amenity_id: UUID,
        condition_status: str,
        next_maintenance_date: Optional[datetime] = None,
        notes: Optional[str] = None
    ) -> HostelAmenity:
        """
        Update maintenance status of an amenity.
        
        Args:
            amenity_id: Amenity UUID
            condition_status: Condition status (excellent, good, fair, poor)
            next_maintenance_date: Next scheduled maintenance date
            notes: Maintenance notes
            
        Returns:
            Updated HostelAmenity instance
        """
        valid_statuses = ['excellent', 'good', 'fair', 'poor']
        if condition_status not in valid_statuses:
            raise ValidationError(
                f"Invalid condition status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        amenity = await self.amenity_repo.update_maintenance_status(
            amenity_id,
            condition_status,
            next_maintenance_date
        )
        
        # If condition is poor, mark as unavailable
        if condition_status == 'poor':
            await self.amenity_repo.update(amenity_id, {'is_available': False})
        
        # Log event
        await self._log_event('maintenance_updated', {
            'amenity_id': amenity_id,
            'condition_status': condition_status,
            'notes': notes
        })
        
        return amenity

    async def get_amenities_needing_maintenance(
        self,
        hostel_id: Optional[UUID] = None
    ) -> List[HostelAmenity]:
        """
        Get amenities that need maintenance.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of amenities needing maintenance
        """
        return await self.amenity_repo.find_amenities_needing_maintenance(hostel_id)

    async def schedule_maintenance(
        self,
        amenity_id: UUID,
        maintenance_date: datetime,
        duration_hours: int = 2
    ) -> Dict[str, Any]:
        """
        Schedule maintenance for an amenity.
        
        Args:
            amenity_id: Amenity UUID
            maintenance_date: Scheduled maintenance date
            duration_hours: Expected duration in hours
            
        Returns:
            Maintenance schedule information
        """
        amenity = await self.get_amenity_by_id(amenity_id)
        
        # Update next maintenance date
        await self.amenity_repo.update(amenity_id, {
            'next_maintenance_at': maintenance_date
        })
        
        # Mark as unavailable during maintenance
        end_time = maintenance_date + timedelta(hours=duration_hours)
        
        return {
            'amenity_id': amenity_id,
            'amenity_name': amenity.name,
            'maintenance_start': maintenance_date,
            'maintenance_end': end_time,
            'duration_hours': duration_hours,
            'status': 'scheduled'
        }

    # ===== Analytics =====

    async def get_usage_statistics(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get usage statistics for hostel amenities.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Usage statistics
        """
        return await self.amenity_repo.get_amenity_usage_stats(hostel_id)

    async def get_popular_amenities(
        self,
        hostel_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most popular amenities by usage.
        
        Args:
            hostel_id: Hostel UUID
            limit: Maximum results
            
        Returns:
            List of popular amenities with usage data
        """
        return await self.amenity_repo.get_popular_amenities(hostel_id, limit)

    async def get_amenity_utilization(
        self,
        amenity_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get utilization metrics for an amenity.
        
        Args:
            amenity_id: Amenity UUID
            period_days: Analysis period in days
            
        Returns:
            Utilization metrics
        """
        amenity = await self.get_amenity_by_id(amenity_id)
        
        start_date = datetime.utcnow() - timedelta(days=period_days)
        bookings = await self.booking_repo.find_student_bookings(
            None,  # All students
            start_date=start_date
        )
        
        total_hours = period_days * 24
        booked_hours = sum(
            (b.end_time - b.start_time).total_seconds() / 3600
            for b in bookings
            if b.amenity_id == amenity_id and b.status in ['confirmed', 'completed']
        )
        
        utilization_rate = (booked_hours / total_hours) * 100 if total_hours > 0 else 0
        
        return {
            'amenity_id': amenity_id,
            'amenity_name': amenity.name,
            'period_days': period_days,
            'total_bookings': len(bookings),
            'total_hours_booked': booked_hours,
            'total_available_hours': total_hours,
            'utilization_rate': round(utilization_rate, 2),
            'average_booking_duration': booked_hours / max(len(bookings), 1)
        }

    # ===== Category Management =====

    async def get_active_categories(self) -> List[AmenityCategory]:
        """Get all active amenity categories."""
        return await self.category_repo.find_active_categories()

    async def get_basic_categories(self) -> List[AmenityCategory]:
        """Get basic/essential amenity categories."""
        return await self.category_repo.find_basic_categories()

    # ===== Helper Methods =====

    async def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log service events for audit and analytics."""
        # Implementation depends on your logging/event system
        pass