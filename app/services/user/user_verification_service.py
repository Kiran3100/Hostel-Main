"""
User Verification Service

Handles email and phone verification flows, leveraging OTP services.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.user import UserRepository
from app.repositories.auth import OTPTokenRepository
from app.schemas.common.enums import OTPType
from app.core.exceptions import ValidationException, BusinessLogicException
from app.utils.string_utils import StringHelper


class UserVerificationService:
    """
    High-level orchestration for email/phone verification.

    Delegates OTP generation/validation to OTPTokenRepository.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        otp_repo: OTPTokenRepository,
    ) -> None:
        self.user_repo = user_repo
        self.otp_repo = otp_repo

    # -------------------------------------------------------------------------
    # Email verification
    # -------------------------------------------------------------------------

    def initiate_email_verification(
        self,
        db: Session,
        user_id: UUID,
    ) -> None:
        """
        Generate and send an OTP for email verification.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        if not user.email:
            raise ValidationException("User has no email to verify")

        # Create OTP record
        self.otp_repo.create_otp(
            db=db,
            otp_type=OTPType.EMAIL_VERIFICATION,
            target=user.email,
            user_id=user.id,
        )

        # Actual sending should be performed by a separate OTP/notification service.

    def verify_email(
        self,
        db: Session,
        user_id: UUID,
        otp_code: str,
    ) -> None:
        """
        Verify user's email using OTP.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        if not user.email:
            raise ValidationException("User has no email to verify")

        is_valid = self.otp_repo.verify_otp(
            db=db,
            otp_type=OTPType.EMAIL_VERIFICATION,
            target=user.email,
            otp_code=otp_code,
        )

        if not is_valid:
            raise BusinessLogicException("Invalid or expired verification code")

        self.user_repo.mark_email_verified(db, user)

    # -------------------------------------------------------------------------
    # Phone verification
    # -------------------------------------------------------------------------

    def initiate_phone_verification(
        self,
        db: Session,
        user_id: UUID,
    ) -> None:
        """
        Generate and send OTP for phone verification.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        if not user.phone:
            raise ValidationException("User has no phone to verify")

        phone = StringHelper.normalize_phone(user.phone)

        self.otp_repo.create_otp(
            db=db,
            otp_type=OTPType.PHONE_VERIFICATION,
            target=phone,
            user_id=user.id,
        )

    def verify_phone(
        self,
        db: Session,
        user_id: UUID,
        otp_code: str,
    ) -> None:
        """
        Verify user's phone using OTP.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        if not user.phone:
            raise ValidationException("User has no phone to verify")

        phone = StringHelper.normalize_phone(user.phone)

        is_valid = self.otp_repo.verify_otp(
            db=db,
            otp_type=OTPType.PHONE_VERIFICATION,
            target=phone,
            otp_code=otp_code,
        )

        if not is_valid:
            raise BusinessLogicException("Invalid or expired verification code")

        self.user_repo.mark_phone_verified(db, user)