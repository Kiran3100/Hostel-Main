# --- File: C:\Hostel-Main\app\services\notification\sms_notification_service.py ---
"""
SMS Notification Service - Handles SMS delivery, cost tracking, and DLT compliance.

Integrates with SMS providers (Twilio, MSG91, AWS SNS) and manages
SMS-specific features like segmentation, DLT templates, and delivery tracking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
import re
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.notification.notification import Notification
from app.models.notification.sms_notification import SMSNotification
from app.repositories.notification.sms_notification_repository import (
    SMSNotificationRepository
)
from app.repositories.notification.notification_repository import NotificationRepository
from app.schemas.common.enums import NotificationStatus
from app.core.config import settings
from app.core.exceptions import SMSDeliveryError

logger = logging.getLogger(__name__)


class SMSNotificationService:
    """
    Service for SMS notification delivery and tracking.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.sms_repo = SMSNotificationRepository(db_session)
        self.notification_repo = NotificationRepository(db_session)
        
        # Initialize SMS provider
        self.sms_provider = self._initialize_sms_provider()

    def send_sms(
        self,
        notification: Notification,
        sender_id: Optional[str] = None,
        dlt_template_id: Optional[str] = None,
        dlt_entity_id: Optional[str] = None
    ) -> SMSNotification:
        """
        Send SMS notification with delivery tracking.
        
        Args:
            notification: Base notification object
            sender_id: Sender ID/name (alphanumeric, max 11 chars)
            dlt_template_id: DLT template ID for compliance
            dlt_entity_id: DLT entity ID
            
        Returns:
            SMSNotification object with delivery details
        """
        try:
            # Validate phone number
            phone_number = notification.recipient_phone
            if not phone_number:
                # Try to get phone from user
                if notification.recipient_user and notification.recipient_user.phone:
                    phone_number = notification.recipient_user.phone
                else:
                    raise SMSDeliveryError("No recipient phone number")
            
            # Format phone number to E.164
            formatted_phone = self._format_phone_number(phone_number)
            
            if not self._validate_phone_number(formatted_phone):
                raise SMSDeliveryError(f"Invalid phone number: {phone_number}")
            
            # Prepare message text
            message_text = notification.message_body
            
            # Detect encoding
            encoding = self._detect_encoding(message_text)
            
            # Calculate segments
            character_count = len(message_text)
            segments_count = self._calculate_segments(message_text, encoding)
            
            # Check message length limits
            if segments_count > 10:  # Limit to 10 segments
                raise SMSDeliveryError("Message too long (max 10 segments)")
            
            # Create SMS notification record
            sms_data = {
                'message_text': message_text,
                'sender_id': sender_id or settings.DEFAULT_SMS_SENDER_ID,
                'dlt_template_id': dlt_template_id,
                'dlt_entity_id': dlt_entity_id,
                'segments_count': segments_count,
                'character_count': character_count,
                'encoding': encoding,
                'provider_name': self.sms_provider.provider_name
            }
            
            sms_notification = self.sms_repo.create_sms_with_details(
                notification=notification,
                sms_data=sms_data
            )
            
            # Send via SMS provider
            provider_response = self._send_via_provider(
                to_phone=formatted_phone,
                message=message_text,
                sender_id=sender_id,
                dlt_template_id=dlt_template_id,
                dlt_entity_id=dlt_entity_id
            )
            
            # Calculate cost
            cost_per_segment = self._get_cost_per_segment(formatted_phone)
            total_cost = cost_per_segment * segments_count
            
            # Update SMS notification with provider response
            sms_notification.provider_message_id = provider_response.get('message_id')
            sms_notification.provider_response = provider_response
            sms_notification.provider_status = provider_response.get('status')
            sms_notification.cost = cost_per_segment
            sms_notification.currency = settings.SMS_CURRENCY
            sms_notification.delivery_status = 'sent'
            
            # Update notification status
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            
            self.db_session.commit()
            
            logger.info(
                f"SMS sent successfully: {notification.id} to {formatted_phone} "
                f"({segments_count} segments, cost: {total_cost})"
            )
            
            return sms_notification
            
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}", exc_info=True)
            
            # Update notification as failed
            notification.status = NotificationStatus.FAILED
            notification.failed_at = datetime.utcnow()
            notification.failure_reason = str(e)
            
            self.db_session.commit()
            
            raise SMSDeliveryError(f"Failed to send SMS: {str(e)}")

    def handle_delivery_report(
        self,
        provider_message_id: str,
        delivered: bool,
        delivery_status: str,
        provider_response: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Handle SMS delivery report from provider."""
        try:
            # Find SMS by provider message ID
            provider_name = self.sms_provider.provider_name
            sms = self.sms_repo.find_by_provider_message_id(
                provider_name,
                provider_message_id
            )
            
            if not sms:
                logger.warning(
                    f"SMS not found for provider message ID: {provider_message_id}"
                )
                return False
            
            # Update delivery status
            error_details = None
            if error_code or error_message:
                error_details = {
                    'code': error_code,
                    'message': error_message
                }
            
            success = self.sms_repo.update_delivery_status(
                sms.id,
                delivered,
                delivery_status,
                provider_response,
                error_details
            )
            
            if success:
                logger.info(
                    f"Delivery report processed for SMS {sms.id}: "
                    f"delivered={delivered}, status={delivery_status}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling delivery report: {str(e)}", exc_info=True)
            return False

    def get_cost_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get SMS cost analytics."""
        try:
            return self.sms_repo.get_cost_analytics(start_date, end_date, hostel_id)
        except Exception as e:
            logger.error(f"Error getting cost analytics: {str(e)}", exc_info=True)
            raise

    def get_delivery_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: str = 'day'
    ) -> List[Dict[str, Any]]:
        """Get SMS delivery analytics."""
        try:
            return self.sms_repo.get_delivery_analytics(start_date, end_date, group_by)
        except Exception as e:
            logger.error(f"Error getting delivery analytics: {str(e)}", exc_info=True)
            raise

    def get_provider_performance(self) -> List[Dict[str, Any]]:
        """Get SMS provider performance metrics."""
        try:
            return self.sms_repo.get_provider_performance()
        except Exception as e:
            logger.error(f"Error getting provider performance: {str(e)}", exc_info=True)
            raise

    def get_dlt_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate DLT compliance report."""
        try:
            return self.sms_repo.get_dlt_compliance_report(start_date, end_date)
        except Exception as e:
            logger.error(f"Error getting DLT compliance report: {str(e)}", exc_info=True)
            raise

    def optimize_message_content(
        self,
        message: str,
        max_segments: int = 3
    ) -> Dict[str, Any]:
        """Optimize message content to reduce segments."""
        try:
            encoding = self._detect_encoding(message)
            current_segments = self._calculate_segments(message, encoding)
            
            if current_segments <= max_segments:
                return {
                    'optimized': False,
                    'original_message': message,
                    'current_segments': current_segments,
                    'encoding': encoding
                }
            
            # Suggest optimizations
            suggestions = []
            
            # Remove extra whitespace
            optimized_message = re.sub(r'\s+', ' ', message).strip()
            optimized_segments = self._calculate_segments(optimized_message, encoding)
            
            if optimized_segments < current_segments:
                suggestions.append({
                    'type': 'whitespace_removal',
                    'message': optimized_message,
                    'segments': optimized_segments,
                    'savings': current_segments - optimized_segments
                })
            
            # Suggest abbreviations (you can expand this)
            abbreviations = {
                'and': '&',
                'you': 'u',
                'your': 'ur',
                'please': 'pls',
                'thanks': 'thx'
            }
            
            abbreviated_message = message
            for full, abbr in abbreviations.items():
                abbreviated_message = re.sub(
                    r'\b' + full + r'\b',
                    abbr,
                    abbreviated_message,
                    flags=re.IGNORECASE
                )
            
            abbreviated_segments = self._calculate_segments(abbreviated_message, encoding)
            
            if abbreviated_segments < current_segments:
                suggestions.append({
                    'type': 'abbreviations',
                    'message': abbreviated_message,
                    'segments': abbreviated_segments,
                    'savings': current_segments - abbreviated_segments
                })
            
            return {
                'optimized': True,
                'original_message': message,
                'current_segments': current_segments,
                'encoding': encoding,
                'suggestions': suggestions
            }
            
        except Exception as e:
            logger.error(f"Error optimizing message: {str(e)}", exc_info=True)
            return {
                'optimized': False,
                'error': str(e)
            }

    # Helper methods
    def _initialize_sms_provider(self):
        """Initialize SMS service provider based on configuration."""
        provider_type = getattr(settings, 'SMS_PROVIDER', 'twilio')
        
        if provider_type == 'twilio':
            from app.integrations.sms.twilio_provider import TwilioProvider
            return TwilioProvider()
        elif provider_type == 'msg91':
            from app.integrations.sms.msg91_provider import MSG91Provider
            return MSG91Provider()
        elif provider_type == 'sns':
            from app.integrations.sms.sns_provider import SNSProvider
            return SNSProvider()
        else:
            from app.integrations.sms.mock_provider import MockSMSProvider
            return MockSMSProvider()

    def _send_via_provider(
        self,
        to_phone: str,
        message: str,
        sender_id: Optional[str] = None,
        dlt_template_id: Optional[str] = None,
        dlt_entity_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS via configured provider."""
        return self.sms_provider.send_sms(
            to_phone=to_phone,
            message=message,
            sender_id=sender_id,
            dlt_template_id=dlt_template_id,
            dlt_entity_id=dlt_entity_id
        )

    def _format_phone_number(self, phone: str) -> str:
        """Format phone number to E.164 format."""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Add country code if not present (assume India +91 for this example)
        if not digits.startswith('91') and len(digits) == 10:
            digits = '91' + digits
        
        return '+' + digits

    def _validate_phone_number(self, phone: str) -> bool:
        """Validate phone number in E.164 format."""
        pattern = r'^\+[1-9]\d{1,14}$'
        return re.match(pattern, phone) is not None

    def _detect_encoding(self, message: str) -> str:
        """Detect if message needs Unicode encoding."""
        # Check if message contains non-GSM characters
        gsm_chars = set(
            "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
            "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
        )
        
        for char in message:
            if char not in gsm_chars:
                return 'Unicode'
        
        return 'GSM-7'

    def _calculate_segments(self, message: str, encoding: str) -> int:
        """Calculate number of SMS segments."""
        length = len(message)
        
        if encoding == 'Unicode':
            # Unicode: 70 chars per segment, 67 for concatenated
            if length <= 70:
                return 1
            return (length + 66) // 67
        else:
            # GSM-7: 160 chars per segment, 153 for concatenated
            if length <= 160:
                return 1
            return (length + 152) // 153

    def _get_cost_per_segment(self, phone: str) -> Decimal:
        """Get cost per SMS segment based on destination."""
        # This is a simplified version - in production, you'd have a comprehensive
        # rate table based on country, carrier, etc.
        
        country_code = phone[1:3]  # Extract country code
        
        # Example rates (in USD or INR)
        rates = {
            '91': Decimal('0.02'),  # India
            '1': Decimal('0.01'),   # USA/Canada
            '44': Decimal('0.03'),  # UK
        }
        
        return rates.get(country_code, Decimal('0.05'))  # Default rate


