# --- File: app/schemas/inquiry/inquiry_base.py ---
"""
Base visitor inquiry schemas with comprehensive validation.

This module defines the core inquiry schemas for managing visitor
inquiries about hostel availability and bookings.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional
from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field, computed_field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import InquirySource, InquiryStatus, RoomType

__all__ = [
    "InquiryBase",
    "InquiryCreate",
    "InquiryUpdate",
]


class InquiryBase(BaseSchema):
    """
    Base visitor inquiry schema with common fields.
    
    Contains all core inquiry information including hostel selection,
    visitor contact details, preferences, and inquiry metadata.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "visitor_name": "John Smith",
                "visitor_email": "john.smith@example.com",
                "visitor_phone": "+919876543210",
                "preferred_check_in_date": "2024-03-01",
                "stay_duration_months": 6,
                "room_type_preference": "single",
                "message": "I am interested in a single room for my college studies.",
                "inquiry_source": "website",
                "status": "new"
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Unique identifier of the hostel being inquired about",
    )

    # Visitor Contact Information
    visitor_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name of the visitor making the inquiry",
    )
    visitor_email: EmailStr = Field(
        ...,
        description="Email address for communication",
    )
    visitor_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Contact phone number (international format supported)",
    )

    # Inquiry Preferences
    preferred_check_in_date: Optional[Date] = Field(
        default=None,
        description="Preferred or approximate check-in Date",
    )
    stay_duration_months: Optional[int] = Field(
        default=None,
        ge=1,
        le=36,
        description="Intended stay duration in months (1-36)",
    )
    room_type_preference: Optional[RoomType] = Field(
        default=None,
        description="Preferred room type if any",
    )

    # Inquiry Details
    message: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Additional message or questions from visitor",
    )

    # Metadata
    inquiry_source: InquirySource = Field(
        default=InquirySource.WEBSITE,
        description="Source channel of the inquiry",
    )

    status: InquiryStatus = Field(
        default=InquiryStatus.NEW,
        description="Current status of the inquiry",
    )

    @field_validator("visitor_name")
    @classmethod
    def validate_visitor_name(cls, v: str) -> str:
        """Validate and normalize visitor name."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Visitor name must be at least 2 characters")
        
        # Check for at least one word
        if not v.split():
            raise ValueError("Visitor name cannot be empty or only whitespace")
        
        # Check for numbers (names shouldn't contain digits)
        if any(char.isdigit() for char in v):
            raise ValueError("Visitor name should not contain numbers")
        
        return v

    @field_validator("visitor_phone")
    @classmethod
    def validate_and_normalize_phone(cls, v: str) -> str:
        """Validate and normalize phone number."""
        # Remove common formatting characters
        v = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Check minimum length
        if len(v) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        
        return v

    @field_validator("preferred_check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate preferred check-in Date."""
        if v is not None:
            # Allow past dates for inquiries (they might be inquiring for future)
            # but warn if too far in the past
            days_ago = (Date.today() - v).days
            if days_ago > 7:
                # This might be an error, but we'll allow it
                # In production, you might want to log a warning
                pass
            
            # Warn if too far in the future (> 1 year)
            days_ahead = (v - Date.today()).days
            if days_ahead > 365:
                # Log warning but allow
                pass
        
        return v

    @field_validator("message")
    @classmethod
    def clean_message(cls, v: Optional[str]) -> Optional[str]:
        """Clean and validate message."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            
            # Check for excessive length
            if len(v) > 2000:
                raise ValueError("Message cannot exceed 2000 characters")
        
        return v

    @computed_field  # type: ignore[misc]
    @property
    def has_date_preference(self) -> bool:
        """Check if visitor has specified a preferred check-in Date."""
        return self.preferred_check_in_date is not None

    @computed_field  # type: ignore[misc]
    @property
    def has_duration_preference(self) -> bool:
        """Check if visitor has specified stay duration."""
        return self.stay_duration_months is not None

    @computed_field  # type: ignore[misc]
    @property
    def has_room_preference(self) -> bool:
        """Check if visitor has specified room type preference."""
        return self.room_type_preference is not None

    @computed_field  # type: ignore[misc]
    @property
    def is_detailed_inquiry(self) -> bool:
        """Check if inquiry has detailed information."""
        return (
            self.has_date_preference
            and self.has_duration_preference
            and self.has_room_preference
        )


class InquiryCreate(InquiryBase, BaseCreateSchema):
    """
    Schema for creating a new visitor inquiry.
    
    All base fields are inherited. Status is automatically set to NEW.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "visitor_name": "John Smith",
                "visitor_email": "john.smith@example.com",
                "visitor_phone": "+919876543210",
                "preferred_check_in_date": "2024-03-01",
                "stay_duration_months": 6,
                "room_type_preference": "single",
                "message": "I am interested in a single room for my college studies.",
                "inquiry_source": "website"
            }
        }
    )

    # Override status to always start as NEW
    status: InquiryStatus = Field(
        default=InquiryStatus.NEW,
        description="Status is automatically set to NEW for new inquiries",
    )

    @field_validator("status")
    @classmethod
    def validate_initial_status(cls, v: InquiryStatus) -> InquiryStatus:
        """Ensure new inquiries start with NEW status."""
        if v != InquiryStatus.NEW:
            # Force to NEW regardless of input
            return InquiryStatus.NEW
        return v


class InquiryUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing inquiry.
    
    All fields are optional, allowing partial updates.
    Typically used by admins to add notes or update contact info.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "visitor_phone": "+919876543211",
                "preferred_check_in_date": "2024-04-01",
                "stay_duration_months": 12,
                "status": "contacted"
            }
        }
    )

    # Visitor Contact (rarely updated, but allowed)
    visitor_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Update visitor name",
    )
    visitor_email: Optional[EmailStr] = Field(
        default=None,
        description="Update visitor email",
    )
    visitor_phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Update visitor phone",
    )

    # Preferences (can be updated as inquiry is refined)
    preferred_check_in_date: Optional[Date] = Field(
        default=None,
        description="Update preferred check-in Date",
    )
    stay_duration_months: Optional[int] = Field(
        default=None,
        ge=1,
        le=36,
        description="Update stay duration",
    )
    room_type_preference: Optional[RoomType] = Field(
        default=None,
        description="Update room type preference",
    )

    # Message (can be appended or updated)
    message: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Update inquiry message",
    )

    # Status (usually updated via separate status update endpoint)
    status: Optional[InquiryStatus] = Field(
        default=None,
        description="Update inquiry status",
    )

    @field_validator("visitor_name")
    @classmethod
    def validate_visitor_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate visitor name if provided."""
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Visitor name must be at least 2 characters")
            if any(char.isdigit() for char in v):
                raise ValueError("Visitor name should not contain numbers")
        return v

    @field_validator("visitor_phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number if provided."""
        if v is not None:
            v = v.replace(" ", "").replace("-", "")
            if len(v) < 10:
                raise ValueError("Phone number must be at least 10 digits")
        return v

    @field_validator("message")
    @classmethod
    def clean_message(cls, v: Optional[str]) -> Optional[str]:
        """Clean message if provided."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v