# --- File: app/schemas/mess/mess_menu_response.py ---
"""
Mess menu response schemas for API responses.

Provides various response formats for menu data including
detailed, summary, weekly, and monthly views with computed fields.
"""

from datetime import date as Date, datetime, time
from decimal import Decimal
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import MealType

__all__ = [
    "MenuResponse",
    "MenuDetail",
    "WeeklyMenu",
    "DailyMenuSummary",
    "MonthlyMenu",
    "TodayMenu",
    "MenuListItem",
]


class MenuResponse(BaseResponseSchema):
    """
    Standard menu response with essential information.
    
    Lightweight response schema for list views and basic queries.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    day_of_week: str = Field(
        ...,
        description="Day of the week",
    )
    breakfast_items: List[str] = Field(
        default_factory=list,
        description="Breakfast items",
    )
    lunch_items: List[str] = Field(
        default_factory=list,
        description="Lunch items",
    )
    snacks_items: List[str] = Field(
        default_factory=list,
        description="Snacks items",
    )
    dinner_items: List[str] = Field(
        default_factory=list,
        description="Dinner items",
    )
    is_special_menu: bool = Field(
        ...,
        description="Whether this is a special menu",
    )
    special_occasion: Union[str, None] = Field(
        None,
        description="Special occasion name",
    )
    is_published: bool = Field(
        ...,
        description="Whether menu is published to students",
    )
    average_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average student rating",
    )

    @computed_field  # type: ignore[misc]
    @property
    def total_items_count(self) -> int:
        """Calculate total number of items across all meals."""
        return (
            len(self.breakfast_items)
            + len(self.lunch_items)
            + len(self.snacks_items)
            + len(self.dinner_items)
        )

    @computed_field  # type: ignore[misc]
    @property
    def is_complete(self) -> bool:
        """Check if menu has items for all main meals."""
        return bool(
            self.breakfast_items
            and (self.lunch_items or self.dinner_items)
        )


class MenuDetail(BaseResponseSchema):
    """
    Detailed menu information with complete metadata.
    
    Comprehensive response including all menu details, ratings,
    and management information.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    day_of_week: str = Field(
        ...,
        description="Day of the week",
    )

    # Meals with timings
    breakfast_items: List[str] = Field(
        default_factory=list,
        description="Breakfast menu items",
    )
    breakfast_time: Union[time, None] = Field(
        None,
        description="Breakfast serving time",
    )
    
    lunch_items: List[str] = Field(
        default_factory=list,
        description="Lunch menu items",
    )
    lunch_time: Union[time, None] = Field(
        None,
        description="Lunch serving time",
    )
    
    snacks_items: List[str] = Field(
        default_factory=list,
        description="Snacks menu items",
    )
    snacks_time: Union[time, None] = Field(
        None,
        description="Snacks serving time",
    )
    
    dinner_items: List[str] = Field(
        default_factory=list,
        description="Dinner menu items",
    )
    dinner_time: Union[time, None] = Field(
        None,
        description="Dinner serving time",
    )

    # Dietary options
    vegetarian_available: bool = Field(
        ...,
        description="Vegetarian options available",
    )
    non_vegetarian_available: bool = Field(
        ...,
        description="Non-vegetarian options available",
    )
    vegan_available: bool = Field(
        ...,
        description="Vegan options available",
    )
    jain_available: bool = Field(
        ...,
        description="Jain dietary options available",
    )

    # Special menu information
    is_special_menu: bool = Field(
        ...,
        description="Special menu indicator",
    )
    special_occasion: Union[str, None] = Field(
        None,
        description="Special occasion name",
    )
    special_notes: Union[str, None] = Field(
        None,
        description="Special menu notes",
    )

    # Management information
    created_by: UUID = Field(
        ...,
        description="Creator user ID",
    )
    created_by_name: str = Field(
        ...,
        description="Creator name",
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )
    
    approved_by: Union[UUID, None] = Field(
        None,
        description="Approver user ID",
    )
    approved_by_name: Union[str, None] = Field(
        None,
        description="Approver name",
    )
    approved_at: Union[datetime, None] = Field(
        None,
        description="Approval timestamp",
    )

    # Publication status
    is_published: bool = Field(
        ...,
        description="Publication status",
    )
    published_at: Union[datetime, None] = Field(
        None,
        description="Publication timestamp",
    )
    published_by: Union[UUID, None] = Field(
        None,
        description="Publisher user ID",
    )

    # Feedback and ratings
    average_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average rating",
    )
    total_feedback_count: int = Field(
        default=0,
        ge=0,
        description="Total feedback count",
    )
    rating_breakdown: Union[Dict[str, int], None] = Field(
        None,
        description="Rating distribution (1-5 stars)",
    )

    # Metadata
    last_updated: datetime = Field(
        ...,
        description="Last update timestamp",
    )
    last_updated_by: Union[UUID, None] = Field(
        None,
        description="Last updater user ID",
    )

    @computed_field  # type: ignore[misc]
    @property
    def approval_status(self) -> str:
        """Get approval status label."""
        if self.approved_by:
            return "approved"
        elif self.is_published:
            return "published_without_approval"
        else:
            return "pending"

    @computed_field  # type: ignore[misc]
    @property
    def has_ratings(self) -> bool:
        """Check if menu has received any ratings."""
        return self.total_feedback_count > 0


