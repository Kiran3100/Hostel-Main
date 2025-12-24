"""
User Service

Core user creation/update and generic operations.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.user import (
    UserRepository,
    UserAggregateRepository,
    UserSecurityRepository,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserDetail,
    UserListItem,
    UserStats,
)
from app.core.exceptions import ValidationException, BusinessLogicException


class UserService:
    """
    Core service for the User entity.

    Responsibilities:
    - Create/update/deactivate users
    - Get user by id or email/phone
    - Get list of users and stats
    """

    def __init__(
        self,
        user_repo: UserRepository,
        aggregate_repo: UserAggregateRepository,
        security_repo: UserSecurityRepository,
    ) -> None:
        self.user_repo = user_repo
        self.aggregate_repo = aggregate_repo
        self.security_repo = security_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_user(
        self,
        db: Session,
        data: UserCreate,
    ) -> UserResponse:
        """
        Create a new user.

        NOTE: Password hashing should be done via an auth/security service;
        this method assumes `password` is already hashed if needed,
        or delegates user_repo to handle hashing.
        """
        user = self.user_repo.create_user_with_password(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return UserResponse.model_validate(user)

    def update_user(
        self,
        db: Session,
        user_id: UUID,
        data: UserUpdate,
    ) -> UserResponse:
        """
        Update core user fields.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        updated = self.user_repo.update(
            db,
            user,
            data.model_dump(exclude_none=True),
        )
        return UserResponse.model_validate(updated)

    def deactivate_user(
        self,
        db: Session,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        """
        Deactivate a user account.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        self.user_repo.deactivate_user(db, user, reason)

    def activate_user(
        self,
        db: Session,
        user_id: UUID,
    ) -> None:
        """
        Reactivate a user account.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        self.user_repo.activate_user(db, user)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_user(
        self,
        db: Session,
        user_id: UUID,
    ) -> UserDetail:
        user = self.user_repo.get_full_user(db, user_id)
        if not user:
            raise ValidationException("User not found")
        return UserDetail.model_validate(user)

    def get_user_by_email(
        self,
        db: Session,
        email: str,
    ) -> Optional[UserDetail]:
        user = self.user_repo.get_by_email(db, email)
        if not user:
            return None
        full = self.user_repo.get_full_user(db, user.id)
        return UserDetail.model_validate(full)

    def get_user_by_phone(
        self,
        db: Session,
        phone: str,
    ) -> Optional[UserDetail]:
        user = self.user_repo.get_by_phone(db, phone)
        if not user:
            return None
        full = self.user_repo.get_full_user(db, user.id)
        return UserDetail.model_validate(full)

    def list_users(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 50,
    ) -> List[UserListItem]:
        users = self.user_repo.get_list(db, skip=skip, limit=limit)
        return [UserListItem.model_validate(u) for u in users]

    def get_user_stats(
        self,
        db: Session,
        user_id: UUID,
    ) -> UserStats:
        stats = self.aggregate_repo.get_user_statistics(db, user_id)
        if not stats:
            raise ValidationException("No stats available for this user")
        return UserStats.model_validate(stats)