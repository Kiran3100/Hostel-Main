# --- File: app/schemas/hostel/hostel_analytics.py ---
"""
Hostel analytics and reporting schemas with comprehensive metrics.
"""

from datetime import datetime
from datetime import date as Date
from decimal import Decimal
from enum import Enum
from typing import Annotated, Dict, List, Union
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import BaseSchema
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "HostelAnalytics",
    "OccupancyAnalytics",
    "OccupancyDataPoint",
    "RevenueAnalytics",
    "RevenueDataPoint",
    "BookingAnalytics",
    "BookingDataPoint",
    "ComplaintAnalytics",
    "ReviewAnalytics",
    "RatingDataPoint",
    "HostelOccupancyStats",
    "RoomTypeOccupancy",
    "HostelRevenueStats",
    "MonthlyRevenue",
    "AnalyticsRequest",
    "AnalyticsPeriod",
    "TrendData",
]


class OccupancyDataPoint(BaseSchema):
    """
    Single occupancy data point for trends.
    
    Represents occupancy at a specific point in time.
    """
    model_config = ConfigDict(from_attributes=True)

    data_date: Date = Field(..., description="Date of the data point")
    occupancy_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Occupancy rate percentage")
    ]
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Number of occupied beds",
    )
    total_beds: int = Field(
        ...,
        ge=1,
        description="Total available beds",
    )


class OccupancyAnalytics(BaseSchema):
    """
    Comprehensive occupancy analytics.
    
    Provides detailed occupancy metrics and trends.
    """
    model_config = ConfigDict(from_attributes=True)

    current_occupancy_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Current occupancy percentage")
    ]
    average_occupancy_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Average occupancy for the period")
    ]
    peak_occupancy_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Peak occupancy during period")
    ]
    lowest_occupancy_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Lowest occupancy during period")
    ]

    total_beds: int = Field(
        ...,
        ge=0,
        description="Total bed capacity",
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Currently occupied beds",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Currently available beds",
    )

    # Trends
    occupancy_trend: List[OccupancyDataPoint] = Field(
        default_factory=list,
        description="Historical occupancy trend",
    )

    # Predictions
    predicted_occupancy_next_month: Union[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Predicted occupancy for next month")
    ], None] = None
    trend_direction: str = Field(
        ...,
        pattern=r"^(increasing|decreasing|stable)$",
        description="Overall occupancy trend direction",
    )


class RevenueDataPoint(BaseSchema):
    """
    Single revenue data point.
    
    Represents revenue metrics at a specific point in time.
    """
    model_config = ConfigDict(from_attributes=True)

    data_date: Date = Field(..., description="Date of the data point")
    revenue: Annotated[Decimal, Field(ge=0, description="Total revenue")]
    collected: Annotated[Decimal, Field(ge=0, description="Amount collected")]
    pending: Annotated[Decimal, Field(ge=0, description="Amount pending")]


class RevenueAnalytics(BaseSchema):
    """
    Comprehensive revenue analytics.
    
    Provides detailed financial metrics and trends.
    """
    model_config = ConfigDict(from_attributes=True)

    total_revenue: Annotated[
        Decimal,
        Field(ge=0, description="Total revenue for period")
    ]
    rent_revenue: Annotated[
        Decimal,
        Field(ge=0, description="Revenue from rent")
    ]
    mess_revenue: Annotated[
        Decimal,
        Field(ge=0, description="Revenue from mess charges")
    ]
    other_revenue: Annotated[
        Decimal,
        Field(ge=0, description="Revenue from other sources")
    ]

    total_collected: Annotated[
        Decimal,
        Field(ge=0, description="Total amount collected")
    ]
    total_pending: Annotated[
        Decimal,
        Field(ge=0, description="Total amount pending")
    ]
    total_overdue: Annotated[
        Decimal,
        Field(ge=0, description="Total overdue amount")
    ]

    collection_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Payment collection rate percentage")
    ]

    # Trends
    revenue_trend: List[RevenueDataPoint] = Field(
        default_factory=list,
        description="Historical revenue trend",
    )

    # Comparisons
    revenue_vs_last_period: Decimal = Field(
        ...,
        description="Percentage change from last period",
    )
    revenue_vs_last_year: Union[Decimal, None] = Field(
        default=None,
        description="Year-over-year percentage change",
    )

    # Additional metrics
    average_revenue_per_bed: Annotated[
        Decimal,
        Field(ge=0, description="Average revenue per occupied bed")
    ]


class BookingDataPoint(BaseSchema):
    """
    Single booking data point.
    
    Represents booking metrics at a specific point in time.
    """
    model_config = ConfigDict(from_attributes=True)

    data_date: Date = Field(..., description="Date of the data point")
    total_bookings: int = Field(
        ...,
        ge=0,
        description="Total bookings",
    )
    approved: int = Field(
        ...,
        ge=0,
        description="Approved bookings",
    )
    rejected: int = Field(
        ...,
        ge=0,
        description="Rejected bookings",
    )


