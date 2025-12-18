"""
Search autocomplete and suggestion models.

Real-time search suggestions, autocomplete functionality,
and intelligent query suggestions for enhanced user experience.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Column, String, Integer, DateTime, Date, Boolean, JSON,
    ForeignKey, Index, Numeric, Text, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB, ARRAY, TSVECTOR
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin


class AutocompleteSuggestion(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Autocomplete suggestion model.
    
    Stores suggestions for real-time search autocomplete with
    rich metadata, scoring, and personalization support.
    
    Maps to: search/search_autocomplete.py Suggestion
    """
    __tablename__ = "autocomplete_suggestions"
    
    # ===== Suggestion Content =====
    value: str = Column(String(255), nullable=False, index=True, comment="Value to insert into search")
    label: str = Column(String(255), nullable=False, comment="Display label (formatted)")
    normalized_value: str = Column(String(255), nullable=False, index=True)
    
    # ===== Suggestion Type =====
    suggestion_type: str = Column(String(50), nullable=False, index=True)  # hostel, city, area, landmark, amenity, popular_search
    
    # ===== Scoring and Ranking =====
    score: Decimal = Column(Numeric(precision=10, scale=4), nullable=False, default=0, index=True)
    base_score: Decimal = Column(Numeric(precision=10, scale=4), nullable=False, default=0)
    popularity_boost: Decimal = Column(Numeric(precision=10, scale=4), nullable=False, default=0)
    recency_boost: Decimal = Column(Numeric(precision=10, scale=4), nullable=False, default=0)
    
    # ===== Result Information =====
    result_count: Optional[int] = Column(Integer, nullable=True, comment="Estimated results for this suggestion")
    last_result_count: Optional[int] = Column(Integer, nullable=True)
    result_count_updated_at: Optional[datetime] = Column(DateTime, nullable=True)
    
    # ===== Display Options =====
    icon: Optional[str] = Column(String(100), nullable=True, comment="Icon identifier for UI")
    thumbnail_url: Optional[str] = Column(Text, nullable=True)
    highlighted_label: Optional[str] = Column(Text, nullable=True, comment="HTML highlighted label")
    
    # ===== Additional Metadata =====
    metadata: Optional[dict] = Column(JSONB, nullable=True)
    
    # For hostel suggestions
    hostel_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    # For location suggestions
    city: Optional[str] = Column(String(100), nullable=True, index=True)
    state: Optional[str] = Column(String(100), nullable=True)
    country: Optional[str] = Column(String(100), nullable=True, default="India")
    latitude: Optional[Decimal] = Column(Numeric(precision=10, scale=8), nullable=True)
    longitude: Optional[Decimal] = Column(Numeric(precision=11, scale=8), nullable=True)
    
    # ===== Status and Lifecycle =====
    is_active: bool = Column(Boolean, nullable=False, default=True, index=True)
    is_featured: bool = Column(Boolean, nullable=False, default=False, index=True)
    is_verified: bool = Column(Boolean, nullable=False, default=False)
    
    # ===== Usage Tracking =====
    usage_count: int = Column(Integer, nullable=False, default=0)
    last_used: Optional[datetime] = Column(DateTime, nullable=True)
    selection_count: int = Column(Integer, nullable=False, default=0, comment="How many times users selected this")
    impression_count: int = Column(Integer, nullable=False, default=0, comment="How many times shown")
    
    # ===== Quality Metrics =====
    selection_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    avg_position_shown: Optional[Decimal] = Column(Numeric(precision=5, scale=2), nullable=True)
    quality_score: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Source Tracking =====
    source: str = Column(String(50), nullable=False, index=True)  # manual, auto_generated, user_search, ai_generated
    source_data: Optional[dict] = Column(JSONB, nullable=True)
    created_by: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # ===== Full-text Search =====
    search_vector: Optional[TSVECTOR] = Column(TSVECTOR, nullable=True)
    
    # ===== Relationships =====
    hostel = relationship("Hostel", foreign_keys=[hostel_id])
    creator = relationship("AdminUser", foreign_keys=[created_by])
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_autocomplete_value_type', 'normalized_value', 'suggestion_type'),
        Index('idx_autocomplete_score', 'score', 'is_active'),
        Index('idx_autocomplete_active', 'is_active', 'is_featured'),
        Index('idx_autocomplete_location', 'city', 'state'),
        Index('idx_autocomplete_usage', 'usage_count', 'selection_count'),
        Index('idx_autocomplete_quality', 'quality_score', 'selection_rate'),
        Index('idx_autocomplete_hostel', 'hostel_id', 'is_active'),
        
        # Full-text search index
        Index('idx_autocomplete_search_vector', 'search_vector', postgresql_using='gin'),
        
        # GIN indexes
        Index('idx_autocomplete_metadata_gin', 'metadata', postgresql_using='gin'),
        
        # Unique constraint for active suggestions
        UniqueConstraint('normalized_value', 'suggestion_type', name='uq_autocomplete_value_type'),
        
        CheckConstraint('score >= 0', name='check_score_positive'),
        CheckConstraint('usage_count >= 0', name='check_usage_count_positive'),
        CheckConstraint('selection_rate >= 0 AND selection_rate <= 100', name='check_selection_rate_range'),
        
        {'comment': 'Autocomplete suggestions with rich metadata and scoring'}
    )
    
    def __repr__(self):
        return f"<AutocompleteSuggestion(value='{self.value}', type='{self.suggestion_type}', score={self.score})>"


