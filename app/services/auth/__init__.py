"""
Authentication Services Package

Exports all authentication-related services for convenient imports.

Example:
    from app.services.auth import AuthenticationService, TokenService
    
    auth_service = AuthenticationService(db)
    result = auth_service.login(...)
"""

from app.services.auth.authentication_service import AuthenticationService
from app.services.auth.token_service import TokenService
from app.services.auth.session_service import SessionService
from app.services.auth.password_service import PasswordService
from app.services.auth.otp_service import OTPService
from app.services.auth.mfa_service import MFAService
from app.services.auth.social_auth_service import SocialAuthService
from app.services.auth.security_monitoring_service import SecurityMonitoringService
from app.services.auth.token_blacklist_service import TokenBlacklistService

__all__ = [
    # Core Authentication
    "AuthenticationService",
    
    # Token Management
    "TokenService",
    "TokenBlacklistService",
    
    # Session Management
    "SessionService",
    
    # Password Management
    "PasswordService",
    
    # OTP & MFA
    "OTPService",
    "MFAService",
    
    # Social Authentication
    "SocialAuthService",
    
    # Security
    "SecurityMonitoringService",
]