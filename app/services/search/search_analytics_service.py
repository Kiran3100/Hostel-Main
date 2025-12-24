"""
Search Analytics Service

Returns analytics/insights over search behavior and performance.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.search import SearchAnalyticsRequest, SearchAnalytics
from app.repositories.search import SearchAnalyticsRepository
from app.core.exceptions import ValidationException


class SearchAnalyticsService:
    """
    High-level service for search analytics.

    Responsibilities:
    - Generate analytics for a given period (SearchAnalyticsRequest)
    - Wrap repository results into SearchAnalytics schema
    """

    def __init__(
        self,
        analytics_repo: SearchAnalyticsRepository,
    ) -> None:
        self.analytics_repo = analytics_repo

    def get_analytics(
        self,
        db: Session,
        request: SearchAnalyticsRequest,
    ) -> SearchAnalytics:
        """
        Retrieve analytics for the given request.

        Delegates heavy work to SearchAnalyticsRepository.
        """
        data = self.analytics_repo.get_analytics(
            db=db,
            start_date=request.start_date,
            end_date=request.end_date,
            top_terms_limit=request.top_terms_limit,
            trending_terms_limit=request.trending_terms_limit,
            zero_result_terms_limit=request.zero_result_terms_limit,
            min_searches_threshold=request.min_searches_threshold,
        )
        if not data:
            raise ValidationException("No search analytics data available")

        return SearchAnalytics.model_validate(data)