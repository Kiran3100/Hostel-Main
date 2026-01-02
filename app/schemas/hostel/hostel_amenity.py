"""
Hostel amenity schemas for CRUD and booking operations.
"""

from datetime import datetime, time
from decimal import Decimal
from typing import Annotated, List, Union
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import (
    BaseCreateSchema, 
    BaseResponseSchema, 
    BaseUpdateSchema
)
from app.schemas.common.enums import BookingStatus, Priority

__all__ = [
    "HostelAmenity",
    "AmenityCreate", 
    "AmenityUpdate",
    "AmenityBookingRequest",
    "AmenityBookingResponse",
    "AmenityAvailability",
]


class AmenityCreate(BaseCreateSchema):
    """Create amenity request schema."""
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    name: str = Field(
        ..., 
        min_length=2, 
        max_length=100, 
        description="Amenity name"
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Amenity description"
    )
    amenity_type: str = Field(
        ...,
        description="Type of amenity (gym, library, common_room, etc.)"
    )
    capacity: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Maximum capacity"
    )
    price_per_hour: Annotated[
        Decimal,
        Field(ge=0, description="Hourly rate")
    ] = Decimal("0.00")
    is_bookable: bool = Field(
        default=True,
        description="Whether amenity can be booked"
    )
    is_free: bool = Field(
        default=True,
        description="Whether amenity is free to use"
    )
    advance_booking_hours: int = Field(
        default=24,
        ge=1,
        le=720,  # 30 days max
        description="How many hours in advance booking is allowed"
    )
    max_booking_duration_hours: int = Field(
        default=2,
        ge=1,
        le=24,
        description="Maximum booking duration in hours"
    )
    operating_hours_start: Union[time, None] = Field(
        default=None,
        description="Operating start time"
    )
    operating_hours_end: Union[time, None] = Field(
        default=None, 
        description="Operating end time"
    )
    available_days: List[str] = Field(
        default_factory=lambda: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        description="Days when amenity is available"
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether bookings require admin approval"
    )

    @field_validator("amenity_type")
    @classmethod
    def validate_amenity_type(cls, v: str) -> str:
        """Validate amenity type."""
        valid_types = [
            "gym", "library", "common_room", "study_room", "conference_room",
            "recreation_room", "laundry", "kitchen", "parking", "other"
        ]
        if v.lower() not in valid_types:
            raise ValueError(f"Amenity type must be one of: {', '.join(valid_types)}")
        return v.lower()

    @field_validator("available_days")
    @classmethod
    def validate_available_days(cls, v: List[str]) -> List[str]:
        """Validate available days."""
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        normalized_days = [day.lower() for day in v]
        for day in normalized_days:
            if day not in valid_days:
                raise ValueError(f"Invalid day: {day}. Must be one of: {', '.join(valid_days)}")
        return normalized_days

    @model_validator(mode="after")
    def validate_operating_hours(self):
        """Validate operating hours."""
        if (self.operating_hours_start is not None and 
            self.operating_hours_end is not None):
            if self.operating_hours_start >= self.operating_hours_end:
                raise ValueError("Operating start time must be before end time")
        return self


