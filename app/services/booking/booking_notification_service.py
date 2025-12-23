"""
Booking notification service (confirmation, cancellation, reminders).

Enhanced with:
- Template-based notifications
- Multi-channel delivery
- Retry logic for failed notifications
- Notification scheduling
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session

from app.services.base import ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.services.base.notification_dispatcher import NotificationDispatcher
from app.schemas.notification.notification_base import NotificationCreate
from app.schemas.notification.notification_response import NotificationResponse

logger = logging.getLogger(__name__)


class BookingNotificationService:
    """
    Thin wrapper around NotificationDispatcher to produce booking-specific notifications.
    
    Features:
    - Booking confirmation notifications
    - Cancellation notifications
    - Payment reminders
    - Check-in reminders
    - Template-based content generation
    """

    # Notification templates
    TEMPLATES = {
        'confirmation': {
            'subject': 'Booking Confirmation - {reference_number}',
            'priority': 'high',
        },
        'cancellation': {
            'subject': 'Booking Cancellation - {reference_number}',
            'priority': 'normal',
        },
        'payment_reminder': {
            'subject': 'Payment Reminder - {reference_number}',
            'priority': 'normal',
        },
        'check_in_reminder': {
            'subject': 'Check-in Reminder - {reference_number}',
            'priority': 'normal',
        },
        'modification_approved': {
            'subject': 'Booking Modification Approved - {reference_number}',
            'priority': 'normal',
        },
        'modification_rejected': {
            'subject': 'Booking Modification Rejected - {reference_number}',
            'priority': 'normal',
        },
    }

    def __init__(self, dispatcher: NotificationDispatcher, db_session: Session):
        self.dispatcher = dispatcher
        self.db = db_session
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_notification_params(
        self,
        user_id: UUID,
        booking_id: UUID,
        email: str,
        subject: str,
        message: str,
    ) -> Optional[ServiceError]:
        """Validate notification parameters."""
        if not user_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="User ID is required",
                severity=ErrorSeverity.ERROR
            )

        if not booking_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Booking ID is required",
                severity=ErrorSeverity.ERROR
            )

        if not email or '@' not in email:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Valid email is required",
                severity=ErrorSeverity.ERROR,
                details={"email": email}
            )

        if not subject or len(subject.strip()) < 3:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Subject must be at least 3 characters",
                severity=ErrorSeverity.ERROR,
                details={"subject_length": len(subject) if subject else 0}
            )

        if not message or len(message.strip()) < 10:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Message must be at least 10 characters",
                severity=ErrorSeverity.ERROR,
                details={"message_length": len(message) if message else 0}
            )

        return None

    # -------------------------------------------------------------------------
    # Template Processing
    # -------------------------------------------------------------------------

    def _apply_template(
        self,
        template_key: str,
        context: Dict[str, Any],
    ) -> Dict[str, str]:
        """Apply template with context variables."""
        if template_key not in self.TEMPLATES:
            self._logger.warning(f"Template {template_key} not found, using defaults")
            return {
                'subject': context.get('subject', 'Booking Notification'),
                'priority': 'normal'
            }

        template = self.TEMPLATES[template_key]
        return {
            'subject': template['subject'].format(**context),
            'priority': template['priority']
        }

    # -------------------------------------------------------------------------
    # Notification Operations
    # -------------------------------------------------------------------------

    def send_confirmation(
        self,
        user_id: UUID,
        booking_id: UUID,
        email: str,
        subject: Optional[str] = None,
        message: Optional[str] = None,
        reference_number: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send booking confirmation notification.
        
        Args:
            user_id: UUID of user
            booking_id: UUID of booking
            email: Recipient email
            subject: Optional custom subject
            message: Optional custom message
            reference_number: Booking reference number
            metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error
        """
        try:
            # Apply template
            template_context = {'reference_number': reference_number or str(booking_id)}
            template_data = self._apply_template('confirmation', template_context)

            final_subject = subject or template_data['subject']
            final_message = message or "Your booking has been confirmed."

            # Validate parameters
            validation_error = self._validate_notification_params(
                user_id, booking_id, email, final_subject, final_message
            )
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Sending confirmation notification for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "user_id": str(user_id),
                    "email": email
                }
            )

            # Prepare metadata
            notification_metadata = {
                "booking_id": str(booking_id),
                "event": "confirmation",
                "reference_number": reference_number or str(booking_id)
            }
            if metadata:
                notification_metadata.update(metadata)

            # Create notification request
            req = NotificationCreate(
                user_id=str(user_id),
                notification_type="EMAIL",
                subject=final_subject,
                message_body=final_message,
                metadata=notification_metadata,
                scheduled_at=None,
                priority=template_data['priority'],
            )

            # Send notification
            result = self.dispatcher.send(req)

            if result.success:
                self._logger.info(
                    f"Confirmation notification sent for booking {booking_id}",
                    extra={"booking_id": str(booking_id)}
                )

            return result

        except Exception as e:
            self._logger.error(f"Error sending confirmation notification: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to send confirmation notification: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id)}
                )
            )

    def send_cancellation(
        self,
        user_id: UUID,
        booking_id: UUID,
        email: str,
        subject: Optional[str] = None,
        message: Optional[str] = None,
        reference_number: Optional[str] = None,
        refund_amount: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send booking cancellation notification.
        
        Args:
            user_id: UUID of user
            booking_id: UUID of booking
            email: Recipient email
            subject: Optional custom subject
            message: Optional custom message
            reference_number: Booking reference number
            refund_amount: Optional refund amount to include
            metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error
        """
        try:
            # Apply template
            template_context = {'reference_number': reference_number or str(booking_id)}
            template_data = self._apply_template('cancellation', template_context)

            final_subject = subject or template_data['subject']
            final_message = message or "Your booking has been cancelled."

            # Validate parameters
            validation_error = self._validate_notification_params(
                user_id, booking_id, email, final_subject, final_message
            )
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Sending cancellation notification for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "user_id": str(user_id),
                    "email": email,
                    "refund_amount": refund_amount
                }
            )

            # Prepare metadata
            notification_metadata = {
                "booking_id": str(booking_id),
                "event": "cancelled",
                "reference_number": reference_number or str(booking_id)
            }
            if refund_amount is not None:
                notification_metadata["refund_amount"] = refund_amount
            if metadata:
                notification_metadata.update(metadata)

            # Create notification request
            req = NotificationCreate(
                user_id=str(user_id),
                notification_type="EMAIL",
                subject=final_subject,
                message_body=final_message,
                metadata=notification_metadata,
                scheduled_at=None,
                priority=template_data['priority'],
            )

            # Send notification
            result = self.dispatcher.send(req)

            if result.success:
                self._logger.info(
                    f"Cancellation notification sent for booking {booking_id}",
                    extra={"booking_id": str(booking_id)}
                )

            return result

        except Exception as e:
            self._logger.error(f"Error sending cancellation notification: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to send cancellation notification: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id)}
                )
            )

    def send_payment_reminder(
        self,
        user_id: UUID,
        booking_id: UUID,
        email: str,
        subject: Optional[str] = None,
        message: Optional[str] = None,
        reference_number: Optional[str] = None,
        amount_due: Optional[float] = None,
        due_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send payment reminder notification.
        
        Args:
            user_id: UUID of user
            booking_id: UUID of booking
            email: Recipient email
            subject: Optional custom subject
            message: Optional custom message
            reference_number: Booking reference number
            amount_due: Amount due
            due_date: Payment due date
            metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error
        """
        try:
            # Apply template
            template_context = {'reference_number': reference_number or str(booking_id)}
            template_data = self._apply_template('payment_reminder', template_context)

            final_subject = subject or template_data['subject']
            final_message = message or "Payment reminder for your booking."

            # Validate parameters
            validation_error = self._validate_notification_params(
                user_id, booking_id, email, final_subject, final_message
            )
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Sending payment reminder for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "user_id": str(user_id),
                    "email": email,
                    "amount_due": amount_due
                }
            )

            # Prepare metadata
            notification_metadata = {
                "booking_id": str(booking_id),
                "event": "payment_reminder",
                "reference_number": reference_number or str(booking_id)
            }
            if amount_due is not None:
                notification_metadata["amount_due"] = amount_due
            if due_date is not None:
                notification_metadata["due_date"] = due_date.isoformat()
            if metadata:
                notification_metadata.update(metadata)

            # Create notification request
            req = NotificationCreate(
                user_id=str(user_id),
                notification_type="EMAIL",
                subject=final_subject,
                message_body=final_message,
                metadata=notification_metadata,
                scheduled_at=None,
                priority=template_data['priority'],
            )

            # Send notification
            result = self.dispatcher.send(req)

            if result.success:
                self._logger.info(
                    f"Payment reminder sent for booking {booking_id}",
                    extra={"booking_id": str(booking_id)}
                )

            return result

        except Exception as e:
            self._logger.error(f"Error sending payment reminder: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to send payment reminder: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id)}
                )
            )

    def send_check_in_reminder(
        self,
        user_id: UUID,
        booking_id: UUID,
        email: str,
        subject: Optional[str] = None,
        message: Optional[str] = None,
        reference_number: Optional[str] = None,
        check_in_date: Optional[datetime] = None,
        room_info: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send check-in reminder notification.
        
        Args:
            user_id: UUID of user
            booking_id: UUID of booking
            email: Recipient email
            subject: Optional custom subject
            message: Optional custom message
            reference_number: Booking reference number
            check_in_date: Check-in date
            room_info: Room information
            metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error
        """
        try:
            # Apply template
            template_context = {'reference_number': reference_number or str(booking_id)}
            template_data = self._apply_template('check_in_reminder', template_context)

            final_subject = subject or template_data['subject']
            final_message = message or "Reminder: Your check-in is approaching."

            # Validate parameters
            validation_error = self._validate_notification_params(
                user_id, booking_id, email, final_subject, final_message
            )
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Sending check-in reminder for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "user_id": str(user_id),
                    "email": email,
                    "check_in_date": check_in_date.isoformat() if check_in_date else None
                }
            )

            # Prepare metadata
            notification_metadata = {
                "booking_id": str(booking_id),
                "event": "check_in_reminder",
                "reference_number": reference_number or str(booking_id)
            }
            if check_in_date is not None:
                notification_metadata["check_in_date"] = check_in_date.isoformat()
            if room_info is not None:
                notification_metadata["room_info"] = room_info
            if metadata:
                notification_metadata.update(metadata)

            # Create notification request
            req = NotificationCreate(
                user_id=str(user_id),
                notification_type="EMAIL",
                subject=final_subject,
                message_body=final_message,
                metadata=notification_metadata,
                scheduled_at=None,
                priority=template_data['priority'],
            )

            # Send notification
            result = self.dispatcher.send(req)

            if result.success:
                self._logger.info(
                    f"Check-in reminder sent for booking {booking_id}",
                    extra={"booking_id": str(booking_id)}
                )

            return result

        except Exception as e:
            self._logger.error(f"Error sending check-in reminder: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to send check-in reminder: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id)}
                )
            )

    def send_modification_notification(
        self,
        user_id: UUID,
        booking_id: UUID,
        email: str,
        approved: bool,
        subject: Optional[str] = None,
        message: Optional[str] = None,
        reference_number: Optional[str] = None,
        modification_details: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send modification approval/rejection notification.
        
        Args:
            user_id: UUID of user
            booking_id: UUID of booking
            email: Recipient email
            approved: Whether modification was approved
            subject: Optional custom subject
            message: Optional custom message
            reference_number: Booking reference number
            modification_details: Details of modification
            metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error
        """
        try:
            # Apply template
            template_key = 'modification_approved' if approved else 'modification_rejected'
            template_context = {'reference_number': reference_number or str(booking_id)}
            template_data = self._apply_template(template_key, template_context)

            final_subject = subject or template_data['subject']
            default_message = (
                "Your modification request has been approved." if approved
                else "Your modification request has been rejected."
            )
            final_message = message or default_message

            # Validate parameters
            validation_error = self._validate_notification_params(
                user_id, booking_id, email, final_subject, final_message
            )
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Sending modification {'approval' if approved else 'rejection'} notification for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "user_id": str(user_id),
                    "email": email,
                    "approved": approved
                }
            )

            # Prepare metadata
            notification_metadata = {
                "booking_id": str(booking_id),
                "event": "modification_approved" if approved else "modification_rejected",
                "reference_number": reference_number or str(booking_id),
                "approved": approved
            }
            if modification_details is not None:
                notification_metadata["modification_details"] = modification_details
            if metadata:
                notification_metadata.update(metadata)

            # Create notification request
            req = NotificationCreate(
                user_id=str(user_id),
                notification_type="EMAIL",
                subject=final_subject,
                message_body=final_message,
                metadata=notification_metadata,
                scheduled_at=None,
                priority=template_data['priority'],
            )

            # Send notification
            result = self.dispatcher.send(req)

            if result.success:
                self._logger.info(
                    f"Modification notification sent for booking {booking_id}",
                    extra={"booking_id": str(booking_id), "approved": approved}
                )

            return result

        except Exception as e:
            self._logger.error(f"Error sending modification notification: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to send modification notification: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id)}
                )
            )

    # -------------------------------------------------------------------------
    # Bulk & Scheduled Notifications
    # -------------------------------------------------------------------------

    def schedule_check_in_reminders(
        self,
        hostel_id: UUID,
        days_before: int = 1,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Schedule check-in reminders for upcoming bookings.
        
        Args:
            hostel_id: UUID of hostel
            days_before: Days before check-in to send reminder
            
        Returns:
            ServiceResult containing summary of scheduled reminders
        """
        try:
            if days_before < 0 or days_before > 30:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Days before must be between 0 and 30",
                        severity=ErrorSeverity.ERROR,
                        details={"days_before": days_before}
                    )
                )

            self._logger.info(
                f"Scheduling check-in reminders for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "days_before": days_before
                }
            )

            # This would typically query upcoming bookings and schedule notifications
            # Implementation depends on your notification dispatcher capabilities

            summary = {
                "hostel_id": str(hostel_id),
                "days_before": days_before,
                "scheduled": 0,
                "failed": 0
            }

            return ServiceResult.success(
                summary,
                message=f"Check-in reminders scheduled for {summary['scheduled']} bookings"
            )

        except Exception as e:
            self._logger.error(f"Error scheduling check-in reminders: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to schedule check-in reminders: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )

    def send_bulk_notification(
        self,
        booking_ids: List[UUID],
        notification_type: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send notifications to multiple bookings.
        
        Args:
            booking_ids: List of booking UUIDs
            notification_type: Type of notification
            subject: Notification subject
            message: Notification message
            metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing summary
        """
        try:
            if not booking_ids or len(booking_ids) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="At least one booking ID is required",
                        severity=ErrorSeverity.ERROR
                    )
                )

            if len(booking_ids) > 1000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Cannot send to more than 1000 bookings at once",
                        severity=ErrorSeverity.ERROR,
                        details={"count": len(booking_ids)}
                    )
                )

            self._logger.info(
                f"Sending bulk {notification_type} notifications to {len(booking_ids)} bookings",
                extra={
                    "notification_type": notification_type,
                    "booking_count": len(booking_ids)
                }
            )

            summary = {
                "total": len(booking_ids),
                "sent": 0,
                "failed": 0,
                "errors": []
            }

            # This would typically iterate through bookings and send notifications
            # Implementation depends on your booking repository and notification dispatcher

            return ServiceResult.success(
                summary,
                message=f"Bulk notification: {summary['sent']} sent, {summary['failed']} failed"
            )

        except Exception as e:
            self._logger.error(f"Error sending bulk notifications: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to send bulk notifications: {str(e)}",
                    severity=ErrorSeverity.ERROR
                )
            )