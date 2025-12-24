"""
Review Analytics Service

Provides analytics and insights about reviews for a hostel.
"""

from __future__ import annotations

from uuid import UUID
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.review import ReviewAnalyticsRepository
from app.schemas.common import DateRangeFilter
from app.schemas.review import (
    ReviewAnalytics,
    CompetitorComparison,
)
from app.core.exceptions import ValidationException


class ReviewAnalyticsService:
    """
    High-level service for review analytics.

    Responsibilities:
    - Get analytic summary for a hostel
    - Get competitor comparison for a hostel
    """

    def __init__(self, analytics_repo: ReviewAnalyticsRepository) -> None:
        self.analytics_repo = analytics_repo

    def get_analytics_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> ReviewAnalytics:
        data = self.analytics_repo.get_hostel_analytics(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No analytics available for given period")
        return ReviewAnalytics.model_validate(data)

    def get_competitor_comparison(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> CompetitorComparison:
        data = self.analytics_repo.get_competitor_comparison(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No competitor comparison data available")
        return CompetitorComparison.model_validate(data)