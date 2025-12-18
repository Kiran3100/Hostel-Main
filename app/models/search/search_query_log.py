"""
Search query logging and session tracking models.

Comprehensive logging of all search activity for analytics,
optimization, and user behavior analysis.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean, JSON, 
    ForeignKey, Index, Numeric, ARRAY, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB, INET
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.base.enums import NotificationChannel


class SearchQueryLog(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Comprehensive search query logging model.
    
    Tracks all search queries with detailed metadata, filters,
    performance metrics, and user interaction data for deep analytics.
    
    Maps to: search/search_request.py schemas
    """
    __tablename__ = "search_query_logs"
    
    # ===== Query Information =====
    query: str = Column(String(255), nullable=True, index=True, comment="Original search query")
    normalized_query: str = Column(String(255), nullable=True, index=True, comment="Normalized query for matching")
    query_hash: str = Column(String(64), nullable=False, index=True, comment="Hash for duplicate detection")
    
    # ===== Search Type =====
    search_type: str = Column(
        String(50), 
        nullable=False, 
        default="basic",
        index=True,
        comment="Type of search: basic, advanced, nearby, saved"
    )
    
    # ===== User Information =====
    user_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed search (null for anonymous)"
    )
    
    visitor_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Anonymous visitor ID"
    )
    
    # ===== Session Tracking =====
    session_id: str = Column(String(255), nullable=False, index=True, comment="Search session identifier")
    device_fingerprint: Optional[str] = Column(String(255), nullable=True, comment="Device fingerprint for tracking")
    
    # ===== Location Filters =====
    city: Optional[str] = Column(String(100), nullable=True, index=True)
    state: Optional[str] = Column(String(100), nullable=True, index=True)
    pincode: Optional[str] = Column(String(6), nullable=True, index=True)
    
    # Geographic coordinates (for proximity search)
    latitude: Optional[Decimal] = Column(Numeric(precision=10, scale=8), nullable=True)
    longitude: Optional[Decimal] = Column(Numeric(precision=11, scale=8), nullable=True)
    radius_km: Optional[Decimal] = Column(Numeric(precision=5, scale=2), nullable=True)
    
    # ===== Hostel and Room Type Filters =====
    hostel_type: Optional[str] = Column(String(50), nullable=True, index=True)
    room_types: Optional[list] = Column(ARRAY(String), nullable=True)
    gender_preference: Optional[str] = Column(String(50), nullable=True)
    
    # ===== Price Range Filters =====
    min_price: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    max_price: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # ===== Amenities Filters =====
    required_amenities: Optional[list] = Column(ARRAY(String), nullable=True, comment="All required (AND logic)")
    optional_amenities: Optional[list] = Column(ARRAY(String), nullable=True, comment="Any optional (OR logic)")
    
    # ===== Rating Filter =====
    min_rating: Optional[Decimal] = Column(Numeric(precision=3, scale=2), nullable=True)
    
    # ===== Availability Filters =====
    verified_only: bool = Column(Boolean, nullable=False, default=False)
    available_only: bool = Column(Boolean, nullable=False, default=False)
    instant_booking: bool = Column(Boolean, nullable=False, default=False)
    check_in_date: Optional[datetime] = Column(DateTime, nullable=True)
    check_out_date: Optional[datetime] = Column(DateTime, nullable=True)
    
    # ===== Complete Filter Set (JSONB for flexibility) =====
    filters: Optional[dict] = Column(JSONB, nullable=True, comment="Complete filter set as JSON")
    
    # ===== Sorting Options =====
    sort_by: str = Column(String(100), nullable=False, default="relevance")
    sort_order: str = Column(String(10), nullable=False, default="desc")
    
    # ===== Pagination =====
    page: int = Column(Integer, nullable=False, default=1)
    page_size: int = Column(Integer, nullable=False, default=20)
    offset: int = Column(Integer, nullable=False, default=0)
    
    # ===== Advanced Options =====
    include_nearby_cities: bool = Column(Boolean, nullable=False, default=False)
    boost_featured: bool = Column(Boolean, nullable=False, default=True)
    
    # ===== Results Metrics =====
    results_count: int = Column(Integer, nullable=False, default=0, index=True)
    zero_results: bool = Column(Boolean, nullable=False, default=False, index=True)
    returned_results: int = Column(Integer, nullable=False, default=0)
    total_pages: int = Column(Integer, nullable=False, default=0)
    
    # ===== Performance Metrics =====
    execution_time_ms: int = Column(Integer, nullable=False, comment="Query execution time")
    fetch_time_ms: Optional[int] = Column(Integer, nullable=True, comment="Data fetch time")
    total_time_ms: int = Column(Integer, nullable=False, comment="Total response time")
    cache_hit: bool = Column(Boolean, nullable=False, default=False)
    cache_key: Optional[str] = Column(String(255), nullable=True)
    
    # ===== Result Quality Metrics =====
    max_relevance_score: Optional[Decimal] = Column(Numeric(precision=10, scale=4), nullable=True)
    min_relevance_score: Optional[Decimal] = Column(Numeric(precision=10, scale=4), nullable=True)
    avg_relevance_score: Optional[Decimal] = Column(Numeric(precision=10, scale=4), nullable=True)
    
    # ===== User Interaction =====
    clicked_result_ids: Optional[list] = Column(ARRAY(PostgresUUID(as_uuid=True)), nullable=True)
    clicked_result_positions: Optional[list] = Column(ARRAY(Integer), nullable=True)
    first_click_position: Optional[int] = Column(Integer, nullable=True)
    has_clicks: bool = Column(Boolean, nullable=False, default=False, index=True)
    click_time_seconds: Optional[int] = Column(Integer, nullable=True, comment="Time to first click")
    
    # Conversion tracking
    resulted_in_booking: bool = Column(Boolean, nullable=False, default=False, index=True)
    resulted_in_inquiry: bool = Column(Boolean, nullable=False, default=False)
    booking_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # ===== Source Tracking =====
    source: str = Column(String(50), nullable=False, default="web", index=True)  # web, mobile_app, api
    platform: Optional[str] = Column(String(50), nullable=True)  # ios, android, web
    app_version: Optional[str] = Column(String(50), nullable=True)
    referrer: Optional[str] = Column(Text, nullable=True)
    utm_source: Optional[str] = Column(String(100), nullable=True)
    utm_medium: Optional[str] = Column(String(100), nullable=True)
    utm_campaign: Optional[str] = Column(String(100), nullable=True)
    
    # ===== Device Information =====
    device_type: Optional[str] = Column(String(50), nullable=True)  # mobile, desktop, tablet
    browser: Optional[str] = Column(String(100), nullable=True)
    browser_version: Optional[str] = Column(String(50), nullable=True)
    os: Optional[str] = Column(String(100), nullable=True)
    os_version: Optional[str] = Column(String(50), nullable=True)
    screen_resolution: Optional[str] = Column(String(50), nullable=True)
    
    # ===== Network Information =====
    ip_address: Optional[str] = Column(INET, nullable=True)
    user_agent: Optional[str] = Column(Text, nullable=True)
    
    # ===== Geographic Context (User Location) =====
    user_country: Optional[str] = Column(String(100), nullable=True)
    user_region: Optional[str] = Column(String(100), nullable=True)
    user_city: Optional[str] = Column(String(100), nullable=True)
    user_timezone: Optional[str] = Column(String(50), nullable=True)
    
    # ===== Search Intent Classification =====
    search_intent: Optional[str] = Column(String(50), nullable=True)  # exploratory, comparison, ready_to_book
    confidence_score: Optional[Decimal] = Column(Numeric(precision=3, scale=2), nullable=True)
    
    # ===== Facets Used =====
    facets_applied: Optional[list] = Column(ARRAY(String), nullable=True)
    facets_returned: Optional[dict] = Column(JSONB, nullable=True)
    
    # ===== A/B Testing =====
    experiment_id: Optional[str] = Column(String(100), nullable=True, index=True)
    variant_id: Optional[str] = Column(String(100), nullable=True)
    
    # ===== Error Tracking =====
    had_errors: bool = Column(Boolean, nullable=False, default=False)
    error_type: Optional[str] = Column(String(100), nullable=True)
    error_message: Optional[str] = Column(Text, nullable=True)
    
    # ===== Saved Search Reference =====
    saved_search_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("saved_searches.id", ondelete="SET NULL"),
        nullable=True,
        comment="If this search was executed from a saved search"
    )
    
    # ===== Relationships =====
    user = relationship("User", foreign_keys=[user_id], back_populates="search_logs")
    visitor = relationship("Visitor", foreign_keys=[visitor_id], back_populates="search_logs")
    booking = relationship("Booking", foreign_keys=[booking_id])
    saved_search = relationship("SavedSearch", foreign_keys=[saved_search_id])
    session = relationship("SearchSession", back_populates="query_logs", foreign_keys="SearchQueryLog.session_id")
    
    # ===== Table Configuration =====
    __table_args__ = (
        # Performance indexes
        Index('idx_search_query_user_date', 'user_id', 'created_at'),
        Index('idx_search_query_session', 'session_id', 'created_at'),
        Index('idx_search_query_location', 'city', 'state'),
        Index('idx_search_query_filters', 'hostel_type', 'min_price', 'max_price'),
        Index('idx_search_query_performance', 'execution_time_ms', 'zero_results'),
        Index('idx_search_query_results', 'results_count', 'has_clicks'),
        Index('idx_search_query_conversion', 'resulted_in_booking', 'resulted_in_inquiry'),
        Index('idx_search_query_source', 'source', 'platform'),
        Index('idx_search_query_experiment', 'experiment_id', 'variant_id'),
        Index('idx_search_query_hash', 'query_hash', 'created_at'),
        
        # GIN index for JSONB columns (PostgreSQL)
        Index('idx_search_query_filters_gin', 'filters', postgresql_using='gin'),
        Index('idx_search_query_facets_gin', 'facets_returned', postgresql_using='gin'),
        
        # Constraints
        CheckConstraint('page >= 1', name='check_page_positive'),
        CheckConstraint('page_size >= 1 AND page_size <= 100', name='check_page_size_range'),
        CheckConstraint('results_count >= 0', name='check_results_count_positive'),
        CheckConstraint('execution_time_ms >= 0', name='check_execution_time_positive'),
        
        {'comment': 'Comprehensive search query logging for analytics and optimization'}
    )
    
    def __repr__(self):
        return f"<SearchQueryLog(id={self.id}, query='{self.query}', results={self.results_count})>"


