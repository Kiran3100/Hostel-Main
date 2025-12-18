# --- File: app/models/auth/otp_token.py ---
"""
OTP (One-Time Password) token models.
Supports multi-channel OTP delivery and verification.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.schemas.common.enums import OTPType

__all__ = [
    "OTPToken",
    "OTPTemplate",
    "OTPDelivery",
    "OTPThrottling",
]


class OTPToken(TimestampModel):
    """
    One-time password token storage and management.
    
    Manages OTP generation, validation, and expiration.
    Implements rate limiting and attempt tracking.
    """

    __tablename__ = "otp_tokens"
    __table_args__ = (
        Index("idx_otp_tokens_user_id", "user_id"),
        Index("idx_otp_tokens_email", "email"),
        Index("idx_otp_tokens_phone", "phone"),
        Index("idx_otp_tokens_otp_type", "otp_type"),
        Index("idx_otp_tokens_expires_at", "expires_at"),
        Index("idx_otp_tokens_is_used", "is_used"),
        {"comment": "OTP token management and verification"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="OTP record unique identifier",
    )

    # Foreign Keys (nullable for non-authenticated OTP requests)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="Reference to user (if authenticated)",
    )

    # Recipient Information
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Email address for OTP delivery",
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Phone number for OTP delivery",
    )

    # OTP Information
    otp_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Encrypted OTP code",
    )

    otp_type: Mapped[OTPType] = mapped_column(
        SQLEnum(OTPType, name="otp_type_enum", create_constraint=True),
        nullable=False,
        index=True,
        comment="OTP purpose (email_verification, password_reset, etc.)",
    )

    # Validation
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Maximum verification attempts allowed",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current number of verification attempts",
    )

    # Status
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether OTP has been successfully used",
    )

    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether OTP is expired",
    )

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="OTP generation timestamp",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="OTP expiration timestamp",
    )

    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="OTP verification timestamp",
    )

    # Delivery Information
    delivery_channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Delivery channel (email, sms, both)",
    )

    delivery_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Overall delivery status",
    )

    # Security
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of OTP request",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of OTP request",
    )

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional OTP metadata",
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="otp_tokens",
        lazy="selectin",
    )

    deliveries: Mapped[list["OTPDelivery"]] = relationship(
        "OTPDelivery",
        back_populates="otp_token",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<OTPToken(id={self.id}, type={self.otp_type}, email={self.email})>"

    def is_valid(self) -> bool:
        """Check if OTP is valid for verification."""
        return (
            not self.is_used
            and not self.is_expired
            and self.attempt_count < self.max_attempts
            and datetime.utcnow() < self.expires_at
        )

    def increment_attempt(self) -> None:
        """Increment verification attempt count."""
        self.attempt_count += 1
        if self.attempt_count >= self.max_attempts:
            self.is_expired = True

    def mark_as_used(self) -> None:
        """Mark OTP as successfully used."""
        self.is_used = True
        self.verified_at = datetime.utcnow()

    def check_expiration(self) -> bool:
        """Check and update expiration status."""
        if datetime.utcnow() >= self.expires_at:
            self.is_expired = True
            return True
        return False


class OTPTemplate(TimestampModel):
    """
    OTP message templates for different channels and purposes.
    
    Customizable templates with variable substitution.
    Supports multi-language and multi-channel templates.
    """

    __tablename__ = "otp_templates"
    __table_args__ = (
        Index("idx_otp_templates_otp_type", "otp_type"),
        Index("idx_otp_templates_channel", "channel"),
        Index("idx_otp_templates_language", "language"),
        Index(
            "idx_otp_templates_unique",
            "otp_type",
            "channel",
            "language",
            unique=True,
        ),
        {"comment": "Customizable OTP message templates"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Template unique identifier",
    )

    # Template Configuration
    otp_type: Mapped[OTPType] = mapped_column(
        SQLEnum(OTPType, name="otp_type_enum", create_constraint=True),
        nullable=False,
        index=True,
        comment="OTP type this template is for",
    )

    channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Delivery channel (email, sms)",
    )

    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
        index=True,
        comment="Template language code",
    )

    # Template Content
    subject: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email subject (for email channel)",
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Template body with variable placeholders",
    )

    html_body: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="HTML version (for email)",
    )

    # Template Variables
    variables: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Available variables and their descriptions",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether template is active",
    )

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Template description",
    )

    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional template metadata",
    )

    def __repr__(self) -> str:
        return f"<OTPTemplate(type={self.otp_type}, channel={self.channel})>"


class OTPDelivery(TimestampModel):
    """
    OTP delivery tracking per channel.
    
    Tracks individual delivery attempts and status per channel.
    Supports delivery to multiple channels simultaneously.
    """

    __tablename__ = "otp_deliveries"
    __table_args__ = (
        Index("idx_otp_deliveries_otp_token_id", "otp_token_id"),
        Index("idx_otp_deliveries_channel", "channel"),
        Index("idx_otp_deliveries_status", "status"),
        {"comment": "OTP delivery tracking and status"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Delivery record unique identifier",
    )

    # Foreign Keys
    otp_token_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("otp_tokens.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to OTP token",
    )

    # Delivery Information
    channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Delivery channel (email or sms)",
    )

    recipient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Recipient address (email or phone)",
    )

    # Delivery Status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Delivery status (pending, sent, delivered, failed)",
    )

    provider: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Service provider used (SendGrid, Twilio, etc.)",
    )

    provider_message_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Provider's message ID for tracking",
    )

    # Delivery Attempts
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of delivery attempts",
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Maximum delivery attempts",
    )

    # Timestamps
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when message was sent",
    )

    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when message was delivered",
    )

    failed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of delivery failure",
    )

    # Error Information
    error_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Error code if delivery failed",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if delivery failed",
    )

    # Metadata
    provider_response: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Full provider response data",
    )

    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional delivery metadata",
    )

    # Relationships
    otp_token: Mapped["OTPToken"] = relationship(
        "OTPToken",
        back_populates="deliveries",
    )

    def __repr__(self) -> str:
        return f"<OTPDelivery(channel={self.channel}, status={self.status})>"

    def mark_as_sent(self, provider_id: Optional[str] = None) -> None:
        """Mark delivery as sent."""
        self.status = "sent"
        self.sent_at = datetime.utcnow()
        if provider_id:
            self.provider_message_id = provider_id

    def mark_as_delivered(self) -> None:
        """Mark delivery as delivered."""
        self.status = "delivered"
        self.delivered_at = datetime.utcnow()

    def mark_as_failed(self, error_code: str, error_message: str) -> None:
        """Mark delivery as failed."""
        self.status = "failed"
        self.failed_at = datetime.utcnow()
        self.error_code = error_code
        self.error_message = error_message
        self.attempt_count += 1


class OTPThrottling(TimestampModel):
    """
    OTP request rate limiting and abuse prevention.
    
    Tracks OTP generation requests to prevent abuse.
    Implements sliding window rate limiting.
    """

    __tablename__ = "otp_throttling"
    __table_args__ = (
        Index("idx_otp_throttling_identifier", "identifier"),
        Index("idx_otp_throttling_ip_address", "ip_address"),
        Index("idx_otp_throttling_created_at", "created_at"),
        {"comment": "OTP request rate limiting and abuse prevention"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Throttling record unique identifier",
    )

    # Identifier Information
    identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Email or phone number",
    )

    identifier_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type of identifier (email or phone)",
    )

    # Request Information
    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        index=True,
        comment="IP address of request",
    )

    otp_type: Mapped[OTPType] = mapped_column(
        SQLEnum(OTPType, name="otp_type_enum", create_constraint=True),
        nullable=False,
        comment="Type of OTP requested",
    )

    # Rate Limiting
    request_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Number of requests in current window",
    )

    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Start of current rate limit window",
    )

    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="End of current rate limit window",
    )

    # Block Status
    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether identifier is temporarily blocked",
    )

    blocked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Block expiration timestamp",
    )

    block_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for blocking",
    )

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional throttling metadata",
    )

    def __repr__(self) -> str:
        return f"<OTPThrottling(identifier={self.identifier}, count={self.request_count})>"

    @classmethod
    def check_rate_limit(
        cls,
        db_session,
        identifier: str,
        ip_address: str,
        max_requests: int = 5,
        window_minutes: int = 60,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if rate limit is exceeded.
        
        Args:
            db_session: Database session
            identifier: Email or phone to check
            ip_address: IP address of request
            max_requests: Maximum requests per window
            window_minutes: Time window in minutes
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        from sqlalchemy import and_
        
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Check existing throttling record
        record = db_session.query(cls).filter(
            and_(
                cls.identifier == identifier,
                cls.created_at >= window_start,
            )
        ).first()
        
        if record:
            if record.is_blocked and record.blocked_until and now < record.blocked_until:
                return False, f"Too many requests. Please try again after {record.blocked_until}"
            
            if record.request_count >= max_requests:
                record.is_blocked = True
                record.blocked_until = now + timedelta(hours=1)
                record.block_reason = "Rate limit exceeded"
                db_session.commit()
                return False, "Too many OTP requests. Please try again later."
            
            record.request_count += 1
            db_session.commit()
        
        return True, None