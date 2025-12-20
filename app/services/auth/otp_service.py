"""
OTP Service
Handles OTP generation, delivery, verification, and throttling.
"""

import random
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.auth import (
    OTPTokenRepository,
    OTPTemplateRepository,
    OTPDeliveryRepository,
    OTPThrottlingRepository,
)
from app.schemas.common.enums import OTPType
from app.core.exceptions import (
    OTPGenerationError,
    OTPVerificationError,
    RateLimitExceededError,
)


class OTPService:
    """
    Service for OTP operations including generation, delivery, and verification.
    """

    def __init__(self, db: Session):
        self.db = db
        self.otp_token_repo = OTPTokenRepository(db)
        self.otp_template_repo = OTPTemplateRepository(db)
        self.otp_delivery_repo = OTPDeliveryRepository(db)
        self.otp_throttling_repo = OTPThrottlingRepository(db)

    # ==================== OTP Generation ====================

    def generate_otp(
        self,
        user_id: Optional[UUID],
        identifier: str,
        identifier_type: str,
        otp_type: OTPType,
        ip_address: str,
        user_agent: Optional[str] = None,
        length: int = 6,
        expires_in_minutes: int = 10,
        max_attempts: int = 3
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Generate OTP code with rate limiting.
        
        Args:
            user_id: User identifier (optional for non-authenticated requests)
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            otp_type: Purpose of OTP
            ip_address: Request IP address
            user_agent: Request user agent
            length: OTP code length
            expires_in_minutes: OTP validity period
            max_attempts: Maximum verification attempts
            
        Returns:
            Tuple of (success, otp_code, error_message)
        """
        # Check rate limiting
        is_allowed, error_msg = self.otp_throttling_repo.check_rate_limit(
            identifier=identifier,
            identifier_type=identifier_type,
            ip_address=ip_address,
            otp_type=otp_type,
            max_requests=5,
            window_minutes=60
        )
        
        if not is_allowed:
            raise RateLimitExceededError(error_msg)
        
        # Invalidate previous OTPs
        self.otp_token_repo.invalidate_previous_otps(
            identifier=identifier,
            identifier_type=identifier_type,
            otp_type=otp_type
        )
        
        # Generate OTP code
        otp_code = self._generate_otp_code(length)
        otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
        
        # Prepare parameters based on identifier type
        email = identifier if identifier_type == "email" else None
        phone = identifier if identifier_type == "phone" else None
        
        # Create OTP token
        try:
            otp_token = self.otp_token_repo.create_otp(
                user_id=user_id,
                email=email,
                phone=phone,
                otp_code=otp_hash,
                otp_type=otp_type,
                delivery_channel=identifier_type,
                expires_in_minutes=expires_in_minutes,
                max_attempts=max_attempts,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return True, otp_code, None
            
        except Exception as e:
            raise OTPGenerationError(f"Failed to generate OTP: {str(e)}")

    def _generate_otp_code(self, length: int = 6) -> str:
        """Generate random numeric OTP code."""
        min_value = 10 ** (length - 1)
        max_value = (10 ** length) - 1
        return str(random.randint(min_value, max_value))

    # ==================== OTP Delivery ====================

    def send_otp(
        self,
        user_id: Optional[UUID],
        identifier: str,
        identifier_type: str,
        otp_type: OTPType,
        ip_address: str,
        user_agent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Generate and send OTP via appropriate channel.
        
        Args:
            user_id: User identifier
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            otp_type: Purpose of OTP
            ip_address: Request IP address
            user_agent: Request user agent
            context: Additional context for template rendering
            
        Returns:
            Tuple of (success, otp_code_for_testing, error_message)
        """
        # Generate OTP
        success, otp_code, error = self.generate_otp(
            user_id=user_id,
            identifier=identifier,
            identifier_type=identifier_type,
            otp_type=otp_type,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not success:
            return False, None, error
        
        # Get OTP token
        otp_token = self.otp_token_repo.find_valid_otp(
            identifier=identifier,
            identifier_type=identifier_type,
            otp_type=otp_type
        )
        
        if not otp_token:
            return False, None, "Failed to retrieve OTP token"
        
        # Create delivery record
        delivery = self.otp_delivery_repo.create_delivery(
            otp_token_id=otp_token.id,
            channel=identifier_type,
            recipient=identifier
        )
        
        # Send OTP via appropriate channel
        try:
            if identifier_type == "email":
                self._send_email_otp(
                    recipient=identifier,
                    otp_code=otp_code,
                    otp_type=otp_type,
                    context=context
                )
            elif identifier_type == "phone":
                self._send_sms_otp(
                    recipient=identifier,
                    otp_code=otp_code,
                    otp_type=otp_type,
                    context=context
                )
            
            # Mark delivery as sent
            self.otp_delivery_repo.mark_as_sent(delivery.id)
            
            # In development, return OTP code for testing
            # In production, this should be None
            return True, otp_code, None
            
        except Exception as e:
            # Mark delivery as failed
            self.otp_delivery_repo.mark_as_failed(
                delivery.id,
                error_code="DELIVERY_FAILED",
                error_message=str(e)
            )
            return False, None, f"Failed to send OTP: {str(e)}"

    def _send_email_otp(
        self,
        recipient: str,
        otp_code: str,
        otp_type: OTPType,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send OTP via email.
        
        Args:
            recipient: Email address
            otp_code: OTP code to send
            otp_type: Type of OTP
            context: Template context
        """
        # Get email template
        template = self.otp_template_repo.find_template(
            otp_type=otp_type,
            channel="email"
        )
        
        # Build context for template
        template_context = {
            "otp_code": otp_code,
            "recipient": recipient,
            **(context or {})
        }
        
        # Render template
        if template:
            subject = template.subject
            body = self._render_template(template.body, template_context)
            html_body = self._render_template(template.html_body, template_context) if template.html_body else None
        else:
            # Default template
            subject = self._get_default_subject(otp_type)
            body = f"Your verification code is: {otp_code}\n\nThis code will expire in 10 minutes."
            html_body = None
        
        # TODO: Integrate with email service (SendGrid, AWS SES, etc.)
        # For now, just log
        print(f"Sending OTP email to {recipient}: {otp_code}")
        # email_service.send_email(recipient, subject, body, html_body)

    def _send_sms_otp(
        self,
        recipient: str,
        otp_code: str,
        otp_type: OTPType,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send OTP via SMS.
        
        Args:
            recipient: Phone number
            otp_code: OTP code to send
            otp_type: Type of OTP
            context: Template context
        """
        # Get SMS template
        template = self.otp_template_repo.find_template(
            otp_type=otp_type,
            channel="sms"
        )
        
        # Build context for template
        template_context = {
            "otp_code": otp_code,
            "recipient": recipient,
            **(context or {})
        }
        
        # Render template
        if template:
            message = self._render_template(template.body, template_context)
        else:
            # Default template
            message = f"Your verification code is: {otp_code}"
        
        # TODO: Integrate with SMS service (Twilio, AWS SNS, etc.)
        # For now, just log
        print(f"Sending OTP SMS to {recipient}: {otp_code}")
        # sms_service.send_sms(recipient, message)

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Render template with context variables."""
        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        return template

    def _get_default_subject(self, otp_type: OTPType) -> str:
        """Get default email subject based on OTP type."""
        subjects = {
            OTPType.EMAIL_VERIFICATION: "Verify Your Email Address",
            OTPType.PHONE_VERIFICATION: "Verify Your Phone Number",
            OTPType.PASSWORD_RESET: "Reset Your Password",
            OTPType.TWO_FACTOR_AUTH: "Two-Factor Authentication Code",
            OTPType.LOGIN_VERIFICATION: "Login Verification Code",
            OTPType.TRANSACTION_VERIFICATION: "Transaction Verification Code",
        }
        return subjects.get(otp_type, "Verification Code")

    # ==================== OTP Verification ====================

    def verify_otp(
        self,
        identifier: str,
        identifier_type: str,
        otp_code: str,
        otp_type: OTPType
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify OTP code.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            otp_code: OTP code to verify
            otp_type: Type of OTP
            
        Returns:
            Tuple of (success, error_message)
        """
        # Hash the provided OTP
        otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
        
        # Verify OTP
        success, error = self.otp_token_repo.verify_otp(
            identifier=identifier,
            identifier_type=identifier_type,
            otp_code=otp_hash,
            otp_type=otp_type
        )
        
        if not success:
            raise OTPVerificationError(error)
        
        return True, None

    def validate_otp_format(self, otp_code: str, expected_length: int = 6) -> bool:
        """
        Validate OTP code format.
        
        Args:
            otp_code: OTP code to validate
            expected_length: Expected code length
            
        Returns:
            True if format is valid
        """
        if not otp_code:
            return False
        
        if len(otp_code) != expected_length:
            return False
        
        if not otp_code.isdigit():
            return False
        
        return True

    # ==================== OTP Management ====================

    def resend_otp(
        self,
        identifier: str,
        identifier_type: str,
        otp_type: OTPType,
        ip_address: str,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Resend OTP code (generates new one).
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            otp_type: Type of OTP
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Tuple of (success, error_message)
        """
        # This will generate a new OTP and invalidate the old one
        success, otp_code, error = self.send_otp(
            user_id=None,
            identifier=identifier,
            identifier_type=identifier_type,
            otp_type=otp_type,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return success, error

    def get_otp_status(
        self,
        identifier: str,
        identifier_type: str,
        otp_type: OTPType
    ) -> Optional[Dict[str, Any]]:
        """
        Get status of current OTP.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            otp_type: Type of OTP
            
        Returns:
            OTP status information or None
        """
        otp_token = self.otp_token_repo.find_valid_otp(
            identifier=identifier,
            identifier_type=identifier_type,
            otp_type=otp_type
        )
        
        if not otp_token:
            return None
        
        return {
            "is_valid": otp_token.is_valid(),
            "attempts_remaining": otp_token.max_attempts - otp_token.attempt_count,
            "expires_at": otp_token.expires_at,
            "generated_at": otp_token.generated_at,
            "delivery_status": otp_token.delivery_status
        }

    def cancel_otp(
        self,
        identifier: str,
        identifier_type: str,
        otp_type: OTPType
    ) -> bool:
        """
        Cancel/invalidate current OTP.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            otp_type: Type of OTP
            
        Returns:
            Success status
        """
        count = self.otp_token_repo.invalidate_previous_otps(
            identifier=identifier,
            identifier_type=identifier_type,
            otp_type=otp_type
        )
        
        return count > 0

    # ==================== Rate Limiting ====================

    def check_rate_limit(
        self,
        identifier: str,
        identifier_type: str,
        ip_address: str,
        otp_type: OTPType
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if rate limit allows OTP generation.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            ip_address: Request IP address
            otp_type: Type of OTP
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        return self.otp_throttling_repo.check_rate_limit(
            identifier=identifier,
            identifier_type=identifier_type,
            ip_address=ip_address,
            otp_type=otp_type
        )

    def reset_rate_limit(
        self,
        identifier: str,
        identifier_type: str
    ) -> bool:
        """
        Reset rate limiting for an identifier (admin function).
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            
        Returns:
            Success status
        """
        return self.otp_throttling_repo.reset_throttling(
            identifier=identifier,
            identifier_type=identifier_type
        )

    # ==================== Statistics ====================

    def get_otp_statistics(
        self,
        identifier: str,
        identifier_type: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get OTP usage statistics.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            days: Number of days to analyze
            
        Returns:
            Dictionary with OTP statistics
        """
        return self.otp_token_repo.get_otp_statistics(
            identifier=identifier,
            identifier_type=identifier_type,
            days=days
        )

    def get_delivery_statistics(
        self,
        channel: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get OTP delivery statistics.
        
        Args:
            channel: Filter by channel (email, sms)
            days: Number of days to analyze
            
        Returns:
            Dictionary with delivery statistics
        """
        return self.otp_delivery_repo.get_delivery_statistics(
            channel=channel,
            days=days
        )

    # ==================== Template Management ====================

    def create_otp_template(
        self,
        otp_type: OTPType,
        channel: str,
        subject: Optional[str],
        body: str,
        html_body: Optional[str] = None,
        language: str = "en",
        variables: Optional[Dict[str, str]] = None,
        description: Optional[str] = None
    ) -> Any:
        """
        Create OTP message template.
        
        Args:
            otp_type: Type of OTP
            channel: Delivery channel (email, sms)
            subject: Email subject (for email channel)
            body: Template body
            html_body: HTML version (for email)
            language: Language code
            variables: Available template variables
            description: Template description
            
        Returns:
            Created template
        """
        return self.otp_template_repo.create_template(
            otp_type=otp_type,
            channel=channel,
            subject=subject,
            body=body,
            html_body=html_body,
            language=language,
            variables=variables,
            description=description
        )

    def get_templates(
        self,
        otp_type: Optional[OTPType] = None,
        channel: Optional[str] = None
    ) -> list:
        """
        Get OTP templates.
        
        Args:
            otp_type: Filter by OTP type
            channel: Filter by channel
            
        Returns:
            List of templates
        """
        return self.otp_template_repo.get_all_templates(
            otp_type=otp_type,
            channel=channel
        )

    # ==================== Cleanup ====================

    def cleanup_expired_otps(self, days_old: int = 7) -> Dict[str, int]:
        """
        Clean up expired OTP data.
        
        Args:
            days_old: Remove data older than this many days
            
        Returns:
            Dictionary with cleanup counts
        """
        return {
            "otp_tokens_cleaned": self.otp_token_repo.cleanup_expired_otps(days_old),
            "otp_throttling_cleaned": self.otp_throttling_repo.cleanup_old_records(days_old)
        }