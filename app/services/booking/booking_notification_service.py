# app/services/booking/booking_notification_service.py
"""
Booking notification service for all booking-related notifications.

Handles email, SMS, and push notifications for various booking events
and status changes.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.repositories.booking.booking_repository import BookingRepository
from app.repositories.booking.booking_guest_repository import BookingGuestRepository


class BookingNotificationService:
    """
    Service for booking notification management.
    
    Responsibilities:
    - Send booking confirmation emails
    - Send status change notifications
    - Send payment reminders
    - Send check-in/check-out reminders
    - Track notification delivery
    
    Note: This is a placeholder implementation. In production, integrate with:
    - Email service (SendGrid, AWS SES, etc.)
    - SMS service (Twilio, AWS SNS, etc.)
    - Push notification service (Firebase, OneSignal, etc.)
    """
    
    def __init__(
        self,
        session: Session,
        booking_repo: Optional[BookingRepository] = None,
        guest_repo: Optional[BookingGuestRepository] = None,
    ):
        """Initialize notification service."""
        self.session = session
        self.booking_repo = booking_repo or BookingRepository(session)
        self.guest_repo = guest_repo or BookingGuestRepository(session)
    
    # ==================== BOOKING LIFECYCLE NOTIFICATIONS ====================
    
    def send_booking_received_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """
        Send notification when booking request is received.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Notification delivery status
        """
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return {"sent": False, "reason": "Guest information not found"}
        
        # Prepare notification data
        notification_data = {
            "to": guest.guest_email,
            "guest_name": guest.guest_name,
            "booking_reference": booking.booking_reference,
            "hostel_name": booking.hostel.name if booking.hostel else "Hostel",
            "check_in_date": booking.preferred_check_in_date.isoformat(),
            "room_type": booking.room_type_requested.value,
        }
        
        # In production, send actual email/SMS
        # email_service.send_template("booking_received", notification_data)
        
        return {
            "sent": True,
            "channels": ["email"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "booking_received",
        }
    
    def send_booking_approved_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification when booking is approved."""
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return {"sent": False, "reason": "Guest information not found"}
        
        # Get approval details
        from app.repositories.booking.booking_approval_repository import (
            BookingApprovalRepository,
        )
        
        approval_repo = BookingApprovalRepository(self.session)
        approval = approval_repo.find_by_booking(booking_id)
        
        notification_data = {
            "to": guest.guest_email,
            "guest_name": guest.guest_name,
            "booking_reference": booking.booking_reference,
            "hostel_name": booking.hostel.name if booking.hostel else "Hostel",
            "total_amount": float(booking.total_amount),
            "advance_amount": (
                float(approval.advance_payment_amount) if approval else 0
            ),
            "payment_deadline": (
                approval.advance_payment_deadline.isoformat()
                if approval and approval.advance_payment_deadline
                else None
            ),
        }
        
        # Send notification
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "booking_approved",
        }
    
    def send_booking_rejected_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification when booking is rejected."""
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return {"sent": False, "reason": "Guest information not found"}
        
        return {
            "sent": True,
            "channels": ["email"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "booking_rejected",
        }
    
    def send_booking_confirmed_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification when booking is confirmed (payment received)."""
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return {"sent": False, "reason": "Guest information not found"}
        
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "booking_confirmed",
        }
    
    def send_booking_cancelled_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification when booking is cancelled."""
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return {"sent": False, "reason": "Guest information not found"}
        
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "booking_cancelled",
        }
    
    # ==================== CHECK-IN/CHECK-OUT NOTIFICATIONS ====================
    
    def send_check_in_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification when guest checks in."""
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return {"sent": False, "reason": "Guest information not found"}
        
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "check_in_confirmed",
        }
    
    def send_check_in_reminder(
        self,
        booking_id: UUID,
        days_before: int = 1,
    ) -> Dict:
        """Send check-in reminder notification."""
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return {"sent": False, "reason": "Guest information not found"}
        
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "check_in_reminder",
            "days_before": days_before,
        }
    
    def send_booking_completed_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification when booking is completed."""
        return {
            "sent": True,
            "channels": ["email"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "booking_completed",
        }
    
    def send_no_show_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification for no-show."""
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "no_show",
        }
    
    # ==================== PAYMENT NOTIFICATIONS ====================
    
    def send_payment_reminder(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send payment reminder notification."""
        booking = self.booking_repo.find_by_id(booking_id)
        if not booking:
            raise EntityNotFoundError(f"Booking {booking_id} not found")
        
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return {"sent": False, "reason": "Guest information not found"}
        
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "payment_reminder",
        }
    
    def send_payment_overdue_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send payment overdue notification."""
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "payment_overdue",
        }
    
    def send_refund_initiated_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification when refund is initiated."""
        return {
            "sent": True,
            "channels": ["email"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "refund_initiated",
        }
    
    def send_refund_completed_notification(
        self,
        booking_id: UUID,
    ) -> Dict:
        """Send notification when refund is completed."""
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "refund_completed",
        }
    
    # ==================== MODIFICATION NOTIFICATIONS ====================
    
    def send_modification_requested_notification(
        self,
        modification_id: UUID,
    ) -> Dict:
        """Send notification when modification is requested."""
        return {
            "sent": True,
            "channels": ["email"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "modification_requested",
        }
    
    def send_modification_approved_notification(
        self,
        modification_id: UUID,
    ) -> Dict:
        """Send notification when modification is approved."""
        return {
            "sent": True,
            "channels": ["email", "sms"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "modification_approved",
        }
    
    def send_modification_rejected_notification(
        self,
        modification_id: UUID,
    ) -> Dict:
        """Send notification when modification is rejected."""
        return {
            "sent": True,
            "channels": ["email"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "modification_rejected",
        }
    
    # ==================== WAITLIST NOTIFICATIONS ====================
    
    def send_waitlist_confirmation_notification(
        self,
        waitlist_id: UUID,
    ) -> Dict:
        """Send notification when added to waitlist."""
        return {
            "sent": True,
            "channels": ["email"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "waitlist_confirmation",
        }
    
    def send_waitlist_availability_notification(
        self,
        waitlist_id: UUID,
    ) -> Dict:
        """Send notification when room becomes available."""
        return {
            "sent": True,
            "channels": ["email", "sms", "push"],
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "waitlist_availability",
            "priority": "high",
        }
    
    # ==================== ADMIN NOTIFICATIONS ====================
    
    def send_admin_new_booking_notification(
        self,
        booking_id: UUID,
        admin_emails: List[str],
    ) -> Dict:
        """Send notification to admins about new booking."""
        return {
            "sent": True,
            "channels": ["email"],
            "recipients": admin_emails,
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "admin_new_booking",
        }
    
    def send_admin_cancellation_notification(
        self,
        booking_id: UUID,
        admin_emails: List[str],
    ) -> Dict:
        """Send notification to admins about cancellation."""
        return {
            "sent": True,
            "channels": ["email"],
            "recipients": admin_emails,
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "admin_cancellation",
        }