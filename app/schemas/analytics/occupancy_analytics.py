# --- File: app/schemas/analytics/occupancy_analytics.py ---
"""
Occupancy analytics schemas with forecasting capabilities.

Provides detailed occupancy metrics including:
- Current and historical occupancy rates
- Room type and floor-wise breakdowns
- Occupancy trends and patterns
- Predictive forecasting
- Capacity utilization analysis
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Annotated
from enum import Enum

from pydantic import BaseModel, Field, field_validator, computed_field, model_validator, AfterValidator
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import RoomType
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "ForecastModel",
    "OccupancyKPI",
    "OccupancyTrendPoint",
    "OccupancyByRoomType",
    "OccupancyByFloor",
    "ForecastPoint",
    "ForecastData",
    "SeasonalPattern",
    "OccupancyReport",
]


# Custom validator for rounding
def round_to_2_places(v: Decimal) -> Decimal:
    """Round decimal to 2 places."""
    if isinstance(v, (int, float)):
        v = Decimal(str(v))
    return round(v, 2)


# Type aliases
DecimalPercentage = Annotated[Decimal, Field(ge=0, le=100), AfterValidator(round_to_2_places)]
DecimalNonNegative = Annotated[Decimal, Field(ge=0), AfterValidator(round_to_2_places)]


class ForecastModel(str, Enum):
    """Forecasting model types."""
    
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    ARIMA = "arima"
    LINEAR_REGRESSION = "linear_regression"
    SIMPLE_EXTRAPOLATION = "simple_extrapolation"
    ML_BASED = "ml_based"


class OccupancyKPI(BaseSchema):
    """
    Key occupancy metrics and performance indicators.
    
    Provides comprehensive occupancy statistics for capacity
    planning and performance monitoring.
    """
    
    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel identifier. None for platform-wide metrics"
    )
    hostel_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Hostel name"
    )
    
    # Current state
    current_occupancy_percentage: DecimalPercentage = Field(
        ...,
        description="Current occupancy rate"
    )
    
    # Period averages
    average_occupancy_percentage: DecimalPercentage = Field(
        ...,
        description="Average occupancy rate over the period"
    )
    peak_occupancy_percentage: DecimalPercentage = Field(
        ...,
        description="Peak occupancy rate in the period"
    )
    low_occupancy_percentage: DecimalPercentage = Field(
        ...,
        description="Lowest occupancy rate in the period"
    )
    
    # Capacity metrics
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total bed capacity"
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Currently occupied beds"
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Currently available beds"
    )
    reserved_beds: int = Field(
        0,
        ge=0,
        description="Beds reserved but not yet occupied"
    )
    maintenance_beds: int = Field(
        0,
        ge=0,
        description="Beds under maintenance"
    )
    
    # Utilization metrics
    utilization_rate: DecimalPercentage = Field(
        ...,
        description="Actual utilization rate (occupied / available)"
    )
    turnover_rate: Optional[DecimalNonNegative] = Field(
        None,
        description="Bed turnover rate (check-ins + check-outs)"
    )
    
    @field_validator("occupied_beds", "available_beds", "reserved_beds", "maintenance_beds")
    @classmethod
    def validate_bed_counts(cls, v: int, info) -> int:
        """Validate bed counts are consistent with total."""
        if "total_beds" in info.data:
            total = info.data["total_beds"]
            if v > total:
                raise ValueError(f"{info.field_name} cannot exceed total_beds")
        return v
    
    @model_validator(mode="after")
    def validate_bed_allocation(self) -> "OccupancyKPI":
        """Validate that bed allocation is consistent."""
        allocated = (
            self.occupied_beds +
            self.available_beds +
            self.maintenance_beds
        )
        
        # Allow some flexibility for concurrent updates
        if allocated > self.total_beds + 1:
            raise ValueError(
                f"Allocated beds ({allocated}) exceeds total_beds ({self.total_beds})"
            )
        
        return self
    
    @computed_field  # type: ignore[misc]
    @property
    def occupancy_status(self) -> str:
        """
        Classify occupancy status.
        
        Returns:
            'high', 'optimal', 'low', or 'critical'
        """
        rate = float(self.current_occupancy_percentage)
        
        if rate >= 90:
            return "high"
        elif rate >= 70:
            return "optimal"
        elif rate >= 50:
            return "moderate"
        elif rate >= 30:
            return "low"
        else:
            return "critical"
    
    @computed_field  # type: ignore[misc]
    @property
    def capacity_pressure(self) -> Decimal:
        """
        Calculate capacity pressure score (0-100).
        
        Higher score indicates higher pressure on capacity.
        """
        if self.total_beds == 0:
            return Decimal("0.00")
        
        # Consider both current occupancy and reserved beds
        pressure_beds = self.occupied_beds + self.reserved_beds
        pressure_rate = (Decimal(pressure_beds) / Decimal(self.total_beds)) * 100
        
        return round(min(pressure_rate, Decimal("100.00")), 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def vacancy_rate(self) -> Decimal:
        """Calculate vacancy rate."""
        return round(Decimal("100.00") - self.current_occupancy_percentage, 2)


class OccupancyTrendPoint(BaseSchema):
    """
    Single data point in occupancy trend analysis.
    
    Represents occupancy metrics for a specific date.
    """
    
    trend_date: Date = Field(
        ...,
        description="Date of the data point"
    )
    occupancy_percentage: DecimalPercentage = Field(
        ...,
        description="Occupancy rate for this date"
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Number of occupied beds"
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total beds available"
    )
    check_ins: int = Field(
        0,
        ge=0,
        description="Number of check-ins on this date"
    )
    check_outs: int = Field(
        0,
        ge=0,
        description="Number of check-outs on this date"
    )
    
    @field_validator("occupied_beds")
    @classmethod
    def validate_occupied_beds(cls, v: int, info) -> int:
        """Validate occupied beds don't exceed total."""
        if "total_beds" in info.data and v > info.data["total_beds"]:
            raise ValueError("occupied_beds cannot exceed total_beds")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def net_change(self) -> int:
        """Calculate net change in occupancy for the day."""
        return self.check_ins - self.check_outs


