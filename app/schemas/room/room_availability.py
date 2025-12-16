# --- File: app/schemas/room/room_availability.py ---
"""
Room availability schemas with enhanced Date validation.

Provides schemas for checking room availability, calendar views,
and booking-related information.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- field_validator and model_validator already use v2 syntax
- All Decimal fields now have explicit max_digits/decimal_places constraints
"""

from datetime import date as Date, timedelta
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Union

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import RoomType

__all__ = [
    "RoomAvailabilityRequest",
    "AvailabilityResponse",
    "AvailableRoom",
    "AvailabilityCalendar",
    "DayAvailability",
    "BookingInfo",
    "BulkAvailabilityRequest",
]


class RoomAvailabilityRequest(BaseCreateSchema):
    """
    Request to check room availability.
    
    Validates dates and duration for availability checking.
    """

    hostel_id: str = Field(
        ...,
        description="Hostel ID to check availability for",
    )
    check_in_date: Date = Field(
        ...,
        description="Desired check-in Date",
    )
    duration_months: int = Field(
        ...,
        ge=1,
        le=24,
        description="Stay duration in months (1-24)",
    )
    room_type: Union[RoomType, None] = Field(
        default=None,
        description="Preferred room type (optional filter)",
    )
    min_beds: int = Field(
        default=1,
        ge=1,
        le=20,
        description="Minimum beds required",
    )
    
    # Preferences (optional filters)
    is_ac_required: Union[bool, None] = Field(
        default=None,
        description="AC required",
    )
    attached_bathroom_required: Union[bool, None] = Field(
        default=None,
        description="Attached bathroom required",
    )
    max_price_monthly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Maximum acceptable monthly rent",
            ),
        ],
        None,
    ] = None

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """
        Validate check-in Date.
        
        Ensures Date is not too far in the past.
        """
        today = Date.today()
        # Allow up to 7 days in the past for flexibility
        min_date = today - timedelta(days=7)
        
        if v < min_date:
            raise ValueError(
                "Check-in Date cannot be more than 7 days in the past"
            )
        
        # Warn if too far in future (1 year)
        max_date = today + timedelta(days=365)
        if v > max_date:
            raise ValueError(
                "Check-in Date cannot be more than 1 year in the future"
            )
        
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def check_out_date(self) -> Date:
        """Calculate checkout Date based on duration."""
        # Approximate: 1 month = 30 days
        return self.check_in_date + timedelta(days=self.duration_months * 30)


