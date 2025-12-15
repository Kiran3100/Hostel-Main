# app/services/auth/session_service.py
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Protocol, List
from uuid import UUID, uuid4

from app.schemas.user import (
    UserSession,
    SessionInfo,
    ActiveSessionsList,
)
from app.services.common import errors


class SessionStore(Protocol):
    """
    Abstract session storage.

    Implementations can use Redis, a database table, or another store.
    """

    def save_session(self, session: dict) -> None: ...
    def get_session(self, session_id: UUID) -> dict | None: ...
    def delete_session(self, session_id: UUID) -> None: ...
    def list_sessions_for_user(self, user_id: UUID) -> list[dict]: ...


class SessionService:
    """
    User sessions tracking (e.g. for "active devices" list, revocation).

    This is storage-agnostic and expects a SessionStore implementation.
    """

    def __init__(self, store: SessionStore, default_ttl_hours: int = 24) -> None:
        self._store = store
        self._default_ttl = default_ttl_hours

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def create_session(
        self,
        *,
        user_id: UUID,
        device_info: dict | None = None,
        ip_address: str | None = None,
    ) -> UserSession:
        session_id = uuid4()
        now = self._now()
        expires_at = now + timedelta(hours=self._default_ttl)

        record = {
            "id": session_id,
            "user_id": user_id,
            "device_info": device_info or {},
            "ip_address": ip_address,
            "is_revoked": False,
            "expires_at": expires_at,
            "last_activity": now,
            "created_at": now,
        }
        self._store.save_session(record)

        return UserSession(
            id=session_id,
            user_id=user_id,
            device_info=device_info,
            ip_address=ip_address,
            is_revoked=False,
            expires_at=expires_at,
            last_activity=now,
            created_at=now,
            updated_at=now,
        )

    def list_active_sessions(self, user_id: UUID) -> ActiveSessionsList:
        records = self._store.list_sessions_for_user(user_id)
        now = self._now()
        sessions: List[SessionInfo] = []

        for r in records:
            if r.get("is_revoked") or now >= r["expires_at"]:
                continue
            sessions.append(
                SessionInfo(
                    session_id=r["id"],
                    device_name=r["device_info"].get("device_name"),
                    device_type=r["device_info"].get("device_type"),
                    browser=r["device_info"].get("browser"),
                    os=r["device_info"].get("os"),
                    ip_address=r.get("ip_address"),
                    location=r["device_info"].get("location"),
                    is_current=False,  # mark in API layer based on token/jti
                    created_at=r.get("created_at", now),
                    last_activity=r.get("last_activity", now),
                    expires_at=r["expires_at"],
                )
            )

        return ActiveSessionsList(
            sessions=sessions,
            total_sessions=len(sessions),
        )

    def revoke_session(self, session_id: UUID) -> None:
        record = self._store.get_session(session_id)
        if not record:
            raise errors.NotFoundError("Session not found")

        record["is_revoked"] = True
        self._store.save_session(record)

    def revoke_all_for_user(self, user_id: UUID, *, keep_session_id: UUID | None = None) -> None:
        records = self._store.list_sessions_for_user(user_id)
        for r in records:
            if keep_session_id and r["id"] == keep_session_id:
                continue
            r["is_revoked"] = True
            self._store.save_session(r)