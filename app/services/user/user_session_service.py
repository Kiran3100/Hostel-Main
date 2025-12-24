"""
User Session Service

Manages user sessions at the application level (for UI and security screens).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

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
from app.core.exceptions import ValidationException


class UserSessionService:
    """
    High-level orchestration for user sessions.

    Responsibilities:
    - List active sessions for a user
    - Create new sessions on login
    - Revoke single/all sessions
    """

    def __init__(
        self,
        session_repo: UserSessionRepository,
        session_token_repo: SessionTokenRepository,
        refresh_token_repo: RefreshTokenRepository,
    ) -> None:
        self.session_repo = session_repo
        self.session_token_repo = session_token_repo
        self.refresh_token_repo = refresh_token_repo

    def list_active_sessions(
        self,
        db: Session,
        user_id: UUID,
        current_session_id: Optional[UUID] = None,
    ) -> ActiveSessionsList:
        """
        Return all active sessions for a user (for account management screens).
        """
        sessions = self.session_repo.get_active_sessions_by_user(db, user_id)
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

    def create_session(
        self,
        db: Session,
        data: CreateSessionRequest,
    ) -> UserSession:
        """
        Create a new session. Called by auth/login flows.
        """
        payload = data.model_dump(exclude_none=True)
        session = self.session_repo.create(db, payload)
        return UserSession.model_validate(session)

    def revoke_session(
        self,
        db: Session,
        user_id: UUID,
        request: RevokeSessionRequest,
    ) -> None:
        """
        Revoke a single session by id (and its tokens).
        """
        session = self.session_repo.get_by_id(db, request.session_id)
        if not session or session.user_id != user_id:
            raise ValidationException("Session not found")

        # Revoke tokens associated with this session
        self.session_token_repo.revoke_tokens_for_session(db, session.id)
        self.refresh_token_repo.revoke_tokens_for_session(db, session.id)

        # Mark session as revoked
        self.session_repo.revoke_session(db, session)

    def revoke_all_sessions(
        self,
        db: Session,
        user_id: UUID,
        request: RevokeAllSessionsRequest,
        current_session_id: Optional[UUID] = None,
    ) -> None:
        """
        Revoke all sessions (and tokens) for a user.

        Optionally keep the current session alive.
        """
        sessions = self.session_repo.get_active_sessions_by_user(db, user_id)

        for s in sessions:
            if request.keep_current and current_session_id and s.id == current_session_id:
                continue

            self.session_token_repo.revoke_tokens_for_session(db, s.id)
            self.refresh_token_repo.revoke_tokens_for_session(db, s.id)
            self.session_repo.revoke_session(db, s)