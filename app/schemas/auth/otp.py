# --- File: app/schemas/auth/otp.py ---
"""
OTP (One-Time Password) schemas with enhanced validation.
Pydantic v2 compliant.
"""

from datetime import datetime
from typing import Optional, Union
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import OTPType

__all__ = [
    "OTPGenerateRequest",
    "OTPVerifyRequest",
    "OTPResponse",
    "OTPVerifyResponse",
    "ResendOTPRequest",
]


class OTPGenerateRequest(BaseCreateSchema):
    """
    Generate OTP request.
    
    Requires at least one contact method (email or phone).
    """

    user_id: Union[UUID, None] = Field(
        default=None,
        description="User ID if authenticated context",
    )
    email: Union[EmailStr, None] = Field(
        default=None,
        description="Email address for OTP delivery",
    )
    phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number for OTP delivery",
    )
    otp_type: OTPType = Field(
        ...,
        description="OTP purpose/type",
    )

    @model_validator(mode="after")
    def validate_contact_method(self):
        """
        Ensure at least one contact method is provided.
        
        Raises:
            ValueError: If neither email nor phone is provided.
        """
        if not self.email and not self.phone:
            raise ValueError(
                "At least one contact method (email or phone) must be provided"
            )
        return self

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize phone number by removing spaces and dashes."""
        if v is not None and isinstance(v, str):
            return v.replace(" ", "").replace("-", "")
        return v


class OTPVerifyRequest(BaseCreateSchema):
    """
    Verify OTP request.
    
    Validates OTP code format and ensures contact method is provided.
    """

    user_id: Union[UUID, None] = Field(
        default=None,
        description="User ID for verification",
    )
    email: Union[EmailStr, None] = Field(
        default=None,
        description="Email address used for OTP generation",
    )
    phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number used for OTP generation",
    )
    otp_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code",
        examples=["123456"],
    )
    otp_type: OTPType = Field(
        ...,
        description="OTP purpose/type",
    )

    @model_validator(mode="after")
    def validate_contact_method(self):
        """Ensure at least one contact method is provided."""
        if not self.email and not self.phone:
            raise ValueError(
                "At least one contact method (email or phone) must be provided"
            )
        return self

    @field_validator("otp_code", mode="after")
    @classmethod
    def validate_otp_format(cls, v: str) -> str:
        """Ensure OTP is exactly 6 digits."""
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        if len(v) != 6:
            raise ValueError("OTP must be exactly 6 digits")
        return v


class OTPResponse(BaseSchema):
    """
    OTP generation response.
    
    Provides masked delivery information and expiration details.
    """

    message: str = Field(
        ...,
        description="Response message",
        examples=["OTP sent successfully"],
    )
    expires_in: int = Field(
        ...,
        gt=0,
        description="OTP expiration time in seconds",
        examples=[300],
    )
    sent_to: str = Field(
        ...,
        description="Masked email/phone where OTP was sent",
        examples=["u***@example.com", "+91******3210"],
    )
    otp_type: OTPType = Field(
        ...,
        description="OTP type/purpose",
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum verification attempts allowed",
    )


class OTPVerifyResponse(BaseSchema):
    """
    OTP verification response.
    
    Indicates verification status and provides related information.
    """

    is_valid: bool = Field(
        ...,
        description="Whether OTP verification was successful",
    )
    message: str = Field(
        ...,
        description="Verification result message",
        examples=["OTP verified successfully", "Invalid or expired OTP"],
    )
    verified_at: Union[datetime, None] = Field(
        default=None,
        description="Verification timestamp (UTC)",
    )
    user_id: Union[UUID, None] = Field(
        default=None,
        description="User ID associated with verified OTP",
    )
    remaining_attempts: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Remaining verification attempts (if failed)",
    )


class ResendOTPRequest(BaseCreateSchema):
    """
    Resend OTP request.
    
    Used when user didn't receive the original OTP.
    """

    user_id: Union[UUID, None] = Field(
        default=None,
        description="User ID for OTP resend",
    )
    email: Union[EmailStr, None] = Field(
        default=None,
        description="Email address for OTP delivery",
    )
    phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number for OTP delivery",
    )
    otp_type: OTPType = Field(
        ...,
        description="OTP purpose/type",
    )

    @model_validator(mode="after")
    def validate_contact_method(self):
        """Ensure at least one contact method is provided."""
        if not self.email and not self.phone:
            raise ValueError(
                "At least one contact method (email or phone) must be provided"
            )
        return self