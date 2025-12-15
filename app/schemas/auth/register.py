# --- File: app/schemas/auth/register.py ---
"""
Registration schemas with comprehensive validation.
Pydantic v2 compliant.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import Gender, UserRole

__all__ = [
    "RegisterRequest",
    "RegisterResponse",
    "VerifyEmailRequest",
    "VerifyPhoneRequest",
    "ResendVerificationRequest",
]


class RegisterRequest(BaseCreateSchema):
    """
    User registration request with comprehensive validation.
    
    Validates email, phone, password strength, and personal information.
    """

    email: EmailStr = Field(
        ...,
        description="Email address (must be unique)",
        examples=["user@example.com"],
    )
    phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number (E.164 format recommended)",
        examples=["+919876543210"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 chars, must include uppercase, lowercase, digit)",
    )
    confirm_password: str = Field(
        ...,
        description="Password confirmation (must match password)",
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name",
        examples=["John Doe"],
    )
    role: UserRole = Field(
        default=UserRole.VISITOR,
        description="User role (defaults to visitor for security)",
    )
    gender: Optional[Gender] = Field(
        default=None,
        description="Gender (optional)",
    )
    date_of_birth: Optional[Date] = Field(
        default=None,
        description="Date of birth (optional)",
    )

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """Normalize email to lowercase."""
        return str(v).lower().strip()

    @field_validator("phone", mode="after")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        """Normalize phone number by removing spaces and dashes."""
        return v.replace(" ", "").replace("-", "").strip()

    @field_validator("full_name", mode="after")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """
        Validate and normalize full name.
        
        Ensures name contains at least 2 characters and is not just numbers.
        """
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        if v.isdigit():
            raise ValueError("Full name cannot be only numbers")
        return v

    @field_validator("date_of_birth", mode="after")
    @classmethod
    def validate_age(cls, v: Optional[Date]) -> Optional[Date]:
        """
        Validate Date of birth for reasonable age constraints.
        
        Ensures user is at least 13 years old and not born in the future.
        """
        if v is None:
            return v

        today = Date.today()
        if v >= today:
            raise ValueError("Date of birth cannot be in the future")

        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 13:
            raise ValueError("User must be at least 13 years old")
        if age > 120:
            raise ValueError("Invalid Date of birth")

        return v

    @field_validator("password", mode="after")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets strength requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "RegisterRequest":
        """Ensure password and confirm_password match."""
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @field_validator("role", mode="after")
    @classmethod
    def validate_role_restriction(cls, v: UserRole) -> UserRole:
        """
        Restrict self-registration to certain roles.
        
        Prevents users from self-registering as admin roles.
        """
        allowed_roles = {UserRole.VISITOR, UserRole.STUDENT}
        if v not in allowed_roles:
            raise ValueError(
                f"Cannot self-register with role '{v}'. "
                f"Allowed roles: {', '.join(r.value for r in allowed_roles)}"
            )
        return v


class RegisterResponse(BaseSchema):
    """
    Registration success response.
    
    Provides user details and verification requirements.
    """

    user_id: UUID = Field(
        ...,
        description="Created user ID",
    )
    email: str = Field(
        ...,
        description="Registered email address",
    )
    full_name: str = Field(
        ...,
        description="User full name",
    )
    role: UserRole = Field(
        ...,
        description="Assigned user role",
    )
    message: str = Field(
        ...,
        description="Success message",
        examples=["Registration successful. Please verify your email."],
    )
    verification_required: bool = Field(
        default=True,
        description="Whether email/phone verification is required",
    )


class VerifyEmailRequest(BaseCreateSchema):
    """
    Email verification request.
    
    Used to verify email address with code sent via email.
    """

    user_id: UUID = Field(
        ...,
        description="User ID to verify",
    )
    verification_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit verification code from email",
        examples=["123456"],
    )

    @field_validator("verification_code", mode="after")
    @classmethod
    def validate_code_format(cls, v: str) -> str:
        """Ensure verification code is exactly 6 digits."""
        if not v.isdigit():
            raise ValueError("Verification code must contain only digits")
        if len(v) != 6:
            raise ValueError("Verification code must be exactly 6 digits")
        return v


class VerifyPhoneRequest(BaseCreateSchema):
    """
    Phone verification request.
    
    Used to verify phone number with code sent via SMS.
    """

    user_id: UUID = Field(
        ...,
        description="User ID to verify",
    )
    verification_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit verification code from SMS",
        examples=["123456"],
    )

    @field_validator("verification_code", mode="after")
    @classmethod
    def validate_code_format(cls, v: str) -> str:
        """Ensure verification code is exactly 6 digits."""
        if not v.isdigit():
            raise ValueError("Verification code must contain only digits")
        if len(v) != 6:
            raise ValueError("Verification code must be exactly 6 digits")
        return v


class ResendVerificationRequest(BaseCreateSchema):
    """
    Resend verification code request.
    
    Used when user didn't receive the original verification code.
    """

    user_id: UUID = Field(
        ...,
        description="User ID for verification code resend",
    )
    verification_type: str = Field(
        ...,
        pattern=r"^(email|phone)$",
        description="Type of verification (email or phone)",
        examples=["email", "phone"],
    )

    @field_validator("verification_type", mode="after")
    @classmethod
    def normalize_verification_type(cls, v: str) -> str:
        """Normalize verification type to lowercase."""
        return v.lower().strip()