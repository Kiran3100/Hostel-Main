# --- File: app/schemas/auth/__init__.py ---
"""
Authentication schemas package.
Pydantic v2 compliant.

Re-exports commonly used auth-related schemas for convenient imports.

Example:
    from app.schemas.auth import LoginRequest, RegisterRequest, Token
"""

from app.schemas.auth.login import (
    LoginRequest,
    LoginResponse,
    PhoneLoginRequest,
    TokenData,
    UserLoginInfo,
)
from app.schemas.auth.otp import (
    OTPGenerateRequest,
    OTPResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    ResendOTPRequest,
)
from app.schemas.auth.password import (
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordStrengthCheck,
    PasswordStrengthResponse,
    PasswordValidator,
)
from app.schemas.auth.register import (
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    VerifyEmailRequest,
    VerifyPhoneRequest,
)
from app.schemas.auth.social_auth import (
    FacebookAuthRequest,
    GoogleAuthRequest,
    SocialAuthRequest,
    SocialAuthResponse,
    SocialProfileData,
    SocialUserInfo,
)
from app.schemas.auth.token import (
    LogoutRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RevokeTokenRequest,
    Token,
    TokenPayload,
    TokenValidationRequest,
    TokenValidationResponse,
)

__all__ = [
    # Login
    "LoginRequest",
    "LoginResponse",
    "PhoneLoginRequest",
    "TokenData",
    "UserLoginInfo",
    # Register
    "RegisterRequest",
    "RegisterResponse",
    "VerifyEmailRequest",
    "VerifyPhoneRequest",
    "ResendVerificationRequest",
    # Token
    "Token",
    "TokenPayload",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "TokenValidationRequest",
    "TokenValidationResponse",
    "RevokeTokenRequest",
    "LogoutRequest",
    # Password
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "PasswordChangeRequest",
    "PasswordChangeResponse",
    "PasswordStrengthCheck",
    "PasswordStrengthResponse",
    "PasswordValidator",
    # OTP
    "OTPGenerateRequest",
    "OTPVerifyRequest",
    "OTPResponse",
    "OTPVerifyResponse",
    "ResendOTPRequest",
    # Social Auth
    "SocialAuthRequest",
    "SocialAuthResponse",
    "GoogleAuthRequest",
    "FacebookAuthRequest",
    "SocialUserInfo",
    "SocialProfileData",
]