class AutocompleteQueryLog(BaseModel, UUIDMixin, TimestampMixin):
    """
    Autocomplete query logging model.
    
    Tracks all autocomplete requests for performance monitoring,
    usage analysis, and suggestion optimization.
    
    Maps to: search/search_autocomplete.py AutocompleteRequest
    """
    __tablename__ = "autocomplete_query_logs"
    
    # ===== Query Information =====
    prefix: str = Column(String(255), nullable=False, index=True)
    normalized_prefix: str = Column(String(255), nullable=False, index=True)
    prefix_length: int = Column(Integer, nullable=False)
    
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
    
    session_id: Optional[str] = Column(String(255), nullable=True, index=True)
    
    # ===== Request Parameters =====
    suggestion_type_filter: Optional[str] = Column(String(50), nullable=True)
    include_types: Optional[list] = Column(ARRAY(String), nullable=True)
    exclude_types: Optional[list] = Column(ARRAY(String), nullable=True)
    limit: int = Column(Integer, nullable=False, default=10)
    
    # ===== Location Context =====
    user_latitude: Optional[Decimal] = Column(Numeric(precision=10, scale=8), nullable=True)
    user_longitude: Optional[Decimal] = Column(Numeric(precision=11, scale=8), nullable=True)
    user_city: Optional[str] = Column(String(100), nullable=True)
    
    # ===== Response Metrics =====
    suggestions_returned: int = Column(Integer, nullable=False, default=0)
    execution_time_ms: int = Column(Integer, nullable=False)
    cache_hit: bool = Column(Boolean, nullable=False, default=False)
    cache_key: Optional[str] = Column(String(255), nullable=True)
    
    # ===== User Interaction =====
    selected_suggestion: Optional[str] = Column(String(255), nullable=True)
    selected_suggestion_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("autocomplete_suggestions.id", ondelete="SET NULL"),
        nullable=True
    )
    selected_position: Optional[int] = Column(Integer, nullable=True)
    time_to_selection_ms: Optional[int] = Column(Integer, nullable=True)
    
    # Did user convert to full search?
    resulted_in_search: bool = Column(Boolean, nullable=False, default=False)
    search_query_id: Optional[UUID] = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("search_query_logs.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # ===== Source =====
    source: str = Column(String(50), nullable=False, default="web")
    platform: Optional[str] = Column(String(50), nullable=True)
    
    # ===== Device Information =====
    device_type: Optional[str] = Column(String(50), nullable=True)
    
    # ===== Relationships =====
    user = relationship("User", foreign_keys=[user_id])
    visitor = relationship("Visitor", foreign_keys=[visitor_id])
    selected_suggestion_obj = relationship("AutocompleteSuggestion", foreign_keys=[selected_suggestion_id])
    search_query = relationship("SearchQueryLog", foreign_keys=[search_query_id])
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_autocomplete_query_prefix', 'normalized_prefix', 'prefix_length'),
        Index('idx_autocomplete_query_user', 'user_id', 'created_at'),
        Index('idx_autocomplete_query_session', 'session_id', 'created_at'),
        Index('idx_autocomplete_query_metrics', 'suggestions_returned', 'execution_time_ms'),
        Index('idx_autocomplete_query_selection', 'selected_suggestion_id', 'selected_position'),
        Index('idx_autocomplete_query_conversion', 'resulted_in_search'),
        
        CheckConstraint('prefix_length >= 0', name='check_prefix_length_positive'),
        CheckConstraint('suggestions_returned >= 0', name='check_suggestions_returned_positive'),
        CheckConstraint('execution_time_ms >= 0', name='check_execution_time_positive'),
        
        {'comment': 'Autocomplete query logging for analytics and optimization'}
    )
    
    def __repr__(self):
        return f"<AutocompleteQueryLog(prefix='{self.prefix}', suggestions={self.suggestions_returned})>"


