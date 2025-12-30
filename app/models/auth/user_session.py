# --- File: app/models/auth/user_session.py ---
"""
User session management models.
Tracks active sessions, login attempts, and device information.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin

__all__ = [
    "UserSession",
    "SessionToken",
    "RefreshToken",
    "LoginAttempt",
]


class UserSession(TimestampModel, SoftDeleteMixin):
    """
    Active user session tracking.
    
    Manages user sessions with device information, location tracking,
    and security monitoring. Supports multi-device sessions.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_user_sessions_user_id", "user_id"),
        Index("idx_user_sessions_session_id", "session_id", unique=True),
        Index("idx_user_sessions_last_activity", "last_activity_at"),
        Index("idx_user_sessions_is_active", "is_active"),
        {
            "comment": "User session tracking and management",
            "extend_existing": True,
        },
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Session record unique identifier",
    )

    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to user",
    )

    # Session Information
    session_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique session identifier (UUID or JWT jti)",
    )

    # Device Information
    device_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Device name (e.g., 'iPhone 13 Pro', 'Chrome on Windows')",
    )

    device_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Device type (mobile, tablet, desktop, api)",
    )

    device_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Device fingerprint hash for security",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full user agent string",
    )

    browser: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Browser name and version",
    )

    operating_system: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Operating system and version",
    )

    # Location Information
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        comment="IP address of the session",
    )

    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country from IP geolocation",
    )

    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City from IP geolocation",
    )

    timezone: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="User timezone",
    )

    # Session Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether session is currently active",
    )

    is_remember_me: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is a 'remember me' session",
    )

    # Timestamps
    login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Session login timestamp",
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Last activity timestamp for session timeout",
    )

    logout_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Session logout timestamp",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Session expiration timestamp",
    )

    # Security
    security_events: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Security-related events during session (suspicious activities)",
    )

    risk_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Risk score for this session (0-100)",
    )

    # Metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional session metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions",
        lazy="selectin",
    )

    session_tokens: Mapped[list["SessionToken"]] = relationship(
        "SessionToken",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, device={self.device_type})>"

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at

    def terminate(self) -> None:
        """Terminate the session."""
        self.is_active = False
        self.logout_at = datetime.utcnow()


class SessionToken(TimestampModel):
    """
    JWT access token storage and tracking.
    
    Stores issued access tokens for validation and revocation.
    Implements token rotation for enhanced security.
    """

    __tablename__ = "session_tokens"
    __table_args__ = (
        Index("idx_session_tokens_session_id", "session_id"),
        Index("idx_session_tokens_jti", "jti", unique=True),
        Index("idx_session_tokens_expires_at", "expires_at"),
        Index("idx_session_tokens_is_revoked", "is_revoked"),
        {
            "comment": "JWT access token management",
            "extend_existing": True,
        },
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Token record unique identifier",
    )

    # Foreign Keys
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("user_sessions.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to session",
    )

    # Token Information
    jti: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="JWT ID (unique token identifier)",
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="SHA256 hash of token for validation",
    )

    token_type: Mapped[str] = mapped_column(
        String(50),
        default="access",
        nullable=False,
        comment="Token type (access)",
    )

    # Token Status
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether token has been revoked",
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Token revocation timestamp",
    )

    revocation_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for token revocation",
    )

    # Timestamps
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Token issue timestamp",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Token expiration timestamp",
    )

    # Metadata
    scopes: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Token scopes and permissions",
    )

    # Relationships
    session: Mapped["UserSession"] = relationship(
        "UserSession",
        back_populates="session_tokens",
    )

    def __repr__(self) -> str:
        return f"<SessionToken(jti={self.jti}, expires_at={self.expires_at})>"

    def is_valid(self) -> bool:
        """Check if token is valid (not revoked and not expired)."""
        return (
            not self.is_revoked
            and datetime.utcnow() < self.expires_at
        )

    def revoke(self, reason: Optional[str] = None) -> None:
        """Revoke the token."""
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()
        self.revocation_reason = reason


