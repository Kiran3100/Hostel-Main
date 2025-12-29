"""
Login History model for security auditing.
"""
from sqlalchemy import Boolean, Column, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.common.mixins import TimestampMixin, UUIDMixin

class LoginHistory(BaseModel, UUIDMixin, TimestampMixin):
    """
    Login attempt history for security monitoring.
    
    Tracks both successful and failed login attempts with
    comprehensive device and location information.
    """
    __tablename__ = "user_login_history"
    __table_args__ = (
        {"comment": "Complete login attempt history"}
    )

    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=True,  # Nullable for failed attempts with invalid username
        index=True,
        comment="Foreign key to users table"
    )
    
    # Login Attempt Details
    email_attempted = Column(
        String(255), 
        nullable=False,
        index=True,
        comment="Email address used in login attempt"
    )
    is_successful = Column(
        Boolean, 
        nullable=False,
        index=True,
        comment="Login success status"
    )
    failure_reason = Column(
        String(100), 
        nullable=True,
        comment="Failure reason: invalid_credentials, account_locked, etc."
    )
    
    # Device & Network
    ip_address = Column(
        String(45), 
        nullable=True,
        index=True,
        comment="IP address of login attempt"
    )
    user_agent = Column(
        String(500), 
        nullable=True,
        comment="User agent string"
    )
    device_info = Column(
        JSONB, 
        nullable=True,
        comment="Parsed device information"
    )
    geolocation = Column(
        JSONB, 
        nullable=True,
        comment="GeoIP location data"
    )
    
    # Security Analysis
    is_suspicious = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Flagged as suspicious activity"
    )
    risk_score = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="Calculated risk score (0-100)"
    )
    security_flags = Column(
        JSONB, 
        nullable=True,
        comment="Security flags and anomalies detected"
    )
    
    # Authentication Method
    auth_method = Column(
        String(50), 
        default="password", 
        nullable=False,
        comment="Authentication method: password, otp, social, biometric"
    )
    
    # Session Created
    session_id = Column(
        ForeignKey("user_sessions.id", ondelete="SET NULL"), 
        nullable=True,
        comment="Reference to created session if successful"
    )

    # Relationships
    user = relationship("User", back_populates="login_history")
    session = relationship("UserSession")

    def __repr__(self):
        status = "SUCCESS" if self.is_successful else "FAILED"
        return f"<LoginHistory {self.email_attempted} {status} from {self.ip_address}>"