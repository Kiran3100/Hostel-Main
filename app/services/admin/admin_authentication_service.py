"""
Admin Authentication Service

Handles authentication, session management, security monitoring,
and access control for admin users.
"""

from typing import Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
import secrets
import hashlib
from sqlalchemy.orm import Session

from app.models.admin.admin_user import AdminUser, AdminSession
from app.repositories.admin.admin_user_repository import AdminUserRepository
from app.core.exceptions import (
    AuthenticationError,
    SecurityError,
    ValidationError
)
from app.core.security import (
    verify_password,
    generate_session_token,
    generate_refresh_token,
    verify_2fa_token
)


class AdminAuthenticationService:
    """
    Authentication and session management with:
    - Login/logout with security checks
    - Multi-factor authentication
    - Session management
    - Security monitoring
    - Password management
    """

    def __init__(self, db: Session):
        self.db = db
        self.admin_repo = AdminUserRepository(db)
        
        # Security configuration
        self.session_duration_hours = 8
        self.refresh_token_duration_days = 30
        self.max_failed_attempts = 5
        self.lockout_duration_minutes = 30
        self.max_concurrent_sessions = 3

    # ==================== AUTHENTICATION ====================

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str,
        user_agent: str,
        device_info: Optional[Dict] = None,
        totp_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Authenticate admin and create session.
        
        Args:
            email: Admin email
            password: Password
            ip_address: Client IP
            user_agent: User agent string
            device_info: Optional device information
            totp_code: 2FA TOTP code if enabled
            
        Returns:
            Dict with session token, refresh token, and admin info
        """
        # Find admin by email
        admin = await self.admin_repo.find_by_email(email)
        if not admin:
            raise AuthenticationError("Invalid email or password")

        # Check account status
        if not admin.can_login:
            raise SecurityError(
                f"Account {'suspended' if admin.is_suspended else 'terminated'}"
            )

        # Verify password
        if not verify_password(password, admin.user.password_hash):
            await self._record_failed_attempt(admin.id, ip_address)
            raise AuthenticationError("Invalid email or password")

        # Check 2FA if enabled
        if admin.two_factor_enabled:
            if not totp_code:
                return {
                    'requires_2fa': True,
                    'admin_id': str(admin.id)
                }
            
            if not self._verify_2fa(admin, totp_code):
                await self._record_failed_attempt(admin.id, ip_address)
                raise AuthenticationError("Invalid 2FA code")

        # Check concurrent sessions
        await self._enforce_session_limit(admin.id)

        # Create session
        session = await self.admin_repo.track_login(
            admin_id=admin.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info or {}
        )

        # Generate tokens
        access_token = self._generate_access_token(admin.id, session.id)
        refresh_token = self._generate_refresh_token(admin.id, session.id)

        await self.db.commit()

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': self.session_duration_hours * 3600,
            'admin': self._serialize_admin(admin),
            'session_id': str(session.id)
        }

    async def logout(
        self,
        session_id: UUID,
        admin_id: UUID
    ) -> bool:
        """Logout admin and end session."""
        session = await self.db.get(AdminSession, session_id)
        if not session or session.admin_id != admin_id:
            return False

        await self.admin_repo.end_session(session_id, 'logout')
        await self.db.commit()
        return True

    async def logout_all_sessions(
        self,
        admin_id: UUID,
        except_session_id: Optional[UUID] = None
    ) -> int:
        """Logout admin from all sessions except optionally one."""
        sessions = await self.admin_repo.get_active_sessions(admin_id)
        
        count = 0
        for session in sessions:
            if except_session_id and session.id == except_session_id:
                continue
            
            await self.admin_repo.end_session(session.id, 'logout_all')
            count += 1

        await self.db.commit()
        return count

    # ==================== SESSION MANAGEMENT ====================

    async def validate_session(
        self,
        session_id: UUID,
        admin_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate session is active and valid.
        
        Returns:
            (is_valid, error_message)
        """
        session = await self.db.get(AdminSession, session_id)
        
        if not session:
            return False, "Session not found"
        
        if session.admin_id != admin_id:
            return False, "Session mismatch"
        
        if not session.is_active:
            return False, "Session ended"
        
        if session.is_expired:
            await self.admin_repo.end_session(session_id, 'expired')
            await self.db.commit()
            return False, "Session expired"
        
        # Update last activity
        session.last_activity_at = datetime.utcnow()
        await self.db.commit()
        
        return True, None

    async def refresh_session(
        self,
        refresh_token: str,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        # Verify refresh token
        token_data = self._verify_refresh_token(refresh_token)
        
        if not token_data or token_data['admin_id'] != str(admin_id):
            raise AuthenticationError("Invalid refresh token")
        
        session_id = UUID(token_data['session_id'])
        
        # Validate session still active
        is_valid, error = await self.validate_session(session_id, admin_id)
        if not is_valid:
            raise AuthenticationError(f"Session invalid: {error}")
        
        # Generate new access token
        access_token = self._generate_access_token(admin_id, session_id)
        
        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': self.session_duration_hours * 3600
        }

    async def get_active_sessions(
        self,
        admin_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get all active sessions for admin."""
        sessions = await self.admin_repo.get_active_sessions(admin_id)
        
        return [
            {
                'session_id': str(s.id),
                'started_at': s.started_at,
                'last_activity': s.last_activity_at,
                'ip_address': s.ip_address,
                'device_type': s.device_type,
                'is_current': False  # Would be set by comparing with current session
            }
            for s in sessions
        ]

    async def _enforce_session_limit(self, admin_id: UUID) -> None:
        """Enforce maximum concurrent sessions."""
        sessions = await self.admin_repo.get_active_sessions(admin_id)
        
        if len(sessions) >= self.max_concurrent_sessions:
            # End oldest session
            oldest = min(sessions, key=lambda s: s.started_at)
            await self.admin_repo.end_session(
                oldest.id,
                'max_sessions_reached'
            )

    # ==================== TWO-FACTOR AUTHENTICATION ====================

    async def enable_2fa(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Enable 2FA for admin and return setup info."""
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            raise ValidationError(f"Admin {admin_id} not found")

        if admin.two_factor_enabled:
            raise ValidationError("2FA already enabled")

        # Generate TOTP secret
        secret = self._generate_totp_secret()
        
        # Store encrypted secret
        admin.two_factor_secret = self._encrypt_secret(secret)
        admin.two_factor_enabled = True
        
        await self.db.commit()

        # Return QR code data
        return {
            'secret': secret,
            'qr_code_url': self._generate_qr_code_url(admin.user.email, secret),
            'backup_codes': self._generate_backup_codes(admin_id)
        }

    async def disable_2fa(
        self,
        admin_id: UUID,
        password: str
    ) -> bool:
        """Disable 2FA after password verification."""
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            return False

        # Verify password
        if not verify_password(password, admin.user.password_hash):
            raise AuthenticationError("Invalid password")

        admin.two_factor_enabled = False
        admin.two_factor_secret = None
        
        await self.db.commit()
        return True

    async def verify_2fa_code(
        self,
        admin_id: UUID,
        totp_code: str
    ) -> bool:
        """Verify 2FA TOTP code."""
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin or not admin.two_factor_enabled:
            return False

        return self._verify_2fa(admin, totp_code)

    def _verify_2fa(self, admin: AdminUser, totp_code: str) -> bool:
        """Internal 2FA verification."""
        if not admin.two_factor_secret:
            return False

        secret = self._decrypt_secret(admin.two_factor_secret)
        return verify_2fa_token(secret, totp_code)

    # ==================== SECURITY MONITORING ====================

    async def _record_failed_attempt(
        self,
        admin_id: UUID,
        ip_address: str
    ) -> None:
        """Record failed login attempt and check for lockout."""
        # Implementation would track failed attempts
        # and trigger lockout if threshold exceeded
        pass

    async def check_suspicious_activity(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Check for suspicious login patterns."""
        sessions = await self.admin_repo._get_recent_sessions(admin_id, hours=24)
        
        # Analyze patterns
        unique_ips = len(set(s.ip_address for s in sessions if s.ip_address))
        suspicious_flags = []
        
        if unique_ips > 5:
            suspicious_flags.append('multiple_ips')
        
        if len(sessions) > 20:
            suspicious_flags.append('high_frequency')
        
        return {
            'is_suspicious': len(suspicious_flags) > 0,
            'flags': suspicious_flags,
            'unique_ips': unique_ips,
            'session_count': len(sessions)
        }

    # ==================== PASSWORD MANAGEMENT ====================

    async def change_password(
        self,
        admin_id: UUID,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change admin password with validation."""
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            return False

        # Verify current password
        if not verify_password(current_password, admin.user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        # Validate new password strength
        self._validate_password_strength(new_password)

        # Update password
        from app.core.security import hash_password
        admin.user.password_hash = hash_password(new_password)
        admin.user.password_changed_at = datetime.utcnow()

        # End all sessions except current
        # This would require session_id parameter
        
        await self.db.commit()
        return True

    async def reset_password(
        self,
        admin_id: UUID,
        new_password: str,
        reset_by_id: UUID
    ) -> bool:
        """Admin password reset by another admin."""
        # Verify resetting admin has permission
        resetter = await self.admin_repo.find_by_id(reset_by_id)
        if not resetter or not resetter.can_manage_admins:
            raise AuthorizationError("Insufficient permissions")

        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            return False

        # Validate new password
        self._validate_password_strength(new_password)

        # Update password
        from app.core.security import hash_password
        admin.user.password_hash = hash_password(new_password)
        admin.user.password_changed_at = datetime.utcnow()

        # End all admin's sessions
        await self.admin_repo.terminate_all_sessions(admin_id, 'password_reset')

        await self.db.commit()
        return True

    def _validate_password_strength(self, password: str) -> None:
        """Validate password meets security requirements."""
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")
        
        if not any(c.isupper() for c in password):
            raise ValidationError("Password must contain uppercase letter")
        
        if not any(c.islower() for c in password):
            raise ValidationError("Password must contain lowercase letter")
        
        if not any(c.isdigit() for c in password):
            raise ValidationError("Password must contain number")

    # ==================== TOKEN GENERATION ====================

    def _generate_access_token(
        self,
        admin_id: UUID,
        session_id: UUID
    ) -> str:
        """Generate JWT access token."""
        from jose import jwt
        
        payload = {
            'admin_id': str(admin_id),
            'session_id': str(session_id),
            'type': 'access',
            'exp': datetime.utcnow() + timedelta(hours=self.session_duration_hours),
            'iat': datetime.utcnow()
        }
        
        # Would use actual SECRET_KEY from config
        return jwt.encode(payload, 'SECRET_KEY', algorithm='HS256')

    def _generate_refresh_token(
        self,
        admin_id: UUID,
        session_id: UUID
    ) -> str:
        """Generate refresh token."""
        from jose import jwt
        
        payload = {
            'admin_id': str(admin_id),
            'session_id': str(session_id),
            'type': 'refresh',
            'exp': datetime.utcnow() + timedelta(days=self.refresh_token_duration_days),
            'iat': datetime.utcnow()
        }
        
        return jwt.encode(payload, 'SECRET_KEY', algorithm='HS256')

    def _verify_refresh_token(self, token: str) -> Optional[Dict]:
        """Verify and decode refresh token."""
        from jose import jwt, JWTError
        
        try:
            payload = jwt.decode(token, 'SECRET_KEY', algorithms=['HS256'])
            
            if payload.get('type') != 'refresh':
                return None
            
            return payload
        except JWTError:
            return None

    # ==================== HELPER METHODS ====================

    def _generate_totp_secret(self) -> str:
        """Generate TOTP secret for 2FA."""
        import pyotp
        return pyotp.random_base32()

    def _encrypt_secret(self, secret: str) -> str:
        """Encrypt TOTP secret for storage."""
        # Implementation would use proper encryption
        # For now, simplified
        return secret

    def _decrypt_secret(self, encrypted: str) -> str:
        """Decrypt stored TOTP secret."""
        # Implementation would use proper decryption
        return encrypted

    def _generate_qr_code_url(self, email: str, secret: str) -> str:
        """Generate QR code URL for TOTP setup."""
        import pyotp
        import urllib.parse
        
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=email,
            issuer_name='Hostel Management'
        )
        
        return f"https://chart.googleapis.com/chart?chs=200x200&chld=M|0&cht=qr&chl={urllib.parse.quote(provisioning_uri)}"

    def _generate_backup_codes(self, admin_id: UUID) -> List[str]:
        """Generate backup codes for 2FA recovery."""
        codes = []
        for _ in range(10):
            code = secrets.token_hex(4).upper()
            codes.append(f"{code[:4]}-{code[4:]}")
        
        # Store hashed codes in database
        # Implementation omitted for brevity
        
        return codes

    def _serialize_admin(self, admin: AdminUser) -> Dict[str, Any]:
        """Serialize admin data for response."""
        return {
            'id': str(admin.id),
            'email': admin.user.email if admin.user else None,
            'first_name': admin.user.first_name if admin.user else None,
            'last_name': admin.user.last_name if admin.user else None,
            'admin_level': admin.admin_level,
            'is_super_admin': admin.is_super_admin,
            'department': admin.department,
            'designation': admin.designation
        }