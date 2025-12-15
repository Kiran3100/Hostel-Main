# app/services/users/user_profile_service.py
from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import UserRepository
from app.schemas.user.user_profile import (
    ProfileUpdate,
    ProfileImageUpdate,
    ContactInfoUpdate,
)
from app.schemas.user import UserDetail
from app.services.common import UnitOfWork, errors
from .user_service import UserService


class UserProfileService:
    """
    User profile management:

    - Update basic profile fields (name, gender, DOB, address).
    - Update contact info & emergency details.
    - Update profile image.

    Note:
    - Underlying core_user model currently has only base fields; address/
      emergency fields are applied only if/when they exist on the model.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._user_service = UserService(session_factory)

    # Helpers
    def _get_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Profile
    # ------------------------------------------------------------------ #
    def update_profile(self, user_id: UUID, data: ProfileUpdate) -> UserDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            user = repo.get(user_id)
            if user is None:
                raise errors.NotFoundError(f"User {user_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(user, field) and field != "id":
                    setattr(user, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self._user_service.get_user(user_id)

    def update_profile_image(self, user_id: UUID, data: ProfileImageUpdate) -> UserDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            user = repo.get(user_id)
            if user is None:
                raise errors.NotFoundError(f"User {user_id} not found")

            user.profile_image_url = str(data.profile_image_url)  # type: ignore[attr-defined]
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self._user_service.get_user(user_id)

    def update_contact_info(self, user_id: UUID, data: ContactInfoUpdate) -> UserDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            user = repo.get(user_id)
            if user is None:
                raise errors.NotFoundError(f"User {user_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(user, field) and field != "id":
                    setattr(user, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self._user_service.get_user(user_id)