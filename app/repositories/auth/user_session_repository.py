"""
User Session Repository
Manages user sessions, tokens, and login attempts with advanced security features.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session, joinedload

from app.models.auth import (
    UserSession,
    SessionToken,
    RefreshToken,
    LoginAttempt,
)
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import DeviceType


class UserSessionRepository(BaseRepository[UserSession]):
    """
    Repository for user session management with security monitoring.
    """

    def __init__(self, db: Session):
        super().__init__(UserSession, db)

    # ==================== Session Management ====================

    def create_session(
        self,
        user_id: UUID,
        session_id: str,
        device_info: Dict[str, Any],
        ip_address: str,
        is_remember_me: bool = False,
        expires_in_hours: int = 24,
    ) -> UserSession:
        """
        Create new user session with device tracking.
        
        Args:
            user_id: User identifier
            session_id: Unique session identifier
            device_info: Device information dictionary
            ip_address: IP address
            is_remember_me: Extended session flag
            expires_in_hours: Session expiration hours
            
        Returns:
            Created UserSession instance
        """
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            device_name=device_info.get("device_name"),
            device_type=device_info.get("device_type"),
            device_fingerprint=device_info.get("device_fingerprint"),
            user_agent=device_info.get("user_agent"),
            browser=device_info.get("browser"),
            operating_system=device_info.get("operating_system"),
            ip_address=ip_address,
            country=device_info.get("country"),
            city=device_info.get("city"),
            timezone=device_info.get("timezone"),
            is_remember_me=is_remember_me,
            expires_at=expires_at,
            login_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def find_by_session_id(
        self,
        session_id: str,
        active_only: bool = True
    ) -> Optional[UserSession]:
        """
        Find session by session ID.
        
        Args:
            session_id: Session identifier
            active_only: Only return active sessions
            
        Returns:
            UserSession or None
        """
        query = self.db.query(UserSession).filter(
            UserSession.session_id == session_id
        )
        
        if active_only:
            query = query.filter(UserSession.is_active == True)
        
        return query.first()

    def find_active_sessions(
        self,
        user_id: UUID,
        exclude_session_id: Optional[str] = None
    ) -> List[UserSession]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User identifier
            exclude_session_id: Session ID to exclude (current session)
            
        Returns:
            List of active sessions
        """
        query = self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            )
        )
        
        if exclude_session_id:
            query = query.filter(UserSession.session_id != exclude_session_id)
        
        return query.order_by(desc(UserSession.last_activity_at)).all()

    def update_session_activity(self, session_id: str) -> bool:
        """
        Update last activity timestamp for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Success status
        """
        session = self.find_by_session_id(session_id)
        if session and session.is_active:
            session.update_activity()
            self.db.commit()
            return True
        return False

    def terminate_session(
        self,
        session_id: str,
        revoke_tokens: bool = True
    ) -> bool:
        """
        Terminate a session and optionally revoke associated tokens.
        
        Args:
            session_id: Session identifier
            revoke_tokens: Whether to revoke associated tokens
            
        Returns:
            Success status
        """
        session = self.find_by_session_id(session_id, active_only=False)
        if not session:
            return False
        
        session.terminate()
        
        if revoke_tokens:
            # Revoke all session tokens
            self.db.query(SessionToken).filter(
                SessionToken.session_id == session.id
            ).update({
                "is_revoked": True,
                "revoked_at": datetime.utcnow(),
                "revocation_reason": "Session terminated"
            })
            
            # Revoke all refresh tokens
            self.db.query(RefreshToken).filter(
                RefreshToken.session_id == session.id
            ).update({
                "is_revoked": True,
                "revoked_at": datetime.utcnow(),
                "revocation_reason": "Session terminated"
            })
        
        self.db.commit()
        return True

    def terminate_all_user_sessions(
        self,
        user_id: UUID,
        except_session_id: Optional[str] = None
    ) -> int:
        """
        Terminate all sessions for a user.
        
        Args:
            user_id: User identifier
            except_session_id: Session to keep active (current session)
            
        Returns:
            Number of sessions terminated
        """
        sessions = self.find_active_sessions(user_id, exclude_session_id=except_session_id)
        
        for session in sessions:
            self.terminate_session(session.session_id, revoke_tokens=True)
        
        return len(sessions)

    def cleanup_expired_sessions(self, days_old: int = 30) -> int:
        """
        Clean up old expired sessions.
        
        Args:
            days_old: Remove sessions older than this many days
            
        Returns:
            Number of sessions deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(UserSession).filter(
            and_(
                UserSession.is_active == False,
                UserSession.logout_at < cutoff_date
            )
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count

    # ==================== Security Monitoring ====================

    def find_suspicious_sessions(
        self,
        user_id: UUID,
        risk_threshold: int = 50
    ) -> List[UserSession]:
        """
        Find sessions with high risk scores.
        
        Args:
            user_id: User identifier
            risk_threshold: Minimum risk score to flag
            
        Returns:
            List of suspicious sessions
        """
        return self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.risk_score >= risk_threshold
            )
        ).all()

    def detect_concurrent_locations(self, user_id: UUID) -> bool:
        """
        Detect if user has active sessions from different locations.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if concurrent locations detected
        """
        active_sessions = self.find_active_sessions(user_id)
        
        if len(active_sessions) < 2:
            return False
        
        # Get unique countries from active sessions
        countries = set(
            session.country for session in active_sessions 
            if session.country
        )
        
        return len(countries) > 1

    def get_session_statistics(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get session statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with session statistics
        """
        total_sessions = self.db.query(func.count(UserSession.id)).filter(
            UserSession.user_id == user_id
        ).scalar()
        
        active_sessions = self.db.query(func.count(UserSession.id)).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            )
        ).scalar()
        
        # Get device type breakdown
        device_breakdown = self.db.query(
            UserSession.device_type,
            func.count(UserSession.id)
        ).filter(
            UserSession.user_id == user_id
        ).group_by(UserSession.device_type).all()
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "device_breakdown": {
                device_type: count for device_type, count in device_breakdown
            },
            "has_suspicious_activity": len(self.find_suspicious_sessions(user_id)) > 0,
            "concurrent_locations": self.detect_concurrent_locations(user_id)
        }

    # ==================== Device Management ====================

    def find_sessions_by_device(
        self,
        user_id: UUID,
        device_fingerprint: str
    ) -> List[UserSession]:
        """
        Find all sessions for a specific device.
        
        Args:
            user_id: User identifier
            device_fingerprint: Device fingerprint hash
            
        Returns:
            List of sessions from this device
        """
        return self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.device_fingerprint == device_fingerprint
            )
        ).order_by(desc(UserSession.created_at)).all()

    def is_trusted_device(
        self,
        user_id: UUID,
        device_fingerprint: str,
        trust_threshold_days: int = 30
    ) -> bool:
        """
        Check if device is trusted based on usage history.
        
        Args:
            user_id: User identifier
            device_fingerprint: Device fingerprint hash
            trust_threshold_days: Days of history required
            
        Returns:
            True if device is trusted
        """
        oldest_session = self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.device_fingerprint == device_fingerprint
            )
        ).order_by(UserSession.created_at).first()
        
        if not oldest_session:
            return False
        
        days_used = (datetime.utcnow() - oldest_session.created_at).days
        return days_used >= trust_threshold_days

    def get_user_devices(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Get list of unique devices used by user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of device information dictionaries
        """
        devices = self.db.query(
            UserSession.device_fingerprint,
            UserSession.device_name,
            UserSession.device_type,
            func.max(UserSession.last_activity_at).label("last_used"),
            func.count(UserSession.id).label("session_count")
        ).filter(
            UserSession.user_id == user_id
        ).group_by(
            UserSession.device_fingerprint,
            UserSession.device_name,
            UserSession.device_type
        ).all()
        
        return [
            {
                "device_fingerprint": device.device_fingerprint,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "last_used": device.last_used,
                "session_count": device.session_count,
                "is_trusted": self.is_trusted_device(user_id, device.device_fingerprint)
            }
            for device in devices
        ]


class SessionTokenRepository(BaseRepository[SessionToken]):
    """
    Repository for JWT access token management.
    """

    def __init__(self, db: Session):
        super().__init__(SessionToken, db)

    def create_token(
        self,
        session_id: UUID,
        jti: str,
        token_hash: str,
        expires_in_minutes: int = 15,
        scopes: Optional[List[str]] = None
    ) -> SessionToken:
        """
        Create new session token.
        
        Args:
            session_id: Session identifier
            jti: JWT ID
            token_hash: Token hash
            expires_in_minutes: Expiration time in minutes
            scopes: Token scopes
            
        Returns:
            Created SessionToken instance
        """
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        
        token = SessionToken(
            session_id=session_id,
            jti=jti,
            token_hash=token_hash,
            expires_at=expires_at,
            scopes=scopes,
        )
        
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def find_by_jti(self, jti: str) -> Optional[SessionToken]:
        """Find token by JWT ID."""
        return self.db.query(SessionToken).filter(
            SessionToken.jti == jti
        ).first()

    def is_token_valid(self, jti: str) -> bool:
        """Check if token is valid (not revoked and not expired)."""
        token = self.find_by_jti(jti)
        return token is not None and token.is_valid()

    def revoke_token(self, jti: str, reason: Optional[str] = None) -> bool:
        """Revoke a token."""
        token = self.find_by_jti(jti)
        if token:
            token.revoke(reason)
            self.db.commit()
            return True
        return False

    def revoke_session_tokens(self, session_id: UUID) -> int:
        """Revoke all tokens for a session."""
        count = self.db.query(SessionToken).filter(
            SessionToken.session_id == session_id
        ).update({
            "is_revoked": True,
            "revoked_at": datetime.utcnow(),
            "revocation_reason": "Session terminated"
        })
        self.db.commit()
        return count

    def cleanup_expired_tokens(self, days_old: int = 7) -> int:
        """Clean up old expired tokens."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(SessionToken).filter(
            SessionToken.expires_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """
    Repository for JWT refresh token management with rotation.
    """

    def __init__(self, db: Session):
        super().__init__(RefreshToken, db)

    def create_token(
        self,
        session_id: UUID,
        jti: str,
        token_hash: str,
        family_id: str,
        expires_in_days: int = 30,
        parent_token_id: Optional[UUID] = None
    ) -> RefreshToken:
        """
        Create new refresh token with family tracking.
        
        Args:
            session_id: Session identifier
            jti: JWT ID
            token_hash: Token hash
            family_id: Token family ID for rotation tracking
            expires_in_days: Expiration time in days
            parent_token_id: Parent token in rotation chain
            
        Returns:
            Created RefreshToken instance
        """
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        rotation_count = 0
        if parent_token_id:
            parent = self.find_by_id(parent_token_id)
            if parent:
                rotation_count = parent.rotation_count + 1
        
        token = RefreshToken(
            session_id=session_id,
            jti=jti,
            token_hash=token_hash,
            family_id=family_id,
            parent_token_id=parent_token_id,
            rotation_count=rotation_count,
            expires_at=expires_at,
        )
        
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def find_by_jti(self, jti: str) -> Optional[RefreshToken]:
        """Find token by JWT ID."""
        return self.db.query(RefreshToken).filter(
            RefreshToken.jti == jti
        ).first()

    def find_by_family_id(self, family_id: str) -> List[RefreshToken]:
        """Find all tokens in a family."""
        return self.db.query(RefreshToken).filter(
            RefreshToken.family_id == family_id
        ).order_by(RefreshToken.rotation_count).all()

    def is_token_valid(self, jti: str) -> bool:
        """Check if refresh token is valid."""
        token = self.find_by_jti(jti)
        return token is not None and token.is_valid()

    def use_token(self, jti: str) -> Optional[RefreshToken]:
        """Mark token as used and return it."""
        token = self.find_by_jti(jti)
        if token and token.is_valid():
            token.mark_as_used()
            self.db.commit()
            return token
        return None

    def revoke_token_family(
        self,
        family_id: str,
        reason: str = "Token reuse detected"
    ) -> int:
        """
        Revoke entire token family (security breach).
        
        Args:
            family_id: Token family ID
            reason: Revocation reason
            
        Returns:
            Number of tokens revoked
        """
        tokens = self.find_by_family_id(family_id)
        
        for token in tokens:
            token.revoke_family(reason)
        
        self.db.commit()
        return len(tokens)

    def detect_token_reuse(self, jti: str) -> bool:
        """
        Detect if a refresh token has been reused.
        
        Args:
            jti: JWT ID to check
            
        Returns:
            True if token reuse detected
        """
        token = self.find_by_jti(jti)
        
        if not token:
            return False
        
        # If token is already used but someone tries to use it again
        if token.is_used:
            # This is a security breach - revoke entire family
            self.revoke_token_family(
                token.family_id,
                "Token reuse detected - possible security breach"
            )
            return True
        
        return False

    def cleanup_expired_tokens(self, days_old: int = 7) -> int:
        """Clean up old expired refresh tokens."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(RefreshToken).filter(
            RefreshToken.expires_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count


class LoginAttemptRepository(BaseRepository[LoginAttempt]):
    """
    Repository for login attempt tracking and security monitoring.
    """

    def __init__(self, db: Session):
        super().__init__(LoginAttempt, db)

    def record_attempt(
        self,
        user_id: Optional[UUID],
        email: Optional[str],
        phone: Optional[str],
        is_successful: bool,
        failure_reason: Optional[str],
        ip_address: str,
        user_agent: str,
        device_fingerprint: Optional[str] = None,
        security_flags: Optional[Dict[str, Any]] = None
    ) -> LoginAttempt:
        """
        Record a login attempt.
        
        Args:
            user_id: User identifier (if known)
            email: Email used in attempt
            phone: Phone used in attempt
            is_successful: Whether attempt succeeded
            failure_reason: Reason for failure
            ip_address: IP address
            user_agent: User agent string
            device_fingerprint: Device fingerprint
            security_flags: Security analysis flags
            
        Returns:
            Created LoginAttempt instance
        """
        attempt = LoginAttempt(
            user_id=user_id,
            email=email,
            phone=phone,
            is_successful=is_successful,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            security_flags=security_flags,
        )
        
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def count_recent_failures(
        self,
        identifier: str,
        identifier_type: str = "email",
        minutes: int = 15
    ) -> int:
        """
        Count recent failed login attempts.
        
        Args:
            identifier: Email or phone to check
            identifier_type: Type of identifier ('email' or 'phone')
            minutes: Time window in minutes
            
        Returns:
            Count of failed attempts
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        filter_field = LoginAttempt.email if identifier_type == "email" else LoginAttempt.phone
        
        return self.db.query(func.count(LoginAttempt.id)).filter(
            and_(
                filter_field == identifier,
                LoginAttempt.is_successful == False,
                LoginAttempt.created_at >= cutoff_time,
            )
        ).scalar() or 0

    def find_suspicious_attempts(
        self,
        hours: int = 24,
        min_risk_score: int = 70
    ) -> List[LoginAttempt]:
        """
        Find suspicious login attempts.
        
        Args:
            hours: Time window in hours
            min_risk_score: Minimum risk score to flag
            
        Returns:
            List of suspicious attempts
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return self.db.query(LoginAttempt).filter(
            and_(
                LoginAttempt.created_at >= cutoff_time,
                LoginAttempt.risk_score >= min_risk_score
            )
        ).order_by(desc(LoginAttempt.risk_score)).all()

    def get_attempt_statistics(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get login attempt statistics for a user.
        
        Args:
            user_id: User identifier
            days: Number of days to analyze
            
        Returns:
            Dictionary with attempt statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        total_attempts = self.db.query(func.count(LoginAttempt.id)).filter(
            and_(
                LoginAttempt.user_id == user_id,
                LoginAttempt.created_at >= cutoff_time
            )
        ).scalar()
        
        successful_attempts = self.db.query(func.count(LoginAttempt.id)).filter(
            and_(
                LoginAttempt.user_id == user_id,
                LoginAttempt.is_successful == True,
                LoginAttempt.created_at >= cutoff_time
            )
        ).scalar()
        
        failed_attempts = total_attempts - successful_attempts
        
        # Get unique IPs
        unique_ips = self.db.query(
            func.count(func.distinct(LoginAttempt.ip_address))
        ).filter(
            and_(
                LoginAttempt.user_id == user_id,
                LoginAttempt.created_at >= cutoff_time
            )
        ).scalar()
        
        return {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "success_rate": (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0,
            "unique_ips": unique_ips,
            "has_suspicious_activity": len(self.find_suspicious_attempts()) > 0
        }

    def cleanup_old_attempts(self, days_old: int = 90) -> int:
        """Clean up old login attempts."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(LoginAttempt).filter(
            LoginAttempt.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count