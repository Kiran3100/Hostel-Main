"""
Authentication Service
Core authentication logic including login, logout, and registration.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.auth import (
    LoginAttemptRepository,
    AuthAggregateRepository,
)
from app.services.auth.token_service import TokenService
from app.services.auth.session_service import SessionService
from app.services.auth.password_service import PasswordService
from app.services.auth.security_monitoring_service import SecurityMonitoringService
from app.core.exceptions import (
    AuthenticationError,
    AccountLockoutError,
    InvalidCredentialsError,
)


class AuthenticationService:
    """
    Service for core authentication operations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.auth_repo = AuthAggregateRepository(db)
        self.login_attempt_repo = LoginAttemptRepository(db)
        
        # Initialize dependent services
        self.token_service = TokenService(db)
        self.session_service = SessionService(db)
        self.password_service = PasswordService(db)
        self.security_service = SecurityMonitoringService(db)

    # ==================== User Login ====================

    def login(
        self,
        identifier: str,
        password: str,
        identifier_type: str = "email",
        ip_address: str = "",
        user_agent: str = "",
        device_fingerprint: Optional[str] = None,
        is_remember_me: bool = False,
        country: Optional[str] = None,
        city: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Authenticate user and create session.
        
        Args:
            identifier: Email or phone number
            password: User password
            identifier_type: 'email' or 'phone'
            ip_address: Request IP address
            user_agent: Request user agent
            device_fingerprint: Device fingerprint hash
            is_remember_me: Extended session flag
            country: Country from geolocation
            city: City from geolocation
            timezone: User timezone
            
        Returns:
            Dictionary with authentication result and tokens
            
        Raises:
            AuthenticationError: If authentication fails
            AccountLockoutError: If account is locked
        """
        # Get user by identifier (this needs to be implemented in user repository)
        user = self._get_user_by_identifier(identifier, identifier_type)
        
        if not user:
            # Record failed attempt
            self._record_failed_login(
                user_id=None,
                identifier=identifier,
                identifier_type=identifier_type,
                reason="invalid_credentials",
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint
            )
            raise InvalidCredentialsError("Invalid credentials")
        
        # Check if account is locked
        is_locked, lockout_until = self.password_service.check_account_lockout(
            user_id=user.id,
            tenant_id=getattr(user, 'tenant_id', None)
        )
        
        if is_locked:
            self.security_service.record_security_event(
                event_type="login_attempt_while_locked",
                severity="high",
                description="Login attempt on locked account",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                risk_score=80
            )
            raise AccountLockoutError(
                f"Account is locked until {lockout_until}. "
                f"Please try again later or contact support."
            )
        
        # Verify password
        if not self.password_service.verify_password(password, user.password_hash):
            # Record failed attempt
            self._record_failed_login(
                user_id=user.id,
                identifier=identifier,
                identifier_type=identifier_type,
                reason="invalid_password",
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint
            )
            
            # Check if this should trigger lockout
            is_locked, lockout_until = self.password_service.check_account_lockout(
                user_id=user.id,
                tenant_id=getattr(user, 'tenant_id', None)
            )
            
            if is_locked:
                raise AccountLockoutError(
                    f"Too many failed login attempts. "
                    f"Account locked until {lockout_until}."
                )
            
            raise InvalidCredentialsError("Invalid credentials")
        
        # Check if user account is active
        if not user.is_active:
            self._record_failed_login(
                user_id=user.id,
                identifier=identifier,
                identifier_type=identifier_type,
                reason="account_inactive",
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint
            )
            raise AuthenticationError("Account is inactive")
        
        # Check if email is verified (if required)
        if hasattr(user, 'email_verified') and not user.email_verified:
            # You might want to allow login but require verification
            pass
        
        # Check password expiration
        expiration_info = self.password_service.check_password_expiration(
            user_id=user.id,
            tenant_id=getattr(user, 'tenant_id', None)
        )
        
        if expiration_info.get('is_expired'):
            # Force password change
            return {
                "requires_password_change": True,
                "reason": "Password has expired",
                "user_id": user.id
            }
        
        # Create session and generate tokens
        session_data = self.session_service.create_session(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            is_remember_me=is_remember_me,
            country=country,
            city=city,
            timezone=timezone
        )
        
        # Record successful login
        self._record_successful_login(
            user_id=user.id,
            identifier=identifier,
            identifier_type=identifier_type,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint
        )
        
        # Check for security warnings
        security_warnings = self._check_security_warnings(
            user_id=user.id,
            expiration_info=expiration_info
        )
        
        return {
            "user_id": user.id,
            "session_id": session_data["session_id"],
            "access_token": session_data["tokens"]["access_token"],
            "refresh_token": session_data["tokens"]["refresh_token"],
            "token_type": session_data["tokens"]["token_type"],
            "expires_in": session_data["tokens"]["expires_in"],
            "requires_password_change": False,
            "password_warning": expiration_info.get('should_warn', False),
            "days_until_password_expiration": expiration_info.get('days_until_expiration'),
            "security_warnings": security_warnings,
            "device_info": session_data["device_info"]
        }

    def _get_user_by_identifier(
        self,
        identifier: str,
        identifier_type: str
    ) -> Optional[Any]:
        """
        Get user by email or phone.
        This is a placeholder - implement based on your User model.
        """
        from app.models.user import User  # Adjust import based on your structure
        
        if identifier_type == "email":
            return self.db.query(User).filter(User.email == identifier).first()
        elif identifier_type == "phone":
            return self.db.query(User).filter(User.phone == identifier).first()
        
        return None

    def _record_failed_login(
        self,
        user_id: Optional[UUID],
        identifier: str,
        identifier_type: str,
        reason: str,
        ip_address: str,
        user_agent: str,
        device_fingerprint: Optional[str] = None
    ) -> None:
        """Record failed login attempt."""
        email = identifier if identifier_type == "email" else None
        phone = identifier if identifier_type == "phone" else None
        
        # Analyze risk
        risk_score = self.security_service.calculate_login_risk(
            user_id=user_id,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint
        )
        
        self.login_attempt_repo.record_attempt(
            user_id=user_id,
            email=email,
            phone=phone,
            is_successful=False,
            failure_reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            security_flags={"risk_score": risk_score}
        )
        
        # Record password attempt if user exists
        if user_id:
            self.password_service.record_password_attempt(
                user_id=user_id,
                is_successful=False,
                ip_address=ip_address,
                user_agent=user_agent,
                attempt_type="login"
            )

    def _record_successful_login(
        self,
        user_id: UUID,
        identifier: str,
        identifier_type: str,
        ip_address: str,
        user_agent: str,
        device_fingerprint: Optional[str] = None
    ) -> None:
        """Record successful login attempt."""
        email = identifier if identifier_type == "email" else None
        phone = identifier if identifier_type == "phone" else None
        
        self.login_attempt_repo.record_attempt(
            user_id=user_id,
            email=email,
            phone=phone,
            is_successful=True,
            failure_reason=None,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint
        )
        
        self.password_service.record_password_attempt(
            user_id=user_id,
            is_successful=True,
            ip_address=ip_address,
            user_agent=user_agent,
            attempt_type="login"
        )

    def _check_security_warnings(
        self,
        user_id: UUID,
        expiration_info: Dict[str, Any]
    ) -> list:
        """Check for security warnings to display to user."""
        warnings = []
        
        # Password expiration warning
        if expiration_info.get('should_warn'):
            days_left = expiration_info.get('days_until_expiration', 0)
            warnings.append({
                "type": "password_expiration",
                "message": f"Your password will expire in {days_left} days",
                "severity": "medium"
            })
        
        # Check for suspicious sessions
        suspicious_sessions = self.session_service.get_suspicious_sessions(user_id)
        if suspicious_sessions:
            warnings.append({
                "type": "suspicious_activity",
                "message": "Suspicious activity detected on your account",
                "severity": "high",
                "details": suspicious_sessions
            })
        
        return warnings

    # ==================== User Logout ====================

    def logout(
        self,
        session_id: str,
        user_id: UUID,
        ip_address: str = "",
        user_agent: str = ""
    ) -> bool:
        """
        Logout user and terminate session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Success status
        """
        success = self.session_service.terminate_session(
            session_id=session_id,
            reason="User logout"
        )
        
        if success:
            self.security_service.record_security_event(
                event_type="user_logout",
                severity="low",
                description="User logged out",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        return success

    def logout_all_devices(
        self,
        user_id: UUID,
        current_session_id: Optional[str] = None,
        ip_address: str = "",
        user_agent: str = ""
    ) -> int:
        """
        Logout user from all devices.
        
        Args:
            user_id: User identifier
            current_session_id: Keep this session active
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Number of sessions terminated
        """
        count = self.session_service.terminate_all_sessions(
            user_id=user_id,
            except_session_id=current_session_id,
            reason="User requested logout from all devices"
        )
        
        if count > 0:
            self.security_service.record_security_event(
                event_type="logout_all_devices",
                severity="medium",
                description=f"User logged out from {count} devices",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        return count

    # ==================== Token Refresh ====================

    def refresh_access_token(
        self,
        refresh_token: str,
        ip_address: str = "",
        user_agent: str = ""
    ) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Current refresh token
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            New token pair
            
        Raises:
            AuthenticationError: If refresh fails
        """
        try:
            tokens = self.token_service.refresh_tokens(refresh_token)
            
            # Get user_id from token for logging
            token_info = self.token_service.get_token_info(refresh_token)
            user_id = token_info.get('user_id')
            
            if user_id:
                self.security_service.record_security_event(
                    event_type="token_refreshed",
                    severity="low",
                    description="Access token refreshed",
                    user_id=UUID(user_id),
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            
            return tokens
            
        except Exception as e:
            raise AuthenticationError(f"Token refresh failed: {str(e)}")

    # ==================== Session Validation ====================

    def validate_session(
        self,
        session_id: str,
        update_activity: bool = True
    ) -> Dict[str, Any]:
        """
        Validate session and optionally update activity.
        
        Args:
            session_id: Session identifier
            update_activity: Whether to update last activity
            
        Returns:
            Session information
            
        Raises:
            AuthenticationError: If session is invalid
        """
        try:
            return self.session_service.validate_session(
                session_id=session_id,
                update_activity=update_activity
            )
        except Exception as e:
            raise AuthenticationError(f"Session validation failed: {str(e)}")

    def validate_access_token(self, token: str) -> Dict[str, Any]:
        """
        Validate access token.
        
        Args:
            token: Access token
            
        Returns:
            Token payload
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            return self.token_service.validate_access_token(token)
        except Exception as e:
            raise AuthenticationError(f"Token validation failed: {str(e)}")

    # ==================== User Registration ====================

    def register_user(
        self,
        email: str,
        password: str,
        ip_address: str,
        user_agent: str,
        additional_data: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Register new user account.
        
        Args:
            email: User email
            password: User password
            ip_address: Request IP address
            user_agent: Request user agent
            additional_data: Additional user data
            tenant_id: Tenant ID
            
        Returns:
            Dictionary with user and initial session
            
        Raises:
            AuthenticationError: If registration fails
        """
        # Validate password against policy
        is_valid, errors = self.password_service.validate_password(
            password=password,
            tenant_id=tenant_id
        )
        
        if not is_valid:
            raise AuthenticationError("; ".join(errors))
        
        # Hash password
        password_hash = self.password_service.hash_password(password)
        
        # Create user (this needs to be implemented based on your User model)
        user = self._create_user_account(
            email=email,
            password_hash=password_hash,
            additional_data=additional_data
        )
        
        # Add initial password to history
        self.password_service.password_history_repo.add_to_history(
            user_id=user.id,
            password_hash=password_hash,
            change_reason="Initial registration",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Record security event
        self.security_service.record_security_event(
            event_type="user_registered",
            severity="low",
            description="New user account created",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            "user_id": user.id,
            "email": user.email,
            "requires_email_verification": True
        }

    def _create_user_account(
        self,
        email: str,
        password_hash: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create user account.
        This is a placeholder - implement based on your User model.
        """
        from app.models.user import User  # Adjust import
        
        user = User(
            email=email,
            password_hash=password_hash,
            is_active=True,
            email_verified=False,
            **(additional_data or {})
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user

    # ==================== Account Status ====================

    def check_account_status(self, user_id: UUID) -> Dict[str, Any]:
        """
        Check comprehensive account status.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with account status information
        """
        # Check lockout status
        is_locked, lockout_until = self.password_service.check_account_lockout(user_id)
        
        # Check password expiration
        expiration_info = self.password_service.check_password_expiration(user_id)
        
        # Get active sessions
        active_sessions = len(self.session_service.get_active_sessions(user_id))
        
        # Get recent security events
        recent_events = self.security_service.get_recent_security_events(
            user_id=user_id,
            hours=24
        )
        
        return {
            "is_locked": is_locked,
            "lockout_until": lockout_until,
            "password_expired": expiration_info.get('is_expired', False),
            "password_warning": expiration_info.get('should_warn', False),
            "days_until_password_expiration": expiration_info.get('days_until_expiration'),
            "active_sessions_count": active_sessions,
            "recent_security_events": len(recent_events),
            "has_high_risk_events": any(
                event.get('risk_score', 0) >= 70 for event in recent_events
            )
        }

    # ==================== Statistics ====================

    def get_authentication_statistics(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive authentication statistics.
        
        Args:
            user_id: User identifier
            days: Number of days to analyze
            
        Returns:
            Dictionary with authentication statistics
        """
        return {
            "login_attempts": self.login_attempt_repo.get_attempt_statistics(user_id, days),
            "password_stats": self.password_service.get_password_statistics(user_id, days),
            "session_stats": self.session_service.get_session_statistics(user_id),
            "security_stats": self.security_service.get_user_security_summary(user_id, days)
        }