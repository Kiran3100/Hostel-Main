# app/services/booking/booking_waitlist_service.py
"""
Booking waitlist service for waitlist management.

Handles waitlist entry management, priority tracking, availability notifications,
and conversion to bookings.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from app.models.base.enums import RoomType, WaitlistStatus
from app.repositories.booking.booking_waitlist_repository import (
    BookingWaitlistRepository,
    WaitlistNotificationRepository,
)
from app.repositories.base.base_repository import AuditContext


class BookingWaitlistService:
    """
    Service for booking waitlist management.
    
    Responsibilities:
    - Add/remove waitlist entries
    - Manage priority queue
    - Send availability notifications
    - Convert waitlist to bookings
    - Track waitlist analytics
    """
    
    def __init__(
        self,
        session: Session,
        waitlist_repo: Optional[BookingWaitlistRepository] = None,
        notification_repo: Optional[WaitlistNotificationRepository] = None,
    ):
        """Initialize waitlist service."""
        self.session = session
        self.waitlist_repo = waitlist_repo or BookingWaitlistRepository(session)
        self.notification_repo = (
            notification_repo or WaitlistNotificationRepository(session)
        )
    
    # ==================== WAITLIST OPERATIONS ====================
    
    def add_to_waitlist(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
        room_type: RoomType,
        preferred_check_in_date: date,
        contact_email: str,
        contact_phone: str,
        notes: Optional[str] = None,
        expiry_days: int = 30,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Add visitor to waitlist.
        
        Args:
            visitor_id: Visitor UUID
            hostel_id: Hostel UUID
            room_type: Desired room type
            preferred_check_in_date: Desired check-in date
            contact_email: Email for notifications
            contact_phone: Phone for notifications
            notes: Additional notes
            expiry_days: Days until entry expires
            audit_context: Audit context
            
        Returns:
            Created waitlist entry dictionary
        """
        # Check if visitor already on waitlist for same criteria
        existing = self.waitlist_repo.find_by_visitor(visitor_id, active_only=True)
        
        for entry in existing:
            if (
                entry.hostel_id == hostel_id
                and entry.room_type == room_type
                and entry.status == WaitlistStatus.WAITING
            ):
                raise BusinessRuleViolationError(
                    "Visitor already on waitlist for this hostel and room type"
                )
        
        # Create waitlist entry
        waitlist_data = {
            "visitor_id": visitor_id,
            "hostel_id": hostel_id,
            "room_type": room_type,
            "preferred_check_in_date": preferred_check_in_date,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "notes": notes,
            "expires_at": datetime.utcnow() + timedelta(days=expiry_days),
        }
        
        waitlist_entry = self.waitlist_repo.add_to_waitlist(
            waitlist_data, audit_context
        )
        
        return self._waitlist_to_dict(waitlist_entry)
    
    def cancel_waitlist_entry(
        self,
        waitlist_id: UUID,
        reason: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Cancel a waitlist entry.
        
        Args:
            waitlist_id: Waitlist UUID
            reason: Cancellation reason
            audit_context: Audit context
            
        Returns:
            Updated waitlist entry dictionary
        """
        waitlist_entry = self.waitlist_repo.cancel_waitlist_entry(
            waitlist_id, reason, audit_context
        )
        
        return self._waitlist_to_dict(waitlist_entry)
    
    def update_waitlist_priority(
        self,
        waitlist_id: UUID,
        new_priority: int,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Update waitlist entry priority.
        
        Args:
            waitlist_id: Waitlist UUID
            new_priority: New priority position
            audit_context: Audit context
            
        Returns:
            Updated waitlist entry dictionary
        """
        waitlist_entry = self.waitlist_repo.find_by_id(waitlist_id)
        if not waitlist_entry:
            raise EntityNotFoundError(f"Waitlist entry {waitlist_id} not found")
        
        waitlist_entry.update_priority(new_priority)
        self.session.flush()
        
        return self._waitlist_to_dict(waitlist_entry)
    
    # ==================== AVAILABILITY NOTIFICATION ====================
    
    def notify_availability(
        self,
        waitlist_id: UUID,
        available_room_id: UUID,
        available_bed_id: UUID,
        response_deadline_hours: int = 24,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Notify waitlist entry about room availability.
        
        Args:
            waitlist_id: Waitlist UUID
            available_room_id: Available room UUID
            available_bed_id: Available bed UUID
            response_deadline_hours: Hours to respond
            audit_context: Audit context
            
        Returns:
            Notification dictionary
        """
        waitlist_entry, notification = self.waitlist_repo.notify_availability(
            waitlist_id, available_room_id, available_bed_id, audit_context
        )
        
        # In production, send actual notification via email/SMS
        # notification_service.send_waitlist_availability(notification)
        
        return self._notification_to_dict(notification)
    
    def record_visitor_response(
        self,
        notification_id: UUID,
        response: str,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Record visitor's response to availability notification.
        
        Args:
            notification_id: Notification UUID
            response: "accepted" or "declined"
            audit_context: Audit context
            
        Returns:
            Updated notification dictionary
        """
        if response.lower() not in ["accepted", "declined"]:
            raise ValidationError("Response must be 'accepted' or 'declined'")
        
        notification = self.notification_repo.record_response(
            notification_id, response, audit_context
        )
        
        return self._notification_to_dict(notification)
    
    def convert_waitlist_to_booking(
        self,
        waitlist_id: UUID,
        booking_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Convert waitlist entry to booking.
        
        Args:
            waitlist_id: Waitlist UUID
            booking_id: Created booking UUID
            audit_context: Audit context
            
        Returns:
            Updated waitlist entry dictionary
        """
        waitlist_entry = self.waitlist_repo.convert_to_booking(
            waitlist_id, booking_id, audit_context
        )
        
        return self._waitlist_to_dict(waitlist_entry)
    
    # ==================== WAITLIST QUERIES ====================
    
    def get_waitlist_by_hostel_and_room_type(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        active_only: bool = True,
    ) -> List[Dict]:
        """
        Get waitlist entries for hostel and room type.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Room type
            active_only: Only active entries
            
        Returns:
            List of waitlist entry dictionaries
        """
        entries = self.waitlist_repo.find_by_hostel_and_room_type(
            hostel_id, room_type, active_only=active_only
        )
        
        return [self._waitlist_to_dict(e) for e in entries]
    
    def get_next_in_line(
        self,
        hostel_id: UUID,
        room_type: RoomType,
    ) -> Optional[Dict]:
        """
        Get next visitor in line for waitlist.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Room type
            
        Returns:
            Top priority waitlist entry or None
        """
        entry = self.waitlist_repo.get_next_in_line(hostel_id, room_type)
        
        if not entry:
            return None
        
        return self._waitlist_to_dict(entry)
    
    def get_visitor_waitlist_entries(
        self,
        visitor_id: UUID,
        active_only: bool = True,
    ) -> List[Dict]:
        """
        Get all waitlist entries for a visitor.
        
        Args:
            visitor_id: Visitor UUID
            active_only: Only active entries
            
        Returns:
            List of waitlist entry dictionaries
        """
        entries = self.waitlist_repo.find_by_visitor(visitor_id, active_only)
        
        return [self._waitlist_to_dict(e) for e in entries]
    
    def get_expiring_waitlist_entries(
        self,
        within_hours: int = 24,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Get waitlist entries expiring soon.
        
        Args:
            within_hours: Hours threshold
            hostel_id: Optional hostel filter
            
        Returns:
            List of expiring waitlist entries
        """
        entries = self.waitlist_repo.find_expiring_soon(within_hours, hostel_id)
        
        return [self._waitlist_to_dict(e) for e in entries]
    
    def get_pending_responses(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Get notifications awaiting visitor response.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of notification dictionaries
        """
        notifications = self.notification_repo.find_pending_responses(hostel_id)
        
        return [self._notification_to_dict(n) for n in notifications]
    
    # ==================== MAINTENANCE OPERATIONS ====================
    
    def expire_old_waitlist_entries(
        self,
        audit_context: Optional[AuditContext] = None,
    ) -> int:
        """
        Expire waitlist entries past their expiry date.
        
        Args:
            audit_context: Audit context
            
        Returns:
            Number of expired entries
        """
        count = self.waitlist_repo.expire_old_entries(audit_context)
        
        if count > 0:
            self.session.commit()
        
        return count
    
    # ==================== ANALYTICS ====================
    
    def get_waitlist_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict:
        """
        Get waitlist statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics dictionary
        """
        return self.waitlist_repo.get_waitlist_statistics(
            hostel_id, date_from, date_to
        )
    
    # ==================== HELPER METHODS ====================
    
    def _waitlist_to_dict(self, waitlist) -> Dict:
        """Convert waitlist model to dictionary."""
        return {
            "id": str(waitlist.id),
            "hostel_id": str(waitlist.hostel_id),
            "visitor_id": str(waitlist.visitor_id),
            "room_type": waitlist.room_type.value,
            "preferred_check_in_date": waitlist.preferred_check_in_date.isoformat(),
            "contact_email": waitlist.contact_email,
            "contact_phone": waitlist.contact_phone,
            "notes": waitlist.notes,
            "priority": waitlist.priority,
            "status": waitlist.status.value,
            "estimated_availability_date": (
                waitlist.estimated_availability_date.isoformat()
                if waitlist.estimated_availability_date
                else None
            ),
            "notified_count": waitlist.notified_count,
            "last_notified_at": (
                waitlist.last_notified_at.isoformat()
                if waitlist.last_notified_at
                else None
            ),
            "converted_to_booking": waitlist.converted_to_booking,
            "converted_booking_id": (
                str(waitlist.converted_booking_id)
                if waitlist.converted_booking_id
                else None
            ),
            "conversion_date": (
                waitlist.conversion_date.isoformat()
                if waitlist.conversion_date
                else None
            ),
            "expires_at": (
                waitlist.expires_at.isoformat() if waitlist.expires_at else None
            ),
            "cancelled_at": (
                waitlist.cancelled_at.isoformat() if waitlist.cancelled_at else None
            ),
            "cancellation_reason": waitlist.cancellation_reason,
            "created_at": waitlist.created_at.isoformat(),
            # Computed properties
            "days_on_waitlist": waitlist.days_on_waitlist,
            "is_top_priority": waitlist.is_top_priority,
            "is_expired": waitlist.is_expired,
            "days_until_check_in": waitlist.days_until_check_in,
            "is_active": waitlist.is_active,
        }
    
    def _notification_to_dict(self, notification) -> Dict:
        """Convert notification model to dictionary."""
        return {
            "id": str(notification.id),
            "waitlist_id": str(notification.waitlist_id),
            "available_room_id": (
                str(notification.available_room_id)
                if notification.available_room_id
                else None
            ),
            "available_bed_id": (
                str(notification.available_bed_id)
                if notification.available_bed_id
                else None
            ),
            "notification_message": notification.notification_message,
            "sent_at": notification.sent_at.isoformat(),
            "response_deadline": notification.response_deadline.isoformat(),
            "visitor_response": notification.visitor_response,
            "response_received_at": (
                notification.response_received_at.isoformat()
                if notification.response_received_at
                else None
            ),
            "booking_link": notification.booking_link,
            "booking_created": notification.booking_created,
            "notification_channels": notification.notification_channels,
            "delivery_status": notification.delivery_status,
            # Computed properties
            "hours_until_deadline": notification.hours_until_deadline,
            "is_expiring_soon": notification.is_expiring_soon,
            "is_expired": notification.is_expired,
            "has_response": notification.has_response,
        }