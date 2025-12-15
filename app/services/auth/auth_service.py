# app/services/auth/auth_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import UserRepository
from app.schemas.auth.login import (
    LoginRequest,
    PhoneLoginRequest,
    LoginResponse,
    UserLoginInfo,
)
from app.schemas.auth.token import (
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.schemas.common.enums import UserRole
from app.services.common import UnitOfWork, security, errors
from app.services.users import UserActivityService


class AuthService:
    """
    Authentication service:

    - Email/password login
    - Phone/password login
    - Refresh token handling

    This service assumes:
    - User model has a password hash column named `password_hash` or `hashed_password`.
    - Passwords are stored using the same hashing scheme as `security.hash_password`.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        jwt_settings: security.JWTSettings,
        user_activity_service: UserActivityService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._jwt_settings = jwt_settings
        self._user_activity = user_activity_service

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_user_password_hash(self, user) -> str:
        """
        Extract the password hash from the User model.

        Adjust this helper to match your actual column name.
        """
        pwd_hash = getattr(user, "password_hash", None) or getattr(
            user, "hashed_password", None
        )
        if not pwd_hash:
            raise errors.ServiceError(
                "User model is missing password hash. "
                "Add a 'password_hash' (or 'hashed_password') column."
            )
        return pwd_hash

    def _build_user_login_info(self, user) -> UserLoginInfo:
        return UserLoginInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.user_role,
            is_email_verified=user.is_email_verified,
            is_phone_verified=user.is_phone_verified,
            profile_image_url=user.profile_image_url,
        )

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #
    def login(
        self,
        data: LoginRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponse:
        """
        Email/password login.

        Raises:
        - ValidationError on invalid credentials
        - NotFoundError if user not found (masked as ValidationError)
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_user_repo(uow)
            user = repo.get_by_email(data.email)

            # Do not leak whether email exists; generic error
            if user is None or not user.is_active:
                raise errors.ValidationError("Invalid email or password")

            if not security.verify_password(
                data.password,
                self._get_user_password_hash(user),
            ):
                raise errors.ValidationError("Invalid email or password")

            # Update last_login_at
            user.last_login_at = self._now()  # type: ignore[attr-defined]
            uow.session.flush()  # type: ignore[union-attr]

            # Issue tokens
            access_token = security.create_access_token(
                subject=user.id,
                email=user.email,
                role=user.user_role,
                jwt_settings=self._jwt_settings,
            )
            refresh_token = security.create_refresh_token(
                subject=user.id,
                jwt_settings=self._jwt_settings,
            )

            if self._user_activity:
                self._user_activity.log_login(
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

            # Access token TTL in seconds
            expires_in = self._jwt_settings.access_token_expires_minutes * 60

            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=expires_in,
                user=self._build_user_login_info(user),
            )

    def login_with_phone(
        self,
        data: PhoneLoginRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponse:
        """
        Phone/password login.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_user_repo(uow)
            user = repo.get_by_phone(data.phone)

            if user is None or not user.is_active:
                raise errors.ValidationError("Invalid phone or password")

            if not security.verify_password(
                data.password,
                self._get_user_password_hash(user),
            ):
                raise errors.ValidationError("Invalid phone or password")

            user.last_login_at = self._now()  # type: ignore[attr-defined]
            uow.session.flush()  # type: ignore[union-attr]

            access_token = security.create_access_token(
                subject=user.id,
                email=user.email,
                role=user.user_role,
                jwt_settings=self._jwt_settings,
            )
            refresh_token = security.create_refresh_token(
                subject=user.id,
                jwt_settings=self._jwt_settings,
            )

            if self._user_activity:
                self._user_activity.log_login(
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

            expires_in = self._jwt_settings.access_token_expires_minutes * 60

            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=expires_in,
                user=self._build_user_login_info(user),
            )

    # ------------------------------------------------------------------ #
    # Token refresh
    # ------------------------------------------------------------------ #
    def refresh_token(self, data: RefreshTokenRequest) -> RefreshTokenResponse:
        """
        Given a refresh token, issue a new access (and refresh) token.

        This implementation is stateless (no server-side token store or
        revocation list). For production security, consider:
        - Saving refresh-token jti in DB or cache;
        - Supporting logout/revocation; etc.
        """
        try:
            payload = security.decode_token(data.refresh_token, self._jwt_settings)
        except security.TokenDecodeError:
            raise errors.ValidationError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise errors.ValidationError("Invalid token type for refresh")

        user_id_str = payload.get("user_id") or payload.get("sub")
        if not user_id_str:
            raise errors.ValidationError("Invalid refresh token payload")

        user_id = UUID(user_id_str)

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_user_repo(uow)
            user = repo.get(user_id)
            if user is None or not user.is_active:
                raise errors.NotFoundError("User not found or inactive")

            access_token = security.create_access_token(
                subject=user.id,
                email=user.email,
                role=user.user_role,
                jwt_settings=self._jwt_settings,
            )
            new_refresh_token = security.create_refresh_token(
                subject=user.id,
                jwt_settings=self._jwt_settings,
            )

            expires_in = self._jwt_settings.access_token_expires_minutes * 60

            return RefreshTokenResponse(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=expires_in,
            )