# --- File: app/schemas/analytics/visitor_analytics.py ---
"""
Visitor and funnel analytics schemas for marketing optimization.

Provides comprehensive visitor behavior analysis including:
- Acquisition funnel tracking
- Traffic source analysis
- Visitor behavior patterns
- Conversion optimization insights
- Search and engagement metrics
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Annotated
from enum import Enum

from pydantic import BaseModel, Field, field_validator, computed_field, model_validator, AfterValidator
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import SearchSource
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "FunnelStage",
    "VisitorFunnel",
    "TrafficSourceMetrics",
    "TrafficSourceAnalytics",
    "SearchBehavior",
    "EngagementMetrics",
    "VisitorBehaviorAnalytics",
    "ConversionPathAnalysis",
]


# Custom validator
def round_to_2_places(v: Decimal) -> Decimal:
    """Round decimal to 2 places."""
    if isinstance(v, (int, float)):
        v = Decimal(str(v))
    return round(v, 2)


# Type aliases
DecimalPercentage = Annotated[Decimal, Field(ge=0, le=100), AfterValidator(round_to_2_places)]
DecimalNonNegative = Annotated[Decimal, Field(ge=0), AfterValidator(round_to_2_places)]


class FunnelStage(str, Enum):
    """Visitor journey funnel stages."""
    
    VISIT = "visit"
    SEARCH = "search"
    VIEW_HOSTEL = "view_hostel"
    COMPARE = "compare"
    REGISTER = "register"
    BOOK = "book"
    CONFIRM = "confirm"


class TrafficSourceMetrics(BaseSchema):
    """
    Metrics for a specific traffic source.
    
    Provides detailed performance data for individual
    acquisition channels to optimize marketing spend.
    """
    
    source: SearchSource = Field(
        ...,
        description="Traffic source"
    )
    source_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Human-readable source name"
    )
    
    # Volume metrics
    visits: int = Field(
        ...,
        ge=0,
        description="Total visits from this source"
    )
    unique_visitors: int = Field(
        ...,
        ge=0,
        description="Unique visitors from this source"
    )
    page_views: int = Field(
        ...,
        ge=0,
        description="Total page views from this source"
    )
    
    # Engagement metrics
    avg_session_duration_seconds: DecimalNonNegative = Field(
        ...,
        description="Average session duration"
    )
    avg_pages_per_session: DecimalNonNegative = Field(
        ...,
        description="Average pages viewed per session"
    )
    bounce_rate: DecimalPercentage = Field(
        ...,
        description="Bounce rate percentage"
    )
    
    # Conversion metrics
    registrations: int = Field(
        ...,
        ge=0,
        description="User registrations from this source"
    )
    bookings: int = Field(
        ...,
        ge=0,
        description="Bookings from this source"
    )
    confirmed_bookings: int = Field(
        ...,
        ge=0,
        description="Confirmed bookings from this source"
    )
    
    # Conversion rates
    visit_to_registration_rate: DecimalPercentage = Field(
        ...,
        description="Visit to registration conversion rate"
    )
    visit_to_booking_rate: DecimalPercentage = Field(
        ...,
        description="Visit to booking conversion rate"
    )
    registration_to_booking_rate: DecimalPercentage = Field(
        ...,
        description="Registration to booking conversion rate"
    )
    
    # Revenue metrics
    total_revenue: DecimalNonNegative = Field(
        0,
        description="Total revenue from this source"
    )
    revenue_per_visit: DecimalNonNegative = Field(
        0,
        description="Average revenue per visit"
    )
    
    # Cost metrics (if available)
    marketing_cost: Optional[DecimalNonNegative] = Field(
        None,
        description="Marketing cost for this source"
    )
    cost_per_acquisition: Optional[DecimalNonNegative] = Field(
        None,
        description="Cost per booking acquisition"
    )
    roi: Optional[Annotated[Decimal, AfterValidator(round_to_2_places)]] = Field(
        None,
        description="Return on investment percentage"
    )
    
    @field_validator("unique_visitors")
    @classmethod
    def validate_unique_visitors(cls, v: int, info) -> int:
        """Validate unique visitors don't exceed total visits."""
        if "visits" in info.data and v > info.data["visits"]:
            raise ValueError("unique_visitors cannot exceed visits")
        return v
    
    @field_validator("registrations", "bookings", "confirmed_bookings")
    @classmethod
    def validate_conversion_counts(cls, v: int, info) -> int:
        """Validate conversion counts are reasonable."""
        if "visits" in info.data and v > info.data["visits"]:
            # Allow slight excess for cross-session conversions
            if v > info.data["visits"] * 1.1:
                raise ValueError(f"{info.field_name} significantly exceeds visits")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def engagement_score(self) -> Decimal:
        """
        Calculate engagement score (0-100).
        
        Based on session duration, pages per session, and bounce rate.
        """
        # Normalize metrics to 0-100 scale
        duration_score = min(float(self.avg_session_duration_seconds) / 300 * 100, 100)
        pages_score = min(float(self.avg_pages_per_session) / 10 * 100, 100)
        bounce_score = 100 - float(self.bounce_rate)
        
        # Weighted average
        score = (duration_score * 0.4 + pages_score * 0.3 + bounce_score * 0.3)
        return round(Decimal(str(score)), 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def quality_score(self) -> Decimal:
        """
        Calculate source quality score (0-100).
        
        Combines engagement and conversion metrics.
        """
        engagement = float(self.engagement_score)
        conversion = float(self.visit_to_booking_rate) * 10  # Scale to 0-100
        
        score = (engagement * 0.4 + conversion * 0.6)
        return round(Decimal(str(min(score, 100))), 2)


class VisitorFunnel(BaseSchema):
    """
    Visitor acquisition and conversion funnel.
    
    Tracks visitor journey from initial visit through
    to confirmed booking with drop-off analysis.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Funnel analysis period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Funnel stages
    total_visits: int = Field(
        ...,
        ge=0,
        description="Total website visits"
    )
    unique_visitors: int = Field(
        ...,
        ge=0,
        description="Unique visitors"
    )
    searches_performed: int = Field(
        ...,
        ge=0,
        description="Number of searches performed"
    )
    hostel_views: int = Field(
        ...,
        ge=0,
        description="Hostel detail page views"
    )
    comparisons_made: int = Field(
        0,
        ge=0,
        description="Comparison tool uses"
    )
    registrations: int = Field(
        ...,
        ge=0,
        description="User registrations"
    )
    booking_starts: int = Field(
        ...,
        ge=0,
        description="Booking form starts"
    )
    bookings: int = Field(
        ...,
        ge=0,
        description="Booking submissions"
    )
    confirmed_bookings: int = Field(
        0,
        ge=0,
        description="Confirmed bookings"
    )
    
    # Conversion rates
    visit_to_search_rate: DecimalPercentage = Field(
        ...,
        description="Visit to search conversion rate"
    )
    search_to_view_rate: DecimalPercentage = Field(
        ...,
        description="Search to hostel view conversion rate"
    )
    view_to_registration_rate: DecimalPercentage = Field(
        ...,
        description="Hostel view to registration rate"
    )
    registration_to_booking_rate: DecimalPercentage = Field(
        ...,
        description="Registration to booking rate"
    )
    booking_to_confirm_rate: DecimalPercentage = Field(
        ...,
        description="Booking to confirmation rate"
    )
    visit_to_booking_rate: DecimalPercentage = Field(
        ...,
        description="Overall visit to booking conversion rate"
    )
    
    # Drop-off analysis
    dropped_after_search: int = Field(
        ...,
        ge=0,
        description="Visitors who left after searching"
    )
    dropped_after_hostel_view: int = Field(
        ...,
        ge=0,
        description="Visitors who left after viewing hostel"
    )
    dropped_after_booking_start: int = Field(
        ...,
        ge=0,
        description="Visitors who abandoned booking form"
    )
    
    @field_validator(
        "unique_visitors",
        "searches_performed",
        "hostel_views",
        "registrations",
        "bookings"
    )
    @classmethod
    def validate_funnel_progression(cls, v: int, info) -> int:
        """Validate funnel stages progress logically."""
        # Note: We allow some flexibility as users may skip stages
        # or stages may be tracked across multiple sessions
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def total_drop_offs(self) -> int:
        """Calculate total visitors who dropped off."""
        return self.total_visits - self.confirmed_bookings
    
    @computed_field  # type: ignore[misc]
    @property
    def largest_drop_off_stage(self) -> str:
        """Identify stage with largest drop-off."""
        drop_offs = {
            "after_search": self.dropped_after_search,
            "after_view": self.dropped_after_hostel_view,
            "after_booking_start": self.dropped_after_booking_start,
        }
        
        if not any(drop_offs.values()):
            return "none"
        
        return max(drop_offs, key=drop_offs.get)  # type: ignore[arg-type]
    
    @computed_field  # type: ignore[misc]
    @property
    def funnel_efficiency_score(self) -> Decimal:
        """
        Calculate overall funnel efficiency (0-100).
        
        Based on conversion rates at each stage.
        """
        rates = [
            float(self.visit_to_search_rate),
            float(self.search_to_view_rate),
            float(self.view_to_registration_rate),
            float(self.registration_to_booking_rate),
            float(self.booking_to_confirm_rate),
        ]
        
        # Geometric mean for compound conversion
        if any(r == 0 for r in rates):
            return Decimal("0.00")
        
        product = 1
        for rate in rates:
            product *= (rate / 100)
        
        efficiency = (product ** (1/len(rates))) * 100
        return round(Decimal(str(efficiency)), 2)


class TrafficSourceAnalytics(BaseSchema):
    """
    Comprehensive traffic source analysis.
    
    Aggregates and compares performance across all
    traffic acquisition channels.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    total_visits: int = Field(
        ...,
        ge=0,
        description="Total visits across all sources"
    )
    
    # Source breakdowns
    visits_by_source: Dict[str, int] = Field(
        default_factory=dict,
        description="Visit count by source"
    )
    registrations_by_source: Dict[str, int] = Field(
        default_factory=dict,
        description="Registration count by source"
    )
    bookings_by_source: Dict[str, int] = Field(
        default_factory=dict,
        description="Booking count by source"
    )
    
    # Conversion rates
    visit_to_booking_rate_by_source: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Visit to booking conversion rate by source"
    )
    
    # Detailed metrics per source
    source_metrics: List[TrafficSourceMetrics] = Field(
        default_factory=list,
        description="Detailed metrics for each source"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def best_converting_source(self) -> Optional[SearchSource]:
        """Identify source with highest conversion rate."""
        if not self.source_metrics:
            return None
        return max(
            self.source_metrics,
            key=lambda x: x.visit_to_booking_rate
        ).source
    
    @computed_field  # type: ignore[misc]
    @property
    def highest_volume_source(self) -> Optional[SearchSource]:
        """Identify source with highest visit volume."""
        if not self.source_metrics:
            return None
        return max(
            self.source_metrics,
            key=lambda x: x.visits
        ).source
    
    @computed_field  # type: ignore[misc]
    @property
    def best_roi_source(self) -> Optional[SearchSource]:
        """Identify source with best ROI."""
        sources_with_roi = [
            s for s in self.source_metrics
            if s.roi is not None
        ]
        
        if not sources_with_roi:
            return None
        
        return max(sources_with_roi, key=lambda x: x.roi).source  # type: ignore[arg-type, return-value]


class SearchBehavior(BaseSchema):
    """
    Search behavior analytics.
    
    Analyzes how visitors search for hostels to improve
    search experience and SEO.
    """
    
    # Search volume
    total_searches: int = Field(
        ...,
        ge=0,
        description="Total number of searches"
    )
    unique_searchers: int = Field(
        ...,
        ge=0,
        description="Unique users who searched"
    )
    avg_searches_per_session: DecimalNonNegative = Field(
        ...,
        description="Average searches per session"
    )
    
    # Search patterns
    most_searched_cities: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Top 10 most searched cities"
    )
    most_searched_keywords: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Top 20 search keywords"
    )
    
    # Filter usage
    avg_filters_used: DecimalNonNegative = Field(
        ...,
        description="Average number of filters applied"
    )
    most_filtered_amenities: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Top 10 filtered amenities"
    )
    most_common_price_range: Optional[str] = Field(
        None,
        max_length=50,
        description="Most common price range filter"
    )
    
    # Search quality
    avg_results_per_search: DecimalNonNegative = Field(
        ...,
        description="Average results returned per search"
    )
    zero_result_searches: int = Field(
        0,
        ge=0,
        description="Number of searches with zero results"
    )
    zero_result_rate: DecimalPercentage = Field(
        0,
        description="Percentage of searches with no results"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def search_effectiveness_score(self) -> Decimal:
        """
        Calculate search effectiveness score (0-100).
        
        Based on result relevance and zero-result rate.
        """
        # Lower zero-result rate is better
        result_score = 100 - float(self.zero_result_rate)
        
        # More results indicate better coverage
        coverage_score = min(float(self.avg_results_per_search) / 10 * 100, 100)
        
        score = (result_score * 0.7 + coverage_score * 0.3)
        return round(Decimal(str(score)), 2)


class EngagementMetrics(BaseSchema):
    """
    Visitor engagement metrics.
    
    Measures depth and quality of visitor interaction
    with the platform.
    """
    
    # Page engagement
    avg_hostels_viewed_per_session: DecimalNonNegative = Field(
        ...,
        description="Average hostel pages viewed per session"
    )
    avg_time_on_hostel_page_seconds: DecimalNonNegative = Field(
        ...,
        description="Average time spent on hostel detail page"
    )
    avg_pages_per_session: DecimalNonNegative = Field(
        ...,
        description="Average pages viewed per session"
    )
    
    # Feature usage
    comparison_tool_usage_rate: DecimalPercentage = Field(
        ...,
        description="Percentage of sessions using comparison tool"
    )
    review_read_rate: DecimalPercentage = Field(
        0,
        description="Percentage of visitors who read reviews"
    )
    photo_gallery_usage_rate: DecimalPercentage = Field(
        0,
        description="Percentage using photo gallery"
    )
    
    # Interaction depth
    avg_review_pages_viewed: DecimalNonNegative = Field(
        0,
        description="Average review pages viewed"
    )
    avg_photos_viewed: DecimalNonNegative = Field(
        0,
        description="Average photos viewed per hostel"
    )
    
    # Call-to-action engagement
    inquiry_form_views: int = Field(
        0,
        ge=0,
        description="Number of inquiry form views"
    )
    inquiry_submissions: int = Field(
        0,
        ge=0,
        description="Number of inquiry submissions"
    )
    inquiry_conversion_rate: DecimalPercentage = Field(
        0,
        description="Inquiry form conversion rate"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def engagement_level(self) -> str:
        """Classify overall engagement level."""
        score = (
            min(float(self.avg_hostels_viewed_per_session) / 5, 1) * 30 +
            min(float(self.avg_time_on_hostel_page_seconds) / 180, 1) * 30 +
            float(self.comparison_tool_usage_rate) * 0.2 +
            float(self.review_read_rate) * 0.2
        )
        
        if score >= 70:
            return "high"
        elif score >= 40:
            return "moderate"
        else:
            return "low"


class VisitorBehaviorAnalytics(BaseSchema):
    """
    Comprehensive visitor behavior analytics.
    
    Consolidates search, engagement, and exit behavior
    for complete visitor insight.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Search behavior
    search_behavior: SearchBehavior = Field(
        ...,
        description="Search behavior metrics"
    )
    
    # Engagement
    engagement: EngagementMetrics = Field(
        ...,
        description="Engagement metrics"
    )
    
    # Exit behavior
    common_exit_pages: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Top 10 exit pages"
    )
    common_exit_reasons: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Common reasons for exit (from surveys/feedback)"
    )
    bounce_rate: DecimalPercentage = Field(
        ...,
        description="Overall bounce rate"
    )
    
    # Session metrics
    avg_session_duration_seconds: DecimalNonNegative = Field(
        ...,
        description="Average session duration"
    )
    return_visitor_rate: DecimalPercentage = Field(
        0,
        description="Percentage of return visitors"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def visitor_quality_score(self) -> Decimal:
        """
        Calculate overall visitor quality score (0-100).
        
        Combines engagement, search effectiveness, and retention.
        """
        engagement_level_scores = {
            "high": 100,
            "moderate": 60,
            "low": 30,
        }
        
        engagement_score = engagement_level_scores.get(
            self.engagement.engagement_level,
            50
        )
        search_score = float(self.search_behavior.search_effectiveness_score)
        retention_score = float(self.return_visitor_rate)
        
        score = (
            engagement_score * 0.5 +
            search_score * 0.3 +
            retention_score * 0.2
        )
        
        return round(Decimal(str(score)), 2)
    
    def get_optimization_recommendations(self) -> List[str]:
        """
        Generate actionable optimization recommendations.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Search optimization
        if self.search_behavior.zero_result_rate > 10:
            recommendations.append(
                f"High zero-result search rate ({self.search_behavior.zero_result_rate}%) - "
                "improve search coverage or query handling"
            )
        
        # Engagement optimization
        if self.engagement.engagement_level == "low":
            recommendations.append(
                "Low visitor engagement - consider improving content quality "
                "and visual appeal"
            )
        
        # Exit optimization
        if self.bounce_rate > 60:
            recommendations.append(
                f"High bounce rate ({self.bounce_rate}%) - "
                "optimize landing pages and initial user experience"
            )
        
        # Feature adoption
        if self.engagement.comparison_tool_usage_rate < 20:
            recommendations.append(
                "Low comparison tool usage - make feature more prominent"
            )
        
        # Session duration
        if float(self.avg_session_duration_seconds) < 60:
            recommendations.append(
                "Short session duration - improve content engagement "
                "and reduce friction"
            )
        
        return recommendations


class ConversionPathAnalysis(BaseSchema):
    """
    Conversion path and attribution analysis.
    
    Tracks multi-touch visitor journeys to understand
    conversion attribution.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    
    # Path metrics
    avg_touches_before_conversion: DecimalNonNegative = Field(
        ...,
        description="Average touchpoints before booking"
    )
    avg_days_to_conversion: DecimalNonNegative = Field(
        ...,
        description="Average days from first visit to booking"
    )
    
    # Common paths
    top_conversion_paths: List[List[str]] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 conversion paths (sequences of pages/actions)"
    )
    
    # Attribution
    first_touch_attribution: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Revenue attributed to first touch by source"
    )
    last_touch_attribution: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Revenue attributed to last touch by source"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def conversion_complexity(self) -> str:
        """Assess conversion path complexity."""
        touches = float(self.avg_touches_before_conversion)
        
        if touches <= 2:
            return "simple"
        elif touches <= 5:
            return "moderate"
        else:
            return "complex"