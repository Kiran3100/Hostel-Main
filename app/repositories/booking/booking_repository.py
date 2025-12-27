# app/repositories/booking/booking_repository.py
"""
Booking repository for comprehensive booking management.

Provides advanced search, availability checking, booking optimization,
lifecycle management, and analytics for hostel bookings.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core1.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking import Booking, BookingNote, BookingStatusHistory
from app.models.base.enums import BookingSource, BookingStatus, RoomType
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingSearchCriteria:
    """Advanced search criteria for bookings."""
    
    def __init__(
        self,
        booking_reference: Optional[str] = None,
        visitor_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        hostel_ids: Optional[List[UUID]] = None,
        status: Optional[BookingStatus] = None,
        statuses: Optional[List[BookingStatus]] = None,
        source: Optional[BookingSource] = None,
        room_type: Optional[RoomType] = None,
        check_in_date_from: Optional[date] = None,
        check_in_date_to: Optional[date] = None,
        booking_date_from: Optional[datetime] = None,
        booking_date_to: Optional[datetime] = None,
        advance_paid: Optional[bool] = None,
        converted_to_student: Optional[bool] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        expiring_within_hours: Optional[int] = None,
        is_expired: Optional[bool] = None,
        referral_code: Optional[str] = None,
        guest_email: Optional[str] = None,
        guest_phone: Optional[str] = None,
    ):
        self.booking_reference = booking_reference
        self.visitor_id = visitor_id
        self.hostel_id = hostel_id
        self.hostel_ids = hostel_ids
        self.status = status
        self.statuses = statuses
        self.source = source
        self.room_type = room_type
        self.check_in_date_from = check_in_date_from
        self.check_in_date_to = check_in_date_to
        self.booking_date_from = booking_date_from
        self.booking_date_to = booking_date_to
        self.advance_paid = advance_paid
        self.converted_to_student = converted_to_student
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.expiring_within_hours = expiring_within_hours
        self.is_expired = is_expired
        self.referral_code = referral_code
        self.guest_email = guest_email
        self.guest_phone = guest_phone


class BookingStatistics:
    """Booking statistics data structure."""
    
    def __init__(self):
        self.total_bookings: int = 0
        self.pending_bookings: int = 0
        self.approved_bookings: int = 0
        self.confirmed_bookings: int = 0
        self.cancelled_bookings: int = 0
        self.completed_bookings: int = 0
        self.total_revenue: Decimal = Decimal("0.00")
        self.average_booking_value: Decimal = Decimal("0.00")
        self.conversion_rate: float = 0.0
        self.cancellation_rate: float = 0.0
        self.advance_payment_rate: float = 0.0


class BookingRepository(BaseRepository[Booking]):
    """
    Repository for booking operations.
    
    Provides:
    - Advanced booking search and filtering
    - Availability checking and conflict resolution
    - Dynamic pricing calculations
    - Booking lifecycle management
    - Status tracking and transitions
    - Analytics and reporting
    - Booking optimization
    """
    
    def __init__(self, session: Session):
        """Initialize booking repository."""
        super().__init__(session, Booking)
    
    # ==================== SEARCH & RETRIEVAL ====================
    
    def search_bookings(
        self,
        criteria: BookingSearchCriteria,
        page: int = 1,
        page_size: int = 50,
        order_by: Optional[List[str]] = None,
        options: Optional[QueryOptions] = None,
    ) -> Tuple[List[Booking], int]:
        """
        Advanced booking search with multiple criteria.
        
        Args:
            criteria: Search criteria
            page: Page number (1-indexed)
            page_size: Results per page
            order_by: List of fields to order by
            options: Query options
            
        Returns:
            Tuple of (bookings list, total count)
        """
        options = options or QueryOptions()
        
        # Build base query
        query = select(Booking)
        count_query = select(func.count(Booking.id))
        
        # Apply filters
        filters = self._build_search_filters(criteria)
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Apply soft delete filter
        if not options.include_deleted:
            query = query.where(Booking.deleted_at.is_(None))
            count_query = count_query.where(Booking.deleted_at.is_(None))
        
        # Get total count
        total = self.session.execute(count_query).scalar_one()
        
        # Apply ordering
        if order_by:
            for order_field in order_by:
                if order_field.startswith("-"):
                    field_name = order_field[1:]
                    if hasattr(Booking, field_name):
                        query = query.order_by(getattr(Booking, field_name).desc())
                else:
                    if hasattr(Booking, order_field):
                        query = query.order_by(getattr(Booking, order_field).asc())
        else:
            # Default ordering: newest first
            query = query.order_by(Booking.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Apply prefetching
        if options.prefetch_relationships:
            query = self._apply_prefetch(query, options.prefetch_relationships)
        else:
            # Default prefetch common relationships
            query = query.options(
                joinedload(Booking.visitor),
                joinedload(Booking.hostel),
                selectinload(Booking.guest_info),
            )
        
        # Execute query
        result = self.session.execute(query)
        bookings = list(result.scalars().all())
        
        return bookings, total
    
    def _build_search_filters(self, criteria: BookingSearchCriteria) -> List:
        """Build SQLAlchemy filters from search criteria."""
        filters = []
        
        if criteria.booking_reference:
            filters.append(Booking.booking_reference == criteria.booking_reference)
        
        if criteria.visitor_id:
            filters.append(Booking.visitor_id == criteria.visitor_id)
        
        if criteria.hostel_id:
            filters.append(Booking.hostel_id == criteria.hostel_id)
        
        if criteria.hostel_ids:
            filters.append(Booking.hostel_id.in_(criteria.hostel_ids))
        
        if criteria.status:
            filters.append(Booking.booking_status == criteria.status)
        
        if criteria.statuses:
            filters.append(Booking.booking_status.in_(criteria.statuses))
        
        if criteria.source:
            filters.append(Booking.source == criteria.source)
        
        if criteria.room_type:
            filters.append(Booking.room_type_requested == criteria.room_type)
        
        if criteria.check_in_date_from:
            filters.append(Booking.preferred_check_in_date >= criteria.check_in_date_from)
        
        if criteria.check_in_date_to:
            filters.append(Booking.preferred_check_in_date <= criteria.check_in_date_to)
        
        if criteria.booking_date_from:
            filters.append(Booking.booking_date >= criteria.booking_date_from)
        
        if criteria.booking_date_to:
            filters.append(Booking.booking_date <= criteria.booking_date_to)
        
        if criteria.advance_paid is not None:
            filters.append(Booking.advance_paid == criteria.advance_paid)
        
        if criteria.converted_to_student is not None:
            filters.append(Booking.converted_to_student == criteria.converted_to_student)
        
        if criteria.min_amount:
            filters.append(Booking.total_amount >= criteria.min_amount)
        
        if criteria.max_amount:
            filters.append(Booking.total_amount <= criteria.max_amount)
        
        if criteria.expiring_within_hours:
            expiry_threshold = datetime.utcnow() + timedelta(hours=criteria.expiring_within_hours)
            filters.append(Booking.expires_at.isnot(None))
            filters.append(Booking.expires_at <= expiry_threshold)
            filters.append(Booking.expires_at > datetime.utcnow())
        
        if criteria.is_expired is not None:
            if criteria.is_expired:
                filters.append(Booking.expires_at.isnot(None))
                filters.append(Booking.expires_at <= datetime.utcnow())
            else:
                filters.append(
                    or_(
                        Booking.expires_at.is_(None),
                        Booking.expires_at > datetime.utcnow()
                    )
                )
        
        if criteria.referral_code:
            filters.append(Booking.referral_code == criteria.referral_code)
        
        # Guest info filters (requires join)
        if criteria.guest_email or criteria.guest_phone:
            from app.models.booking.booking_guest import BookingGuest
            
            if criteria.guest_email:
                filters.append(BookingGuest.guest_email == criteria.guest_email)
            
            if criteria.guest_phone:
                filters.append(BookingGuest.guest_phone == criteria.guest_phone)
        
        return filters
    
    def find_by_reference(self, booking_reference: str) -> Optional[Booking]:
        """
        Find booking by reference number.
        
        Args:
            booking_reference: Booking reference
            
        Returns:
            Booking if found, None otherwise
        """
        query = select(Booking).where(
            Booking.booking_reference == booking_reference
        ).where(
            Booking.deleted_at.is_(None)
        ).options(
            joinedload(Booking.visitor),
            joinedload(Booking.hostel),
            selectinload(Booking.guest_info),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def find_by_visitor(
        self,
        visitor_id: UUID,
        status: Optional[BookingStatus] = None,
        limit: Optional[int] = None,
    ) -> List[Booking]:
        """
        Find bookings for a specific visitor.
        
        Args:
            visitor_id: Visitor UUID
            status: Optional status filter
            limit: Optional result limit
            
        Returns:
            List of visitor's bookings
        """
        query = select(Booking).where(
            Booking.visitor_id == visitor_id
        ).where(
            Booking.deleted_at.is_(None)
        )
        
        if status:
            query = query.where(Booking.booking_status == status)
        
        query = query.order_by(Booking.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        query = query.options(
            joinedload(Booking.hostel),
            selectinload(Booking.guest_info),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        status: Optional[BookingStatus] = None,
        check_in_date_from: Optional[date] = None,
        check_in_date_to: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[Booking]:
        """
        Find bookings for a specific hostel.
        
        Args:
            hostel_id: Hostel UUID
            status: Optional status filter
            check_in_date_from: Optional check-in date range start
            check_in_date_to: Optional check-in date range end
            limit: Optional result limit
            
        Returns:
            List of hostel bookings
        """
        query = select(Booking).where(
            Booking.hostel_id == hostel_id
        ).where(
            Booking.deleted_at.is_(None)
        )
        
        if status:
            query = query.where(Booking.booking_status == status)
        
        if check_in_date_from:
            query = query.where(Booking.preferred_check_in_date >= check_in_date_from)
        
        if check_in_date_to:
            query = query.where(Booking.preferred_check_in_date <= check_in_date_to)
        
        query = query.order_by(Booking.preferred_check_in_date.asc())
        
        if limit:
            query = query.limit(limit)
        
        query = query.options(
            joinedload(Booking.visitor),
            selectinload(Booking.guest_info),
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    # ==================== BOOKING LIFECYCLE ====================
    
    def create_booking_request(
        self,
        booking_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> Booking:
        """
        Create new booking request with validation.
        
        Args:
            booking_data: Booking information
            audit_context: Audit context
            
        Returns:
            Created booking
            
        Raises:
            ValidationError: If validation fails
        """
        # Create booking instance
        booking = Booking(**booking_data)
        
        # Set default status
        if not booking.booking_status:
            booking.booking_status = BookingStatus.PENDING
        
        # Set booking date
        if not booking.booking_date:
            booking.booking_date = datetime.utcnow()
        
        # Calculate total amount if not provided
        if not booking.total_amount and booking.quoted_rent_monthly:
            booking.total_amount = (
                booking.quoted_rent_monthly * booking.stay_duration_months
            )
        
        # Set expiry time for pending bookings
        if booking.booking_status == BookingStatus.PENDING and not booking.expires_at:
            booking.set_expiry(hours=48)  # Default 48-hour expiry
        
        # Create with audit
        created_booking = self.create(booking, audit_context)
        
        # Create initial status history
        self._create_status_history(
            created_booking,
            None,
            BookingStatus.PENDING,
            audit_context,
        )
        
        return created_booking
    
    def approve_booking(
        self,
        booking_id: UUID,
        approved_by_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Booking:
        """
        Approve a pending booking.
        
        Args:
            booking_id: Booking UUID
            approved_by_id: Admin UUID approving the booking
            audit_context: Audit context
            
        Returns:
            Approved booking
            
        Raises:
            EntityNotFoundError: If booking not found
            ValidationError: If booking cannot be approved
        """
        booking = self.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        # Use booking's approve method
        old_status = booking.booking_status
        booking.approve(approved_by_id)
        
        # Update
        self.session.flush()
        self.session.refresh(booking)
        
        # Create status history
        self._create_status_history(
            booking,
            old_status,
            BookingStatus.APPROVED,
            audit_context,
            f"Approved by admin {approved_by_id}",
        )
        
        return booking
    
    def reject_booking(
        self,
        booking_id: UUID,
        rejected_by_id: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> Booking:
        """
        Reject a pending booking.
        
        Args:
            booking_id: Booking UUID
            rejected_by_id: Admin UUID rejecting the booking
            reason: Rejection reason
            audit_context: Audit context
            
        Returns:
            Rejected booking
        """
        booking = self.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        old_status = booking.booking_status
        booking.reject(rejected_by_id, reason)
        
        self.session.flush()
        self.session.refresh(booking)
        
        self._create_status_history(
            booking,
            old_status,
            BookingStatus.REJECTED,
            audit_context,
            f"Rejected: {reason}",
        )
        
        return booking
    
    def confirm_booking(
        self,
        booking_id: UUID,
        payment_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Booking:
        """
        Confirm booking after advance payment.
        
        Args:
            booking_id: Booking UUID
            payment_id: Payment transaction UUID
            audit_context: Audit context
            
        Returns:
            Confirmed booking
        """
        booking = self.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        old_status = booking.booking_status
        booking.confirm_payment(payment_id)
        
        self.session.flush()
        self.session.refresh(booking)
        
        self._create_status_history(
            booking,
            old_status,
            BookingStatus.CONFIRMED,
            audit_context,
            f"Payment confirmed: {payment_id}",
        )
        
        return booking
    
    def cancel_booking(
        self,
        booking_id: UUID,
        cancelled_by_id: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> Booking:
        """
        Cancel a booking.
        
        Args:
            booking_id: Booking UUID
            cancelled_by_id: User UUID cancelling the booking
            reason: Cancellation reason
            audit_context: Audit context
            
        Returns:
            Cancelled booking
        """
        booking = self.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        old_status = booking.booking_status
        booking.cancel(cancelled_by_id, reason)
        
        self.session.flush()
        self.session.refresh(booking)
        
        self._create_status_history(
            booking,
            old_status,
            BookingStatus.CANCELLED,
            audit_context,
            f"Cancelled: {reason}",
        )
        
        return booking
    
    def mark_as_checked_in(
        self,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Booking:
        """
        Mark booking as checked in.
        
        Args:
            booking_id: Booking UUID
            audit_context: Audit context
            
        Returns:
            Updated booking
        """
        booking = self.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        if booking.booking_status != BookingStatus.CONFIRMED:
            raise ValidationError("Only confirmed bookings can be checked in")
        
        old_status = booking.booking_status
        booking.booking_status = BookingStatus.CHECKED_IN
        
        self.session.flush()
        self.session.refresh(booking)
        
        self._create_status_history(
            booking,
            old_status,
            BookingStatus.CHECKED_IN,
            audit_context,
            "Guest checked in",
        )
        
        return booking
    
    def mark_as_completed(
        self,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Booking:
        """
        Mark booking as completed.
        
        Args:
            booking_id: Booking UUID
            audit_context: Audit context
            
        Returns:
            Completed booking
        """
        booking = self.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        old_status = booking.booking_status
        booking.mark_as_completed()
        
        self.session.flush()
        self.session.refresh(booking)
        
        self._create_status_history(
            booking,
            old_status,
            BookingStatus.COMPLETED,
            audit_context,
            "Booking completed",
        )
        
        return booking
    
    def mark_as_no_show(
        self,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Booking:
        """
        Mark booking as no-show.
        
        Args:
            booking_id: Booking UUID
            audit_context: Audit context
            
        Returns:
            Updated booking
        """
        booking = self.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        old_status = booking.booking_status
        booking.mark_as_no_show()
        
        self.session.flush()
        self.session.refresh(booking)
        
        self._create_status_history(
            booking,
            old_status,
            BookingStatus.NO_SHOW,
            audit_context,
            "Guest did not show up",
        )
        
        return booking
    
    # ==================== STATUS TRACKING ====================
    
    def _create_status_history(
        self,
        booking: Booking,
        from_status: Optional[BookingStatus],
        to_status: BookingStatus,
        audit_context: Optional[AuditContext] = None,
        reason: Optional[str] = None,
    ) -> BookingStatusHistory:
        """Create status history entry."""
        history = BookingStatusHistory(
            booking_id=booking.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=audit_context.user_id if audit_context else None,
            change_reason=reason,
            changed_at=datetime.utcnow(),
        )
        
        self.session.add(history)
        self.session.flush()
        
        return history
    
    def get_status_history(self, booking_id: UUID) -> List[BookingStatusHistory]:
        """
        Get status change history for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            List of status changes
        """
        query = select(BookingStatusHistory).where(
            BookingStatusHistory.booking_id == booking_id
        ).order_by(
            BookingStatusHistory.changed_at.desc()
        ).options(
            joinedload(BookingStatusHistory.changer)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    # ==================== NOTES ====================
    
    def add_note(
        self,
        booking_id: UUID,
        note_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingNote:
        """
        Add note to booking.
        
        Args:
            booking_id: Booking UUID
            note_data: Note information
            audit_context: Audit context
            
        Returns:
            Created note
        """
        note = BookingNote(
            booking_id=booking_id,
            created_by=audit_context.user_id if audit_context else None,
            **note_data,
        )
        
        self.session.add(note)
        self.session.flush()
        
        return note
    
    def get_notes(
        self,
        booking_id: UUID,
        include_deleted: bool = False,
    ) -> List[BookingNote]:
        """
        Get notes for a booking.
        
        Args:
            booking_id: Booking UUID
            include_deleted: Whether to include deleted notes
            
        Returns:
            List of notes
        """
        query = select(BookingNote).where(
            BookingNote.booking_id == booking_id
        )
        
        if not include_deleted:
            query = query.where(BookingNote.deleted_at.is_(None))
        
        query = query.order_by(
            BookingNote.is_pinned.desc(),
            BookingNote.created_at.desc()
        ).options(
            joinedload(BookingNote.creator)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    # ==================== AVAILABILITY & CONFLICTS ====================
    
    def check_availability(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        check_in_date: date,
        duration_months: int,
    ) -> bool:
        """
        Check if booking is available for given parameters.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Requested room type
            check_in_date: Desired check-in date
            duration_months: Stay duration in months
            
        Returns:
            True if available, False otherwise
        """
        # Calculate check-out date
        check_out_date = check_in_date + timedelta(days=duration_months * 30)
        
        # Query for conflicting bookings
        query = select(func.count(Booking.id)).where(
            and_(
                Booking.hostel_id == hostel_id,
                Booking.room_type_requested == room_type,
                Booking.booking_status.in_([
                    BookingStatus.APPROVED,
                    BookingStatus.CONFIRMED,
                    BookingStatus.CHECKED_IN,
                ]),
                Booking.deleted_at.is_(None),
                or_(
                    # New booking starts during existing booking
                    and_(
                        Booking.preferred_check_in_date <= check_in_date,
                        func.date(
                            Booking.preferred_check_in_date +
                            func.cast(Booking.stay_duration_months * 30, func.text('interval day'))
                        ) > check_in_date
                    ),
                    # New booking ends during existing booking
                    and_(
                        Booking.preferred_check_in_date < check_out_date,
                        func.date(
                            Booking.preferred_check_in_date +
                            func.cast(Booking.stay_duration_months * 30, func.text('interval day'))
                        ) >= check_out_date
                    ),
                    # New booking completely contains existing booking
                    and_(
                        Booking.preferred_check_in_date >= check_in_date,
                        func.date(
                            Booking.preferred_check_in_date +
                            func.cast(Booking.stay_duration_months * 30, func.text('interval day'))
                        ) <= check_out_date
                    )
                )
            )
        )
        
        conflicts = self.session.execute(query).scalar_one()
        return conflicts == 0
    
    def find_conflicting_bookings(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        check_in_date: date,
        duration_months: int,
        exclude_booking_id: Optional[UUID] = None,
    ) -> List[Booking]:
        """
        Find bookings that conflict with given parameters.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Requested room type
            check_in_date: Desired check-in date
            duration_months: Stay duration
            exclude_booking_id: Booking ID to exclude (for modifications)
            
        Returns:
            List of conflicting bookings
        """
        check_out_date = check_in_date + timedelta(days=duration_months * 30)
        
        query = select(Booking).where(
            and_(
                Booking.hostel_id == hostel_id,
                Booking.room_type_requested == room_type,
                Booking.booking_status.in_([
                    BookingStatus.APPROVED,
                    BookingStatus.CONFIRMED,
                    BookingStatus.CHECKED_IN,
                ]),
                Booking.deleted_at.is_(None),
                or_(
                    and_(
                        Booking.preferred_check_in_date <= check_in_date,
                        func.date(
                            Booking.preferred_check_in_date +
                            func.cast(Booking.stay_duration_months * 30, func.text('interval day'))
                        ) > check_in_date
                    ),
                    and_(
                        Booking.preferred_check_in_date < check_out_date,
                        func.date(
                            Booking.preferred_check_in_date +
                            func.cast(Booking.stay_duration_months * 30, func.text('interval day'))
                        ) >= check_out_date
                    ),
                    and_(
                        Booking.preferred_check_in_date >= check_in_date,
                        func.date(
                            Booking.preferred_check_in_date +
                            func.cast(Booking.stay_duration_months * 30, func.text('interval day'))
                        ) <= check_out_date
                    )
                )
            )
        )
        
        if exclude_booking_id:
            query = query.where(Booking.id != exclude_booking_id)
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    # ==================== EXPIRY MANAGEMENT ====================
    
    def find_expiring_bookings(
        self,
        within_hours: int = 24,
        hostel_id: Optional[UUID] = None,
    ) -> List[Booking]:
        """
        Find bookings expiring within specified hours.
        
        Args:
            within_hours: Hours threshold
            hostel_id: Optional hostel filter
            
        Returns:
            List of expiring bookings
        """
        expiry_threshold = datetime.utcnow() + timedelta(hours=within_hours)
        
        query = select(Booking).where(
            and_(
                Booking.booking_status == BookingStatus.PENDING,
                Booking.expires_at.isnot(None),
                Booking.expires_at <= expiry_threshold,
                Booking.expires_at > datetime.utcnow(),
                Booking.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.order_by(Booking.expires_at.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_expired_bookings(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Booking]:
        """
        Find bookings that have expired.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of expired bookings
        """
        query = select(Booking).where(
            and_(
                Booking.booking_status == BookingStatus.PENDING,
                Booking.expires_at.isnot(None),
                Booking.expires_at <= datetime.utcnow(),
                Booking.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.order_by(Booking.expires_at.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def expire_pending_bookings(
        self,
        audit_context: Optional[AuditContext] = None,
    ) -> int:
        """
        Automatically expire pending bookings past their expiry time.
        
        Args:
            audit_context: Audit context
            
        Returns:
            Number of expired bookings
        """
        expired_bookings = self.find_expired_bookings()
        count = 0
        
        for booking in expired_bookings:
            old_status = booking.booking_status
            booking.booking_status = BookingStatus.EXPIRED
            
            self._create_status_history(
                booking,
                old_status,
                BookingStatus.EXPIRED,
                audit_context,
                "Booking expired automatically",
            )
            
            count += 1
        
        if count > 0:
            self.session.flush()
        
        return count
    
    # ==================== ANALYTICS ====================
    
    def get_booking_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> BookingStatistics:
        """
        Get booking statistics for analysis.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Booking statistics
        """
        stats = BookingStatistics()
        
        # Build base query
        base_query = select(Booking).where(Booking.deleted_at.is_(None))
        
        if hostel_id:
            base_query = base_query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            base_query = base_query.where(Booking.booking_date >= date_from)
        
        if date_to:
            base_query = base_query.where(Booking.booking_date <= date_to)
        
        # Total bookings
        count_query = select(func.count(Booking.id)).select_from(base_query.subquery())
        stats.total_bookings = self.session.execute(count_query).scalar_one()
        
        if stats.total_bookings == 0:
            return stats
        
        # Count by status
        for status in BookingStatus:
            status_query = select(func.count(Booking.id)).select_from(
                base_query.where(Booking.booking_status == status).subquery()
            )
            count = self.session.execute(status_query).scalar_one()
            
            if status == BookingStatus.PENDING:
                stats.pending_bookings = count
            elif status == BookingStatus.APPROVED:
                stats.approved_bookings = count
            elif status == BookingStatus.CONFIRMED:
                stats.confirmed_bookings = count
            elif status == BookingStatus.CANCELLED:
                stats.cancelled_bookings = count
            elif status == BookingStatus.COMPLETED:
                stats.completed_bookings = count
        
        # Total revenue (from confirmed/completed bookings)
        revenue_query = select(func.sum(Booking.total_amount)).select_from(
            base_query.where(
                Booking.booking_status.in_([
                    BookingStatus.CONFIRMED,
                    BookingStatus.CHECKED_IN,
                    BookingStatus.COMPLETED,
                ])
            ).subquery()
        )
        total_revenue = self.session.execute(revenue_query).scalar_one()
        stats.total_revenue = total_revenue or Decimal("0.00")
        
        # Average booking value
        if stats.total_bookings > 0:
            stats.average_booking_value = stats.total_revenue / stats.total_bookings
        
        # Conversion rate (confirmed / total)
        confirmed_count = (
            stats.confirmed_bookings +
            stats.completed_bookings
        )
        if stats.total_bookings > 0:
            stats.conversion_rate = (confirmed_count / stats.total_bookings) * 100
        
        # Cancellation rate
        if stats.total_bookings > 0:
            stats.cancellation_rate = (stats.cancelled_bookings / stats.total_bookings) * 100
        
        # Advance payment rate
        advance_paid_query = select(func.count(Booking.id)).select_from(
            base_query.where(Booking.advance_paid == True).subquery()
        )
        advance_paid_count = self.session.execute(advance_paid_query).scalar_one()
        
        if stats.total_bookings > 0:
            stats.advance_payment_rate = (advance_paid_count / stats.total_bookings) * 100
        
        return stats
    
    def get_bookings_by_source(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[BookingSource, int]:
        """
        Get booking count by source.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Dictionary of source to count
        """
        query = select(
            Booking.source,
            func.count(Booking.id)
        ).where(
            Booking.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(Booking.booking_date >= date_from)
        
        if date_to:
            query = query.where(Booking.booking_date <= date_to)
        
        query = query.group_by(Booking.source)
        
        result = self.session.execute(query)
        return {source: count for source, count in result.all()}
    
    def get_bookings_by_room_type(
        self,
        hostel_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[RoomType, int]:
        """
        Get booking count by room type.
        
        Args:
            hostel_id: Hostel UUID
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Dictionary of room type to count
        """
        query = select(
            Booking.room_type_requested,
            func.count(Booking.id)
        ).where(
            and_(
                Booking.hostel_id == hostel_id,
                Booking.deleted_at.is_(None),
            )
        )
        
        if date_from:
            query = query.where(Booking.booking_date >= date_from)
        
        if date_to:
            query = query.where(Booking.booking_date <= date_to)
        
        query = query.group_by(Booking.room_type_requested)
        
        result = self.session.execute(query)
        return {room_type: count for room_type, count in result.all()}
    
    # ==================== REFERRAL TRACKING ====================
    
    def find_by_referral_code(
        self,
        referral_code: str,
        hostel_id: Optional[UUID] = None,
    ) -> List[Booking]:
        """
        Find bookings using a specific referral code.
        
        Args:
            referral_code: Referral code
            hostel_id: Optional hostel filter
            
        Returns:
            List of bookings with referral code
        """
        query = select(Booking).where(
            and_(
                Booking.referral_code == referral_code,
                Booking.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.order_by(Booking.created_at.desc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_referral_statistics(
        self,
        referral_code: str,
        hostel_id: Optional[UUID] = None,
    ) -> Dict[str, any]:
        """
        Get statistics for a referral code.
        
        Args:
            referral_code: Referral code
            hostel_id: Optional hostel filter
            
        Returns:
            Referral statistics
        """
        bookings = self.find_by_referral_code(referral_code, hostel_id)
        
        total_bookings = len(bookings)
        confirmed_bookings = sum(
            1 for b in bookings
            if b.booking_status in [
                BookingStatus.CONFIRMED,
                BookingStatus.CHECKED_IN,
                BookingStatus.COMPLETED,
            ]
        )
        
        total_revenue = sum(
            b.total_amount for b in bookings
            if b.booking_status in [
                BookingStatus.CONFIRMED,
                BookingStatus.CHECKED_IN,
                BookingStatus.COMPLETED,
            ]
        )
        
        return {
            "referral_code": referral_code,
            "total_bookings": total_bookings,
            "confirmed_bookings": confirmed_bookings,
            "conversion_rate": (confirmed_bookings / total_bookings * 100) if total_bookings > 0 else 0,
            "total_revenue": total_revenue,
            "average_booking_value": total_revenue / confirmed_bookings if confirmed_bookings > 0 else Decimal("0.00"),
        }