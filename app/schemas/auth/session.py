# --- File: app/schemas/auth/session.py ---
"""
Session management schemas with device tracking and activity monitoring.
Pydantic v2 compliant.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseSchema

__all__ = [
    "SessionInfo",
    "SessionListResponse",
    "SessionStatistics",
]


class SessionInfo(BaseSchema):
    """
    Individual session information with device and activity details.
    
    Provides comprehensive session metadata for user review.
    """

    id: str = Field(
        ...,
        description="Session unique identifier",
    )
    user_id: str = Field(
        ...,
        description="User identifier",
    )
    device_info: Dict[str, str] = Field(
        ...,
        description="Parsed device information (type, browser, OS)",
        examples=[{
            "device_type": "Desktop",
            "browser": "Chrome",
            "os": "Windows"
        }],
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="IP address of the session",
        examples=["192.168.1.1"],
    )
    location: Optional[str] = Field(
        default=None,
        description="Geographic location based on IP",
        examples=["Mumbai, India"],
    )
    created_at: datetime = Field(
        ...,
        description="Session creation timestamp (UTC)",
    )
    last_activity: datetime = Field(
        ...,
        description="Last activity timestamp (UTC)",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Session expiration timestamp (UTC)",
    )
    is_current: bool = Field(
        default=False,
        description="Whether this is the current session",
    )
    is_revoked: bool = Field(
        default=False,
        description="Whether session has been revoked",
    )


class SessionListResponse(BaseSchema):
    """
    Response containing list of user sessions.
    
    Provides session overview with count statistics.
    """

    sessions: List[SessionInfo] = Field(
        default_factory=list,
        description="List of session information",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of sessions",
    )
    active_count: int = Field(
        ...,
        ge=0,
        description="Number of currently active sessions",
    )

    @field_validator("active_count", mode="after")
    @classmethod
    def validate_active_count(cls, v: int, info) -> int:
        """Ensure active count doesn't exceed total count."""
        if hasattr(info, 'data') and 'total_count' in info.data:
            total = info.data['total_count']
            if v > total:
                raise ValueError("Active count cannot exceed total count")
        return v


class SessionStatistics(BaseSchema):
    """
    Session statistics and analytics for a user.
    
    Provides insights into session patterns and usage.
    """

    total_sessions: int = Field(
        ...,
        ge=0,
        description="Total number of sessions (all time)",
    )
    active_sessions: int = Field(
        ...,
        ge=0,
        description="Number of currently active sessions",
    )
    revoked_sessions: int = Field(
        ...,
        ge=0,
        description="Number of revoked sessions",
    )
    unique_ip_addresses: int = Field(
        ...,
        ge=0,
        description="Number of unique IP addresses used",
    )
    unique_devices: int = Field(
        ...,
        ge=0,
        description="Number of unique devices",
    )
    most_recent_activity: Optional[datetime] = Field(
        default=None,
        description="Timestamp of most recent activity (UTC)",
    )
    average_session_duration_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Average session duration in seconds",
    )

    @field_validator("active_sessions", mode="after")
    @classmethod
    def validate_active_sessions(cls, v: int, info) -> int:
        """Ensure active sessions doesn't exceed total sessions."""
        if hasattr(info, 'data') and 'total_sessions' in info.data:
            total = info.data['total_sessions']
            if v > total:
                raise ValueError("Active sessions cannot exceed total sessions")
        return v

    @field_validator("revoked_sessions", mode="after")
    @classmethod
    def validate_revoked_sessions(cls, v: int, info) -> int:
        """Ensure revoked sessions doesn't exceed total sessions."""
        if hasattr(info, 'data') and 'total_sessions' in info.data:
            total = info.data['total_sessions']
            if v > total:
                raise ValueError("Revoked sessions cannot exceed total sessions")
        return v