class RefreshToken(TimestampModel):
    """
    JWT refresh token management.
    
    Manages refresh tokens with rotation for enhanced security.
    Implements family-based token tracking for security monitoring.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("idx_refresh_tokens_session_id", "session_id"),
        Index("idx_refresh_tokens_jti", "jti", unique=True),
        Index("idx_refresh_tokens_expires_at", "expires_at"),
        Index("idx_refresh_tokens_is_used", "is_used"),
        Index("idx_refresh_tokens_family_id", "family_id"),
        {
            "comment": "JWT refresh token management with rotation",
            "extend_existing": True,
        },
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Refresh token record unique identifier",
    )

    # Foreign Keys
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("user_sessions.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to session",
    )

    # Token Information
    jti: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="JWT ID (unique refresh token identifier)",
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="SHA256 hash of refresh token",
    )

    family_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Token family ID for rotation tracking",
    )

    # Token Rotation
    parent_token_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent token in rotation chain",
    )

    rotation_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of times token has been rotated",
    )

    # Token Status
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether refresh token has been used",
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether token has been revoked",
    )

    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when token was used",
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Token revocation timestamp",
    )

    revocation_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for revocation",
    )

    # Timestamps
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Token issue timestamp",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Token expiration timestamp",
    )

    # Relationships
    session: Mapped["UserSession"] = relationship(
        "UserSession",
        back_populates="refresh_tokens",
    )

    parent_token: Mapped[Optional["RefreshToken"]] = relationship(
        "RefreshToken",
        remote_side=[id],
        back_populates="child_tokens",
    )

    child_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="parent_token",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(jti={self.jti}, family={self.family_id})>"

    def is_valid(self) -> bool:
        """Check if refresh token is valid."""
        return (
            not self.is_used
            and not self.is_revoked
            and datetime.utcnow() < self.expires_at
        )

    def mark_as_used(self) -> None:
        """Mark refresh token as used."""
        self.is_used = True
        self.used_at = datetime.utcnow()

    def revoke_family(self, reason: str = "Token reuse detected") -> None:
        """Revoke entire token family (security breach)."""
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()
        self.revocation_reason = reason


class LoginAttempt(TimestampModel):
    """
    Failed login attempt tracking.
    
    Monitors failed login attempts for security purposes.
    Implements rate limiting and brute force prevention.
    """

    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("idx_login_attempts_user_id", "user_id"),
        Index("idx_login_attempts_ip_address", "ip_address"),
        Index("idx_login_attempts_created_at", "created_at"),
        Index("idx_login_attempts_is_successful", "is_successful"),
        {
            "comment": "Login attempt tracking for security monitoring",
            "extend_existing": True,
        },
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Login attempt unique identifier",
    )

    # Foreign Keys (nullable for failed attempts with unknown user)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to user (if identified)",
    )

    # Attempt Information
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email/username used in attempt",
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Phone number used in attempt",
    )

    # Attempt Result
    is_successful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
        comment="Whether login was successful",
    )

    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for failure (invalid_credentials, account_locked, etc.)",
    )

    # Device and Location
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        index=True,
        comment="IP address of login attempt",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent string",
    )

    device_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Device fingerprint hash",
    )

    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country from IP geolocation",
    )

    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City from IP geolocation",
    )

    # Security Analysis
    risk_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Risk score for this attempt (0-100)",
    )

    is_suspicious: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether attempt was flagged as suspicious",
    )

    security_flags: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Security flags and alerts",
    )

    # Metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional attempt metadata",
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="login_attempts",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<LoginAttempt(email={self.email}, successful={self.is_successful})>"

    @classmethod
    def count_recent_failures(
        cls,
        db_session,
        identifier: str,
        identifier_type: str = "email",
        minutes: int = 15,
    ) -> int:
        """
        Count recent failed login attempts.
        
        Args:
            db_session: Database session
            identifier: Email or phone to check
            identifier_type: Type of identifier ('email' or 'phone')
            minutes: Time window in minutes
            
        Returns:
            Count of failed attempts
        """
        from sqlalchemy import and_, func
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        filter_field = cls.email if identifier_type == "email" else cls.phone
        
        return db_session.query(func.count(cls.id)).filter(
            and_(
                filter_field == identifier,
                cls.is_successful == False,
                cls.created_at >= cutoff_time,
            )
        ).scalar() or 0