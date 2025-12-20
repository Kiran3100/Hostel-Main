# --- File: C:\Hostel-Main\app\services\user\user_session_service.py ---
"""
User Session Service - Session lifecycle and security management.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import hashlib
import secrets

from app.models.user import UserSession
from app.repositories.user import UserSessionRepository, UserRepository
from app.core.exceptions import (
    EntityNotFoundError,
    AuthenticationError,
    BusinessRuleViolationError
)


class UserSessionService:
    """
    Service for user session operations including creation,
    validation, revocation, and security monitoring.
    """

    def __init__(self, db: Session):
        self.db = db
        self.session_repo = UserSessionRepository(db)
        self.user_repo = UserRepository(db)

    # ==================== Session Creation ====================

    def create_session(
        self,
        user_id: str,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[Dict] = None,
        session_type: str = "web",
        is_remember_me: bool = False,
        duration_days: int = 7
    ) -> UserSession:
        """
        Create a new user session.
        
        Args:
            user_id: User ID
            refresh_token: Refresh token (will be hashed)
            ip_address: IP address
            user_agent: User agent string
            device_info: Parsed device information
            session_type: Session type (web, mobile, api)
            is_remember_me: Extended session flag
            duration_days: Session duration in days
            
        Returns:
            Created UserSession
            
        Raises:
            EntityNotFoundError: If user not found
        """
        # Validate user exists
        user = self.user_repo.get_by_id(user_id)
        
        # Hash refresh token
        refresh_token_hash = self._hash_token(refresh_token)
        
        # Calculate expiration
        if is_remember_me:
            duration_days = 30  # Extended session
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
        
        # Parse device info from user agent if not provided
        if not device_info and user_agent:
            device_info = self._parse_user_agent(user_agent)
        
        # Generate device fingerprint
        device_fingerprint = self._generate_device_fingerprint(
            user_agent, ip_address
        )
        
        # Get geolocation from IP
        ip_location = self._get_ip_location(ip_address) if ip_address else None
        
        # Create session
        session = self.session_repo.create_session(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            session_type=session_type,
            is_remember_me=is_remember_me
        )
        
        # Update additional fields
        self.session_repo.update(session.id, {
            'device_fingerprint': device_fingerprint,
            'ip_location': ip_location
        })
        
        # Check for suspicious activity
        self._check_session_security(session.id, user_id)
        
        return session

    def _hash_token(self, token: str) -> str:
        """
        Hash refresh token for storage.
        
        Args:
            token: Token to hash
            
        Returns:
            Hashed token
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def _generate_device_fingerprint(
        self,
        user_agent: Optional[str],
        ip_address: Optional[str]
    ) -> str:
        """
        Generate device fingerprint.
        
        Args:
            user_agent: User agent string
            ip_address: IP address
            
        Returns:
            Device fingerprint
        """
        data = f"{user_agent or ''}{ip_address or ''}"
        return hashlib.md5(data.encode()).hexdigest()

    def _parse_user_agent(self, user_agent: str) -> Dict[str, Any]:
        """
        Parse user agent string to extract device information.
        
        Args:
            user_agent: User agent string
            
        Returns:
            Parsed device information
        """
        # TODO: Implement actual user agent parsing
        # Use library like user-agents or ua-parser
        
        return {
            'browser': {'name': 'Unknown', 'version': ''},
            'os': {'name': 'Unknown', 'version': ''},
            'device_type': 'desktop'
        }

    def _get_ip_location(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Get geolocation from IP address.
        
        Args:
            ip_address: IP address
            
        Returns:
            Location data or None
        """
        # TODO: Implement GeoIP lookup
        # Use service like MaxMind GeoIP2, IP-API, etc.
        
        return None

    # ==================== Session Validation ====================

    def validate_session(
        self,
        session_id: str,
        refresh_token: Optional[str] = None
    ) -> UserSession:
        """
        Validate and retrieve session.
        
        Args:
            session_id: Session ID
            refresh_token: Optional refresh token for validation
            
        Returns:
            Valid UserSession
            
        Raises:
            AuthenticationError: If session is invalid
        """
        session = self.session_repo.get_by_id(session_id)
        
        # Check if session is active
        if not session.is_active:
            raise AuthenticationError("Session is invalid or expired")
        
        # Validate refresh token if provided
        if refresh_token:
            token_hash = self._hash_token(refresh_token)
            if session.refresh_token_hash != token_hash:
                raise AuthenticationError("Invalid refresh token")
        
        # Update last activity
        self.session_repo.update_last_activity(session_id)
        
        return session

    def validate_by_jti(self, jti: str) -> UserSession:
        """
        Validate session by JWT Token ID.
        
        Args:
            jti: JWT Token ID
            
        Returns:
            Valid UserSession
            
        Raises:
            AuthenticationError: If session is invalid
        """
        session = self.session_repo.find_by_jti(jti)
        
        if not session:
            raise AuthenticationError("Session not found")
        
        if not session.is_active:
            raise AuthenticationError("Session is invalid or expired")
        
        return session

    # ==================== Session Lifecycle ====================

    def update_session_activity(
        self,
        session_id: str,
        increment_requests: bool = True
    ) -> UserSession:
        """
        Update session last activity timestamp.
        
        Args:
            session_id: Session ID
            increment_requests: Increment request counter
            
        Returns:
            Updated session
        """
        return self.session_repo.update_last_activity(
            session_id,
            increment_requests
        )

    def revoke_session(
        self,
        session_id: str,
        revoked_by: Optional[str] = None,
        reason: str = "user_logout"
    ) -> UserSession:
        """
        Revoke a session.
        
        Args:
            session_id: Session ID
            revoked_by: User ID who revoked the session
            reason: Revocation reason
            
        Returns:
            Revoked session
        """
        return self.session_repo.revoke_session(
            session_id,
            revoked_by,
            reason
        )

    def revoke_all_user_sessions(
        self,
        user_id: str,
        exclude_session_id: Optional[str] = None,
        reason: str = "logout_all"
    ) -> int:
        """
        Revoke all active sessions for a user.
        
        Args:
            user_id: User ID
            exclude_session_id: Session ID to keep active (current session)
            reason: Revocation reason
            
        Returns:
            Count of revoked sessions
        """
        return self.session_repo.revoke_all_user_sessions(
            user_id,
            exclude_session_id,
            reason
        )

    def extend_session(
        self,
        session_id: str,
        additional_days: int = 7
    ) -> UserSession:
        """
        Extend session expiration.
        
        Args:
            session_id: Session ID
            additional_days: Days to add to expiration
            
        Returns:
            Updated session
        """
        session = self.session_repo.get_by_id(session_id)
        
        new_expiry = session.expires_at + timedelta(days=additional_days)
        
        return self.session_repo.update(session.id, {
            'expires_at': new_expiry
        })

    def refresh_session(
        self,
        session_id: str,
        new_refresh_token: str,
        new_access_token_jti: Optional[str] = None
    ) -> UserSession:
        """
        Refresh session with new tokens.
        
        Args:
            session_id: Session ID
            new_refresh_token: New refresh token
            new_access_token_jti: New access token JTI
            
        Returns:
            Updated session
        """
        session = self.validate_session(session_id)
        
        # Hash new refresh token
        new_token_hash = self._hash_token(new_refresh_token)
        
        update_data = {
            'refresh_token_hash': new_token_hash,
            'last_activity': datetime.now(timezone.utc)
        }
        
        if new_access_token_jti:
            update_data['access_token_jti'] = new_access_token_jti
        
        return self.session_repo.update(session.id, update_data)

    # ==================== Session Queries ====================

    def get_user_sessions(
        self,
        user_id: str,
        active_only: bool = True,
        limit: int = 50
    ) -> List[UserSession]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User ID
            active_only: Only return active sessions
            limit: Maximum results
            
        Returns:
            List of sessions
        """
        return self.session_repo.find_by_user_id(
            user_id,
            active_only,
            limit
        )

    def get_active_sessions_count(self, user_id: str) -> int:
        """
        Get count of active sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Count of active sessions
        """
        sessions = self.get_user_sessions(user_id, active_only=True)
        return len(sessions)

    def get_user_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of unique devices for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of unique device information
        """
        return self.session_repo.get_unique_devices(user_id)

    # ==================== Security Monitoring ====================

    def _check_session_security(
        self,
        session_id: str,
        user_id: str
    ) -> None:
        """
        Check session for security anomalies.
        
        Args:
            session_id: Session ID
            user_id: User ID
        """
        session = self.session_repo.get_by_id(session_id)
        security_flags = []
        
        # Check for concurrent sessions from different IPs
        concurrent_ips = self.session_repo.find_multiple_ip_sessions(
            user_id,
            time_window_minutes=5
        )
        
        if len(concurrent_ips) > 1:
            security_flags.append({
                'type': 'concurrent_ips',
                'severity': 'medium',
                'details': f"Sessions from {len(concurrent_ips)} different IPs"
            })
        
        # Check for excessive concurrent sessions
        if self.session_repo.detect_concurrent_sessions(user_id, threshold=5):
            security_flags.append({
                'type': 'excessive_sessions',
                'severity': 'high',
                'details': 'More than 5 concurrent sessions detected'
            })
        
        # Mark as suspicious if flags detected
        if security_flags:
            self.session_repo.mark_suspicious(session_id, {
                'flags': security_flags,
                'detected_at': datetime.now(timezone.utc).isoformat()
            })

    def mark_session_suspicious(
        self,
        session_id: str,
        security_flags: Optional[Dict] = None
    ) -> UserSession:
        """
        Mark session as suspicious.
        
        Args:
            session_id: Session ID
            security_flags: Security flags and anomalies
            
        Returns:
            Updated session
        """
        return self.session_repo.mark_suspicious(session_id, security_flags)

    def get_suspicious_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[UserSession]:
        """
        Get sessions flagged as suspicious.
        
        Args:
            user_id: Optional user ID filter
            limit: Maximum results
            
        Returns:
            List of suspicious sessions
        """
        return self.session_repo.find_suspicious_sessions(user_id, limit)

    def find_sessions_from_ip(
        self,
        ip_address: str,
        active_only: bool = True
    ) -> List[UserSession]:
        """
        Find sessions from specific IP address.
        
        Args:
            ip_address: IP address to search
            active_only: Only active sessions
            
        Returns:
            List of sessions
        """
        return self.session_repo.find_sessions_by_ip(ip_address, active_only)

    # ==================== Cleanup Operations ====================

    def cleanup_expired_sessions(self) -> int:
        """
        Delete expired sessions from database.
        
        Returns:
            Count of deleted sessions
        """
        return self.session_repo.cleanup_expired_sessions()

    def cleanup_old_revoked_sessions(self, days: int = 30) -> int:
        """
        Delete old revoked sessions.
        
        Args:
            days: Keep sessions revoked within X days
            
        Returns:
            Count of deleted sessions
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        sessions = self.db.query(UserSession).filter(
            UserSession.is_revoked == True,
            UserSession.revoked_at < cutoff
        ).all()
        
        count = 0
        for session in sessions:
            self.session_repo.delete(session.id)
            count += 1
        
        return count

    def revoke_inactive_sessions(self, hours: int = 24) -> int:
        """
        Revoke sessions with no recent activity.
        
        Args:
            hours: Hours of inactivity threshold
            
        Returns:
            Count of revoked sessions
        """
        inactive_sessions = self.session_repo.find_inactive_sessions(
            hours=hours,
            limit=1000
        )
        
        count = 0
        for session in inactive_sessions:
            self.revoke_session(
                session.id,
                reason="inactivity_timeout"
            )
            count += 1
        
        return count

    # ==================== Analytics ====================

    def get_session_statistics(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive session statistics.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            Dictionary with session metrics
        """
        return self.session_repo.get_session_statistics(user_id)

    def get_session_duration_stats(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get session duration statistics.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            Dictionary with duration metrics
        """
        return self.session_repo.get_session_duration_stats(user_id)

    def get_device_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get device usage statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Device statistics
        """
        devices = self.get_user_devices(user_id)
        
        total_devices = len(devices)
        active_devices = sum(1 for d in devices if d['is_active'])
        
        # Device type distribution
        device_types = {}
        for device in devices:
            device_type = device.get('device_info', {}).get('device_type', 'unknown')
            device_types[device_type] = device_types.get(device_type, 0) + 1
        
        return {
            'total_devices': total_devices,
            'active_devices': active_devices,
            'device_type_distribution': device_types,
            'devices': devices
        }


