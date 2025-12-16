# --- File: app/schemas/room/room_response.py ---
"""
Room response schemas for API responses.

Provides various response formats for room data including
detailed views, list items, and statistics.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- All Decimal fields now have explicit max_digits/decimal_places constraints
- Financial fields use appropriate precision for currency calculations
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, List, Union

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import BedStatus, RoomStatus, RoomType

__all__ = [
    "RoomResponse",
    "RoomDetail",   
    "RoomListItem",
    "RoomWithBeds",
    "RoomOccupancyStats",
    "RoomFinancialSummary",
]


class RoomResponse(BaseResponseSchema):
    """
    Standard room response schema.
    
    Basic room information for general API responses.
    """

    hostel_id: str = Field(..., description="Hostel ID")
    room_number: str = Field(..., description="Room number")
    floor_number: Union[int, None] = Field(default=None, description="Floor number")
    wing: Union[str, None] = Field(default=None, description="Wing/Block")
    
    # Type and capacity
    room_type: RoomType = Field(..., description="Room type")
    total_beds: int = Field(..., ge=0, description="Total bed capacity")
    occupied_beds: int = Field(..., ge=0, description="Currently occupied beds")
    available_beds: int = Field(..., ge=0, description="Available beds")
    
    # Pricing with proper Decimal constraints
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent",
        ),
    ]
    
    # Features
    is_ac: bool = Field(..., description="Air conditioned")
    has_attached_bathroom: bool = Field(..., description="Attached bathroom")
    
    # Status
    status: RoomStatus = Field(..., description="Room status")
    is_available_for_booking: bool = Field(
        ...,
        description="Available for booking",
    )
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_percentage(self) -> Decimal:
        """Calculate occupancy percentage."""
        if self.total_beds == 0:
            return Decimal("0.00")
        return Decimal(
            (self.occupied_beds / self.total_beds * 100)
        ).quantize(Decimal("0.01"))


class BedDetail(BaseSchema):
    """
    Detailed bed information within a room.
    
    Provides complete bed status and assignment details.
    """

    id: str = Field(..., description="Bed ID")
    bed_number: str = Field(..., description="Bed identifier")
    is_occupied: bool = Field(..., description="Currently occupied")
    status: BedStatus = Field(..., description="Bed status")
    
    # Current occupant
    current_student_id: Union[str, None] = Field(
        default=None,
        description="Current student ID (if occupied)",
    )
    current_student_name: Union[str, None] = Field(
        default=None,
        description="Current student name (if occupied)",
    )
    occupied_from: Union[Date, None] = Field(
        default=None,
        description="Occupancy start Date",
    )
    expected_vacate_date: Union[Date, None] = Field(
        default=None,
        description="Expected checkout Date",
    )
    
    # Additional info
    last_maintenance_date: Union[Date, None] = Field(
        default=None,
        description="Last maintenance Date",
    )
    notes: Union[str, None] = Field(
        default=None,
        description="Bed notes",
    )


class RoomDetail(BaseResponseSchema):
    """
    Detailed room information.
    
    Comprehensive room data including all specifications,
    amenities, and bed details.
    """

    # Basic info
    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    room_number: str = Field(..., description="Room number")
    floor_number: Union[int, None] = Field(default=None, description="Floor number")
    wing: Union[str, None] = Field(default=None, description="Wing/Block")

    # Type and capacity
    room_type: RoomType = Field(..., description="Room type")
    total_beds: int = Field(..., ge=0, description="Total beds")
    occupied_beds: int = Field(..., ge=0, description="Occupied beds")
    available_beds: int = Field(..., ge=0, description="Available beds")

    # Pricing with proper Decimal constraints
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent",
        ),
    ]
    price_quarterly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Quarterly rent",
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
                description="Half-yearly rent",
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
                description="Yearly rent",
            ),
        ],
        None,
    ] = None

    # Specifications
    room_size_sqft: Union[int, None] = Field(
        default=None,
        description="Room size in sq ft",
    )
    is_ac: bool = Field(..., description="Air conditioned")
    has_attached_bathroom: bool = Field(..., description="Attached bathroom")
    has_balcony: bool = Field(..., description="Has balcony")
    has_wifi: bool = Field(..., description="WiFi available")

    # Amenities
    amenities: List[str] = Field(
        default_factory=list,
        description="Room amenities",
    )
    furnishing: List[str] = Field(
        default_factory=list,
        description="Furniture items",
    )

    # Status
    status: RoomStatus = Field(..., description="Room status")
    is_available_for_booking: bool = Field(
        ...,
        description="Available for booking",
    )
    is_under_maintenance: bool = Field(
        ...,
        description="Under maintenance",
    )
    maintenance_start_date: Union[Date, None] = Field(
        default=None,
        description="Maintenance start Date",
    )
    maintenance_end_date: Union[Date, None] = Field(
        default=None,
        description="Expected maintenance end Date",
    )
    maintenance_notes: Union[str, None] = Field(
        default=None,
        description="Maintenance notes",
    )

    # Media
    room_images: List[str] = Field(
        default_factory=list,
        description="Room image URLs",
    )
    primary_image: Union[str, None] = Field(
        default=None,
        description="Primary/cover image",
    )
    virtual_tour_url: Union[str, None] = Field(
        default=None,
        description="Virtual tour URL",
    )

    # Beds detail
    beds: List[BedDetail] = Field(
        default_factory=list,
        description="Detailed bed information",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_percentage(self) -> Decimal:
        """Calculate current occupancy percentage."""
        if self.total_beds == 0:
            return Decimal("0.00")
        return Decimal(
            (self.occupied_beds / self.total_beds * 100)
        ).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_fully_occupied(self) -> bool:
        """Check if room is fully occupied."""
        return self.occupied_beds >= self.total_beds

    @computed_field  # type: ignore[prop-decorator]
    @property
    def discount_percentage_quarterly(self) -> Union[Decimal, None]:
        """Calculate quarterly discount percentage."""
        if not self.price_quarterly:
            return None
        monthly_equivalent = self.price_monthly * 3
        if monthly_equivalent == 0:
            return None
        discount = (
            (monthly_equivalent - self.price_quarterly) / monthly_equivalent * 100
        )
        return Decimal(discount).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def discount_percentage_yearly(self) -> Union[Decimal, None]:
        """Calculate yearly discount percentage."""
        if not self.price_yearly:
            return None
        monthly_equivalent = self.price_monthly * 12
        if monthly_equivalent == 0:
            return None
        discount = (
            (monthly_equivalent - self.price_yearly) / monthly_equivalent * 100
        )
        return Decimal(discount).quantize(Decimal("0.01"))


class RoomListItem(BaseSchema):
    """
    Room list item for list views.
    
    Minimal room information for efficient list rendering.
    """

    id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    floor_number: Union[int, None] = Field(default=None, description="Floor")
    wing: Union[str, None] = Field(default=None, description="Wing")
    room_type: RoomType = Field(..., description="Room type")
    total_beds: int = Field(..., ge=0, description="Total beds")
    available_beds: int = Field(..., ge=0, description="Available beds")
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent",
        ),
    ]
    is_ac: bool = Field(..., description="AC available")
    status: RoomStatus = Field(..., description="Status")
    is_available_for_booking: bool = Field(..., description="Bookable")
    primary_image: Union[str, None] = Field(default=None, description="Cover image")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_percentage(self) -> Decimal:
        """Calculate occupancy percentage."""
        if self.total_beds == 0:
            return Decimal("0.00")
        occupied = self.total_beds - self.available_beds
        return Decimal((occupied / self.total_beds * 100)).quantize(
            Decimal("0.01")
        )


class BedInfo(BaseSchema):
    """
    Brief bed information for room overview.
    
    Simplified bed data for quick views.
    """

    id: str = Field(..., description="Bed ID")
    bed_number: str = Field(..., description="Bed number")
    is_occupied: bool = Field(..., description="Occupied status")
    status: BedStatus = Field(..., description="Bed status")
    student_name: Union[str, None] = Field(
        default=None,
        description="Occupant name (if applicable)",
    )
    occupied_from: Union[Date, None] = Field(
        default=None,
        description="Occupancy start Date",
    )


class RoomWithBeds(BaseResponseSchema):
    """
    Room with bed information.
    
    Room overview with bed-level details.
    """

    hostel_id: str = Field(..., description="Hostel ID")
    room_number: str = Field(..., description="Room number")
    room_type: RoomType = Field(..., description="Room type")
    total_beds: int = Field(..., ge=0, description="Total beds")
    occupied_beds: int = Field(..., ge=0, description="Occupied beds")
    available_beds: int = Field(..., ge=0, description="Available beds")
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent",
        ),
    ]
    beds: List[BedInfo] = Field(
        default_factory=list,
        description="Bed details",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_rate(self) -> Decimal:
        """Calculate occupancy rate."""
        if self.total_beds == 0:
            return Decimal("0.00")
        return Decimal(
            (self.occupied_beds / self.total_beds * 100)
        ).quantize(Decimal("0.01"))


class RoomOccupancyStats(BaseSchema):
    """
    Room occupancy statistics.
    
    Provides occupancy metrics and revenue calculations.
    """

    room_id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    room_type: RoomType = Field(..., description="Room type")
    
    # Capacity
    total_beds: int = Field(..., ge=0, description="Total beds")
    occupied_beds: int = Field(..., ge=0, description="Occupied beds")
    available_beds: int = Field(..., ge=0, description="Available beds")
    reserved_beds: int = Field(
        default=0,
        ge=0,
        description="Reserved beds",
    )
    
    # Revenue with proper Decimal constraints
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent per bed",
        ),
    ]
    current_revenue: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Current monthly revenue",
        ),
    ]
    potential_revenue: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Potential revenue at full capacity",
        ),
    ]
    
    # Status
    status: RoomStatus = Field(..., description="Room status")
    is_available_for_booking: bool = Field(..., description="Booking availability")
    
    # Timestamps
    last_occupancy_change: Union[datetime, None] = Field(
        default=None,
        description="Last occupancy change timestamp",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_percentage(self) -> Decimal:
        """Calculate occupancy percentage."""
        if self.total_beds == 0:
            return Decimal("0.00")
        return Decimal(
            (self.occupied_beds / self.total_beds * 100)
        ).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def revenue_percentage(self) -> Decimal:
        """Calculate revenue realization percentage."""
        if self.potential_revenue == 0:
            return Decimal("0.00")
        return Decimal(
            (self.current_revenue / self.potential_revenue * 100)
        ).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def lost_revenue(self) -> Decimal:
        """Calculate lost revenue due to vacancy."""
        return self.potential_revenue - self.current_revenue


class RoomFinancialSummary(BaseSchema):
    """
    Room financial summary.
    
    Provides detailed financial metrics for a room.
    """

    room_id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    
    # Pricing with proper Decimal constraints
    price_monthly_per_bed: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent per bed",
        ),
    ]
    total_beds: int = Field(..., ge=0, description="Total beds")
    occupied_beds: int = Field(..., ge=0, description="Occupied beds")
    
    # Current month financial data
    current_month_revenue: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Current month revenue",
        ),
    ]
    current_month_collected: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Amount collected this month",
        ),
    ]
    current_month_pending: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Amount pending this month",
        ),
    ]
    
    # Historical financial data
    total_revenue_ytd: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=15,
            decimal_places=2,
            description="Year-to-Date total revenue",
        ),
    ]
    total_collected_ytd: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=15,
            decimal_places=2,
            description="Year-to-Date collected amount",
        ),
    ]
    average_occupancy_ytd: Annotated[
        Decimal,
        Field(
            ge=0,
            le=100,
            max_digits=5,
            decimal_places=2,
            description="Year-to-Date average occupancy %",
        ),
    ]
    
    # Projections
    projected_monthly_revenue: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Projected revenue at current occupancy",
        ),
    ]
    projected_yearly_revenue: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=15,
            decimal_places=2,
            description="Projected yearly revenue",
        ),
    ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def collection_rate(self) -> Decimal:
        """Calculate collection rate for current month."""
        if self.current_month_revenue == 0:
            return Decimal("100.00")
        return Decimal(
            (self.current_month_collected / self.current_month_revenue * 100)
        ).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_rate(self) -> Decimal:
        """Calculate current occupancy rate."""
        if self.total_beds == 0:
            return Decimal("0.00")
        return Decimal(
            (self.occupied_beds / self.total_beds * 100)
        ).quantize(Decimal("0.01"))