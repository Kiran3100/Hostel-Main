"""
User session schemas with enhanced tracking and management.
"""

from datetime import datetime
from typing import Dict, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema

__all__ = [
    "UserSession",
    "SessionInfo",
    "ActiveSessionsList",
    "RevokeSessionRequest",
    "RevokeAllSessionsRequest",
    "CreateSessionRequest",
    "SessionAnalytics",
]


class UserSession(BaseResponseSchema):
    """
    User session database model representation.
    
    Persistent session information stored in database.
    """

    user_id: UUID = Field(
        ...,
        description="User ID associated with session",
    )
    device_info: Union[Dict[str, str], None] = Field(
        default=None,
        description="Device information (user agent, platform, etc.)",
    )
    ip_address: Union[str, None] = Field(
        default=None,
        description="IP address from which session was created",
    )
    is_revoked: bool = Field(
        default=False,
        description="Whether session has been revoked",
    )
    expires_at: datetime = Field(
        ...,
        description="Session expiration timestamp (UTC)",
    )
    last_activity: datetime = Field(
        ...,
        description="Last activity timestamp (UTC)",
    )


class SessionInfo(BaseSchema):
    """
    Session information for display to users.
    
    Enhanced session details for frontend presentation.
    """

    session_id: UUID = Field(
        ...,
        description="Unique session identifier",
    )
    device_name: Union[str, None] = Field(
        default=None,
        description="Device name/description",
        examples=["iPhone 13", "Chrome on Windows"],
    )
    device_type: Union[str, None] = Field(
        default=None,
        description="Device category",
        examples=["mobile", "desktop", "tablet"],
    )
    browser: Union[str, None] = Field(
        default=None,
        description="Browser name and version",
        examples=["Chrome 120.0", "Safari 17.1"],
    )
    os: Union[str, None] = Field(
        default=None,
        description="Operating system",
        examples=["Windows 11", "macOS 14.0", "iOS 17.0"],
    )
    ip_address: Union[str, None] = Field(
        default=None,
        description="IP address (masked for privacy)",
        examples=["192.168.1.***"],
    )
    location: Union[str, None] = Field(
        default=None,
        description="Approximate location (city, country)",
        examples=["Mumbai, India", "New York, USA"],
    )
    is_current: bool = Field(
        default=False,
        description="Whether this is the current session",
    )
    created_at: datetime = Field(
        ...,
        description="Session creation timestamp",
    )
    last_activity: datetime = Field(
        ...,
        description="Last activity timestamp",
    )
    expires_at: datetime = Field(
        ...,
        description="Session expiration timestamp",
    )


class ActiveSessionsList(BaseSchema):
    """
    List of active user sessions.
    
    Response schema for retrieving all active sessions.
    """

    sessions: List[SessionInfo] = Field(
        ...,
        description="List of active sessions",
    )
    total_sessions: int = Field(
        ...,
        ge=0,
        description="Total number of active sessions",
    )
    current_session_id: Union[UUID, None] = Field(
        default=None,
        description="ID of the current session making the request",
    )


class RevokeSessionRequest(BaseCreateSchema):
    """
    Request to revoke a specific session.
    
    Used to terminate a single session by ID.
    """

    session_id: UUID = Field(
        ...,
        description="Session ID to revoke",
    )


class RevokeAllSessionsRequest(BaseCreateSchema):
    """
    Request to revoke all sessions.
    
    Option to keep current session active for security.
    """

    keep_current: bool = Field(
        default=True,
        description="Keep current session active after revoking others",
    )
    reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Reason for revoking all sessions (optional)",
        examples=["Security concern", "Lost device"],
    )


class CreateSessionRequest(BaseCreateSchema):
    """
    Request to create a new session.
    
    Used during login to track session information.
    """

    user_id: UUID = Field(
        ...,
        description="User ID for the session",
    )
    device_info: Union[Dict[str, str], None] = Field(
        default=None,
        description="Device information",
    )
    ip_address: Union[str, None] = Field(
        default=None,
        description="IP address",
    )
    user_agent: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="User agent string",
    )
    remember_me: bool = Field(
        default=False,
        description="Whether to extend session duration",
    )

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate IP address format."""
        if v is not None:
            v = v.strip()
            # Basic IP validation - can be enhanced
            if v and not (
                v.replace(".", "").replace(":", "").isalnum()
            ):
                raise ValueError("Invalid IP address format")
        return v


class SessionAnalytics(BaseResponseSchema):
    """
    Session analytics and statistics.
    
    Comprehensive session metrics for security and usage analysis.
    """

    user_id: UUID = Field(
        ...,
        description="User ID for the analytics",
    )
    total_sessions: int = Field(
        ...,
        ge=0,
        description="Total number of sessions (all time)",
    )
    active_sessions: int = Field(
        ...,
        ge=0,
        description="Currently active sessions",
    )
    sessions_last_30_days: int = Field(
        ...,
        ge=0,
        description="Sessions created in last 30 days",
    )
    device_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Session count by device type",
        examples=[{"desktop": 5, "mobile": 3, "tablet": 1}],
    )
    browser_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Session count by browser",
        examples=[{"Chrome": 6, "Safari": 2, "Firefox": 1}],
    )
    os_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Session count by operating system",
        examples=[{"Windows": 4, "iOS": 3, "macOS": 2}],
    )
    location_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Session count by location",
        examples=[{"Mumbai, India": 5, "New York, USA": 2}],
    )
    average_session_duration_minutes: Union[float, None] = Field(
        default=None,
        ge=0,
        description="Average session duration in minutes",
    )
    last_login_at: Union[datetime, None] = Field(
        default=None,
        description="Last login timestamp",
    )
    most_recent_locations: List[str] = Field(
        default_factory=list,
        description="Most recent login locations",
        examples=[["Mumbai, India", "New York, USA"]],
    )
    suspicious_activity_count: int = Field(
        default=0,
        ge=0,
        description="Count of flagged suspicious activities",
    )