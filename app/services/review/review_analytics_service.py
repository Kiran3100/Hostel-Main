# app/services/review/review_analytics_service.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import ReviewRepository
from app.repositories.core import HostelRepository
from app.schemas.common.filters import DateRangeFilter
from app.schemas.review.review_analytics import (
    ReviewAnalytics,
    RatingDistribution,
    TrendAnalysis,
    MonthlyRating,
    SentimentAnalysis,
)
from app.services.common import UnitOfWork, errors


class ReviewAnalyticsService:
    """
    Review analytics per hostel:

    - Rating distribution
    - Detailed aspect averages
    - TrendAnalysis over time
    - Simple engagement metrics (helpful votes, verification rate)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_review_repo(self, uow: UnitOfWork) -> ReviewRepository:
        return uow.get_repo(ReviewRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_hostel_review_analytics(
        self,
        hostel_id: UUID,
        period: Optional[DateRangeFilter] = None,
    ) -> ReviewAnalytics:
        """
        Build ReviewAnalytics for a hostel over optional period.
        If period is None or missing dates, considers all time.
        """
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            recs = review_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

        if not period or (not period.start_date and not period.end_date):
            start = date.min
            end = date.max
        else:
            start = period.start_date or date.min
            end = period.end_date or date.max

        # Filter by created_at date
        reviews = [
            r for r in recs
            if start <= r.created_at.date() <= end
        ]

        total = len(reviews)
        if total == 0:
            return ReviewAnalytics(
                hostel_id=hostel_id,
                hostel_name=hostel.name,
                analysis_period=period,
                generated_at=self._now(),
                total_reviews=0,
                average_rating=Decimal("0"),
                rating_distribution=RatingDistribution(
                    rating_5_count=0,
                    rating_4_count=0,
                    rating_3_count=0,
                    rating_2_count=0,
                    rating_1_count=0,
                    rating_5_percentage=Decimal("0"),
                    rating_4_percentage=Decimal("0"),
                    rating_3_percentage=Decimal("0"),
                    rating_2_percentage=Decimal("0"),
                    rating_1_percentage=Decimal("0"),
                    positive_reviews=0,
                    neutral_reviews=0,
                    negative_reviews=0,
                    positive_percentage=Decimal("0"),
                    neutral_percentage=Decimal("0"),
                    negative_percentage=Decimal("0"),
                ),
                detailed_ratings_average={},
                rating_trend=TrendAnalysis(
                    trend_direction="stable",
                    trend_percentage=None,
                    monthly_ratings=[],
                    last_30_days_rating=Decimal("0"),
                    last_90_days_rating=Decimal("0"),
                    all_time_rating=Decimal("0"),
                ),
                sentiment_analysis=None,
                verified_reviews_count=0,
                verification_rate=Decimal("0"),
                average_helpful_votes=Decimal("0"),
                response_rate=Decimal("0"),
            )

        # Overall average
        total_rating = sum((r.overall_rating for r in reviews), Decimal("0"))
        avg_rating = total_rating / Decimal(str(total))

        # Rating distribution
        rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in reviews:
            val = int(round(float(r.overall_rating)))
            val = min(5, max(1, val))
            rating_counts[val] += 1

        def _pct(num: int, denom: int) -> Decimal:
            return (
                Decimal(str(num)) / Decimal(str(denom)) * Decimal("100")
                if denom > 0
                else Decimal("0")
            )

        dist = RatingDistribution(
            rating_5_count=rating_counts[5],
            rating_4_count=rating_counts[4],
            rating_3_count=rating_counts[3],
            rating_2_count=rating_counts[2],
            rating_1_count=rating_counts[1],
            rating_5_percentage=_pct(rating_counts[5], total),
            rating_4_percentage=_pct(rating_counts[4], total),
            rating_3_percentage=_pct(rating_counts[3], total),
            rating_2_percentage=_pct(rating_counts[2], total),
            rating_1_percentage=_pct(rating_counts[1], total),
            positive_reviews=rating_counts[5] + rating_counts[4],
            neutral_reviews=rating_counts[3],
            negative_reviews=rating_counts[1] + rating_counts[2],
            positive_percentage=_pct(rating_counts[5] + rating_counts[4], total),
            neutral_percentage=_pct(rating_counts[3], total),
            negative_percentage=_pct(rating_counts[1] + rating_counts[2], total),
        )

        # Detailed aspect averages
        aspects = [
            "cleanliness_rating",
            "food_quality_rating",
            "staff_behavior_rating",
            "security_rating",
            "value_for_money_rating",
            "amenities_rating",
        ]
        detailed: Dict[str, Decimal] = {}
        for field in aspects:
            vals = [
                Decimal(str(getattr(r, field)))
                for r in reviews
                if getattr(r, field) is not None
            ]
            if vals:
                detailed[field] = sum(vals) / Decimal(str(len(vals)))

        # Trend: monthly
        monthly_map: Dict[str, Dict[str, object]] = {}
        for r in reviews:
            key = r.created_at.strftime("%Y-%m")
            bucket = monthly_map.setdefault(
                key, {"sum": Decimal("0"), "count": 0}
            )
            bucket["sum"] = bucket["sum"] + r.overall_rating  # type: ignore[operator]
            bucket["count"] = bucket["count"] + 1  # type: ignore[operator]

        monthly_ratings: List[MonthlyRating] = []
        for month, vals in sorted(monthly_map.items()):
            avg_m = (
                vals["sum"] / Decimal(str(vals["count"]))  # type: ignore[index]
                if vals["count"]  # type: ignore[index]
                else Decimal("0")
            )
            monthly_ratings.append(
                MonthlyRating(
                    month=month,
                    average_rating=avg_m,
                    review_count=vals["count"],  # type: ignore[index]
                )
            )

        # Trend direction based on first vs last month
        trend_direction = "stable"
        trend_pct: Optional[Decimal] = None
        if len(monthly_ratings) >= 2:
            first = monthly_ratings[0].average_rating
            last = monthly_ratings[-1].average_rating
            if first > 0:
                change = (last - first) / first * Decimal("100")
                trend_pct = change
                if change > Decimal("5"):
                    trend_direction = "improving"
                elif change < Decimal("-5"):
                    trend_direction = "declining"
                else:
                    trend_direction = "stable"

        # Last 30/90 days vs all-time
        today = date.today()
        last_30 = [
            r for r in reviews if r.created_at.date() >= today - timedelta(days=30)
        ]
        last_90 = [
            r for r in reviews if r.created_at.date() >= today - timedelta(days=90)
        ]
        def _avg(lst) -> Decimal:
            if not lst:
                return Decimal("0")
            s = sum((x.overall_rating for x in lst), Decimal("0"))
            return s / Decimal(str(len(lst)))

        trend = TrendAnalysis(
            trend_direction=trend_direction,
            trend_percentage=trend_pct,
            monthly_ratings=monthly_ratings,
            last_30_days_rating=_avg(last_30),
            last_90_days_rating=_avg(last_90),
            all_time_rating=avg_rating,
        )

        # Sentiment placeholder
        sentiment: Optional[SentimentAnalysis] = None

        # Verification & engagement
        verified_count = sum(1 for r in reviews if r.is_verified_stay)
        verification_rate = _pct(verified_count, total)

        avg_helpful = (
            Decimal(
                str(sum(int(r.helpful_count) for r in reviews))
            )
            / Decimal(str(total))
        )

        # Response rate not tracked here -> 0
        response_rate = Decimal("0")

        return ReviewAnalytics(
            hostel_id=hostel_id,
            hostel_name=hostel.name,
            analysis_period=period,
            generated_at=self._now(),
            total_reviews=total,
            average_rating=avg_rating,
            rating_distribution=dist,
            detailed_ratings_average=detailed,
            rating_trend=trend,
            sentiment_analysis=sentiment,
            verified_reviews_count=verified_count,
            verification_rate=verification_rate,
            average_helpful_votes=avg_helpful,
            response_rate=response_rate,
        )