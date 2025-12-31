"""
Authentication service: login/logout and token issuance.

Handles multi-factor authentication flows, session management,
and comprehensive security logging.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.user import UserRepository
from app.repositories.auth import (
    UserSessionRepository,
    LoginAttemptRepository,
)
from app.schemas.auth.login import (
    LoginRequest,
    LoginResponse,
    UserLoginInfo,
    PhoneLoginRequest,
)
from app.schemas.auth.token import RefreshTokenRequest, RefreshTokenResponse
from app.models.user.user import User
from app.core.security.password_hasher import PasswordHasher
from app.core.security.jwt_handler import JWTManager

logger = logging.getLogger(__name__)


class AuthenticationService(BaseService[User, UserRepository]):
    """
    Service for authenticating users across roles (admin/supervisor/student/visitor).
    
    Features:
    - Email and phone-based authentication
    - Session management with device tracking
    - Comprehensive login attempt logging
    - Token lifecycle management
    - Security event monitoring
    """

    # Configuration constants - should be moved to settings
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    REFRESH_TOKEN_EXPIRE_DAYS = 30
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: UserSessionRepository,
        login_attempt_repository: LoginAttemptRepository,
        db_session: Session,
    ):
        super().__init__(user_repository, db_session)
        self.user_repository = user_repository
        self.session_repository = session_repository
        self.login_attempt_repository = login_attempt_repository
        self.password_hasher = PasswordHasher()
        self.jwt = JWTManager()

    # -------------------------------------------------------------------------
    # Email-based Authentication
    # -------------------------------------------------------------------------

    def login(
        self,
        request: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResult[LoginResponse]:
        """
        Authenticate user via email and password.
        
        Args:
            request: Login credentials
            ip_address: Client IP for security tracking
            user_agent: Client user agent for device identification
            
        Returns:
            ServiceResult with LoginResponse or error
        """
        try:
            # Sanitize email input
            email = self._sanitize_email(request.email)
            
            # Check for account lockout
            if self._is_account_locked(email, ip_address):
                logger.warning(
                    f"Login attempt on locked account: {email} from {ip_address}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Account temporarily locked due to multiple failed attempts",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Fetch user
            user = self.user_repository.find_by_email(email)
            if not user:
                self._record_failed_login(None, email, ip_address, user_agent)
                return self._invalid_credentials_error()

            # Verify account status
            if not user.is_active:
                self._record_failed_login(user.id, email, ip_address, user_agent)
                logger.warning(f"Login attempt on inactive account: {email}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.FORBIDDEN,
                        message="Account is inactive. Please contact support.",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Verify password
            if not self.password_hasher.verify(request.password, user.password_hash):
                self._record_failed_login(user.id, email, ip_address, user_agent)
                return self._invalid_credentials_error()

            # Check if MFA is required
            if user.mfa_enabled:
                # Return partial success indicating MFA required
                return ServiceResult.success(
                    data={
                        "requires_mfa": True,
                        "user_id": str(user.id),
                        "mfa_methods": ["totp"],  # Extensible for SMS, email OTP
                    },
                    message="MFA verification required",
                )

            # Generate tokens and create session
            login_response = self._create_authenticated_session(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # Record successful login
            self._record_successful_login(user.id, email, ip_address, user_agent)

            logger.info(f"Successful login for user: {email}")
            return ServiceResult.success(
                login_response,
                message="Login successful",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during login: {str(e)}")
            return self._handle_exception(e, "user login", request.email)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during login: {str(e)}")
            return self._handle_exception(e, "user login", request.email)

    # -------------------------------------------------------------------------
    # Phone-based Authentication
    # -------------------------------------------------------------------------

    def phone_login(
        self,
        request: PhoneLoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResult[LoginResponse]:
        """
        Authenticate user via phone number and password.
        
        Args:
            request: Phone login credentials
            ip_address: Client IP for security tracking
            user_agent: Client user agent for device identification
            
        Returns:
            ServiceResult with LoginResponse or error
        """
        try:
            # Sanitize phone input
            phone = self._sanitize_phone(request.phone)
            
            # Check for account lockout
            if self._is_account_locked(phone, ip_address):
                logger.warning(
                    f"Login attempt on locked phone: {phone} from {ip_address}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Account temporarily locked due to multiple failed attempts",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Fetch user
            user = self.user_repository.find_by_phone(phone)
            if not user:
                self._record_failed_login(None, phone, ip_address, user_agent)
                return self._invalid_credentials_error()

            # Verify account status
            if not user.is_active:
                self._record_failed_login(user.id, phone, ip_address, user_agent)
                logger.warning(f"Login attempt on inactive phone: {phone}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.FORBIDDEN,
                        message="Account is inactive. Please contact support.",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Verify password
            if not self.password_hasher.verify(request.password, user.password_hash):
                self._record_failed_login(user.id, phone, ip_address, user_agent)
                return self._invalid_credentials_error()

            # Check if MFA is required
            if user.mfa_enabled:
                return ServiceResult.success(
                    data={
                        "requires_mfa": True,
                        "user_id": str(user.id),
                        "mfa_methods": ["totp"],
                    },
                    message="MFA verification required",
                )

            # Generate tokens and create session
            login_response = self._create_authenticated_session(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # Record successful login
            self._record_successful_login(user.id, phone, ip_address, user_agent)

            logger.info(f"Successful phone login for user: {phone}")
            return ServiceResult.success(
                login_response,
                message="Login successful",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during phone login: {str(e)}")
            return self._handle_exception(e, "phone login", request.phone)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during phone login: {str(e)}")
            return self._handle_exception(e, "phone login", request.phone)

    # -------------------------------------------------------------------------
    # Token Management
    # -------------------------------------------------------------------------

    def refresh(
        self,
        request: RefreshTokenRequest,
    ) -> ServiceResult[RefreshTokenResponse]:
        """
        Refresh access token using valid refresh token.
        
        Args:
            request: Refresh token request
            
        Returns:
            ServiceResult with new tokens or error
        """
        try:
            # Decode and validate refresh token
            payload = self.jwt.decode_token(request.refresh_token)
            if not payload:
                logger.warning("Invalid refresh token attempted")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid or expired refresh token",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            user_id_str = payload.get("sub")
            token_type = payload.get("type")

            if not user_id_str or token_type != "refresh":
                logger.warning(f"Invalid token payload: {payload}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid refresh token",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Fetch user
            user = self.user_repository.get_by_id(UUID(user_id_str))
            if not user:
                logger.warning(f"Refresh token for non-existent user: {user_id_str}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid user",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            if not user.is_active:
                logger.warning(f"Refresh token for inactive user: {user_id_str}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.FORBIDDEN,
                        message="Account is inactive",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Generate new tokens
            access_token = self._create_access_token(user)
            refresh_token = self._create_refresh_token(user)

            logger.info(f"Token refreshed for user: {user.id}")
            return ServiceResult.success(
                RefreshTokenResponse(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_type="Bearer",
                    expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                ),
                message="Token refreshed successfully",
            )

        except ValueError as e:
            logger.error(f"Invalid UUID in refresh token: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.UNAUTHORIZED,
                    message="Invalid token format",
                    severity=ErrorSeverity.WARNING,
                )
            )
        except Exception as e:
            logger.error(f"Error during token refresh: {str(e)}")
            return self._handle_exception(e, "refresh access token")

    # -------------------------------------------------------------------------
    # Logout Operations
    # -------------------------------------------------------------------------

    def logout(
        self,
        user_id: UUID,
        logout_all_devices: bool = False,
    ) -> ServiceResult[bool]:
        """
        Logout user from current or all sessions.
        
        Args:
            user_id: User identifier
            logout_all_devices: If True, revoke all user sessions
            
        Returns:
            ServiceResult with success status
        """
        try:
            if logout_all_devices:
                revoked_count = self.session_repository.revoke_all_for_user(user_id)
                logger.info(
                    f"Revoked {revoked_count} sessions for user: {user_id}"
                )
                message = f"Logged out from all devices ({revoked_count} sessions)"
            else:
                self.session_repository.revoke_current_for_user(user_id)
                logger.info(f"Revoked current session for user: {user_id}")
                message = "Logged out successfully"

            self.db.commit()
            return ServiceResult.success(True, message=message)

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during logout: {str(e)}")
            return self._handle_exception(e, "logout", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during logout: {str(e)}")
            return self._handle_exception(e, "logout", user_id)

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _create_authenticated_session(
        self,
        user: User,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> LoginResponse:
        """
        Create authenticated session with tokens.
        
        Args:
            user: Authenticated user
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            LoginResponse with tokens and user info
        """
        # Generate tokens
        access_token = self._create_access_token(user)
        refresh_token = self._create_refresh_token(user)

        # Create session record
        session_expires_at = datetime.utcnow() + timedelta(
            days=self.REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        self.session_repository.create({
            "user_id": user.id,
            "device_info": user_agent or "Unknown",
            "ip_address": ip_address or "Unknown",
            "is_revoked": False,
            "expires_at": session_expires_at,
            "last_activity": datetime.utcnow(),
        })
        self.db.commit()

        # Build response
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserLoginInfo(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=user.user_role.value,
                is_email_verified=bool(user.email_verified_at),
                is_phone_verified=bool(user.phone_verified_at),
                profile_image_url=user.profile_image_url,
            ),
        )

    def _create_access_token(self, user: User) -> str:
        """Generate access token for user."""
        return self.jwt.create_access_token(
            subject=str(user.id),
            role=user.user_role.value,
            hostel_id=None,
            expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    def _create_refresh_token(self, user: User) -> str:
        """Generate refresh token for user."""
        return self.jwt.create_refresh_token(
            subject=str(user.id),
            expires_delta=timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
        )

    def _record_successful_login(
        self,
        user_id: UUID,
        identifier: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """Record successful login attempt."""
        try:
            self.login_attempt_repository.create({
                "user_id": user_id,
                "identifier": identifier,
                "ip_address": ip_address or "Unknown",
                "user_agent": user_agent or "Unknown",
                "success": True,
                "attempted_at": datetime.utcnow(),
            })
            self.db.flush()
        except Exception as e:
            logger.error(f"Failed to record successful login: {str(e)}")
            # Non-critical, continue

    def _record_failed_login(
        self,
        user_id: Optional[UUID],
        identifier: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """Record failed login attempt for security monitoring."""
        try:
            self.login_attempt_repository.create({
                "user_id": user_id,
                "identifier": identifier,
                "ip_address": ip_address or "Unknown",
                "user_agent": user_agent or "Unknown",
                "success": False,
                "attempted_at": datetime.utcnow(),
            })
            self.db.flush()
        except Exception as e:
            logger.error(f"Failed to record login attempt: {str(e)}")
            # Best-effort logging, don't fail authentication

    def _is_account_locked(
        self,
        identifier: str,
        ip_address: Optional[str],
    ) -> bool:
        """
        Check if account is locked due to failed login attempts.
        
        Args:
            identifier: Email or phone number
            ip_address: Client IP address
            
        Returns:
            True if account is locked
        """
        try:
            # Check failed attempts in lockout window
            lockout_since = datetime.utcnow() - timedelta(
                minutes=self.LOCKOUT_DURATION_MINUTES
            )
            
            failed_attempts = self.login_attempt_repository.count_failed_attempts(
                identifier=identifier,
                since=lockout_since,
            )
            
            return failed_attempts >= self.MAX_LOGIN_ATTEMPTS
            
        except Exception as e:
            logger.error(f"Error checking account lockout: {str(e)}")
            # Fail open - don't lock on error
            return False

    def _invalid_credentials_error(self) -> ServiceResult:
        """Return standard invalid credentials error."""
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.UNAUTHORIZED,
                message="Invalid email or password",
                severity=ErrorSeverity.WARNING,
            )
        )

    @staticmethod
    def _sanitize_email(email: str) -> str:
        """Sanitize and normalize email address."""
        return email.strip().lower() if email else ""

    @staticmethod
    def _sanitize_phone(phone: str) -> str:
        """Sanitize and normalize phone number."""
        # Remove all non-digit characters except leading +
        if not phone:
            return ""
        
        sanitized = "".join(c for c in phone if c.isdigit() or c == "+")
        return sanitized