"""
Authentication and authorization service layer.

Comprehensive auth services providing:
- Multi-factor authentication (password, OTP, TOTP)
- Social OAuth integration (Google, Facebook)
- Session management and tracking
- Token lifecycle management
- Password security and policies
- Security monitoring and threat detection
- Token revocation and blacklisting

Version: 2.0.0
Last Updated: 2024
"""

from app.services.auth.authentication_service import AuthenticationService
from app.services.auth.session_service import SessionService
from app.services.auth.otp_service import OTPService
from app.services.auth.mfa_service import MFAService
from app.services.auth.password_service import PasswordService
from app.services.auth.token_service import TokenService
from app.services.auth.token_blacklist_service import TokenBlacklistService
from app.services.auth.social_auth_service import SocialAuthService
from app.services.auth.security_monitoring_service import SecurityMonitoringService

__all__ = [
    "AuthenticationService",
    "SessionService",
    "OTPService",
    "MFAService",
    "PasswordService",
    "TokenService",
    "TokenBlacklistService",
    "SocialAuthService",
    "SecurityMonitoringService",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System Team"