class SuggestionSource(BaseModel, UUIDMixin, TimestampMixin):
    """
    Suggestion source configuration model.
    
    Manages different sources for autocomplete suggestions
    with priority and sync configuration.
    
    Maps to: Multiple suggestion sources in autocomplete system
    """
    __tablename__ = "suggestion_sources"
    
    # ===== Source Information =====
    name: str = Column(String(100), nullable=False, unique=True, index=True)
    source_type: str = Column(String(50), nullable=False, index=True)  # database, api, file, manual, ai_generated
    description: Optional[str] = Column(Text, nullable=True)
    
    # ===== Configuration =====
    config: Optional[dict] = Column(JSONB, nullable=True, comment="Source-specific configuration")
    priority: int = Column(Integer, nullable=False, default=0, index=True)
    weight: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=1.0)
    
    # ===== Status =====
    is_active: bool = Column(Boolean, nullable=False, default=True, index=True)
    is_realtime: bool = Column(Boolean, nullable=False, default=False)
    
    # ===== Sync Configuration =====
    last_sync: Optional[datetime] = Column(DateTime, nullable=True)
    next_sync: Optional[datetime] = Column(DateTime, nullable=True, index=True)
    sync_frequency_minutes: Optional[int] = Column(Integer, nullable=True)
    auto_sync: bool = Column(Boolean, nullable=False, default=False)
    
    # ===== Metrics =====
    total_suggestions: int = Column(Integer, nullable=False, default=0)
    active_suggestions: int = Column(Integer, nullable=False, default=0)
    failed_suggestions: int = Column(Integer, nullable=False, default=0)
    
    # ===== Performance =====
    avg_sync_time_seconds: Optional[Decimal] = Column(Numeric(precision=10, scale=2), nullable=True)
    last_sync_duration_seconds: Optional[int] = Column(Integer, nullable=True)
    last_sync_status: Optional[str] = Column(String(50), nullable=True)  # success, failed, partial
    last_sync_error: Optional[str] = Column(Text, nullable=True)
    
    # ===== Filters =====
    suggestion_types: Optional[list] = Column(ARRAY(String), nullable=True, comment="Which suggestion types this source provides")
    target_languages: Optional[list] = Column(ARRAY(String), nullable=True)
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_suggestion_source_type', 'source_type', 'is_active'),
        Index('idx_suggestion_source_priority', 'priority', 'is_active'),
        Index('idx_suggestion_source_sync', 'next_sync', 'auto_sync'),
        
        # GIN index
        Index('idx_suggestion_source_config_gin', 'config', postgresql_using='gin'),
        
        CheckConstraint('priority >= 0', name='check_priority_positive'),
        CheckConstraint('weight > 0', name='check_weight_positive'),
        
        {'comment': 'Suggestion source configuration and management'}
    )
    
    def __repr__(self):
        return f"<SuggestionSource(name='{self.name}', type='{self.source_type}', active={self.is_active})>"