class DailyMenuSummary(BaseSchema):
    """
    Daily menu summary for weekly/monthly views.
    
    Compact representation of single day's menu for
    calendar and list views.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    day_of_week: str = Field(
        ...,
        description="Day of the week",
    )
    breakfast: List[str] = Field(
        default_factory=list,
        description="Breakfast items (top 3 shown)",
    )
    lunch: List[str] = Field(
        default_factory=list,
        description="Lunch items (top 3 shown)",
    )
    dinner: List[str] = Field(
        default_factory=list,
        description="Dinner items (top 3 shown)",
    )
    is_special: bool = Field(
        ...,
        description="Special menu indicator",
    )
    special_occasion: Union[str, None] = Field(
        None,
        description="Special occasion name",
    )
    average_rating: Union[Decimal, None] = Field(
        None,
        ge=0,
        le=5,
        description="Average rating",
    )
    is_published: bool = Field(
        default=False,
        description="Publication status",
    )

    @computed_field  # type: ignore[misc]
    @property
    def has_complete_menu(self) -> bool:
        """Check if menu has all main meals."""
        return bool(self.breakfast and self.lunch and self.dinner)

    @computed_field  # type: ignore[misc]
    @property
    def rating_stars(self) -> str:
        """Get star rating display string."""
        if self.average_rating is None:
            return "No ratings"
        
        rating = float(self.average_rating)
        full_stars = int(rating)
        half_star = rating - full_stars >= 0.5
        
        stars = "★" * full_stars
        if half_star:
            stars += "½"
        
        return f"{stars} ({rating:.1f})"


class WeeklyMenu(BaseSchema):
    """
    Weekly menu display with all days.
    
    Provides complete week view for menu planning and
    student information.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    week_number: int = Field(
        ...,
        ge=1,
        le=53,
        description="Week number in year",
    )
    year: int = Field(
        ...,
        ge=2000,
        description="Year",
    )
    week_start_date: Date = Field(
        ...,
        description="Week start Date (Monday)",
    )
    week_end_date: Date = Field(
        ...,
        description="Week end Date (Sunday)",
    )
    menus: List[DailyMenuSummary] = Field(
        ...,
        min_length=0,
        max_length=7,
        description="Daily menus for the week",
    )
    total_menus: int = Field(
        default=0,
        ge=0,
        le=7,
        description="Number of menus available",
    )
    special_days_count: int = Field(
        default=0,
        ge=0,
        le=7,
        description="Number of special menus",
    )
    average_weekly_rating: Union[Decimal, None] = Field(
        None,
        ge=0,
        le=5,
        description="Average rating for the week",
    )

    @computed_field  # type: ignore[misc]
    @property
    def completion_percentage(self) -> Decimal:
        """Calculate percentage of days with menus."""
        if self.total_menus == 0:
            return Decimal("0.00")
        return round(Decimal(self.total_menus) / Decimal("7") * 100, 2)

    @computed_field  # type: ignore[misc]
    @property
    def is_complete(self) -> bool:
        """Check if all 7 days have menus."""
        return self.total_menus == 7


