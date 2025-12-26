"""
Review Analytics Service

Enhanced analytics with comprehensive metrics, caching,
and performance optimization.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.review import ReviewAnalyticsRepository
from app.schemas.common import DateRangeFilter
from app.schemas.review import (
    ReviewAnalytics,
    CompetitorComparison,
)
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    DatabaseException,
)
from app.core.cache import cache_result
from app.core.metrics import track_performance

logger = logging.getLogger(__name__)


class ReviewAnalyticsService:
    """
    High-level service for review analytics and insights.

    Features:
    - Comprehensive hostel analytics
    - Competitor comparison
    - Trend analysis
    - Performance metrics with caching
    """

    # Default analytics period
    DEFAULT_PERIOD_DAYS = 30
    
    # Maximum period for analytics
    MAX_PERIOD_DAYS = 365

    def __init__(self, analytics_repo: ReviewAnalyticsRepository) -> None:
        """
        Initialize ReviewAnalyticsService.

        Args:
            analytics_repo: Repository for analytics operations

        Raises:
            ValueError: If repository is None
        """
        if not analytics_repo:
            raise ValueError("AnalyticsRepository cannot be None")

        self.analytics_repo = analytics_repo
        logger.info("ReviewAnalyticsService initialized")

    # -------------------------------------------------------------------------
    # Analytics retrieval
    # -------------------------------------------------------------------------

    @track_performance("analytics.get_hostel_analytics")
    @cache_result(ttl=600, key_prefix="hostel_analytics")
    def get_analytics_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        period: Optional[DateRangeFilter] = None,
    ) -> ReviewAnalytics:
        """
        Get comprehensive analytics summary for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            period: Optional date range filter

        Returns:
            ReviewAnalytics object with metrics

        Raises:
            ValidationException: If period is invalid
            NotFoundException: If no data available
            DatabaseException: If database error occurs
        """
        try:
            # Validate and normalize period
            start_date, end_date = self._validate_period(period)

            logger.info(
                f"Fetching analytics for hostel {hostel_id}: "
                f"{start_date} to {end_date}"
            )

            data = self.analytics_repo.get_hostel_analytics(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )

            if not data:
                logger.warning(
                    f"No analytics data for hostel {hostel_id} "
                    f"in period {start_date} to {end_date}"
                )
                raise NotFoundException(
                    "No analytics available for the specified period"
                )

            analytics = ReviewAnalytics.model_validate(data)

            logger.info(
                f"Analytics retrieved: {analytics.total_reviews} reviews, "
                f"avg rating {analytics.average_rating:.2f}"
            )

            return analytics

        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching analytics: {str(e)}")
            raise DatabaseException("Failed to fetch analytics") from e

    @track_performance("analytics.get_competitor_comparison")
    @cache_result(ttl=1800, key_prefix="competitor_comparison")
    def get_competitor_comparison(
        self,
        db: Session,
        hostel_id: UUID,
        period: Optional[DateRangeFilter] = None,
        competitor_ids: Optional[List[UUID]] = None,
    ) -> CompetitorComparison:
        """
        Get competitor comparison data for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            period: Optional date range filter
            competitor_ids: Optional list of specific competitor IDs

        Returns:
            CompetitorComparison object

        Raises:
            ValidationException: If period is invalid
            NotFoundException: If no comparison data available
            DatabaseException: If database error occurs
        """
        try:
            # Validate and normalize period
            start_date, end_date = self._validate_period(period)

            logger.info(
                f"Fetching competitor comparison for hostel {hostel_id}: "
                f"{start_date} to {end_date}"
            )

            data = self.analytics_repo.get_competitor_comparison(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
                competitor_ids=competitor_ids,
            )

            if not data:
                logger.warning(
                    f"No competitor data for hostel {hostel_id} "
                    f"in period {start_date} to {end_date}"
                )
                raise NotFoundException(
                    "No competitor comparison data available for the specified period"
                )

            comparison = CompetitorComparison.model_validate(data)

            logger.info(
                f"Competitor comparison retrieved: "
                f"{len(comparison.competitors)} competitors"
            )

            return comparison

        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching competitor comparison: {str(e)}")
            raise DatabaseException("Failed to fetch competitor comparison") from e

    @track_performance("analytics.get_trends")
    @cache_result(ttl=900, key_prefix="analytics_trends")
    def get_trends(
        self,
        db: Session,
        hostel_id: UUID,
        period: Optional[DateRangeFilter] = None,
        granularity: str = "daily",
    ) -> Dict[str, Any]:
        """
        Get trend data for hostel analytics.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            period: Optional date range filter
            granularity: Trend granularity ('daily', 'weekly', 'monthly')

        Returns:
            Dictionary with trend data

        Raises:
            ValidationException: If parameters are invalid
            DatabaseException: If database error occurs
        """
        try:
            # Validate granularity
            valid_granularities = {'daily', 'weekly', 'monthly'}
            if granularity not in valid_granularities:
                raise ValidationException(
                    f"Invalid granularity. Must be one of: {', '.join(valid_granularities)}"
                )

            # Validate and normalize period
            start_date, end_date = self._validate_period(period)

            logger.info(
                f"Fetching trends for hostel {hostel_id}: "
                f"granularity={granularity}, {start_date} to {end_date}"
            )

            trends = self.analytics_repo.get_trends(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
            )

            logger.info(f"Trends retrieved: {len(trends.get('data_points', []))} points")

            return trends

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching trends: {str(e)}")
            raise DatabaseException("Failed to fetch trends") from e

    @track_performance("analytics.get_sentiment_analysis")
    @cache_result(ttl=1200, key_prefix="sentiment_analysis")
    def get_sentiment_analysis(
        self,
        db: Session,
        hostel_id: UUID,
        period: Optional[DateRangeFilter] = None,
    ) -> Dict[str, Any]:
        """
        Get sentiment analysis for reviews.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            period: Optional date range filter

        Returns:
            Dictionary with sentiment metrics

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            # Validate and normalize period
            start_date, end_date = self._validate_period(period)

            logger.info(
                f"Fetching sentiment analysis for hostel {hostel_id}: "
                f"{start_date} to {end_date}"
            )

            sentiment = self.analytics_repo.get_sentiment_analysis(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )

            logger.info(
                f"Sentiment analysis retrieved: "
                f"positive={sentiment.get('positive_percentage', 0):.1f}%"
            )

            return sentiment

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching sentiment: {str(e)}")
            raise DatabaseException("Failed to fetch sentiment analysis") from e

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_period(
        self,
        period: Optional[DateRangeFilter],
    ) -> tuple[datetime, datetime]:
        """
        Validate and normalize date period.

        Args:
            period: Optional DateRangeFilter

        Returns:
            Tuple of (start_date, end_date)

        Raises:
            ValidationException: If period is invalid
        """
        if period:
            start_date = period.start_date
            end_date = period.end_date
        else:
            # Default to last 30 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=self.DEFAULT_PERIOD_DAYS)

        # Validate dates
        if start_date > end_date:
            raise ValidationException("Start date must be before end date")

        # Check max period
        period_days = (end_date - start_date).days
        if period_days > self.MAX_PERIOD_DAYS:
            raise ValidationException(
                f"Maximum period is {self.MAX_PERIOD_DAYS} days"
            )

        return start_date, end_date