class PopularSearchSuggestion(BaseModel, UUIDMixin, TimestampMixin):
    """
    Popular search suggestions model.
    
    Stores popular searches for showing when no autocomplete matches
    or as default suggestions.
    
    Maps to: Popular searches shown in autocomplete
    """
    __tablename__ = "popular_search_suggestions"
    
    # ===== Search Term =====
    term: str = Column(String(255), nullable=False, index=True)
    normalized_term: str = Column(String(255), nullable=False, index=True)
    
    # ===== Ranking =====
    rank: int = Column(Integer, nullable=False, index=True)
    global_rank: int = Column(Integer, nullable=False, default=0)
    
    # ===== Popularity Metrics =====
    search_count: int = Column(Integer, nullable=False, default=0)
    unique_users: int = Column(Integer, nullable=False, default=0)
    trend_score: Decimal = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    
    # ===== Context =====
    city: Optional[str] = Column(String(100), nullable=True, index=True)
    state: Optional[str] = Column(String(100), nullable=True)
    hostel_type: Optional[str] = Column(String(50), nullable=True, index=True)
    category: Optional[str] = Column(String(100), nullable=True, index=True)
    
    # ===== Display =====
    display_text: str = Column(String(255), nullable=False)
    description: Optional[str] = Column(Text, nullable=True)
    icon: Optional[str] = Column(String(100), nullable=True)
    
    # ===== Result Information =====
    result_count: int = Column(Integer, nullable=False, default=0)
    avg_click_through_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Status =====
    is_active: bool = Column(Boolean, nullable=False, default=True, index=True)
    is_featured: bool = Column(Boolean, nullable=False, default=False)
    is_seasonal: bool = Column(Boolean, nullable=False, default=False)
    
    # ===== Period =====
    period_start: date = Column(Date, nullable=False, index=True)
    period_end: date = Column(Date, nullable=False, index=True)
    period_type: str = Column(String(20), nullable=False, default="weekly")
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_popular_suggestion_term', 'normalized_term', 'is_active'),
        Index('idx_popular_suggestion_rank', 'rank', 'period_start'),
        Index('idx_popular_suggestion_count', 'search_count', 'trend_score'),
        Index('idx_popular_suggestion_context', 'city', 'hostel_type', 'category'),
        Index('idx_popular_suggestion_period', 'period_start', 'period_end', 'period_type'),
        
        CheckConstraint('rank >= 1', name='check_rank_positive'),
        CheckConstraint('search_count >= 0', name='check_search_count_positive'),
        
        {'comment': 'Popular search suggestions for autocomplete fallback'}
    )
    
    def __repr__(self):
        return f"<PopularSearchSuggestion(rank={self.rank}, term='{self.term}', count={self.search_count})>"


class SuggestionPerformance(BaseModel, UUIDMixin, TimestampMixin):
    """
    Suggestion performance tracking model.
    
    Tracks detailed performance metrics for autocomplete suggestions
    to optimize ranking and relevance.
    """
    __tablename__ = "suggestion_performance"
    
    # ===== Reference =====
    suggestion_id: UUID = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("autocomplete_suggestions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # ===== Period =====
    metric_date: date = Column(Date, nullable=False, index=True)
    period_type: str = Column(String(20), nullable=False, default="daily")
    
    # ===== Usage Metrics =====
    impression_count: int = Column(Integer, nullable=False, default=0)
    selection_count: int = Column(Integer, nullable=False, default=0)
    selection_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Position Metrics =====
    avg_position_shown: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    avg_position_selected: Optional[Decimal] = Column(Numeric(precision=5, scale=2), nullable=True)
    
    # ===== Context =====
    unique_users: int = Column(Integer, nullable=False, default=0)
    unique_sessions: int = Column(Integer, nullable=False, default=0)
    
    # ===== Conversion =====
    resulted_in_searches: int = Column(Integer, nullable=False, default=0)
    search_conversion_rate: Decimal = Column(Numeric(precision=5, scale=2), nullable=False, default=0)
    
    # ===== Relationships =====
    suggestion = relationship("AutocompleteSuggestion", backref="performance_metrics")
    
    # ===== Table Configuration =====
    __table_args__ = (
        Index('idx_suggestion_perf_suggestion_date', 'suggestion_id', 'metric_date'),
        Index('idx_suggestion_perf_period', 'metric_date', 'period_type'),
        Index('idx_suggestion_perf_metrics', 'selection_rate', 'search_conversion_rate'),
        
        UniqueConstraint('suggestion_id', 'metric_date', 'period_type', name='uq_suggestion_perf_date'),
        
        {'comment': 'Suggestion performance metrics tracking'}
    )
    
    def __repr__(self):
        return f"<SuggestionPerformance(suggestion_id={self.suggestion_id}, date={self.metric_date})>"