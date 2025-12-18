"""
User Session model configuration.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.common.mixins import UUIDMixin

class UserSession(BaseModel, UUIDMixin):
    """
    User session management with security tracking.
    
    Tracks active login sessions, device information, geolocation,
    and security events for comprehensive session monitoring.
    """
    __tablename__ = "user_sessions"
    __table_args__ = (
        {"comment": "Active user sessions with device tracking"}
    )

    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True,
        comment="Foreign key to users table"
    )
    
    # Token Management
    refresh_token_hash = Column(
        String(255), 
        unique=True,
        index=True, 
        nullable=False,
        comment="Hashed refresh token for session validation"
    )
    access_token_jti = Column(
        String(36), 
        nullable=True,
        index=True,
        comment="JWT Token ID for access token tracking"
    )
    
    # Device Information
    device_info = Column(
        JSONB, 
        nullable=True,
        comment="Parsed device information (browser, os, device_type)"
    )
    user_agent = Column(
        String(500), 
        nullable=True,
        comment="Raw user agent string"
    )
    device_fingerprint = Column(
        String(255), 
        nullable=True,
        index=True,
        comment="Device fingerprint for fraud detection"
    )
    
    # Network Information
    ip_address = Column(
        String(45), 
        nullable=True,
        index=True,
        comment="IP address (IPv4 or IPv6)"
    )
    ip_location = Column(
        JSONB, 
        nullable=True,
        comment="GeoIP location data (city, country, coordinates)"
    )
    
    # Session Lifecycle
    is_revoked = Column(
        Boolean, 
        default=False, 
        nullable=False,
        index=True,
        comment="Session revocation status"
    )
    revoked_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Revocation timestamp"
    )
    revoked_by = Column(
        ForeignKey("users.id"), 
        nullable=True,
        comment="User who revoked the session"
    )
    revocation_reason = Column(
        String(255), 
        nullable=True,
        comment="Reason for session revocation"
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), 
        nullable=False,
        index=True,
        comment="Session creation timestamp"
    )
    expires_at = Column(
        DateTime(timezone=True), 
        nullable=False,
        index=True,
        comment="Session expiration timestamp"
    )
    last_activity = Column(
        DateTime(timezone=True), 
        nullable=False,
        index=True,
        comment="Last activity timestamp (updated on each request)"
    )
    
    # Session Type & Context
    session_type = Column(
        String(50), 
        default="web", 
        nullable=False,
        comment="Session type: web, mobile, api, admin"
    )
    is_remember_me = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Extended session duration flag"
    )
    
    # Security Flags
    is_suspicious = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Suspicious activity flag"
    )
    security_events = Column(
        JSONB, 
        nullable=True,
        comment="Log of security events during session"
    )
    
    # Performance Tracking
    requests_count = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="Number of requests made in this session"
    )

    # Relationships
    user = relationship("User", back_populates="sessions", foreign_keys=[user_id])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by])

    def __repr__(self):
        return f"<UserSession user_id={self.user_id} ip={self.ip_address} active={not self.is_revoked}>"
    
    @property
    def is_active(self):
        """Check if session is currently active."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return not self.is_revoked and self.expires_at > now
    
    @property
    def device_name(self):
        """Get human-readable device name."""
        if self.device_info:
            browser = self.device_info.get('browser', {}).get('name', 'Unknown')
            os = self.device_info.get('os', {}).get('name', 'Unknown')
            return f"{browser} on {os}"
        return "Unknown Device"