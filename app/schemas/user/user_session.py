# --- File: app/schemas/user/user_session.py ---
"""
User session schemas with enhanced tracking and management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
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
    device_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Device information (user agent, platform, etc.)",
    )
    ip_address: Optional[str] = Field(
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
    device_name: Optional[str] = Field(
        default=None,
        description="Device name/description",
        examples=["iPhone 13", "Chrome on Windows"],
    )
    device_type: Optional[str] = Field(
        default=None,
        description="Device category",
        examples=["mobile", "desktop", "tablet"],
    )
    browser: Optional[str] = Field(
        default=None,
        description="Browser name and version",
        examples=["Chrome 120.0", "Safari 17.1"],
    )
    os: Optional[str] = Field(
        default=None,
        description="Operating system",
        examples=["Windows 11", "macOS 14.0", "iOS 17.0"],
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="IP address (masked for privacy)",
        examples=["192.168.1.***"],
    )
    location: Optional[str] = Field(
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
    current_session_id: Optional[UUID] = Field(
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
    reason: Optional[str] = Field(
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
    device_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Device information",
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="IP address",
    )
    user_agent: Optional[str] = Field(
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
    def validate_ip_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate IP address format."""
        if v is not None:
            v = v.strip()
            # Basic IP validation - can be enhanced
            if v and not (
                v.replace(".", "").replace(":", "").isalnum()
            ):
                raise ValueError("Invalid IP address format")
        return v