class BookingAnalytics(BaseSchema):
    """
    Comprehensive booking analytics.
    
    Provides detailed booking metrics and conversion rates.
    """
    model_config = ConfigDict(from_attributes=True)

    total_bookings: int = Field(
        ...,
        ge=0,
        description="Total booking requests",
    )
    approved_bookings: int = Field(
        ...,
        ge=0,
        description="Approved bookings",
    )
    pending_bookings: int = Field(
        ...,
        ge=0,
        description="Pending bookings",
    )
    rejected_bookings: int = Field(
        ...,
        ge=0,
        description="Rejected bookings",
    )
    cancelled_bookings: int = Field(
        ...,
        ge=0,
        description="Cancelled bookings",
    )

    conversion_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Booking approval rate percentage")
    ]
    cancellation_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Cancellation rate percentage")
    ]

    # Sources
    booking_sources: Dict[str, int] = Field(
        default_factory=dict,
        description="Bookings by source (website, app, etc.)",
    )

    # Trends
    booking_trend: List[BookingDataPoint] = Field(
        default_factory=list,
        description="Historical booking trend",
    )

    # Average metrics
    average_booking_value: Annotated[
        Decimal,
        Field(ge=0, description="Average booking value")
    ]


class ComplaintAnalytics(BaseSchema):
    """
    Comprehensive complaint analytics.
    
    Provides detailed complaint metrics and resolution statistics.
    """
    model_config = ConfigDict(from_attributes=True)

    total_complaints: int = Field(
        ...,
        ge=0,
        description="Total complaints",
    )
    open_complaints: int = Field(
        ...,
        ge=0,
        description="Currently open complaints",
    )
    resolved_complaints: int = Field(
        ...,
        ge=0,
        description="Resolved complaints",
    )
    closed_complaints: int = Field(
        ...,
        ge=0,
        description="Closed complaints",
    )

    average_resolution_time_hours: Annotated[
        Decimal,
        Field(ge=0, description="Average time to resolve (hours)")
    ]
    resolution_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Percentage of resolved complaints")
    ]

    # By category
    complaints_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Complaints grouped by category",
    )

    # By priority
    complaints_by_priority: Dict[str, int] = Field(
        default_factory=dict,
        description="Complaints grouped by priority",
    )

    # SLA compliance
    sla_compliance_rate: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Percentage meeting SLA")
    ]
    sla_breaches: int = Field(
        ...,
        ge=0,
        description="Number of SLA breaches",
    )


class RatingDataPoint(BaseSchema):
    """
    Single rating data point.
    
    Represents rating metrics for a period.
    """
    model_config = ConfigDict(from_attributes=True)

    month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
    )
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating")
    ]
    review_count: int = Field(
        ...,
        ge=0,
        description="Number of reviews",
    )


class ReviewAnalytics(BaseSchema):
    """
    Comprehensive review analytics.
    
    Provides detailed review and rating statistics.
    """
    model_config = ConfigDict(from_attributes=True)

    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total number of reviews",
    )
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Overall average rating")
    ]

    # Rating distribution
    rating_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of ratings by star (1-5)",
    )

    # Detailed aspect ratings
    average_cleanliness_rating: Union[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average cleanliness rating")
    ], None] = None
    average_food_quality_rating: Union[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average food quality rating")
    ], None] = None
    average_staff_behavior_rating: Union[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average staff behavior rating")
    ], None] = None
    average_security_rating: Union[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average security rating")
    ], None] = None
    average_value_rating: Union[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average value for money rating")
    ], None] = None

    # Trends
    rating_trend: List[RatingDataPoint] = Field(
        default_factory=list,
        description="Historical rating trend",
    )

    # Sentiment
    positive_reviews: int = Field(
        ...,
        ge=0,
        description="Number of positive reviews (4-5 stars)",
    )
    negative_reviews: int = Field(
        ...,
        ge=0,
        description="Number of negative reviews (1-2 stars)",
    )
    sentiment_score: Annotated[
        Decimal,
        Field(ge=-1, le=1, description="Overall sentiment score (-1 to 1)")
    ]


