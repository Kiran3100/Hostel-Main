# app/repositories/booking/booking_calendar_repository.py
"""
Booking calendar repository for calendar management and availability tracking.

Provides calendar event management, availability calculations, blocking,
and visual calendar data generation.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core1.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking_calendar import (
    BookingCalendarEvent,
    CalendarBlock,
    DayAvailability,
)
from app.models.booking.booking import Booking
from app.models.room.room import Room
from app.models.room.bed import Bed
from app.models.base.enums import BookingStatus, BedStatus
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingCalendarEventRepository(BaseRepository[BookingCalendarEvent]):
    """
    Repository for booking calendar events.
    
    Provides:
    - Calendar event management
    - Event visualization
    - Event filtering and search
    - Priority event tracking
    """
    
    def __init__(self, session: Session):
        """Initialize calendar event repository."""
        super().__init__(session, BookingCalendarEvent)
    
    # ==================== EVENT OPERATIONS ====================
    
    def create_event_from_booking(
        self,
        booking: Booking,
        event_type: str,
        event_date: date,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingCalendarEvent:
        """
        Create calendar event from booking.
        
        Args:
            booking: Booking instance
            event_type: Type of event
            event_date: Event date
            audit_context: Audit context
            
        Returns:
            Created event
        """
        # Determine color based on event type
        color_map = {
            "check_in": "#4CAF50",  # Green
            "check_out": "#F44336",  # Red
            "booking_request": "#2196F3",  # Blue
            "payment_due": "#FF9800",  # Orange
        }
        
        # Generate event title
        guest_name = None
        if booking.guest_info:
            guest_name = booking.guest_info.guest_name
        
        title_map = {
            "check_in": f"Check-in: {guest_name or 'Guest'}",
            "check_out": f"Check-out: {guest_name or 'Guest'}",
            "booking_request": f"New Booking: {booking.booking_reference}",
            "payment_due": f"Payment Due: {booking.booking_reference}",
        }
        
        event = BookingCalendarEvent(
            hostel_id=booking.hostel_id,
            booking_id=booking.id,
            room_id=booking.assignment.room_id if booking.assignment else None,
            event_type=event_type,
            event_date=event_date,
            event_title=title_map.get(event_type, event_type),
            guest_name=guest_name,
            room_type=str(booking.room_type_requested),
            booking_status=booking.booking_status,
            color_code=color_map.get(event_type, "#9E9E9E"),
        )
        
        return self.create(event, audit_context)
    
    def find_events_for_date_range(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        event_types: Optional[List[str]] = None,
    ) -> List[BookingCalendarEvent]:
        """
        Find calendar events for a date range.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Range start date
            end_date: Range end date
            event_types: Optional event type filter
            
        Returns:
            List of calendar events
        """
        query = select(BookingCalendarEvent).where(
            and_(
                BookingCalendarEvent.hostel_id == hostel_id,
                BookingCalendarEvent.event_date >= start_date,
                BookingCalendarEvent.event_date <= end_date,
                BookingCalendarEvent.deleted_at.is_(None),
            )
        )
        
        if event_types:
            query = query.where(BookingCalendarEvent.event_type.in_(event_types))
        
        query = query.order_by(
            BookingCalendarEvent.event_date.asc(),
            BookingCalendarEvent.event_type.asc()
        ).options(
            joinedload(BookingCalendarEvent.booking),
            joinedload(BookingCalendarEvent.room),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_events_for_month(
        self,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> List[BookingCalendarEvent]:
        """
        Find all events for a specific month.
        
        Args:
            hostel_id: Hostel UUID
            year: Year
            month: Month (1-12)
            
        Returns:
            List of calendar events
        """
        from calendar import monthrange
        
        start_date = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        
        return self.find_events_for_date_range(hostel_id, start_date, end_date)
    
    def find_high_priority_events(
        self,
        hostel_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[BookingCalendarEvent]:
        """
        Find high priority events.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            List of high priority events
        """
        query = select(BookingCalendarEvent).where(
            and_(
                BookingCalendarEvent.hostel_id == hostel_id,
                BookingCalendarEvent.is_high_priority == True,
                BookingCalendarEvent.deleted_at.is_(None),
            )
        )
        
        if date_from:
            query = query.where(BookingCalendarEvent.event_date >= date_from)
        
        if date_to:
            query = query.where(BookingCalendarEvent.event_date <= date_to)
        
        query = query.order_by(BookingCalendarEvent.event_date.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_events_requiring_action(
        self,
        hostel_id: UUID,
    ) -> List[BookingCalendarEvent]:
        """
        Find events that require admin action.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            List of events requiring action
        """
        query = select(BookingCalendarEvent).where(
            and_(
                BookingCalendarEvent.hostel_id == hostel_id,
                BookingCalendarEvent.requires_action == True,
                BookingCalendarEvent.deleted_at.is_(None),
            )
        ).order_by(
            BookingCalendarEvent.event_date.asc()
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def mark_action_completed(
        self,
        event_id: UUID,
    ) -> BookingCalendarEvent:
        """
        Mark event action as completed.
        
        Args:
            event_id: Event UUID
            
        Returns:
            Updated event
        """
        event = self.find_by_id(event_id)
        if not event:
            raise EntityNotFoundError(f"Calendar event {event_id} not found")
        
        event.clear_action_required()
        
        self.session.flush()
        self.session.refresh(event)
        
        return event


class DayAvailabilityRepository(BaseRepository[DayAvailability]):
    """
    Repository for day-by-day availability tracking.
    
    Provides:
    - Availability calculation and caching
    - Occupancy tracking
    - Availability forecasting
    """
    
    def __init__(self, session: Session):
        """Initialize day availability repository."""
        super().__init__(session, DayAvailability)
    
    # ==================== AVAILABILITY OPERATIONS ====================
    
    def find_or_create_for_date(
        self,
        hostel_id: UUID,
        availability_date: date,
        room_id: Optional[UUID] = None,
    ) -> DayAvailability:
        """
        Find or create availability record for a specific date.
        
        Args:
            hostel_id: Hostel UUID
            availability_date: Date
            room_id: Optional room UUID for room-specific availability
            
        Returns:
            Day availability record
        """
        query = select(DayAvailability).where(
            and_(
                DayAvailability.hostel_id == hostel_id,
                DayAvailability.availability_date == availability_date,
            )
        )
        
        if room_id:
            query = query.where(DayAvailability.room_id == room_id)
        else:
            query = query.where(DayAvailability.room_id.is_(None))
        
        result = self.session.execute(query)
        availability = result.scalar_one_or_none()
        
        if not availability:
            # Create new record
            availability = DayAvailability(
                hostel_id=hostel_id,
                room_id=room_id,
                availability_date=availability_date,
            )
            self.session.add(availability)
            self.session.flush()
        
        return availability
    
    def calculate_and_update_availability(
        self,
        hostel_id: UUID,
        availability_date: date,
        room_id: Optional[UUID] = None,
    ) -> DayAvailability:
        """
        Calculate and update availability for a date.
        
        Args:
            hostel_id: Hostel UUID
            availability_date: Date to calculate
            room_id: Optional room UUID
            
        Returns:
            Updated availability record
        """
        availability = self.find_or_create_for_date(hostel_id, availability_date, room_id)
        
        # Query total beds
        bed_query = select(func.count(Bed.id)).join(
            Room,
            Bed.room_id == Room.id
        ).where(
            and_(
                Room.hostel_id == hostel_id,
                Bed.deleted_at.is_(None),
                Room.deleted_at.is_(None),
            )
        )
        
        if room_id:
            bed_query = bed_query.where(Room.id == room_id)
        
        availability.total_beds = self.session.execute(bed_query).scalar_one()
        
        # Count beds by status
        for status in [BedStatus.OCCUPIED, BedStatus.RESERVED, BedStatus.MAINTENANCE, BedStatus.BLOCKED]:
            status_query = select(func.count(Bed.id)).join(
                Room,
                Bed.room_id == Room.id
            ).where(
                and_(
                    Room.hostel_id == hostel_id,
                    Bed.status == status,
                    Bed.deleted_at.is_(None),
                    Room.deleted_at.is_(None),
                )
            )
            
            if room_id:
                status_query = status_query.where(Room.id == room_id)
            
            count = self.session.execute(status_query).scalar_one()
            
            if status == BedStatus.OCCUPIED:
                availability.occupied_beds = count
            elif status == BedStatus.RESERVED:
                availability.reserved_beds = count
            elif status == BedStatus.MAINTENANCE:
                availability.maintenance_beds = count
            elif status == BedStatus.BLOCKED:
                availability.blocked_beds = count
        
        # Calculate availability
        availability.calculate_availability()
        
        self.session.flush()
        self.session.refresh(availability)
        
        return availability
    
    def get_availability_for_date_range(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        room_id: Optional[UUID] = None,
    ) -> List[DayAvailability]:
        """
        Get availability records for a date range.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Range start
            end_date: Range end
            room_id: Optional room filter
            
        Returns:
            List of availability records
        """
        query = select(DayAvailability).where(
            and_(
                DayAvailability.hostel_id == hostel_id,
                DayAvailability.availability_date >= start_date,
                DayAvailability.availability_date <= end_date,
            )
        )
        
        if room_id:
            query = query.where(DayAvailability.room_id == room_id)
        else:
            query = query.where(DayAvailability.room_id.is_(None))
        
        query = query.order_by(DayAvailability.availability_date.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_fully_booked_dates(
        self,
        hostel_id: UUID,
        date_from: date,
        date_to: date,
    ) -> List[date]:
        """
        Find dates when hostel is fully booked.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Range start
            date_to: Range end
            
        Returns:
            List of fully booked dates
        """
        query = select(DayAvailability.availability_date).where(
            and_(
                DayAvailability.hostel_id == hostel_id,
                DayAvailability.is_fully_booked == True,
                DayAvailability.availability_date >= date_from,
                DayAvailability.availability_date <= date_to,
            )
        ).order_by(DayAvailability.availability_date.asc())
        
        result = self.session.execute(query)
        return [row[0] for row in result.all()]
    
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
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        availabilities = self.get_availability_for_date_range(
            hostel_id,
            start_date,
            end_date
        )
        
        return [
            {
                "date": avail.availability_date,
                "total_beds": avail.total_beds,
                "occupied_beds": avail.occupied_beds,
                "available_beds": avail.available_beds,
                "occupancy_rate": avail.occupancy_rate,
            }
            for avail in availabilities
        ]


class CalendarBlockRepository(BaseRepository[CalendarBlock]):
    """
    Repository for calendar blocking management.
    
    Provides:
    - Block creation and management
    - Conflict detection
    - Block impact analysis
    - Completion tracking
    """
    
    def __init__(self, session: Session):
        """Initialize calendar block repository."""
        super().__init__(session, CalendarBlock)
    
    # ==================== BLOCK OPERATIONS ====================
    
    def create_block(
        self,
        block_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> CalendarBlock:
        """
        Create calendar block.
        
        Args:
            block_data: Block information
            audit_context: Audit context
            
        Returns:
            Created block
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate dates
        start_date = block_data.get('start_date')
        end_date = block_data.get('end_date')
        
        if end_date < start_date:
            raise ValidationError("End date must be after or equal to start date")
        
        block = CalendarBlock(
            blocked_by=audit_context.user_id if audit_context else None,
            **block_data,
        )
        
        created = self.create(block, audit_context)
        
        # Calculate affected bookings if needed
        if created.affects_bookings:
            affected_count = self._count_affected_bookings(created)
            created.affected_booking_count = affected_count
            self.session.flush()
        
        return created
    
    def _count_affected_bookings(self, block: CalendarBlock) -> int:
        """Count bookings affected by a block."""
        query = select(func.count(Booking.id)).where(
            and_(
                Booking.hostel_id == block.hostel_id,
                Booking.booking_status.in_([
                    BookingStatus.APPROVED,
                    BookingStatus.CONFIRMED,
                ]),
                Booking.preferred_check_in_date <= block.end_date,
                func.date(
                    Booking.preferred_check_in_date +
                    func.cast(Booking.stay_duration_months * 30, func.text('interval day'))
                ) >= block.start_date,
                Booking.deleted_at.is_(None),
            )
        )
        
        if block.room_id:
            # Check assignments
            from app.models.booking.booking_assignment import BookingAssignment
            query = query.join(
                BookingAssignment,
                Booking.id == BookingAssignment.booking_id
            ).where(
                BookingAssignment.room_id == block.room_id
            )
        
        return self.session.execute(query).scalar_one()
    
    def find_active_blocks(
        self,
        hostel_id: UUID,
        as_of_date: Optional[date] = None,
    ) -> List[CalendarBlock]:
        """
        Find active blocks for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            as_of_date: Optional date to check (default: today)
            
        Returns:
            List of active blocks
        """
        check_date = as_of_date or date.today()
        
        query = select(CalendarBlock).where(
            and_(
                CalendarBlock.hostel_id == hostel_id,
                CalendarBlock.is_active == True,
                CalendarBlock.start_date <= check_date,
                CalendarBlock.end_date >= check_date,
                CalendarBlock.deleted_at.is_(None),
            )
        ).options(
            joinedload(CalendarBlock.room),
            joinedload(CalendarBlock.bed),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_blocks_for_date_range(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        room_id: Optional[UUID] = None,
    ) -> List[CalendarBlock]:
        """
        Find blocks overlapping with a date range.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Range start
            end_date: Range end
            room_id: Optional room filter
            
        Returns:
            List of overlapping blocks
        """
        query = select(CalendarBlock).where(
            and_(
                CalendarBlock.hostel_id == hostel_id,
                CalendarBlock.is_active == True,
                or_(
                    # Block starts during range
                    and_(
                        CalendarBlock.start_date >= start_date,
                        CalendarBlock.start_date <= end_date,
                    ),
                    # Block ends during range
                    and_(
                        CalendarBlock.end_date >= start_date,
                        CalendarBlock.end_date <= end_date,
                    ),
                    # Block completely contains range
                    and_(
                        CalendarBlock.start_date <= start_date,
                        CalendarBlock.end_date >= end_date,
                    )
                ),
                CalendarBlock.deleted_at.is_(None),
            )
        )
        
        if room_id:
            query = query.where(
                or_(
                    CalendarBlock.room_id == room_id,
                    CalendarBlock.room_id.is_(None),  # Hostel-wide blocks
                )
            )
        
        query = query.order_by(CalendarBlock.start_date.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_upcoming_blocks(
        self,
        hostel_id: UUID,
        days_ahead: int = 30,
    ) -> List[CalendarBlock]:
        """
        Find upcoming blocks.
        
        Args:
            hostel_id: Hostel UUID
            days_ahead: Days to look ahead
            
        Returns:
            List of upcoming blocks
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)
        
        query = select(CalendarBlock).where(
            and_(
                CalendarBlock.hostel_id == hostel_id,
                CalendarBlock.is_active == True,
                CalendarBlock.start_date > today,
                CalendarBlock.start_date <= end_date,
                CalendarBlock.deleted_at.is_(None),
            )
        ).order_by(CalendarBlock.start_date.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def mark_completed(
        self,
        block_id: UUID,
        completion_notes: Optional[str] = None,
    ) -> CalendarBlock:
        """
        Mark block as completed.
        
        Args:
            block_id: Block UUID
            completion_notes: Optional completion notes
            
        Returns:
            Updated block
        """
        block = self.find_by_id(block_id)
        if not block:
            raise EntityNotFoundError(f"Calendar block {block_id} not found")
        
        block.mark_completed(completion_notes)
        
        self.session.flush()
        self.session.refresh(block)
        
        return block
    
    def send_notification(
        self,
        block_id: UUID,
    ) -> CalendarBlock:
        """
        Mark notification as sent for a block.
        
        Args:
            block_id: Block UUID
            
        Returns:
            Updated block
        """
        block = self.find_by_id(block_id)
        if not block:
            raise EntityNotFoundError(f"Calendar block {block_id} not found")
        
        block.send_notification()
        
        self.session.flush()
        self.session.refresh(block)
        
        return block
    
    def get_block_statistics(
        self,
        hostel_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, any]:
        """
        Get statistics about calendar blocks.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = select(CalendarBlock).where(
            and_(
                CalendarBlock.hostel_id == hostel_id,
                CalendarBlock.deleted_at.is_(None),
            )
        )
        
        if date_from:
            query = query.where(CalendarBlock.start_date >= date_from)
        
        if date_to:
            query = query.where(CalendarBlock.end_date <= date_to)
        
        blocks = self.session.execute(query).scalars().all()
        
        total_blocks = len(blocks)
        active_blocks = sum(1 for b in blocks if b.is_active)
        completed_blocks = sum(1 for b in blocks if b.is_completed)
        
        # Group by type
        by_type = {}
        for block in blocks:
            by_type[block.block_type] = by_type.get(block.block_type, 0) + 1
        
        # Total affected bookings
        total_affected = sum(b.affected_booking_count for b in blocks)
        
        # Average duration
        total_days = sum(b.duration_days for b in blocks)
        avg_duration = total_days / total_blocks if total_blocks > 0 else 0
        
        return {
            "total_blocks": total_blocks,
            "active_blocks": active_blocks,
            "completed_blocks": completed_blocks,
            "completion_rate": (completed_blocks / total_blocks * 100) if total_blocks > 0 else 0,
            "blocks_by_type": by_type,
            "total_affected_bookings": total_affected,
            "average_duration_days": avg_duration,
        }