class MonthlyMenu(BaseSchema):
    """
    Monthly menu calendar view.
    
    Provides complete month overview with all menus
    and summary statistics.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format",
    )
    month_name: str = Field(
        ...,
        description="Month name (January, February, etc.)",
    )
    year: int = Field(
        ...,
        ge=2000,
        description="Year",
    )
    menus_by_date: Dict[str, DailyMenuSummary] = Field(
        ...,
        description="Menus indexed by Date (YYYY-MM-DD)",
    )
    
    # Summary statistics
    total_days: int = Field(
        ...,
        ge=28,
        le=31,
        description="Total days in month",
    )
    menus_created: int = Field(
        ...,
        ge=0,
        description="Number of menus created",
    )
    menus_published: int = Field(
        default=0,
        ge=0,
        description="Number of published menus",
    )
    special_days: int = Field(
        default=0,
        ge=0,
        description="Number of special occasion menus",
    )
    average_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average monthly rating",
    )
    total_feedbacks: int = Field(
        default=0,
        ge=0,
        description="Total feedback count for month",
    )

    @computed_field  # type: ignore[misc]
    @property
    def completion_rate(self) -> Decimal:
        """Calculate menu completion rate for month."""
        if self.total_days == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.menus_created) / Decimal(self.total_days) * 100,
            2,
        )

    @computed_field  # type: ignore[misc]
    @property
    def publication_rate(self) -> Decimal:
        """Calculate publication rate."""
        if self.menus_created == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.menus_published) / Decimal(self.menus_created) * 100,
            2,
        )


class TodayMenu(BaseSchema):
    """
    Today's menu for student view.
    
    Simplified, student-friendly view of current day's menu
    with timing and dietary information.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    menu_date: Date = Field(
        ...,
        description="Today's Date",
    )
    day_of_week: str = Field(
        ...,
        description="Day of the week",
    )

    # Breakfast
    breakfast: List[str] = Field(
        ...,
        description="Breakfast items",
    )
    breakfast_time: str = Field(
        ...,
        description="Breakfast timing (formatted)",
    )
    
    # Lunch
    lunch: List[str] = Field(
        ...,
        description="Lunch items",
    )
    lunch_time: str = Field(
        ...,
        description="Lunch timing (formatted)",
    )
    
    # Snacks
    snacks: List[str] = Field(
        default_factory=list,
        description="Snacks items",
    )
    snacks_time: Union[str, None] = Field(
        None,
        description="Snacks timing (formatted)",
    )
    
    # Dinner
    dinner: List[str] = Field(
        ...,
        description="Dinner items",
    )
    dinner_time: str = Field(
        ...,
        description="Dinner timing (formatted)",
    )

    # Special menu
    is_special: bool = Field(
        ...,
        description="Special menu indicator",
    )
    special_occasion: Union[str, None] = Field(
        None,
        description="Special occasion name",
    )
    special_message: Union[str, None] = Field(
        None,
        description="Special message for students",
    )

    # Dietary information
    dietary_note: Union[str, None] = Field(
        None,
        description="Dietary information note",
    )
    allergen_warning: Union[str, None] = Field(
        None,
        description="Allergen warning",
    )

    # Student interaction
    can_provide_feedback: bool = Field(
        default=True,
        description="Whether student can provide feedback",
    )
    already_rated: bool = Field(
        default=False,
        description="Whether student has already rated",
    )

    @computed_field  # type: ignore[misc]
    @property
    def next_meal(self) -> str:
        """Determine next upcoming meal based on current time."""
        from datetime import datetime, time as dt_time
        
        current_time = datetime.now().time()
        
        # Parse times (assuming format like "07:30 AM")
        def parse_time(time_str: str) -> dt_time:
            try:
                return datetime.strptime(time_str, "%I:%M %p").time()
            except:
                return dt_time(0, 0)
        
        breakfast_time = parse_time(self.breakfast_time)
        lunch_time = parse_time(self.lunch_time)
        dinner_time = parse_time(self.dinner_time)
        
        if current_time < breakfast_time:
            return "Breakfast"
        elif current_time < lunch_time:
            return "Lunch"
        elif self.snacks_time and current_time < parse_time(self.snacks_time):
            return "Snacks"
        elif current_time < dinner_time:
            return "Dinner"
        else:
            return "Dinner service ended"


class MenuListItem(BaseSchema):
    """
    Minimal menu list item for efficient list rendering.
    
    Optimized for pagination and management list views.
    """

    id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    day_of_week: str = Field(
        ...,
        description="Day of the week",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    total_items: int = Field(
        ...,
        ge=0,
        description="Total menu items across all meals",
    )
    is_special: bool = Field(
        ...,
        description="Special menu indicator",
    )
    is_published: bool = Field(
        ...,
        description="Publication status",
    )
    average_rating: Union[Decimal, None] = Field(
        None,
        ge=0,
        le=5,
        description="Average rating",
    )
    feedback_count: int = Field(
        default=0,
        ge=0,
        description="Number of feedbacks",
    )

    @computed_field  # type: ignore[misc]
    @property
    def status_badge_color(self) -> str:
        """Get status badge color for UI."""
        if self.is_published:
            return "green"
        else:
            return "yellow"

    @computed_field  # type: ignore[misc]
    @property
    def rating_badge_color(self) -> str:
        """Get rating badge color based on average rating."""
        if self.average_rating is None:
            return "gray"
        
        rating = float(self.average_rating)
        if rating >= 4.5:
            return "green"
        elif rating >= 3.5:
            return "yellow"
        elif rating >= 2.5:
            return "orange"
        else:
            return "red"