# --- File: app/schemas/visitor/visitor_dashboard.py ---
"""
Visitor dashboard schemas for comprehensive dashboard views.

This module defines schemas for visitor dashboard including saved hostels,
booking history, recent activity, recommendations, and alerts.
"""

from datetime import datetime, date as Date
from decimal import Decimal
from typing import Annotated, Dict, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, field_validator

from app.schemas.common.base import BaseSchema

__all__ = [
    "VisitorDashboard",
    "SavedHostels",
    "SavedHostelItem",
    "BookingHistory",
    "BookingHistoryItem",
    "RecentSearch",
    "RecentlyViewedHostel",
    "RecommendedHostel",
    "PriceDropAlert",
    "AvailabilityAlert",
]


class SavedHostelItem(BaseSchema):
    """
    Individual saved/favorite hostel item.
    
    Contains hostel details, pricing information, and
    tracking metadata for saved hostels.
    """

    hostel_id: UUID = Field(
        ...,
        description="Unique hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the hostel",
    )
    hostel_city: str = Field(
        ...,
        description="City where hostel is located",
    )
    # Updated for Pydantic v2
    starting_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Starting price per month",
    )
    average_rating: Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)] = Field(
        ...,
        description="Average rating (0-5)",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Number of available beds",
    )
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="URL to cover image",
    )

    # Save Metadata
    saved_at: datetime = Field(
        ...,
        description="When hostel was saved to favorites",
    )
    notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Personal notes about this hostel",
    )

    # Price Tracking
    price_when_saved: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Price when hostel was first saved",
    )
    current_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Current price",
    )
    price_changed: bool = Field(
        ...,
        description="Whether price has changed since saving",
    )
    price_change_percentage: Union[Decimal, None] = Field(
        default=None,
        description="Percentage change in price (negative = drop, positive = increase)",
    )

    @computed_field  # type: ignore[misc]
    @property
    def has_availability(self) -> bool:
        """Check if hostel has available beds."""
        return self.available_beds > 0

    @computed_field  # type: ignore[misc]
    @property
    def price_drop_amount(self) -> Union[Decimal, None]:
        """Calculate absolute price drop amount if applicable."""
        if self.price_changed and self.current_price < self.price_when_saved:
            return (self.price_when_saved - self.current_price).quantize(
                Decimal("0.01")
            )
        return None

    @computed_field  # type: ignore[misc]
    @property
    def is_good_deal(self) -> bool:
        """Determine if this is a good deal (price dropped or high rating with availability)."""
        price_dropped = (
            self.price_changed and self.current_price < self.price_when_saved
        )
        high_rated_available = self.average_rating >= Decimal("4.0") and self.has_availability
        return price_dropped or high_rated_available


class SavedHostels(BaseSchema):
    """
    Collection of saved/favorite hostels.
    """

    total_saved: int = Field(
        ...,
        ge=0,
        description="Total number of saved hostels",
    )
    hostels: List[SavedHostelItem] = Field(
        default_factory=list,
        description="List of saved hostel items",
    )

    @computed_field  # type: ignore[misc]
    @property
    def hostels_with_price_drops(self) -> int:
        """Count hostels with price drops."""
        return sum(
            1
            for h in self.hostels
            if h.price_changed and h.current_price < h.price_when_saved
        )

    @computed_field  # type: ignore[misc]
    @property
    def hostels_with_availability(self) -> int:
        """Count hostels with available beds."""
        return sum(1 for h in self.hostels if h.has_availability)


