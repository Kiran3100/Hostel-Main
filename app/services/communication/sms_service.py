"""
SMS channel service with enhanced validation and quota management.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.notification import SMSNotificationRepository
from app.models.notification.sms_notification import SMSNotification as SMSNotificationModel
from app.schemas.notification.sms_notification import (
    SMSRequest,
    BulkSMSRequest,
    SMSStats,
    SMSQuota,
)
from app.schemas.notification.notification_response import NotificationResponse


logger = logging.getLogger(__name__)


class SMSService(BaseService[SMSNotificationModel, SMSNotificationRepository]):
    """
    SMS communication service with comprehensive features.
    
    Features:
    - Single and bulk SMS sending
    - Phone number validation
    - Message length validation and segmentation
    - Quota management and tracking
    - Delivery statistics
    - International number support
    """

    # Phone number validation regex (E.164 format)
    # Matches: +[country code][number] (e.g., +1234567890)
    PHONE_REGEX = re.compile(r'^\+?[1-9]\d{1,14}$')
    
    # SMS length limits (GSM 7-bit encoding)
    SINGLE_SMS_LENGTH = 160
    MULTI_SMS_SEGMENT_LENGTH = 153  # UDH overhead
    MAX_SMS_SEGMENTS = 10
    MAX_MESSAGE_LENGTH = MULTI_SMS_SEGMENT_LENGTH * MAX_SMS_SEGMENTS
    
    # Bulk sending limits
    MAX_BULK_RECIPIENTS = 10000
    DEFAULT_BULK_BATCH_SIZE = 1000

    def __init__(self, repository: SMSNotificationRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logger

    def send(
        self,
        request: SMSRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Queue and/or send a single SMS message.
        
        Args:
            request: SMS request with recipient, message, etc.
            
        Returns:
            ServiceResult containing delivery information
        """
        # Validate SMS request
        validation_result = self._validate_sms_request(request)
        if not validation_result["valid"]:
            return ServiceResult.failure(
                message=validation_result["error"],
                error=ValueError(validation_result["error"]),
            )

        # Check quota before sending
        quota_check = self._check_quota(1)
        if not quota_check["allowed"]:
            return ServiceResult.failure(
                message=quota_check["error"],
                error=ValueError(quota_check["error"]),
            )

        # Calculate segment count
        segment_count = self._calculate_segments(request.message)
        
        self._logger.info(
            f"Sending SMS to {request.recipient} ({segment_count} segment(s))"
        )

        try:
            result = self.repository.send_sms(request)
            self.db.commit()
            
            payload = self._serialize_result(result)
            payload["segment_count"] = segment_count
            
            self._logger.info(f"SMS queued successfully: {payload.get('id')}")
            
            return ServiceResult.success(
                payload,
                message="SMS queued successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error sending SMS: {str(e)}", exc_info=True)
            return self._handle_exception(e, "send sms")
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error sending SMS: {str(e)}", exc_info=True)
            return self._handle_exception(e, "send sms")

    def send_bulk(
        self,
        request: BulkSMSRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send SMS messages to multiple recipients.
        
        Args:
            request: Bulk SMS request with multiple recipients
            
        Returns:
            ServiceResult containing bulk send statistics
        """
        # Validate bulk request
        if not request.recipients or len(request.recipients) == 0:
            return ServiceResult.failure(
                message="No recipients specified",
                error=ValueError("Recipients list is empty"),
            )

        if len(request.recipients) > self.MAX_BULK_RECIPIENTS:
            return ServiceResult.failure(
                message=f"Exceeds maximum bulk size of {self.MAX_BULK_RECIPIENTS}",
                error=ValueError("Too many recipients"),
            )

        # Check quota for bulk send
        quota_check = self._check_quota(len(request.recipients))
        if not quota_check["allowed"]:
            return ServiceResult.failure(
                message=quota_check["error"],
                error=ValueError(quota_check["error"]),
            )

        # Calculate total segments
        segment_count = self._calculate_segments(request.message)
        total_segments = segment_count * len(request.recipients)
        
        self._logger.info(
            f"Sending bulk SMS to {len(request.recipients)} recipients "
            f"({total_segments} total segments)"
        )

        try:
            summary = self.repository.send_bulk(request)
            self.db.commit()
            
            payload = self._serialize_result(summary)
            payload["total_segments"] = total_segments
            payload["segment_count_per_message"] = segment_count
            
            self._logger.info(
                f"Bulk SMS queued: {payload.get('total_queued', 0)} messages"
            )
            
            return ServiceResult.success(
                payload,
                message="Bulk SMS queued successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error sending bulk SMS: {str(e)}", exc_info=True)
            return self._handle_exception(e, "send bulk sms")
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error sending bulk SMS: {str(e)}", exc_info=True)
            return self._handle_exception(e, "send bulk sms")

    def get_stats(
        self,
        start: datetime,
        end: datetime,
    ) -> ServiceResult[SMSStats]:
        """
        Get SMS statistics for a time period.
        
        Args:
            start: Start of period
            end: End of period
            
        Returns:
            ServiceResult containing SMS statistics
        """
        self._logger.debug(f"Retrieving SMS stats for period {start} to {end}")
        
        try:
            stats = self.repository.get_stats(start, end)
            return ServiceResult.success(stats)
        except Exception as e:
            self._logger.error(f"Error retrieving SMS stats: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get sms stats")

    def get_quota(self) -> ServiceResult[SMSQuota]:
        """
        Get current SMS quota information.
        
        Returns:
            ServiceResult containing quota details
        """
        self._logger.debug("Retrieving SMS quota")
        
        try:
            quota = self.repository.get_quota()
            return ServiceResult.success(quota)
        except Exception as e:
            self._logger.error(f"Error retrieving SMS quota: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get sms quota")

    def check_delivery_status(
        self,
        notification_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Check delivery status of a specific SMS.
        
        Args:
            notification_id: SMS notification identifier
            
        Returns:
            ServiceResult containing delivery status
        """
        self._logger.debug(f"Checking SMS delivery status for {notification_id}")
        
        try:
            if hasattr(self.repository, 'get_delivery_status'):
                status = self.repository.get_delivery_status(notification_id)
                return ServiceResult.success(status or {})
            else:
                return ServiceResult.success(
                    {"message": "Delivery status tracking not yet implemented"}
                )
        except Exception as e:
            self._logger.error(
                f"Error checking delivery status: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "check delivery status", notification_id)

    # ═══════════════════════════════════════════════════════════════
    # Validation and Helper Methods
    # ═══════════════════════════════════════════════════════════════

    def _validate_sms_request(self, request: SMSRequest) -> Dict[str, Any]:
        """
        Validate SMS request.
        
        Returns:
            Dictionary with 'valid' boolean and optional 'error' message
        """
        # Validate recipient
        if not request.recipient or not request.recipient.strip():
            return {"valid": False, "error": "Recipient phone number is required"}
        
        if not self._is_valid_phone(request.recipient):
            return {
                "valid": False,
                "error": f"Invalid phone number format: {request.recipient}"
            }
        
        # Validate message
        if not request.message or not request.message.strip():
            return {"valid": False, "error": "Message content is required"}
        
        if len(request.message) > self.MAX_MESSAGE_LENGTH:
            return {
                "valid": False,
                "error": f"Message exceeds maximum length of {self.MAX_MESSAGE_LENGTH} characters"
            }
        
        return {"valid": True}

    def _is_valid_phone(self, phone: str) -> bool:
        """
        Validate phone number format (E.164).
        
        Args:
            phone: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not phone or not isinstance(phone, str):
            return False
        
        # Remove common separators for validation
        cleaned = phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        return bool(self.PHONE_REGEX.match(cleaned))

    def _calculate_segments(self, message: str) -> int:
        """
        Calculate number of SMS segments required for message.
        
        Args:
            message: Message content
            
        Returns:
            Number of segments required
        """
        if not message:
            return 0
        
        message_length = len(message)
        
        if message_length <= self.SINGLE_SMS_LENGTH:
            return 1
        
        # Multi-part message
        segments = (message_length + self.MULTI_SMS_SEGMENT_LENGTH - 1) // self.MULTI_SMS_SEGMENT_LENGTH
        
        return min(segments, self.MAX_SMS_SEGMENTS)

    def _check_quota(self, message_count: int) -> Dict[str, Any]:
        """
        Check if quota allows sending specified number of messages.
        
        Args:
            message_count: Number of messages to send
            
        Returns:
            Dictionary with 'allowed' boolean and optional 'error' message
        """
        try:
            quota_result = self.get_quota()
            
            if not quota_result.success or not quota_result.data:
                # If quota check fails, allow by default (fail open)
                self._logger.warning("Quota check failed, allowing send")
                return {"allowed": True}
            
            quota = quota_result.data
            
            # Check if quota information is available
            if hasattr(quota, 'remaining'):
                remaining = quota.remaining
                if remaining < message_count:
                    return {
                        "allowed": False,
                        "error": f"Insufficient SMS quota (need {message_count}, have {remaining})"
                    }
            
            return {"allowed": True}
            
        except Exception as e:
            # Fail open on quota check errors
            self._logger.warning(f"Quota check error, allowing send: {str(e)}")
            return {"allowed": True}

    def _serialize_result(self, result: Any) -> Dict[str, Any]:
        """Serialize result object to dictionary."""
        if hasattr(result, "model_dump"):
            return result.model_dump()
        elif hasattr(result, "dict"):
            return result.dict()
        elif isinstance(result, dict):
            return result
        return {}

    def format_phone_number(self, phone: str, country_code: str = "1") -> str:
        """
        Format phone number to E.164 standard.
        
        Args:
            phone: Phone number (various formats)
            country_code: Default country code if not provided
            
        Returns:
            Formatted phone number in E.164 format
        """
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Add + if not present
        if not cleaned.startswith('+'):
            # Add country code if number doesn't have one
            if len(cleaned) == 10:  # US/Canada format
                cleaned = f"+{country_code}{cleaned}"
            else:
                cleaned = f"+{cleaned}"
        
        return cleaned