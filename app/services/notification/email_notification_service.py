# app/services/notification/email_notification_service.py
"""
Enhanced Email Notification Service

Handles high-level operations around email notifications with improved:
- Performance through batch operations
- Better error handling and validation
- Enhanced logging and monitoring
- Template validation and rendering
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import EmailNotificationRepository
from app.schemas.notification import (
    EmailRequest,
    BulkEmailRequest,
    EmailStats,
)
from app.core.exceptions import ValidationException, DatabaseException
from app.core.logging import LoggingContext

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Enhanced orchestration of email notification creation and scheduling.

    Delivery to external providers is handled by background workers.
    Enhanced with validation, error handling, and performance optimizations.
    """

    def __init__(self, email_repo: EmailNotificationRepository) -> None:
        self.email_repo = email_repo
        self._max_bulk_size = 1000  # Maximum bulk email size

    def _validate_email_request(self, request: EmailRequest) -> None:
        """Validate email request parameters."""
        if not request.recipient_email:
            raise ValidationException("Recipient email is required")
        
        if '@' not in request.recipient_email:
            raise ValidationException("Invalid email format")
        
        if not request.subject and not request.template_code:
            raise ValidationException("Either subject or template_code is required")
        
        if request.template_code and not isinstance(request.template_variables, dict):
            if request.template_variables is not None:
                raise ValidationException("Template variables must be a dictionary")

    def _validate_bulk_email_request(self, request: BulkEmailRequest) -> None:
        """Validate bulk email request parameters."""
        if not request.recipients:
            raise ValidationException("Recipients list cannot be empty")
        
        if len(request.recipients) > self._max_bulk_size:
            raise ValidationException(
                f"Bulk email size cannot exceed {self._max_bulk_size} recipients"
            )
        
        if not request.subject and not request.template_code:
            raise ValidationException("Either subject or template_code is required")
        
        # Validate all recipient emails
        for recipient in request.recipients:
            if '@' not in recipient:
                raise ValidationException(f"Invalid email format: {recipient}")

    # -------------------------------------------------------------------------
    # Single send with enhanced validation
    # -------------------------------------------------------------------------

    def send_email(
        self,
        db: Session,
        request: EmailRequest,
        user_id: Optional[UUID] = None,
        priority: str = "normal",
    ) -> UUID:
        """
        Create an email notification entry with enhanced validation.

        Enhanced with:
        - Input validation
        - Priority handling
        - Better error handling
        - Performance monitoring

        Args:
            db: Database session
            request: Email request data
            user_id: Optional user identifier
            priority: Email priority (high, normal, low)

        Returns:
            UUID: Email notification ID

        Raises:
            ValidationException: For invalid input data
            DatabaseException: For database operation failures
        """
        self._validate_email_request(request)
        
        if priority not in ["high", "normal", "low"]:
            priority = "normal"

        payload = request.model_dump(exclude_none=True)
        payload["user_id"] = user_id
        payload["priority"] = priority

        with LoggingContext(
            channel="email",
            template_code=payload.get("template_code"),
            recipient=request.recipient_email,
            priority=priority
        ):
            try:
                logger.info(
                    f"Creating email notification for {request.recipient_email}, "
                    f"template: {request.template_code}, priority: {priority}"
                )
                
                obj = self.email_repo.create_email_notification(db, payload)
                
                logger.info(f"Email notification created successfully: {obj.id}")
                return obj.id  # type: ignore[attr-defined]
                
            except SQLAlchemyError as e:
                logger.error(f"Database error creating email notification: {str(e)}")
                raise DatabaseException("Failed to create email notification") from e
            except Exception as e:
                logger.error(f"Unexpected error creating email: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Bulk send with chunking for performance
    # -------------------------------------------------------------------------

    def send_bulk_email(
        self,
        db: Session,
        request: BulkEmailRequest,
        owner_id: Optional[UUID] = None,
        chunk_size: int = 100,
    ) -> List[UUID]:
        """
        Create multiple email notifications with chunking for performance.

        Enhanced with:
        - Request validation
        - Chunked processing for large batches
        - Progress tracking
        - Transaction management

        Args:
            db: Database session
            request: Bulk email request
            owner_id: Optional owner identifier
            chunk_size: Size of processing chunks

        Returns:
            List[UUID]: List of email notification IDs

        Raises:
            ValidationException: For invalid input data
            DatabaseException: For database operation failures
        """
        self._validate_bulk_email_request(request)

        payload = request.model_dump(exclude_none=True)
        payload["owner_id"] = owner_id

        with LoggingContext(
            channel="email_bulk",
            subject=payload.get("subject"),
            recipient_count=len(request.recipients)
        ):
            try:
                logger.info(
                    f"Creating bulk email campaign for {len(request.recipients)} recipients, "
                    f"subject: {request.subject}"
                )
                
                # Process in chunks for better performance and memory management
                all_ids = []
                total_recipients = len(request.recipients)
                
                for i in range(0, total_recipients, chunk_size):
                    chunk_recipients = request.recipients[i:i + chunk_size]
                    chunk_payload = payload.copy()
                    chunk_payload["recipients"] = chunk_recipients
                    
                    logger.debug(
                        f"Processing chunk {i//chunk_size + 1}, "
                        f"recipients: {len(chunk_recipients)}"
                    )
                    
                    objs = self.email_repo.create_bulk_email_notifications(
                        db, chunk_payload
                    )
                    chunk_ids = [o.id for o in objs]  # type: ignore[attr-defined]
                    all_ids.extend(chunk_ids)
                    
                    # Commit each chunk to avoid large transactions
                    db.commit()
                
                logger.info(
                    f"Bulk email campaign created successfully, "
                    f"total notifications: {len(all_ids)}"
                )
                return all_ids
                
            except SQLAlchemyError as e:
                logger.error(f"Database error creating bulk email: {str(e)}")
                db.rollback()
                raise DatabaseException("Failed to create bulk email campaign") from e
            except Exception as e:
                logger.error(f"Unexpected error creating bulk email: {str(e)}")
                db.rollback()
                raise

    # -------------------------------------------------------------------------
    # Enhanced stats with caching
    # -------------------------------------------------------------------------

    def get_email_stats_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        use_cache: bool = True,
    ) -> EmailStats:
        """
        Get email statistics for a hostel with optional caching.

        Enhanced with:
        - Input validation
        - Fallback handling
        - Performance optimization
        - Detailed error handling

        Args:
            db: Database session
            hostel_id: Hostel identifier
            use_cache: Whether to use cached results

        Returns:
            EmailStats: Email statistics

        Raises:
            ValidationException: For invalid hostel ID
            DatabaseException: For database operation failures
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        with LoggingContext(channel="email_stats", hostel_id=str(hostel_id)):
            try:
                logger.debug(f"Retrieving email stats for hostel {hostel_id}")
                
                data = self.email_repo.get_stats_for_hostel(db, hostel_id, use_cache)
                
                if not data:
                    logger.debug(f"No email stats found for hostel {hostel_id}, returning defaults")
                    return EmailStats(
                        hostel_id=hostel_id,
                        total_sent=0,
                        total_delivered=0,
                        total_bounced=0,
                        total_failed=0,
                        total_opened=0,
                        total_clicked=0,
                        delivery_rate=0.0,
                        open_rate=0.0,
                        click_rate=0.0,
                        bounce_rate=0.0,
                    )
                
                stats = EmailStats.model_validate(data)
                logger.debug(f"Email stats retrieved: {stats.total_sent} sent")
                
                return stats
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving email stats: {str(e)}")
                raise DatabaseException("Failed to retrieve email statistics") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving email stats: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Additional utility methods
    # -------------------------------------------------------------------------

    def get_email_status(
        self,
        db: Session,
        notification_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get detailed status of an email notification.

        Args:
            db: Database session
            notification_id: Email notification ID

        Returns:
            Dict[str, Any]: Email status information

        Raises:
            ValidationException: For invalid notification ID
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")

        with LoggingContext(channel="email_status", notification_id=str(notification_id)):
            try:
                logger.debug(f"Retrieving email status for {notification_id}")
                
                status = self.email_repo.get_email_status(db, notification_id)
                if not status:
                    raise ValidationException("Email notification not found")
                
                return status
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving email status: {str(e)}")
                raise DatabaseException("Failed to retrieve email status") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving email status: {str(e)}")
                raise

    def cancel_scheduled_email(
        self,
        db: Session,
        notification_id: UUID,
        reason: str = "Cancelled by user",
    ) -> bool:
        """
        Cancel a scheduled email if it hasn't been sent yet.

        Args:
            db: Database session
            notification_id: Email notification ID
            reason: Cancellation reason

        Returns:
            bool: True if cancelled successfully

        Raises:
            ValidationException: For invalid input
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")

        with LoggingContext(channel="email_cancel", notification_id=str(notification_id)):
            try:
                logger.info(f"Cancelling email notification {notification_id}: {reason}")
                
                success = self.email_repo.cancel_email_notification(
                    db, notification_id, reason
                )
                
                if success:
                    logger.info(f"Email notification cancelled successfully")
                else:
                    logger.warning(f"Email notification could not be cancelled (may already be sent)")
                
                return success
                
            except SQLAlchemyError as e:
                logger.error(f"Database error cancelling email: {str(e)}")
                raise DatabaseException("Failed to cancel email notification") from e
            except Exception as e:
                logger.error(f"Unexpected error cancelling email: {str(e)}")
                raise