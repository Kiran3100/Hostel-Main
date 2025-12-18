"""
Visitor and funnel analytics models for marketing optimization.

Provides persistent storage for:
- Acquisition funnel tracking
- Traffic source analysis
- Visitor behavior patterns
- Conversion optimization
- Search and engagement metrics
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Date, Boolean,
    ForeignKey, Text, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.models.analytics.base_analytics import (
    BaseAnalyticsModel,
    AnalyticsMixin,
    MetricMixin,
    TrendMixin,
    CachedAnalyticsMixin
)


class VisitorFunnel(BaseAnalyticsModel, AnalyticsMixin, CachedAnalyticsMixin):
    """
    Visitor acquisition and conversion funnel.
    
    Tracks visitor journey from initial visit through
    to confirmed booking.
    """
    
    __tablename__ = 'visitor_funnels'
    
    # Funnel stages
    total_visits = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total website visits"
    )
    
    unique_visitors = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Unique visitors"
    )
    
    searches_performed = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Searches performed"
    )
    
    hostel_views = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Hostel detail page views"
    )
    
    comparisons_made = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Comparison tool uses"
    )
    
    registrations = Column(
        Integer,
        nullable=False,
        default=0,
        comment="User registrations"
    )
    
    booking_starts = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Booking form starts"
    )
    
    bookings = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Booking submissions"
    )
    
    confirmed_bookings = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Confirmed bookings"
    )
    
    # Conversion rates
    visit_to_search_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Visit to search %"
    )
    
    search_to_view_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Search to view %"
    )
    
    view_to_registration_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="View to registration %"
    )
    
    registration_to_booking_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Registration to booking %"
    )
    
    booking_to_confirm_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Booking to confirmation %"
    )
    
    visit_to_booking_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Overall conversion %"
    )
    
    # Drop-off analysis
    dropped_after_search = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Drop-offs after search"
    )
    
    dropped_after_hostel_view = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Drop-offs after view"
    )
    
    dropped_after_booking_start = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Booking abandonment"
    )
    
    # Insights
    total_drop_offs = Column(
        Integer,
        nullable=True,
        comment="Total drop-offs"
    )
    
    largest_drop_off_stage = Column(
        String(50),
        nullable=True,
        comment="Stage with largest drop-off"
    )
    
    funnel_efficiency_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Overall efficiency (0-100)"
    )
    
    __table_args__ = (
        Index('ix_visitor_funnel_period', 'period_start', 'period_end'),
        UniqueConstraint(
            'period_start',
            'period_end',
            name='uq_visitor_funnel_unique'
        ),
    )


class TrafficSourceMetrics(BaseAnalyticsModel, AnalyticsMixin):
    """
    Performance metrics by traffic source.
    
    Tracks individual acquisition channel performance.
    """
    
    __tablename__ = 'traffic_source_metrics'
    
    source = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Traffic source"
    )
    
    source_name = Column(
        String(100),
        nullable=True,
        comment="Human-readable name"
    )
    
    # Volume metrics
    visits = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total visits"
    )
    
    unique_visitors = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Unique visitors"
    )
    
    page_views = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total page views"
    )
    
    # Engagement
    avg_session_duration_seconds = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average session duration"
    )
    
    avg_pages_per_session = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg pages per session"
    )
    
    bounce_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Bounce rate %"
    )
    
    # Conversions
    registrations = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Registrations"
    )
    
    bookings = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Bookings"
    )
    
    confirmed_bookings = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Confirmed bookings"
    )
    
    # Conversion rates
    visit_to_registration_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Visit to registration %"
    )
    
    visit_to_booking_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Visit to booking %"
    )
    
    registration_to_booking_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Registration to booking %"
    )
    
    # Revenue
    total_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Total revenue"
    )
    
    revenue_per_visit = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Revenue per visit"
    )
    
    # Cost metrics
    marketing_cost = Column(
        Numeric(precision=15, scale=2),
        nullable=True,
        comment="Marketing cost"
    )
    
    cost_per_acquisition = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Cost per booking"
    )
    
    roi = Column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="Return on investment %"
    )
    
    # Calculated scores
    engagement_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Engagement score (0-100)"
    )
    
    quality_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Source quality score (0-100)"
    )
    
    __table_args__ = (
        Index(
            'ix_traffic_source_period_source',
            'period_start',
            'period_end',
            'source'
        ),
        UniqueConstraint(
            'period_start',
            'period_end',
            'source',
            name='uq_traffic_source_unique'
        ),
    )


class SearchBehavior(BaseAnalyticsModel, AnalyticsMixin, CachedAnalyticsMixin):
    """
    Search behavior analytics.
    
    Analyzes how visitors search to improve
    search experience.
    """
    
    __tablename__ = 'search_behavior'
    
    # Search volume
    total_searches = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total searches"
    )
    
    unique_searchers = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Unique searchers"
    )
    
    avg_searches_per_session = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg searches per session"
    )
    
    # Search patterns
    most_searched_cities = Column(
        JSONB,
        nullable=True,
        comment="Top searched cities"
    )
    
    most_searched_keywords = Column(
        JSONB,
        nullable=True,
        comment="Top keywords"
    )
    
    # Filter usage
    avg_filters_used = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg filters applied"
    )
    
    most_filtered_amenities = Column(
        JSONB,
        nullable=True,
        comment="Top filtered amenities"
    )
    
    most_common_price_range = Column(
        String(50),
        nullable=True,
        comment="Most common price filter"
    )
    
    # Search quality
    avg_results_per_search = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg results returned"
    )
    
    zero_result_searches = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Searches with no results"
    )
    
    zero_result_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=0,
        comment="Zero result rate %"
    )
    
    search_effectiveness_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Effectiveness score (0-100)"
    )
    
    __table_args__ = (
        Index('ix_search_behavior_period', 'period_start', 'period_end'),
    )


class EngagementMetrics(BaseAnalyticsModel, AnalyticsMixin):
    """
    Visitor engagement metrics.
    
    Measures interaction depth and quality.
    """
    
    __tablename__ = 'engagement_metrics'
    
    # Page engagement
    avg_hostels_viewed_per_session = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg hostels viewed"
    )
    
    avg_time_on_hostel_page_seconds = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg time on hostel page"
    )
    
    avg_pages_per_session = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg pages per session"
    )
    
    # Feature usage
    comparison_tool_usage_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Comparison tool usage %"
    )
    
    review_read_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=0,
        comment="Review reading %"
    )
    
    photo_gallery_usage_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=0,
        comment="Photo gallery usage %"
    )
    
    # Interaction depth
    avg_review_pages_viewed = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=0,
        comment="Avg review pages"
    )
    
    avg_photos_viewed = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=0,
        comment="Avg photos viewed"
    )
    
    # Call-to-action
    inquiry_form_views = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Inquiry form views"
    )
    
    inquiry_submissions = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Inquiry submissions"
    )
    
    inquiry_conversion_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=0,
        comment="Inquiry conversion %"
    )
    
    engagement_level = Column(
        String(20),
        nullable=True,
        comment="high, moderate, low"
    )
    
    __table_args__ = (
        Index('ix_engagement_metrics_period', 'period_start', 'period_end'),
    )


class VisitorBehaviorAnalytics(
    BaseAnalyticsModel,
    AnalyticsMixin,
    CachedAnalyticsMixin
):
    """
    Comprehensive visitor behavior analytics.
    
    Consolidates search, engagement, and exit behavior.
    """
    
    __tablename__ = 'visitor_behavior_analytics'
    
    search_behavior_id = Column(
        UUID(as_uuid=True),
        ForeignKey('search_behavior.id', ondelete='SET NULL'),
        nullable=True
    )
    
    engagement_metrics_id = Column(
        UUID(as_uuid=True),
        ForeignKey('engagement_metrics.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Exit behavior
    common_exit_pages = Column(
        JSONB,
        nullable=True,
        comment="Top exit pages"
    )
    
    common_exit_reasons = Column(
        JSONB,
        nullable=True,
        comment="Exit reasons from feedback"
    )
    
    bounce_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Overall bounce rate"
    )
    
    # Session metrics
    avg_session_duration_seconds = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg session duration"
    )
    
    return_visitor_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=0,
        comment="Return visitor %"
    )
    
    # Insights
    visitor_quality_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Quality score (0-100)"
    )
    
    optimization_recommendations = Column(
        JSONB,
        nullable=True,
        comment="Generated recommendations"
    )
    
    __table_args__ = (
        Index('ix_visitor_behavior_period', 'period_start', 'period_end'),
    )
    
    # Relationships
    search_behavior = relationship('SearchBehavior', foreign_keys=[search_behavior_id])
    engagement_metrics = relationship('EngagementMetrics', foreign_keys=[engagement_metrics_id])


class ConversionPathAnalysis(BaseAnalyticsModel, AnalyticsMixin):
    """
    Conversion path and attribution analysis.
    
    Tracks multi-touch visitor journeys for
    conversion attribution.
    """
    
    __tablename__ = 'conversion_path_analysis'
    
    # Path metrics
    avg_touches_before_conversion = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg touchpoints before booking"
    )
    
    avg_days_to_conversion = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg days to booking"
    )
    
    # Common paths
    top_conversion_paths = Column(
        JSONB,
        nullable=True,
        comment="Top conversion paths"
    )
    
    # Attribution
    first_touch_attribution = Column(
        JSONB,
        nullable=True,
        comment="First-touch revenue by source"
    )
    
    last_touch_attribution = Column(
        JSONB,
        nullable=True,
        comment="Last-touch revenue by source"
    )
    
    conversion_complexity = Column(
        String(20),
        nullable=True,
        comment="simple, moderate, complex"
    )
    
    __table_args__ = (
        Index('ix_conversion_path_period', 'period_start', 'period_end'),
    )


class TrafficSourceAnalytics(
    BaseAnalyticsModel,
    AnalyticsMixin,
    CachedAnalyticsMixin
):
    """
    Comprehensive traffic source analysis.
    
    Aggregates and compares all acquisition channels.
    """
    
    __tablename__ = 'traffic_source_analytics'
    
    total_visits = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total visits"
    )
    
    # Source breakdowns
    visits_by_source = Column(
        JSONB,
        nullable=True,
        comment="Visits by source"
    )
    
    registrations_by_source = Column(
        JSONB,
        nullable=True,
        comment="Registrations by source"
    )
    
    bookings_by_source = Column(
        JSONB,
        nullable=True,
        comment="Bookings by source"
    )
    
    visit_to_booking_rate_by_source = Column(
        JSONB,
        nullable=True,
        comment="Conversion rates by source"
    )
    
    # Best performers
    best_converting_source = Column(
        String(50),
        nullable=True,
        comment="Source with best conversion"
    )
    
    highest_volume_source = Column(
        String(50),
        nullable=True,
        comment="Source with highest volume"
    )
    
    best_roi_source = Column(
        String(50),
        nullable=True,
        comment="Source with best ROI"
    )
    
    __table_args__ = (
        Index('ix_traffic_analytics_period', 'period_start', 'period_end'),
    )