class BookingHistoryItem(BaseSchema):
    """
    Individual booking in history.
    
    Contains booking details, status, and available actions.
    """

    booking_id: UUID = Field(
        ...,
        description="Unique booking identifier",
    )
    booking_reference: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Human-readable booking reference",
    )
    hostel_id: UUID = Field(
        ...,
        description="Associated hostel ID",
    )
    hostel_name: str = Field(
        ...,
        description="Name of the hostel",
    )
    room_type: str = Field(
        ...,
        description="Type of room booked",
    )

    # Dates
    booking_date: datetime = Field(
        ...,
        description="When booking was made",
    )
    check_in_date: Date = Field(
        ...,
        description="Check-in Date",
    )
    duration_months: int = Field(
        ...,
        ge=1,
        description="Booking duration in months",
    )

    # Status and Payment
    status: str = Field(
        ...,
        description="Current booking status",
    )
    total_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total booking amount",
    )

    # Available Actions
    can_cancel: bool = Field(
        ...,
        description="Whether booking can be cancelled",
    )
    can_modify: bool = Field(
        ...,
        description="Whether booking can be modified",
    )
    can_review: bool = Field(
        ...,
        description="Whether hostel can be reviewed",
    )

    @computed_field  # type: ignore[misc]
    @property
    def check_out_date(self) -> Date:
        """Calculate check-out Date based on duration."""
        from dateutil.relativedelta import relativedelta

        return self.check_in_date + relativedelta(months=self.duration_months)

    @computed_field  # type: ignore[misc]
    @property
    def days_until_checkin(self) -> int:
        """Calculate days until check-in."""
        return (self.check_in_date - Date.today()).days

    @computed_field  # type: ignore[misc]
    @property
    def is_upcoming(self) -> bool:
        """Check if booking is upcoming."""
        return self.check_in_date > Date.today()


class BookingHistory(BaseSchema):
    """
    Booking history summary with statistics.
    """

    total_bookings: int = Field(
        ...,
        ge=0,
        description="Total number of bookings",
    )
    active_bookings: int = Field(
        ...,
        ge=0,
        description="Number of active bookings",
    )
    completed_bookings: int = Field(
        ...,
        ge=0,
        description="Number of completed bookings",
    )
    cancelled_bookings: int = Field(
        ...,
        ge=0,
        description="Number of cancelled bookings",
    )

    bookings: List[BookingHistoryItem] = Field(
        default_factory=list,
        description="List of booking items",
    )

    @computed_field  # type: ignore[misc]
    @property
    def cancellation_rate(self) -> Decimal:
        """Calculate cancellation rate as percentage."""
        if self.total_bookings == 0:
            return Decimal("0")
        return Decimal(
            (self.cancelled_bookings / self.total_bookings) * 100
        ).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[misc]
    @property
    def completion_rate(self) -> Decimal:
        """Calculate completion rate as percentage."""
        if self.total_bookings == 0:
            return Decimal("0")
        return Decimal(
            (self.completed_bookings / self.total_bookings) * 100
        ).quantize(Decimal("0.01"))


class RecentSearch(BaseSchema):
    """
    Recent search item with metadata.
    """

    search_id: UUID = Field(
        ...,
        description="Unique search identifier",
    )
    search_query: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Search query text",
    )
    filters_applied: Dict = Field(
        default_factory=dict,
        description="Filters applied in this search",
    )
    results_count: int = Field(
        ...,
        ge=0,
        description="Number of results found",
    )
    searched_at: datetime = Field(
        ...,
        description="When search was performed",
    )

    @computed_field  # type: ignore[misc]
    @property
    def filters_count(self) -> int:
        """Count number of filters applied."""
        return len(self.filters_applied)


class RecentlyViewedHostel(BaseSchema):
    """
    Recently viewed hostel item.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    hostel_city: str = Field(
        ...,
        description="City",
    )
    starting_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Starting price",
    )
    average_rating: Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)] = Field(
        ...,
        description="Average rating",
    )
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image URL",
    )

    viewed_at: datetime = Field(
        ...,
        description="When hostel was last viewed",
    )
    view_count: int = Field(
        ...,
        ge=1,
        description="Number of times this hostel was viewed",
    )

    @computed_field  # type: ignore[misc]
    @property
    def is_highly_viewed(self) -> bool:
        """Check if hostel has been viewed multiple times (interest indicator)."""
        return self.view_count >= 3


class RecommendedHostel(BaseSchema):
    """
    Recommended hostel based on visitor preferences.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    hostel_city: str = Field(
        ...,
        description="City",
    )
    starting_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Starting price",
    )
    average_rating: Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)] = Field(
        ...,
        description="Average rating",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds",
    )
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image URL",
    )

    match_score: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="How well hostel matches visitor preferences (0-100)",
    )
    match_reasons: List[str] = Field(
        ...,
        min_length=1,
        description="Reasons why this hostel is recommended",
    )

    @field_validator("match_reasons")
    @classmethod
    def validate_match_reasons(cls, v: List[str]) -> List[str]:
        """Ensure match reasons are not empty."""
        if not v or len(v) == 0:
            raise ValueError("At least one match reason must be provided")
        return v

    @computed_field  # type: ignore[misc]
    @property
    def is_excellent_match(self) -> bool:
        """Check if this is an excellent match (score >= 80)."""
        return self.match_score >= Decimal("80")


