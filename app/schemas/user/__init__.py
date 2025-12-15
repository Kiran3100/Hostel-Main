# --- File: app/schemas/user/__init__.py ---
"""
User schemas package.

Re-exports commonly used user-related schemas for convenient imports.

Example:
    from app.schemas.user import UserCreate, UserResponse, ProfileUpdate
"""

from __future__ import annotations

from app.schemas.user.user_base import (
    UserAddressUpdate,
    UserBase,
    UserCreate,
    UserEmergencyContactUpdate,
    UserUpdate,
)
from app.schemas.user.user_profile import (
    ContactInfoUpdate,
    NotificationPreferencesUpdate,
    ProfileImageUpdate,
    ProfileUpdate,
)
from app.schemas.user.user_response import (
    UserDetail,
    UserListItem,
    UserProfile,
    UserResponse,
    UserStats,
)
from app.schemas.user.user_session import (
    ActiveSessionsList,
    CreateSessionRequest,
    RevokeAllSessionsRequest,
    RevokeSessionRequest,
    SessionInfo,
    UserSession,
)

__all__ = [
    # Base
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserAddressUpdate",
    "UserEmergencyContactUpdate",
    # Profile
    "ProfileUpdate",
    "ProfileImageUpdate",
    "ContactInfoUpdate",
    "NotificationPreferencesUpdate",
    # Response
    "UserResponse",
    "UserDetail",
    "UserListItem",
    "UserProfile",
    "UserStats",
    # Session
    "UserSession",
    "SessionInfo",
    "ActiveSessionsList",
    "RevokeSessionRequest",
    "RevokeAllSessionsRequest",
    "CreateSessionRequest",
]