class OccupancyByRoomType(BaseSchema):
    """
    Occupancy breakdown by room type.
    
    Provides granular occupancy metrics for each room type
    to identify optimization opportunities.
    """
    
    room_type: RoomType = Field(
        ...,
        description="Room type category"
    )
    room_type_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Human-readable room type name"
    )
    
    total_rooms: int = Field(
        ...,
        ge=0,
        description="Total rooms of this type"
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total beds in this room type"
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Occupied beds in this room type"
    )
    occupancy_percentage: DecimalPercentage = Field(
        ...,
        description="Occupancy rate for this room type"
    )
    
    # Revenue metrics
    average_rate: Optional[DecimalNonNegative] = Field(
        None,
        description="Average rate charged for this room type"
    )
    revenue_generated: Optional[DecimalNonNegative] = Field(
        None,
        description="Total revenue from this room type"
    )
    
    @field_validator("occupied_beds")
    @classmethod
    def validate_occupied_beds(cls, v: int, info) -> int:
        """Validate occupied beds don't exceed total."""
        if "total_beds" in info.data and v > info.data["total_beds"]:
            raise ValueError("occupied_beds cannot exceed total_beds")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def available_beds(self) -> int:
        """Calculate available beds."""
        return self.total_beds - self.occupied_beds
    
    @computed_field  # type: ignore[misc]
    @property
    def revenue_per_bed(self) -> Optional[Decimal]:
        """Calculate revenue per bed."""
        if self.revenue_generated is None or self.total_beds == 0:
            return None
        return round(self.revenue_generated / Decimal(self.total_beds), 2)


class OccupancyByFloor(BaseSchema):
    """
    Occupancy breakdown by floor.
    
    Provides floor-wise occupancy metrics for facility management.
    """
    
    floor_number: int = Field(
        ...,
        description="Floor number"
    )
    floor_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Floor name/identifier"
    )
    
    total_rooms: int = Field(
        ...,
        ge=0,
        description="Total rooms on this floor"
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total beds on this floor"
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Occupied beds on this floor"
    )
    occupancy_percentage: DecimalPercentage = Field(
        ...,
        description="Occupancy rate for this floor"
    )
    
    @field_validator("occupied_beds")
    @classmethod
    def validate_occupied_beds(cls, v: int, info) -> int:
        """Validate occupied beds don't exceed total."""
        if "total_beds" in info.data and v > info.data["total_beds"]:
            raise ValueError("occupied_beds cannot exceed total_beds")
        return v


class ForecastPoint(BaseSchema):
    """
    Single forecast data point.
    
    Represents predicted occupancy for a future date.
    """
    
    forecast_date: Date = Field(
        ...,
        description="Forecast date"
    )
    forecasted_occupancy_percentage: DecimalPercentage = Field(
        ...,
        description="Predicted occupancy rate"
    )
    forecasted_occupied_beds: int = Field(
        ...,
        ge=0,
        description="Predicted number of occupied beds"
    )
    
    # Confidence intervals
    lower_bound: Optional[DecimalPercentage] = Field(
        None,
        description="Lower confidence bound"
    )
    upper_bound: Optional[DecimalPercentage] = Field(
        None,
        description="Upper confidence bound"
    )
    confidence_level: Optional[DecimalPercentage] = Field(
        None,
        description="Confidence level (e.g., 95%)"
    )
    
    @model_validator(mode="after")
    def validate_bounds(self) -> "ForecastPoint":
        """Validate confidence bounds are reasonable."""
        if self.lower_bound is not None and self.upper_bound is not None:
            if self.lower_bound > self.forecasted_occupancy_percentage:
                raise ValueError("lower_bound cannot exceed forecasted value")
            if self.upper_bound < self.forecasted_occupancy_percentage:
                raise ValueError("upper_bound cannot be less than forecasted value")
            if self.lower_bound > self.upper_bound:
                raise ValueError("lower_bound cannot exceed upper_bound")
        
        return self


