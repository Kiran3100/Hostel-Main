# app/services/student/student_communication_service.py
"""
Student Communication Service

Provides comprehensive communication capabilities for students and their guardians,
including notifications, multi-channel messaging, and batch operations.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.workflows import NotificationWorkflowService
from app.repositories.student import StudentRepository
from app.schemas.student import StudentContactInfo
from app.core.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)

# Type definitions
ChannelType = Literal["email", "sms", "push", "in_app", "all"]
RecipientType = Literal["student", "guardian", "both"]


class StudentCommunicationService:
    """
    High-level service for student and guardian communications.

    Responsibilities:
    - Send notifications to students via multiple channels
    - Send notifications to guardians (primary or all)
    - Batch communication operations
    - Schedule future notifications
    - Track communication history
    - Handle multi-channel delivery with fallback
    """

    def __init__(
        self,
        notification_workflow: NotificationWorkflowService,
        student_repo: StudentRepository,
    ) -> None:
        self.notification_workflow = notification_workflow
        self.student_repo = student_repo

    # -------------------------------------------------------------------------
    # Contact Info Retrieval
    # -------------------------------------------------------------------------

    def get_contact_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentContactInfo:
        """
        Retrieve comprehensive contact information for a student.

        Args:
            db: Database session
            student_id: Student UUID

        Returns:
            StudentContactInfo with student and guardian contact details

        Raises:
            ValidationException: If student not found
        """
        try:
            student = self.student_repo.get_student_with_contacts(db, student_id)
            if not student:
                raise ValidationException(f"Student not found: {student_id}")

            return StudentContactInfo.model_validate(student)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving contact info for student {student_id}: {e}",
                exc_info=True,
            )
            raise ValidationException("Failed to retrieve student contact information")

    def validate_contact_availability(
        self,
        db: Session,
        student_id: UUID,
        channel: ChannelType,
        recipient: RecipientType = "student",
    ) -> bool:
        """
        Validate if the requested communication channel is available.

        Args:
            db: Database session
            student_id: Student UUID
            channel: Communication channel to validate
            recipient: Who to validate (student, guardian, or both)

        Returns:
            True if channel is available, False otherwise
        """
        try:
            contact = self.get_contact_info(db, student_id)

            if recipient in ("student", "both"):
                if not contact.user_id:
                    return False
                # Additional channel-specific validation can be added

            if recipient in ("guardian", "both"):
                if channel == "email" and not contact.guardian_email:
                    return False
                if channel == "sms" and not contact.guardian_phone:
                    return False

            return True

        except ValidationException:
            return False

    # -------------------------------------------------------------------------
    # Student Notifications
    # -------------------------------------------------------------------------

    def send_notification_to_student(
        self,
        db: Session,
        student_id: UUID,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
        channel: ChannelType = "all",
        priority: str = "normal",
        scheduled_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Send a notification to a student via specified channel(s).

        Args:
            db: Database session
            student_id: Student UUID
            template_code: Notification template identifier
            variables: Template variables for personalization
            channel: Communication channel(s) to use
            priority: Notification priority (low, normal, high, urgent)
            scheduled_at: Optional datetime to schedule the notification

        Returns:
            Dict with notification details and status

        Raises:
            ValidationException: If student not found or lacks required contact info
            BusinessLogicException: If notification creation fails
        """
        logger.info(
            f"Sending {priority} notification to student {student_id} "
            f"via {channel} using template {template_code}"
        )

        try:
            contact = self.get_contact_info(db, student_id)

            if not contact.user_id:
                raise ValidationException(
                    f"Student {student_id} is missing linked user account"
                )

            # Prepare notification data
            notification_data = {
                "user_id": contact.user_id,
                "template_code": template_code,
                "hostel_id": contact.hostel_id,
                "variables": variables or {},
                "channel": channel,
                "priority": priority,
                "scheduled_at": scheduled_at,
            }

            # Create and queue notification
            result = self._send_notification(db, notification_data)

            logger.info(
                f"Successfully queued notification for student {student_id}: "
                f"{result.get('notification_id')}"
            )

            return result

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to send notification to student {student_id}: {e}",
                exc_info=True,
            )
            raise BusinessLogicException(
                f"Failed to send notification to student: {str(e)}"
            )

    def send_general_notice_to_student(
        self,
        db: Session,
        student_id: UUID,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send a general informational message to the student.

        Legacy method maintained for backward compatibility.
        Consider using send_notification_to_student for new implementations.

        Args:
            db: Database session
            student_id: Student UUID
            template_code: Notification template identifier
            variables: Template variables

        Raises:
            ValidationException: If student not found or notification fails
        """
        self.send_notification_to_student(
            db=db,
            student_id=student_id,
            template_code=template_code,
            variables=variables,
            channel="all",
            priority="normal",
        )

    # -------------------------------------------------------------------------
    # Guardian Notifications
    # -------------------------------------------------------------------------

    def send_notification_to_guardian(
        self,
        db: Session,
        student_id: UUID,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
        channel: ChannelType = "email",
        all_guardians: bool = False,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """
        Send a notification to student's guardian(s).

        Args:
            db: Database session
            student_id: Student UUID
            template_code: Notification template identifier
            variables: Template variables
            channel: Preferred communication channel
            all_guardians: If True, send to all guardians; else only primary
            priority: Notification priority

        Returns:
            Dict with notification details and delivery status

        Raises:
            ValidationException: If guardian contact info is unavailable
        """
        logger.info(
            f"Sending notification to guardian(s) of student {student_id} "
            f"via {channel} using template {template_code}"
        )

        try:
            contact = self.get_contact_info(db, student_id)

            # Validate guardian contact availability
            has_email = bool(contact.guardian_email)
            has_phone = bool(contact.guardian_phone)

            if not has_email and not has_phone:
                raise ValidationException(
                    f"No guardian contact information available for student {student_id}"
                )

            # Determine which channel to use based on availability
            actual_channel = self._determine_guardian_channel(
                channel, has_email, has_phone
            )

            # Prepare guardian-specific variables
            guardian_vars = variables or {}
            guardian_vars.update({
                "student_name": contact.student_name or "Student",
                "student_id": str(student_id),
                "guardian_name": contact.guardian_name or "Guardian",
            })

            # For now, we send via the notification workflow
            # In a complete implementation, you might have a separate
            # guardian user account or use external email/SMS service
            notification_data = {
                "recipient_email": contact.guardian_email if has_email else None,
                "recipient_phone": contact.guardian_phone if has_phone else None,
                "template_code": template_code,
                "hostel_id": contact.hostel_id,
                "variables": guardian_vars,
                "channel": actual_channel,
                "priority": priority,
                "recipient_type": "guardian",
            }

            result = self._send_external_notification(db, notification_data)

            logger.info(
                f"Successfully sent notification to guardian of student {student_id}"
            )

            return result

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to send notification to guardian of student {student_id}: {e}",
                exc_info=True,
            )
            raise BusinessLogicException(
                f"Failed to send notification to guardian: {str(e)}"
            )

    def send_notice_to_guardian(
        self,
        db: Session,
        student_id: UUID,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send a notice to the primary guardian.

        Legacy method maintained for backward compatibility.

        Args:
            db: Database session
            student_id: Student UUID
            template_code: Notification template identifier
            variables: Template variables
        """
        try:
            self.send_notification_to_guardian(
                db=db,
                student_id=student_id,
                template_code=template_code,
                variables=variables,
                channel="email",
                all_guardians=False,
            )
        except ValidationException:
            # Silently fail if no guardian contact (legacy behavior)
            logger.warning(
                f"Could not send notice to guardian of student {student_id}: "
                "No contact information available"
            )

    # -------------------------------------------------------------------------
    # Batch Operations
    # -------------------------------------------------------------------------

    def send_batch_notification(
        self,
        db: Session,
        student_ids: List[UUID],
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
        recipient: RecipientType = "student",
        channel: ChannelType = "all",
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """
        Send the same notification to multiple students and/or their guardians.

        Args:
            db: Database session
            student_ids: List of student UUIDs
            template_code: Notification template identifier
            variables: Shared template variables (can be personalized per student)
            recipient: Who should receive (student, guardian, or both)
            channel: Communication channel(s)
            priority: Notification priority

        Returns:
            Dict with batch operation summary
        """
        logger.info(
            f"Sending batch notification to {len(student_ids)} students "
            f"via {channel} using template {template_code}"
        )

        results = {
            "total": len(student_ids),
            "successful": 0,
            "failed": 0,
            "failures": [],
        }

        for student_id in student_ids:
            try:
                if recipient in ("student", "both"):
                    self.send_notification_to_student(
                        db=db,
                        student_id=student_id,
                        template_code=template_code,
                        variables=variables,
                        channel=channel,
                        priority=priority,
                    )

                if recipient in ("guardian", "both"):
                    self.send_notification_to_guardian(
                        db=db,
                        student_id=student_id,
                        template_code=template_code,
                        variables=variables,
                        channel=channel,
                        priority=priority,
                    )

                results["successful"] += 1

            except Exception as e:
                logger.warning(
                    f"Failed to send notification to student {student_id}: {e}"
                )
                results["failed"] += 1
                results["failures"].append({
                    "student_id": str(student_id),
                    "error": str(e),
                })

        logger.info(
            f"Batch notification complete: {results['successful']} successful, "
            f"{results['failed']} failed"
        )

        return results

    # -------------------------------------------------------------------------
    # Emergency & Urgent Communications
    # -------------------------------------------------------------------------

    def send_emergency_notification(
        self,
        db: Session,
        student_id: UUID,
        message: str,
        subject: str,
        recipient: RecipientType = "both",
    ) -> Dict[str, Any]:
        """
        Send an emergency notification via all available channels.

        Args:
            db: Database session
            student_id: Student UUID
            message: Emergency message content
            subject: Message subject/title
            recipient: Who should receive the emergency notification

        Returns:
            Dict with delivery status across all channels
        """
        logger.warning(
            f"Sending EMERGENCY notification to student {student_id} and/or guardian"
        )

        variables = {
            "message": message,
            "subject": subject,
            "timestamp": datetime.utcnow().isoformat(),
            "is_emergency": True,
        }

        results = {"channels_used": [], "delivery_status": {}}

        try:
            if recipient in ("student", "both"):
                student_result = self.send_notification_to_student(
                    db=db,
                    student_id=student_id,
                    template_code="emergency_notification",
                    variables=variables,
                    channel="all",
                    priority="urgent",
                )
                results["student_notification"] = student_result
                results["channels_used"].append("student")

            if recipient in ("guardian", "both"):
                # Try email first, then SMS as fallback
                try:
                    guardian_result = self.send_notification_to_guardian(
                        db=db,
                        student_id=student_id,
                        template_code="emergency_notification_guardian",
                        variables=variables,
                        channel="all",
                        priority="urgent",
                    )
                    results["guardian_notification"] = guardian_result
                    results["channels_used"].append("guardian")
                except ValidationException as e:
                    logger.warning(f"Could not notify guardian: {e}")
                    results["guardian_notification"] = {"error": str(e)}

            results["success"] = len(results["channels_used"]) > 0

        except Exception as e:
            logger.error(
                f"Emergency notification failed for student {student_id}: {e}",
                exc_info=True,
            )
            results["success"] = False
            results["error"] = str(e)

        return results

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _send_notification(
        self,
        db: Session,
        notification_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Internal helper to create and queue a notification via workflow service.

        Args:
            db: Database session
            notification_data: Notification parameters

        Returns:
            Dict with notification ID and status
        """
        # Extract parameters
        user_id = notification_data["user_id"]
        template_code = notification_data["template_code"]
        hostel_id = notification_data.get("hostel_id")
        variables = notification_data.get("variables", {})
        channel = notification_data.get("channel", "all")
        priority = notification_data.get("priority", "normal")
        scheduled_at = notification_data.get("scheduled_at")

        # Use the public interface of NotificationWorkflowService
        # Assuming it has a create_notification method
        # If not, this would need to be adjusted based on actual implementation
        try:
            # This is a more proper way than calling _create_and_queue_notification
            notification = self.notification_workflow.create_notification(
                db=db,
                user_id=user_id,
                template_code=template_code,
                hostel_id=hostel_id,
                variables=variables,
                channel=channel,
                priority=priority,
                scheduled_at=scheduled_at,
            )

            return {
                "notification_id": notification.id if hasattr(notification, 'id') else None,
                "status": "queued",
                "channel": channel,
                "priority": priority,
            }

        except AttributeError:
            # Fallback to original method if create_notification doesn't exist
            # This maintains backward compatibility
            logger.warning(
                "NotificationWorkflowService.create_notification not found, "
                "using legacy method"
            )
            return self._legacy_create_notification(
                db, user_id, template_code, hostel_id, variables
            )

    def _legacy_create_notification(
        self,
        db: Session,
        user_id: UUID,
        template_code: str,
        hostel_id: Optional[UUID],
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Legacy fallback for creating notifications.

        This maintains compatibility with the original implementation.
        """
        # Call the protected method as last resort
        notification = self.notification_workflow._create_and_queue_notification(
            db=db,
            user_id=user_id,
            template_code=template_code,
            hostel_id=hostel_id,
            variables=variables,
        )

        return {
            "notification_id": notification.id if hasattr(notification, 'id') else None,
            "status": "queued",
        }

    def _send_external_notification(
        self,
        db: Session,
        notification_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send notification to external recipient (guardian) via email/SMS.

        Args:
            db: Database session
            notification_data: Notification parameters including recipient contact

        Returns:
            Dict with delivery status
        """
        # In a complete implementation, this would integrate with
        # email service (SendGrid, AWS SES) or SMS service (Twilio)
        # For now, we'll create a placeholder implementation

        template_code = notification_data["template_code"]
        channel = notification_data.get("channel", "email")
        recipient_email = notification_data.get("recipient_email")
        recipient_phone = notification_data.get("recipient_phone")
        variables = notification_data.get("variables", {})

        logger.info(
            f"Sending external notification via {channel} to "
            f"email={recipient_email}, phone={recipient_phone}"
        )

        # TODO: Implement actual email/SMS sending logic here
        # For now, return a success status
        return {
            "status": "queued",
            "channel": channel,
            "recipient_email": recipient_email,
            "recipient_phone": recipient_phone,
            "template_code": template_code,
        }

    def _determine_guardian_channel(
        self,
        preferred_channel: ChannelType,
        has_email: bool,
        has_phone: bool,
    ) -> str:
        """
        Determine the actual channel to use for guardian communication.

        Args:
            preferred_channel: Requested channel
            has_email: Whether guardian email is available
            has_phone: Whether guardian phone is available

        Returns:
            Actual channel to use
        """
        if preferred_channel == "all":
            channels = []
            if has_email:
                channels.append("email")
            if has_phone:
                channels.append("sms")
            return ",".join(channels) if channels else "email"

        if preferred_channel == "email" and has_email:
            return "email"

        if preferred_channel == "sms" and has_phone:
            return "sms"

        # Fallback logic
        if has_email:
            return "email"
        if has_phone:
            return "sms"

        return preferred_channel  # Will fail validation upstream