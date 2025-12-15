# --- File: app/schemas/booking/booking_request.py ---
"""
Booking request schemas for initiating bookings.

This module defines schemas for various types of booking requests
including full bookings, inquiries, and quick bookings.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import RoomType

__all__ = [
    "GuestInformation",
    "BookingRequest",
    "BookingInquiry",
    "QuickBookingRequest",
]


class GuestInformation(BaseSchema):
    """
    Guest information schema for bookings.
    
    Contains all personal, contact, and background information
    about the guest making the booking.
    """

    # Basic Information
    guest_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name of the guest",
    )
    guest_email: EmailStr = Field(
        ...,
        description="Email address for communication and booking confirmations",
    )
    guest_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Contact phone number (with optional country code)",
    )

    # ID Proof (optional at booking, required at check-in)
    guest_id_proof_type: Optional[str] = Field(
        None,
        pattern=r"^(aadhaar|passport|driving_license|voter_id|pan_card)$",
        description="Type of government-issued ID proof",
    )
    guest_id_proof_number: Optional[str] = Field(
        None,
        max_length=50,
        description="ID proof number/reference",
    )

    # Emergency Contact
    emergency_contact_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Name of emergency contact person",
    )
    emergency_contact_phone: Optional[str] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact phone number",
    )
    emergency_contact_relation: Optional[str] = Field(
        None,
        max_length=50,
        description="Relationship to emergency contact (parent, spouse, friend, etc.)",
    )

    # Institutional/Employment Details
    institution_or_company: Optional[str] = Field(
        None,
        max_length=255,
        description="Name of educational institution or employer",
    )
    designation_or_course: Optional[str] = Field(
        None,
        max_length=255,
        description="Job designation or course/program of study",
    )

    @field_validator("guest_name")
    @classmethod
    def validate_guest_name(cls, v: str) -> str:
        """Validate and clean guest name."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Guest name must be at least 2 characters long")
        
        # Ensure at least one word
        if not v.split():
            raise ValueError("Guest name cannot be empty or only whitespace")
        
        # Check for numbers (names shouldn't contain digits)
        if any(char.isdigit() for char in v):
            raise ValueError("Guest name should not contain numbers")
        
        return v

    @field_validator("guest_phone", "emergency_contact_phone")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize phone number."""
        if v is None:
            return v
        
        # Remove common formatting characters
        v = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Check minimum length
        if len(v) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        
        return v

    @model_validator(mode="after")
    def validate_id_proof_consistency(self) -> "GuestInformation":
        """Ensure ID proof type and number are provided together."""
        has_type = self.guest_id_proof_type is not None
        has_number = self.guest_id_proof_number is not None
        
        if has_type != has_number:
            raise ValueError(
                "Both ID proof type and number must be provided together, or both omitted"
            )
        
        return self

    @model_validator(mode="after")
    def validate_emergency_contact_consistency(self) -> "GuestInformation":
        """Ensure emergency contact fields are provided together."""
        has_name = self.emergency_contact_name is not None
        has_phone = self.emergency_contact_phone is not None
        
        # If either is provided, both should be provided
        if has_name or has_phone:
            if not (has_name and has_phone):
                raise ValueError(
                    "Both emergency contact name and phone must be provided together"
                )
        
        return self


class BookingRequest(BaseCreateSchema):
    """
    Complete booking request schema.
    
    Contains all information needed to create a booking including
    hostel selection, room preferences, guest details, and special requirements.
    """

    hostel_id: UUID = Field(
        ...,
        description="Unique identifier of the hostel to book",
    )

    # Booking Preferences
    room_type_requested: RoomType = Field(
        ...,
        description="Desired type of room (single, double, dormitory, etc.)",
    )
    preferred_check_in_date: Date = Field(
        ...,
        description="Desired check-in Date",
    )
    stay_duration_months: int = Field(
        ...,
        ge=1,
        le=24,
        description="Intended stay duration in months (1-24)",
    )

    # Guest Information
    guest_info: GuestInformation = Field(
        ...,
        description="Detailed guest information",
    )

    # Special Requirements
    special_requests: Optional[str] = Field(
        None,
        max_length=1000,
        description="Any special requests or requirements (quiet room, ground floor, etc.)",
    )
    dietary_preferences: Optional[str] = Field(
        None,
        max_length=255,
        description="Dietary preferences or restrictions (vegetarian, vegan, allergies, etc.)",
    )
    has_vehicle: bool = Field(
        False,
        description="Whether guest has a vehicle and needs parking",
    )
    vehicle_details: Optional[str] = Field(
        None,
        max_length=255,
        description="Vehicle details if applicable (type, registration, etc.)",
    )

    # Referral
    referral_code: Optional[str] = Field(
        None,
        max_length=50,
        description="Referral or promo code if applicable",
    )

    @field_validator("preferred_check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate check-in Date is in the future."""
        if v < Date.today():
            raise ValueError(
                f"Check-in Date ({v.strftime('%Y-%m-%d')}) cannot be in the past. "
                "Please select today or a future Date."
            )
        
        # Warn about very far future dates (> 6 months)
        days_ahead = (v - Date.today()).days
        if days_ahead > 180:
            # Log warning but don't reject
            # In production, this could trigger a notification
            pass
        
        return v

    @model_validator(mode="after")
    def validate_vehicle_consistency(self) -> "BookingRequest":
        """Ensure vehicle details are provided if has_vehicle is True."""
        if self.has_vehicle and not self.vehicle_details:
            raise ValueError(
                "Vehicle details must be provided when has_vehicle is True"
            )
        
        return self

    @field_validator("special_requests", "dietary_preferences", "vehicle_details")
    @classmethod
    def clean_optional_text(cls, v: Optional[str]) -> Optional[str]:
        """Clean optional text fields."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class BookingInquiry(BaseCreateSchema):
    """
    Simple inquiry schema for potential bookings.
    
    Used when a visitor wants to express interest without
    making a full booking commitment.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel of interest",
    )

    # Basic Contact Information
    visitor_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Name of the person inquiring",
    )
    visitor_email: EmailStr = Field(
        ...,
        description="Email address for follow-up",
    )
    visitor_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Contact phone number",
    )

    # Interest Details (all optional)
    room_type_interest: Optional[RoomType] = Field(
        None,
        description="Room type of interest",
    )
    preferred_check_in_date: Optional[Date] = Field(
        None,
        description="Approximate check-in Date if known",
    )
    message: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional message or questions",
    )

    @field_validator("visitor_name")
    @classmethod
    def validate_visitor_name(cls, v: str) -> str:
        """Validate visitor name."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("visitor_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Normalize phone number."""
        return v.replace(" ", "").replace("-", "")

    @field_validator("preferred_check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate check-in Date if provided."""
        if v is not None and v < Date.today():
            raise ValueError("Check-in Date cannot be in the past")
        return v


class QuickBookingRequest(BaseCreateSchema):
    """
    Quick booking schema with minimal required information.
    
    Used for fast-track bookings where detailed information
    can be collected later.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel to book",
    )
    room_type_requested: RoomType = Field(
        ...,
        description="Desired room type",
    )
    check_in_date: Date = Field(
        ...,
        description="Check-in Date",
    )
    duration_months: int = Field(
        ...,
        ge=1,
        le=24,
        description="Stay duration in months",
    )

    # Minimal Guest Information
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Guest name",
    )
    email: EmailStr = Field(
        ...,
        description="Guest email",
    )
    phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Guest phone",
    )

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate check-in Date."""
        if v < Date.today():
            raise ValueError(
                f"Check-in Date ({v.strftime('%Y-%m-%d')}) must be today or in the future"
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and clean name."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        if any(char.isdigit() for char in v):
            raise ValueError("Name should not contain numbers")
        return v