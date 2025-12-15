# --- File: app/schemas/search/search_analytics.py ---
"""
Search analytics and insights schemas.

Provides comprehensive analytics on search behavior, popular queries,
and zero-result searches for optimization.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator, model_validator, computed_field, ConfigDict

from app.schemas.common.base import BaseSchema
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "SearchTermStats",
    "SearchMetrics",
    "PopularSearchTerm",
    "TrendingSearch",
    "ZeroResultTerm",
    "SearchAnalyticsRequest",
    "SearchAnalytics",
]


class SearchTermStats(BaseSchema):
    """
    Detailed statistics for a single search term.

    Tracks usage patterns and result quality for search optimization.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    term: str = Field(
        ...,
        description="Search term or query",
    )
    search_count: int = Field(
        ...,
        ge=0,
        description="Number of times this term was searched",
    )
    unique_users: int = Field(
        default=0,
        ge=0,
        description="Number of unique users who searched this term",
    )

    # Result quality metrics
    avg_results: float = Field(
        ...,
        ge=0,
        description="Average number of results returned",
    )
    zero_result_count: int = Field(
        ...,
        ge=0,
        description="Number of searches with zero results",
    )
    zero_result_rate: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Percentage of searches with zero results",
    )

    # Engagement metrics
    avg_click_position: Optional[float] = Field(
        default=None,
        ge=0,
        description="Average position of clicked results (1-based)",
    )
    click_through_rate: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Percentage of searches that resulted in clicks",
    )

    # Temporal data
    first_searched_at: datetime = Field(
        ...,
        description="When this term was first searched",
    )
    last_searched_at: datetime = Field(
        ...,
        description="Most recent search timestamp",
    )

    # Trend indicators
    trend_direction: Optional[str] = Field(
        default=None,
        pattern=r"^(rising|falling|stable)$",
        description="Search trend direction",
    )
    growth_rate: Optional[float] = Field(
        default=None,
        description="Percentage change in search volume (vs previous period)",
    )


class SearchMetrics(BaseSchema):
    """
    Aggregated search performance metrics.

    Provides overview of search system health and performance.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Volume metrics
    total_searches: int = Field(
        ...,
        ge=0,
        description="Total number of searches in period",
    )
    unique_searches: int = Field(
        ...,
        ge=0,
        description="Number of unique search queries",
    )
    unique_users: int = Field(
        default=0,
        ge=0,
        description="Number of unique users who performed searches",
    )

    # Quality metrics
    avg_results_per_search: float = Field(
        ...,
        ge=0,
        description="Average number of results per search",
    )
    zero_result_searches: int = Field(
        ...,
        ge=0,
        description="Number of searches with zero results",
    )
    zero_result_rate: float = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of searches with zero results",
    )

    # Performance metrics
    avg_response_time_ms: float = Field(
        ...,
        ge=0,
        description="Average search response time in milliseconds",
    )
    p95_response_time_ms: float = Field(
        ...,
        ge=0,
        description="95th percentile response time",
    )
    p99_response_time_ms: float = Field(
        ...,
        ge=0,
        description="99th percentile response time",
    )

    # Engagement metrics
    avg_click_through_rate: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Average click-through rate across all searches",
    )
    searches_with_clicks: int = Field(
        default=0,
        ge=0,
        description="Number of searches that resulted in at least one click",
    )


class PopularSearchTerm(BaseSchema):
    """
    Popular search term with ranking.

    Used for displaying trending/popular searches to users.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    rank: int = Field(
        ...,
        ge=1,
        description="Popularity ranking (1 = most popular)",
    )
    term: str = Field(
        ...,
        description="Search term",
    )
    search_count: int = Field(
        ...,
        ge=0,
        description="Number of searches",
    )
    result_count: int = Field(
        ...,
        ge=0,
        description="Average number of results",
    )
    change_from_previous: Optional[int] = Field(
        default=None,
        description="Change in rank from previous period (+/- positions)",
    )