class SeasonalPattern(BaseSchema):
    """
    Identified seasonal occupancy pattern.
    
    Describes recurring occupancy patterns for planning.
    """
    
    pattern_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Pattern identifier (e.g., 'Summer Peak', 'Winter Low')"
    )
    start_month: int = Field(
        ...,
        ge=1,
        le=12,
        description="Starting month of the pattern"
    )
    end_month: int = Field(
        ...,
        ge=1,
        le=12,
        description="Ending month of the pattern"
    )
    average_occupancy: DecimalPercentage = Field(
        ...,
        description="Average occupancy during this pattern"
    )
    occupancy_variance: DecimalNonNegative = Field(
        ...,
        description="Variance in occupancy during this pattern"
    )
    confidence: DecimalPercentage = Field(
        ...,
        description="Confidence in pattern identification"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def is_high_season(self) -> bool:
        """Check if this is a high-occupancy season."""
        return self.average_occupancy >= 80


class ForecastData(BaseSchema):
    """
    Occupancy forecast data with model information.
    
    Provides predicted occupancy with metadata about
    the forecasting methodology and confidence.
    """
    
    forecast_horizon_days: int = Field(
        ...,
        ge=1,
        le=365,
        description="Number of days forecasted into the future"
    )
    forecast_points: List[ForecastPoint] = Field(
        ...,
        min_length=1,
        description="Forecast data points"
    )
    
    # Model information
    model_used: ForecastModel = Field(
        ...,
        description="Forecasting model used"
    )
    model_accuracy: Optional[DecimalPercentage] = Field(
        None,
        description="Historical model accuracy percentage"
    )
    confidence_interval: Optional[DecimalPercentage] = Field(
        None,
        description="Confidence interval for forecasts (e.g., 95%)"
    )
    
    # Training data info
    training_data_start: Optional[Date] = Field(
        None,
        description="Start date of training data"
    )
    training_data_end: Optional[Date] = Field(
        None,
        description="End date of training data"
    )
    training_samples: Optional[int] = Field(
        None,
        ge=0,
        description="Number of data points used for training"
    )
    
    # Seasonality
    seasonal_patterns: List[SeasonalPattern] = Field(
        default_factory=list,
        description="Identified seasonal patterns"
    )
    
    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Forecast generation timestamp"
    )
    last_updated: Optional[datetime] = Field(
        None,
        description="Last update timestamp"
    )
    
    @field_validator("forecast_points")
    @classmethod
    def validate_forecast_chronological(
        cls,
        v: List[ForecastPoint]
    ) -> List[ForecastPoint]:
        """Ensure forecast points are in chronological order."""
        if len(v) > 1:
            dates = [point.forecast_date for point in v]
            if dates != sorted(dates):
                raise ValueError("Forecast points must be in chronological order")
        return v
    
    @model_validator(mode="after")
    def validate_horizon_matches_points(self) -> "ForecastData":
        """Validate forecast horizon matches number of points."""
        if self.forecast_points:
            # Allow some tolerance
            if abs(len(self.forecast_points) - self.forecast_horizon_days) > 1:
                raise ValueError(
                    f"Number of forecast points ({len(self.forecast_points)}) "
                    f"should match horizon ({self.forecast_horizon_days})"
                )
        return self
    
    @computed_field  # type: ignore[misc]
    @property
    def average_forecasted_occupancy(self) -> Decimal:
        """Calculate average forecasted occupancy."""
        if not self.forecast_points:
            return Decimal("0.00")
        
        total = sum(p.forecasted_occupancy_percentage for p in self.forecast_points)
        return round(total / len(self.forecast_points), 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def peak_forecasted_date(self) -> Optional[Date]:
        """Identify date with highest forecasted occupancy."""
        if not self.forecast_points:
            return None
        return max(
            self.forecast_points,
            key=lambda x: x.forecasted_occupancy_percentage
        ).forecast_date
    
    @computed_field  # type: ignore[misc]
    @property
    def low_forecasted_date(self) -> Optional[Date]:
        """Identify date with lowest forecasted occupancy."""
        if not self.forecast_points:
            return None
        return min(
            self.forecast_points,
            key=lambda x: x.forecasted_occupancy_percentage
        ).forecast_date


class OccupancyReport(BaseSchema):
    """
    Comprehensive occupancy analytics report.
    
    Consolidates current metrics, historical trends,
    breakdowns, and forecasts into a complete occupancy view.
    """
    
    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel identifier. None for platform-wide report"
    )
    hostel_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Hostel name"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Core metrics
    kpi: OccupancyKPI = Field(
        ...,
        description="Key performance indicators"
    )
    
    # Trends
    daily_trend: List[OccupancyTrendPoint] = Field(
        default_factory=list,
        description="Daily occupancy trend data"
    )
    
    # Breakdowns
    by_room_type: List[OccupancyByRoomType] = Field(
        default_factory=list,
        description="Occupancy by room type"
    )
    by_floor: List[OccupancyByFloor] = Field(
        default_factory=list,
        description="Occupancy by floor"
    )
    
    # Legacy support
    by_floor_dict: Dict[int, OccupancyKPI] = Field(
        default_factory=dict,
        description="Floor occupancy dict (deprecated: use by_floor)"
    )
    
    # Forecast
    forecast: Optional[ForecastData] = Field(
        None,
        description="Occupancy forecast"
    )
    
    # Seasonal patterns
    seasonal_patterns: List[SeasonalPattern] = Field(
        default_factory=list,
        description="Identified seasonal patterns"
    )
    
    @field_validator("daily_trend")
    @classmethod
    def validate_trend_chronological(
        cls,
        v: List[OccupancyTrendPoint]
    ) -> List[OccupancyTrendPoint]:
        """Ensure trend points are chronological."""
        if len(v) > 1:
            dates = [point.trend_date for point in v]
            if dates != sorted(dates):
                raise ValueError("Trend points must be in chronological order")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def best_performing_room_type(self) -> Optional[RoomType]:
        """Identify room type with highest occupancy."""
        if not self.by_room_type:
            return None
        return max(
            self.by_room_type,
            key=lambda x: x.occupancy_percentage
        ).room_type
    
    @computed_field  # type: ignore[misc]
    @property
    def worst_performing_room_type(self) -> Optional[RoomType]:
        """Identify room type with lowest occupancy."""
        if not self.by_room_type:
            return None
        return min(
            self.by_room_type,
            key=lambda x: x.occupancy_percentage
        ).room_type
    
    @computed_field  # type: ignore[misc]
    @property
    def occupancy_trend_direction(self) -> str:
        """
        Determine overall trend direction.
        
        Returns:
            'increasing', 'decreasing', or 'stable'
        """
        if len(self.daily_trend) < 2:
            return "stable"
        
        first_half = self.daily_trend[:len(self.daily_trend)//2]
        second_half = self.daily_trend[len(self.daily_trend)//2:]
        
        first_avg = sum(
            p.occupancy_percentage for p in first_half
        ) / len(first_half)
        second_avg = sum(
            p.occupancy_percentage for p in second_half
        ) / (len(second_half) if second_half else 1)
        
        change = float(second_avg - first_avg)
        
        if change > 5:
            return "increasing"
        elif change < -5:
            return "decreasing"
        return "stable"
    
    def get_optimization_insights(self) -> List[str]:
        """
        Generate actionable optimization insights.
        
        Returns:
            List of insight strings for improving occupancy
        """
        insights = []
        
        # Overall occupancy check
        if self.kpi.current_occupancy_percentage < 60:
            insights.append(
                f"Current occupancy at {self.kpi.current_occupancy_percentage}% - "
                "consider targeted marketing campaigns"
            )
        
        # Room type performance
        if self.worst_performing_room_type:
            worst = next(
                (rt for rt in self.by_room_type
                 if rt.room_type == self.worst_performing_room_type),
                None
            )
            if worst and worst.occupancy_percentage < 50:
                insights.append(
                    f"{worst.room_type.value} rooms at {worst.occupancy_percentage}% - "
                    "consider pricing adjustments or promotions"
                )
        
        # Capacity pressure
        if self.kpi.capacity_pressure > 85:
            insights.append(
                f"Capacity pressure at {self.kpi.capacity_pressure}% - "
                "consider expansion or waitlist management"
            )
        
        # Trend analysis
        if self.occupancy_trend_direction == "decreasing":
            insights.append(
                "Occupancy trending downward - investigate causes and take corrective action"
            )
        
        # Forecast insights
        if self.forecast and self.forecast.average_forecasted_occupancy < 60:
            insights.append(
                f"Forecasted occupancy at {self.forecast.average_forecasted_occupancy}% - "
                "plan ahead for low season"
            )
        
        return insights