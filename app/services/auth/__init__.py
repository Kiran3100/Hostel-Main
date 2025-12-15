# app/services/auth/__init__.py
"""
Authentication and authorization services.

- AuthService: login/logout, token issuance, refresh.
- RegistrationService: user registration (visitor-facing signup).
- PasswordService: password change and strength checks.
- OTPService: OTP generation/verification (stubbed integration point).
- SocialAuthService: Google/Facebook OAuth (stubbed).
- SessionService: user session tracking (stubbed, e.g. Redis-based).
- RBACService: role-based permission matrix helpers (stubbed).
- ContextService: per-admin active hostel context (stubbed).
"""

from .auth_service import AuthService
from .registration_service import RegistrationService
from .password_service import PasswordService
from .otp_service import OTPService
from .social_auth_service import SocialAuthService
from .session_service import SessionService
from .rbac_service import RBACService
from .context_service import ContextService

__all__ = [
    "AuthService",
    "RegistrationService",
    "PasswordService",
    "OTPService",
    "SocialAuthService",
    "SessionService",
    "RBACService",
    "ContextService",
]