# --- File: app/models/auth/token_blacklist.py ---
"""
Token blacklist and revocation models.
Implements token revocation and security event tracking.
"""

from datetime import datetime
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
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel

__all__ = [
    "BlacklistedToken",
    "TokenRevocation",
    "SecurityEvent",
]


class BlacklistedToken(TimestampModel):
    """
    Revoked token tracking.
    
    Maintains a blacklist of revoked tokens for validation.
    Implements automatic cleanup of expired blacklisted tokens.
    """

    __tablename__ = "blacklisted_tokens"
    __table_args__ = (
        Index("idx_blacklisted_tokens_jti", "jti", unique=True),
        Index("idx_blacklisted_tokens_user_id", "user_id"),
        Index("idx_blacklisted_tokens_expires_at", "expires_at"),
        Index("idx_blacklisted_tokens_token_type", "token_type"),
        {"comment": "Revoked token blacklist for validation"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Blacklist record unique identifier",
    )

    # Token Information
    jti: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="JWT ID (unique token identifier)",
    )

    token_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Token type (access, refresh)",
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="SHA256 hash of token",
    )

    # User Information
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="Reference to user",
    )

    # Revocation Information
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Token revocation timestamp",
    )

    revocation_reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Reason for revocation",
    )

    revoked_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who revoked the token (admin action)",
    )

    # Token Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Original token expiration (for cleanup)",
    )

    # Request Information
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        comment="IP address of revocation request",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of revocation request",
    )

    # Metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional revocation metadata",
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="blacklisted_tokens",
        lazy="selectin",
    )

    revoked_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[revoked_by_user_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<BlacklistedToken(jti={self.jti}, reason={self.revocation_reason})>"

    @classmethod
    def is_blacklisted(cls, db_session, jti: str) -> bool:
        """
        Check if token is blacklisted.
        
        Args:
            db_session: Database session
            jti: JWT ID to check
            
        Returns:
            True if token is blacklisted
        """
        return db_session.query(
            db_session.query(cls).filter(cls.jti == jti).exists()
        ).scalar()


class TokenRevocation(TimestampModel):
    """
    Token revocation audit trail.
    
    Maintains detailed audit trail of all token revocations.
    Supports bulk revocation tracking and analysis.
    """

    __tablename__ = "token_revocations"
    __table_args__ = (
        Index("idx_token_revocations_user_id", "user_id"),
        Index("idx_token_revocations_revocation_type", "revocation_type"),
        Index("idx_token_revocations_created_at", "created_at"),
        {"comment": "Token revocation audit trail"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Revocation record unique identifier",
    )

    # User Information
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to user whose tokens were revoked",
    )

    # Revocation Information
    revocation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of revocation (single, session, all_tokens)",
    )

    revocation_reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Reason for revocation",
    )

    tokens_revoked_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of tokens revoked",
    )

    # Initiator Information
    initiated_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who initiated revocation (self or admin)",
    )

    is_forced: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether revocation was forced by admin",
    )

    # Request Information
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        comment="IP address of revocation request",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of revocation request",
    )

    # Metadata
    affected_token_ids: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of affected token JTIs",
    )

    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional revocation metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="token_revocations",
        lazy="selectin",
    )

    initiated_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[initiated_by_user_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TokenRevocation(user_id={self.user_id}, type={self.revocation_type}, count={self.tokens_revoked_count})>"


class SecurityEvent(TimestampModel):
    """
    Security event tracking and monitoring.
    
    Tracks security-related events for monitoring and analysis.
    Supports real-time threat detection and response.
    """

    __tablename__ = "security_events"
    __table_args__ = (
        Index("idx_security_events_user_id", "user_id"),
        Index("idx_security_events_event_type", "event_type"),
        Index("idx_security_events_severity", "severity"),
        Index("idx_security_events_created_at", "created_at"),
        Index("idx_security_events_ip_address", "ip_address"),
        {"comment": "Security event tracking and monitoring"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Security event unique identifier",
    )

    # User Information (nullable for anonymous events)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="Reference to user (if applicable)",
    )

    # Event Information
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of security event",
    )

    severity: Mapped[str] = mapped_column(
        SQLEnum(
            "low",
            "medium",
            "high",
            "critical",
            name="security_event_severity",
            create_constraint=True,
        ),
        nullable=False,
        index=True,
        comment="Event severity level",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Event description",
    )

    # Request Information
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        index=True,
        comment="IP address associated with event",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent associated with event",
    )

    device_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Device fingerprint",
    )

    # Location Information
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

    # Response Information
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether event has been resolved",
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Event resolution timestamp",
    )

    resolved_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who resolved the event",
    )

    resolution_note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Resolution notes",
    )

    # Action Taken
    action_taken: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Action taken in response to event",
    )

    # Metadata
    event_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional event data and context",
    )

    risk_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Calculated risk score (0-100)",
    )

    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional event metadata",
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="security_events",
        lazy="selectin",
    )

    resolved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[resolved_by_user_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SecurityEvent(type={self.event_type}, severity={self.severity})>"

    def resolve(self, resolved_by_id: UUID, note: Optional[str] = None) -> None:
        """Mark security event as resolved."""
        self.is_resolved = True
        self.resolved_at = datetime.utcnow()
        self.resolved_by_user_id = resolved_by_id
        self.resolution_note = note