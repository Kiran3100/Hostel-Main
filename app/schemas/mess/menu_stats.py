# --- File: app/schemas/mess/menu_stats.py ---
"""
Menu statistics and analytics schemas.

Provides comprehensive statistics for menu performance and trends.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseSchema

__all__ = [
    "MenuStats",
    "ItemPopularity",
    "MealTypeStats",
    "DietaryDistribution",
]


class ItemPopularity(BaseSchema):
    """
    Individual item popularity statistics.
    """

    item_name: str = Field(..., description="Item name")
    appearance_count: int = Field(..., ge=0, description="Times appeared in menus")
    average_rating: Union[Decimal, None] = Field(None, ge=0, le=5)
    total_feedbacks: int = Field(default=0, ge=0)
    popularity_rank: int = Field(..., ge=1, description="Popularity ranking")


class MealTypeStats(BaseSchema):
    """
    Statistics for a specific meal type.
    """

    meal_type: str = Field(
        ...,
        pattern=r"^(breakfast|lunch|snacks|dinner)$",
        description="Meal type",
    )
    total_menus: int = Field(..., ge=0, description="Total menus with this meal")
    average_items_count: Decimal = Field(
        ...,
        ge=0,
        description="Average items per meal",
    )
    average_rating: Union[Decimal, None] = Field(None, ge=0, le=5)
    total_feedbacks: int = Field(default=0, ge=0)
    most_common_items: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Most frequently served items",
    )


class DietaryDistribution(BaseSchema):
    """
    Distribution of dietary options in menus.
    """

    vegetarian_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of vegetarian menus",
    )
    non_vegetarian_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of non-veg menus",
    )
    vegan_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
    )
    jain_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
    )


class MenuStats(BaseSchema):
    """
    Comprehensive menu statistics.
    
    Provides aggregated statistics and insights for menus.
    """

    hostel_id: UUID = Field(..., description="Hostel unique identifier")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Time period
    period_start: Date = Field(..., description="Statistics period start")
    period_end: Date = Field(..., description="Statistics period end")
    period_type: str = Field(
        ...,
        pattern=r"^(week|month|quarter|year)$",
        description="Statistics period type",
    )
    
    # Overall counts
    total_menus_created: int = Field(..., ge=0, description="Total menus created")
    total_menus_published: int = Field(..., ge=0, description="Total menus published")
    total_special_menus: int = Field(..., ge=0, description="Special occasion menus")
    
    # Ratings
    overall_average_rating: Union[Decimal, None] = Field(
        None,
        ge=0,
        le=5,
        description="Overall average rating",
    )
    total_feedbacks_received: int = Field(
        default=0,
        ge=0,
        description="Total feedback count",
    )
    
    # Item statistics
    total_unique_items: int = Field(
        ...,
        ge=0,
        description="Total unique items used",
    )
    average_items_per_menu: Decimal = Field(
        ...,
        ge=0,
        description="Average items per menu",
    )
    most_popular_items: List[ItemPopularity] = Field(
        default_factory=list,
        max_length=20,
        description="Most popular items",
    )
    least_popular_items: List[ItemPopularity] = Field(
        default_factory=list,
        max_length=10,
        description="Least popular items",
    )
    
    # Meal type breakdown
    meal_type_stats: Dict[str, MealTypeStats] = Field(
        default_factory=dict,
        description="Statistics per meal type",
    )
    
    # Dietary distribution
    dietary_distribution: DietaryDistribution = Field(
        ...,
        description="Dietary options distribution",
    )
    
    # Trends
    rating_trend: str = Field(
        ...,
        pattern=r"^(improving|declining|stable)$",
        description="Rating trend",
    )
    trend_percentage: Union[Decimal, None] = Field(
        None,
        description="Trend change percentage",
    )
    
    # Day of week analysis
    best_rated_day: Union[str, None] = Field(
        None,
        description="Day with highest ratings",
    )
    worst_rated_day: Union[str, None] = Field(
        None,
        description="Day with lowest ratings",
    )
    
    # Compliance
    approval_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of approved menus",
    )
    publication_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of published menus",
    )
    
    # Generated timestamp
    generated_at: datetime = Field(
        ...,
        description="Statistics generation timestamp",
    )

    @computed_field
    @property
    def satisfaction_rate(self) -> Decimal:
        """Calculate overall satisfaction rate."""
        if self.overall_average_rating is None:
            return Decimal("0.00")
        
        return round((self.overall_average_rating / Decimal("5")) * 100, 2)

    @computed_field
    @property
    def menu_completion_rate(self) -> Decimal:
        """Calculate menu completion rate."""
        total_days = (self.period_end - self.period_start).days + 1
        if total_days == 0:
            return Decimal("0.00")
        
        return round(
            (Decimal(self.total_menus_created) / Decimal(total_days)) * 100,
            2,
        )