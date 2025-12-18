"""
Search analytics and insights models.

Comprehensive analytics on search behavior, popular queries,
trending searches, and zero-result analysis for optimization.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Column, String, Integer, DateTime, Date, Boolean, JSON, 
    ForeignKey, Index, Numeric, Text, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import UUIDMixin, TimestampMixin


class SearchTermStats(BaseModel, UUIDMixin, TimestampMixin):
    """
    Detailed statistics for individual search terms.
    
    Tracks usage patterns, result quality, and engagement metrics
    for search optimization and content gap analysis.
    
    Maps to: search/search_analytics.py SearchTermStats
    """
    __tablename__ = "search_term_stats"
    
    # ===== Term Information =====
    term: str = Column(String(255), nullable=False, index=True)
    normalized_term: str = Column(String(255), nullable=False, unique=True, index=True)
    term_hash: str = Column(String(64), nullable=False, index=True)
    
    # ===== Period Information =====
    period_start: date = Column(Date, nullable=False, index=True)
    period_end: date = Column(Date, nullable=False, index=True)
    period_type: str = Column(String(20), nullable=False, default="daily")  # daily, weekly, monthly
    
    # ===== Usage Metrics =====
    search_count: int = Column(Integer, nullable=False, default=0)
    unique_users: int = Column(Integer, nullable=False, default=0)
    unique_sessions: int = Column(Integer, nullable=False, default=0)
    
    # ===== Result Quality Metrics =====
    avg_results: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    total_results_shown: int = Column(Integer, nullable=False, default=0)
    zero_result_count: int = Column(Integer, nullable=False, default=0)
    zero_result_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Engagement Metrics =====
    total_clicks: int = Column(Integer, nullable=False, default=0)
    unique_clicked_hostels: int = Column(Integer, nullable=False, default=0)
    avg_click_position: Optional[Decimal] = Column(Numeric(precision=5, scale=2), nullable=True)
    click_through_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Conversion Metrics =====
    resulted_in_bookings: int = Column(Integer, nullable=False, default=0)
    resulted_in_inquiries: int = Column(Integer, nullable=False, default=0)
    booking_conversion_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Temporal Data =====
    first_searched_at: datetime = Column(DateTime, nullable=False)
    last_searched_at: datetime = Column(DateTime, nullable=False)
    
    # ===== Trend Indicators =====
    trend_direction: Optional[str] = Column(String(20), nullable=True, index=True)  # rising, falling, stable
    growth_rate: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    velocity_score: Optional[Decimal] = Column(Numeric(precision=10, scale=4), nullable=True)
    
    # Previous period comparison
    previous_period_count: Optional[int] = Column(Integer, nullable=True)
    period_over_period_change: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # ===== Category Breakdown =====
    category_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    hostel_type_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    location_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    
    # ===== Search Context =====
    common_filters: Optional[dict] = Column(JSONB, nullable=True, comment="Most common filters used with this term")
    common_refinements: Optional[list] = Column(JSONB, nullable=True, comment="Common search refinements")
    
    # ===== Quality Indicators =====
    avg_relevance_score: Optional[Decimal] = Column(Numeric(precision=10, scale=4), nullable=True)
    user_satisfaction_score: Optional[Decimal] = Column(Numeric(precision=5, scale=2), nullable=True)
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_search_term_stats_term', 'normalized_term'),
        Index('idx_search_term_stats_period', 'period_start', 'period_end', 'period_type'),
        Index('idx_search_term_stats_count', 'search_count'),
        Index('idx_search_term_stats_trend', 'trend_direction', 'growth_rate'),
        Index('idx_search_term_stats_quality', 'zero_result_rate', 'click_through_rate'),
        Index('idx_search_term_stats_conversion', 'booking_conversion_rate'),
        
        # GIN indexes
        Index('idx_search_term_stats_categories_gin', 'category_breakdown', postgresql_using='gin'),
        
        CheckConstraint('search_count >= 0', name='check_search_count_positive'),
        CheckConstraint('zero_result_rate >= 0 AND zero_result_rate <= 100', name='check_zero_result_rate_range'),
        CheckConstraint('click_through_rate >= 0 AND click_through_rate <= 100', name='check_ctr_range'),
        
        {'comment': 'Detailed statistics for individual search terms'}
    )
    
    def __repr__(self):
        return f"<SearchTermStats(term='{self.term}', count={self.search_count}, ctr={self.click_through_rate})>"


class SearchMetrics(BaseModel, UUIDMixin, TimestampMixin):
    """
    Aggregated search performance metrics.
    
    Provides overview of search system health, performance,
    and quality across all searches.
    
    Maps to: search/search_analytics.py SearchMetrics
    """
    __tablename__ = "search_metrics"
    
    # ===== Period Information =====
    metric_date: date = Column(Date, nullable=False, index=True)
    period_type: str = Column(String(20), nullable=False, index=True)  # hourly, daily, weekly, monthly
    period_start: datetime = Column(DateTime, nullable=False)
    period_end: datetime = Column(DateTime, nullable=False)
    
    # ===== Hostel Context (for multi-hostel analytics) =====
    hostel_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Null for platform-wide metrics"
    )
    
    # ===== Volume Metrics =====
    total_searches: int = Column(Integer, nullable=False, default=0)
    unique_searches: int = Column(Integer, nullable=False, default=0)
    unique_users: int = Column(Integer, nullable=False, default=0)
    unique_sessions: int = Column(Integer, nullable=False, default=0)
    anonymous_searches: int = Column(Integer, nullable=False, default=0)
    
    # ===== Search Type Breakdown =====
    basic_searches: int = Column(Integer, nullable=False, default=0)
    advanced_searches: int = Column(Integer, nullable=False, default=0)
    nearby_searches: int = Column(Integer, nullable=False, default=0)
    saved_searches_executed: int = Column(Integer, nullable=False, default=0)
    
    # ===== Quality Metrics =====
    avg_results_per_search: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    median_results_per_search: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    zero_result_searches: int = Column(Integer, nullable=False, default=0)
    zero_result_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Performance Metrics =====
    avg_response_time_ms: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    median_response_time_ms: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    p50_response_time_ms: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    p95_response_time_ms: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    p99_response_time_ms: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    max_response_time_ms: int = Column(Integer, nullable=False, default=0)
    
    # ===== Cache Performance =====
    cache_hit_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    cache_hits: int = Column(Integer, nullable=False, default=0)
    cache_misses: int = Column(Integer, nullable=False, default=0)
    
    # ===== Engagement Metrics =====
    total_clicks: int = Column(Integer, nullable=False, default=0)
    searches_with_clicks: int = Column(Integer, nullable=False, default=0)
    avg_click_through_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    avg_time_to_first_click: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # ===== Conversion Metrics =====
    searches_resulting_in_bookings: int = Column(Integer, nullable=False, default=0)
    searches_resulting_in_inquiries: int = Column(Integer, nullable=False, default=0)
    search_to_booking_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    search_to_inquiry_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Filter Usage =====
    searches_with_filters: int = Column(Integer, nullable=False, default=0)
    avg_filters_per_search: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    filter_usage_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    
    # ===== Popular Filters =====
    most_used_locations: Optional[list] = Column(JSONB, nullable=True)
    most_used_hostel_types: Optional[list] = Column(JSONB, nullable=True)
    most_used_amenities: Optional[list] = Column(JSONB, nullable=True)
    common_price_ranges: Optional[dict] = Column(JSONB, nullable=True)
    
    # ===== Error Metrics =====
    error_count: int = Column(Integer, nullable=False, default=0)
    error_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Device Breakdown =====
    mobile_searches: int = Column(Integer, nullable=False, default=0)
    desktop_searches: int = Column(Integer, nullable=False, default=0)
    tablet_searches: int = Column(Integer, nullable=False, default=0)
    
    # ===== Source Breakdown =====
    organic_searches: int = Column(Integer, nullable=False, default=0)
    paid_searches: int = Column(Integer, nullable=False, default=0)
    direct_searches: int = Column(Integer, nullable=False, default=0)
    referral_searches: int = Column(Integer, nullable=False, default=0)
    
    # ===== Relationships =====
    hostel = relationship("Hostel", foreign_keys=[hostel_id])
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_search_metrics_date_period', 'metric_date', 'period_type'),
        Index('idx_search_metrics_hostel', 'hostel_id', 'metric_date'),
        Index('idx_search_metrics_volume', 'total_searches', 'unique_users'),
        Index('idx_search_metrics_quality', 'zero_result_rate', 'avg_response_time_ms'),
        Index('idx_search_metrics_conversion', 'search_to_booking_rate'),
        
        # GIN indexes
        Index('idx_search_metrics_filters_gin', 'filter_usage_breakdown', postgresql_using='gin'),
        
        CheckConstraint('total_searches >= 0', name='check_total_searches_positive'),
        CheckConstraint('zero_result_rate >= 0 AND zero_result_rate <= 100', name='check_zero_result_rate_range'),
        CheckConstraint('cache_hit_rate >= 0 AND cache_hit_rate <= 100', name='check_cache_hit_rate_range'),
        
        {'comment': 'Aggregated search performance metrics'}
    )
    
    def __repr__(self):
        return f"<SearchMetrics(date={self.metric_date}, searches={self.total_searches})>"


class PopularSearchTerm(BaseModel, UUIDMixin, TimestampMixin):
    """
    Popular search terms with rankings.
    
    Updated periodically to show trending/popular searches to users.
    
    Maps to: search/search_analytics.py PopularSearchTerm
    """
    __tablename__ = "popular_search_terms"
    
    # ===== Ranking Information =====
    rank: int = Column(Integer, nullable=False, index=True)
    previous_rank: Optional[int] = Column(Integer, nullable=True)
    rank_change: Optional[int] = Column(Integer, nullable=True, comment="+/- positions moved")
    
    # ===== Period Information =====
    period_start: date = Column(Date, nullable=False, index=True)
    period_end: date = Column(Date, nullable=False, index=True)
    period_type: str = Column(String(20), nullable=False, default="weekly")
    
    # ===== Term Details =====
    term: str = Column(String(255), nullable=False, index=True)
    normalized_term: str = Column(String(255), nullable=False, index=True)
    
    # ===== Metrics =====
    search_count: int = Column(Integer, nullable=False, default=0)
    unique_users: int = Column(Integer, nullable=False, default=0)
    result_count: int = Column(Integer, nullable=False, default=0)
    avg_results: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    click_through_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Context Filters =====
    city: Optional[str] = Column(String(100), nullable=True, index=True)
    state: Optional[str] = Column(String(100), nullable=True)
    hostel_type: Optional[str] = Column(String(50), nullable=True, index=True)
    category: Optional[str] = Column(String(100), nullable=True)
    
    # ===== Display Information =====
    display_text: Optional[str] = Column(String(255), nullable=True)
    description: Optional[str] = Column(Text, nullable=True)
    
    # ===== Status =====
    is_active: bool = Column(Boolean, nullable=False, default=True)
    is_featured: bool = Column(Boolean, nullable=False, default=False)
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_popular_search_ranking', 'rank', 'period_start', 'period_type'),
        Index('idx_popular_search_term', 'normalized_term', 'period_start'),
        Index('idx_popular_search_context', 'city', 'hostel_type'),
        Index('idx_popular_search_period', 'period_start', 'period_end'),
        
        CheckConstraint('rank >= 1', name='check_rank_positive'),
        CheckConstraint('search_count >= 0', name='check_search_count_positive'),
        
        {'comment': 'Popular search terms with rankings for display'}
    )
    
    def __repr__(self):
        return f"<PopularSearchTerm(rank={self.rank}, term='{self.term}', count={self.search_count})>"


class TrendingSearch(BaseModel, UUIDMixin, TimestampMixin):
    """
    Rapidly growing search terms.
    
    Identifies emerging search patterns and seasonal trends.
    
    Maps to: search/search_analytics.py TrendingSearch
    """
    __tablename__ = "trending_searches"
    
    # ===== Term Information =====
    term: str = Column(String(255), nullable=False, index=True)
    normalized_term: str = Column(String(255), nullable=False, index=True)
    
    # ===== Growth Metrics =====
    current_period_count: int = Column(Integer, nullable=False)
    previous_period_count: int = Column(Integer, nullable=False)
    growth_rate: Decimal = Column(Numeric(precision=10, scale=2), nullable=False)
    growth_absolute: int = Column(Integer, nullable=False, comment="Absolute increase in searches")
    velocity_score: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, comment="Trending velocity (higher = faster growth)")
    
    # ===== Period Information =====
    current_period_start: date = Column(Date, nullable=False, index=True)
    current_period_end: date = Column(Date, nullable=False)
    previous_period_start: date = Column(Date, nullable=False)
    previous_period_end: date = Column(Date, nullable=False)
    period_type: str = Column(String(20), nullable=False, default="daily")
    
    # ===== Ranking =====
    trending_rank: int = Column(Integer, nullable=False, index=True)
    
    # ===== Context =====
    category: Optional[str] = Column(String(100), nullable=True, index=True)
    geographic_focus: Optional[str] = Column(String(100), nullable=True, comment="Primary city/region")
    hostel_type_focus: Optional[str] = Column(String(50), nullable=True)
    
    # ===== Trend Classification =====
    trend_type: str = Column(String(50), nullable=False, default="emerging")  # emerging, seasonal, event_driven, sustained
    confidence_score: Decimal = Column(Numeric(precision=3, scale=2), nullable=False, default=0)
    
    # ===== Additional Metrics =====
    unique_users: int = Column(Integer, nullable=False, default=0)
    avg_results: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    click_through_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Prediction =====
    predicted_next_period: Optional[int] = Column(Integer, nullable=True, comment="Predicted searches for next period")
    
    # ===== Status =====
    is_active: bool = Column(Boolean, nullable=False, default=True)
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_trending_search_growth', 'growth_rate', 'velocity_score'),
        Index('idx_trending_search_term', 'normalized_term', 'current_period_start'),
        Index('idx_trending_search_period', 'current_period_start', 'current_period_end'),
        Index('idx_trending_search_rank', 'trending_rank', 'is_active'),
        Index('idx_trending_search_category', 'category', 'trend_type'),
        
        CheckConstraint('current_period_count >= 0', name='check_current_count_positive'),
        CheckConstraint('previous_period_count >= 0', name='check_previous_count_positive'),
        CheckConstraint('velocity_score >= 0', name='check_velocity_positive'),
        
        {'comment': 'Rapidly growing search terms and emerging trends'}
    )
    
    def __repr__(self):
        return f"<TrendingSearch(term='{self.term}', growth={self.growth_rate}%, velocity={self.velocity_score})>"


class ZeroResultTerm(BaseModel, UUIDMixin, TimestampMixin):
    """
    Search terms that consistently return zero results.
    
    Critical for search optimization, content gap analysis,
    and improving search coverage.
    
    Maps to: search/search_analytics.py ZeroResultTerm
    """
    __tablename__ = "zero_result_terms"
    
    # ===== Term Information =====
    term: str = Column(String(255), nullable=False, index=True)
    normalized_term: str = Column(String(255), nullable=False, unique=True, index=True)
    term_hash: str = Column(String(64), nullable=False, index=True)
    
    # ===== Search Metrics =====
    search_count: int = Column(Integer, nullable=False, default=0)
    unique_users: int = Column(Integer, nullable=False, default=0)
    unique_sessions: int = Column(Integer, nullable=False, default=0)
    
    # ===== Temporal Data =====
    first_seen: datetime = Column(DateTime, nullable=False, index=True)
    last_seen: datetime = Column(DateTime, nullable=False, index=True)
    days_active: int = Column(Integer, nullable=False, default=0)
    
    # ===== Intent Analysis =====
    likely_intent: Optional[str] = Column(String(100), nullable=True, index=True)  # location, amenity, price, specific_hostel
    intent_confidence: Decimal = Column(Numeric(precision=3, scale=2), nullable=False, default=0)
    extracted_entities: Optional[dict] = Column(JSONB, nullable=True, comment="Extracted locations, amenities, etc.")
    
    # ===== Suggestions =====
    suggested_alternatives: Optional[list] = Column(JSONB, nullable=True)
    similar_successful_queries: Optional[list] = Column(JSONB, nullable=True)
    auto_suggestion_enabled: bool = Column(Boolean, nullable=False, default=False)
    
    # ===== Resolution Tracking =====
    resolution_status: str = Column(String(50), nullable=False, default="unresolved", index=True)  # unresolved, resolved, ignored, investigating
    resolution_type: Optional[str] = Column(String(50), nullable=True)  # content_added, synonym_added, spelling_fixed, ignored
    resolved_at: Optional[datetime] = Column(DateTime, nullable=True)
    resolved_by: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True
    )
    resolution_notes: Optional[str] = Column(Text, nullable=True)
    
    # ===== Priority and Impact =====
    priority_score: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0, comment="Based on frequency and user impact")
    business_impact: str = Column(String(20), nullable=False, default="low")  # low, medium, high, critical
    
    # ===== Context =====
    common_filters: Optional[dict] = Column(JSONB, nullable=True)
    geographic_distribution: Optional[dict] = Column(JSONB, nullable=True)
    device_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    
    # ===== Follow-up Actions =====
    requires_content: bool = Column(Boolean, nullable=False, default=False)
    requires_synonym: bool = Column(Boolean, nullable=False, default=False)
    requires_spelling_fix: bool = Column(Boolean, nullable=False, default=False)
    requires_disambiguation: bool = Column(Boolean, nullable=False, default=False)
    
    # ===== Monitoring =====
    last_reviewed: Optional[datetime] = Column(DateTime, nullable=True)
    reviewed_by: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # ===== Relationships =====
    resolver = relationship("AdminUser", foreign_keys=[resolved_by])
    reviewer = relationship("AdminUser", foreign_keys=[reviewed_by])
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_zero_result_term', 'normalized_term'),
        Index('idx_zero_result_count', 'search_count', 'unique_users'),
        Index('idx_zero_result_status', 'resolution_status', 'last_seen'),
        Index('idx_zero_result_priority', 'priority_score', 'business_impact'),
        Index('idx_zero_result_dates', 'first_seen', 'last_seen'),
        Index('idx_zero_result_intent', 'likely_intent', 'intent_confidence'),
        
        # GIN indexes
        Index('idx_zero_result_entities_gin', 'extracted_entities', postgresql_using='gin'),
        Index('idx_zero_result_filters_gin', 'common_filters', postgresql_using='gin'),
        
        CheckConstraint('search_count >= 0', name='check_search_count_positive'),
        CheckConstraint('intent_confidence >= 0 AND intent_confidence <= 1', name='check_confidence_range'),
        
        {'comment': 'Search terms with zero results for optimization'}
    )
    
    def __repr__(self):
        return f"<ZeroResultTerm(term='{self.term}', count={self.search_count}, status='{self.resolution_status}')>"


class SearchAnalyticsReport(BaseModel, UUIDMixin, TimestampMixin):
    """
    Generated search analytics reports.
    
    Stores pre-computed analytics reports for quick retrieval.
    
    Maps to: search/search_analytics.py SearchAnalytics
    """
    __tablename__ = "search_analytics_reports"
    
    # ===== Report Information =====
    report_name: str = Column(String(100), nullable=False)
    report_type: str = Column(String(50), nullable=False, index=True)  # daily, weekly, monthly, custom
    
    # ===== Period Information =====
    period_start: date = Column(Date, nullable=False, index=True)
    period_end: date = Column(Date, nullable=False, index=True)
    generated_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # ===== Scope =====
    hostel_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Null for platform-wide reports"
    )
    
    # ===== Report Data =====
    overall_metrics: dict = Column(JSONB, nullable=False, comment="SearchMetrics data")
    top_searches: list = Column(JSONB, nullable=False, comment="PopularSearchTerm list")
    trending_searches: list = Column(JSONB, nullable=False, comment="TrendingSearch list")
    zero_result_searches: list = Column(JSONB, nullable=False, comment="ZeroResultTerm list")
    
    # ===== Breakdowns =====
    category_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    geographic_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    device_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    temporal_breakdown: Optional[dict] = Column(JSONB, nullable=True)
    
    # ===== Insights =====
    key_insights: Optional[list] = Column(JSONB, nullable=True, comment="AI-generated insights")
    recommendations: Optional[list] = Column(JSONB, nullable=True, comment="Optimization recommendations")
    
    # ===== Quality Indicators =====
    has_quality_issues: bool = Column(Boolean, nullable=False, default=False)
    engagement_score: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Status =====
    is_published: bool = Column(Boolean, nullable=False, default=False)
    published_at: Optional[datetime] = Column(DateTime, nullable=True)
    
    # ===== Relationships =====
    hostel = relationship("Hostel", foreign_keys=[hostel_id])
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_analytics_report_period', 'period_start', 'period_end', 'report_type'),
        Index('idx_analytics_report_hostel', 'hostel_id', 'generated_at'),
        Index('idx_analytics_report_published', 'is_published', 'published_at'),
        
        # GIN indexes
        Index('idx_analytics_report_metrics_gin', 'overall_metrics', postgresql_using='gin'),
        
        {'comment': 'Pre-computed search analytics reports'}
    )
    
    def __repr__(self):
        return f"<SearchAnalyticsReport(type='{self.report_type}', period={self.period_start} to {self.period_end})>"