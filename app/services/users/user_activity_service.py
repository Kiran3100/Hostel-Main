# app/services/users/user_activity_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.audit import UserActivityRepository
from app.services.common import UnitOfWork, errors


class UserActivityService:
    """
    Lightweight user activity logger:

    - log_login
    - log_logout
    - log_password_change
    - log_custom_activity

    Backed by audit_user_activity via UserActivityRepository.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_repo(self, uow: UnitOfWork) -> UserActivityRepository:
        return uow.get_repo(UserActivityRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Logging helpers
    # ------------------------------------------------------------------ #
    def log_login(
        self,
        *,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self._log(
            user_id=user_id,
            activity_type="login",
            description="User logged in",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_logout(
        self,
        *,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self._log(
            user_id=user_id,
            activity_type="logout",
            description="User logged out",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_password_change(
        self,
        *,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self._log(
            user_id=user_id,
            activity_type="password_change",
            description="User changed password",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_custom(
        self,
        *,
        user_id: UUID,
        activity_type: str,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self._log(
            user_id=user_id,
            activity_type=activity_type,
            description=description or activity_type,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # Internal
    def _log(
        self,
        *,
        user_id: UUID,
        activity_type: str,
        description: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            record = {
                "user_id": user_id,
                "activity_type": activity_type,
                "description": description,
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
            repo.create(record)  # type: ignore[arg-type]
            uow.commit()