"""
User Verification Service

Handles email and phone verification flows, leveraging OTP services.
Enhanced with rate limiting, verification tracking, and improved error handling.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.user import UserRepository
from app.repositories.auth import OTPTokenRepository
from app.schemas.common.enums import OTPType
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.utils.string_utils import StringHelper

logger = logging.getLogger(__name__)


class UserVerificationService:
    """
    High-level orchestration for email/phone verification.

    Responsibilities:
    - Initiate email/phone verification
    - Verify OTP codes
    - Track verification attempts
    - Rate limiting
    - Resend verification codes

    Delegates OTP generation/validation to OTPTokenRepository.
    """

    # Business rules
    MAX_VERIFICATION_ATTEMPTS = 5
    VERIFICATION_ATTEMPT_WINDOW_MINUTES = 15
    MAX_RESEND_ATTEMPTS = 3
    RESEND_COOLDOWN_SECONDS = 60

    def __init__(
        self,
        user_repo: UserRepository,
        otp_repo: OTPTokenRepository,
    ) -> None:
        self.user_repo = user_repo
        self.otp_repo = otp_repo
        self._verification_attempts: Dict[str, list] = {}  # In-memory tracking
        self._resend_attempts: Dict[str, datetime] = {}  # Last resend timestamp

    # -------------------------------------------------------------------------
    # Email Verification
    # -------------------------------------------------------------------------

    def initiate_email_verification(
        self,
        db: Session,
        user_id: UUID,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate and send an OTP for email verification.

        Args:
            db: Database session
            user_id: User identifier
            email: Optional email override (for email change verification)

        Returns:
            Dictionary with verification details

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If email is invalid or already verified
            BusinessLogicException: If rate limit exceeded
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            # Determine target email
            target_email = email or user.email
            if not target_email:
                raise ValidationException("No email address available for verification")

            # Validate email format
            if not StringHelper.is_valid_email(target_email):
                raise ValidationException("Invalid email format")

            # Check if already verified (for primary email)
            if not email and user.email_verified:
                raise BusinessLogicException("Email is already verified")

            # Normalize email
            target_email = target_email.strip().lower()

            # Check rate limiting
            self._check_rate_limit(f"email_{user_id}_{target_email}")

            # Check resend cooldown
            self._check_resend_cooldown(f"email_{user_id}_{target_email}")

            # Create OTP record
            otp_token = self.otp_repo.create_otp(
                db=db,
                otp_type=OTPType.EMAIL_VERIFICATION,
                target=target_email,
                user_id=user.id,
            )

            # Update resend timestamp
            self._resend_attempts[f"email_{user_id}_{target_email}"] = datetime.utcnow()

            logger.info(
                f"Initiated email verification for user {user_id} "
                f"(email={target_email})"
            )

            # Return verification details (actual sending should be done by notification service)
            return {
                "verification_type": "email",
                "target": target_email,
                "otp_id": str(otp_token.id),
                "expires_at": otp_token.expires_at,
                "message": "Verification code sent to email",
            }

        except (NotFoundException, ValidationException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error initiating email verification for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to initiate email verification")

    def verify_email(
        self,
        db: Session,
        user_id: UUID,
        otp_code: str,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify user's email using OTP.

        Args:
            db: Database session
            user_id: User identifier
            otp_code: OTP code to verify
            email: Optional email override (for email change verification)

        Returns:
            Dictionary with verification result

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If OTP is invalid
            BusinessLogicException: If verification fails
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            # Determine target email
            target_email = email or user.email
            if not target_email:
                raise ValidationException("No email address available for verification")

            # Normalize email
            target_email = target_email.strip().lower()

            # Track verification attempt
            attempt_key = f"email_{user_id}_{target_email}"
            self._track_verification_attempt(attempt_key)

            # Verify OTP
            is_valid = self.otp_repo.verify_otp(
                db=db,
                otp_type=OTPType.EMAIL_VERIFICATION,
                target=target_email,
                otp_code=otp_code,
            )

            if not is_valid:
                remaining = self._get_remaining_attempts(attempt_key)
                raise BusinessLogicException(
                    f"Invalid or expired verification code. "
                    f"{remaining} attempts remaining"
                )

            # Mark email as verified
            if not email:  # Verifying primary email
                self.user_repo.mark_email_verified(db, user)
                logger.info(f"Email verified for user {user_id}")
            else:  # Verifying new email (email change)
                # Update to new email
                self.user_repo.update(db, user, {"email": target_email, "email_verified": True})
                logger.info(f"Email changed and verified for user {user_id} (new={target_email})")

            # Clear attempt tracking
            self._clear_attempts(attempt_key)

            return {
                "verified": True,
                "email": target_email,
                "verified_at": datetime.utcnow(),
                "message": "Email successfully verified",
            }

        except (NotFoundException, ValidationException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error verifying email for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to verify email")

    # -------------------------------------------------------------------------
    # Phone Verification
    # -------------------------------------------------------------------------

    def initiate_phone_verification(
        self,
        db: Session,
        user_id: UUID,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate and send OTP for phone verification.

        Args:
            db: Database session
            user_id: User identifier
            phone: Optional phone override (for phone change verification)

        Returns:
            Dictionary with verification details

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If phone is invalid or already verified
            BusinessLogicException: If rate limit exceeded
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            # Determine target phone
            target_phone = phone or user.phone
            if not target_phone:
                raise ValidationException("No phone number available for verification")

            # Normalize phone
            target_phone = StringHelper.normalize_phone(target_phone)

            # Validate phone
            if len(target_phone) < 10 or len(target_phone) > 15:
                raise ValidationException("Invalid phone number format")

            # Check if already verified (for primary phone)
            if not phone and user.phone_verified:
                raise BusinessLogicException("Phone number is already verified")

            # Check rate limiting
            self._check_rate_limit(f"phone_{user_id}_{target_phone}")

            # Check resend cooldown
            self._check_resend_cooldown(f"phone_{user_id}_{target_phone}")

            # Create OTP record
            otp_token = self.otp_repo.create_otp(
                db=db,
                otp_type=OTPType.PHONE_VERIFICATION,
                target=target_phone,
                user_id=user.id,
            )

            # Update resend timestamp
            self._resend_attempts[f"phone_{user_id}_{target_phone}"] = datetime.utcnow()

            logger.info(
                f"Initiated phone verification for user {user_id} "
                f"(phone={self._mask_phone(target_phone)})"
            )

            # Return verification details (actual sending should be done by notification service)
            return {
                "verification_type": "phone",
                "target": self._mask_phone(target_phone),
                "otp_id": str(otp_token.id),
                "expires_at": otp_token.expires_at,
                "message": "Verification code sent to phone",
            }

        except (NotFoundException, ValidationException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error initiating phone verification for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to initiate phone verification")

    def verify_phone(
        self,
        db: Session,
        user_id: UUID,
        otp_code: str,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify user's phone using OTP.

        Args:
            db: Database session
            user_id: User identifier
            otp_code: OTP code to verify
            phone: Optional phone override (for phone change verification)

        Returns:
            Dictionary with verification result

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If OTP is invalid
            BusinessLogicException: If verification fails
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            # Determine target phone
            target_phone = phone or user.phone
            if not target_phone:
                raise ValidationException("No phone number available for verification")

            # Normalize phone
            target_phone = StringHelper.normalize_phone(target_phone)

            # Track verification attempt
            attempt_key = f"phone_{user_id}_{target_phone}"
            self._track_verification_attempt(attempt_key)

            # Verify OTP
            is_valid = self.otp_repo.verify_otp(
                db=db,
                otp_type=OTPType.PHONE_VERIFICATION,
                target=target_phone,
                otp_code=otp_code,
            )

            if not is_valid:
                remaining = self._get_remaining_attempts(attempt_key)
                raise BusinessLogicException(
                    f"Invalid or expired verification code. "
                    f"{remaining} attempts remaining"
                )

            # Mark phone as verified
            if not phone:  # Verifying primary phone
                self.user_repo.mark_phone_verified(db, user)
                logger.info(f"Phone verified for user {user_id}")
            else:  # Verifying new phone (phone change)
                # Update to new phone
                self.user_repo.update(db, user, {"phone": target_phone, "phone_verified": True})
                logger.info(
                    f"Phone changed and verified for user {user_id} "
                    f"(new={self._mask_phone(target_phone)})"
                )

            # Clear attempt tracking
            self._clear_attempts(attempt_key)

            return {
                "verified": True,
                "phone": self._mask_phone(target_phone),
                "verified_at": datetime.utcnow(),
                "message": "Phone successfully verified",
            }

        except (NotFoundException, ValidationException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error verifying phone for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to verify phone")

    # -------------------------------------------------------------------------
    # Resend and Status
    # -------------------------------------------------------------------------

    def resend_verification_code(
        self,
        db: Session,
        user_id: UUID,
        verification_type: str,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resend verification code.

        Args:
            db: Database session
            user_id: User identifier
            verification_type: Type ('email' or 'phone')
            target: Optional target override

        Returns:
            Dictionary with resend details

        Raises:
            ValidationException: If invalid type or cooldown not elapsed
        """
        if verification_type == "email":
            return self.initiate_email_verification(db, user_id, target)
        elif verification_type == "phone":
            return self.initiate_phone_verification(db, user_id, target)
        else:
            raise ValidationException(
                "Invalid verification type. Must be 'email' or 'phone'"
            )

    def get_verification_status(
        self,
        db: Session,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get verification status for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Dictionary with verification status

        Raises:
            NotFoundException: If user doesn't exist
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            return {
                "email": {
                    "address": user.email,
                    "verified": user.email_verified,
                    "verified_at": user.email_verified_at if hasattr(user, 'email_verified_at') else None,
                },
                "phone": {
                    "number": self._mask_phone(user.phone) if user.phone else None,
                    "verified": user.phone_verified,
                    "verified_at": user.phone_verified_at if hasattr(user, 'phone_verified_at') else None,
                },
                "is_fully_verified": user.email_verified and user.phone_verified,
            }

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error getting verification status for user {user_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to get verification status")

    # -------------------------------------------------------------------------
    # Rate Limiting and Attempt Tracking
    # -------------------------------------------------------------------------

    def _check_rate_limit(self, key: str) -> None:
        """Check if rate limit is exceeded for verification attempts."""
        if key not in self._verification_attempts:
            return

        # Get attempts within the window
        cutoff = datetime.utcnow() - timedelta(minutes=self.VERIFICATION_ATTEMPT_WINDOW_MINUTES)
        recent_attempts = [
            attempt for attempt in self._verification_attempts[key]
            if attempt > cutoff
        ]

        if len(recent_attempts) >= self.MAX_VERIFICATION_ATTEMPTS:
            raise BusinessLogicException(
                f"Too many verification attempts. "
                f"Please try again in {self.VERIFICATION_ATTEMPT_WINDOW_MINUTES} minutes"
            )

    def _check_resend_cooldown(self, key: str) -> None:
        """Check if resend cooldown has elapsed."""
        if key not in self._resend_attempts:
            return

        last_resend = self._resend_attempts[key]
        elapsed = (datetime.utcnow() - last_resend).total_seconds()

        if elapsed < self.RESEND_COOLDOWN_SECONDS:
            remaining = int(self.RESEND_COOLDOWN_SECONDS - elapsed)
            raise BusinessLogicException(
                f"Please wait {remaining} seconds before requesting a new code"
            )

    def _track_verification_attempt(self, key: str) -> None:
        """Track a verification attempt."""
        if key not in self._verification_attempts:
            self._verification_attempts[key] = []

        self._verification_attempts[key].append(datetime.utcnow())

        # Clean old attempts
        cutoff = datetime.utcnow() - timedelta(minutes=self.VERIFICATION_ATTEMPT_WINDOW_MINUTES)
        self._verification_attempts[key] = [
            attempt for attempt in self._verification_attempts[key]
            if attempt > cutoff
        ]

        # Check if limit exceeded
        if len(self._verification_attempts[key]) > self.MAX_VERIFICATION_ATTEMPTS:
            raise BusinessLogicException(
                f"Maximum verification attempts exceeded. "
                f"Please try again in {self.VERIFICATION_ATTEMPT_WINDOW_MINUTES} minutes"
            )

    def _get_remaining_attempts(self, key: str) -> int:
        """Get remaining verification attempts."""
        if key not in self._verification_attempts:
            return self.MAX_VERIFICATION_ATTEMPTS

        cutoff = datetime.utcnow() - timedelta(minutes=self.VERIFICATION_ATTEMPT_WINDOW_MINUTES)
        recent_attempts = [
            attempt for attempt in self._verification_attempts[key]
            if attempt > cutoff
        ]

        return max(0, self.MAX_VERIFICATION_ATTEMPTS - len(recent_attempts))

    def _clear_attempts(self, key: str) -> None:
        """Clear verification attempts after successful verification."""
        if key in self._verification_attempts:
            del self._verification_attempts[key]
        if key in self._resend_attempts:
            del self._resend_attempts[key]

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _mask_phone(self, phone: Optional[str]) -> Optional[str]:
        """Mask phone number for privacy (show last 4 digits)."""
        if not phone or len(phone) < 4:
            return phone

        return "*" * (len(phone) - 4) + phone[-4:]