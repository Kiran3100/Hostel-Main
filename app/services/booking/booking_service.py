# app/services/booking/booking_service.py
"""
Core booking service for end-to-end booking management.

Orchestrates the complete booking lifecycle including creation, approval,
payment, assignment, and conversion workflows.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from app.models.base.enums import BookingSource, BookingStatus, RoomType, UserRole
from app.repositories.booking.booking_repository import (
    BookingRepository,
    BookingSearchCriteria,
    BookingStatistics,
)
from app.repositories.booking.booking_approval_repository import (
    ApprovalSettingsRepository,
    BookingApprovalRepository,
)
from app.repositories.booking.booking_assignment_repository import (
    BookingAssignmentRepository,
)
from app.repositories.booking.booking_guest_repository import BookingGuestRepository
from app.repositories.base.base_repository import AuditContext
from app.services.booking.booking_pricing_service import BookingPricingService
from app.services.booking.booking_notification_service import (
    BookingNotificationService,
)
from app.services.booking.booking_calendar_service import BookingCalendarService


class BookingService:
    """
    Core booking service for comprehensive booking management.
    
    Responsibilities:
    - End-to-end booking creation and validation
    - Booking lifecycle management (approve, reject, cancel, etc.)
    - Availability checking and conflict resolution
    - Integration with other booking services
    - Transaction coordination
    - Business rule enforcement
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
        approval_repo: Optional[BookingApprovalRepository] = None,
        assignment_repo: Optional[BookingAssignmentRepository] = None,
        guest_repo: Optional[BookingGuestRepository] = None,
        approval_settings_repo: Optional[ApprovalSettingsRepository] = None,
        pricing_service: Optional[BookingPricingService] = None,
        notification_service: Optional[BookingNotificationService] = None,
        calendar_service: Optional[BookingCalendarService] = None,
    ):
        """
        Initialize booking service.
        
        Args:
            session: Database session
            booking_repo: Booking repository (auto-created if not provided)
            approval_repo: Approval repository
            assignment_repo: Assignment repository
            guest_repo: Guest repository
            approval_settings_repo: Approval settings repository
            pricing_service: Pricing service
            notification_service: Notification service
            calendar_service: Calendar service
        """
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
        self.approval_repo = approval_repo or BookingApprovalRepository(session)
        self.assignment_repo = assignment_repo or BookingAssignmentRepository(session)
        self.guest_repo = guest_repo or BookingGuestRepository(session)
        self.approval_settings_repo = (
            approval_settings_repo or ApprovalSettingsRepository(session)
        )
        self.pricing_service = pricing_service or BookingPricingService(session)
        self.notification_service = (
            notification_service or BookingNotificationService(session)
        )
        self.calendar_service = calendar_service or BookingCalendarService(session)
    
    # ==================== BOOKING CREATION ====================
    
    def create_booking_request(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
        room_type: RoomType,
        check_in_date: date,
        duration_months: int,
        source: BookingSource,
        guest_info: Dict,
        special_requests: Optional[str] = None,
        dietary_preferences: Optional[str] = None,
        has_vehicle: bool = False,
        vehicle_details: Optional[str] = None,
        referral_code: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Tuple[UUID, str]:
        """
        Create a new booking request with complete validation and processing.
        
        Args:
            visitor_id: Visitor UUID
            hostel_id: Hostel UUID
            room_type: Requested room type
            check_in_date: Preferred check-in date
            duration_months: Stay duration in months
            source: Booking source
            guest_info: Guest information dictionary
            special_requests: Special requests
            dietary_preferences: Dietary preferences
            has_vehicle: Whether guest has vehicle
            vehicle_details: Vehicle details
            referral_code: Referral code
            audit_context: Audit context
            
        Returns:
            Tuple of (booking_id, booking_reference)
            
        Raises:
            ValidationError: If validation fails
            BusinessRuleViolationError: If business rules violated
        """
        try:
            # 1. Validate inputs
            self._validate_booking_request(
                hostel_id, room_type, check_in_date, duration_months
            )
            
            # 2. Check availability
            is_available = self.booking_repo.check_availability(
                hostel_id, room_type, check_in_date, duration_months
            )
            
            if not is_available:
                raise BusinessRuleViolationError(
                    "No availability for the requested dates and room type"
                )
            
            # 3. Calculate pricing
            pricing = self.pricing_service.calculate_booking_price(
                hostel_id=hostel_id,
                room_type=room_type,
                duration_months=duration_months,
                check_in_date=check_in_date,
            )
            
            # 4. Create booking
            booking_data = {
                "visitor_id": visitor_id,
                "hostel_id": hostel_id,
                "room_type_requested": room_type,
                "preferred_check_in_date": check_in_date,
                "stay_duration_months": duration_months,
                "quoted_rent_monthly": pricing["monthly_rent"],
                "total_amount": pricing["total_amount"],
                "security_deposit": pricing["security_deposit"],
                "advance_amount": pricing["advance_amount"],
                "source": source,
                "special_requests": special_requests,
                "dietary_preferences": dietary_preferences,
                "has_vehicle": has_vehicle,
                "vehicle_details": vehicle_details,
                "referral_code": referral_code,
            }
            
            booking = self.booking_repo.create_booking_request(
                booking_data, audit_context
            )
            
            # 5. Create guest information
            guest_info["booking_id"] = booking.id
            self.guest_repo.create_guest_info(guest_info, audit_context)
            
            # 6. Create calendar event
            self.calendar_service.create_booking_request_event(
                booking, audit_context
            )
            
            # 7. Check for auto-approval
            should_auto_approve, criteria_met = (
                self.approval_settings_repo.check_auto_approval_criteria(
                    hostel_id, booking_data
                )
            )
            
            if should_auto_approve:
                self._auto_approve_booking(booking.id, criteria_met, audit_context)
            else:
                # 8. Send pending notification
                self.notification_service.send_booking_received_notification(
                    booking.id
                )
            
            # 9. Commit transaction
            self.session.commit()
            
            return booking.id, booking.booking_reference
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def _validate_booking_request(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        check_in_date: date,
        duration_months: int,
    ) -> None:
        """Validate booking request parameters."""
        # Check-in date validation
        if check_in_date < date.today():
            raise ValidationError("Check-in date cannot be in the past")
        
        if check_in_date > date.today() + timedelta(days=365):
            raise ValidationError("Check-in date cannot be more than 1 year in future")
        
        # Duration validation
        if duration_months < 1 or duration_months > 24:
            raise ValidationError("Duration must be between 1 and 24 months")
    
    def _auto_approve_booking(
        self,
        booking_id: UUID,
        criteria_met: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> None:
        """Auto-approve a booking that meets criteria."""
        from app.services.booking.booking_approval_service import (
            BookingApprovalService,
        )
        
        approval_service = BookingApprovalService(self.session)
        
        # System user for auto-approval
        system_audit = AuditContext(
            user_id=audit_context.user_id if audit_context else None,
            user_role=UserRole.SYSTEM,
            ip_address="system",
            user_agent="auto-approval",
        )
        
        approval_service.approve_booking(
            booking_id=booking_id,
            approved_by_id=system_audit.user_id,
            approval_notes=f"Auto-approved: {criteria_met}",
            auto_approved=True,
            audit_context=system_audit,
        )
    
    # ==================== BOOKING RETRIEVAL ====================
    
    def get_booking_by_id(
        self,
        booking_id: UUID,
        include_details: bool = True,
    ) -> Dict:
        """
        Get booking by ID with optional detailed information.
        
        Args:
            booking_id: Booking UUID
            include_details: Whether to include related details
            
        Returns:
            Booking dictionary with details
            
        Raises:
            EntityNotFoundError: If booking not found
        """
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        result = self._booking_to_dict(booking)
        
        if include_details:
            # Add guest info
            guest_info = self.guest_repo.find_by_booking(booking_id)
            if guest_info:
                result["guest_info"] = self._guest_to_dict(guest_info)
            
            # Add approval info
            approval = self.approval_repo.find_by_booking(booking_id)
            if approval:
                result["approval"] = self._approval_to_dict(approval)
            
            # Add assignment info
            assignment = self.assignment_repo.find_by_booking(booking_id)
            if assignment:
                result["assignment"] = self._assignment_to_dict(assignment)
            
            # Add status history
            status_history = self.booking_repo.get_status_history(booking_id)
            result["status_history"] = [
                self._status_history_to_dict(sh) for sh in status_history
            ]
            
            # Add notes
            notes = self.booking_repo.get_notes(booking_id)
            result["notes"] = [self._note_to_dict(note) for note in notes]
        
        return result
    
    def get_booking_by_reference(self, booking_reference: str) -> Dict:
        """
        Get booking by reference number.
        
        Args:
            booking_reference: Booking reference
            
        Returns:
            Booking dictionary
        """
        booking = self.booking_repo.find_by_reference(booking_reference)
        if not booking:
            raise EntityNotFoundError(
                f"Booking with reference {booking_reference} not found"
            )
        
        return self.get_booking_by_id(booking.id)
    
    def search_bookings(
        self,
        criteria: BookingSearchCriteria,
        page: int = 1,
        page_size: int = 50,
        order_by: Optional[List[str]] = None,
    ) -> Tuple[List[Dict], int, Dict]:
        """
        Search bookings with advanced criteria.
        
        Args:
            criteria: Search criteria
            page: Page number
            page_size: Results per page
            order_by: Order by fields
            
        Returns:
            Tuple of (bookings list, total count, pagination info)
        """
        bookings, total = self.booking_repo.search_bookings(
            criteria, page, page_size, order_by
        )
        
        total_pages = (total + page_size - 1) // page_size
        
        return (
            [self._booking_to_dict(b) for b in bookings],
            total,
            {
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_items": total,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        )
    
    def get_visitor_bookings(
        self,
        visitor_id: UUID,
        status: Optional[BookingStatus] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get all bookings for a visitor.
        
        Args:
            visitor_id: Visitor UUID
            status: Optional status filter
            limit: Optional result limit
            
        Returns:
            List of booking dictionaries
        """
        bookings = self.booking_repo.find_by_visitor(visitor_id, status, limit)
        return [self._booking_to_dict(b) for b in bookings]
    
    def get_hostel_bookings(
        self,
        hostel_id: UUID,
        status: Optional[BookingStatus] = None,
        check_in_date_from: Optional[date] = None,
        check_in_date_to: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get all bookings for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            status: Optional status filter
            check_in_date_from: Optional date range start
            check_in_date_to: Optional date range end
            limit: Optional result limit
            
        Returns:
            List of booking dictionaries
        """
        bookings = self.booking_repo.find_by_hostel(
            hostel_id, status, check_in_date_from, check_in_date_to, limit
        )
        return [self._booking_to_dict(b) for b in bookings]
    
    # ==================== BOOKING LIFECYCLE ====================
    
    def approve_booking(
        self,
        booking_id: UUID,
        approved_by_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Approve a pending booking.
        
        Args:
            booking_id: Booking UUID
            approved_by_id: Admin UUID
            audit_context: Audit context
            
        Returns:
            Updated booking dictionary
        """
        try:
            from app.services.booking.booking_approval_service import (
                BookingApprovalService,
            )
            
            approval_service = BookingApprovalService(self.session)
            
            # Approve booking
            approval_service.approve_booking(
                booking_id, approved_by_id, audit_context=audit_context
            )
            
            # Send approval notification
            self.notification_service.send_booking_approved_notification(booking_id)
            
            # Create calendar event
            booking = self.booking_repo.find_by_id(booking_id)
            self.calendar_service.create_check_in_event(booking, audit_context)
            
            self.session.commit()
            
            return self.get_booking_by_id(booking_id)
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def reject_booking(
        self,
        booking_id: UUID,
        rejected_by_id: UUID,
        reason: str,
        suggest_alternatives: bool = False,
        alternative_dates: Optional[List[date]] = None,
        alternative_room_types: Optional[List[RoomType]] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Reject a pending booking.
        
        Args:
            booking_id: Booking UUID
            rejected_by_id: Admin UUID
            reason: Rejection reason
            suggest_alternatives: Whether to suggest alternatives
            alternative_dates: Alternative check-in dates
            alternative_room_types: Alternative room types
            audit_context: Audit context
            
        Returns:
            Updated booking dictionary
        """
        try:
            from app.services.booking.booking_approval_service import (
                BookingApprovalService,
            )
            
            approval_service = BookingApprovalService(self.session)
            
            # Reject booking
            approval_service.reject_booking(
                booking_id=booking_id,
                rejected_by_id=rejected_by_id,
                reason=reason,
                suggest_alternatives=suggest_alternatives,
                alternative_dates=alternative_dates,
                alternative_room_types=alternative_room_types,
                audit_context=audit_context,
            )
            
            # Send rejection notification
            self.notification_service.send_booking_rejected_notification(booking_id)
            
            self.session.commit()
            
            return self.get_booking_by_id(booking_id)
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def cancel_booking(
        self,
        booking_id: UUID,
        cancelled_by_id: UUID,
        reason: str,
        request_refund: bool = True,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Cancel a booking.
        
        Args:
            booking_id: Booking UUID
            cancelled_by_id: User UUID
            reason: Cancellation reason
            request_refund: Whether to request refund
            audit_context: Audit context
            
        Returns:
            Updated booking dictionary with cancellation info
        """
        try:
            from app.services.booking.booking_cancellation_service import (
                BookingCancellationService,
            )
            
            cancellation_service = BookingCancellationService(self.session)
            
            # Cancel booking
            cancellation_service.cancel_booking(
                booking_id=booking_id,
                cancelled_by_id=cancelled_by_id,
                reason=reason,
                request_refund=request_refund,
                audit_context=audit_context,
            )
            
            # Send cancellation notification
            self.notification_service.send_booking_cancelled_notification(booking_id)
            
            self.session.commit()
            
            return self.get_booking_by_id(booking_id)
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def confirm_booking_payment(
        self,
        booking_id: UUID,
        payment_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Confirm booking after advance payment.
        
        Args:
            booking_id: Booking UUID
            payment_id: Payment transaction UUID
            audit_context: Audit context
            
        Returns:
            Updated booking dictionary
        """
        try:
            booking = self.booking_repo.confirm_booking(
                booking_id, payment_id, audit_context
            )
            
            # Send confirmation notification
            self.notification_service.send_booking_confirmed_notification(booking_id)
            
            # Update calendar
            self.calendar_service.update_booking_status(booking, audit_context)
            
            self.session.commit()
            
            return self.get_booking_by_id(booking_id)
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def mark_as_checked_in(
        self,
        booking_id: UUID,
        actual_check_in_date: Optional[date] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark booking as checked in.
        
        Args:
            booking_id: Booking UUID
            actual_check_in_date: Actual check-in date (default: today)
            audit_context: Audit context
            
        Returns:
            Updated booking dictionary
        """
        try:
            booking = self.booking_repo.mark_as_checked_in(booking_id, audit_context)
            
            # Create check-in calendar event
            self.calendar_service.create_check_in_event(
                booking, audit_context, actual_check_in_date
            )
            
            # Send check-in notification
            self.notification_service.send_check_in_notification(booking_id)
            
            self.session.commit()
            
            return self.get_booking_by_id(booking_id)
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def mark_as_completed(
        self,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark booking as completed.
        
        Args:
            booking_id: Booking UUID
            audit_context: Audit context
            
        Returns:
            Updated booking dictionary
        """
        try:
            booking = self.booking_repo.mark_as_completed(booking_id, audit_context)
            
            # Send completion notification
            self.notification_service.send_booking_completed_notification(booking_id)
            
            self.session.commit()
            
            return self.get_booking_by_id(booking_id)
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def mark_as_no_show(
        self,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark booking as no-show.
        
        Args:
            booking_id: Booking UUID
            audit_context: Audit context
            
        Returns:
            Updated booking dictionary
        """
        try:
            booking = self.booking_repo.mark_as_no_show(booking_id, audit_context)
            
            # Send no-show notification
            self.notification_service.send_no_show_notification(booking_id)
            
            self.session.commit()
            
            return self.get_booking_by_id(booking_id)
            
        except Exception as e:
            self.session.rollback()
            raise
    
    # ==================== BOOKING NOTES ====================
    
    def add_booking_note(
        self,
        booking_id: UUID,
        content: str,
        note_type: str = "internal",
        is_pinned: bool = False,
        visibility: str = "all_staff",
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Add note to booking.
        
        Args:
            booking_id: Booking UUID
            content: Note content
            note_type: Note type
            is_pinned: Whether to pin note
            visibility: Who can see the note
            audit_context: Audit context
            
        Returns:
            Created note dictionary
        """
        note_data = {
            "content": content,
            "note_type": note_type,
            "is_pinned": is_pinned,
            "visibility": visibility,
        }
        
        note = self.booking_repo.add_note(booking_id, note_data, audit_context)
        self.session.commit()
        
        return self._note_to_dict(note)
    
    def get_booking_notes(
        self,
        booking_id: UUID,
        include_deleted: bool = False,
    ) -> List[Dict]:
        """
        Get all notes for a booking.
        
        Args:
            booking_id: Booking UUID
            include_deleted: Whether to include deleted notes
            
        Returns:
            List of note dictionaries
        """
        notes = self.booking_repo.get_notes(booking_id, include_deleted)
        return [self._note_to_dict(note) for note in notes]
    
    # ==================== AVAILABILITY & VALIDATION ====================
    
    def check_availability(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        check_in_date: date,
        duration_months: int,
    ) -> Dict:
        """
        Check booking availability with detailed information.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Room type
            check_in_date: Check-in date
            duration_months: Duration in months
            
        Returns:
            Availability details dictionary
        """
        is_available = self.booking_repo.check_availability(
            hostel_id, room_type, check_in_date, duration_months
        )
        
        result = {
            "is_available": is_available,
            "hostel_id": str(hostel_id),
            "room_type": room_type.value,
            "check_in_date": check_in_date.isoformat(),
            "duration_months": duration_months,
        }
        
        if not is_available:
            # Find conflicting bookings
            conflicts = self.booking_repo.find_conflicting_bookings(
                hostel_id, room_type, check_in_date, duration_months
            )
            
            result["conflicts"] = [
                {
                    "booking_id": str(c.id),
                    "booking_reference": c.booking_reference,
                    "check_in_date": c.preferred_check_in_date.isoformat(),
                    "duration_months": c.stay_duration_months,
                }
                for c in conflicts
            ]
            
            # Suggest alternative dates
            result["alternative_suggestions"] = (
                self._suggest_alternative_availability(
                    hostel_id, room_type, check_in_date, duration_months
                )
            )
        
        return result
    
    def _suggest_alternative_availability(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        preferred_date: date,
        duration_months: int,
    ) -> List[Dict]:
        """Suggest alternative available dates."""
        suggestions = []
        
        # Check next 60 days
        for days_offset in [7, 14, 21, 30, 45, 60]:
            alternative_date = preferred_date + timedelta(days=days_offset)
            
            if self.booking_repo.check_availability(
                hostel_id, room_type, alternative_date, duration_months
            ):
                suggestions.append(
                    {
                        "check_in_date": alternative_date.isoformat(),
                        "days_from_preferred": days_offset,
                    }
                )
        
        return suggestions[:3]  # Return top 3 suggestions
    
    # ==================== ANALYTICS & STATISTICS ====================
    
    def get_booking_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """
        Get comprehensive booking statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        stats = self.booking_repo.get_booking_statistics(hostel_id, date_from, date_to)
        
        return {
            "total_bookings": stats.total_bookings,
            "pending_bookings": stats.pending_bookings,
            "approved_bookings": stats.approved_bookings,
            "confirmed_bookings": stats.confirmed_bookings,
            "cancelled_bookings": stats.cancelled_bookings,
            "completed_bookings": stats.completed_bookings,
            "total_revenue": float(stats.total_revenue),
            "average_booking_value": float(stats.average_booking_value),
            "conversion_rate": stats.conversion_rate,
            "cancellation_rate": stats.cancellation_rate,
            "advance_payment_rate": stats.advance_payment_rate,
        }
    
    def get_bookings_by_source(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """Get booking distribution by source."""
        by_source = self.booking_repo.get_bookings_by_source(
            hostel_id, date_from, date_to
        )
        
        return {source.value: count for source, count in by_source.items()}
    
    def get_bookings_by_room_type(
        self,
        hostel_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """Get booking distribution by room type."""
        by_room_type = self.booking_repo.get_bookings_by_room_type(
            hostel_id, date_from, date_to
        )
        
        return {room_type.value: count for room_type, count in by_room_type.items()}
    
    # ==================== EXPIRY MANAGEMENT ====================
    
    def expire_pending_bookings(
        self,
        audit_context: Optional[AuditContext] = None,
    ) -> int:
        """
        Automatically expire pending bookings.
        
        Args:
            audit_context: Audit context
            
        Returns:
            Number of expired bookings
        """
        try:
            count = self.booking_repo.expire_pending_bookings(audit_context)
            
            if count > 0:
                self.session.commit()
            
            return count
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def get_expiring_bookings(
        self,
        within_hours: int = 24,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Get bookings expiring soon.
        
        Args:
            within_hours: Hours threshold
            hostel_id: Optional hostel filter
            
        Returns:
            List of expiring bookings
        """
        bookings = self.booking_repo.find_expiring_bookings(within_hours, hostel_id)
        return [self._booking_to_dict(b) for b in bookings]
    
    # ==================== HELPER METHODS ====================
    
    def _booking_to_dict(self, booking) -> Dict:
        """Convert booking model to dictionary."""
        return {
            "id": str(booking.id),
            "booking_reference": booking.booking_reference,
            "visitor_id": str(booking.visitor_id),
            "hostel_id": str(booking.hostel_id),
            "room_type_requested": booking.room_type_requested.value,
            "preferred_check_in_date": booking.preferred_check_in_date.isoformat(),
            "stay_duration_months": booking.stay_duration_months,
            "quoted_rent_monthly": float(booking.quoted_rent_monthly),
            "total_amount": float(booking.total_amount),
            "security_deposit": float(booking.security_deposit),
            "advance_amount": float(booking.advance_amount),
            "advance_paid": booking.advance_paid,
            "booking_status": booking.booking_status.value,
            "source": booking.source.value,
            "special_requests": booking.special_requests,
            "dietary_preferences": booking.dietary_preferences,
            "has_vehicle": booking.has_vehicle,
            "vehicle_details": booking.vehicle_details,
            "referral_code": booking.referral_code,
            "expires_at": (
                booking.expires_at.isoformat() if booking.expires_at else None
            ),
            "booking_date": booking.booking_date.isoformat(),
            "created_at": booking.created_at.isoformat(),
            "updated_at": booking.updated_at.isoformat(),
            # Computed properties
            "expected_check_out_date": booking.expected_check_out_date.isoformat(),
            "days_until_check_in": booking.days_until_check_in,
            "is_expiring_soon": booking.is_expiring_soon,
            "is_expired": booking.is_expired,
            "balance_amount": float(booking.balance_amount),
            "is_long_term_booking": booking.is_long_term_booking,
            "is_pending_approval": booking.is_pending_approval,
            "is_active": booking.is_active,
        }
    
    def _guest_to_dict(self, guest) -> Dict:
        """Convert guest model to dictionary."""
        return {
            "id": str(guest.id),
            "guest_name": guest.guest_name,
            "guest_email": guest.guest_email,
            "guest_phone": guest.guest_phone,
            "guest_id_proof_type": guest.guest_id_proof_type,
            "guest_id_proof_number": guest.guest_id_proof_number,
            "id_proof_verified": guest.id_proof_verified,
            "emergency_contact_name": guest.emergency_contact_name,
            "emergency_contact_phone": guest.emergency_contact_phone,
            "emergency_contact_relation": guest.emergency_contact_relation,
            "institution_or_company": guest.institution_or_company,
            "designation_or_course": guest.designation_or_course,
            "has_complete_profile": guest.has_complete_profile,
            "has_verified_id": guest.has_verified_id,
        }
    
    def _approval_to_dict(self, approval) -> Dict:
        """Convert approval model to dictionary."""
        return {
            "id": str(approval.id),
            "approved_by": str(approval.approved_by) if approval.approved_by else None,
            "approved_at": approval.approved_at.isoformat(),
            "final_rent_monthly": float(approval.final_rent_monthly),
            "total_amount": float(approval.total_amount),
            "advance_payment_required": approval.advance_payment_required,
            "advance_payment_amount": float(approval.advance_payment_amount),
            "auto_approved": approval.auto_approved,
        }
    
    def _assignment_to_dict(self, assignment) -> Dict:
        """Convert assignment model to dictionary."""
        return {
            "id": str(assignment.id),
            "room_id": str(assignment.room_id),
            "bed_id": str(assignment.bed_id),
            "assigned_by": (
                str(assignment.assigned_by) if assignment.assigned_by else None
            ),
            "assigned_at": assignment.assigned_at.isoformat(),
            "is_active": assignment.is_active,
            "auto_assigned": assignment.auto_assigned,
        }
    
    def _status_history_to_dict(self, history) -> Dict:
        """Convert status history to dictionary."""
        return {
            "id": str(history.id),
            "from_status": history.from_status.value if history.from_status else None,
            "to_status": history.to_status.value,
            "changed_at": history.changed_at.isoformat(),
            "change_reason": history.change_reason,
        }
    
    def _note_to_dict(self, note) -> Dict:
        """Convert note to dictionary."""
        return {
            "id": str(note.id),
            "note_type": note.note_type,
            "content": note.content,
            "is_pinned": note.is_pinned,
            "visibility": note.visibility,
            "created_at": note.created_at.isoformat(),
        }