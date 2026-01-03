"""
User profile update schemas with comprehensive field validation.
"""

from datetime import date as Date
from typing import Union, List

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

from app.schemas.common.base import BaseResponseSchema, BaseUpdateSchema
from app.schemas.common.enums import Gender

__all__ = [
    "ProfileUpdate",
    "ProfileImageUpdate",
    "ContactInfoUpdate",
    "NotificationPreferencesUpdate",
    "ProfileCompletenessResponse",
]


class ProfileUpdate(BaseUpdateSchema):
    """
    Update user profile information.
    
    Comprehensive profile update with personal and address information.
    """

    full_name: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Full name",
        examples=["John Doe"],
    )
    gender: Union[Gender, None] = Field(
        default=None,
        description="Gender",
    )
    date_of_birth: Union[Date, None] = Field(
        default=None,
        description="Date of birth",
    )
    address_line1: Union[str, None] = Field(
        default=None,
        min_length=5,
        max_length=255,
        description="Address line 1",
    )
    address_line2: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Address line 2 (optional)",
    )
    city: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="City",
    )
    state: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="State",
    )
    pincode: Union[str, None] = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="6-digit pincode",
    )
    country: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Country",
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Union[str, None]) -> Union[str, None]:
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
    def validate_age(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate Date of birth for reasonable age constraints."""
        if v is not None:
            today = Date.today()
            if v >= today:
                raise ValueError("Date of birth cannot be in the future")

            age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
            if age < 16:
                raise ValueError("User must be at least 16 years old")
            if age > 100:
                raise ValueError("Invalid Date of birth")
        return v

    @field_validator("city", "state", "country")
    @classmethod
    def validate_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
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

    phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number (E.164 format recommended)",
        examples=["+919876543210"],
    )
    email: Union[EmailStr, None] = Field(
        default=None,
        description="Email address",
        examples=["user@example.com"],
    )
    emergency_contact_name: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Emergency contact name",
    )
    emergency_contact_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact phone number",
    )
    emergency_contact_relation: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Relation to emergency contact",
        examples=["Father", "Mother", "Spouse", "Friend"],
    )

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def normalize_phone(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize phone number by removing spaces and dashes."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return v

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: Union[EmailStr, None]) -> Union[EmailStr, None]:
        """Normalize email to lowercase and trim whitespace."""
        if v is not None:
            return EmailStr(v.lower().strip())
        return v

    @field_validator("emergency_contact_name", "emergency_contact_relation")
    @classmethod
    def validate_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
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
    email_notifications: Union[bool, None] = Field(
        default=None,
        description="Enable email notifications",
    )
    sms_notifications: Union[bool, None] = Field(
        default=None,
        description="Enable SMS notifications",
    )
    push_notifications: Union[bool, None] = Field(
        default=None,
        description="Enable push notifications",
    )

    # Notification type preferences
    booking_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive booking-related notifications",
    )
    payment_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive payment notifications",
    )
    complaint_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive complaint status updates",
    )
    announcement_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive hostel announcements",
    )
    maintenance_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive maintenance updates",
    )
    marketing_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive marketing communications (opt-in)",
    )

    # Advanced preferences
    digest_frequency: Union[str, None] = Field(
        default=None,
        pattern=r"^(immediate|daily|weekly|never)$",
        description="Notification digest frequency",
        examples=["immediate", "daily", "weekly", "never"],
    )
    quiet_hours_start: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours start time (HH:MM format)",
        examples=["22:00"],
    )
    quiet_hours_end: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours end time (HH:MM format)",
        examples=["08:00"],
    )

    @field_validator("digest_frequency")
    @classmethod
    def normalize_digest_frequency(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize digest frequency to lowercase."""
        if v is not None:
            return v.lower().strip()
        return v


class ProfileCompletenessResponse(BaseResponseSchema):
    """
    Profile completeness analysis response.
    
    Provides metrics about profile completion and suggestions.
    """

    completion_percentage: float = Field(
        ...,
        ge=0,
        le=100,
        description="Profile completion percentage (0-100)",
    )
    total_fields: int = Field(
        ...,
        ge=0,
        description="Total number of profile fields",
    )
    completed_fields: int = Field(
        ...,
        ge=0,
        description="Number of completed profile fields",
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="List of missing/incomplete field names",
        examples=[["phone", "address", "emergency_contact"]],
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions for improving profile",
        examples=[["Add a profile photo", "Complete your address information"]],
    )
    is_complete: bool = Field(
        ...,
        description="Whether profile meets minimum completion requirements",
    )