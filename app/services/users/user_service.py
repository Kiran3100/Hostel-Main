# app/services/users/user_service.py
from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import UserRepository
from app.schemas.common.enums import UserRole
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserDetail,
    UserListItem,
)
from app.services.common import UnitOfWork, security, errors


class UserService:
    """
    Core user service (core_user):

    - Create users (admin-side; registration has its own service).
    - Update users.
    - Get user detail.
    - List/search users.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _to_response(self, u) -> UserResponse:
        return UserResponse(
            id=u.id,
            created_at=u.created_at,
            updated_at=u.updated_at,
            email=u.email,
            phone=u.phone,
            full_name=u.full_name,
            user_role=u.user_role,
            is_active=u.is_active,
            is_email_verified=u.is_email_verified,
            is_phone_verified=u.is_phone_verified,
            profile_image_url=getattr(u, "profile_image_url", None),
            last_login_at=u.last_login_at,
        )

    def _to_detail(self, u) -> UserDetail:
        # Address/emergency fields are not on core_user by default; use getattr.
        return UserDetail(
            id=u.id,
            created_at=u.created_at,
            updated_at=u.updated_at,
            email=u.email,
            phone=u.phone,
            full_name=u.full_name,
            user_role=u.user_role,
            gender=getattr(u, "gender", None),
            date_of_birth=getattr(u, "date_of_birth", None),
            profile_image_url=getattr(u, "profile_image_url", None),
            address_line1=getattr(u, "address_line1", None),
            address_line2=getattr(u, "address_line2", None),
            city=getattr(u, "city", None),
            state=getattr(u, "state", None),
            country=getattr(u, "country", None),
            pincode=getattr(u, "pincode", None),
            emergency_contact_name=getattr(u, "emergency_contact_name", None),
            emergency_contact_phone=getattr(u, "emergency_contact_phone", None),
            emergency_contact_relation=getattr(u, "emergency_contact_relation", None),
            is_active=u.is_active,
            is_email_verified=u.is_email_verified,
            is_phone_verified=u.is_phone_verified,
            email_verified_at=getattr(u, "email_verified_at", None),
            phone_verified_at=getattr(u, "phone_verified_at", None),
            last_login_at=u.last_login_at,
        )

    def _to_list_item(self, u) -> UserListItem:
        return UserListItem(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            user_role=u.user_role,
            is_active=u.is_active,
            profile_image_url=getattr(u, "profile_image_url", None),
            created_at=u.created_at,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_user(self, data: UserCreate) -> UserDetail:
        """
        Admin-driven user creation.

        Note:
        - For self-registration, use RegistrationService instead.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            if repo.get_by_email(data.email):
                raise errors.ConflictError(f"User with email {data.email!r} already exists")
            if repo.get_by_phone(data.phone):
                raise errors.ConflictError(f"User with phone {data.phone!r} already exists")

            hashed_pwd = security.hash_password(data.password)

            payload = {
                "email": data.email,
                "phone": data.phone,
                "full_name": data.full_name,
                "user_role": data.user_role,
                "gender": data.gender,
                "date_of_birth": data.date_of_birth,
                "profile_image_url": data.profile_image_url,
                "is_active": True,
                "is_email_verified": False,
                "is_phone_verified": False,
                "password_hash": hashed_pwd,
            }
            u = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self._to_detail(u)

    def update_user(self, user_id: UUID, data: UserUpdate) -> UserDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            u = repo.get(user_id)
            if u is None:
                raise errors.NotFoundError(f"User {user_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(u, field) and field != "id":
                    setattr(u, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self._to_detail(u)

    def get_user(self, user_id: UUID) -> UserDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            u = repo.get(user_id)
            if u is None:
                raise errors.NotFoundError(f"User {user_id} not found")
            return self._to_detail(u)

    # ------------------------------------------------------------------ #
    # Listing & search
    # ------------------------------------------------------------------ #
    def list_users(
        self,
        params: PaginationParams,
        *,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> PaginatedResponse[UserListItem]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            filters: Dict[str, object] = {}
            if role:
                filters["user_role"] = role
            if is_active is not None:
                filters["is_active"] = is_active

            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

            if search:
                q = search.lower()
                def _match(u) -> bool:
                    return (
                        q in (u.full_name or "").lower()
                        or q in (u.email or "").lower()
                        or q in (u.phone or "").lower()
                    )
                records = [u for u in records if _match(u)]

            # sort by created_at desc
            sorted_records = sorted(records, key=lambda u: u.created_at, reverse=True)

            start = params.offset
            end = start + params.limit
            page_users = sorted_records[start:end]

            items = [self._to_list_item(u) for u in page_users]

            return PaginatedResponse[UserListItem].create(
                items=items,
                total_items=len(sorted_records),
                page=params.page,
                page_size=params.page_size,
            )