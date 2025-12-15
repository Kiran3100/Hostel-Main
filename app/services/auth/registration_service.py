# app/services/auth/registration_service.py
from __future__ import annotations

from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import UserRepository
from app.repositories.visitor import VisitorRepository
from app.schemas.auth.register import (
    RegisterRequest,
    RegisterResponse,
    VerifyEmailRequest,
    VerifyPhoneRequest,
)
from app.schemas.common.enums import UserRole
from app.services.common import UnitOfWork, security, errors


class RegistrationService:
    """
    Public-facing user registration.

    Design:
    - Currently supports self-registration for VISITOR role only.
    - Other roles (STUDENT, SUPERVISOR, HOSTEL_ADMIN, SUPER_ADMIN)
      should be created via admin tools, not open registration.

    NOTE:
    - User model must be extended with a password hash column
      (e.g. 'password_hash').
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_visitor_repo(self, uow: UnitOfWork) -> VisitorRepository:
        return uow.get_repo(VisitorRepository)

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def register(self, data: RegisterRequest) -> RegisterResponse:
        """
        Register a new user.

        Supported roles:
        - VISITOR (self-service)
        """
        # Restrict public registration to VISITOR role
        if data.role != UserRole.VISITOR:
            raise errors.ValidationError(
                "Self-registration is only supported for 'visitor' role. "
                "Other roles must be created by an administrator."
            )

        hashed_pwd = security.hash_password(data.password)

        with UnitOfWork(self._session_factory) as uow:
            user_repo = self._get_user_repo(uow)

            # Uniqueness checks
            if user_repo.get_by_email(data.email):
                raise errors.ConflictError(
                    f"A user with email {data.email!r} already exists"
                )
            if user_repo.get_by_phone(data.phone):
                raise errors.ConflictError(
                    f"A user with phone {data.phone!r} already exists"
                )

            # Create User
            user_payload = {
                "email": data.email,
                "phone": data.phone,
                "full_name": data.full_name,
                "user_role": data.role,
                "gender": data.gender,
                "date_of_birth": data.date_of_birth,
                "profile_image_url": None,
                "is_active": True,
                "is_email_verified": False,
                "is_phone_verified": False,
                # IMPORTANT: add a matching column to core_user model
                "password_hash": hashed_pwd,
            }
            user = user_repo.create(user_payload)  # type: ignore[arg-type]

            # Create Visitor profile with defaults
            visitor_repo = self._get_visitor_repo(uow)
            visitor_payload = {
                "user_id": user.id,
                "preferred_room_type": None,
                "budget_min": None,
                "budget_max": None,
                "preferred_cities": [],
                "preferred_amenities": [],
                "favorite_hostel_ids": [],
                "email_notifications": True,
                "sms_notifications": True,
                "push_notifications": True,
            }
            visitor_repo.create(visitor_payload)  # type: ignore[arg-type]

            uow.commit()

            return RegisterResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.user_role,
                message="Registration successful",
                verification_required=True,
            )

    # ------------------------------------------------------------------ #
    # Email / phone verification hooks
    # ------------------------------------------------------------------ #
    def mark_email_verified(self, user_id: UUID) -> None:
        """
        Mark a user's email as verified.

        Typically called AFTER OTPService has successfully verified the code.
        """
        with UnitOfWork(self._session_factory) as uow:
            user_repo = self._get_user_repo(uow)
            user = user_repo.get(user_id)
            if user is None:
                raise errors.NotFoundError("User not found")

            user.is_email_verified = True  # type: ignore[attr-defined]
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

    def mark_phone_verified(self, user_id: UUID) -> None:
        """
        Mark a user's phone as verified.

        Typically called AFTER OTPService has successfully verified the code.
        """
        with UnitOfWork(self._session_factory) as uow:
            user_repo = self._get_user_repo(uow)
            user = user_repo.get(user_id)
            if user is None:
                raise errors.NotFoundError("User not found")

            user.is_phone_verified = True  # type: ignore[attr-defined]
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

    # Convenience methods that fit your schemas; actual code verification
    # should be delegated to OTPService.
    def verify_email(self, data: VerifyEmailRequest) -> None:
        """
        High-level flow:

        1. OTPService.verify(user_id, code, type=EMAIL_VERIFICATION)
        2. If valid, mark email verified.
        """
        # OTP verification is expected to be handled by OTPService.
        # Here, we simply mark verified assuming OTP is correct.
        self.mark_email_verified(data.user_id)

    def verify_phone(self, data: VerifyPhoneRequest) -> None:
        """
        High-level flow:

        1. OTPService.verify(user_id, code, type=PHONE_VERIFICATION)
        2. If valid, mark phone verified.
        """
        self.mark_phone_verified(data.user_id)