# app/services/auth/password_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import UserRepository
from app.schemas.auth.password import (
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordStrengthCheck,
    PasswordStrengthResponse,
)
from app.services.common import UnitOfWork, security, errors
from app.services.users import UserActivityService


class PasswordService:
    """
    Password management service:

    - Change password (authenticated user).
    - Password strength evaluation.
    - Hooks for reset flows (token/OTP-based) can be added later.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        user_activity_service: UserActivityService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._user_activity = user_activity_service

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_user_password_hash(self, user) -> str:
        pwd_hash = getattr(user, "password_hash", None) or getattr(
            user, "hashed_password", None
        )
        if not pwd_hash:
            raise errors.ServiceError(
                "User model missing password hash column "
                "(expected 'password_hash' or 'hashed_password')."
            )
        return pwd_hash

    # ------------------------------------------------------------------ #
    # Change password (authenticated)
    # ------------------------------------------------------------------ #
    def change_password(
        self,
        user_id: UUID,
        data: PasswordChangeRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> PasswordChangeResponse:
        """
        Change password for an authenticated user.

        Validates:
        - current_password matches existing hash
        - new_password != current_password (enforced by schema validators)
        """
        with UnitOfWork(self._session_factory) as uow:
            user_repo = self._get_user_repo(uow)
            user = user_repo.get(user_id)
            if user is None or not user.is_active:
                raise errors.NotFoundError("User not found or inactive")

            existing_hash = self._get_user_password_hash(user)
            if not security.verify_password(data.current_password, existing_hash):
                raise errors.ValidationError("Current password is incorrect")

            new_hash = security.hash_password(data.new_password)
            # Assign to the correct attribute
            if hasattr(user, "password_hash"):
                setattr(user, "password_hash", new_hash)
            elif hasattr(user, "hashed_password"):
                setattr(user, "hashed_password", new_hash)
            else:
                raise errors.ServiceError(
                    "User model missing password hash attribute "
                    "(expected 'password_hash' or 'hashed_password')."
                )

            # Optionally update last_login_at or a last_password_change_at column
            if hasattr(user, "updated_at"):
                # timestamp column is already auto-managed; no need to modify.
                pass

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        if self._user_activity:
            self._user_activity.log_password_change(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return PasswordChangeResponse(
            message="Password changed successfully",
            user_id=user_id,
        )

    # ------------------------------------------------------------------ #
    # Password strength evaluation
    # ------------------------------------------------------------------ #
    def evaluate_strength(self, data: PasswordStrengthCheck) -> PasswordStrengthResponse:
        """
        Provide a simple password strength evaluation.

        This is independent of DB and can be used client-side as a helper.
        """
        pwd = data.password
        suggestions: list[str] = []
        score = 0

        has_min_length = len(pwd) >= 8
        has_digit = any(c.isdigit() for c in pwd)
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/\\'" for c in pwd)

        # Basic scoring
        if has_min_length:
            score += 1
        if has_digit:
            score += 1
        if has_upper:
            score += 1
        if has_lower:
            score += 1
        if has_special:
            score += 1

        if not has_min_length:
            suggestions.append("Use at least 8 characters.")
        if not has_digit:
            suggestions.append("Add at least one digit.")
        if not has_upper:
            suggestions.append("Add at least one uppercase letter.")
        if not has_lower:
            suggestions.append("Add at least one lowercase letter.")
        if not has_special:
            suggestions.append("Add at least one special character.")

        if score <= 2:
            strength_label = "weak"
        elif score == 3:
            strength_label = "medium"
        elif score == 4:
            strength_label = "strong"
        else:
            strength_label = "very_strong"

        return PasswordStrengthResponse(
            score=score,
            strength=strength_label,
            has_minimum_length=has_min_length,
            has_uppercase=has_upper,
            has_lowercase=has_lower,
            has_digit=has_digit,
            has_special_char=has_special,
            suggestions=suggestions,
        )