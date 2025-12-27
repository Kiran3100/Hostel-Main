"""
User Session Service

Manages user sessions at the application level (for UI and security screens).
Enhanced with session analytics, device tracking, and security features.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.auth import (
    UserSessionRepository,
    SessionTokenRepository,
    RefreshTokenRepository,
)
from app.schemas.user import (
    UserSession,
    SessionInfo,
    ActiveSessionsList,
    RevokeSessionRequest,
    RevokeAllSessionsRequest,
    CreateSessionRequest,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class UserSessionService:
    """
    High-level orchestration for user sessions.

    Responsibilities:
    - List active sessions for a user
    - Create new sessions on login
    - Revoke single/all sessions
    - Track session activity
    - Detect suspicious sessions
    - Manage session limits
    """

    # Business rules
    MAX_SESSIONS_PER_USER = 10
    SESSION_INACTIVITY_DAYS = 30
    SUSPICIOUS_LOGIN_THRESHOLD = 3  # Different locations in short time

    def __init__(
        self,
        session_repo: UserSessionRepository,
        session_token_repo: SessionTokenRepository,
        refresh_token_repo: RefreshTokenRepository,
    ) -> None:
        self.session_repo = session_repo
        self.session_token_repo = session_token_repo
        self.refresh_token_repo = refresh_token_repo

    # -------------------------------------------------------------------------
    # Session Listing and Retrieval
    # -------------------------------------------------------------------------

    def list_active_sessions(
        self,
        db: Session,
        user_id: UUID,
        current_session_id: Optional[UUID] = None,
        include_expired: bool = False,
    ) -> ActiveSessionsList:
        """
        Return all active sessions for a user (for account management screens).

        Args:
            db: Database session
            user_id: User identifier
            current_session_id: Optional current session ID to mark
            include_expired: If True, includes expired but not revoked sessions

        Returns:
            ActiveSessionsList with session details
        """
        try:
            sessions = self.session_repo.get_active_sessions_by_user(db, user_id)

            # Filter expired sessions if needed
            if not include_expired:
                now = datetime.utcnow()
                sessions = [s for s in sessions if s.expires_at > now]

            # Sort sessions: current first, then by last activity
            sessions.sort(
                key=lambda x: (
                    x.id != current_session_id,
                    -x.last_activity.timestamp() if x.last_activity else 0,
                ),
            )

            items = []
            for s in sessions:
                items.append(
                    SessionInfo(
                        session_id=s.id,
                        device_name=s.device_name,
                        device_type=s.device_type,
                        browser=s.browser,
                        os=s.os,
                        ip_address=s.ip_address,
                        location=s.location,
                        is_current=(s.id == current_session_id),
                        created_at=s.created_at,
                        last_activity=s.last_activity,
                        expires_at=s.expires_at,
                    )
                )

            return ActiveSessionsList(
                sessions=items,
                total_sessions=len(items),
                current_session_id=current_session_id,
            )

        except SQLAlchemyError as e:
            logger.error(
                f"Database error listing sessions for user {user_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to retrieve user sessions")

    def get_session(
        self,
        db: Session,
        session_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> UserSession:
        """
        Get a specific session by ID.

        Args:
            db: Database session
            session_id: Session identifier
            user_id: Optional user ID for ownership verification

        Returns:
            UserSession schema

        Raises:
            NotFoundException: If session doesn't exist
            ValidationException: If user_id provided and doesn't match
        """
        session = self.session_repo.get_by_id(db, session_id)
        if not session:
            raise NotFoundException(f"Session {session_id} not found")

        # Verify ownership if user_id provided
        if user_id and session.user_id != user_id:
            raise ValidationException("Session does not belong to the specified user")

        return UserSession.model_validate(session)

    def get_session_analytics(
        self,
        db: Session,
        user_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get session analytics for a user.

        Args:
            db: Database session
            user_id: User identifier
            days: Number of days to analyze

        Returns:
            Dictionary with session analytics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            from app.models.auth.user_session import UserSession as SessionModel
            from sqlalchemy import func

            # Get all sessions within the period
            sessions = (
                db.query(SessionModel)
                .filter(
                    SessionModel.user_id == user_id,
                    SessionModel.created_at >= cutoff_date,
                )
                .all()
            )

            # Calculate analytics
            total_sessions = len(sessions)
            active_sessions = len([s for s in sessions if not s.revoked_at])
            
            devices = {}
            browsers = {}
            locations = {}
            
            for session in sessions:
                # Count by device type
                device_type = session.device_type or "unknown"
                devices[device_type] = devices.get(device_type, 0) + 1
                
                # Count by browser
                browser = session.browser or "unknown"
                browsers[browser] = browsers.get(browser, 0) + 1
                
                # Count by location
                location = session.location or "unknown"
                locations[location] = locations.get(location, 0) + 1

            return {
                "period_days": days,
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "revoked_sessions": total_sessions - active_sessions,
                "devices": devices,
                "browsers": browsers,
                "locations": locations,
                "most_used_device": max(devices.items(), key=lambda x: x[1])[0] if devices else None,
                "most_used_browser": max(browsers.items(), key=lambda x: x[1])[0] if browsers else None,
            }

        except SQLAlchemyError as e:
            logger.error(
                f"Database error getting session analytics for user {user_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to retrieve session analytics")

    # -------------------------------------------------------------------------
    # Session Creation
    # -------------------------------------------------------------------------

    def create_session(
        self,
        db: Session,
        data: CreateSessionRequest,
    ) -> UserSession:
        """
        Create a new session. Called by auth/login flows.

        Args:
            db: Database session
            data: Session creation data

        Returns:
            Created UserSession schema

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If session limit exceeded
        """
        # Validate session data
        self._validate_session_data(data)

        try:
            # Check session limit
            active_sessions = self.session_repo.get_active_sessions_by_user(
                db, data.user_id
            )
            
            if len(active_sessions) >= self.MAX_SESSIONS_PER_USER:
                # Auto-revoke oldest inactive session
                self._revoke_oldest_inactive_session(db, data.user_id)

            # Check for suspicious activity
            if self._is_suspicious_login(db, data):
                logger.warning(
                    f"Suspicious login detected for user {data.user_id} "
                    f"from IP {data.ip_address}"
                )
                # You might want to trigger additional security measures here

            # Create session
            payload = data.model_dump(exclude_none=True)
            session = self.session_repo.create(db, payload)

            logger.info(
                f"Created session {session.id} for user {data.user_id} "
                f"from {data.ip_address} ({data.device_type})"
            )

            return UserSession.model_validate(session)

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error creating session for user {data.user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to create session")

    def update_session_activity(
        self,
        db: Session,
        session_id: UUID,
        ip_address: Optional[str] = None,
    ) -> UserSession:
        """
        Update last activity timestamp for a session.

        Args:
            db: Database session
            session_id: Session identifier
            ip_address: Optional new IP address

        Returns:
            Updated UserSession schema

        Raises:
            NotFoundException: If session doesn't exist
        """
        try:
            session = self.session_repo.get_by_id(db, session_id)
            if not session:
                raise NotFoundException(f"Session {session_id} not found")

            update_data: Dict[str, Any] = {
                "last_activity": datetime.utcnow(),
            }

            if ip_address:
                update_data["ip_address"] = ip_address

            updated = self.session_repo.update(db, session, update_data)

            return UserSession.model_validate(updated)

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error updating session activity {session_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to update session activity")

    # -------------------------------------------------------------------------
    # Session Revocation
    # -------------------------------------------------------------------------

    def revoke_session(
        self,
        db: Session,
        user_id: UUID,
        request: RevokeSessionRequest,
    ) -> None:
        """
        Revoke a single session by id (and its tokens).

        Args:
            db: Database session
            user_id: User identifier (for ownership verification)
            request: Revocation request data

        Raises:
            NotFoundException: If session doesn't exist
            ValidationException: If session doesn't belong to user
        """
        try:
            session = self.session_repo.get_by_id(db, request.session_id)
            if not session:
                raise NotFoundException(f"Session {request.session_id} not found")

            if session.user_id != user_id:
                raise ValidationException("Session does not belong to the specified user")

            # Revoke tokens associated with this session
            self.session_token_repo.revoke_tokens_for_session(db, session.id)
            self.refresh_token_repo.revoke_tokens_for_session(db, session.id)

            # Mark session as revoked
            self.session_repo.revoke_session(db, session)

            logger.info(
                f"Revoked session {session.id} for user {user_id} - "
                f"Reason: {request.reason or 'User initiated'}"
            )

        except (NotFoundException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error revoking session {request.session_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to revoke session")

    def revoke_all_sessions(
        self,
        db: Session,
        user_id: UUID,
        request: RevokeAllSessionsRequest,
        current_session_id: Optional[UUID] = None,
    ) -> int:
        """
        Revoke all sessions (and tokens) for a user.

        Args:
            db: Database session
            user_id: User identifier
            request: Revocation request data
            current_session_id: Optional current session to preserve

        Returns:
            Number of sessions revoked

        Raises:
            BusinessLogicException: If revocation fails
        """
        try:
            sessions = self.session_repo.get_active_sessions_by_user(db, user_id)
            revoked_count = 0

            for s in sessions:
                # Skip current session if requested
                if request.keep_current and current_session_id and s.id == current_session_id:
                    continue

                # Revoke tokens
                self.session_token_repo.revoke_tokens_for_session(db, s.id)
                self.refresh_token_repo.revoke_tokens_for_session(db, s.id)
                
                # Revoke session
                self.session_repo.revoke_session(db, s)
                revoked_count += 1

            logger.info(
                f"Revoked {revoked_count} sessions for user {user_id} - "
                f"Reason: {request.reason or 'User initiated'} "
                f"(kept_current={request.keep_current})"
            )

            return revoked_count

        except SQLAlchemyError as e:
            logger.error(
                f"Database error revoking all sessions for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to revoke sessions")

    def revoke_expired_sessions(
        self,
        db: Session,
        user_id: Optional[UUID] = None,
    ) -> int:
        """
        Revoke all expired sessions (cleanup job).

        Args:
            db: Database session
            user_id: Optional user ID to limit cleanup to specific user

        Returns:
            Number of sessions revoked
        """
        try:
            from app.models.auth.user_session import UserSession as SessionModel

            now = datetime.utcnow()
            query = db.query(SessionModel).filter(
                SessionModel.expires_at < now,
                SessionModel.revoked_at.is_(None),
            )

            if user_id:
                query = query.filter(SessionModel.user_id == user_id)

            expired_sessions = query.all()
            revoked_count = 0

            for session in expired_sessions:
                # Revoke tokens
                self.session_token_repo.revoke_tokens_for_session(db, session.id)
                self.refresh_token_repo.revoke_tokens_for_session(db, session.id)
                
                # Revoke session
                self.session_repo.revoke_session(db, session)
                revoked_count += 1

            if revoked_count > 0:
                logger.info(
                    f"Revoked {revoked_count} expired sessions"
                    + (f" for user {user_id}" if user_id else "")
                )

            return revoked_count

        except SQLAlchemyError as e:
            logger.error(f"Database error revoking expired sessions: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Failed to revoke expired sessions")

    def revoke_inactive_sessions(
        self,
        db: Session,
        user_id: UUID,
        days: int = None,
    ) -> int:
        """
        Revoke sessions inactive for a specified number of days.

        Args:
            db: Database session
            user_id: User identifier
            days: Number of days (defaults to SESSION_INACTIVITY_DAYS)

        Returns:
            Number of sessions revoked
        """
        if days is None:
            days = self.SESSION_INACTIVITY_DAYS

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            from app.models.auth.user_session import UserSession as SessionModel

            inactive_sessions = (
                db.query(SessionModel)
                .filter(
                    SessionModel.user_id == user_id,
                    SessionModel.last_activity < cutoff_date,
                    SessionModel.revoked_at.is_(None),
                )
                .all()
            )

            revoked_count = 0

            for session in inactive_sessions:
                # Revoke tokens
                self.session_token_repo.revoke_tokens_for_session(db, session.id)
                self.refresh_token_repo.revoke_tokens_for_session(db, session.id)
                
                # Revoke session
                self.session_repo.revoke_session(db, session)
                revoked_count += 1

            if revoked_count > 0:
                logger.info(
                    f"Revoked {revoked_count} inactive sessions (>{days} days) "
                    f"for user {user_id}"
                )

            return revoked_count

        except SQLAlchemyError as e:
            logger.error(
                f"Database error revoking inactive sessions for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to revoke inactive sessions")

    # -------------------------------------------------------------------------
    # Security and Detection
    # -------------------------------------------------------------------------

    def detect_suspicious_sessions(
        self,
        db: Session,
        user_id: UUID,
    ) -> List[SessionInfo]:
        """
        Detect potentially suspicious sessions for a user.

        Criteria:
        - Multiple locations in short time
        - Unusual devices
        - Concurrent sessions from different locations

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            List of suspicious SessionInfo objects
        """
        try:
            sessions = self.session_repo.get_active_sessions_by_user(db, user_id)
            suspicious = []

            # Get recent sessions (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_sessions = [
                s for s in sessions 
                if s.created_at >= recent_cutoff
            ]

            # Check for multiple locations
            locations = set()
            for session in recent_sessions:
                if session.location:
                    locations.add(session.location)

            if len(locations) >= self.SUSPICIOUS_LOGIN_THRESHOLD:
                # Flag all recent sessions as suspicious
                for session in recent_sessions:
                    suspicious.append(
                        SessionInfo(
                            session_id=session.id,
                            device_name=session.device_name,
                            device_type=session.device_type,
                            browser=session.browser,
                            os=session.os,
                            ip_address=session.ip_address,
                            location=session.location,
                            is_current=False,
                            created_at=session.created_at,
                            last_activity=session.last_activity,
                            expires_at=session.expires_at,
                        )
                    )

            return suspicious

        except SQLAlchemyError as e:
            logger.error(
                f"Database error detecting suspicious sessions for user {user_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to detect suspicious sessions")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_session_data(self, data: CreateSessionRequest) -> None:
        """Validate session creation data."""
        if not data.user_id:
            raise ValidationException("User ID is required")

        if data.device_name and len(data.device_name) > 100:
            raise ValidationException("Device name must not exceed 100 characters")

        if data.ip_address and not self._is_valid_ip(data.ip_address):
            raise ValidationException("Invalid IP address format")

    def _is_valid_ip(self, ip: str) -> bool:
        """Basic IP address validation."""
        import re
        
        # IPv4 pattern
        ipv4_pattern = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
        
        # IPv6 pattern (simplified)
        ipv6_pattern = r"^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4})$"
        
        return bool(re.match(ipv4_pattern, ip) or re.match(ipv6_pattern, ip))

    def _is_suspicious_login(
        self,
        db: Session,
        data: CreateSessionRequest,
    ) -> bool:
        """
        Check if login attempt is suspicious.

        Args:
            db: Database session
            data: Session creation data

        Returns:
            True if suspicious, False otherwise
        """
        # Get recent sessions (last hour)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        
        from app.models.auth.user_session import UserSession as SessionModel

        recent_sessions = (
            db.query(SessionModel)
            .filter(
                SessionModel.user_id == data.user_id,
                SessionModel.created_at >= cutoff,
            )
            .all()
        )

        if not recent_sessions:
            return False

        # Check for different locations
        locations = set()
        for session in recent_sessions:
            if session.location:
                locations.add(session.location)

        # Add current location
        if data.location:
            locations.add(data.location)

        # Suspicious if multiple different locations in short time
        return len(locations) >= self.SUSPICIOUS_LOGIN_THRESHOLD

    def _revoke_oldest_inactive_session(
        self,
        db: Session,
        user_id: UUID,
    ) -> None:
        """Revoke the oldest inactive session for a user."""
        sessions = self.session_repo.get_active_sessions_by_user(db, user_id)
        
        if not sessions:
            return

        # Sort by last activity (oldest first)
        sessions.sort(key=lambda x: x.last_activity or x.created_at)

        # Revoke the oldest
        oldest = sessions[0]
        self.session_token_repo.revoke_tokens_for_session(db, oldest.id)
        self.refresh_token_repo.revoke_tokens_for_session(db, oldest.id)
        self.session_repo.revoke_session(db, oldest)

        logger.info(
            f"Auto-revoked oldest inactive session {oldest.id} for user {user_id} "
            f"(session limit reached)"
        )