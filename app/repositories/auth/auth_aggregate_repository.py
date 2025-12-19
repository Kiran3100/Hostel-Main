"""
Authentication Aggregate Repository
Provides unified access to all authentication-related repositories and operations.
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

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
from app.schemas.common.enums import OTPType


class AuthAggregateRepository:
    """
    Aggregate repository providing unified access to all authentication operations.
    
    This repository serves as a facade for all authentication-related repositories,
    providing a single entry point for complex authentication workflows.
    """

    def __init__(self, db: Session):
        self.db = db
        
        # Session Management
        self.user_sessions = UserSessionRepository(db)
        self.session_tokens = SessionTokenRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.login_attempts = LoginAttemptRepository(db)
        
        # OTP Management
        self.otp_tokens = OTPTokenRepository(db)
        self.otp_templates = OTPTemplateRepository(db)
        self.otp_deliveries = OTPDeliveryRepository(db)
        self.otp_throttling = OTPThrottlingRepository(db)
        
        # Password Management
        self.password_resets = PasswordResetRepository(db)
        self.password_history = PasswordHistoryRepository(db)
        self.password_policies = PasswordPolicyRepository(db)
        self.password_attempts = PasswordAttemptRepository(db)
        
        # Social Authentication
        self.social_providers = SocialAuthProviderRepository(db)
        self.social_tokens = SocialAuthTokenRepository(db)
        self.social_profiles = SocialAuthProfileRepository(db)
        self.social_links = SocialAuthLinkRepository(db)
        
        # Token Blacklist & Security
        self.blacklisted_tokens = BlacklistedTokenRepository(db)
        self.token_revocations = TokenRevocationRepository(db)
        self.security_events = SecurityEventRepository(db)

    # ==================== Complete Authentication Workflows ====================

    def authenticate_user(
        self,
        user_id: UUID,
        device_info: Dict[str, Any],
        ip_address: str,
        is_remember_me: bool = False
    ) -> Dict[str, Any]:
        """
        Complete user authentication workflow.
        
        Creates session, generates tokens, and records login attempt.
        
        Args:
            user_id: User identifier
            device_info: Device information
            ip_address: IP address
            is_remember_me: Extended session flag
            
        Returns:
            Dictionary with session and token information
        """
        import uuid
        import hashlib
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Create session
        session = self.user_sessions.create_session(
            user_id=user_id,
            session_id=session_id,
            device_info=device_info,
            ip_address=ip_address,
            is_remember_me=is_remember_me,
            expires_in_hours=720 if is_remember_me else 24  # 30 days or 24 hours
        )
        
        # Generate access token JTI
        access_jti = str(uuid.uuid4())
        access_token_hash = hashlib.sha256(access_jti.encode()).hexdigest()
        
        # Create access token
        access_token = self.session_tokens.create_token(
            session_id=session.id,
            jti=access_jti,
            token_hash=access_token_hash,
            expires_in_minutes=15
        )
        
        # Generate refresh token
        refresh_jti = str(uuid.uuid4())
        refresh_token_hash = hashlib.sha256(refresh_jti.encode()).hexdigest()
        family_id = str(uuid.uuid4())
        
        refresh_token = self.refresh_tokens.create_token(
            session_id=session.id,
            jti=refresh_jti,
            token_hash=refresh_token_hash,
            family_id=family_id,
            expires_in_days=30 if is_remember_me else 7
        )
        
        # Record successful login attempt
        self.login_attempts.record_attempt(
            user_id=user_id,
            email=None,  # Should be passed from caller
            phone=None,
            is_successful=True,
            failure_reason=None,
            ip_address=ip_address,
            user_agent=device_info.get("user_agent"),
            device_fingerprint=device_info.get("device_fingerprint")
        )
        
        return {
            "session_id": session_id,
            "access_token_jti": access_jti,
            "refresh_token_jti": refresh_jti,
            "family_id": family_id,
            "session": session,
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    def logout_user(
        self,
        session_id: str,
        revocation_reason: str = "User logout"
    ) -> bool:
        """
        Complete user logout workflow.
        
        Terminates session, revokes tokens, and records revocation.
        
        Args:
            session_id: Session identifier
            revocation_reason: Reason for logout
            
        Returns:
            Success status
        """
        session = self.user_sessions.find_by_session_id(session_id)
        
        if not session:
            return False
        
        # Get all tokens for session
        session_tokens = self.db.query(self.session_tokens.model).filter_by(
            session_id=session.id
        ).all()
        
        refresh_tokens = self.db.query(self.refresh_tokens.model).filter_by(
            session_id=session.id
        ).all()
        
        # Blacklist all tokens
        for token in session_tokens:
            if not self.blacklisted_tokens.is_blacklisted(token.jti):
                self.blacklisted_tokens.blacklist_token(
                    jti=token.jti,
                    token_type="access",
                    token_hash=token.token_hash,
                    user_id=session.user_id,
                    expires_at=token.expires_at,
                    revocation_reason=revocation_reason
                )
        
        for token in refresh_tokens:
            if not self.blacklisted_tokens.is_blacklisted(token.jti):
                self.blacklisted_tokens.blacklist_token(
                    jti=token.jti,
                    token_type="refresh",
                    token_hash=token.token_hash,
                    user_id=session.user_id,
                    expires_at=token.expires_at,
                    revocation_reason=revocation_reason
                )
        
        # Record revocation
        self.token_revocations.record_revocation(
            user_id=session.user_id,
            revocation_type="session",
            revocation_reason=revocation_reason,
            tokens_revoked_count=len(session_tokens) + len(refresh_tokens),
            initiated_by_user_id=session.user_id
        )
        
        # Terminate session
        return self.user_sessions.terminate_session(session_id, revoke_tokens=False)

    def logout_all_sessions(
        self,
        user_id: UUID,
        except_session_id: Optional[str] = None
    ) -> int:
        """
        Logout user from all sessions.
        
        Args:
            user_id: User identifier
            except_session_id: Keep this session active
            
        Returns:
            Number of sessions terminated
        """
        sessions = self.user_sessions.find_active_sessions(
            user_id,
            exclude_session_id=except_session_id
        )
        
        total_tokens = 0
        
        for session in sessions:
            # Get token count for this session
            session_token_count = self.db.query(
                self.session_tokens.model
            ).filter_by(session_id=session.id).count()
            
            refresh_token_count = self.db.query(
                self.refresh_tokens.model
            ).filter_by(session_id=session.id).count()
            
            total_tokens += session_token_count + refresh_token_count
            
            # Logout session
            self.logout_user(session.session_id, "Logout all sessions")
        
        # Record global revocation
        if total_tokens > 0:
            self.token_revocations.record_revocation(
                user_id=user_id,
                revocation_type="all_tokens",
                revocation_reason="User requested logout from all sessions",
                tokens_revoked_count=total_tokens,
                initiated_by_user_id=user_id
            )
        
        return len(sessions)

    def refresh_authentication(
        self,
        refresh_token_jti: str
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh authentication tokens.
        
        Args:
            refresh_token_jti: Refresh token JTI
            
        Returns:
            New tokens or None if refresh failed
        """
        import uuid
        import hashlib
        
        # Check for token reuse
        if self.refresh_tokens.detect_token_reuse(refresh_token_jti):
            # Security breach detected
            self.security_events.record_event(
                event_type="token_reuse_detected",
                severity="high",
                description="Refresh token reuse detected - possible security breach",
                event_data={"refresh_token_jti": refresh_token_jti}
            )
            return None
        
        # Use refresh token
        refresh_token = self.refresh_tokens.use_token(refresh_token_jti)
        
        if not refresh_token:
            return None
        
        # Generate new access token
        access_jti = str(uuid.uuid4())
        access_token_hash = hashlib.sha256(access_jti.encode()).hexdigest()
        
        access_token = self.session_tokens.create_token(
            session_id=refresh_token.session_id,
            jti=access_jti,
            token_hash=access_token_hash,
            expires_in_minutes=15
        )
        
        # Generate new refresh token (rotation)
        new_refresh_jti = str(uuid.uuid4())
        new_refresh_token_hash = hashlib.sha256(new_refresh_jti.encode()).hexdigest()
        
        new_refresh_token = self.refresh_tokens.create_token(
            session_id=refresh_token.session_id,
            jti=new_refresh_jti,
            token_hash=new_refresh_token_hash,
            family_id=refresh_token.family_id,
            parent_token_id=refresh_token.id,
            expires_in_days=7
        )
        
        # Update session activity
        session = self.user_sessions.find_by_id(refresh_token.session_id)
        if session:
            self.user_sessions.update_session_activity(session.session_id)
        
        return {
            "access_token_jti": access_jti,
            "refresh_token_jti": new_refresh_jti,
            "family_id": refresh_token.family_id,
            "access_token": access_token,
            "refresh_token": new_refresh_token
        }

    # ==================== OTP Workflows ====================

    def send_otp(
        self,
        user_id: Optional[UUID],
        identifier: str,
        identifier_type: str,
        otp_type: OTPType,
        ip_address: str,
        max_requests: int = 5,
        window_minutes: int = 60
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Complete OTP generation and sending workflow.
        
        Args:
            user_id: User identifier (optional)
            identifier: Email or phone
            identifier_type: 'email' or 'phone'
            otp_type: Type of OTP
            ip_address: IP address
            max_requests: Maximum requests per window
            window_minutes: Time window in minutes
            
        Returns:
            Tuple of (success, otp_code, error_message)
        """
        import random
        import hashlib
        
        # Check rate limiting
        is_allowed, error_msg = self.otp_throttling.check_rate_limit(
            identifier=identifier,
            identifier_type=identifier_type,
            ip_address=ip_address,
            otp_type=otp_type,
            max_requests=max_requests,
            window_minutes=window_minutes
        )
        
        if not is_allowed:
            return False, None, error_msg
        
        # Invalidate previous OTPs
        self.otp_tokens.invalidate_previous_otps(
            identifier=identifier,
            identifier_type=identifier_type,
            otp_type=otp_type
        )
        
        # Generate OTP code
        otp_code = str(random.randint(100000, 999999))
        otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
        
        # Create OTP token
        email = identifier if identifier_type == "email" else None
        phone = identifier if identifier_type == "phone" else None
        
        otp_token = self.otp_tokens.create_otp(
            user_id=user_id,
            email=email,
            phone=phone,
            otp_code=otp_hash,
            otp_type=otp_type,
            delivery_channel=identifier_type,
            ip_address=ip_address
        )
        
        # Create delivery record
        delivery = self.otp_deliveries.create_delivery(
            otp_token_id=otp_token.id,
            channel=identifier_type,
            recipient=identifier
        )
        
        # In production, you would send the OTP via email/SMS here
        # For now, we'll just mark it as sent
        self.otp_deliveries.mark_as_sent(delivery.id)
        
        return True, otp_code, None

    def verify_otp(
        self,
        identifier: str,
        identifier_type: str,
        otp_code: str,
        otp_type: OTPType
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify OTP code.
        
        Args:
            identifier: Email or phone
            identifier_type: 'email' or 'phone'
            otp_code: OTP code to verify
            otp_type: Type of OTP
            
        Returns:
            Tuple of (success, error_message)
        """
        import hashlib
        
        # Hash the provided OTP
        otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
        
        return self.otp_tokens.verify_otp(
            identifier=identifier,
            identifier_type=identifier_type,
            otp_code=otp_hash,
            otp_type=otp_type
        )

    # ==================== Password Reset Workflows ====================

    def initiate_password_reset(
        self,
        user_id: UUID,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Initiate password reset workflow.
        
        Args:
            user_id: User identifier
            ip_address: IP address
            user_agent: User agent
            
        Returns:
            Tuple of (success, reset_token, error_message)
        """
        import secrets
        import hashlib
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        
        # Create reset record
        reset = self.password_resets.create_reset_token(
            user_id=user_id,
            token=reset_token,
            token_hash=token_hash,
            expires_in_hours=1,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Record security event
        self.security_events.record_event(
            event_type="password_reset_requested",
            severity="medium",
            description="Password reset requested",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return True, reset_token, None

    def complete_password_reset(
        self,
        reset_token: str,
        new_password_hash: str,
        ip_address: str,
        user_agent: str,
        tenant_id: Optional[UUID] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Complete password reset workflow.
        
        Args:
            reset_token: Reset token
            new_password_hash: New password hash
            ip_address: IP address
            user_agent: User agent
            tenant_id: Tenant ID for policy lookup
            
        Returns:
            Tuple of (success, error_message)
        """
        # Verify reset token
        success, reset, error = self.password_resets.verify_and_use_token(
            token=reset_token,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not success or not reset:
            return False, error
        
        # Check password reuse
        policy = self.password_policies.get_active_policy(tenant_id)
        check_count = policy.prevent_reuse_count if policy else 5
        
        is_reused = self.password_history.check_password_reuse(
            user_id=reset.user_id,
            new_password_hash=new_password_hash,
            check_last_n=check_count
        )
        
        if is_reused:
            return False, "Password has been used recently. Please choose a different password."
        
        # Add to password history
        self.password_history.add_to_history(
            user_id=reset.user_id,
            password_hash=new_password_hash,
            change_reason="Password reset",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Terminate all user sessions
        self.logout_all_sessions(reset.user_id)
        
        # Record security event
        self.security_events.record_event(
            event_type="password_reset_completed",
            severity="medium",
            description="Password successfully reset",
            user_id=reset.user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return True, None

    # ==================== Social Authentication Workflows ====================

    def link_social_account(
        self,
        user_id: UUID,
        provider_name: str,
        provider_user_id: str,
        access_token: str,
        refresh_token: Optional[str],
        profile_data: Dict[str, Any],
        expires_in: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Link social account to user.
        
        Args:
            user_id: User identifier
            provider_name: OAuth provider name
            provider_user_id: User ID from provider
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            profile_data: Profile data from provider
            expires_in: Token expiration in seconds
            
        Returns:
            Tuple of (success, error_message)
        """
        # Get provider
        provider = self.social_providers.find_by_name(provider_name)
        
        if not provider or not provider.is_enabled:
            return False, f"Provider {provider_name} not available"
        
        # Check if account already linked
        existing_link = self.social_links.find_by_user_and_provider(
            user_id=user_id,
            provider_id=provider.id
        )
        
        if existing_link and existing_link.is_linked:
            return False, "Social account already linked"
        
        # Create or update social profile
        self.social_profiles.create_or_update_profile(
            user_id=user_id,
            provider_id=provider.id,
            provider_user_id=provider_user_id,
            profile_data=profile_data
        )
        
        # Create or update token
        self.social_tokens.create_token(
            user_id=user_id,
            provider_id=provider.id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
        
        # Create or relink account
        if existing_link:
            self.social_links.relink_account(existing_link.id)
        else:
            self.social_links.create_link(
                user_id=user_id,
                provider_id=provider.id,
                link_method="manual_link"
            )
        
        # Record security event
        self.security_events.record_event(
            event_type="social_account_linked",
            severity="low",
            description=f"Social account linked: {provider_name}",
            user_id=user_id
        )
        
        return True, None

    # ==================== Comprehensive Statistics ====================

    def get_authentication_overview(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive authentication overview for user.
        
        Args:
            user_id: User identifier
            days: Number of days to analyze
            
        Returns:
            Dictionary with complete authentication statistics
        """
        return {
            "sessions": self.user_sessions.get_session_statistics(user_id),
            "login_attempts": self.login_attempts.get_attempt_statistics(user_id, days),
            "password_attempts": self.password_attempts.get_attempt_statistics(user_id, days),
            "security_events": self.security_events.get_event_statistics(user_id, days),
            "social_links": {
                "active_links": self.social_links.count_active_links(user_id),
                "links": [
                    {
                        "provider": link.provider.provider_name,
                        "is_primary": link.is_primary,
                        "linked_at": link.linked_at
                    }
                    for link in self.social_links.find_user_links(user_id)
                ]
            },
            "devices": self.user_sessions.get_user_devices(user_id)
        }

    def get_security_dashboard(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get security dashboard with threat intelligence.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with security metrics and threats
        """
        return {
            "security_events": self.security_events.get_event_statistics(days=days),
            "threat_intelligence": self.security_events.get_threat_intelligence(days),
            "high_risk_events": len(self.security_events.find_high_risk_events(hours=days*24)),
            "critical_events": len(self.security_events.find_critical_events(hours=days*24)),
            "blacklist_stats": self.blacklisted_tokens.get_blacklist_statistics(days=days),
            "revocation_stats": self.token_revocations.get_revocation_statistics(days=days)
        }

    # ==================== Cleanup Operations ====================

    def cleanup_expired_data(self, days_old: int = 30) -> Dict[str, int]:
        """
        Clean up expired authentication data.
        
        Args:
            days_old: Remove data older than this many days
            
        Returns:
            Dictionary with cleanup counts
        """
        return {
            "sessions_cleaned": self.user_sessions.cleanup_expired_sessions(days_old),
            "session_tokens_cleaned": self.session_tokens.cleanup_expired_tokens(days_old),
            "refresh_tokens_cleaned": self.refresh_tokens.cleanup_expired_tokens(days_old),
            "login_attempts_cleaned": self.login_attempts.cleanup_old_attempts(days_old),
            "otp_tokens_cleaned": self.otp_tokens.cleanup_expired_otps(days_old),
            "otp_throttling_cleaned": self.otp_throttling.cleanup_old_records(days_old),
            "password_resets_cleaned": self.password_resets.cleanup_expired_tokens(days_old),
            "password_attempts_cleaned": self.password_attempts.cleanup_old_attempts(days_old),
            "blacklisted_tokens_cleaned": self.blacklisted_tokens.cleanup_expired_tokens(days_old),
            "security_events_cleaned": self.security_events.cleanup_old_events(days_old, keep_critical=True)
        }