class AvailableRoom(BaseSchema):
    """
    Available room details for booking.
    
    Comprehensive room information for availability results.
    """

    room_id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    room_type: RoomType = Field(..., description="Room type")
    floor_number: Union[int, None] = Field(default=None, description="Floor")
    wing: Union[str, None] = Field(default=None, description="Wing/Block")
    
    # Availability
    available_beds: int = Field(..., ge=0, description="Available beds")
    total_beds: int = Field(..., ge=1, description="Total beds")
    
    # Pricing with proper Decimal constraints
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent per bed",
        ),
    ]
    price_quarterly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Quarterly rate",
            ),
        ],
        None,
    ] = None
    price_half_yearly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Half-yearly rate",
            ),
        ],
        None,
    ] = None
    price_yearly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Yearly rate",
            ),
        ],
        None,
    ] = None
    
    # Features
    is_ac: bool = Field(..., description="Air conditioned")
    has_attached_bathroom: bool = Field(..., description="Attached bathroom")
    has_balcony: bool = Field(default=False, description="Has balcony")
    has_wifi: bool = Field(default=True, description="WiFi available")
    room_size_sqft: Union[int, None] = Field(
        default=None,
        description="Room size",
    )
    
    # Amenities
    amenities: List[str] = Field(
        default_factory=list,
        description="Room amenities",
    )
    furnishing: List[str] = Field(
        default_factory=list,
        description="Furniture items",
    )
    
    # Media
    room_images: List[str] = Field(
        default_factory=list,
        description="Room images",
    )
    primary_image: Union[str, None] = Field(
        default=None,
        description="Primary image URL",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_rate(self) -> Decimal:
        """Calculate current occupancy rate."""
        if self.total_beds == 0:
            return Decimal("0.00")
        occupied = self.total_beds - self.available_beds
        return Decimal((occupied / self.total_beds * 100)).quantize(
            Decimal("0.01")
        )


class AvailabilityResponse(BaseSchema):
    """
    Room availability response.
    
    Complete availability results with metadata.
    """

    hostel_id: str = Field(..., description="Hostel ID")
    check_in_date: Date = Field(..., description="Requested check-in Date")
    check_out_date: Date = Field(..., description="Calculated checkout Date")
    duration_months: int = Field(..., ge=1, description="Stay duration")
    
    # Results
    available_rooms: List[AvailableRoom] = Field(
        default_factory=list,
        description="List of available rooms",
    )
    total_available_beds: int = Field(
        ...,
        ge=0,
        description="Total available beds across all rooms",
    )
    has_availability: bool = Field(
        ...,
        description="Whether any beds are available",
    )
    
    # Filters applied
    filters_applied: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of applied filters",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_rooms_available(self) -> int:
        """Count of rooms with availability."""
        return len(self.available_rooms)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def price_range(self) -> Union[Dict[str, Decimal], None]:
        """Calculate price range across available rooms."""
        if not self.available_rooms:
            return None
        
        prices = [room.price_monthly for room in self.available_rooms]
        return {
            "min": min(prices),
            "max": max(prices),
            "average": Decimal(sum(prices) / len(prices)).quantize(
                Decimal("0.01")
            ),
        }


class BookingInfo(BaseSchema):
    """
    Booking information for calendar display.
    
    Brief booking details for availability calendar.
    """

    booking_id: str = Field(..., description="Booking ID")
    student_name: str = Field(..., description="Student name")
    student_id: str = Field(..., description="Student ID")
    check_in_date: Date = Field(..., description="Check-in Date")
    check_out_date: Date = Field(..., description="Check-out Date")
    bed_number: Union[str, None] = Field(
        default=None,
        description="Assigned bed number",
    )
    status: str = Field(..., description="Booking status")


class DayAvailability(BaseSchema):
    """
    Availability information for a specific day.
    
    Day-level availability with booking details.
    """

    Date: Date = Field(..., description="Date")
    available_beds: int = Field(..., ge=0, description="Available beds")
    total_beds: int = Field(..., ge=1, description="Total beds")
    is_available: bool = Field(..., description="Has availability")
    bookings: List[BookingInfo] = Field(
        default_factory=list,
        description="Active bookings for this day",
    )
    notes: Union[str, None] = Field(
        default=None,
        description="Special notes (holidays, maintenance, etc.)",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_percentage(self) -> Decimal:
        """Calculate occupancy percentage for the day."""
        if self.total_beds == 0:
            return Decimal("0.00")
        occupied = self.total_beds - self.available_beds
        return Decimal((occupied / self.total_beds * 100)).quantize(
            Decimal("0.01")
        )


class AvailabilityCalendar(BaseSchema):
    """
    Availability calendar for a room.
    
    Month-view calendar showing daily availability.
    """

    room_id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
    )
    total_beds: int = Field(..., ge=1, description="Total beds in room")
    
    # Day-by-day availability
    availability: Dict[str, DayAvailability] = Field(
        ...,
        description="Availability by Date (ISO Date string as key)",
    )

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        """Validate month format and range."""
        try:
            year, month = map(int, v.split("-"))
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 01 and 12")
            if not (2000 <= year <= 2100):
                raise ValueError("Year must be between 2000 and 2100")
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid month format: {e}")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def average_occupancy(self) -> Decimal:
        """Calculate average occupancy for the month."""
        if not self.availability:
            return Decimal("0.00")
        
        total_occupancy = sum(
            day.occupancy_percentage for day in self.availability.values()
        )
        return Decimal(total_occupancy / len(self.availability)).quantize(
            Decimal("0.01")
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fully_booked_days(self) -> int:
        """Count days with no availability."""
        return sum(
            1 for day in self.availability.values()
            if day.available_beds == 0
        )


class BulkAvailabilityRequest(BaseCreateSchema):
    """
    Request to check availability for multiple rooms/hostels.
    
    Batch availability checking for comparison or bulk operations.
    """

    hostel_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of hostel IDs (max 10)",
    )
    check_in_date: Date = Field(
        ...,
        description="Check-in Date",
    )
    duration_months: int = Field(
        ...,
        ge=1,
        le=24,
        description="Stay duration",
    )
    room_type: Union[RoomType, None] = Field(
        default=None,
        description="Room type filter",
    )
    min_beds_per_hostel: int = Field(
        default=1,
        ge=1,
        description="Minimum beds required per hostel",
    )

    @field_validator("hostel_ids")
    @classmethod
    def validate_unique_hostel_ids(cls, v: List[str]) -> List[str]:
        """Ensure hostel IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Hostel IDs must be unique")
        return v

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate check-in Date is not in the past."""
        today = Date.today()
        if v < today - timedelta(days=7):
            raise ValueError(
                "Check-in Date cannot be more than 7 days in the past"
            )
        return v