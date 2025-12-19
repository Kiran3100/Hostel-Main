"""
User Session Repository - Session management with security tracking.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session, joinedload

from app.models.user import UserSession
from app.repositories.base.base_repository import BaseRepository


class UserSessionRepository(BaseRepository[UserSession]):
    """
    Repository for UserSession entity with security monitoring,
    device tracking, and session lifecycle management.
    """

    def __init__(self, db: Session):
        super().__init__(UserSession, db)

    # ==================== Session Retrieval ====================

    def find_by_user_id(
        self, 
        user_id: str,
        active_only: bool = True,
        limit: int = 50
    ) -> List[UserSession]:
        """
        Find all sessions for a user.
        
        Args:
            user_id: User ID
            active_only: Only return active sessions
            limit: Maximum results
            
        Returns:
            List of sessions ordered by last activity
        """
        query = self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        )
        
        if active_only:
            now = datetime.now(timezone.utc)
            query = query.filter(
                UserSession.is_revoked == False,
                UserSession.expires_at > now
            )
        
        return query.order_by(
            desc(UserSession.last_activity)
        ).limit(limit).all()

    def find_by_refresh_token_hash(
        self, 
        refresh_token_hash: str
    ) -> Optional[UserSession]:
        """
        Find session by refresh token hash.
        
        Args:
            refresh_token_hash: Hashed refresh token
            
        Returns:
            UserSession or None
        """
        return self.db.query(UserSession).filter(
            UserSession.refresh_token_hash == refresh_token_hash,
            UserSession.is_revoked == False
        ).first()

    def find_by_jti(self, jti: str) -> Optional[UserSession]:
        """
        Find session by JWT Token ID.
        
        Args:
            jti: JWT Token ID
            
        Returns:
            UserSession or None
        """
        return self.db.query(UserSession).filter(
            UserSession.access_token_jti == jti,
            UserSession.is_revoked == False
        ).first()

    def find_by_device_fingerprint(
        self, 
        user_id: str,
        device_fingerprint: str
    ) -> List[UserSession]:
        """
        Find sessions by device fingerprint.
        
        Args:
            user_id: User ID
            device_fingerprint: Device fingerprint
            
        Returns:
            List of sessions from same device
        """
        return self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.device_fingerprint == device_fingerprint
        ).order_by(desc(UserSession.created_at)).all()

    # ==================== Session Lifecycle ====================

    def create_session(
        self,
        user_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[Dict] = None,
        session_type: str = "web",
        is_remember_me: bool = False
    ) -> UserSession:
        """
        Create a new user session.
        
        Args:
            user_id: User ID
            refresh_token_hash: Hashed refresh token
            expires_at: Session expiration datetime
            ip_address: IP address
            user_agent: User agent string
            device_info: Parsed device information
            session_type: Session type (web, mobile, api)
            is_remember_me: Extended session flag
            
        Returns:
            Created UserSession
        """
        now = datetime.now(timezone.utc)
        
        session_data = {
            "user_id": user_id,
            "refresh_token_hash": refresh_token_hash,
            "expires_at": expires_at,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "device_info": device_info,
            "session_type": session_type,
            "is_remember_me": is_remember_me,
            "created_at": now,
            "last_activity": now,
            "is_revoked": False,
            "requests_count": 0
        }
        
        return self.create(session_data)

    def update_last_activity(
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
        session = self.get_by_id(session_id)
        
        session.last_activity = datetime.now(timezone.utc)
        
        if increment_requests:
            session.requests_count = (session.requests_count or 0) + 1
        
        self.db.commit()
        self.db.refresh(session)
        
        return session

    def revoke_session(
        self, 
        session_id: str,
        revoked_by: Optional[str] = None,
        reason: Optional[str] = None
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
        session = self.get_by_id(session_id)
        
        session.is_revoked = True
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_by = revoked_by
        session.revocation_reason = reason
        
        self.db.commit()
        self.db.refresh(session)
        
        return session

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
        now = datetime.now(timezone.utc)
        
        query = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False
        )
        
        if exclude_session_id:
            query = query.filter(UserSession.id != exclude_session_id)
        
        count = query.update({
            "is_revoked": True,
            "revoked_at": now,
            "revocation_reason": reason
        })
        
        self.db.commit()
        return count

    def cleanup_expired_sessions(self) -> int:
        """
        Delete expired sessions from database.
        
        Returns:
            Count of deleted sessions
        """
        now = datetime.now(timezone.utc)
        
        count = self.db.query(UserSession).filter(
            UserSession.expires_at < now
        ).delete()
        
        self.db.commit()
        return count

    # ==================== Security Monitoring ====================

    def mark_suspicious(
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
        session = self.get_by_id(session_id)
        
        session.is_suspicious = True
        
        if security_flags:
            current_events = session.security_events or []
            current_events.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "flags": security_flags
            })
            session.security_events = current_events
        
        self.db.commit()
        self.db.refresh(session)
        
        return session

    def find_suspicious_sessions(
        self, 
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[UserSession]:
        """
        Find sessions flagged as suspicious.
        
        Args:
            user_id: Optional user ID filter
            limit: Maximum results
            
        Returns:
            List of suspicious sessions
        """
        query = self.db.query(UserSession).filter(
            UserSession.is_suspicious == True
        )
        
        if user_id:
            query = query.filter(UserSession.user_id == user_id)
        
        return query.order_by(
            desc(UserSession.created_at)
        ).limit(limit).all()

    def find_sessions_by_ip(
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
        query = self.db.query(UserSession).filter(
            UserSession.ip_address == ip_address
        )
        
        if active_only:
            now = datetime.now(timezone.utc)
            query = query.filter(
                UserSession.is_revoked == False,
                UserSession.expires_at > now
            )
        
        return query.order_by(desc(UserSession.created_at)).all()

    def detect_concurrent_sessions(
        self, 
        user_id: str,
        threshold: int = 5
    ) -> bool:
        """
        Detect if user has excessive concurrent sessions.
        
        Args:
            user_id: User ID
            threshold: Maximum allowed concurrent sessions
            
        Returns:
            True if threshold exceeded
        """
        now = datetime.now(timezone.utc)
        
        count = self.db.query(func.count(UserSession.id)).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).scalar()
        
        return count > threshold

    def find_multiple_ip_sessions(
        self, 
        user_id: str,
        time_window_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find sessions from multiple IPs in short time window (potential account sharing).
        
        Args:
            user_id: User ID
            time_window_minutes: Time window in minutes
            
        Returns:
            List of potentially suspicious session groups
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)
        
        sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.created_at >= cutoff,
            UserSession.is_revoked == False
        ).all()
        
        # Group by IP
        ip_groups = {}
        for session in sessions:
            ip = session.ip_address or "unknown"
            if ip not in ip_groups:
                ip_groups[ip] = []
            ip_groups[ip].append(session)
        
        # Return if multiple IPs detected
        if len(ip_groups) > 1:
            return [
                {
                    "ip_address": ip,
                    "session_count": len(sessions),
                    "sessions": [s.id for s in sessions]
                }
                for ip, sessions in ip_groups.items()
            ]
        
        return []

    # ==================== Device Management ====================

    def find_sessions_by_device_type(
        self, 
        user_id: str,
        device_type: str
    ) -> List[UserSession]:
        """
        Find sessions by device type (desktop, mobile, tablet).
        
        Args:
            user_id: User ID
            device_type: Device type filter
            
        Returns:
            List of sessions
        """
        return self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.device_info['device_type'].astext == device_type
        ).order_by(desc(UserSession.last_activity)).all()

    def get_unique_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of unique devices for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of unique device information
        """
        sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).order_by(desc(UserSession.last_activity)).all()
        
        unique_devices = {}
        
        for session in sessions:
            fingerprint = session.device_fingerprint or session.id
            
            if fingerprint not in unique_devices:
                unique_devices[fingerprint] = {
                    "fingerprint": fingerprint,
                    "device_info": session.device_info,
                    "first_seen": session.created_at,
                    "last_seen": session.last_activity,
                    "session_count": 0,
                    "is_active": session.is_active
                }
            
            unique_devices[fingerprint]["session_count"] += 1
            
            # Update last_seen if more recent
            if session.last_activity > unique_devices[fingerprint]["last_seen"]:
                unique_devices[fingerprint]["last_seen"] = session.last_activity
                unique_devices[fingerprint]["is_active"] = session.is_active
        
        return list(unique_devices.values())

    # ==================== Analytics ====================

    def get_session_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive session statistics.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            Dictionary with session metrics
        """
        query_base = self.db.query(UserSession)
        
        if user_id:
            query_base = query_base.filter(UserSession.user_id == user_id)
        
        now = datetime.now(timezone.utc)
        
        total = query_base.count()
        
        active = query_base.filter(
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).count()
        
        revoked = query_base.filter(UserSession.is_revoked == True).count()
        
        suspicious = query_base.filter(UserSession.is_suspicious == True).count()
        
        avg_requests = self.db.query(
            func.avg(UserSession.requests_count)
        ).filter(UserSession.user_id == user_id if user_id else True).scalar()
        
        session_types = self.db.query(
            UserSession.session_type,
            func.count(UserSession.id).label('count')
        ).filter(
            UserSession.user_id == user_id if user_id else True
        ).group_by(UserSession.session_type).all()
        
        return {
            "total_sessions": total,
            "active_sessions": active,
            "revoked_sessions": revoked,
            "suspicious_sessions": suspicious,
            "average_requests_per_session": float(avg_requests) if avg_requests else 0,
            "by_type": {stype: count for stype, count in session_types}
        }

    def get_session_duration_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get session duration statistics.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            Dictionary with duration metrics
        """
        query = self.db.query(
            func.avg(
                func.extract('epoch', UserSession.last_activity - UserSession.created_at)
            ).label('avg_duration'),
            func.max(
                func.extract('epoch', UserSession.last_activity - UserSession.created_at)
            ).label('max_duration'),
            func.min(
                func.extract('epoch', UserSession.last_activity - UserSession.created_at)
            ).label('min_duration')
        )
        
        if user_id:
            query = query.filter(UserSession.user_id == user_id)
        
        result = query.first()
        
        return {
            "average_duration_seconds": float(result.avg_duration) if result.avg_duration else 0,
            "max_duration_seconds": float(result.max_duration) if result.max_duration else 0,
            "min_duration_seconds": float(result.min_duration) if result.min_duration else 0,
            "average_duration_hours": float(result.avg_duration / 3600) if result.avg_duration else 0
        }

    def find_long_running_sessions(
        self, 
        hours: int = 24,
        limit: int = 50
    ) -> List[UserSession]:
        """
        Find sessions active for extended period.
        
        Args:
            hours: Minimum hours active
            limit: Maximum results
            
        Returns:
            List of long-running sessions
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        now = datetime.now(timezone.utc)
        
        return self.db.query(UserSession).filter(
            UserSession.created_at < cutoff,
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).order_by(UserSession.created_at.asc()).limit(limit).all()

    def find_inactive_sessions(
        self, 
        hours: int = 1,
        limit: int = 100
    ) -> List[UserSession]:
        """
        Find sessions with no recent activity.
        
        Args:
            hours: Hours of inactivity
            limit: Maximum results
            
        Returns:
            List of inactive sessions
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        now = datetime.now(timezone.utc)
        
        return self.db.query(UserSession).filter(
            UserSession.last_activity < cutoff,
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).order_by(UserSession.last_activity.asc()).limit(limit).all()