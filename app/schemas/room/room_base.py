# --- File: app/schemas/room/room_base.py ---
"""
Room base schemas with enhanced validation and type safety.

Provides core room management schemas including creation, updates,
bulk operations, and pricing/status management.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- field_validator and model_validator already use v2 syntax
- All Decimal fields now have explicit max_digits/decimal_places constraints
- Validators properly handle Optional types in update schemas
"""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import RoomStatus, RoomType

__all__ = [
    "RoomBase",
    "RoomCreate",
    "RoomUpdate",
    "BulkRoomCreate",
    "RoomPricingUpdate",
    "RoomStatusUpdate",
    "RoomMediaUpdate",
]


class RoomBase(BaseSchema):
    """
    Base room schema with comprehensive room attributes.
    
    Contains common fields shared across room operations including
    specifications, pricing, amenities, and availability.
    """

    hostel_id: str = Field(
        ...,
        description="Hostel ID this room belongs to",
    )
    room_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Room number/identifier (e.g., '101', 'A-201')",
        examples=["101", "A-201", "Block-B-301"],
    )
    floor_number: Optional[int] = Field(
        default=None,
        ge=0,
        le=50,
        description="Floor number (0 for ground floor)",
    )
    wing: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Wing/Block designation (A, B, North Wing, etc.)",
        examples=["A", "B", "North Wing", "Block-1"],
    )

    # Type and capacity
    room_type: RoomType = Field(
        ...,
        description="Room occupancy type",
    )
    total_beds: int = Field(
        ...,
        ge=1,
        le=20,
        description="Total bed capacity in the room",
    )

    # Pricing with proper Decimal constraints
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent amount",
        ),
    ]
    price_quarterly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Quarterly rent (3 months, often discounted)",
            ),
        ]
    ] = None
    price_half_yearly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Half-yearly rent (6 months, often discounted)",
            ),
        ]
    ] = None
    price_yearly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Yearly rent (12 months, often discounted)",
            ),
        ]
    ] = None

    # Physical specifications
    room_size_sqft: Optional[int] = Field(
        default=None,
        ge=50,
        le=1000,
        description="Room size in square feet",
    )
    is_ac: bool = Field(
        default=False,
        description="Air conditioning available",
    )
    has_attached_bathroom: bool = Field(
        default=False,
        description="Attached/ensuite bathroom",
    )
    has_balcony: bool = Field(
        default=False,
        description="Private balcony available",
    )
    has_wifi: bool = Field(
        default=True,
        description="WiFi connectivity available",
    )

    # Amenities and furnishing
    amenities: List[str] = Field(
        default_factory=list,
        description="Room-specific amenities (separate from general hostel amenities)",
        examples=[["Study Table", "Wardrobe", "Fan", "Geyser"]],
    )
    furnishing: List[str] = Field(
        default_factory=list,
        description="Furniture and fixtures provided",
        examples=[["Bed", "Mattress", "Study Table", "Chair", "Wardrobe"]],
    )

    # Availability and status
    is_available_for_booking: bool = Field(
        default=True,
        description="Available for online booking requests",
    )
    is_under_maintenance: bool = Field(
        default=False,
        description="Currently under maintenance",
    )

    # Media
    room_images: List[str] = Field(
        default_factory=list,
        max_length=15,
        description="Room image URLs (max 15)",
    )

    @field_validator("room_number")
    @classmethod
    def validate_room_number(cls, v: str) -> str:
        """
        Validate and normalize room number.
        
        Ensures room number is properly formatted and trimmed.
        """
        v = v.strip().upper()
        if not v:
            raise ValueError("Room number cannot be empty")
        # Remove excessive whitespace
        v = " ".join(v.split())
        return v

    @field_validator("wing")
    @classmethod
    def validate_wing(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize wing/block designation."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Remove excessive whitespace
            v = " ".join(v.split())
        return v

    @field_validator("amenities", "furnishing")
    @classmethod
    def validate_and_clean_lists(cls, v: List[str]) -> List[str]:
        """
        Validate and clean list fields.
        
        Removes empty strings, duplicates, and normalizes values.
        """
        if not v:
            return []
        # Clean and normalize
        cleaned = [item.strip() for item in v if item and item.strip()]
        # Remove duplicates while preserving order (case-insensitive)
        seen = set()
        unique = []
        for item in cleaned:
            item_lower = item.lower()
            if item_lower not in seen:
                seen.add(item_lower)
                unique.append(item)
        return unique

    @field_validator("room_images")
    @classmethod
    def validate_room_images(cls, v: List[str]) -> List[str]:
        """
        Validate room image URLs.
        
        Removes empty strings, duplicates, and validates URL format.
        """
        if not v:
            return []
        # Clean URLs
        cleaned = []
        seen = set()
        for url in v:
            if not url or not url.strip():
                continue
            url = url.strip()
            # Basic URL validation
            if not (url.startswith("http://") or url.startswith("https://")):
                continue
            # Remove duplicates
            if url not in seen:
                seen.add(url)
                cleaned.append(url)
        return cleaned[:15]  # Limit to 15 images

    @model_validator(mode="after")
    def validate_pricing_consistency(self) -> "RoomBase":
        """
        Validate pricing consistency and logical discounts.
        
        Ensures longer-term prices are not higher than monthly equivalent.
        Pydantic v2: mode="after" validators receive the model instance.
        """
        monthly = self.price_monthly
        
        # Validate quarterly pricing
        if self.price_quarterly is not None:
            monthly_equivalent = monthly * 3
            if self.price_quarterly > monthly_equivalent:
                raise ValueError(
                    f"Quarterly price ({self.price_quarterly}) should not exceed "
                    f"3x monthly price ({monthly_equivalent})"
                )
        
        # Validate half-yearly pricing
        if self.price_half_yearly is not None:
            monthly_equivalent = monthly * 6
            if self.price_half_yearly > monthly_equivalent:
                raise ValueError(
                    f"Half-yearly price ({self.price_half_yearly}) should not exceed "
                    f"6x monthly price ({monthly_equivalent})"
                )
        
        # Validate yearly pricing
        if self.price_yearly is not None:
            monthly_equivalent = monthly * 12
            if self.price_yearly > monthly_equivalent:
                raise ValueError(
                    f"Yearly price ({self.price_yearly}) should not exceed "
                    f"12x monthly price ({monthly_equivalent})"
                )
        
        return self

    @model_validator(mode="after")
    def validate_room_type_beds(self) -> "RoomBase":
        """
        Validate bed count matches room type expectations.
        
        Provides warnings for unusual configurations.
        Pydantic v2: mode="after" validators receive the model instance.
        """
        expected_beds = {
            RoomType.SINGLE: (1, 1),
            RoomType.DOUBLE: (2, 2),
            RoomType.TRIPLE: (3, 3),
            RoomType.FOUR_SHARING: (4, 4),
            RoomType.DORMITORY: (5, 20),
        }
        
        if self.room_type in expected_beds:
            min_beds, max_beds = expected_beds[self.room_type]
            if not (min_beds <= self.total_beds <= max_beds):
                # Note: We don't raise an error to allow flexibility
                # but this could be logged as a warning
                pass
        
        return self


class RoomCreate(RoomBase, BaseCreateSchema):
    """
    Schema for creating a new room.
    
    Enforces all required fields for room creation.
    """

    # Override to ensure required fields
    hostel_id: str = Field(
        ...,
        description="Hostel ID (required)",
    )
    room_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Room number (required)",
    )
    room_type: RoomType = Field(
        ...,
        description="Room type (required)",
    )
    total_beds: int = Field(
        ...,
        ge=1,
        le=20,
        description="Total beds (required)",
    )
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent (required)",
        ),
    ]


class RoomUpdate(BaseUpdateSchema):
    """
    Schema for updating room information.
    
    All fields are optional for partial updates.
    """

    room_number: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Room number",
    )
    floor_number: Optional[int] = Field(
        default=None,
        ge=0,
        le=50,
        description="Floor number",
    )
    wing: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Wing/Block",
    )
    room_type: Optional[RoomType] = Field(
        default=None,
        description="Room type",
    )
    total_beds: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Total beds",
    )

    # Pricing updates with proper Decimal constraints
    price_monthly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Monthly rent",
            ),
        ]
    ] = None
    price_quarterly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Quarterly rent",
            ),
        ]
    ] = None
    price_half_yearly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Half-yearly rent",
            ),
        ]
    ] = None
    price_yearly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Yearly rent",
            ),
        ]
    ] = None

    # Physical specifications
    room_size_sqft: Optional[int] = Field(
        default=None,
        ge=50,
        le=1000,
        description="Room size in sq ft",
    )
    is_ac: Optional[bool] = Field(
        default=None,
        description="Air conditioning",
    )
    has_attached_bathroom: Optional[bool] = Field(
        default=None,
        description="Attached bathroom",
    )
    has_balcony: Optional[bool] = Field(
        default=None,
        description="Balcony",
    )
    has_wifi: Optional[bool] = Field(
        default=None,
        description="WiFi",
    )

    # Amenities
    amenities: Optional[List[str]] = Field(
        default=None,
        description="Room amenities",
    )
    furnishing: Optional[List[str]] = Field(
        default=None,
        description="Furniture items",
    )

    # Availability
    is_available_for_booking: Optional[bool] = Field(
        default=None,
        description="Booking availability",
    )
    is_under_maintenance: Optional[bool] = Field(
        default=None,
        description="Maintenance status",
    )

    # Status
    status: Optional[RoomStatus] = Field(
        default=None,
        description="Room operational status",
    )

    # Media
    room_images: Optional[List[str]] = Field(
        default=None,
        max_length=15,
        description="Room image URLs",
    )

    @field_validator("room_number")
    @classmethod
    def validate_room_number(cls, v: Optional[str]) -> Optional[str]:
        """Validate room number format."""
        if v is not None:
            v = v.strip().upper()
            if not v:
                raise ValueError("Room number cannot be empty")
            v = " ".join(v.split())
        return v

    @field_validator("wing")
    @classmethod
    def validate_wing(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize wing/block designation."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            v = " ".join(v.split())
        return v

    @field_validator("amenities", "furnishing")
    @classmethod
    def validate_and_clean_lists(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and clean list fields."""
        if v is not None:
            if not v:
                return []
            cleaned = [item.strip() for item in v if item and item.strip()]
            seen = set()
            unique = []
            for item in cleaned:
                item_lower = item.lower()
                if item_lower not in seen:
                    seen.add(item_lower)
                    unique.append(item)
            return unique
        return v

    @field_validator("room_images")
    @classmethod
    def validate_room_images(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate room image URLs."""
        if v is not None:
            if not v:
                return []
            cleaned = []
            seen = set()
            for url in v:
                if not url or not url.strip():
                    continue
                url = url.strip()
                if not (url.startswith("http://") or url.startswith("https://")):
                    continue
                if url not in seen:
                    seen.add(url)
                    cleaned.append(url)
            return cleaned[:15]
        return v


class BulkRoomCreate(BaseCreateSchema):
    """
    Schema for bulk room creation.
    
    Allows creating multiple rooms in a single operation.
    Useful for initial hostel setup or adding multiple similar rooms.
    """

    hostel_id: str = Field(
        ...,
        description="Hostel ID for all rooms",
    )
    rooms: List[RoomCreate] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of rooms to create (max 100 per batch)",
    )

    @field_validator("rooms")
    @classmethod
    def validate_unique_room_numbers(cls, v: List[RoomCreate]) -> List[RoomCreate]:
        """
        Validate room numbers are unique within the batch.
        
        Prevents duplicate room numbers in bulk creation.
        """
        room_numbers = [room.room_number.strip().upper() for room in v]
        if len(room_numbers) != len(set(room_numbers)):
            raise ValueError("Room numbers must be unique within the batch")
        return v

    @model_validator(mode="after")
    def validate_consistent_hostel(self) -> "BulkRoomCreate":
        """
        Validate all rooms belong to the same hostel.
        
        Ensures consistency in bulk operations.
        Pydantic v2: mode="after" validators receive the model instance.
        """
        hostel_id = self.hostel_id
        if hostel_id:
            for room in self.rooms:
                if room.hostel_id != hostel_id:
                    raise ValueError(
                        f"All rooms must belong to hostel {hostel_id}. "
                        f"Found room with hostel_id: {room.hostel_id}"
                    )
        return self


class RoomPricingUpdate(BaseUpdateSchema):
    """
    Schema for updating room pricing.
    
    Dedicated schema for price updates with validation.
    """

    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent (required)",
        ),
    ]
    price_quarterly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Quarterly rent (optional discount)",
            ),
        ]
    ] = None
    price_half_yearly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Half-yearly rent (optional discount)",
            ),
        ]
    ] = None
    price_yearly: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Yearly rent (optional discount)",
            ),
        ]
    ] = None
    effective_from: Optional[Date] = Field(
        default=None,
        description="Effective date for new pricing (optional)",
    )

    @model_validator(mode="after")
    def validate_pricing_logic(self) -> "RoomPricingUpdate":
        """
        Validate pricing consistency.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        monthly = self.price_monthly

        if self.price_quarterly is not None:
            if self.price_quarterly > (monthly * 3):
                raise ValueError(
                    "Quarterly price should not exceed 3x monthly price"
                )

        if self.price_half_yearly is not None:
            if self.price_half_yearly > (monthly * 6):
                raise ValueError(
                    "Half-yearly price should not exceed 6x monthly price"
                )

        if self.price_yearly is not None:
            if self.price_yearly > (monthly * 12):
                raise ValueError(
                    "Yearly price should not exceed 12x monthly price"
                )

        return self

    @field_validator("effective_from")
    @classmethod
    def validate_effective_date(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate effective date is not in the past."""
        if v is not None:
            if v < Date.today():
                raise ValueError("Effective date cannot be in the past")
        return v


class RoomStatusUpdate(BaseUpdateSchema):
    """
    Schema for updating room operational status.
    
    Manages room availability and maintenance status with proper tracking.
    """

    status: RoomStatus = Field(
        ...,
        description="Room operational status",
    )
    is_available_for_booking: bool = Field(
        ...,
        description="Available for online bookings",
    )
    is_under_maintenance: bool = Field(
        default=False,
        description="Currently under maintenance",
    )
    maintenance_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Maintenance details and notes",
    )
    maintenance_start_date: Optional[Date] = Field(
        default=None,
        description="Maintenance start date",
    )
    maintenance_end_date: Optional[Date] = Field(
        default=None,
        description="Expected maintenance completion date",
    )

    @model_validator(mode="after")
    def validate_maintenance_requirements(self) -> "RoomStatusUpdate":
        """
        Validate maintenance-related fields.
        
        Ensures proper documentation when room is under maintenance.
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.is_under_maintenance or self.status == RoomStatus.MAINTENANCE:
            # Require maintenance notes when under maintenance
            if not self.maintenance_notes:
                raise ValueError(
                    "Maintenance notes are required when room is under maintenance"
                )
            # Require maintenance start date
            if not self.maintenance_start_date:
                raise ValueError(
                    "Maintenance start date is required when room is under maintenance"
                )
            # Set room as unavailable for booking
            if self.is_available_for_booking:
                raise ValueError(
                    "Room cannot be available for booking while under maintenance"
                )
        
        return self

    @model_validator(mode="after")
    def validate_maintenance_dates(self) -> "RoomStatusUpdate":
        """
        Validate maintenance date range.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.maintenance_start_date and self.maintenance_end_date:
            if self.maintenance_end_date < self.maintenance_start_date:
                raise ValueError(
                    "Maintenance end date must be after or equal to start date"
                )
        return self


