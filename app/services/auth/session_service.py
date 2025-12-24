"""
Session management service: track, list, and revoke user sessions.

Comprehensive session lifecycle management with device tracking,
activity monitoring, and security controls.
"""

from typing import Optional, List, Dict, Any
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
from app.repositories.auth import UserSessionRepository
from app.models.auth.user_session import UserSession
from app.schemas.auth.session import (
    SessionInfo,
    SessionListResponse,
    SessionStatistics,
)

logger = logging.getLogger(__name__)


class SessionService(BaseService[UserSession, UserSessionRepository]):
    """
    Manage user sessions across devices and platforms.
    
    Features:
    - Active session tracking
    - Device fingerprinting and identification
    - Session activity monitoring
    - Selective and bulk revocation
    - Session statistics and analytics
    - Automatic cleanup of expired sessions
    """

    # Configuration
    SESSION_INACTIVITY_TIMEOUT_HOURS = 24
    MAX_CONCURRENT_SESSIONS = 5
    SESSION_CLEANUP_BATCH_SIZE = 100

    def __init__(self, repository: UserSessionRepository, db_session: Session):
        super().__init__(repository, db_session)

    # -------------------------------------------------------------------------
    # Session Listing
    # -------------------------------------------------------------------------

    def list_active(
        self,
        user_id: UUID,
        include_current: bool = True,
    ) -> ServiceResult[SessionListResponse]:
        """
        List all active sessions for a user.
        
        Args:
            user_id: User identifier
            include_current: Include current session in results
            
        Returns:
            ServiceResult with list of active sessions
        """
        try:
            sessions = self.repository.get_active_sessions(user_id)

            if not sessions:
                logger.info(f"No active sessions found for user: {user_id}")
                return ServiceResult.success(
                    SessionListResponse(
                        sessions=[],
                        total_count=0,
                        active_count=0,
                    ),
                    message="No active sessions",
                )

            # Transform to response format
            session_infos = []
            for session in sessions:
                session_info = SessionInfo(
                    id=str(session.id),
                    user_id=str(session.user_id),
                    device_info=self._parse_device_info(session.device_info),
                    ip_address=session.ip_address,
                    location=self._get_location_from_ip(session.ip_address),
                    created_at=session.created_at,
                    last_activity=session.last_activity,
                    expires_at=session.expires_at,
                    is_current=self._is_current_session(session),
                )
                session_infos.append(session_info)

            # Sort by last activity (most recent first)
            session_infos.sort(key=lambda x: x.last_activity, reverse=True)

            response = SessionListResponse(
                sessions=session_infos,
                total_count=len(session_infos),
                active_count=len([s for s in session_infos if s.is_current]),
            )

            logger.info(f"Retrieved {len(session_infos)} sessions for user: {user_id}")
            
            return ServiceResult.success(
                response,
                message=f"Found {len(session_infos)} active session(s)",
            )

        except SQLAlchemyError as e:
            logger.error(f"Database error listing sessions: {str(e)}")
            return self._handle_exception(e, "list active sessions", user_id)
        except Exception as e:
            logger.error(f"Error listing sessions: {str(e)}")
            return self._handle_exception(e, "list active sessions", user_id)

    def get_session(
        self,
        session_id: UUID,
    ) -> ServiceResult[SessionInfo]:
        """
        Get details of a specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ServiceResult with session details
        """
        try:
            session = self.repository.get_by_id(session_id)
            
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Session not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            session_info = SessionInfo(
                id=str(session.id),
                user_id=str(session.user_id),
                device_info=self._parse_device_info(session.device_info),
                ip_address=session.ip_address,
                location=self._get_location_from_ip(session.ip_address),
                created_at=session.created_at,
                last_activity=session.last_activity,
                expires_at=session.expires_at,
                is_current=self._is_current_session(session),
                is_revoked=session.is_revoked,
            )

            return ServiceResult.success(
                session_info,
                message="Session details retrieved",
            )

        except Exception as e:
            logger.error(f"Error getting session: {str(e)}")
            return self._handle_exception(e, "get session", session_id)

    # -------------------------------------------------------------------------
    # Session Revocation
    # -------------------------------------------------------------------------

    def revoke(
        self,
        session_id: UUID,
        reason: Optional[str] = None,
    ) -> ServiceResult[bool]:
        """
        Revoke a specific session.
        
        Args:
            session_id: Session identifier
            reason: Revocation reason
            
        Returns:
            ServiceResult with success status
        """
        try:
            session = self.repository.get_by_id(session_id)
            
            if not session:
                logger.warning(f"Attempt to revoke non-existent session: {session_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Session not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            if session.is_revoked:
                logger.info(f"Session already revoked: {session_id}")
                return ServiceResult.success(
                    True,
                    message="Session already revoked",
                )

            # Revoke session
            self.repository.revoke_session(session_id, reason=reason)
            self.db.commit()

            logger.info(
                f"Session revoked: {session_id} for user: {session.user_id}"
                f"{f' - Reason: {reason}' if reason else ''}"
            )
            
            return ServiceResult.success(
                True,
                message="Session revoked successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error revoking session: {str(e)}")
            return self._handle_exception(e, "revoke session", session_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error revoking session: {str(e)}")
            return self._handle_exception(e, "revoke session", session_id)

    def revoke_all(
        self,
        user_id: UUID,
        except_current: bool = False,
        reason: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Revoke all sessions for a user.
        
        Args:
            user_id: User identifier
            except_current: Keep current session active
            reason: Revocation reason
            
        Returns:
            ServiceResult with revocation count
        """
        try:
            if except_current:
                revoked_count = self.repository.revoke_all_except_current(
                    user_id=user_id,
                    reason=reason,
                )
                message = f"Revoked all sessions except current"
            else:
                revoked_count = self.repository.revoke_all_for_user(
                    user_id=user_id,
                    reason=reason,
                )
                message = "Revoked all sessions"

            self.db.commit()

            logger.info(
                f"Revoked {revoked_count} session(s) for user: {user_id}"
                f"{f' - Reason: {reason}' if reason else ''}"
            )
            
            return ServiceResult.success(
                {
                    "revoked_count": revoked_count,
                    "user_id": str(user_id),
                },
                message=f"{message} ({revoked_count} session(s))",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error revoking sessions: {str(e)}")
            return self._handle_exception(e, "revoke all sessions", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error revoking sessions: {str(e)}")
            return self._handle_exception(e, "revoke all sessions", user_id)

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    def update_activity(
        self,
        session_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Update last activity timestamp for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ServiceResult with success status
        """
        try:
            session = self.repository.get_by_id(session_id)
            
            if not session or session.is_revoked:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Session not found or revoked",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Check if session is expired
            if session.expires_at and session.expires_at < datetime.utcnow():
                self.repository.revoke_session(
                    session_id,
                    reason="Session expired",
                )
                self.db.commit()
                
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Session expired",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Update activity
            self.repository.update(session_id, {
                "last_activity": datetime.utcnow(),
            })
            self.db.commit()

            return ServiceResult.success(
                True,
                message="Session activity updated",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating session activity: {str(e)}")
            return self._handle_exception(e, "update session activity", session_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating session activity: {str(e)}")
            return self._handle_exception(e, "update session activity", session_id)

    def cleanup_expired(
        self,
        batch_size: Optional[int] = None,
    ) -> ServiceResult[Dict[str, int]]:
        """
        Clean up expired and inactive sessions.
        
        Args:
            batch_size: Number of sessions to process per batch
            
        Returns:
            ServiceResult with cleanup statistics
        """
        try:
            batch_size = batch_size or self.SESSION_CLEANUP_BATCH_SIZE
            
            # Clean up expired sessions
            expired_count = self.repository.cleanup_expired_sessions(
                batch_size=batch_size,
            )

            # Clean up inactive sessions
            inactive_threshold = datetime.utcnow() - timedelta(
                hours=self.SESSION_INACTIVITY_TIMEOUT_HOURS
            )
            inactive_count = self.repository.cleanup_inactive_sessions(
                inactive_since=inactive_threshold,
                batch_size=batch_size,
            )

            self.db.commit()

            total_cleaned = expired_count + inactive_count

            logger.info(
                f"Session cleanup completed: {total_cleaned} sessions "
                f"({expired_count} expired, {inactive_count} inactive)"
            )
            
            return ServiceResult.success(
                {
                    "expired_count": expired_count,
                    "inactive_count": inactive_count,
                    "total_count": total_cleaned,
                },
                message=f"Cleaned up {total_cleaned} session(s)",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during session cleanup: {str(e)}")
            return self._handle_exception(e, "cleanup expired sessions")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during session cleanup: {str(e)}")
            return self._handle_exception(e, "cleanup expired sessions")

    # -------------------------------------------------------------------------
    # Session Statistics
    # -------------------------------------------------------------------------

    def get_statistics(
        self,
        user_id: UUID,
    ) -> ServiceResult[SessionStatistics]:
        """
        Get session statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            ServiceResult with session statistics
        """
        try:
            sessions = self.repository.get_all_sessions(user_id)
            active_sessions = [s for s in sessions if not s.is_revoked]
            
            # Calculate statistics
            unique_ips = len(set(s.ip_address for s in active_sessions if s.ip_address))
            unique_devices = len(
                set(s.device_info for s in active_sessions if s.device_info)
            )

            # Get most recent session
            most_recent = max(
                (s.last_activity for s in active_sessions),
                default=None,
            )

            # Calculate average session duration
            session_durations = [
                (s.last_activity - s.created_at).total_seconds()
                for s in active_sessions
                if s.last_activity and s.created_at
            ]
            avg_duration = (
                sum(session_durations) / len(session_durations)
                if session_durations else 0
            )

            statistics = SessionStatistics(
                total_sessions=len(sessions),
                active_sessions=len(active_sessions),
                revoked_sessions=len(sessions) - len(active_sessions),
                unique_ip_addresses=unique_ips,
                unique_devices=unique_devices,
                most_recent_activity=most_recent,
                average_session_duration_seconds=avg_duration,
            )

            return ServiceResult.success(
                statistics,
                message="Session statistics retrieved",
            )

        except Exception as e:
            logger.error(f"Error getting session statistics: {str(e)}")
            return self._handle_exception(e, "get session statistics", user_id)

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _parse_device_info(self, device_info: Optional[str]) -> Dict[str, str]:
        """Parse device information from user agent."""
        if not device_info:
            return {
                "device_type": "Unknown",
                "browser": "Unknown",
                "os": "Unknown",
            }

        # Simplified parsing - use user-agents library in production
        parsed = {
            "device_type": "Desktop",
            "browser": "Unknown",
            "os": "Unknown",
        }

        if device_info:
            if "Mobile" in device_info or "Android" in device_info:
                parsed["device_type"] = "Mobile"
            elif "Tablet" in device_info or "iPad" in device_info:
                parsed["device_type"] = "Tablet"

            if "Chrome" in device_info:
                parsed["browser"] = "Chrome"
            elif "Firefox" in device_info:
                parsed["browser"] = "Firefox"
            elif "Safari" in device_info:
                parsed["browser"] = "Safari"
            elif "Edge" in device_info:
                parsed["browser"] = "Edge"

            if "Windows" in device_info:
                parsed["os"] = "Windows"
            elif "Mac" in device_info:
                parsed["os"] = "macOS"
            elif "Linux" in device_info:
                parsed["os"] = "Linux"
            elif "Android" in device_info:
                parsed["os"] = "Android"
            elif "iOS" in device_info:
                parsed["os"] = "iOS"

        return parsed

    def _get_location_from_ip(self, ip_address: Optional[str]) -> Optional[str]:
        """Get geographic location from IP address."""
        if not ip_address:
            return None

        # Placeholder - integrate with GeoIP service in production
        return "Unknown Location"

    def _is_current_session(self, session: UserSession) -> bool:
        """Determine if session is the current one."""
        # This would typically check against current request context
        # Placeholder implementation
        return False