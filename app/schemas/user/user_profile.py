# --- File: app/schemas/user/user_profile.py ---
"""
User profile update schemas with comprehensive field validation.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

from app.schemas.common.base import BaseUpdateSchema
from app.schemas.common.enums import Gender

__all__ = [
    "ProfileUpdate",
    "ProfileImageUpdate",
    "ContactInfoUpdate",
    "NotificationPreferencesUpdate",
]


class ProfileUpdate(BaseUpdateSchema):
    """
    Update user profile information.
    
    Comprehensive profile update with personal and address information.
    """

    full_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Full name",
        examples=["John Doe"],
    )
    gender: Optional[Gender] = Field(
        default=None,
        description="Gender",
    )
    date_of_birth: Optional[Date] = Field(
        default=None,
        description="Date of birth",
    )
    address_line1: Optional[str] = Field(
        default=None,
        min_length=5,
        max_length=255,
        description="Address line 1",
    )
    address_line2: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Address line 2 (optional)",
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
            # Remove excessive whitespace
            v = " ".join(v.split())
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_age(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate date of birth for reasonable age constraints."""
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

    @field_validator("city", "state", "country")
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize text fields."""
        if v is not None:
            v = v.strip()
            if v.isdigit():
                raise ValueError("Field cannot be only numbers")
            v = " ".join(v.split())
        return v


class ProfileImageUpdate(BaseUpdateSchema):
    """
    Update user profile image.
    
    Validates and updates the profile image URL.
    """

    profile_image_url: HttpUrl = Field(
        ...,
        description="Profile image URL (must be valid HTTP/HTTPS URL)",
        examples=["https://example.com/images/profile.jpg"],
    )


class ContactInfoUpdate(BaseUpdateSchema):
    """
    Update user contact information.
    
    Includes phone, email, and emergency contact details.
    """

    phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number (E.164 format recommended)",
        examples=["+919876543210"],
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email address",
        examples=["user@example.com"],
    )
    emergency_contact_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Emergency contact name",
    )
    emergency_contact_phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact phone number",
    )
    emergency_contact_relation: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Relation to emergency contact",
        examples=["Father", "Mother", "Spouse", "Friend"],
    )

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number by removing spaces and dashes."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return v

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: Optional[EmailStr]) -> Optional[EmailStr]:
        """Normalize email to lowercase and trim whitespace."""
        if v is not None:
            return EmailStr(v.lower().strip())
        return v

    @field_validator("emergency_contact_name", "emergency_contact_relation")
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize text fields."""
        if v is not None:
            v = v.strip()
            if v.isdigit():
                raise ValueError("Field cannot be only numbers")
            v = " ".join(v.split())
        return v


class NotificationPreferencesUpdate(BaseUpdateSchema):
    """
    Update user notification preferences.
    
    Granular control over different notification channels and types.
    """

    # Channel preferences
    email_notifications: bool = Field(
        default=True,
        description="Enable email notifications",
    )
    sms_notifications: bool = Field(
        default=True,
        description="Enable SMS notifications",
    )
    push_notifications: bool = Field(
        default=True,
        description="Enable push notifications",
    )

    # Notification type preferences
    booking_notifications: bool = Field(
        default=True,
        description="Receive booking-related notifications",
    )
    payment_notifications: bool = Field(
        default=True,
        description="Receive payment notifications",
    )
    complaint_notifications: bool = Field(
        default=True,
        description="Receive complaint status updates",
    )
    announcement_notifications: bool = Field(
        default=True,
        description="Receive hostel announcements",
    )
    maintenance_notifications: bool = Field(
        default=True,
        description="Receive maintenance updates",
    )
    marketing_notifications: bool = Field(
        default=False,
        description="Receive marketing communications (opt-in)",
    )

    # Advanced preferences
    digest_frequency: Optional[str] = Field(
        default=None,
        pattern=r"^(immediate|daily|weekly|never)$",
        description="Notification digest frequency",
        examples=["immediate", "daily", "weekly", "never"],
    )
    quiet_hours_start: Optional[str] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours start time (HH:MM format)",
        examples=["22:00"],
    )
    quiet_hours_end: Optional[str] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours end time (HH:MM format)",
        examples=["08:00"],
    )

    @field_validator("digest_frequency")
    @classmethod
    def normalize_digest_frequency(cls, v: Optional[str]) -> Optional[str]:
        """Normalize digest frequency to lowercase."""
        if v is not None:
            return v.lower().strip()
        return v