class SearchSession(BaseModel, UUIDMixin, TimestampMixin):
    """
    Search session tracking model.
    
    Groups related searches into sessions for journey analysis,
    conversion tracking, and user behavior insights.
    
    Maps to: search/search_analytics.py session tracking
    """
    __tablename__ = "search_sessions"
    
    # ===== Session Information =====
    session_id: str = Column(String(255), nullable=False, unique=True, index=True)
    
    # ===== User Information =====
    user_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    visitor_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # ===== Session Timeline =====
    start_time: datetime = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    end_time: Optional[datetime] = Column(DateTime, nullable=True)
    last_activity: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    duration_seconds: Optional[int] = Column(Integer, nullable=True)
    is_active: bool = Column(Boolean, nullable=False, default=True, index=True)
    
    # ===== Search Metrics =====
    total_searches: int = Column(Integer, nullable=False, default=0)
    unique_queries: int = Column(Integer, nullable=False, default=0)
    zero_result_searches: int = Column(Integer, nullable=False, default=0)
    refined_searches: int = Column(Integer, nullable=False, default=0, comment="Number of filter refinements")
    
    # ===== Engagement Metrics =====
    total_clicks: int = Column(Integer, nullable=False, default=0)
    unique_hostels_clicked: int = Column(Integer, nullable=False, default=0)
    avg_time_to_first_click: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # ===== Conversion Metrics =====
    conversion_events: int = Column(Integer, nullable=False, default=0)
    resulted_in_booking: bool = Column(Boolean, nullable=False, default=False, index=True)
    resulted_in_inquiry: bool = Column(Boolean, nullable=False, default=False)
    booking_ids: Optional[list] = Column(ARRAY(PostgresUUID(as_uuid=True)), nullable=True)
    
    # ===== Search Patterns =====
    search_progression: Optional[list] = Column(JSONB, nullable=True, comment="Ordered list of searches in session")
    filter_evolution: Optional[dict] = Column(JSONB, nullable=True, comment="How filters changed over session")
    
    # ===== Device and Context =====
    device_type: Optional[str] = Column(String(50), nullable=True, index=True)
    browser: Optional[str] = Column(String(100), nullable=True)
    browser_version: Optional[str] = Column(String(50), nullable=True)
    os: Optional[str] = Column(String(100), nullable=True)
    os_version: Optional[str] = Column(String(50), nullable=True)
    device_fingerprint: Optional[str] = Column(String(255), nullable=True)
    
    # ===== Network Information =====
    ip_address: Optional[str] = Column(INET, nullable=True)
    user_agent: Optional[str] = Column(Text, nullable=True)
    
    # ===== Geographic Context =====
    country: Optional[str] = Column(String(100), nullable=True, index=True)
    region: Optional[str] = Column(String(100), nullable=True)
    city: Optional[str] = Column(String(100), nullable=True, index=True)
    timezone: Optional[str] = Column(String(50), nullable=True)
    
    # ===== Source Tracking =====
    entry_source: str = Column(String(50), nullable=False, default="direct")  # direct, organic, paid, referral, social
    landing_page: Optional[str] = Column(Text, nullable=True)
    referrer: Optional[str] = Column(Text, nullable=True)
    utm_source: Optional[str] = Column(String(100), nullable=True)
    utm_medium: Optional[str] = Column(String(100), nullable=True)
    utm_campaign: Optional[str] = Column(String(100), nullable=True)
    utm_content: Optional[str] = Column(String(100), nullable=True)
    utm_term: Optional[str] = Column(String(100), nullable=True)
    
    # ===== Session Quality Metrics =====
    bounce: bool = Column(Boolean, nullable=False, default=False, comment="Single search with no clicks")
    quality_score: Optional[Decimal] = Column(Numeric(precision=5, scale=2), nullable=True)
    engagement_score: Optional[Decimal] = Column(Numeric(precision=5, scale=2), nullable=True)
    
    # ===== A/B Testing =====
    experiments: Optional[dict] = Column(JSONB, nullable=True, comment="Active experiments in this session")
    
    # ===== Session Notes =====
    notes: Optional[str] = Column(Text, nullable=True, comment="Additional session metadata")
    
    # ===== Relationships =====
    user = relationship("User", foreign_keys=[user_id], back_populates="search_sessions")
    visitor = relationship("Visitor", foreign_keys=[visitor_id], back_populates="search_sessions")
    query_logs = relationship(
        "SearchQueryLog", 
        back_populates="session",
        foreign_keys="SearchQueryLog.session_id",
        primaryjoin="SearchSession.session_id==SearchQueryLog.session_id"
    )
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_search_session_user', 'user_id', 'start_time'),
        Index('idx_search_session_visitor', 'visitor_id', 'start_time'),
        Index('idx_search_session_dates', 'start_time', 'end_time'),
        Index('idx_search_session_metrics', 'total_searches', 'total_clicks'),
        Index('idx_search_session_conversion', 'resulted_in_booking', 'conversion_events'),
        Index('idx_search_session_active', 'is_active', 'last_activity'),
        Index('idx_search_session_device', 'device_type', 'country'),
        Index('idx_search_session_source', 'entry_source', 'utm_campaign'),
        
        # GIN indexes
        Index('idx_search_session_experiments_gin', 'experiments', postgresql_using='gin'),
        
        CheckConstraint('total_searches >= 0', name='check_total_searches_positive'),
        CheckConstraint('duration_seconds >= 0', name='check_duration_positive'),
        
        {'comment': 'Search session tracking for user journey analysis'}
    )
    
    def __repr__(self):
        return f"<SearchSession(id={self.id}, session_id='{self.session_id}', searches={self.total_searches})>"


