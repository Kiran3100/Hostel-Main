"""
Email channel service with enhanced validation and error handling.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.notification import (
    EmailNotificationRepository,
    NotificationTemplateRepository,
)
from app.models.notification.email_notification import EmailNotification as EmailNotificationModel
from app.schemas.notification.email_notification import (
    EmailRequest,
    BulkEmailRequest,
    EmailStats,
    EmailTracking,
    EmailTemplate,
    EmailSchedule,
)
from app.schemas.notification.notification_template import TemplatePreview, TemplateResponse


logger = logging.getLogger(__name__)


class EmailService(BaseService[EmailNotificationModel, EmailNotificationRepository]):
    """
    Email communication service with comprehensive features.
    
    Features:
    - Single and bulk email sending
    - Template rendering and management
    - Email scheduling (one-time and recurring)
    - Open and click tracking
    - Delivery analytics
    - Retry management for failures
    - Email validation
    """

    # Email validation regex (basic RFC 5322 compliance)
    EMAIL_REGEX = re.compile(
        r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9]"
        r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9]"
        r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
    )
    
    MAX_RECIPIENTS_PER_EMAIL = 50
    MAX_SUBJECT_LENGTH = 255
    MAX_BULK_BATCH_SIZE = 10000

    def __init__(
        self,
        repository: EmailNotificationRepository,
        template_repo: NotificationTemplateRepository,
        db_session: Session,
    ):
        super().__init__(repository, db_session)
        self.template_repo = template_repo
        self._logger = logger

    def send(
        self,
        request: EmailRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Queue and/or send a single email with tracking.
        
        Args:
            request: Email request with recipients, subject, body, etc.
            
        Returns:
            ServiceResult containing tracking information
        """
        # Validate email request
        validation_result = self._validate_email_request(request)
        if not validation_result["valid"]:
            return ServiceResult.failure(
                message=validation_result["error"],
                error=ValueError(validation_result["error"]),
            )

        self._logger.info(
            f"Sending email to {len(request.recipients)} recipient(s): {request.subject}"
        )

        try:
            tracking = self.repository.send_email(request)
            self.db.commit()
            
            payload = self._serialize_tracking(tracking)
            
            self._logger.info(f"Email queued successfully: {payload.get('id')}")
            
            return ServiceResult.success(
                payload,
                message="Email queued successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error sending email: {str(e)}", exc_info=True)
            return self._handle_exception(e, "send email")
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error sending email: {str(e)}", exc_info=True)
            return self._handle_exception(e, "send email")

    def send_bulk(
        self,
        request: BulkEmailRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send bulk emails with batching support.
        
        Args:
            request: Bulk email request with multiple recipients
            
        Returns:
            ServiceResult containing bulk send statistics
        """
        # Validate bulk request
        if not request.recipients or len(request.recipients) == 0:
            return ServiceResult.failure(
                message="No recipients specified",
                error=ValueError("Recipients list is empty"),
            )

        if len(request.recipients) > self.MAX_BULK_BATCH_SIZE:
            return ServiceResult.failure(
                message=f"Exceeds maximum bulk size of {self.MAX_BULK_BATCH_SIZE}",
                error=ValueError("Too many recipients"),
            )

        self._logger.info(
            f"Sending bulk email to {len(request.recipients)} recipients: {request.subject}"
        )

        try:
            stats = self.repository.send_bulk(request)
            self.db.commit()
            
            payload = self._serialize_stats(stats)
            
            self._logger.info(
                f"Bulk email queued: {payload.get('total_queued', 0)} messages"
            )
            
            return ServiceResult.success(
                payload,
                message="Bulk email queued successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error sending bulk email: {str(e)}", exc_info=True)
            return self._handle_exception(e, "send bulk email")
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error sending bulk email: {str(e)}", exc_info=True)
            return self._handle_exception(e, "send bulk email")

    def send_template(
        self,
        template_code: str,
        variables: Dict[str, Any],
        recipients: List[str],
        subject_override: Optional[str] = None,
        priority: str = "normal",
        track_opens: bool = True,
        track_clicks: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Render an email template and send to recipients.
        
        Args:
            template_code: Template identifier
            variables: Variables for template rendering
            recipients: List of email addresses
            subject_override: Override template subject
            priority: Email priority
            track_opens: Enable open tracking
            track_clicks: Enable click tracking
            
        Returns:
            ServiceResult containing send status
        """
        # Validate recipients
        if not recipients:
            return ServiceResult.failure(
                message="No recipients specified",
                error=ValueError("Recipients list is empty"),
            )

        self._logger.info(
            f"Rendering and sending template '{template_code}' to {len(recipients)} recipient(s)"
        )

        try:
            # Render template
            preview = self.template_repo.preview(
                TemplatePreview(
                    template_code=template_code,
                    variables=variables,
                    use_defaults=True,
                )
            )
            
            if not preview or not preview.rendered_body:
                self._logger.error(f"Template rendering failed for '{template_code}'")
                return ServiceResult.failure(
                    message=f"Template '{template_code}' rendering failed",
                    error=ValueError("Template render failed"),
                )

            # Create email request
            email_request = EmailRequest(
                recipients=recipients,
                subject=subject_override or preview.subject or f"Message - {template_code}",
                html_body=preview.rendered_body,
                text_body=preview.rendered_text if hasattr(preview, 'rendered_text') else None,
                attachments=[],
                template_code=template_code,
                template_variables=variables,
                track_opens=track_opens,
                track_clicks=track_clicks,
                priority=priority,
            )
            
            # Send email
            return self.send(email_request)
            
        except Exception as e:
            self._logger.error(
                f"Error sending templated email: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "send templated email")

    def schedule(
        self,
        schedule: EmailSchedule,
    ) -> ServiceResult[bool]:
        """
        Schedule email for future delivery or set up recurring emails.
        
        Args:
            schedule: Email schedule configuration
            
        Returns:
            ServiceResult indicating success
        """
        self._logger.info(
            f"Scheduling email for {schedule.send_at if hasattr(schedule, 'send_at') else 'recurring delivery'}"
        )

        try:
            success = self.repository.schedule_email(schedule)
            self.db.commit()
            
            if success:
                self._logger.info("Email scheduled successfully")
            else:
                self._logger.warning("Email scheduling returned false")
            
            return ServiceResult.success(
                bool(success),
                message="Email scheduled successfully" if success else "Email scheduling failed"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error scheduling email: {str(e)}", exc_info=True)
            return self._handle_exception(e, "schedule email")
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error scheduling email: {str(e)}", exc_info=True)
            return self._handle_exception(e, "schedule email")

    def get_stats(
        self,
        start: datetime,
        end: datetime,
    ) -> ServiceResult[EmailStats]:
        """
        Get email statistics for a time period.
        
        Args:
            start: Start of period
            end: End of period
            
        Returns:
            ServiceResult containing email statistics
        """
        self._logger.debug(f"Retrieving email stats for period {start} to {end}")
        
        try:
            stats = self.repository.get_stats(start, end)
            return ServiceResult.success(stats)
        except Exception as e:
            self._logger.error(f"Error retrieving email stats: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get email stats")

    def get_tracking(
        self,
        notification_id: UUID,
    ) -> ServiceResult[EmailTracking]:
        """
        Get detailed tracking information for a specific email.
        
        Args:
            notification_id: Email notification identifier
            
        Returns:
            ServiceResult containing tracking details
        """
        self._logger.debug(f"Retrieving email tracking for {notification_id}")
        
        try:
            tracking = self.repository.get_tracking(notification_id)
            return ServiceResult.success(tracking)
        except Exception as e:
            self._logger.error(
                f"Error retrieving email tracking: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get email tracking", notification_id)

    def retry_failed(
        self,
        notification_id: UUID,
        max_retries: int = 3,
    ) -> ServiceResult[int]:
        """
        Retry failed email delivery.
        
        Args:
            notification_id: Email to retry
            max_retries: Maximum retry attempts
            
        Returns:
            ServiceResult containing count of emails queued for retry
        """
        self._logger.info(f"Retrying failed email {notification_id}")
        
        try:
            count = self.repository.retry_failed(notification_id)
            self.db.commit()
            
            self._logger.info(f"Queued {count} email(s) for retry")
            
            return ServiceResult.success(
                count or 0,
                message=f"{count or 0} email(s) queued for retry"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error retrying email: {str(e)}", exc_info=True)
            return self._handle_exception(e, "retry failed emails", notification_id)
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error retrying email: {str(e)}", exc_info=True)
            return self._handle_exception(e, "retry failed emails", notification_id)

    # ═══════════════════════════════════════════════════════════════
    # Validation and Helper Methods
    # ═══════════════════════════════════════════════════════════════

    def _validate_email_request(self, request: EmailRequest) -> Dict[str, Any]:
        """
        Validate email request.
        
        Returns:
            Dictionary with 'valid' boolean and optional 'error' message
        """
        # Validate recipients
        if not request.recipients or len(request.recipients) == 0:
            return {"valid": False, "error": "No recipients specified"}
        
        if len(request.recipients) > self.MAX_RECIPIENTS_PER_EMAIL:
            return {
                "valid": False,
                "error": f"Too many recipients (max {self.MAX_RECIPIENTS_PER_EMAIL})"
            }
        
        # Validate email addresses
        for email in request.recipients:
            if not self._is_valid_email(email):
                return {"valid": False, "error": f"Invalid email address: {email}"}
        
        # Validate subject
        if not request.subject or not request.subject.strip():
            return {"valid": False, "error": "Subject is required"}
        
        if len(request.subject) > self.MAX_SUBJECT_LENGTH:
            return {
                "valid": False,
                "error": f"Subject exceeds maximum length of {self.MAX_SUBJECT_LENGTH}"
            }
        
        # Validate body
        if not request.html_body and not request.text_body:
            return {"valid": False, "error": "Email body is required"}
        
        return {"valid": True}

    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format."""
        if not email or not isinstance(email, str):
            return False
        return bool(self.EMAIL_REGEX.match(email.strip()))

    def _serialize_tracking(self, tracking: Any) -> Dict[str, Any]:
        """Serialize tracking object to dictionary."""
        if hasattr(tracking, "model_dump"):
            return tracking.model_dump()
        elif hasattr(tracking, "dict"):
            return tracking.dict()
        elif isinstance(tracking, dict):
            return tracking
        return {}

    def _serialize_stats(self, stats: Any) -> Dict[str, Any]:
        """Serialize stats object to dictionary."""
        if hasattr(stats, "model_dump"):
            return stats.model_dump()
        elif hasattr(stats, "dict"):
            return stats.dict()
        elif isinstance(stats, dict):
            return stats
        return {}