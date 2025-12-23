"""
Leave Notification Service Module

Manages notifications for leave-related events including:
- Application submission acknowledgments
- Approval/rejection notifications
- Return date reminders
- Escalation alerts
- Status change notifications

Version: 2.0.0
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import date, timedelta, datetime
import logging

from sqlalchemy.orm import Session

from app.services.base import ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.services.base.notification_dispatcher import NotificationDispatcher
from app.schemas.notification.notification_base import NotificationCreate
from app.schemas.notification.notification_response import NotificationResponse

logger = logging.getLogger(__name__)


class LeaveNotificationService:
    """
    Comprehensive notification service for leave-related events.
    
    Provides:
    - Templated notifications
    - Multi-channel delivery (email, SMS, push)
    - Scheduled notifications
    - Batch notifications
    - Notification tracking
    """

    # Notification priority levels
    PRIORITY_LOW = "low"
    PRIORITY_NORMAL = "normal"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"

    # Notification types
    TYPE_EMAIL = "EMAIL"
    TYPE_SMS = "SMS"
    TYPE_PUSH = "PUSH"
    TYPE_IN_APP = "IN_APP"

    def __init__(self, dispatcher: NotificationDispatcher, db_session: Session):
        """
        Initialize the leave notification service.
        
        Args:
            dispatcher: Notification dispatcher instance
            db_session: Active database session
        """
        self.dispatcher = dispatcher
        self.db = db_session
        self._logger = logger

    def send_submission_ack(
        self,
        student_user_id: UUID,
        leave_id: UUID,
        subject: str,
        message: str,
        notification_type: str = TYPE_EMAIL,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send acknowledgment notification for leave application submission.
        
        Args:
            student_user_id: UUID of the student user
            leave_id: UUID of the leave application
            subject: Notification subject
            message: Notification message body
            notification_type: Type of notification (EMAIL, SMS, etc.)
            additional_metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error information
        """
        try:
            self._logger.info(
                f"Sending submission acknowledgment for leave {leave_id} "
                f"to student {student_user_id}"
            )
            
            # Prepare metadata
            metadata = {
                "leave_id": str(leave_id),
                "event": "submission_ack",
                "timestamp": datetime.utcnow().isoformat(),
            }
            if additional_metadata:
                metadata.update(additional_metadata)
            
            # Create notification request
            notification_request = NotificationCreate(
                user_id=str(student_user_id),
                notification_type=notification_type,
                subject=subject,
                message_body=message,
                metadata=metadata,
                scheduled_at=None,
                priority=self.PRIORITY_NORMAL,
            )
            
            # Send via dispatcher
            result = self.dispatcher.send(notification_request)
            
            if result.success:
                self._logger.info(
                    f"Submission acknowledgment sent successfully for leave {leave_id}"
                )
            else:
                self._logger.warning(
                    f"Failed to send submission acknowledgment for leave {leave_id}: "
                    f"{result.error.message if result.error else 'Unknown error'}"
                )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error sending submission acknowledgment: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.OPERATION_FAILED,
                    message=f"Failed to send submission acknowledgment: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def send_decision_notice(
        self,
        student_user_id: UUID,
        leave_id: UUID,
        approved: bool,
        subject: str,
        message: str,
        notification_type: str = TYPE_EMAIL,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send notification for leave approval or rejection decision.
        
        Args:
            student_user_id: UUID of the student user
            leave_id: UUID of the leave application
            approved: True if approved, False if rejected
            subject: Notification subject
            message: Notification message body
            notification_type: Type of notification (EMAIL, SMS, etc.)
            additional_metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error information
        """
        try:
            decision_type = "approved" if approved else "rejected"
            
            self._logger.info(
                f"Sending {decision_type} notification for leave {leave_id} "
                f"to student {student_user_id}"
            )
            
            # Prepare metadata
            metadata = {
                "leave_id": str(leave_id),
                "event": decision_type,
                "approved": approved,
                "timestamp": datetime.utcnow().isoformat(),
            }
            if additional_metadata:
                metadata.update(additional_metadata)
            
            # Use high priority for approved leaves
            priority = self.PRIORITY_HIGH if approved else self.PRIORITY_NORMAL
            
            # Create notification request
            notification_request = NotificationCreate(
                user_id=str(student_user_id),
                notification_type=notification_type,
                subject=subject,
                message_body=message,
                metadata=metadata,
                scheduled_at=None,
                priority=priority,
            )
            
            # Send via dispatcher
            result = self.dispatcher.send(notification_request)
            
            if result.success:
                self._logger.info(
                    f"Decision notification ({decision_type}) sent successfully "
                    f"for leave {leave_id}"
                )
            else:
                self._logger.warning(
                    f"Failed to send decision notification for leave {leave_id}: "
                    f"{result.error.message if result.error else 'Unknown error'}"
                )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error sending decision notification: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.OPERATION_FAILED,
                    message=f"Failed to send decision notification: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def send_return_reminder(
        self,
        student_user_id: UUID,
        leave_id: UUID,
        return_date: date,
        subject: str,
        message: str,
        days_before: int = 1,
        notification_type: str = TYPE_EMAIL,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send reminder notification about upcoming return date.
        
        Args:
            student_user_id: UUID of the student user
            leave_id: UUID of the leave application
            return_date: Expected return date
            subject: Notification subject
            message: Notification message body
            days_before: Days before return date to send reminder
            notification_type: Type of notification (EMAIL, SMS, etc.)
            additional_metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error information
        """
        try:
            self._logger.info(
                f"Sending return reminder for leave {leave_id} "
                f"to student {student_user_id} (return date: {return_date})"
            )
            
            # Calculate scheduled send time
            reminder_date = return_date - timedelta(days=days_before)
            scheduled_at = datetime.combine(
                reminder_date,
                datetime.min.time()
            ).replace(hour=9, minute=0)  # Send at 9 AM
            
            # Only schedule if reminder date is in the future
            if reminder_date <= date.today():
                scheduled_at = None  # Send immediately
            
            # Prepare metadata
            metadata = {
                "leave_id": str(leave_id),
                "event": "return_reminder",
                "return_date": return_date.isoformat(),
                "days_before": days_before,
                "timestamp": datetime.utcnow().isoformat(),
            }
            if additional_metadata:
                metadata.update(additional_metadata)
            
            # Create notification request
            notification_request = NotificationCreate(
                user_id=str(student_user_id),
                notification_type=notification_type,
                subject=subject,
                message_body=message,
                metadata=metadata,
                scheduled_at=scheduled_at,
                priority=self.PRIORITY_NORMAL,
            )
            
            # Send via dispatcher
            result = self.dispatcher.send(notification_request)
            
            if result.success:
                send_type = "scheduled" if scheduled_at else "sent"
                self._logger.info(
                    f"Return reminder {send_type} successfully for leave {leave_id}"
                )
            else:
                self._logger.warning(
                    f"Failed to send return reminder for leave {leave_id}: "
                    f"{result.error.message if result.error else 'Unknown error'}"
                )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error sending return reminder: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.OPERATION_FAILED,
                    message=f"Failed to send return reminder: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def send_escalation_alert(
        self,
        approver_user_id: UUID,
        leave_id: UUID,
        subject: str,
        message: str,
        notification_type: str = TYPE_EMAIL,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send escalation alert to higher authority or designated approver.
        
        Args:
            approver_user_id: UUID of the approver to notify
            leave_id: UUID of the leave application
            subject: Notification subject
            message: Notification message body
            notification_type: Type of notification (EMAIL, SMS, etc.)
            additional_metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error information
        """
        try:
            self._logger.info(
                f"Sending escalation alert for leave {leave_id} "
                f"to approver {approver_user_id}"
            )
            
            # Prepare metadata
            metadata = {
                "leave_id": str(leave_id),
                "event": "escalation_alert",
                "timestamp": datetime.utcnow().isoformat(),
            }
            if additional_metadata:
                metadata.update(additional_metadata)
            
            # Create notification request with urgent priority
            notification_request = NotificationCreate(
                user_id=str(approver_user_id),
                notification_type=notification_type,
                subject=subject,
                message_body=message,
                metadata=metadata,
                scheduled_at=None,
                priority=self.PRIORITY_URGENT,
            )
            
            # Send via dispatcher
            result = self.dispatcher.send(notification_request)
            
            if result.success:
                self._logger.info(
                    f"Escalation alert sent successfully for leave {leave_id}"
                )
            else:
                self._logger.warning(
                    f"Failed to send escalation alert for leave {leave_id}: "
                    f"{result.error.message if result.error else 'Unknown error'}"
                )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error sending escalation alert: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.OPERATION_FAILED,
                    message=f"Failed to send escalation alert: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def send_status_change_notification(
        self,
        student_user_id: UUID,
        leave_id: UUID,
        old_status: str,
        new_status: str,
        subject: str,
        message: str,
        notification_type: str = TYPE_EMAIL,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send notification about leave application status change.
        
        Args:
            student_user_id: UUID of the student user
            leave_id: UUID of the leave application
            old_status: Previous status
            new_status: New status
            subject: Notification subject
            message: Notification message body
            notification_type: Type of notification (EMAIL, SMS, etc.)
            additional_metadata: Optional additional metadata
            
        Returns:
            ServiceResult containing NotificationResponse or error information
        """
        try:
            self._logger.info(
                f"Sending status change notification for leave {leave_id} "
                f"to student {student_user_id} ({old_status} -> {new_status})"
            )
            
            # Prepare metadata
            metadata = {
                "leave_id": str(leave_id),
                "event": "status_change",
                "old_status": old_status,
                "new_status": new_status,
                "timestamp": datetime.utcnow().isoformat(),
            }
            if additional_metadata:
                metadata.update(additional_metadata)
            
            # Create notification request
            notification_request = NotificationCreate(
                user_id=str(student_user_id),
                notification_type=notification_type,
                subject=subject,
                message_body=message,
                metadata=metadata,
                scheduled_at=None,
                priority=self.PRIORITY_NORMAL,
            )
            
            # Send via dispatcher
            result = self.dispatcher.send(notification_request)
            
            if result.success:
                self._logger.info(
                    f"Status change notification sent successfully for leave {leave_id}"
                )
            else:
                self._logger.warning(
                    f"Failed to send status change notification for leave {leave_id}: "
                    f"{result.error.message if result.error else 'Unknown error'}"
                )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error sending status change notification: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.OPERATION_FAILED,
                    message=f"Failed to send status change notification: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def send_bulk_notifications(
        self,
        user_ids: list[UUID],
        leave_id: UUID,
        subject: str,
        message: str,
        event_type: str,
        notification_type: str = TYPE_EMAIL,
        priority: str = PRIORITY_NORMAL,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send bulk notifications to multiple users.
        
        Args:
            user_ids: List of user UUIDs to notify
            leave_id: UUID of the leave application
            subject: Notification subject
            message: Notification message body
            event_type: Type of event triggering notifications
            notification_type: Type of notification (EMAIL, SMS, etc.)
            priority: Notification priority level
            
        Returns:
            ServiceResult containing summary of sent notifications
        """
        try:
            self._logger.info(
                f"Sending bulk notifications for leave {leave_id} "
                f"to {len(user_ids)} recipients"
            )
            
            results = {
                "total": len(user_ids),
                "successful": 0,
                "failed": 0,
                "errors": [],
            }
            
            for user_id in user_ids:
                metadata = {
                    "leave_id": str(leave_id),
                    "event": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                notification_request = NotificationCreate(
                    user_id=str(user_id),
                    notification_type=notification_type,
                    subject=subject,
                    message_body=message,
                    metadata=metadata,
                    scheduled_at=None,
                    priority=priority,
                )
                
                result = self.dispatcher.send(notification_request)
                
                if result.success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "user_id": str(user_id),
                        "error": result.error.message if result.error else "Unknown error"
                    })
            
            self._logger.info(
                f"Bulk notification completed: {results['successful']} successful, "
                f"{results['failed']} failed out of {results['total']} total"
            )
            
            return ServiceResult.success(
                results,
                message=f"Bulk notifications sent: {results['successful']}/{results['total']} successful"
            )
            
        except Exception as e:
            self._logger.error(
                f"Error sending bulk notifications: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.OPERATION_FAILED,
                    message=f"Failed to send bulk notifications: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )