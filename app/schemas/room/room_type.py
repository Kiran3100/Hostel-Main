# --- File: app/schemas/room_type.py ---
"""
Room Type schemas with validation and type safety.

Provides schemas for room type definitions, creation, updates,
and summary statistics.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- All Decimal fields now have explicit max_digits/decimal_places constraints
"""

from decimal import Decimal
from typing import Annotated, List, Union

from pydantic import Field, field_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema, BaseResponseSchema
from app.schemas.common.enums import RoomType

__all__ = [
    "RoomTypeDefinition",
    "RoomTypeCreate",
    "RoomTypeUpdate",
    "RoomTypeSummary",
]


class RoomTypeDefinition(BaseResponseSchema):
    """
    Complete room type definition.
    
    Defines a category of rooms with specifications and pricing.
    """
    
    hostel_id: str = Field(..., description="Hostel ID this room type belongs to")
    name: str = Field(..., description="Room type name (e.g., 'Single', 'Double')")
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Detailed description of the room type"
    )
    
    # Capacity
    room_type: RoomType = Field(..., description="Standard room type enum")
    min_beds: int = Field(..., ge=1, le=20, description="Minimum bed capacity")
    max_beds: int = Field(..., ge=1, le=20, description="Maximum bed capacity")
    typical_beds: int = Field(..., ge=1, le=20, description="Typical/default bed count")
    
    # Pricing with proper Decimal constraints
    base_price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Base monthly price per bed",
        ),
    ]
    base_price_quarterly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Base quarterly price per bed",
            ),
        ],
        None,
    ] = None
    base_price_yearly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Base yearly price per bed",
            ),
        ],
        None,
    ] = None
    
    # Features
    is_ac_available: bool = Field(default=False, description="AC can be provided")
    has_attached_bathroom: bool = Field(default=False, description="Attached bathroom standard")
    has_balcony: bool = Field(default=False, description="Balcony available")
    
    # Specifications
    min_room_size_sqft: Union[int, None] = Field(
        default=None,
        ge=50,
        le=1000,
        description="Minimum room size in sq ft"
    )
    max_room_size_sqft: Union[int, None] = Field(
        default=None,
        ge=50,
        le=1000,
        description="Maximum room size in sq ft"
    )
    
    # Amenities
    standard_amenities: List[str] = Field(
        default_factory=list,
        description="Standard amenities for this room type"
    )
    optional_amenities: List[str] = Field(
        default_factory=list,
        description="Optional amenities that can be added"
    )
    
    # Status
    is_active: bool = Field(default=True, description="Room type is active and bookable")
    display_order: int = Field(default=0, description="Display order for sorting")
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def quarterly_discount_percentage(self) -> Union[Decimal, None]:
        """Calculate quarterly discount percentage."""
        if not self.base_price_quarterly:
            return None
        monthly_equivalent = self.base_price_monthly * 3
        if monthly_equivalent == 0:
            return None
        discount = ((monthly_equivalent - self.base_price_quarterly) / monthly_equivalent * 100)
        return Decimal(discount).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def yearly_discount_percentage(self) -> Union[Decimal, None]:
        """Calculate yearly discount percentage."""
        if not self.base_price_yearly:
            return None
        monthly_equivalent = self.base_price_monthly * 12
        if monthly_equivalent == 0:
            return None
        discount = ((monthly_equivalent - self.base_price_yearly) / monthly_equivalent * 100)
        return Decimal(discount).quantize(Decimal("0.01"))


class RoomTypeCreate(BaseCreateSchema):
    """
    Schema for creating a new room type.
    """
    
    hostel_id: str = Field(..., description="Hostel ID (required)")
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Room type name (required)"
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Room type description"
    )
    
    # Capacity
    room_type: RoomType = Field(..., description="Standard room type")
    min_beds: int = Field(..., ge=1, le=20, description="Minimum beds")
    max_beds: int = Field(..., ge=1, le=20, description="Maximum beds")
    typical_beds: int = Field(..., ge=1, le=20, description="Typical bed count")
    
    # Pricing
    base_price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Base monthly price (required)",
        ),
    ]
    base_price_quarterly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Base quarterly price",
            ),
        ],
        None,
    ] = None
    base_price_yearly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Base yearly price",
            ),
        ],
        None,
    ] = None
    
    # Features
    is_ac_available: bool = Field(default=False, description="AC available")
    has_attached_bathroom: bool = Field(default=False, description="Attached bathroom")
    has_balcony: bool = Field(default=False, description="Balcony")
    
    # Specifications
    min_room_size_sqft: Union[int, None] = Field(
        default=None,
        ge=50,
        le=1000,
        description="Min room size"
    )
    max_room_size_sqft: Union[int, None] = Field(
        default=None,
        ge=50,
        le=1000,
        description="Max room size"
    )
    
    # Amenities
    standard_amenities: List[str] = Field(
        default_factory=list,
        description="Standard amenities"
    )
    optional_amenities: List[str] = Field(
        default_factory=list,
        description="Optional amenities"
    )
    
    # Settings
    is_active: bool = Field(default=True, description="Active status")
    display_order: int = Field(default=0, description="Display order")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and normalize name."""
        v = v.strip()
        if not v:
            raise ValueError("Room type name cannot be empty")
        return v
    
    @field_validator("min_beds", "max_beds", "typical_beds")
    @classmethod
    def validate_bed_counts(cls, v: int) -> int:
        """Validate bed counts are reasonable."""
        if v < 1:
            raise ValueError("Bed count must be at least 1")
        if v > 20:
            raise ValueError("Bed count cannot exceed 20")
        return v


class RoomTypeUpdate(BaseUpdateSchema):
    """
    Schema for updating room type information.
    """
    
    name: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Room type name"
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Room type description"
    )
    
    # Capacity
    room_type: Union[RoomType, None] = Field(default=None, description="Standard room type")
    min_beds: Union[int, None] = Field(default=None, ge=1, le=20, description="Minimum beds")
    max_beds: Union[int, None] = Field(default=None, ge=1, le=20, description="Maximum beds")
    typical_beds: Union[int, None] = Field(default=None, ge=1, le=20, description="Typical beds")
    
    # Pricing
    base_price_monthly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Base monthly price",
            ),
        ],
        None,
    ] = None
    base_price_quarterly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Base quarterly price",
            ),
        ],
        None,
    ] = None
    base_price_yearly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Base yearly price",
            ),
        ],
        None,
    ] = None
    
    # Features
    is_ac_available: Union[bool, None] = Field(default=None, description="AC available")
    has_attached_bathroom: Union[bool, None] = Field(default=None, description="Attached bathroom")
    has_balcony: Union[bool, None] = Field(default=None, description="Balcony")
    
    # Specifications
    min_room_size_sqft: Union[int, None] = Field(
        default=None,
        ge=50,
        le=1000,
        description="Min room size"
    )
    max_room_size_sqft: Union[int, None] = Field(
        default=None,
        ge=50,
        le=1000,
        description="Max room size"
    )
    
    # Amenities
    standard_amenities: Union[List[str], None] = Field(
        default=None,
        description="Standard amenities"
    )
    optional_amenities: Union[List[str], None] = Field(
        default=None,
        description="Optional amenities"
    )
    
    # Settings
    is_active: Union[bool, None] = Field(default=None, description="Active status")
    display_order: Union[int, None] = Field(default=None, description="Display order")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate and normalize name."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Room type name cannot be empty")
        return v


class RoomTypeSummary(BaseSchema):
    """
    Room type summary with statistics.
    
    Provides aggregated data for dashboard displays.
    """
    
    id: str = Field(..., description="Room type ID")
    name: str = Field(..., description="Room type name")
    room_type: RoomType = Field(..., description="Standard room type")
    
    # Capacity stats
    total_rooms: int = Field(default=0, ge=0, description="Total rooms of this type")
    total_bed_capacity: int = Field(default=0, ge=0, description="Total bed capacity")
    occupied_beds: int = Field(default=0, ge=0, description="Currently occupied beds")
    available_beds: int = Field(default=0, ge=0, description="Available beds")
    
    # Pricing
    base_price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Base monthly price",
        ),
    ]
    
    # Revenue metrics
    current_monthly_revenue: Annotated[
        Decimal,
        Field(
            default=Decimal("0.00"),
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Current monthly revenue",
        ),
    ]
    potential_monthly_revenue: Annotated[
        Decimal,
        Field(
            default=Decimal("0.00"),
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Potential revenue at full capacity",
        ),
    ]
    
    # Status
    is_active: bool = Field(..., description="Room type is active")
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_percentage(self) -> Decimal:
        """Calculate occupancy percentage."""
        if self.total_bed_capacity == 0:
            return Decimal("0.00")
        return Decimal((self.occupied_beds / self.total_bed_capacity * 100)).quantize(
            Decimal("0.01")
        )
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def revenue_realization_percentage(self) -> Decimal:
        """Calculate revenue realization percentage."""
        if self.potential_monthly_revenue == 0:
            return Decimal("0.00")
        return Decimal(
            (self.current_monthly_revenue / self.potential_monthly_revenue * 100)
        ).quantize(Decimal("0.01"))
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def average_occupancy_per_room(self) -> Decimal:
        """Calculate average occupancy per room."""
        if self.total_rooms == 0:
            return Decimal("0.00")
        return Decimal(self.occupied_beds / self.total_rooms).quantize(Decimal("0.01"))