class PriceDropAlert(BaseSchema):
    """
    Price drop alert for saved hostel.
    """

    alert_id: UUID = Field(
        ...,
        description="Alert identifier",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    previous_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Previous price",
    )
    new_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="New reduced price",
    )
    discount_percentage: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Discount percentage",
    )

    alert_created: datetime = Field(
        ...,
        description="When alert was created",
    )
    is_read: bool = Field(
        ...,
        description="Whether alert has been read",
    )

    @computed_field  # type: ignore[misc]
    @property
    def savings_amount(self) -> Decimal:
        """Calculate absolute savings amount."""
        return (self.previous_price - self.new_price).quantize(Decimal("0.01"))


class AvailabilityAlert(BaseSchema):
    """
    Availability alert for previously full hostel.
    """

    alert_id: UUID = Field(
        ...,
        description="Alert identifier",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    room_type: str = Field(
        ...,
        description="Room type that became available",
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Alert message",
    )

    alert_created: datetime = Field(
        ...,
        description="When alert was created",
    )
    is_read: bool = Field(
        ...,
        description="Whether alert has been read",
    )


class VisitorDashboard(BaseSchema):
    """
    Comprehensive visitor dashboard overview.
    
    Contains all information needed for visitor dashboard including
    saved hostels, booking history, recent activity, recommendations,
    and alerts.
    """

    visitor_id: UUID = Field(
        ...,
        description="Visitor identifier",
    )
    visitor_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Visitor full name",
    )

    # Saved Hostels Section
    saved_hostels: SavedHostels = Field(
        ...,
        description="Saved/favorite hostels",
    )

    # Booking History Section
    booking_history: BookingHistory = Field(
        ...,
        description="Booking history and statistics",
    )

    # Recent Activity
    recent_searches: List[RecentSearch] = Field(
        default_factory=list,
        max_length=5,
        description="5 most recent searches",
    )
    recently_viewed: List[RecentlyViewedHostel] = Field(
        default_factory=list,
        max_length=10,
        description="10 most recently viewed hostels",
    )

    # Recommendations
    recommended_hostels: List[RecommendedHostel] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 recommended hostels",
    )

    # Alerts
    price_drop_alerts: List[PriceDropAlert] = Field(
        default_factory=list,
        description="Active price drop alerts",
    )
    availability_alerts: List[AvailabilityAlert] = Field(
        default_factory=list,
        description="Active availability alerts",
    )

    # Overall Statistics
    total_searches: int = Field(
        ...,
        ge=0,
        description="Total number of searches performed",
    )
    total_hostel_views: int = Field(
        ...,
        ge=0,
        description="Total hostel views",
    )
    total_bookings: int = Field(
        ...,
        ge=0,
        description="Total bookings made",
    )

    @computed_field  # type: ignore[misc]
    @property
    def unread_alerts_count(self) -> int:
        """Count total unread alerts."""
        price_alerts = sum(1 for alert in self.price_drop_alerts if not alert.is_read)
        availability_alerts = sum(
            1 for alert in self.availability_alerts if not alert.is_read
        )
        return price_alerts + availability_alerts

    @computed_field  # type: ignore[misc]
    @property
    def has_activity(self) -> bool:
        """Check if visitor has any activity."""
        return (
            self.total_searches > 0
            or self.total_hostel_views > 0
            or self.total_bookings > 0
        )