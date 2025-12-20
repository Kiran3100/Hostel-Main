# app/services/booking/booking_calendar_service.py
"""
Booking calendar service for calendar event and availability management.

Handles calendar visualization, availability tracking, blocking periods,
and occupancy calculations.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.base.enums import BookingStatus
from app.repositories.booking.booking_repository import BookingRepository
from app.repositories.booking.booking_calendar_repository import (
    BookingCalendarEventRepository,
    CalendarBlockRepository,
    DayAvailabilityRepository,
)
from app.repositories.base.base_repository import AuditContext


class BookingCalendarService:
    """
    Service for booking calendar and availability management.
    
    Responsibilities:
    - Calendar event creation and management
    - Daily availability calculation
    - Calendar blocking for maintenance
    - Occupancy tracking and trends
    - Visual calendar data generation
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
        event_repo: Optional[BookingCalendarEventRepository] = None,
        availability_repo: Optional[DayAvailabilityRepository] = None,
        block_repo: Optional[CalendarBlockRepository] = None,
    ):
        """Initialize calendar service."""
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
        self.event_repo = event_repo or BookingCalendarEventRepository(session)
        self.availability_repo = availability_repo or DayAvailabilityRepository(session)
        self.block_repo = block_repo or CalendarBlockRepository(session)
    
    # ==================== CALENDAR EVENTS ====================
    
    def create_booking_request_event(
        self,
        booking,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Create calendar event for new booking request.
        
        Args:
            booking: Booking model instance
            audit_context: Audit context
            
        Returns:
            Created event dictionary
        """
        event = self.event_repo.create_event_from_booking(
            booking=booking,
            event_type="booking_request",
            event_date=booking.preferred_check_in_date,
            audit_context=audit_context,
        )
        
        return self._event_to_dict(event)
    
    def create_check_in_event(
        self,
        booking,
        audit_context: Optional[AuditContext] = None,
        actual_date: Optional[date] = None,
    ) -> Dict:
        """
        Create calendar event for check-in.
        
        Args:
            booking: Booking model instance
            audit_context: Audit context
            actual_date: Actual check-in date (default: today)
            
        Returns:
            Created event dictionary
        """
        check_in_date = actual_date or date.today()
        
        event = self.event_repo.create_event_from_booking(
            booking=booking,
            event_type="check_in",
            event_date=check_in_date,
            audit_context=audit_context,
        )
        
        # Mark as high priority
        event.is_high_priority = True
        self.session.flush()
        
        return self._event_to_dict(event)
    
    def create_check_out_event(
        self,
        booking,
        check_out_date: date,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Create calendar event for check-out.
        
        Args:
            booking: Booking model instance
            check_out_date: Check-out date
            audit_context: Audit context
            
        Returns:
            Created event dictionary
        """
        event = self.event_repo.create_event_from_booking(
            booking=booking,
            event_type="check_out",
            event_date=check_out_date,
            audit_context=audit_context,
        )
        
        return self._event_to_dict(event)
    
    def update_booking_status(
        self,
        booking,
        audit_context: Optional[AuditContext] = None,
    ) -> None:
        """
        Update calendar events when booking status changes.
        
        Args:
            booking: Booking model instance
            audit_context: Audit context
        """
        # This would update existing events or create new ones
        # based on status transitions
        pass
    
    def get_calendar_events(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        event_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Get calendar events for a date range.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Range start date
            end_date: Range end date
            event_types: Optional event type filter
            
        Returns:
            List of event dictionaries
        """
        events = self.event_repo.find_events_for_date_range(
            hostel_id, start_date, end_date, event_types
        )
        
        return [self._event_to_dict(e) for e in events]
    
    def get_month_calendar(
        self,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> Dict:
        """
        Get complete calendar data for a month.
        
        Args:
            hostel_id: Hostel UUID
            year: Year
            month: Month (1-12)
            
        Returns:
            Month calendar dictionary with events and availability
        """
        # Get all events for the month
        events = self.event_repo.find_events_for_month(hostel_id, year, month)
        
        # Get availability data
        from calendar import monthrange
        start_date = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        
        availability = self.availability_repo.get_availability_for_date_range(
            hostel_id, start_date, end_date
        )
        
        # Group events by date
        events_by_date = {}
        for event in events:
            date_key = event.event_date.isoformat()
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(self._event_to_dict(event))
        
        # Group availability by date
        availability_by_date = {
            avail.availability_date.isoformat(): self._availability_to_dict(avail)
            for avail in availability
        }
        
        return {
            "year": year,
            "month": month,
            "events_by_date": events_by_date,
            "availability_by_date": availability_by_date,
            "total_events": len(events),
        }
    
    def get_high_priority_events(
        self,
        hostel_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict]:
        """Get high priority events requiring attention."""
        events = self.event_repo.find_high_priority_events(
            hostel_id, date_from, date_to
        )
        return [self._event_to_dict(e) for e in events]
    
    def get_events_requiring_action(
        self,
        hostel_id: UUID,
    ) -> List[Dict]:
        """Get events that require admin action."""
        events = self.event_repo.find_events_requiring_action(hostel_id)
        return [self._event_to_dict(e) for e in events]
    
    def mark_event_action_completed(
        self,
        event_id: UUID,
    ) -> Dict:
        """Mark event action as completed."""
        event = self.event_repo.mark_action_completed(event_id)
        return self._event_to_dict(event)
    
    # ==================== AVAILABILITY TRACKING ====================
    
    def calculate_daily_availability(
        self,
        hostel_id: UUID,
        target_date: date,
        room_id: Optional[UUID] = None,
    ) -> Dict:
        """
        Calculate and cache availability for a specific date.
        
        Args:
            hostel_id: Hostel UUID
            target_date: Date to calculate
            room_id: Optional room filter
            
        Returns:
            Availability dictionary
        """
        availability = self.availability_repo.calculate_and_update_availability(
            hostel_id, target_date, room_id
        )
        
        return self._availability_to_dict(availability)
    
    def get_availability_for_period(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        room_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Get availability data for a date range.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Range start
            end_date: Range end
            room_id: Optional room filter
            
        Returns:
            List of daily availability dictionaries
        """
        availability_records = self.availability_repo.get_availability_for_date_range(
            hostel_id, start_date, end_date, room_id
        )
        
        return [self._availability_to_dict(a) for a in availability_records]
    
    def get_fully_booked_dates(
        self,
        hostel_id: UUID,
        date_from: date,
        date_to: date,
    ) -> List[str]:
        """
        Get dates when hostel is fully booked.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Range start
            date_to: Range end
            
        Returns:
            List of date strings (ISO format)
        """
        dates = self.availability_repo.find_fully_booked_dates(
            hostel_id, date_from, date_to
        )
        return [d.isoformat() for d in dates]
    
    def get_occupancy_trend(
        self,
        hostel_id: UUID,
        days: int = 30,
    ) -> List[Dict]:
        """
        Get occupancy trend for recent days.
        
        Args:
            hostel_id: Hostel UUID
            days: Number of days to look back
            
        Returns:
            List of occupancy data points
        """
        return self.availability_repo.get_occupancy_trend(hostel_id, days)
    
    # ==================== CALENDAR BLOCKING ====================
    
    def create_calendar_block(
        self,
        hostel_id: UUID,
        block_type: str,
        start_date: date,
        end_date: date,
        reason: str,
        description: Optional[str] = None,
        room_id: Optional[UUID] = None,
        bed_id: Optional[UUID] = None,
        affects_bookings: bool = True,
        blocked_by_id: Optional[UUID] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Create calendar block for maintenance or unavailability.
        
        Args:
            hostel_id: Hostel UUID
            block_type: Type of block
            start_date: Block start date
            end_date: Block end date
            reason: Block reason
            description: Detailed description
            room_id: Optional room to block
            bed_id: Optional bed to block
            affects_bookings: Whether to impact bookings
            blocked_by_id: Admin creating block
            audit_context: Audit context
            
        Returns:
            Created block dictionary
        """
        block_data = {
            "hostel_id": hostel_id,
            "room_id": room_id,
            "bed_id": bed_id,
            "block_type": block_type,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "description": description,
            "affects_bookings": affects_bookings,
            "blocked_by": blocked_by_id,
        }
        
        block = self.block_repo.create_block(block_data, audit_context)
        
        return self._block_to_dict(block)
    
    def get_active_blocks(
        self,
        hostel_id: UUID,
        as_of_date: Optional[date] = None,
    ) -> List[Dict]:
        """Get currently active blocks."""
        blocks = self.block_repo.find_active_blocks(hostel_id, as_of_date)
        return [self._block_to_dict(b) for b in blocks]
    
    def get_blocks_for_period(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        room_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get blocks overlapping with a date range."""
        blocks = self.block_repo.find_blocks_for_date_range(
            hostel_id, start_date, end_date, room_id
        )
        return [self._block_to_dict(b) for b in blocks]
    
    def get_upcoming_blocks(
        self,
        hostel_id: UUID,
        days_ahead: int = 30,
    ) -> List[Dict]:
        """Get upcoming blocks."""
        blocks = self.block_repo.find_upcoming_blocks(hostel_id, days_ahead)
        return [self._block_to_dict(b) for b in blocks]
    
    def mark_block_completed(
        self,
        block_id: UUID,
        completion_notes: Optional[str] = None,
    ) -> Dict:
        """Mark calendar block as completed."""
        block = self.block_repo.mark_completed(block_id, completion_notes)
        return self._block_to_dict(block)
    
    def send_block_notification(
        self,
        block_id: UUID,
    ) -> Dict:
        """Mark block notification as sent."""
        block = self.block_repo.send_notification(block_id)
        return self._block_to_dict(block)
    
    # ==================== ANALYTICS ====================
    
    def get_calendar_statistics(
        self,
        hostel_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict:
        """
        Get comprehensive calendar statistics.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Calendar statistics dictionary
        """
        block_stats = self.block_repo.get_block_statistics(
            hostel_id, date_from, date_to
        )
        
        # Get occupancy stats
        if date_from and date_to:
            availability = self.get_availability_for_period(
                hostel_id, date_from, date_to
            )
            
            if availability:
                avg_occupancy = sum(a["occupancy_rate"] for a in availability) / len(
                    availability
                )
                avg_available = sum(a["available_beds"] for a in availability) / len(
                    availability
                )
            else:
                avg_occupancy = 0
                avg_available = 0
        else:
            avg_occupancy = 0
            avg_available = 0
        
        return {
            "block_statistics": block_stats,
            "average_occupancy_rate": avg_occupancy,
            "average_available_beds": avg_available,
        }
    
    # ==================== HELPER METHODS ====================
    
    def _event_to_dict(self, event) -> Dict:
        """Convert calendar event to dictionary."""
        return {
            "id": str(event.id),
            "hostel_id": str(event.hostel_id),
            "booking_id": str(event.booking_id) if event.booking_id else None,
            "room_id": str(event.room_id) if event.room_id else None,
            "event_type": event.event_type,
            "event_date": event.event_date.isoformat(),
            "event_title": event.event_title,
            "event_description": event.event_description,
            "guest_name": event.guest_name,
            "room_number": event.room_number,
            "room_type": event.room_type,
            "booking_status": event.booking_status.value if event.booking_status else None,
            "color_code": event.color_code,
            "is_all_day": event.is_all_day,
            "is_high_priority": event.is_high_priority,
            "requires_action": event.requires_action,
            "is_past_event": event.is_past_event,
            "is_today": event.is_today,
            "is_upcoming": event.is_upcoming,
            "days_until_event": event.days_until_event,
        }
    
    def _availability_to_dict(self, availability) -> Dict:
        """Convert availability to dictionary."""
        return {
            "id": str(availability.id),
            "hostel_id": str(availability.hostel_id),
            "room_id": str(availability.room_id) if availability.room_id else None,
            "availability_date": availability.availability_date.isoformat(),
            "total_beds": availability.total_beds,
            "available_beds": availability.available_beds,
            "occupied_beds": availability.occupied_beds,
            "reserved_beds": availability.reserved_beds,
            "maintenance_beds": availability.maintenance_beds,
            "blocked_beds": availability.blocked_beds,
            "is_fully_booked": availability.is_fully_booked,
            "occupancy_rate": availability.occupancy_rate,
            "availability_level": availability.availability_level,
            "is_past_date": availability.is_past_date,
            "is_today": availability.is_today,
        }
    
    def _block_to_dict(self, block) -> Dict:
        """Convert calendar block to dictionary."""
        return {
            "id": str(block.id),
            "hostel_id": str(block.hostel_id),
            "room_id": str(block.room_id) if block.room_id else None,
            "bed_id": str(block.bed_id) if block.bed_id else None,
            "block_type": block.block_type,
            "start_date": block.start_date.isoformat(),
            "end_date": block.end_date.isoformat(),
            "reason": block.reason,
            "description": block.description,
            "is_active": block.is_active,
            "affects_bookings": block.affects_bookings,
            "affected_booking_count": block.affected_booking_count,
            "is_completed": block.is_completed,
            "duration_days": block.duration_days,
            "is_current": block.is_current,
            "is_upcoming": block.is_upcoming,
            "is_past": block.is_past,
            "days_until_start": block.days_until_start,
            "days_until_end": block.days_until_end,
        }