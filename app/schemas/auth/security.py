# --- File: app/schemas/auth/security.py ---
"""
Security monitoring schemas for login attempts, security events, and threat analysis.
Pydantic v2 compliant.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseSchema

__all__ = [
    "SecurityEventType",
    "SecurityEventSeverity",
    "LoginAttemptSummary",
    "SecurityEventSummary",
    "ThreatAnalysis",
]


class SecurityEventType(str, Enum):
    """Security event types."""
    
    FAILED_LOGIN = "failed_login"
    SUSPICIOUS_LOGIN = "suspicious_login"
    ACCOUNT_LOCKED = "account_locked"
    PASSWORD_CHANGED = "password_changed"
    EMAIL_CHANGED = "email_changed"
    PHONE_CHANGED = "phone_changed"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SESSION_HIJACK = "session_hijack"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    CREDENTIAL_STUFFING = "credential_stuffing"
    ACCOUNT_TAKEOVER = "account_takeover"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_BREACH = "data_breach"
    ANOMALOUS_ACTIVITY = "anomalous_activity"


class SecurityEventSeverity(str, Enum):
    """Security event severity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LoginAttemptSummary(BaseSchema):
    """
    Summary of a login attempt.
    
    Provides essential information about login attempts for monitoring.
    """
    
    id: str = Field(
        ...,
        description="Login attempt ID",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID (if attempt was for existing user)",
    )
    identifier: str = Field(
        ...,
        description="Email or phone used for login attempt",
        examples=["user@example.com", "+919876543210"],
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="IP address of the attempt",
        examples=["192.168.1.1"],
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="User agent string",
    )
    success: bool = Field(
        ...,
        description="Whether login attempt was successful",
    )
    attempted_at: datetime = Field(
        ...,
        description="Timestamp of login attempt (UTC)",
    )
    location: Optional[str] = Field(
        default=None,
        description="Geographic location based on IP",
        examples=["Mumbai, India"],
    )
    device_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Parsed device information",
        examples=[{
            "device_type": "mobile",
            "browser": "Chrome",
            "os": "Android"
        }],
    )


class SecurityEventSummary(BaseSchema):
    """
    Summary of a security event.
    
    Provides detailed information about security incidents.
    """
    
    id: str = Field(
        ...,
        description="Security event ID",
    )
    user_id: str = Field(
        ...,
        description="User ID associated with event",
    )
    event_type: str = Field(
        ...,
        description="Type of security event",
        examples=[e.value for e in SecurityEventType],
    )
    reason: str = Field(
        ...,
        description="Event reason/description",
        examples=["Multiple failed login attempts from same IP"],
    )
    severity: str = Field(
        ...,
        description="Event severity level",
        examples=[s.value for s in SecurityEventSeverity],
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event details",
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="IP address associated with event",
    )
    created_at: datetime = Field(
        ...,
        description="Event creation timestamp (UTC)",
    )
    resolved: bool = Field(
        default=False,
        description="Whether event has been resolved",
    )
    resolved_at: Optional[datetime] = Field(
        default=None,
        description="Resolution timestamp (UTC)",
    )

    @field_validator("resolved_at", mode="after")
    @classmethod
    def validate_resolved_timestamp(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Ensure resolved_at is set only when resolved is True."""
        if hasattr(info, 'data'):
            data = info.data
            if v is not None and not data.get('resolved', False):
                raise ValueError("resolved_at can only be set when resolved is True")
            if data.get('resolved', False) and v is None:
                # Auto-set if not provided
                return datetime.utcnow()
        return v


class ThreatAnalysis(BaseSchema):
    """
    Comprehensive threat analysis for a user.
    
    Provides risk assessment and actionable recommendations.
    """
    
    user_id: str = Field(
        ...,
        description="User ID being analyzed",
    )
    threat_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall threat score (0-100)",
    )
    threat_level: str = Field(
        ...,
        description="Threat level classification",
        examples=["MINIMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
    )
    failed_login_rate: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Failed login rate percentage (0-100)",
    )
    unusual_activity_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Unusual activity score (0-100)",
    )
    security_event_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Security event severity score (0-100)",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Security recommendations",
        examples=[
            ["Enable MFA", "Review recent login activity"],
            ["Force password reset", "Temporary account suspension"],
        ],
    )
    analyzed_at: datetime = Field(
        ...,
        description="Analysis timestamp (UTC)",
    )

    @field_validator("threat_level", mode="after")
    @classmethod
    def validate_threat_level(cls, v: str) -> str:
        """Validate threat level is one of the allowed values."""
        allowed_levels = {"MINIMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(
                f"Threat level must be one of: {', '.join(allowed_levels)}"
            )
        return v_upper