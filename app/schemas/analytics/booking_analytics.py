# --- File: app/schemas/analytics/booking_analytics.py ---
"""
Booking analytics schemas with enhanced validation and type safety.

This module provides comprehensive analytics for booking operations including:
- Key Performance Indicators (KPIs)
- Trend analysis
- Conversion funnels
- Cancellation analytics
- Source-based metrics
"""

from datetime import datetime
from datetime import date as Date
from decimal import Decimal
from typing import Dict, List, Optional, Any, Annotated

from pydantic import BaseModel, Field, field_validator, computed_field, model_validator
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import BookingStatus, BookingSource
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "BookingKPI",
    "BookingTrendPoint",
    "BookingFunnel",
    "CancellationAnalytics",
    "BookingAnalyticsSummary",
    "BookingSourceMetrics",
]


# Type aliases for Decimal fields with constraints
DecimalPercentage = Annotated[Decimal, Field(ge=0, le=100)]
DecimalCurrency = Annotated[Decimal, Field(ge=0)]


class BookingKPI(BaseSchema):
    """
    Key Performance Indicators for booking operations.
    
    Provides essential metrics including total bookings, conversion rates,
    and cancellation statistics for a specific hostel or platform-wide.
    """
    
    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel identifier. None indicates platform-wide metrics"
    )
    hostel_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Hostel name for display purposes"
    )
    
    # Booking counts
    total_bookings: int = Field(
        ...,
        ge=0,
        description="Total number of bookings in the period"
    )
    confirmed_bookings: int = Field(
        ...,
        ge=0,
        description="Number of confirmed bookings"
    )
    cancelled_bookings: int = Field(
        ...,
        ge=0,
        description="Number of cancelled bookings"
    )
    rejected_bookings: int = Field(
        ...,
        ge=0,
        description="Number of rejected bookings"
    )
    pending_bookings: int = Field(
        0,
        ge=0,
        description="Number of pending bookings awaiting approval"
    )
    
    # Performance metrics
    # Note: In Pydantic v2, decimal_places is handled via post-validation rounding
    booking_conversion_rate: DecimalPercentage = Field(
        ...,
        description="Percentage of bookings that were confirmed"
    )
    cancellation_rate: DecimalPercentage = Field(
        ...,
        description="Percentage of bookings that were cancelled"
    )
    average_lead_time_days: DecimalCurrency = Field(
        ...,
        description="Average days between booking creation and check-in date"
    )
    
    @field_validator("confirmed_bookings", "cancelled_bookings", "rejected_bookings", "pending_bookings")
    @classmethod
    def validate_booking_counts(cls, v: int, info) -> int:
        """Validate that individual booking counts don't exceed total."""
        # In Pydantic v2, info.data contains already-validated fields
        if "total_bookings" in info.data:
            total = info.data["total_bookings"]
            if v > total:
                raise ValueError(
                    f"{info.field_name} ({v}) cannot exceed total_bookings ({total})"
                )
        return v
    
    @field_validator("booking_conversion_rate", "cancellation_rate")
    @classmethod
    def validate_percentage(cls, v: Decimal) -> Decimal:
        """Ensure percentages are within valid range and rounded to 2 decimal places."""
        if not (0 <= v <= 100):
            raise ValueError("Percentage must be between 0 and 100")
        return round(v, 2)
    
    @field_validator("average_lead_time_days")
    @classmethod
    def round_lead_time(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def approval_rate(self) -> Decimal:
        """Calculate approval rate (confirmed / (confirmed + rejected))."""
        denominator = self.confirmed_bookings + self.rejected_bookings
        if denominator == 0:
            return Decimal("0.00")
        return round(
            (Decimal(self.confirmed_bookings) / Decimal(denominator)) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def completion_rate(self) -> Decimal:
        """Calculate completion rate (non-pending / total)."""
        if self.total_bookings == 0:
            return Decimal("0.00")
        completed = self.total_bookings - self.pending_bookings
        return round(
            (Decimal(completed) / Decimal(self.total_bookings)) * 100,
            2
        )


class BookingTrendPoint(BaseSchema):
    """
    Single data point in booking trend analysis.
    
    Represents booking metrics for a specific date, enabling
    time-series visualization and trend analysis.
    """
    
    trend_date: Date = Field(
        ...,
        description="Date of the data point"
    )
    total_bookings: int = Field(
        ...,
        ge=0,
        description="Total bookings on this date"
    )
    confirmed: int = Field(
        ...,
        ge=0,
        description="Confirmed bookings on this date"
    )
    cancelled: int = Field(
        ...,
        ge=0,
        description="Cancelled bookings on this date"
    )
    rejected: int = Field(
        ...,
        ge=0,
        description="Rejected bookings on this date"
    )
    pending: int = Field(
        0,
        ge=0,
        description="Pending bookings on this date"
    )
    revenue_for_day: DecimalCurrency = Field(
        ...,
        description="Total revenue generated on this date"
    )
    
    @field_validator("confirmed", "cancelled", "rejected", "pending")
    @classmethod
    def validate_counts(cls, v: int, info) -> int:
        """Validate that status counts don't exceed total."""
        if "total_bookings" in info.data:
            total = info.data["total_bookings"]
            if v > total:
                raise ValueError(
                    f"{info.field_name} ({v}) cannot exceed total_bookings ({total})"
                )
        return v
    
    @field_validator("revenue_for_day")
    @classmethod
    def round_revenue(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def conversion_rate(self) -> Decimal:
        """Calculate conversion rate for this date."""
        if self.total_bookings == 0:
            return Decimal("0.00")
        return round(
            (Decimal(self.confirmed) / Decimal(self.total_bookings)) * 100,
            2
        )


class BookingFunnel(BaseSchema):
    """
    Booking conversion funnel analytics.
    
    Tracks user journey from hostel page views through to confirmed bookings,
    providing insights into conversion bottlenecks.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Time period for funnel analysis"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when this report was generated"
    )
    
    # Funnel stages
    hostel_page_views: int = Field(
        ...,
        ge=0,
        description="Total hostel detail page views"
    )
    booking_form_starts: int = Field(
        ...,
        ge=0,
        description="Users who started the booking form"
    )
    booking_submissions: int = Field(
        ...,
        ge=0,
        description="Completed booking form submissions"
    )
    bookings_confirmed: int = Field(
        ...,
        ge=0,
        description="Final confirmed bookings"
    )
    
    # Conversion rates
    view_to_start_rate: DecimalPercentage = Field(
        ...,
        description="Conversion rate from page view to form start (%)"
    )
    start_to_submit_rate: DecimalPercentage = Field(
        ...,
        description="Conversion rate from form start to submission (%)"
    )
    submit_to_confirm_rate: DecimalPercentage = Field(
        ...,
        description="Conversion rate from submission to confirmation (%)"
    )
    view_to_confirm_rate: DecimalPercentage = Field(
        ...,
        description="Overall conversion rate from view to confirmation (%)"
    )
    
    @field_validator(
        "booking_form_starts",
        "booking_submissions",
        "bookings_confirmed"
    )
    @classmethod
    def validate_funnel_progression(cls, v: int, info) -> int:
        """Validate that funnel stages progress logically."""
        field_name = info.field_name
        data = info.data
        
        if field_name == "booking_form_starts" and "hostel_page_views" in data:
            if v > data["hostel_page_views"]:
                raise ValueError(
                    "booking_form_starts cannot exceed hostel_page_views"
                )
        elif field_name == "booking_submissions" and "booking_form_starts" in data:
            if v > data["booking_form_starts"]:
                raise ValueError(
                    "booking_submissions cannot exceed booking_form_starts"
                )
        elif field_name == "bookings_confirmed" and "booking_submissions" in data:
            if v > data["booking_submissions"]:
                raise ValueError(
                    "bookings_confirmed cannot exceed booking_submissions"
                )
        
        return v
    
    @field_validator(
        "view_to_start_rate",
        "start_to_submit_rate",
        "submit_to_confirm_rate",
        "view_to_confirm_rate"
    )
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def total_drop_offs(self) -> int:
        """Calculate total number of users who dropped off."""
        return self.hostel_page_views - self.bookings_confirmed
    
    @computed_field  # type: ignore[misc]
    @property
    def largest_drop_off_stage(self) -> str:
        """Identify the stage with largest drop-off."""
        drop_offs = {
            "view_to_start": self.hostel_page_views - self.booking_form_starts,
            "start_to_submit": self.booking_form_starts - self.booking_submissions,
            "submit_to_confirm": self.booking_submissions - self.bookings_confirmed,
        }
        return max(drop_offs, key=drop_offs.get)  # type: ignore[arg-type]


class CancellationAnalytics(BaseSchema):
    """
    Detailed analytics for booking cancellations.
    
    Provides insights into cancellation patterns, reasons,
    and timing to help reduce cancellation rates.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    total_cancellations: int = Field(
        ...,
        ge=0,
        description="Total number of cancellations in period"
    )
    cancellation_rate: DecimalPercentage = Field(
        ...,
        description="Cancellation rate as percentage of total bookings"
    )
    
    # Breakdown by reason
    cancellations_by_reason: Dict[str, int] = Field(
        default_factory=dict,
        description="Cancellation count grouped by reason"
    )
    cancellations_by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Cancellation count grouped by original booking status"
    )
    
    # Timing analysis
    average_time_before_check_in_cancelled_days: DecimalCurrency = Field(
        ...,
        description="Average days before check-in when cancellations occur"
    )
    cancellations_within_24h: int = Field(
        0,
        ge=0,
        description="Cancellations made within 24 hours of check-in"
    )
    cancellations_within_week: int = Field(
        0,
        ge=0,
        description="Cancellations made within 1 week of check-in"
    )
    
    @field_validator("cancellation_rate")
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @field_validator("average_time_before_check_in_cancelled_days")
    @classmethod
    def round_days(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @field_validator("cancellations_by_reason", "cancellations_by_status")
    @classmethod
    def validate_breakdown_totals(cls, v: Dict[str, int], info) -> Dict[str, int]:
        """Ensure breakdown totals match overall total."""
        if v and "total_cancellations" in info.data:
            breakdown_total = sum(v.values())
            total_cancellations = info.data["total_cancellations"]
            # Allow some tolerance for rounding or filtering
            if breakdown_total > total_cancellations:
                raise ValueError(
                    f"Breakdown total ({breakdown_total}) exceeds "
                    f"total_cancellations ({total_cancellations})"
                )
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def top_cancellation_reason(self) -> Optional[str]:
        """Identify the most common cancellation reason."""
        if not self.cancellations_by_reason:
            return None
        return max(
            self.cancellations_by_reason,
            key=self.cancellations_by_reason.get  # type: ignore[arg-type]
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def early_cancellation_rate(self) -> Decimal:
        """Calculate percentage of cancellations made >7 days before check-in."""
        if self.total_cancellations == 0:
            return Decimal("0.00")
        early = self.total_cancellations - self.cancellations_within_week
        return round(
            (Decimal(early) / Decimal(self.total_cancellations)) * 100,
            2
        )


class BookingSourceMetrics(BaseSchema):
    """
    Metrics for a specific booking source.
    
    Tracks performance of individual booking channels
    to optimize marketing and acquisition strategies.
    """
    
    source: BookingSource = Field(
        ...,
        description="Booking source"
    )
    total_bookings: int = Field(
        ...,
        ge=0,
        description="Total bookings from this source"
    )
    confirmed_bookings: int = Field(
        ...,
        ge=0,
        description="Confirmed bookings from this source"
    )
    conversion_rate: DecimalPercentage = Field(
        ...,
        description="Conversion rate for this source (%)"
    )
    total_revenue: DecimalCurrency = Field(
        ...,
        description="Total revenue generated from this source"
    )
    average_booking_value: DecimalCurrency = Field(
        ...,
        description="Average revenue per booking from this source"
    )
    
    @field_validator("conversion_rate")
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @field_validator("total_revenue", "average_booking_value")
    @classmethod
    def round_currency(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def revenue_per_confirmed_booking(self) -> Decimal:
        """Calculate average revenue per confirmed booking."""
        if self.confirmed_bookings == 0:
            return Decimal("0.00")
        return round(
            self.total_revenue / Decimal(self.confirmed_bookings),
            2
        )


class BookingAnalyticsSummary(BaseSchema):
    """
    Comprehensive booking analytics summary.
    
    Consolidates all booking metrics, trends, and analytics
    into a single comprehensive report.
    """
    
    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel identifier. None for platform-wide analytics"
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
    kpi: BookingKPI = Field(
        ...,
        description="Key performance indicators"
    )
    trend: List[BookingTrendPoint] = Field(
        default_factory=list,
        description="Daily trend data points"
    )
    
    # Funnel and cancellations
    funnel: BookingFunnel = Field(
        ...,
        description="Booking conversion funnel analysis"
    )
    cancellations: CancellationAnalytics = Field(
        ...,
        description="Cancellation analytics"
    )
    
    # Source analysis
    bookings_by_source: Dict[str, int] = Field(
        default_factory=dict,
        description="Booking count by source"
    )
    source_metrics: List[BookingSourceMetrics] = Field(
        default_factory=list,
        description="Detailed metrics for each booking source"
    )
    
    # Legacy field for backward compatibility
    conversion_rate_by_source: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Conversion rate by source (deprecated: use source_metrics)"
    )
    
    @field_validator("trend")
    @classmethod
    def validate_trend_chronological(
        cls,
        v: List[BookingTrendPoint]
    ) -> List[BookingTrendPoint]:
        """Ensure trend points are in chronological order."""
        if len(v) > 1:
            dates = [point.trend_date for point in v]
            if dates != sorted(dates):
                raise ValueError("Trend points must be in chronological order")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def best_performing_source(self) -> Optional[BookingSource]:
        """Identify the booking source with highest conversion rate."""
        if not self.source_metrics:
            return None
        best = max(
            self.source_metrics,
            key=lambda x: x.conversion_rate
        )
        return best.source
    
    @computed_field  # type: ignore[misc]
    @property
    def highest_revenue_source(self) -> Optional[BookingSource]:
        """Identify the booking source with highest total revenue."""
        if not self.source_metrics:
            return None
        best = max(
            self.source_metrics,
            key=lambda x: x.total_revenue
        )
        return best.source
    
    def get_trend_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of booking trends.
        
        Returns:
            Dictionary containing trend insights like growth rate,
            peak booking date, etc.
        """
        if not self.trend:
            return {}
        
        total_bookings = [point.total_bookings for point in self.trend]
        revenues = [float(point.revenue_for_day) for point in self.trend]
        
        peak_date = max(self.trend, key=lambda x: x.total_bookings).trend_date
        best_revenue_date = max(self.trend, key=lambda x: x.revenue_for_day).trend_date
        
        return {
            "peak_booking_date": peak_date,
            "peak_bookings": max(total_bookings),
            "best_revenue_date": best_revenue_date,
            "best_revenue": max(revenues),
            "average_daily_bookings": round(
                sum(total_bookings) / len(total_bookings), 2
            ),
            "average_daily_revenue": round(
                sum(revenues) / len(revenues), 2
            ),
        }