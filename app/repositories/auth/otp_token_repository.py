"""
OTP Token Repository
Manages OTP generation, validation, delivery, and throttling.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session

from app.models.auth import (
    OTPToken,
    OTPTemplate,
    OTPDelivery,
    OTPThrottling,
)
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import OTPType


class OTPTokenRepository(BaseRepository[OTPToken]):
    """
    Repository for OTP token management with multi-channel delivery.
    """

    def __init__(self, db: Session):
        super().__init__(OTPToken, db)

    def create_otp(
        self,
        user_id: Optional[UUID],
        email: Optional[str],
        phone: Optional[str],
        otp_code: str,
        otp_type: OTPType,
        delivery_channel: str,
        expires_in_minutes: int = 10,
        max_attempts: int = 3,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OTPToken:
        """
        Create new OTP token.
        
        Args:
            user_id: User identifier (optional for non-authenticated requests)
            email: Email for OTP delivery
            phone: Phone for OTP delivery
            otp_code: OTP code (should be hashed)
            otp_type: Purpose of OTP
            delivery_channel: Delivery channel (email, sms, both)
            expires_in_minutes: OTP validity period
            max_attempts: Maximum verification attempts
            ip_address: Request IP address
            user_agent: Request user agent
            metadata: Additional metadata
            
        Returns:
            Created OTPToken instance
        """
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        
        otp = OTPToken(
            user_id=user_id,
            email=email,
            phone=phone,
            otp_code=otp_code,
            otp_type=otp_type,
            delivery_channel=delivery_channel,
            max_attempts=max_attempts,
            expires_at=expires_at,
            generated_at=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
        
        self.db.add(otp)
        self.db.commit()
        self.db.refresh(otp)
        return otp

    def find_valid_otp(
        self,
        identifier: str,
        identifier_type: str,
        otp_type: OTPType
    ) -> Optional[OTPToken]:
        """
        Find valid OTP for verification.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            otp_type: Type of OTP
            
        Returns:
            Valid OTPToken or None
        """
        filter_field = OTPToken.email if identifier_type == "email" else OTPToken.phone
        
        otp = self.db.query(OTPToken).filter(
            and_(
                filter_field == identifier,
                OTPToken.otp_type == otp_type,
                OTPToken.is_used == False,
                OTPToken.is_expired == False,
                OTPToken.expires_at > datetime.utcnow()
            )
        ).order_by(desc(OTPToken.created_at)).first()
        
        # Check expiration
        if otp:
            otp.check_expiration()
            self.db.commit()
            
            if not otp.is_valid():
                return None
        
        return otp

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
        otp = self.find_valid_otp(identifier, identifier_type, otp_type)
        
        if not otp:
            return False, "Invalid or expired OTP"
        
        if not otp.is_valid():
            return False, "OTP has expired or exceeded maximum attempts"
        
        # Verify OTP code (assuming otp_code in DB is hashed)
        # You should implement proper hash verification here
        if otp.otp_code != otp_code:
            otp.increment_attempt()
            self.db.commit()
            
            remaining_attempts = otp.max_attempts - otp.attempt_count
            if remaining_attempts > 0:
                return False, f"Invalid OTP. {remaining_attempts} attempts remaining"
            else:
                return False, "Maximum verification attempts exceeded"
        
        # Mark as used
        otp.mark_as_used()
        self.db.commit()
        
        return True, None

    def invalidate_previous_otps(
        self,
        identifier: str,
        identifier_type: str,
        otp_type: OTPType
    ) -> int:
        """
        Invalidate all previous OTPs for an identifier.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            otp_type: Type of OTP
            
        Returns:
            Number of OTPs invalidated
        """
        filter_field = OTPToken.email if identifier_type == "email" else OTPToken.phone
        
        count = self.db.query(OTPToken).filter(
            and_(
                filter_field == identifier,
                OTPToken.otp_type == otp_type,
                OTPToken.is_used == False,
                OTPToken.is_expired == False
            )
        ).update({
            "is_expired": True
        })
        
        self.db.commit()
        return count

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
        filter_field = OTPToken.email if identifier_type == "email" else OTPToken.phone
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        total_otps = self.db.query(func.count(OTPToken.id)).filter(
            and_(
                filter_field == identifier,
                OTPToken.created_at >= cutoff_time
            )
        ).scalar()
        
        successful_verifications = self.db.query(func.count(OTPToken.id)).filter(
            and_(
                filter_field == identifier,
                OTPToken.is_used == True,
                OTPToken.created_at >= cutoff_time
            )
        ).scalar()
        
        expired_otps = self.db.query(func.count(OTPToken.id)).filter(
            and_(
                filter_field == identifier,
                OTPToken.is_expired == True,
                OTPToken.created_at >= cutoff_time
            )
        ).scalar()
        
        return {
            "total_otps": total_otps,
            "successful_verifications": successful_verifications,
            "expired_otps": expired_otps,
            "success_rate": (successful_verifications / total_otps * 100) if total_otps > 0 else 0
        }

    def cleanup_expired_otps(self, days_old: int = 7) -> int:
        """Clean up old expired OTPs."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(OTPToken).filter(
            OTPToken.expires_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count


