"""
Booking base schemas with comprehensive validation.

This module defines the core booking schemas including creation,
updates, and base validation logic for the booking lifecycle.
"""

from datetime import date as Date, timedelta
from decimal import Decimal
from typing import Union
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import BookingSource, BookingStatus, RoomType

__all__ = [
    "BookingBase",
    "BookingCreate",
    "BookingUpdate",
]


class BookingBase(BaseSchema):
    """
    Base booking schema with common fields and validation.
    
    Contains all core booking information including visitor details,
    hostel selection, room preferences, pricing, and special requirements.
    """

    visitor_id: UUID = Field(
        ...,
        description="Unique identifier of the visitor/guest making the booking",
    )
    hostel_id: UUID = Field(
        ...,
        description="Unique identifier of the hostel being booked",
    )

    # Booking Details
    room_type_requested: RoomType = Field(
        ...,
        description="Type of room requested (single, double, dormitory, etc.)",
    )
    preferred_check_in_date: Date = Field(
        ...,
        description="Preferred check-in Date",
    )
    stay_duration_months: int = Field(
        ...,
        ge=1,
        le=24,
        description="Duration of stay in months (1-24)",
    )

    # Pricing Information - decimal_places removed, precision handled via quantization
    quoted_rent_monthly: Decimal = Field(
        ...,
        ge=0,
        description="Monthly rent amount quoted at time of booking (precision: 2 decimal places)",
    )
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total amount for entire stay (monthly rent × duration, precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        Decimal("0.00"),
        ge=0,
        description="Refundable security deposit amount (precision: 2 decimal places)",
    )
    advance_amount: Decimal = Field(
        Decimal("0.00"),
        ge=0,
        description="Advance payment amount required (precision: 2 decimal places)",
    )

    # Special Requirements
    special_requests: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Any special requests or requirements from the guest",
    )
    dietary_preferences: Union[str, None] = Field(
        None,
        max_length=255,
        description="Dietary preferences (vegetarian, vegan, etc.)",
    )
    has_vehicle: bool = Field(
        False,
        description="Whether guest has a vehicle requiring parking",
    )
    vehicle_details: Union[str, None] = Field(
        None,
        max_length=255,
        description="Vehicle details (type, registration number)",
    )

    # Booking Source
    source: BookingSource = Field(
        BookingSource.WEBSITE,
        description="Source of the booking (website, app, referral, etc.)",
    )
    referral_code: Union[str, None] = Field(
        None,
        max_length=50,
        description="Referral code used during booking",
    )

    @field_validator("preferred_check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate check-in Date is not in the past."""
        if v < Date.today():
            raise ValueError(
                f"Check-in Date ({v}) cannot be in the past. "
                f"Please select today or a future Date."
            )
        
        # Warn if check-in is too far in the future (e.g., > 6 months)
        max_advance_days = 180  # 6 months
        if (v - Date.today()).days > max_advance_days:
            # Note: This is a warning, not an error
            # Could be logged or handled differently in production
            pass
        
        return v

    @field_validator("quoted_rent_monthly")
    @classmethod
    def validate_rent_amount(cls, v: Decimal) -> Decimal:
        """Validate rent amount is reasonable and quantize to 2 decimal places."""
        # Quantize to 2 decimal places
        v = v.quantize(Decimal("0.01"))
        
        if v <= 0:
            raise ValueError("Monthly rent must be greater than zero")
        
        # Sanity check: Rent should typically be between ₹1,000 and ₹1,00,000
        min_rent = Decimal("1000.00")
        max_rent = Decimal("100000.00")
        
        if v < min_rent:
            raise ValueError(
                f"Monthly rent (₹{v}) seems too low. Minimum is ₹{min_rent}"
            )
        if v > max_rent:
            raise ValueError(
                f"Monthly rent (₹{v}) seems too high. Maximum is ₹{max_rent}"
            )
        
        return v

    @field_validator("total_amount", "security_deposit", "advance_amount")
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_total_amount(self) -> "BookingBase":
        """Validate total amount calculation."""
        expected_total = self.quoted_rent_monthly * self.stay_duration_months
        
        # Allow small floating-point differences (up to ₹1)
        tolerance = Decimal("1.00")
        difference = abs(self.total_amount - expected_total)
        
        if difference > tolerance:
            raise ValueError(
                f"Total amount (₹{self.total_amount}) does not match "
                f"expected calculation (₹{expected_total:.2f} = "
                f"₹{self.quoted_rent_monthly} × {self.stay_duration_months} months). "
                f"Difference: ₹{difference:.2f}"
            )
        
        return self

    @model_validator(mode="after")
    def validate_advance_amount(self) -> "BookingBase":
        """Validate advance amount is reasonable."""
        if self.advance_amount > self.total_amount:
            raise ValueError(
                f"Advance amount (₹{self.advance_amount}) cannot exceed "
                f"total amount (₹{self.total_amount})"
            )
        
        # Typically, advance is 10-50% of total
        min_advance_percent = Decimal("0.10")  # 10%
        max_advance_percent = Decimal("0.50")  # 50%
        
        if self.advance_amount > 0:
            advance_percent = self.advance_amount / self.total_amount
            
            if advance_percent < min_advance_percent:
                # Warning: Less than typical advance
                pass
            elif advance_percent > max_advance_percent:
                raise ValueError(
                    f"Advance amount (₹{self.advance_amount}) is "
                    f"{advance_percent * 100:.1f}% of total, which exceeds "
                    f"the maximum allowed ({max_advance_percent * 100}%)"
                )
        
        return self

    @model_validator(mode="after")
    def validate_vehicle_details(self) -> "BookingBase":
        """Validate vehicle details are provided if has_vehicle is True."""
        if self.has_vehicle and not self.vehicle_details:
            raise ValueError(
                "Vehicle details must be provided when has_vehicle is True"
            )
        
        return self

    @field_validator("special_requests", "dietary_preferences")
    @classmethod
    def clean_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean and validate text fields."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v

    @computed_field
    @property
    def expected_check_out_date(self) -> Date:
        """Calculate expected check-out Date based on duration."""
        # Approximate: 1 month = 30 days
        return self.preferred_check_in_date + timedelta(
            days=self.stay_duration_months * 30
        )

    @computed_field
    @property
    def days_until_check_in(self) -> int:
        """Calculate days remaining until check-in."""
        return (self.preferred_check_in_date - Date.today()).days

    @computed_field
    @property
    def is_long_term_booking(self) -> bool:
        """Check if this is a long-term booking (>= 6 months)."""
        return self.stay_duration_months >= 6


class BookingCreate(BookingBase, BaseCreateSchema):
    """
    Schema for creating a new booking.
    
    Includes all base booking fields plus guest information
    that must be provided at booking time.
    """

    # Guest Information (embedded for convenience)
    guest_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name of the guest",
    )
    guest_email: EmailStr = Field(
        ...,
        description="Guest email address for communication",
    )
    guest_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Guest contact phone number (international format supported)",
    )

    # Optional ID Proof (can be provided later)
    guest_id_proof_type: Union[str, None] = Field(
        None,
        pattern=r"^(aadhaar|passport|driving_license|voter_id|pan_card)$",
        description="Type of ID proof",
    )
    guest_id_proof_number: Union[str, None] = Field(
        None,
        max_length=50,
        description="ID proof number",
    )

    # Emergency Contact Information
    emergency_contact_name: Union[str, None] = Field(
        None,
        max_length=255,
        description="Emergency contact person name",
    )
    emergency_contact_phone: Union[str, None] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact phone number",
    )
    emergency_contact_relation: Union[str, None] = Field(
        None,
        max_length=50,
        description="Relation to emergency contact",
    )

    # Institutional/Employment Details
    institution_or_company: Union[str, None] = Field(
        None,
        max_length=255,
        description="Name of institution or company",
    )
    designation_or_course: Union[str, None] = Field(
        None,
        max_length=255,
        description="Designation (if employed) or course (if student)",
    )

    @field_validator("guest_name")
    @classmethod
    def validate_guest_name(cls, v: str) -> str:
        """Validate and normalize guest name."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Guest name must be at least 2 characters")
        
        # Check for minimum name parts (at least first name)
        name_parts = v.split()
        if len(name_parts) < 1:
            raise ValueError("Please provide at least a first name")
        
        # Check for invalid characters
        if any(char.isdigit() for char in v):
            raise ValueError("Guest name should not contain numbers")
        
        return v

    @field_validator("guest_phone")
    @classmethod
    def validate_guest_phone(cls, v: str) -> str:
        """Validate and normalize phone number."""
        # Remove spaces and dashes
        v = v.replace(" ", "").replace("-", "")
        
        # Ensure it's not too short
        if len(v) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        
        return v

    @model_validator(mode="after")
    def validate_emergency_contact(self) -> "BookingCreate":
        """Validate emergency contact consistency."""
        has_emergency_name = self.emergency_contact_name is not None
        has_emergency_phone = self.emergency_contact_phone is not None
        
        # If one is provided, encourage both
        if has_emergency_name and not has_emergency_phone:
            raise ValueError(
                "Emergency contact phone is required when name is provided"
            )
        if has_emergency_phone and not has_emergency_name:
            raise ValueError(
                "Emergency contact name is required when phone is provided"
            )
        
        return self

    @model_validator(mode="after")
    def validate_id_proof(self) -> "BookingCreate":
        """Validate ID proof consistency."""
        has_id_type = self.guest_id_proof_type is not None
        has_id_number = self.guest_id_proof_number is not None
        
        if has_id_type and not has_id_number:
            raise ValueError("ID proof number is required when type is provided")
        if has_id_number and not has_id_type:
            raise ValueError("ID proof type is required when number is provided")
        
        return self


class BookingUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing booking.
    
    All fields are optional, allowing partial updates.
    Only admin-modifiable fields are included.
    """

    # Booking Details (modifiable)
    room_type_requested: Union[RoomType, None] = Field(
        None,
        description="Update requested room type",
    )
    preferred_check_in_date: Union[Date, None] = Field(
        None,
        description="Update preferred check-in Date",
    )
    stay_duration_months: Union[int, None] = Field(
        None,
        ge=1,
        le=24,
        description="Update stay duration",
    )

    # Special Requirements
    special_requests: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Update special requests",
    )
    dietary_preferences: Union[str, None] = Field(
        None,
        max_length=255,
        description="Update dietary preferences",
    )
    has_vehicle: Union[bool, None] = Field(
        None,
        description="Update vehicle status",
    )
    vehicle_details: Union[str, None] = Field(
        None,
        max_length=255,
        description="Update vehicle details",
    )

    # Status Updates (admin only)
    booking_status: Union[BookingStatus, None] = Field(
        None,
        description="Update booking status (admin only)",
    )

    @field_validator("preferred_check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate updated check-in Date."""
        if v is not None and v < Date.today():
            raise ValueError(
                f"Check-in Date ({v}) cannot be in the past"
            )
        return v

    @field_validator("special_requests", "dietary_preferences")
    @classmethod
    def clean_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean text fields."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v