class SavedSearch(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Saved search model for users.
    
    Allows users to save frequently used search criteria with optional
    alerts for new matching hostels.
    
    Maps to: search/search_request.py SavedSearch schemas
    """
    __tablename__ = "saved_searches"
    
    # ===== User Information =====
    user_id: UUID = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # ===== Search Information =====
    name: str = Column(String(100), nullable=False, comment="User-friendly name for saved search")
    description: Optional[str] = Column(Text, nullable=True)
    
    # ===== Search Criteria (Complete filter set) =====
    search_criteria: dict = Column(JSONB, nullable=False, comment="Complete search parameters")
    
    # Quick access fields (denormalized for performance)
    query: Optional[str] = Column(String(255), nullable=True)
    city: Optional[str] = Column(String(100), nullable=True, index=True)
    state: Optional[str] = Column(String(100), nullable=True)
    hostel_type: Optional[str] = Column(String(50), nullable=True)
    min_price: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    max_price: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # ===== Alert Configuration =====
    is_alert_enabled: bool = Column(Boolean, nullable=False, default=False, index=True)
    alert_frequency: Optional[str] = Column(String(20), nullable=True)  # daily, weekly, instant
    alert_channels: Optional[list] = Column(ARRAY(String), nullable=True)  # email, sms, push, in_app
    
    # ===== Alert Status =====
    last_alert_sent: Optional[datetime] = Column(DateTime, nullable=True)
    next_alert_scheduled: Optional[datetime] = Column(DateTime, nullable=True, index=True)
    alert_count: int = Column(Integer, nullable=False, default=0)
    
    # ===== Execution Tracking =====
    last_executed_at: Optional[datetime] = Column(DateTime, nullable=True)
    execution_count: int = Column(Integer, nullable=False, default=0)
    last_result_count: int = Column(Integer, nullable=False, default=0)
    
    # ===== Status =====
    is_active: bool = Column(Boolean, nullable=False, default=True, index=True)
    is_favorite: bool = Column(Boolean, nullable=False, default=False)
    
    # ===== Display Order =====
    display_order: int = Column(Integer, nullable=False, default=0)
    
    # ===== Metadata =====
    tags: Optional[list] = Column(ARRAY(String), nullable=True)
    notes: Optional[str] = Column(Text, nullable=True)
    
    # ===== Relationships =====
    user = relationship("User", back_populates="saved_searches")
    executions = relationship("SearchQueryLog", back_populates="saved_search", foreign_keys="SearchQueryLog.saved_search_id")
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_saved_search_user', 'user_id', 'is_active'),
        Index('idx_saved_search_alerts', 'is_alert_enabled', 'next_alert_scheduled'),
        Index('idx_saved_search_location', 'city', 'state'),
        Index('idx_saved_search_favorite', 'user_id', 'is_favorite'),
        
        # GIN index for JSONB
        Index('idx_saved_search_criteria_gin', 'search_criteria', postgresql_using='gin'),
        
        {'comment': 'User saved searches with alert functionality'}
    )
    
    def __repr__(self):
        return f"<SavedSearch(id={self.id}, name='{self.name}', user_id={self.user_id})>"