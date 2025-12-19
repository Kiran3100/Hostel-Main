"""
Authentication Repositories Package

Exports all authentication-related repositories for convenient imports.

Example:
    from app.repositories.auth import AuthAggregateRepository
    
    auth_repo = AuthAggregateRepository(db)
    result = auth_repo.authenticate_user(...)
"""

from app.repositories.auth.user_session_repository import (
    UserSessionRepository,
    SessionTokenRepository,
    RefreshTokenRepository,
    LoginAttemptRepository,
)
from app.repositories.auth.otp_token_repository import (
    OTPTokenRepository,
    OTPTemplateRepository,
    OTPDeliveryRepository,
    OTPThrottlingRepository,
)
from app.repositories.auth.password_reset_repository import (
    PasswordResetRepository,
    PasswordHistoryRepository,
    PasswordPolicyRepository,
    PasswordAttemptRepository,
)
from app.repositories.auth.social_auth_token_repository import (
    SocialAuthProviderRepository,
    SocialAuthTokenRepository,
    SocialAuthProfileRepository,
    SocialAuthLinkRepository,
)
from app.repositories.auth.token_blacklist_repository import (
    BlacklistedTokenRepository,
    TokenRevocationRepository,
    SecurityEventRepository,
)
from app.repositories.auth.auth_aggregate_repository import (
    AuthAggregateRepository,
)

__all__ = [
    # Session Management
    "UserSessionRepository",
    "SessionTokenRepository",
    "RefreshTokenRepository",
    "LoginAttemptRepository",
    # OTP Management
    "OTPTokenRepository",
    "OTPTemplateRepository",
    "OTPDeliveryRepository",
    "OTPThrottlingRepository",
    # Password Management
    "PasswordResetRepository",
    "PasswordHistoryRepository",
    "PasswordPolicyRepository",
    "PasswordAttemptRepository",
    # Social Authentication
    "SocialAuthProviderRepository",
    "SocialAuthTokenRepository",
    "SocialAuthProfileRepository",
    "SocialAuthLinkRepository",
    # Token Blacklist & Security
    "BlacklistedTokenRepository",
    "TokenRevocationRepository",
    "SecurityEventRepository",
    # Aggregate Repository
    "AuthAggregateRepository",
]