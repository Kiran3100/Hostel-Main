"""
Admin authentication and session management service.

Handles login, token issuance/rotation, session lifecycle,
and security event tracking.
"""

from typing import Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.admin import AdminUserRepository
from app.models.admin import AdminUser, AdminSession
from app.schemas.auth.login import LoginRequest, LoginResponse, UserLoginInfo
from app.schemas.auth.token import Token, RefreshTokenRequest, RefreshTokenResponse
from app.core.security.password_hasher import PasswordHasher
from app.core.security.jwt_handler import JWTManager
from app.models.base.enums import UserRole


class AdminAuthenticationService(BaseService[AdminUser, AdminUserRepository]):
    """
    Service handling admin authentication operations.
    
    Responsibilities:
    - Login authentication
    - Token issuance and rotation
    - Session lifecycle management
    - Security event tracking
    """
    
    # Token expiry configuration
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    REFRESH_TOKEN_EXPIRE_DAYS = 30
    
    # Valid admin roles
    ADMIN_ROLES = frozenset([UserRole.ADMIN, UserRole.SUPER_ADMIN])
    
    def __init__(
        self,
        repository: AdminUserRepository,
        db_session: Session,
    ):
        """
        Initialize authentication service.
        
        Args:
            repository: Admin user repository
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self.password_hasher = PasswordHasher()
        self.jwt_manager = JWTManager()
    
    # =========================================================================
    # Authentication
    # =========================================================================
    
    def login(
        self,
        request: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResult[LoginResponse]:
        """
        Authenticate admin user and issue tokens.
        
        Process:
        1. Locate admin by email
        2. Verify password
        3. Check account status
        4. Issue access and refresh tokens
        5. Create session record
        
        Args:
            request: Login request with credentials
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            ServiceResult containing login response or error
        """
        try:
            # Authenticate user
            admin = self._authenticate_admin(request.email, request.password)
            if isinstance(admin, ServiceResult):
                # Authentication failed
                if ip_address or user_agent:
                    # Record failed login attempt
                    self._record_failed_login(request.email, ip_address, user_agent)
                return admin
            
            # Check account status
            status_check = self._check_account_status(admin)
            if not status_check.is_success:
                return status_check
            
            # Generate tokens
            access_token, refresh_token = self._generate_token_pair(admin)
            
            # Create session
            self._create_admin_session(
                admin.id,
                user_agent,
                ip_address,
                bool(request.remember_me),
            )
            
            self.db.commit()
            
            # Build response
            response = self._build_login_response(
                admin,
                access_token,
                refresh_token,
            )
            
            self._logger.info(
                "Admin login successful",
                extra={
                    "admin_id": str(admin.id),
                    "email": request.email,
                    "ip_address": ip_address,
                },
            )
            
            return ServiceResult.success(response, message="Login successful")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "admin login")
    
    def refresh(
        self,
        request: RefreshTokenRequest,
    ) -> ServiceResult[RefreshTokenResponse]:
        """
        Rotate tokens using a valid refresh token.
        
        Args:
            request: Refresh token request
            
        Returns:
            ServiceResult containing new tokens or error
        """
        try:
            # Decode and validate refresh token
            payload = self._decode_refresh_token(request.refresh_token)
            if isinstance(payload, ServiceResult):
                return payload
            
            user_id = payload.get("sub")
            if not user_id:
                return self._token_error("Invalid refresh token: missing subject")
            
            # Fetch admin
            admin = self.repository.get_admin_by_user_id(UUID(user_id))
            if not admin:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Admin not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check account status
            status_check = self._check_account_status(admin)
            if not status_check.is_success:
                return status_check
            
            # Generate new token pair
            access_token, refresh_token = self._generate_token_pair(admin)
            
            response = RefreshTokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="Bearer",
                expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )
            
            self._logger.info(
                "Tokens refreshed successfully",
                extra={"admin_id": str(admin.id)},
            )
            
            return ServiceResult.success(response, message="Token refreshed")
            
        except Exception as e:
            return self._handle_exception(e, "refresh token")
    
    def logout(
        self,
        admin_id: UUID,
        revoke_all_devices: bool = False,
    ) -> ServiceResult[bool]:
        """
        End session(s) for admin.
        
        Args:
            admin_id: Admin user ID
            revoke_all_devices: If True, revoke all sessions; otherwise, current only
            
        Returns:
            ServiceResult indicating success or error
        """
        try:
            if revoke_all_devices:
                self.repository.revoke_all_sessions(admin_id)
                message = "All sessions revoked"
            else:
                self.repository.revoke_current_session(admin_id)
                message = "Current session revoked"
            
            self.db.commit()
            
            self._logger.info(
                f"Admin logout: {message}",
                extra={
                    "admin_id": str(admin_id),
                    "revoke_all": revoke_all_devices,
                },
            )
            
            return ServiceResult.success(True, message=message)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "logout admin", admin_id)
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    def get_active_sessions(
        self,
        admin_id: UUID,
    ) -> ServiceResult[list[AdminSession]]:
        """
        Get all active sessions for an admin.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult containing list of active sessions
        """
        try:
            sessions = self.repository.get_active_sessions(admin_id)
            
            return ServiceResult.success(
                sessions,
                message="Active sessions retrieved",
                metadata={"count": len(sessions)},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get active sessions", admin_id)
    
    def revoke_session(
        self,
        admin_id: UUID,
        session_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Revoke a specific session.
        
        Args:
            admin_id: Admin user ID
            session_id: Session ID to revoke
            
        Returns:
            ServiceResult indicating success or error
        """
        try:
            self.repository.revoke_session(admin_id, session_id)
            self.db.commit()
            
            self._logger.info(
                "Session revoked",
                extra={
                    "admin_id": str(admin_id),
                    "session_id": str(session_id),
                },
            )
            
            return ServiceResult.success(True, message="Session revoked")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "revoke session", admin_id)
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _authenticate_admin(
        self,
        email: str,
        password: str,
    ) -> AdminUser | ServiceResult:
        """
        Authenticate admin by email and password.
        
        Returns:
            AdminUser if successful, ServiceResult error otherwise
        """
        # Locate admin
        admin = self.repository.get_admin_by_email(email)
        if not admin or admin.user.role not in self.ADMIN_ROLES:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.UNAUTHORIZED,
                    message="Invalid credentials",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Verify password
        if not self.password_hasher.verify(password, admin.user.password_hash):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.UNAUTHORIZED,
                    message="Invalid credentials",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return admin
    
    def _check_account_status(self, admin: AdminUser) -> ServiceResult[None]:
        """Check if admin account is active and usable."""
        if admin.status != "active" or not admin.user.is_active:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.FORBIDDEN,
                    message="Account is not active",
                    severity=ErrorSeverity.WARNING,
                )
            )
        return ServiceResult.success(None)
    
    def _generate_token_pair(self, admin: AdminUser) -> Tuple[str, str]:
        """Generate access and refresh token pair."""
        access_token = self.jwt_manager.create_access_token(
            subject=str(admin.user_id),
            role=admin.user.role.value,
            hostel_id=None,
            expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        
        refresh_token = self.jwt_manager.create_refresh_token(
            subject=str(admin.user_id),
            expires_delta=timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        
        return access_token, refresh_token
    
    def _create_admin_session(
        self,
        admin_id: UUID,
        device_info: Optional[str],
        ip_address: Optional[str],
        remember_me: bool,
    ) -> None:
        """Create admin session record."""
        self.repository.create_session(
            admin_id=admin_id,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            remember_me=remember_me,
        )
    
    def _build_login_response(
        self,
        admin: AdminUser,
        access_token: str,
        refresh_token: str,
    ) -> LoginResponse:
        """Build login response object."""
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserLoginInfo(
                id=str(admin.user_id),
                email=admin.user.email,
                full_name=admin.user.full_name,
                role=admin.user.role.value,
                is_email_verified=bool(admin.user.email_verified_at),
                is_phone_verified=bool(admin.user.phone_verified_at),
                profile_image_url=admin.user.profile_image_url,
            ),
        )
    
    def _decode_refresh_token(self, token: str) -> dict | ServiceResult:
        """
        Decode refresh token.
        
        Returns:
            Payload dict if successful, ServiceResult error otherwise
        """
        try:
            payload = self.jwt_manager.decode_token(token)
            return payload
        except Exception as e:
            self._logger.warning(
                f"Failed to decode refresh token: {str(e)}",
                exc_info=True,
            )
            return self._token_error("Invalid refresh token")
    
    def _token_error(self, message: str) -> ServiceResult:
        """Create token validation error."""
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.UNAUTHORIZED,
                message=message,
                severity=ErrorSeverity.WARNING,
            )
        )
    
    def _record_failed_login(
        self,
        email: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """Record failed login attempt for security tracking."""
        try:
            admin = self.repository.get_admin_by_email(email)
            if admin:
                self.repository.record_failed_login(
                    admin.user_id,
                    ip_address,
                    user_agent,
                )
                self.db.commit()
        except Exception as e:
            self._logger.error(
                f"Failed to record login attempt: {str(e)}",
                exc_info=True,
            )