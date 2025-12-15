# --- File: app/schemas/user/user_base.py ---
"""
User base schemas with enhanced validation and type safety.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import Gender, UserRole
from app.schemas.common.mixins import AddressMixin, EmergencyContactMixin

__all__ = [
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserAddressUpdate",
    "UserEmergencyContactUpdate",
]


class UserBase(BaseSchema):
    """
    Base user schema with core user attributes.
    
    Contains common fields shared across user operations.
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
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name",
        examples=["John Doe"],
    )
    user_role: UserRole = Field(
        ...,
        description="User role for authorization",
    )
    gender: Optional[Gender] = Field(
        default=None,
        description="Gender (optional)",
    )
    date_of_birth: Optional[Date] = Field(
        default=None,
        description="Date of birth",
    )
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
        examples=["https://example.com/images/profile.jpg"],
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> EmailStr:
        """Normalize email to lowercase and trim whitespace."""
        # In v2, we should return EmailStr type to match the field type
        return EmailStr(v.lower().strip())

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        """Normalize phone number by removing spaces and dashes."""
        return v.replace(" ", "").replace("-", "").strip()

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """
        Validate and normalize full name.
        
        Ensures name is properly formatted and contains valid characters.
        """
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        if v.isdigit():
            raise ValueError("Full name cannot be only numbers")
        # Remove excessive whitespace
        v = " ".join(v.split())
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_age(cls, v: Optional[Date]) -> Optional[Date]:
        """
        Validate user age constraints.
        
        Ensures user is at least 16 years old and date is not in the future.
        """
        if v is None:
            return v

        today = Date.today()
        
        # Check if date is in the future
        if v >= today:
            raise ValueError("Date of birth cannot be in the future")

        # Calculate age
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        
        if age < 16:
            raise ValueError("User must be at least 16 years old")
        if age > 100:
            raise ValueError("Invalid date of birth (age exceeds 100 years)")

        return v

    @field_validator("profile_image_url")
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate profile image URL format."""
        if v is not None:
            v = v.strip()
            if v and not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("Profile image URL must start with http:// or https://")
        return v


class UserCreate(UserBase, BaseCreateSchema):
    """
    Create user schema with password validation.
    
    Used for creating new user accounts.
    """

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 chars with complexity requirements)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Validate password meets strength requirements.
        
        Requirements:
        - Minimum 8 characters
        - At least one digit
        - At least one uppercase letter
        - At least one lowercase letter
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v


class UserUpdate(BaseUpdateSchema):
    """
    Update user schema with all fields optional.
    
    Used for partial updates to user profiles.
    """

    email: Optional[EmailStr] = Field(
        default=None,
        description="Email address",
    )
    phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number",
    )
    full_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Full name",
    )
    gender: Optional[Gender] = Field(
        default=None,
        description="Gender",
    )
    date_of_birth: Optional[Date] = Field(
        default=None,
        description="Date of birth",
    )
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Account active status",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: Optional[EmailStr]) -> Optional[EmailStr]:
        """Normalize email to lowercase and trim whitespace."""
        if v is not None:
            return EmailStr(v.lower().strip())
        return v

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces and dashes."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize full name."""
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Full name must be at least 2 characters")
            if v.isdigit():
                raise ValueError("Full name cannot be only numbers")
            v = " ".join(v.split())
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_age(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate user age constraints."""
        if v is not None:
            today = Date.today()
            if v >= today:
                raise ValueError("Date of birth cannot be in the future")

            age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
            if age < 16:
                raise ValueError("User must be at least 16 years old")
            if age > 100:
                raise ValueError("Invalid date of birth")
        return v

    @field_validator("profile_image_url")
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate profile image URL format."""
        if v is not None:
            v = v.strip()
            if v and not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("Profile image URL must start with http:// or https://")
        return v


class UserAddressUpdate(AddressMixin, BaseUpdateSchema):
    """
    Update user address information.
    
    Inherits address fields from AddressMixin.
    """

    # Override to make all fields optional for updates
    address_line1: Optional[str] = Field(
        default=None,
        min_length=5,
        max_length=255,
        description="Address line 1",
    )
    address_line2: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Address line 2",
    )
    city: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="City",
    )
    state: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="State",
    )
    pincode: Optional[str] = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="6-digit pincode",
    )
    country: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Country",
    )


class UserEmergencyContactUpdate(EmergencyContactMixin, BaseUpdateSchema):
    """
    Update emergency contact information.
    
    Inherits emergency contact fields from EmergencyContactMixin.
    """

    # Override to make all fields optional for updates
    emergency_contact_name: Optional[str] = Field(
        default=None,
        description="Emergency contact name",
    )
    emergency_contact_phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact phone",
    )
    emergency_contact_relation: Optional[str] = Field(
        default=None,
        description="Relation to user",
    )

    @field_validator("emergency_contact_phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces and dashes."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return v