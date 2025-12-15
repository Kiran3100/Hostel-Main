# app/services/auth/otp_service.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, Optional
from uuid import UUID

from app.schemas.auth.otp import (
    OTPGenerateRequest,
    OTPVerifyRequest,
    OTPResponse,
    OTPVerifyResponse,
)
from app.schemas.common.enums import OTPType
from app.services.common import errors


class OTPStore(Protocol):
    """
    Abstract storage for OTP codes.

    Implementations can use Redis, a database table, in-memory cache, etc.
    """

    def save_otp(
        self,
        *,
        key: str,
        code: str,
        otp_type: OTPType,
        expires_at: datetime,
        max_attempts: int,
    ) -> None: ...

    def get_otp(self, key: str, otp_type: OTPType) -> Optional[dict]: ...

    def delete_otp(self, key: str, otp_type: OTPType) -> None: ...


class OTPService:
    """
    OTP generation & verification.

    This service does NOT decide how to send the OTP (email/SMS); it only:
    - generates codes;
    - stores them via an OTPStore;
    - verifies codes on request.
    """

    def __init__(self, store: OTPStore, ttl_seconds: int = 300, max_attempts: int = 3):
        self._store = store
        self._ttl_seconds = ttl_seconds
        self._max_attempts = max_attempts

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _make_key(self, *, user_id: UUID | None, email: str | None, phone: str | None) -> str:
        if user_id:
            return f"user:{user_id}"
        if email:
            return f"email:{email.lower()}"
        if phone:
            return f"phone:{phone}"
        # Fallback; should not generally happen if validation is correct
        raise errors.ValidationError("OTP request missing identifier")

    # ------------------------------------------------------------------ #
    # Generate
    # ------------------------------------------------------------------ #
    def generate(self, data: OTPGenerateRequest) -> OTPResponse:
        """
        Generate an OTP and store it.

        NOTE: This method does not send the OTP; caller should trigger
        notification_service.email/sms, etc.
        """
        key = self._make_key(
            user_id=data.user_id,
            email=data.email,
            phone=data.phone,
        )

        # Simple numeric 6-digit OTP
        import secrets

        code = "".join(str(secrets.randbelow(10)) for _ in range(6))
        expires_at = self._now() + timedelta(seconds=self._ttl_seconds)

        self._store.save_otp(
            key=key,
            code=code,
            otp_type=data.otp_type,
            expires_at=expires_at,
            max_attempts=self._max_attempts,
        )

        # Masked contact
        if data.email:
            sent_to = data.email
            if "@" in sent_to:
                name, domain = sent_to.split("@", 1)
                masked = name[0] + "***@" + domain
                sent_to = masked
        elif data.phone:
            sent_to = f"***{data.phone[-4:]}"
        else:
            sent_to = "unknown"

        return OTPResponse(
            message="OTP generated successfully",
            expires_in=self._ttl_seconds,
            sent_to=sent_to,
            otp_type=data.otp_type,
            max_attempts=self._max_attempts,
        )

    # ------------------------------------------------------------------ #
    # Verify
    # ------------------------------------------------------------------ #
    def verify(self, data: OTPVerifyRequest) -> OTPVerifyResponse:
        key = self._make_key(
            user_id=data.user_id,
            email=data.email,
            phone=data.phone,
        )
        record = self._store.get_otp(key, data.otp_type)
        now = self._now()

        if not record:
            return OTPVerifyResponse(
                is_valid=False,
                message="OTP not found or expired",
                verified_at=None,
                user_id=data.user_id,
            )

        if now >= record["expires_at"]:
            self._store.delete_otp(key, data.otp_type)
            return OTPVerifyResponse(
                is_valid=False,
                message="OTP expired",
                verified_at=None,
                user_id=data.user_id,
            )

        attempts = record.get("attempts", 0)
        if attempts >= record.get("max_attempts", self._max_attempts):
            self._store.delete_otp(key, data.otp_type)
            return OTPVerifyResponse(
                is_valid=False,
                message="Maximum OTP attempts exceeded",
                verified_at=None,
                user_id=data.user_id,
            )

        # Update attempts
        record["attempts"] = attempts + 1

        if data.otp_code != record["code"]:
            # Save back with incremented attempts
            self._store.save_otp(
                key=key,
                code=record["code"],
                otp_type=data.otp_type,
                expires_at=record["expires_at"],
                max_attempts=record["max_attempts"],
            )
            return OTPVerifyResponse(
                is_valid=False,
                message="Invalid OTP code",
                verified_at=None,
                user_id=data.user_id,
            )

        # Valid OTP: delete and return success
        self._store.delete_otp(key, data.otp_type)
        return OTPVerifyResponse(
            is_valid=True,
            message="OTP verified successfully",
            verified_at=now,
            user_id=data.user_id,
        )