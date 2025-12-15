# app/services/users/__init__.py
"""
User-facing services.

- UserService:
    Core CRUD, listing, and detail for users (core_user).

- UserProfileService:
    Profile/contact/image updates and simple document-like extensions.

- UserActivityService:
    Lightweight activity logging (logins, password changes, etc.).
"""

from .user_service import UserService
from .user_profile_service import UserProfileService
from .user_activity_service import UserActivityService

__all__ = [
    "UserService",
    "UserProfileService",
    "UserActivityService",
]