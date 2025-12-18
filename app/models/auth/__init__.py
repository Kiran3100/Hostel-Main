# --- File: app/models/auth/__init__.py ---
"""
Authentication models package.

Exports all authentication-related SQLAlchemy models for convenient imports.

Example:
    from app.models.auth import UserSession, OTPToken, PasswordReset
"""

from app.models.auth.otp_token import (
    OTPDelivery,
    OTPTemplate,
    OTPThrottling,
    OTPToken,
)
from app.models.auth.password_reset import (
    PasswordAttempt,
    PasswordHistory,
    PasswordPolicy,
    PasswordReset,
)
from app.models.auth.social_auth_token import (
    SocialAuthLink,
    SocialAuthProfile,
    SocialAuthProvider,
    SocialAuthToken,
)
from app.models.auth.token_blacklist import (
    BlacklistedToken,
    SecurityEvent,
    TokenRevocation,
)
from app.models.auth.user_session import (
    LoginAttempt,
    RefreshToken,
    SessionToken,
    UserSession,
)

__all__ = [
    # User Session
    "UserSession",
    "SessionToken",
    "RefreshToken",
    "LoginAttempt",
    # OTP
    "OTPToken",
    "OTPTemplate",
    "OTPDelivery",
    "OTPThrottling",
    # Password Reset
    "PasswordReset",
    "PasswordHistory",
    "PasswordPolicy",
    "PasswordAttempt",
    # Social Auth
    "SocialAuthProvider",
    "SocialAuthToken",
    "SocialAuthProfile",
    "SocialAuthLink",
    # Token Blacklist
    "BlacklistedToken",
    "TokenRevocation",
    "SecurityEvent",
]