class TrendingSearch(BaseSchema):
    """
    Trending search term (rapidly growing in popularity).

    Identifies emerging search patterns.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    term: str = Field(
        ...,
        description="Trending search term",
    )
    current_count: int = Field(
        ...,
        ge=0,
        description="Number of searches in current period",
    )
    previous_count: int = Field(
        ...,
        ge=0,
        description="Number of searches in previous period",
    )
    growth_rate: float = Field(
        ...,
        description="Percentage growth rate",
    )
    velocity: float = Field(
        ...,
        ge=0,
        description="Trending velocity score (higher = faster growth)",
    )


class ZeroResultTerm(BaseSchema):
    """
    Search term that consistently returns zero results.

    Critical for search optimization and content gap analysis.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    term: str = Field(
        ...,
        description="Search term with zero results",
    )
    search_count: int = Field(
        ...,
        ge=1,
        description="Number of times searched (with zero results)",
    )
    unique_users: int = Field(
        ...,
        ge=0,
        description="Number of unique users affected",
    )
    first_seen: datetime = Field(
        ...,
        description="First occurrence of this zero-result search",
    )
    last_seen: datetime = Field(
        ...,
        description="Most recent occurrence",
    )
    suggested_alternatives: Optional[List[str]] = Field(
        default=None,
        description="Suggested alternative search terms",
    )


class SearchAnalyticsRequest(BaseSchema):
    """
    Request parameters for search analytics.

    Allows filtering analytics by Date range and other criteria.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Date range
    date_range: DateRangeFilter = Field(
        ...,
        description="Date range for analytics",
    )

    # Filters
    min_search_count: int = Field(
        default=1,
        ge=1,
        description="Minimum number of searches to include term",
    )
    include_zero_results: bool = Field(
        default=True,
        description="Include zero-result searches in analysis",
    )

    # Limits
    top_terms_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of top terms to return",
    )
    trending_limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of trending terms to return",
    )
    zero_result_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of zero-result terms to return",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "SearchAnalyticsRequest":
        """Validate Date range is reasonable."""
        if self.date_range.start_date and self.date_range.end_date:
            delta = self.date_range.end_date - self.date_range.start_date
            if delta.days > 365:
                raise ValueError("Date range cannot exceed 365 days")
        return self


class SearchAnalytics(BaseSchema):
    """
    Comprehensive search analytics response.

    Provides detailed insights into search behavior and performance.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Period information
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="When this analytics report was generated",
    )

    # Overall metrics
    metrics: SearchMetrics = Field(
        ...,
        description="Aggregated search metrics",
    )

    # Top searches
    top_searches: List[PopularSearchTerm] = Field(
        default_factory=list,
        description="Most popular search terms",
    )

    # Trending searches
    trending_searches: List[TrendingSearch] = Field(
        default_factory=list,
        description="Rapidly growing search terms",
    )

    # Zero-result searches
    zero_result_searches: List[ZeroResultTerm] = Field(
        default_factory=list,
        description="Searches that returned no results",
    )

    # Detailed term statistics (optional, for deep dive)
    term_statistics: Optional[List[SearchTermStats]] = Field(
        default=None,
        description="Detailed statistics for individual search terms",
    )

    # Breakdown by category
    category_breakdown: Optional[Dict[str, int]] = Field(
        default=None,
        description="Search volume by category (hostel_type, location, etc.)",
    )

    # Geographic breakdown
    geographic_breakdown: Optional[Dict[str, int]] = Field(
        default=None,
        description="Search volume by location (city/state)",
    )

    @computed_field
    @property
    def has_quality_issues(self) -> bool:
        """
        Check if there are search quality issues.

        Returns True if zero-result rate is high or response times are slow.
        """
        return (
            self.metrics.zero_result_rate > 20
            or self.metrics.p95_response_time_ms > 1000
        )

    @computed_field
    @property
    def engagement_score(self) -> float:
        """
        Calculate overall engagement score (0-100).

        Based on click-through rate and result quality.
        """
        # Weight CTR (70%) and inverse zero-result rate (30%)
        ctr_score = self.metrics.avg_click_through_rate * 0.7
        quality_score = (100 - self.metrics.zero_result_rate) * 0.3
        return min(ctr_score + quality_score, 100)