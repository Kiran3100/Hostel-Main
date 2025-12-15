"""
Enhanced hostel selector UI schemas with comprehensive filtering and organization.

Provides optimized schemas for hostel selection dropdown/sidebar with quick stats,
favorites management, and recent access tracking for improved user experience.

Fully migrated to Pydantic v2.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "HostelSelectorResponse",
    "HostelSelectorItem",
    "RecentHostels",
    "RecentHostelItem",
    "FavoriteHostels",
    "FavoriteHostelItem",
    "UpdateFavoriteRequest",
]


class HostelSelectorItem(BaseSchema):
    """
    Enhanced individual hostel item in selector with comprehensive quick view.
    
    Provides essential hostel information with visual indicators,
    quick statistics, and status information for efficient selection.
    """
    
    model_config = ConfigDict()
    
    # Hostel identification
    hostel_id: UUID = Field(..., description="Hostel unique identifier")
    hostel_name: str = Field(..., description="Hostel display name")
    hostel_city: str = Field(..., description="Hostel city location")
    hostel_type: str = Field(..., description="Hostel type (boys/girls/co-ed)")
    hostel_address: Optional[str] = Field(None, description="Short address for display")
    
    # Visual indicators and flags
    is_active: bool = Field(True, description="Currently active hostel in context")
    is_primary: bool = Field(False, description="Primary hostel for this admin")
    is_favorite: bool = Field(False, description="Marked as favorite by admin")
    is_recently_accessed: bool = Field(False, description="Accessed in last 24 hours")
    
    # Quick statistics for decision making - Pydantic v2: Decimal with constraints
    occupancy_percentage: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), le=Decimal("100"), description="Current occupancy rate"
    )
    total_students: int = Field(0, ge=0, description="Total student count")
    available_beds: int = Field(0, ge=0, description="Available beds count")
    
    # Alert indicators
    pending_bookings: int = Field(0, ge=0, description="Pending booking requests")
    pending_complaints: int = Field(0, ge=0, description="Open complaints")
    urgent_tasks: int = Field(0, ge=0, description="Urgent tasks count")
    
    # Permission summary
    permission_level: str = Field(..., description="Admin permission level for this hostel")
    can_manage: bool = Field(True, description="Has management permissions")
    
    # Activity tracking
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    access_count: int = Field(0, ge=0, description="Total access count")
    
    # Display customization
    display_order: int = Field(0, description="Custom display order")
    custom_label: Optional[str] = Field(None, description="Custom label/nickname for hostel")

    @computed_field
    @property
    def requires_attention(self) -> bool:
        """Determine if hostel requires immediate attention."""
        return (
            self.urgent_tasks > 0 or
            self.pending_complaints > 5 or
            self.occupancy_percentage < Decimal("50.00")
        )

    @computed_field
    @property
    def notification_badge_count(self) -> int:
        """Calculate notification badge count for visual indicator."""
        return self.pending_bookings + self.urgent_tasks

    @computed_field
    @property
    def status_indicator_color(self) -> str:
        """Determine status indicator color for UI."""
        if self.urgent_tasks > 0:
            return "red"  # Critical
        elif self.pending_complaints > 5 or self.occupancy_percentage < Decimal("50.00"):
            return "yellow"  # Warning
        else:
            return "green"  # Good

    @computed_field
    @property
    def display_label(self) -> str:
        """Get display label (custom or default)."""
        return self.custom_label if self.custom_label else self.hostel_name

    @computed_field
    @property
    def quick_summary(self) -> str:
        """Generate quick summary text for tooltip."""
        return (
            f"{int(self.occupancy_percentage)}% occupied • "
            f"{self.total_students} students • "
            f"{self.available_beds} beds available"
        )


class HostelSelectorResponse(BaseSchema):
    """
    Enhanced hostel selector dropdown/sidebar response with organized data.
    
    Provides complete hostel list with categorization, recent access,
    favorites, and intelligent sorting for optimal user experience.
    """
    
    model_config = ConfigDict()
    
    admin_id: UUID = Field(..., description="Admin user ID")
    total_hostels: int = Field(..., ge=0, description="Total hostels managed")
    active_hostels: int = Field(..., ge=0, description="Active hostel assignments")
    
    # Active context
    active_hostel_id: Optional[UUID] = Field(None, description="Currently active hostel ID")
    active_hostel_name: Optional[str] = Field(None, description="Currently active hostel name")
    
    # Organized hostel lists
    hostels: List[HostelSelectorItem] = Field(
        default_factory=list,
        description="All hostels with details"
    )
    
    # Quick access lists (IDs for reference)
    recent_hostel_ids: List[UUID] = Field(
        default_factory=list,
        max_length=10,
        description="Recently accessed hostel IDs (max 10)"
    )
    favorite_hostel_ids: List[UUID] = Field(
        default_factory=list,
        description="Favorite hostel IDs"
    )
    primary_hostel_id: Optional[UUID] = Field(None, description="Primary hostel ID")
    
    # Hostel requiring attention
    attention_required_ids: List[UUID] = Field(
        default_factory=list,
        description="Hostels requiring immediate attention"
    )
    
    # Summary statistics - Pydantic v2: Decimal with constraints
    total_pending_tasks: int = Field(0, ge=0, description="Total pending tasks across all hostels")
    total_urgent_alerts: int = Field(0, ge=0, description="Total urgent alerts")
    avg_occupancy_percentage: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), le=Decimal("100"), description="Average occupancy across hostels"
    )

    @computed_field
    @property
    def has_critical_alerts(self) -> bool:
        """Check if any hostel has critical alerts."""
        return len(self.attention_required_ids) > 0

    @computed_field
    @property
    def hostels_by_category(self) -> Dict[str, List[HostelSelectorItem]]:
        """Organize hostels by category for UI grouping."""
        return {
            "primary": [h for h in self.hostels if h.is_primary],
            "favorites": [h for h in self.hostels if h.is_favorite],
            "recent": [h for h in self.hostels if h.hostel_id in self.recent_hostel_ids[:5]],
            "attention_required": [h for h in self.hostels if h.requires_attention],
            "others": [
                h for h in self.hostels
                if not (h.is_primary or h.is_favorite or h.hostel_id in self.recent_hostel_ids[:5])
            ]
        }

    @computed_field
    @property
    def selector_summary(self) -> str:
        """Generate summary text for selector header."""
        if self.active_hostel_name:
            return f"Managing {self.total_hostels} hostels • Active: {self.active_hostel_name}"
        else:
            return f"Managing {self.total_hostels} hostels"


class RecentHostelItem(BaseSchema):
    """
    Enhanced recent hostel item with access patterns.
    
    Tracks recent hostel access with frequency and recency metrics
    for intelligent sorting and quick access recommendations.
    """
    
    model_config = ConfigDict()
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    hostel_city: str = Field(..., description="Hostel city")
    hostel_type: str = Field(..., description="Hostel type")
    
    # Access tracking
    last_accessed: datetime = Field(..., description="Last access timestamp")
    access_count: int = Field(..., ge=1, description="Total access count")
    access_count_last_7_days: int = Field(0, ge=0, description="Access count in last 7 days")
    access_count_last_30_days: int = Field(0, ge=0, description="Access count in last 30 days")
    
    # Session metrics - Pydantic v2: Decimal with ge constraint
    avg_session_duration_minutes: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), description="Average session duration"
    )
    total_session_time_minutes: int = Field(0, ge=0, description="Total session time")
    
    # Quick stats for recent access
    last_occupancy: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), le=Decimal("100")
    )
    pending_tasks_on_last_visit: int = Field(0, ge=0)

    @computed_field
    @property
    def hours_since_access(self) -> int:
        """Calculate hours since last access."""
        delta = datetime.utcnow() - self.last_accessed
        return int(delta.total_seconds() // 3600)

    @computed_field
    @property
    def access_frequency_score(self) -> Decimal:
        """Calculate access frequency score for ranking."""
        # Recent access gets higher score
        recency_score = max(0, 100 - self.hours_since_access)
        
        # Frequency score based on 7-day access
        frequency_score = min(self.access_count_last_7_days * 10, 100)
        
        # Combined score (60% frequency, 40% recency)
        total_score = (frequency_score * 0.6) + (recency_score * 0.4)
        
        return Decimal(str(total_score)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def is_frequent(self) -> bool:
        """Determine if this is a frequently accessed hostel."""
        return self.access_count_last_7_days >= 5


class RecentHostels(BaseSchema):
    """
    Enhanced recent hostels list with intelligent sorting.
    
    Provides recently accessed hostels sorted by access patterns
    with analytics for usage optimization recommendations.
    """
    
    model_config = ConfigDict()
    
    admin_id: UUID = Field(..., description="Admin user ID")
    
    hostels: List[RecentHostelItem] = Field(
        default_factory=list,
        max_length=20,
        description="Recently accessed hostels (max 20)"
    )
    
    # Summary metrics
    total_recent_hostels: int = Field(0, ge=0, description="Total recent hostels count")
    most_frequent_hostel_id: Optional[UUID] = Field(None, description="Most frequently accessed hostel")
    
    # Time range for recent access
    tracking_period_days: int = Field(30, ge=1, description="Tracking period in days")

    @computed_field
    @property
    def access_pattern_summary(self) -> str:
        """Generate access pattern summary."""
        if not self.hostels:
            return "No recent access"
        
        frequent_count = sum(1 for h in self.hostels if h.is_frequent)
        
        if frequent_count > 0:
            return f"{frequent_count} frequently accessed • {len(self.hostels)} total recent"
        else:
            return f"{len(self.hostels)} hostels accessed recently"


class FavoriteHostelItem(BaseSchema):
    """
    Enhanced favorite hostel item with customization options.
    
    Supports hostel favorites with custom labels, notes,
    and priority ordering for personalized quick access.
    """
    
    model_config = ConfigDict()
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    hostel_city: str = Field(..., description="Hostel city")
    hostel_type: str = Field(..., description="Hostel type")
    
    # Favorite metadata
    added_to_favorites: datetime = Field(..., description="Timestamp when added to favorites")
    custom_label: Optional[str] = Field(
        None, max_length=100, description="Custom label/nickname for hostel"
    )
    notes: Optional[str] = Field(
        None, max_length=500, description="Personal notes about hostel"
    )
    display_order: int = Field(0, description="Custom display order priority")
    
    # Quick stats - Pydantic v2: Decimal with constraints
    current_occupancy: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), le=Decimal("100")
    )
    pending_items: int = Field(0, ge=0, description="Total pending items count")
    
    # Access tracking for favorites
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    access_count_since_favorited: int = Field(0, ge=0)

    @computed_field
    @property
    def days_in_favorites(self) -> int:
        """Calculate days since added to favorites."""
        delta = datetime.utcnow() - self.added_to_favorites
        return delta.days

    @computed_field
    @property
    def display_name(self) -> str:
        """Get display name (custom label or hostel name)."""
        return self.custom_label if self.custom_label else self.hostel_name

    @computed_field
    @property
    def is_recently_accessed(self) -> bool:
        """Check if accessed in last 24 hours."""
        if not self.last_accessed:
            return False
        hours_since = (datetime.utcnow() - self.last_accessed).total_seconds() / 3600
        return hours_since <= 24


class FavoriteHostels(BaseSchema):
    """
    Enhanced favorites list with organization and management.
    
    Provides organized favorites with custom ordering,
    labels, and quick access to frequently used hostels.
    """
    
    model_config = ConfigDict()
    
    admin_id: UUID = Field(..., description="Admin user ID")
    
    hostels: List[FavoriteHostelItem] = Field(
        default_factory=list,
        description="Favorite hostels sorted by display_order"
    )
    
    total_favorites: int = Field(0, ge=0, description="Total favorite hostels count")
    max_favorites_allowed: int = Field(20, ge=1, description="Maximum favorites allowed")

    @computed_field
    @property
    def can_add_more(self) -> bool:
        """Check if more favorites can be added."""
        return self.total_favorites < self.max_favorites_allowed

    @computed_field
    @property
    def favorites_by_city(self) -> Dict[str, List[FavoriteHostelItem]]:
        """Group favorites by city."""
        grouped: Dict[str, List[FavoriteHostelItem]] = {}
        for hostel in self.hostels:
            city = hostel.hostel_city
            if city not in grouped:
                grouped[city] = []
            grouped[city].append(hostel)
        return grouped


class UpdateFavoriteRequest(BaseCreateSchema):
    """
    Enhanced favorite update request with comprehensive customization.
    
    Supports adding/removing favorites with custom labels,
    notes, and display order preferences.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    hostel_id: UUID = Field(..., description="Hostel ID to add/remove from favorites")
    is_favorite: bool = Field(..., description="True to add, False to remove")
    
    # Customization options (only used when is_favorite=True)
    custom_label: Optional[str] = Field(
        None,
        max_length=100,
        description="Custom label/nickname for hostel"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Personal notes about this hostel"
    )
    display_order: Optional[int] = Field(
        None,
        ge=0,
        description="Custom display order (0 = highest priority)"
    )

    @field_validator("custom_label", "notes")
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize text fields."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Normalize whitespace
            v = " ".join(v.split())
        return v

    @model_validator(mode="after")
    def validate_customization_logic(self) -> "UpdateFavoriteRequest":
        """Validate that customization is only provided when adding to favorites."""
        if not self.is_favorite:
            # Clear customization fields when removing from favorites
            if any([self.custom_label, self.notes, self.display_order is not None]):
                # Silently ignore customization when removing
                self.custom_label = None
                self.notes = None
                self.display_order = None
        
        return self