class HostelAnalytics(BaseSchema):
    """
    Comprehensive hostel analytics dashboard.
    
    Aggregates all analytics for a hostel over a period.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    period_start: Date = Field(..., description="Analytics period start")
    period_end: Date = Field(..., description="Analytics period end")

    occupancy: OccupancyAnalytics = Field(
        ...,
        description="Occupancy analytics",
    )
    revenue: RevenueAnalytics = Field(
        ...,
        description="Revenue analytics",
    )
    bookings: BookingAnalytics = Field(
        ...,
        description="Booking analytics",
    )
    complaints: ComplaintAnalytics = Field(
        ...,
        description="Complaint analytics",
    )
    reviews: ReviewAnalytics = Field(
        ...,
        description="Review analytics",
    )

    generated_at: datetime = Field(
        ...,
        description="Analytics generation timestamp",
    )


class RoomTypeOccupancy(BaseSchema):
    """
    Occupancy statistics by room type.
    
    Provides occupancy breakdown for different room types.
    """
    model_config = ConfigDict(from_attributes=True)

    room_type: str = Field(
        ...,
        description="Room type (single, double, etc.)",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total beds of this type",
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Occupied beds of this type",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds of this type",
    )
    occupancy_percentage: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Occupancy percentage for this type")
    ]


class HostelOccupancyStats(BaseSchema):
    """
    Detailed occupancy statistics with breakdowns and projections.
    
    Provides comprehensive occupancy analysis.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: UUID = Field(..., description="Hostel ID")

    # Current status
    total_rooms: int = Field(
        ...,
        ge=0,
        description="Total number of rooms",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total number of beds",
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Currently occupied beds",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Currently available beds",
    )
    occupancy_percentage: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Current occupancy percentage")
    ]

    # By room type
    occupancy_by_room_type: List[RoomTypeOccupancy] = Field(
        default_factory=list,
        description="Occupancy breakdown by room type",
    )

    # Historical
    occupancy_history: List[OccupancyDataPoint] = Field(
        default_factory=list,
        description="Historical occupancy data",
    )

    # Projections
    projected_occupancy_30_days: Union[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Projected occupancy in 30 days")
    ], None] = None
    projected_occupancy_90_days: Union[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Projected occupancy in 90 days")
    ], None] = None


class MonthlyRevenue(BaseSchema):
    """
    Monthly revenue breakdown with detailed metrics.
    
    Represents revenue for a single month.
    """
    model_config = ConfigDict(from_attributes=True)

    month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
    )
    revenue: Annotated[Decimal, Field(ge=0, description="Total revenue")]
    collected: Annotated[Decimal, Field(ge=0, description="Amount collected")]
    pending: Annotated[Decimal, Field(ge=0, description="Amount pending")]
    student_count: int = Field(
        ...,
        ge=0,
        description="Number of students",
    )
    average_revenue_per_student: Annotated[
        Decimal,
        Field(ge=0, description="Average revenue per student")
    ]


class HostelRevenueStats(BaseSchema):
    """
    Detailed revenue statistics with breakdowns and growth metrics.
    
    Provides comprehensive financial analysis.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: UUID = Field(..., description="Hostel ID")
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period",
    )

    # Totals
    total_revenue: Annotated[
        Decimal,
        Field(ge=0, description="Total revenue for period")
    ]
    total_expenses: Annotated[
        Decimal,
        Field(ge=0, description="Total expenses for period")
    ]
    net_profit: Decimal = Field(
        ...,
        description="Net profit (can be negative)",
    )
    profit_margin: Annotated[
        Decimal,
        Field(ge=-100, le=100, description="Profit margin percentage")
    ]

    # Revenue breakdown
    revenue_by_type: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Revenue breakdown by type (rent, mess, etc.)",
    )

    # Collection
    total_collected: Annotated[
        Decimal,
        Field(ge=0, description="Total amount collected")
    ]
    total_pending: Annotated[
        Decimal,
        Field(ge=0, description="Total amount pending")
    ]
    total_overdue: Annotated[
        Decimal,
        Field(ge=0, description="Total overdue amount")
    ]
    collection_efficiency: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Collection efficiency percentage")
    ]

    # Monthly breakdown
    monthly_revenue: List[MonthlyRevenue] = Field(
        default_factory=list,
        description="Month-by-month revenue breakdown",
    )

    # Comparison
    revenue_growth_mom: Decimal = Field(
        ...,
        description="Month-over-month growth percentage",
    )
    revenue_growth_yoy: Union[Decimal, None] = Field(
        default=None,
        description="Year-over-year growth percentage",
    )


class AnalyticsRequest(BaseSchema):
    """
    Request schema for generating analytics.
    
    Specifies parameters for analytics generation.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: UUID = Field(..., description="Hostel ID")
    start_date: Date = Field(..., description="Analytics start Date")
    end_date: Date = Field(..., description="Analytics end Date")
    include_predictions: bool = Field(
        default=False,
        description="Include predictive analytics",
    )
    granularity: str = Field(
        default="daily",
        pattern=r"^(daily|weekly|monthly)$",
        description="Data granularity",
    )

    @model_validator(mode="after")
    def validate_date_range(self):
        """Validate Date range is reasonable."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after or equal to start_date")
        
        # Check if Date range is not too large (max 2 years)
        days_diff = (self.end_date - self.start_date).days
        if days_diff > 730:  # 2 years
            raise ValueError("Date range cannot exceed 2 years")
        
        return self
    
class AnalyticsPeriod(str, Enum):
    """Analytics aggregation periods."""
    DAILY = "daily"
    WEEKLY = "weekly" 
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class TrendData(BaseSchema):
    """Trend data point for time series analysis."""
    model_config = ConfigDict(from_attributes=True)
    
    timestamp: Date = Field(..., description="Data point timestamp")
    value: Decimal = Field(..., description="Metric value")
    metric_type: str = Field(..., description="Type of metric")
    change_percentage: Union[Decimal, None] = Field(
        default=None, 
        description="Percentage change from previous period"
    )