class AmenityUpdate(BaseUpdateSchema):
    """Update amenity schema."""
    model_config = ConfigDict(from_attributes=True)
    
    name: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100
    )
    description: Union[str, None] = Field(default=None, max_length=500)
    amenity_type: Union[str, None] = Field(default=None)
    capacity: Union[int, None] = Field(default=None, ge=1, le=100)
    price_per_hour: Union[Decimal, None] = Field(default=None, ge=0)
    is_bookable: Union[bool, None] = Field(default=None)
    is_free: Union[bool, None] = Field(default=None)
    advance_booking_hours: Union[int, None] = Field(default=None, ge=1, le=720)
    max_booking_duration_hours: Union[int, None] = Field(default=None, ge=1, le=24)
    operating_hours_start: Union[time, None] = Field(default=None)
    operating_hours_end: Union[time, None] = Field(default=None)
    available_days: Union[List[str], None] = Field(default=None)
    requires_approval: Union[bool, None] = Field(default=None)
    is_active: Union[bool, None] = Field(default=None)

    @field_validator("amenity_type")
    @classmethod
    def validate_amenity_type(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate amenity type."""
        if v is not None:
            return AmenityCreate.validate_amenity_type(v)
        return v

    @field_validator("available_days")
    @classmethod
    def validate_available_days(cls, v: Union[List[str], None]) -> Union[List[str], None]:
        """Validate available days."""
        if v is not None:
            return AmenityCreate.validate_available_days(v)
        return v


class HostelAmenity(BaseResponseSchema):
    """Hostel amenity response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    name: str = Field(..., description="Amenity name")
    description: Union[str, None] = Field(default=None)
    amenity_type: str = Field(..., description="Type of amenity")
    capacity: int = Field(..., description="Maximum capacity")
    price_per_hour: Decimal = Field(..., description="Hourly rate")
    is_bookable: bool = Field(..., description="Bookable status")
    is_free: bool = Field(..., description="Free to use")
    is_available: bool = Field(..., description="Current availability")
    is_active: bool = Field(..., description="Active status")
    advance_booking_hours: int = Field(..., description="Advance booking allowed (hours)")
    max_booking_duration_hours: int = Field(..., description="Max booking duration (hours)")
    operating_hours_start: Union[time, None] = Field(default=None)
    operating_hours_end: Union[time, None] = Field(default=None)
    available_days: List[str] = Field(..., description="Available days")
    requires_approval: bool = Field(..., description="Requires approval")
    
    # Stats
    total_bookings: int = Field(default=0, description="Total bookings count")
    active_bookings: int = Field(default=0, description="Active bookings count")


class AmenityBookingRequest(BaseCreateSchema):
    """Amenity booking request schema."""
    model_config = ConfigDict(from_attributes=True)
    
    start_time: datetime = Field(..., description="Booking start time")
    end_time: datetime = Field(..., description="Booking end time")
    purpose: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Purpose of booking"
    )
    guest_count: int = Field(
        default=1,
        ge=1,
        description="Number of guests"
    )
    special_requirements: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Special requirements or notes"
    )

    @model_validator(mode="after")
    def validate_booking_time(self):
        """Validate booking time."""
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        
        # Check if booking is not in the past
        if self.start_time <= datetime.now():
            raise ValueError("Booking cannot be in the past")
        
        # Check if booking duration is reasonable (max 24 hours)
        duration = self.end_time - self.start_time
        if duration.total_seconds() > 24 * 3600:  # 24 hours
            raise ValueError("Booking duration cannot exceed 24 hours")
        
        return self


class AmenityBookingResponse(BaseResponseSchema):
    """Amenity booking response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    amenity_id: UUID = Field(..., description="Amenity ID")
    amenity_name: str = Field(..., description="Amenity name")
    user_id: UUID = Field(..., description="User who booked")
    start_time: datetime = Field(..., description="Booking start time")
    end_time: datetime = Field(..., description="Booking end time")
    purpose: Union[str, None] = Field(default=None)
    guest_count: int = Field(..., description="Number of guests")
    special_requirements: Union[str, None] = Field(default=None)
    total_cost: Decimal = Field(..., description="Total booking cost")
    status: BookingStatus = Field(..., description="Booking status")  # Changed: Use BookingStatus directly
    booking_reference: str = Field(..., description="Unique booking reference")
    
    # Approval fields
    approved_by: Union[UUID, None] = Field(default=None, description="Admin who approved")
    approved_at: Union[datetime, None] = Field(default=None, description="Approval timestamp")
    rejection_reason: Union[str, None] = Field(default=None, description="Rejection reason")


class AmenityAvailability(BaseResponseSchema):
    """Amenity availability information."""
    model_config = ConfigDict(from_attributes=True)
    
    amenity_id: UUID = Field(..., description="Amenity ID")
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    available_slots: List[dict] = Field(
        ..., 
        description="Available time slots"
    )
    booked_slots: List[dict] = Field(
        ...,
        description="Already booked time slots"
    )