class RoomMediaUpdate(BaseUpdateSchema):
    """
    Schema for updating room media (images).
    
    Dedicated schema for managing room photographs and virtual tours.
    """

    room_images: List[str] = Field(
        default_factory=list,
        max_length=15,
        description="Room image URLs (max 15)",
    )
    primary_image: Optional[str] = Field(
        default=None,
        description="Primary/cover image URL (must be in room_images)",
    )
    virtual_tour_url: Optional[str] = Field(
        default=None,
        description="360° virtual tour URL",
    )

    @field_validator("room_images")
    @classmethod
    def validate_room_images(cls, v: List[str]) -> List[str]:
        """Validate room image URLs."""
        if not v:
            return []
        
        cleaned = []
        seen = set()
        for url in v:
            if not url or not url.strip():
                continue
            url = url.strip()
            # Validate URL format
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError(f"Invalid image URL format: {url}")
            # Remove duplicates
            if url not in seen:
                seen.add(url)
                cleaned.append(url)
        
        return cleaned[:15]

    @model_validator(mode="after")
    def validate_primary_image(self) -> "RoomMediaUpdate":
        """
        Validate primary image is in room_images list.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.primary_image:
            if self.primary_image not in self.room_images:
                raise ValueError(
                    "Primary image must be one of the room images"
                )
        return self

    @field_validator("virtual_tour_url")
    @classmethod
    def validate_virtual_tour_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate virtual tour URL format."""
        if v is not None:
            v = v.strip()
            if v and not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("Invalid virtual tour URL format")
        return v