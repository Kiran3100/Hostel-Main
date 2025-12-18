# --- File: app/models/auth/password_reset.py ---
"""
Password reset and management models.
Implements secure password reset workflow with token management.
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
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel

__all__ = [
    "PasswordReset",
    "PasswordHistory",
    "PasswordPolicy",
    "PasswordAttempt",
]


class PasswordReset(TimestampModel):
    """
    Password reset token management.
    
    Manages password reset tokens with secure generation,
    validation, and expiration. Implements single-use tokens.
    """

    __tablename__ = "password_resets"
    __table_args__ = (
        Index("idx_password_resets_user_id", "user_id"),
        Index("idx_password_resets_token", "token", unique=True),
        Index("idx_password_resets_expires_at", "expires_at"),
        Index("idx_password_resets_is_used", "is_used"),
        {"comment": "Password reset token management"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Reset record unique identifier",
    )

    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to user",
    )

    # Token Information
    token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Secure reset token (hashed)",
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="SHA256 hash of token for validation",
    )

    # Status
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether reset token has been used",
    )

    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether reset token is expired",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Token creation timestamp",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Token expiration timestamp (typically 1 hour)",
    )

    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when token was used",
    )

    # Request Information
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of reset request",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of reset request",
    )

    # Reset Information
    reset_ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address where password was reset",
    )

    reset_user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent where password was reset",
    )

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional reset metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="password_resets",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<PasswordReset(user_id={self.user_id}, used={self.is_used})>"

    def is_valid(self) -> bool:
        """Check if reset token is valid."""
        return (
            not self.is_used
            and not self.is_expired
            and datetime.utcnow() < self.expires_at
        )

    def mark_as_used(self, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Mark reset token as used."""
        self.is_used = True
        self.used_at = datetime.utcnow()
        self.reset_ip_address = ip_address
        self.reset_user_agent = user_agent

    def check_expiration(self) -> bool:
        """Check and update expiration status."""
        if datetime.utcnow() >= self.expires_at:
            self.is_expired = True
            return True
        return False


class PasswordHistory(TimestampModel):
    """
    Password history for reuse prevention.
    
    Stores hashed passwords to prevent password reuse.
    Implements configurable password history depth.
    """

    __tablename__ = "password_history"
    __table_args__ = (
        Index("idx_password_history_user_id", "user_id"),
        Index("idx_password_history_created_at", "created_at"),
        {"comment": "Password history for reuse prevention"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Password history record unique identifier",
    )

    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to user",
    )

    # Password Information
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password",
    )

    # Change Information
    changed_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who changed the password (admin override)",
    )

    change_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for password change",
    )

    # Request Information
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of password change",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of password change",
    )

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional password change metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="password_history",
        lazy="selectin",
    )

    changed_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[changed_by_user_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<PasswordHistory(user_id={self.user_id}, created_at={self.created_at})>"


class PasswordPolicy(TimestampModel):
    """
    Password policy configuration.
    
    Defines password strength requirements and policies.
    Supports per-tenant or system-wide policies.
    """

    __tablename__ = "password_policies"
    __table_args__ = (
        Index("idx_password_policies_tenant_id", "tenant_id"),
        Index("idx_password_policies_is_active", "is_active"),
        {"comment": "Password policy configuration and enforcement"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Policy unique identifier",
    )

    # Tenant (nullable for system-wide policy)
    tenant_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        comment="Tenant ID (null for system-wide policy)",
    )

    # Policy Name
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Policy name",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Policy description",
    )

    # Password Requirements
    min_length: Mapped[int] = mapped_column(
        Integer,
        default=8,
        nullable=False,
        comment="Minimum password length",
    )

    max_length: Mapped[int] = mapped_column(
        Integer,
        default=128,
        nullable=False,
        comment="Maximum password length",
    )

    require_uppercase: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Require at least one uppercase letter",
    )

    require_lowercase: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Require at least one lowercase letter",
    )

    require_digit: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Require at least one digit",
    )

    require_special_char: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Require at least one special character",
    )

    special_chars: Mapped[Optional[str]] = mapped_column(
        String(255),
        default="!@#$%^&*()_+-=[]{}|;:,.<>?",
        nullable=True,
        comment="Allowed special characters",
    )

    # Password History
    prevent_reuse_count: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="Number of previous passwords to prevent reuse",
    )

    # Password Expiration
    max_age_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum password age in days (null for no expiration)",
    )

    expire_warning_days: Mapped[int] = mapped_column(
        Integer,
        default=7,
        nullable=False,
        comment="Days before expiration to warn user",
    )

    # Account Lockout
    lockout_threshold: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="Failed attempts before account lockout",
    )

    lockout_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        comment="Account lockout duration in minutes",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether policy is active",
    )

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional policy configuration",
    )

    def __repr__(self) -> str:
        return f"<PasswordPolicy(name={self.name}, active={self.is_active})>"


class PasswordAttempt(TimestampModel):
    """
    Failed password attempt tracking.
    
    Tracks failed password verification attempts for security monitoring
    and account lockout implementation.
    """

    __tablename__ = "password_attempts"
    __table_args__ = (
        Index("idx_password_attempts_user_id", "user_id"),
        Index("idx_password_attempts_ip_address", "ip_address"),
        Index("idx_password_attempts_created_at", "created_at"),
        {"comment": "Failed password attempt tracking"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Attempt record unique identifier",
    )

    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to user",
    )

    # Attempt Information
    attempt_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of attempt (login, password_change, etc.)",
    )

    is_successful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Whether attempt was successful",
    )

    # Request Information
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        index=True,
        comment="IP address of attempt",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of attempt",
    )

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional attempt metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="password_attempts",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<PasswordAttempt(user_id={self.user_id}, successful={self.is_successful})>"

    @classmethod
    def count_recent_failures(
        cls,
        db_session,
        user_id: UUID,
        minutes: int = 30,
    ) -> int:
        """
        Count recent failed password attempts.
        
        Args:
            db_session: Database session
            user_id: User ID to check
            minutes: Time window in minutes
            
        Returns:
            Count of failed attempts
        """
        from sqlalchemy import and_, func
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        return db_session.query(func.count(cls.id)).filter(
            and_(
                cls.user_id == user_id,
                cls.is_successful == False,
                cls.created_at >= cutoff_time,
            )
        ).scalar() or 0