"""
Search Analytics Service

Returns analytics/insights over search behavior and performance.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.search import SearchAnalyticsRequest, SearchAnalytics
from app.repositories.search import SearchAnalyticsRepository
from app.core1.exceptions import ValidationException
from app.core1.logging import logger, LoggingContext


class SearchAnalyticsService:
    """
    High-level service for search analytics.

    Responsibilities:
    - Generate analytics for a given period (SearchAnalyticsRequest)
    - Wrap repository results into SearchAnalytics schema
    - Validate analytics requests
    - Handle edge cases and missing data
    """

    __slots__ = ('analytics_repo', 'max_date_range_days')

    def __init__(
        self,
        analytics_repo: SearchAnalyticsRepository,
        max_date_range_days: int = 365,
    ) -> None:
        """
        Initialize SearchAnalyticsService.

        Args:
            analytics_repo: Repository for search analytics data
            max_date_range_days: Maximum allowed date range in days
        """
        self.analytics_repo = analytics_repo
        self.max_date_range_days = max_date_range_days

    def get_analytics(
        self,
        db: Session,
        request: SearchAnalyticsRequest,
    ) -> SearchAnalytics:
        """
        Retrieve analytics for the given request.

        Delegates heavy work to SearchAnalyticsRepository.

        Args:
            db: SQLAlchemy session
            request: SearchAnalyticsRequest with date range and limits

        Returns:
            SearchAnalytics with aggregated metrics

        Raises:
            ValidationException: If request validation fails or no data available
        """
        self._validate_request(request)

        with LoggingContext(
            action="get_analytics",
            start_date=str(request.start_date),
            end_date=str(request.end_date),
        ):
            try:
                data = self._fetch_analytics_data(db, request)
                
                if not data:
                    logger.warning(
                        "No search analytics data available",
                        extra={
                            "start_date": str(request.start_date),
                            "end_date": str(request.end_date),
                        }
                    )
                    raise ValidationException("No search analytics data available for the specified period")

                return SearchAnalytics.model_validate(data)

            except ValidationException:
                raise
            except Exception as e:
                logger.error(
                    f"Failed to fetch analytics: {str(e)}",
                    extra={
                        "start_date": str(request.start_date),
                        "end_date": str(request.end_date),
                    }
                )
                raise ValidationException(f"Failed to retrieve analytics: {str(e)}")

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _fetch_analytics_data(
        self,
        db: Session,
        request: SearchAnalyticsRequest,
    ) -> Optional[dict]:
        """
        Fetch analytics data from repository.

        Args:
            db: SQLAlchemy session
            request: SearchAnalyticsRequest

        Returns:
            Dictionary containing analytics data or None
        """
        return self.analytics_repo.get_analytics(
            db=db,
            start_date=request.start_date,
            end_date=request.end_date,
            top_terms_limit=request.top_terms_limit,
            trending_terms_limit=request.trending_terms_limit,
            zero_result_terms_limit=request.zero_result_terms_limit,
            min_searches_threshold=request.min_searches_threshold,
        )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_request(self, request: SearchAnalyticsRequest) -> None:
        """
        Validate analytics request.

        Args:
            request: SearchAnalyticsRequest to validate

        Raises:
            ValidationException: If validation fails
        """
        # Validate date range
        if request.start_date > request.end_date:
            raise ValidationException("Start date cannot be after end date")
        
        # Validate date range is not too large
        date_range = (request.end_date - request.start_date).days
        if date_range > self.max_date_range_days:
            raise ValidationException(
                f"Date range cannot exceed {self.max_date_range_days} days"
            )
        
        # Validate dates are not in the future
        today = datetime.now().date()
        if request.start_date > today:
            raise ValidationException("Start date cannot be in the future")
        
        if request.end_date > today:
            raise ValidationException("End date cannot be in the future")
        
        # Validate limits
        if request.top_terms_limit is not None and request.top_terms_limit <= 0:
            raise ValidationException("Top terms limit must be positive")
        
        if request.top_terms_limit is not None and request.top_terms_limit > 1000:
            raise ValidationException("Top terms limit cannot exceed 1000")
        
        if request.trending_terms_limit is not None and request.trending_terms_limit <= 0:
            raise ValidationException("Trending terms limit must be positive")
        
        if request.trending_terms_limit is not None and request.trending_terms_limit > 1000:
            raise ValidationException("Trending terms limit cannot exceed 1000")
        
        if request.zero_result_terms_limit is not None and request.zero_result_terms_limit <= 0:
            raise ValidationException("Zero result terms limit must be positive")
        
        if request.zero_result_terms_limit is not None and request.zero_result_terms_limit > 1000:
            raise ValidationException("Zero result terms limit cannot exceed 1000")
        
        if request.min_searches_threshold is not None and request.min_searches_threshold < 0:
            raise ValidationException("Min searches threshold cannot be negative")