"""
Session Service
Manages user session lifecycle, device tracking, and security monitoring.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
import hashlib

from sqlalchemy.orm import Session
from user_agents import parse as parse_user_agent

from app.repositories.auth import (
    UserSessionRepository,
    SecurityEventRepository,
)
from app.services.auth.token_service import TokenService
from app.core.exceptions import (
    SessionNotFoundError,
    SessionExpiredError,
    InvalidSessionError,
)


class SessionService:
    """
    Service for managing user sessions with device tracking and security monitoring.
    """

    def __init__(self, db: Session):
        self.db = db
        self.session_repo = UserSessionRepository(db)
        self.security_event_repo = SecurityEventRepository(db)
        self.token_service = TokenService(db)

    # ==================== Session Creation ====================

    def create_session(
        self,
        user_id: UUID,
        ip_address: str,
        user_agent: str,
        device_fingerprint: Optional[str] = None,
        is_remember_me: bool = False,
        country: Optional[str] = None,
        city: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create new user session with device tracking.
        
        Args:
            user_id: User identifier
            ip_address: IP address
            user_agent: User agent string
            device_fingerprint: Device fingerprint hash
            is_remember_me: Extended session flag
            country: Country from geolocation
            city: City from geolocation
            timezone: User timezone
            
        Returns:
            Dictionary with session and tokens
        """
        # Parse user agent
        device_info = self._parse_device_info(
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            country=country,
            city=city,
            timezone=timezone
        )
        
        # Generate session ID
        session_id = str(uuid4())
        
        # Calculate session expiration
        expires_in_hours = 720 if is_remember_me else 24  # 30 days or 24 hours
        
        # Create session
        session = self.session_repo.create_session(
            user_id=user_id,
            session_id=session_id,
            device_info=device_info,
            ip_address=ip_address,
            is_remember_me=is_remember_me,
            expires_in_hours=expires_in_hours
        )
        
        # Generate tokens
        tokens = self.token_service.create_token_pair(
            user_id=user_id,
            session_id=session.id,
            is_remember_me=is_remember_me
        )
        
        # Check for security concerns
        self._check_session_security(user_id, ip_address, device_info)
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="session_created",
            severity="low",
            description="New user session created",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            country=country,
            city=city
        )
        
        return {
            "session_id": session_id,
            "session": session,
            "tokens": tokens,
            "device_info": device_info,
            "expires_at": session.expires_at
        }

    def _parse_device_info(
        self,
        user_agent: str,
        device_fingerprint: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse device information from user agent."""
        ua = parse_user_agent(user_agent)
        
        # Determine device type
        if ua.is_mobile:
            device_type = "mobile"
        elif ua.is_tablet:
            device_type = "tablet"
        elif ua.is_pc:
            device_type = "desktop"
        elif ua.is_bot:
            device_type = "bot"
        else:
            device_type = "unknown"
        
        # Build device name
        device_name = f"{ua.browser.family} on {ua.os.family}"
        if ua.device.family and ua.device.family != "Other":
            device_name = f"{ua.device.family} - {device_name}"
        
        return {
            "device_name": device_name,
            "device_type": device_type,
            "device_fingerprint": device_fingerprint,
            "user_agent": user_agent,
            "browser": f"{ua.browser.family} {ua.browser.version_string}",
            "operating_system": f"{ua.os.family} {ua.os.version_string}",
            "country": country,
            "city": city,
            "timezone": timezone
        }

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
            SessionNotFoundError: If session doesn't exist
            SessionExpiredError: If session is expired
            InvalidSessionError: If session is invalid
        """
        session = self.session_repo.find_by_session_id(session_id)
        
        if not session:
            raise SessionNotFoundError("Session not found")
        
        if not session.is_active:
            raise InvalidSessionError("Session is not active")
        
        if session.is_expired():
            raise SessionExpiredError("Session has expired")
        
        # Update activity timestamp
        if update_activity:
            self.session_repo.update_session_activity(session_id)
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "device_info": {
                "device_name": session.device_name,
                "device_type": session.device_type,
                "browser": session.browser,
                "os": session.operating_system
            },
            "location": {
                "country": session.country,
                "city": session.city,
                "ip_address": session.ip_address
            },
            "created_at": session.login_at,
            "last_activity": session.last_activity_at,
            "expires_at": session.expires_at
        }

    def check_session_timeout(
        self,
        session_id: str,
        timeout_minutes: int = 30
    ) -> bool:
        """
        Check if session has timed out due to inactivity.
        
        Args:
            session_id: Session identifier
            timeout_minutes: Inactivity timeout in minutes
            
        Returns:
            True if session has timed out
        """
        session = self.session_repo.find_by_session_id(session_id)
        
        if not session:
            return True
        
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        return session.last_activity_at < timeout_threshold

    # ==================== Session Termination ====================

    def terminate_session(
        self,
        session_id: str,
        reason: str = "User logout"
    ) -> bool:
        """
        Terminate a session and revoke tokens.
        
        Args:
            session_id: Session identifier
            reason: Termination reason
            
        Returns:
            Success status
        """
        session = self.session_repo.find_by_session_id(session_id, active_only=False)
        
        if not session:
            return False
        
        # Revoke all session tokens
        self.token_service.revoke_session_tokens(session.id, reason)
        
        # Terminate session
        self.session_repo.terminate_session(session_id, revoke_tokens=False)
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="session_terminated",
            severity="low",
            description=f"Session terminated: {reason}",
            user_id=session.user_id,
            event_data={"session_id": session_id, "reason": reason}
        )
        
        return True

    def terminate_all_sessions(
        self,
        user_id: UUID,
        except_session_id: Optional[str] = None,
        reason: str = "User requested logout from all devices"
    ) -> int:
        """
        Terminate all user sessions except optionally one.
        
        Args:
            user_id: User identifier
            except_session_id: Session to keep active
            reason: Termination reason
            
        Returns:
            Number of sessions terminated
        """
        count = self.session_repo.terminate_all_user_sessions(
            user_id=user_id,
            except_session_id=except_session_id
        )
        
        # Record security event
        if count > 0:
            self.security_event_repo.record_event(
                event_type="all_sessions_terminated",
                severity="medium",
                description=f"All user sessions terminated: {reason}",
                user_id=user_id,
                event_data={"sessions_terminated": count, "reason": reason}
            )
        
        return count

    # ==================== Session Management ====================

    def get_active_sessions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of session information
        """
        sessions = self.session_repo.find_active_sessions(user_id)
        
        return [
            {
                "session_id": session.session_id,
                "device_name": session.device_name,
                "device_type": session.device_type,
                "browser": session.browser,
                "os": session.operating_system,
                "ip_address": session.ip_address,
                "country": session.country,
                "city": session.city,
                "login_at": session.login_at,
                "last_activity": session.last_activity_at,
                "is_current": False  # Will be set by caller
            }
            for session in sessions
        ]

    def get_user_devices(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Get list of devices used by user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of device information
        """
        return self.session_repo.get_user_devices(user_id)

    def revoke_device_sessions(
        self,
        user_id: UUID,
        device_fingerprint: str
    ) -> int:
        """
        Revoke all sessions for a specific device.
        
        Args:
            user_id: User identifier
            device_fingerprint: Device fingerprint hash
            
        Returns:
            Number of sessions terminated
        """
        sessions = self.session_repo.find_sessions_by_device(
            user_id=user_id,
            device_fingerprint=device_fingerprint
        )
        
        count = 0
        for session in sessions:
            if session.is_active:
                self.terminate_session(
                    session.session_id,
                    reason="Device sessions revoked"
                )
                count += 1
        
        return count

    # ==================== Security Monitoring ====================

    def _check_session_security(
        self,
        user_id: UUID,
        ip_address: str,
        device_info: Dict[str, Any]
    ) -> None:
        """Check for security concerns when creating session."""
        # Check for concurrent locations
        if self.session_repo.detect_concurrent_locations(user_id):
            self.security_event_repo.record_event(
                event_type="concurrent_locations_detected",
                severity="medium",
                description="User has active sessions from different locations",
                user_id=user_id,
                ip_address=ip_address,
                risk_score=60
            )
        
        # Check if device is trusted
        device_fingerprint = device_info.get("device_fingerprint")
        if device_fingerprint:
            is_trusted = self.session_repo.is_trusted_device(
                user_id=user_id,
                device_fingerprint=device_fingerprint
            )
            
            if not is_trusted:
                self.security_event_repo.record_event(
                    event_type="new_device_login",
                    severity="low",
                    description="Login from new or untrusted device",
                    user_id=user_id,
                    ip_address=ip_address,
                    device_fingerprint=device_fingerprint,
                    event_data=device_info,
                    risk_score=40
                )

    def get_suspicious_sessions(
        self,
        user_id: UUID,
        risk_threshold: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get sessions with high risk scores.
        
        Args:
            user_id: User identifier
            risk_threshold: Minimum risk score
            
        Returns:
            List of suspicious sessions
        """
        sessions = self.session_repo.find_suspicious_sessions(
            user_id=user_id,
            risk_threshold=risk_threshold
        )
        
        return [
            {
                "session_id": session.session_id,
                "device_info": session.device_name,
                "ip_address": session.ip_address,
                "location": f"{session.city}, {session.country}",
                "risk_score": session.risk_score,
                "last_activity": session.last_activity_at
            }
            for session in sessions
        ]

    # ==================== Statistics ====================

    def get_session_statistics(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get session statistics for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with statistics
        """
        return self.session_repo.get_session_statistics(user_id)

    # ==================== Cleanup ====================

    def cleanup_expired_sessions(self, days_old: int = 30) -> int:
        """
        Clean up old expired sessions.
        
        Args:
            days_old: Remove sessions older than this many days
            
        Returns:
            Number of sessions cleaned
        """
        return self.session_repo.cleanup_expired_sessions(days_old)