class OTPTemplateRepository(BaseRepository[OTPTemplate]):
    """
    Repository for OTP message template management.
    """

    def __init__(self, db: Session):
        super().__init__(OTPTemplate, db)

    def find_template(
        self,
        otp_type: OTPType,
        channel: str,
        language: str = "en"
    ) -> Optional[OTPTemplate]:
        """
        Find template for OTP type and channel.
        
        Args:
            otp_type: Type of OTP
            channel: Delivery channel (email, sms)
            language: Language code
            
        Returns:
            OTPTemplate or None
        """
        return self.db.query(OTPTemplate).filter(
            and_(
                OTPTemplate.otp_type == otp_type,
                OTPTemplate.channel == channel,
                OTPTemplate.language == language,
                OTPTemplate.is_active == True
            )
        ).first()

    def create_template(
        self,
        otp_type: OTPType,
        channel: str,
        subject: Optional[str],
        body: str,
        html_body: Optional[str] = None,
        language: str = "en",
        variables: Optional[Dict[str, str]] = None,
        description: Optional[str] = None
    ) -> OTPTemplate:
        """Create new OTP template."""
        template = OTPTemplate(
            otp_type=otp_type,
            channel=channel,
            subject=subject,
            body=body,
            html_body=html_body,
            language=language,
            variables=variables,
            description=description,
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def get_all_templates(
        self,
        otp_type: Optional[OTPType] = None,
        channel: Optional[str] = None,
        active_only: bool = True
    ) -> List[OTPTemplate]:
        """Get all templates with optional filtering."""
        query = self.db.query(OTPTemplate)
        
        if otp_type:
            query = query.filter(OTPTemplate.otp_type == otp_type)
        
        if channel:
            query = query.filter(OTPTemplate.channel == channel)
        
        if active_only:
            query = query.filter(OTPTemplate.is_active == True)
        
        return query.all()


class OTPDeliveryRepository(BaseRepository[OTPDelivery]):
    """
    Repository for OTP delivery tracking.
    """

    def __init__(self, db: Session):
        super().__init__(OTPDelivery, db)

    def create_delivery(
        self,
        otp_token_id: UUID,
        channel: str,
        recipient: str,
        provider: Optional[str] = None
    ) -> OTPDelivery:
        """
        Create OTP delivery record.
        
        Args:
            otp_token_id: OTP token ID
            channel: Delivery channel
            recipient: Recipient address
            provider: Service provider
            
        Returns:
            Created OTPDelivery instance
        """
        delivery = OTPDelivery(
            otp_token_id=otp_token_id,
            channel=channel,
            recipient=recipient,
            status="pending",
            provider=provider,
        )
        
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    def mark_as_sent(
        self,
        delivery_id: UUID,
        provider_message_id: Optional[str] = None
    ) -> bool:
        """Mark delivery as sent."""
        delivery = self.find_by_id(delivery_id)
        if delivery:
            delivery.mark_as_sent(provider_message_id)
            self.db.commit()
            return True
        return False

    def mark_as_delivered(self, delivery_id: UUID) -> bool:
        """Mark delivery as delivered."""
        delivery = self.find_by_id(delivery_id)
        if delivery:
            delivery.mark_as_delivered()
            self.db.commit()
            return True
        return False

    def mark_as_failed(
        self,
        delivery_id: UUID,
        error_code: str,
        error_message: str
    ) -> bool:
        """Mark delivery as failed."""
        delivery = self.find_by_id(delivery_id)
        if delivery:
            delivery.mark_as_failed(error_code, error_message)
            self.db.commit()
            return True
        return False

    def get_delivery_statistics(
        self,
        channel: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get delivery statistics.
        
        Args:
            channel: Filter by channel
            days: Number of days to analyze
            
        Returns:
            Dictionary with delivery statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(OTPDelivery).filter(
            OTPDelivery.created_at >= cutoff_time
        )
        
        if channel:
            query = query.filter(OTPDelivery.channel == channel)
        
        total_deliveries = query.count()
        
        status_breakdown = self.db.query(
            OTPDelivery.status,
            func.count(OTPDelivery.id)
        ).filter(
            OTPDelivery.created_at >= cutoff_time
        )
        
        if channel:
            status_breakdown = status_breakdown.filter(OTPDelivery.channel == channel)
        
        status_breakdown = status_breakdown.group_by(OTPDelivery.status).all()
        
        return {
            "total_deliveries": total_deliveries,
            "status_breakdown": {
                status: count for status, count in status_breakdown
            },
            "success_rate": self._calculate_success_rate(status_breakdown, total_deliveries)
        }

    def _calculate_success_rate(
        self,
        status_breakdown: List[Tuple[str, int]],
        total: int
    ) -> float:
        """Calculate delivery success rate."""
        if total == 0:
            return 0.0
        
        successful = sum(
            count for status, count in status_breakdown 
            if status in ["sent", "delivered"]
        )
        
        return (successful / total) * 100


class OTPThrottlingRepository(BaseRepository[OTPThrottling]):
    """
    Repository for OTP rate limiting and abuse prevention.
    """

    def __init__(self, db: Session):
        super().__init__(OTPThrottling, db)

    def check_rate_limit(
        self,
        identifier: str,
        identifier_type: str,
        ip_address: str,
        otp_type: OTPType,
        max_requests: int = 5,
        window_minutes: int = 60
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if rate limit is exceeded.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone'
            ip_address: IP address
            otp_type: Type of OTP
            max_requests: Maximum requests per window
            window_minutes: Time window in minutes
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Check existing throttling record
        record = self.db.query(OTPThrottling).filter(
            and_(
                OTPThrottling.identifier == identifier,
                OTPThrottling.identifier_type == identifier_type,
                OTPThrottling.otp_type == otp_type,
                OTPThrottling.created_at >= window_start
            )
        ).first()
        
        if record:
            # Check if blocked
            if record.is_blocked and record.blocked_until and now < record.blocked_until:
                time_remaining = (record.blocked_until - now).seconds // 60
                return False, f"Too many requests. Please try again after {time_remaining} minutes"
            
            # Check rate limit
            if record.request_count >= max_requests:
                # Block the identifier
                record.is_blocked = True
                record.blocked_until = now + timedelta(hours=1)
                record.block_reason = "Rate limit exceeded"
                self.db.commit()
                return False, "Too many OTP requests. Please try again later."
            
            # Increment count
            record.request_count += 1
            self.db.commit()
        else:
            # Create new throttling record
            window_end = now + timedelta(minutes=window_minutes)
            new_record = OTPThrottling(
                identifier=identifier,
                identifier_type=identifier_type,
                ip_address=ip_address,
                otp_type=otp_type,
                request_count=1,
                window_start=now,
                window_end=window_end,
            )
            self.db.add(new_record)
            self.db.commit()
        
        return True, None

    def reset_throttling(
        self,
        identifier: str,
        identifier_type: str
    ) -> bool:
        """Reset throttling for an identifier."""
        record = self.db.query(OTPThrottling).filter(
            and_(
                OTPThrottling.identifier == identifier,
                OTPThrottling.identifier_type == identifier_type
            )
        ).first()
        
        if record:
            record.is_blocked = False
            record.blocked_until = None
            record.request_count = 0
            self.db.commit()
            return True
        return False

    def cleanup_old_records(self, days_old: int = 7) -> int:
        """Clean up old throttling records."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(OTPThrottling).filter(
            OTPThrottling.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count