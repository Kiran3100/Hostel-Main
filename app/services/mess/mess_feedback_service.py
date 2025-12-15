# app/services/mess/mess_feedback_service.py
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import MessMenuRepository
from app.repositories.core import HostelRepository, StudentRepository
from app.schemas.common.enums import MealType
from app.schemas.common.filters import DateRangeFilter
from app.schemas.mess.menu_feedback import (
    FeedbackRequest,
    FeedbackResponse,
    RatingsSummary,
    QualityMetrics,
    ItemRating,
    FeedbackAnalysis,
)
from app.services.common import UnitOfWork, errors


class MessFeedbackStore(Protocol):
    """
    Abstract storage for mess menu feedback.

    Implementations can use a dedicated DB table, Redis, or another store.

    Expected record shape (example):

        {
            "menu_id": UUID,
            "hostel_id": UUID,
            "menu_date": date,
            "student_id": UUID,
            "student_name": str,
            "meal_type": "BREAKFAST" | "LUNCH" | ...,
            "rating": int,
            "comments": str | None,
            "taste_rating": int | None,
            "quantity_rating": int | None,
            "quality_rating": int | None,
            "hygiene_rating": int | None,
            "submitted_at": datetime,
        }
    """

    def save_feedback(self, record: dict) -> None: ...
    def list_feedback_for_menu(self, menu_id: UUID) -> List[dict]: ...
    def list_feedback_for_hostel(
        self,
        hostel_id: UUID,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[dict]: ...


class MessFeedbackService:
    """
    Mess menu feedback service:

    - Submit feedback for a menu/meal
    - Compute RatingsSummary per menu
    - Compute QualityMetrics / FeedbackAnalysis per hostel & period
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: MessFeedbackStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_menu_repo(self, uow: UnitOfWork) -> MessMenuRepository:
        return uow.get_repo(MessMenuRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Submit feedback
    # ------------------------------------------------------------------ #
    def submit_feedback(self, data: FeedbackRequest) -> FeedbackResponse:
        """
        Persist feedback for a given menu and student.
        """
        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)
            student_repo = self._get_student_repo(uow)

            menu = menu_repo.get(data.menu_id)
            if menu is None:
                raise errors.NotFoundError(f"MessMenu {data.menu_id} not found")

            student = student_repo.get(data.student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(f"Student {data.student_id} not found")
            student_name = student.user.full_name

        submitted_at = self._now()

        record = {
            "menu_id": data.menu_id,
            "hostel_id": menu.hostel_id,
            "menu_date": menu.menu_date,
            "student_id": data.student_id,
            "student_name": student_name,
            "meal_type": data.meal_type.value
            if hasattr(data.meal_type, "value")
            else str(data.meal_type),
            "rating": data.rating,
            "comments": data.comments,
            "taste_rating": data.taste_rating,
            "quantity_rating": data.quantity_rating,
            "quality_rating": data.quality_rating,
            "hygiene_rating": data.hygiene_rating,
            "submitted_at": submitted_at,
        }
        self._store.save_feedback(record)

        return FeedbackResponse(
            id=None,
            created_at=submitted_at,
            updated_at=submitted_at,
            menu_id=data.menu_id,
            student_id=data.student_id,
            student_name=student_name,
            meal_type=data.meal_type,
            rating=data.rating,
            comments=data.comments,
            submitted_at=submitted_at,
        )

    # ------------------------------------------------------------------ #
    # Ratings per menu
    # ------------------------------------------------------------------ #
    def get_ratings_summary(self, menu_id: UUID) -> RatingsSummary:
        """
        Aggregate feedback for a single menu.
        """
        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)

            menu = menu_repo.get(menu_id)
            if menu is None:
                raise errors.NotFoundError(f"MessMenu {menu_id} not found")

        records = self._store.list_feedback_for_menu(menu_id)

        total = len(records)
        if total == 0:
            return RatingsSummary(
                menu_id=menu_id,
                menu_date=menu.menu_date,
                total_feedbacks=0,
                average_rating=Decimal("0"),
                breakfast_rating=None,
                lunch_rating=None,
                snacks_rating=None,
                dinner_rating=None,
                rating_5_count=0,
                rating_4_count=0,
                rating_3_count=0,
                rating_2_count=0,
                rating_1_count=0,
                average_taste_rating=Decimal("0"),
                average_quantity_rating=Decimal("0"),
                average_quality_rating=Decimal("0"),
                average_hygiene_rating=Decimal("0"),
            )

        ratings_by_meal: Dict[str, List[int]] = defaultdict(list)
        rating_counts = {i: 0 for i in range(1, 6)}

        taste_vals: List[int] = []
        qty_vals: List[int] = []
        qual_vals: List[int] = []
        hyg_vals: List[int] = []

        for r in records:
            rating = int(r.get("rating", 0))
            if 1 <= rating <= 5:
                rating_counts[rating] += 1
            meal = str(r.get("meal_type", "")).lower()
            ratings_by_meal[meal].append(rating)

            if r.get("taste_rating") is not None:
                taste_vals.append(int(r["taste_rating"]))
            if r.get("quantity_rating") is not None:
                qty_vals.append(int(r["quantity_rating"]))
            if r.get("quality_rating") is not None:
                qual_vals.append(int(r["quality_rating"]))
            if r.get("hygiene_rating") is not None:
                hyg_vals.append(int(r["hygiene_rating"]))

        def _avg(vals: List[int]) -> Decimal:
            return (
                Decimal(str(sum(vals))) / Decimal(str(len(vals)))
                if vals
                else Decimal("0")
            )

        all_ratings = [int(r.get("rating", 0)) for r in records if r.get("rating")]
        avg_overall = _avg(all_ratings)

        def _meal_avg(key: str) -> Optional[Decimal]:
            vals = ratings_by_meal.get(key, [])
            return _avg(vals) if vals else None

        return RatingsSummary(
            menu_id=menu_id,
            menu_date=menu.menu_date,
            total_feedbacks=total,
            average_rating=avg_overall,
            breakfast_rating=_meal_avg("breakfast"),
            lunch_rating=_meal_avg("lunch"),
            snacks_rating=_meal_avg("snacks"),
            dinner_rating=_meal_avg("dinner"),
            rating_5_count=rating_counts[5],
            rating_4_count=rating_counts[4],
            rating_3_count=rating_counts[3],
            rating_2_count=rating_counts[2],
            rating_1_count=rating_counts[1],
            average_taste_rating=_avg(taste_vals),
            average_quantity_rating=_avg(qty_vals),
            average_quality_rating=_avg(qual_vals),
            average_hygiene_rating=_avg(hyg_vals),
        )

    # ------------------------------------------------------------------ #
    # Quality metrics per hostel
    # ------------------------------------------------------------------ #
    def get_quality_metrics(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> QualityMetrics:
        """
        Compute QualityMetrics for a hostel over a period.
        """
        if not (period.start_date and period.end_date):
            raise errors.ValidationError(
                "Both start_date and end_date are required for quality metrics"
            )

        start = period.start_date
        end = period.end_date

        records = self._store.list_feedback_for_hostel(
            hostel_id, start_date=start, end_date=end
        )

        total_feedbacks = len(records)
        if total_feedbacks == 0:
            return QualityMetrics(
                hostel_id=hostel_id,
                period_start=start,
                period_end=end,
                overall_average_rating=Decimal("0"),
                total_feedbacks=0,
                rating_trend="stable",
                trend_percentage=None,
                best_rated_items=[],
                worst_rated_items=[],
                ratings_by_day={},
            )

        # Overall average
        ratings = [int(r["rating"]) for r in records if r.get("rating") is not None]
        overall_avg = (
            Decimal(str(sum(ratings))) / Decimal(str(len(ratings)))
            if ratings
            else Decimal("0")
        )

        # Trend: compare first half vs second half of period
        mid_point = start + (end - start) / 2
        first_half = [
            int(r["rating"])
            for r in records
            if r.get("submitted_at") and r["submitted_at"].date() <= mid_point
        ]
        second_half = [
            int(r["rating"])
            for r in records
            if r.get("submitted_at") and r["submitted_at"].date() > mid_point
        ]

        def _avg_int(vals: List[int]) -> Decimal:
            return (
                Decimal(str(sum(vals))) / Decimal(str(len(vals)))
                if vals
                else Decimal("0")
            )

        avg_first = _avg_int(first_half)
        avg_second = _avg_int(second_half)

        if avg_first > 0:
            change = (avg_second - avg_first) / avg_first * Decimal("100")
            if change > Decimal("5"):
                trend = "improving"
            elif change < Decimal("-5"):
                trend = "declining"
            else:
                trend = "stable"
            trend_pct = change
        else:
            trend = "stable"
            trend_pct = None

        # Best / worst items – schema suggests per-item ratings, but we do not
        # collect per-item feedback in this codebase. Leave empty lists.
        best_items: List[ItemRating] = []
        worst_items: List[ItemRating] = []

        # Ratings by day-of-week
        by_day: Dict[str, List[int]] = defaultdict(list)
        for r in records:
            d = r.get("menu_date") or (
                r["submitted_at"].date() if r.get("submitted_at") else None
            )
            if not isinstance(d, date):
                continue
            day_name = d.strftime("%A")
            if r.get("rating") is not None:
                by_day[day_name].append(int(r["rating"]))

        ratings_by_day: Dict[str, Decimal] = {
            day: _avg_int(vals) for day, vals in by_day.items()
        }

        return QualityMetrics(
            hostel_id=hostel_id,
            period_start=start,
            period_end=end,
            overall_average_rating=overall_avg,
            total_feedbacks=total_feedbacks,
            rating_trend=trend,
            trend_percentage=trend_pct,
            best_rated_items=best_items,
            worst_rated_items=worst_items,
            ratings_by_day=ratings_by_day,
        )

    # ------------------------------------------------------------------ #
    # Deeper analysis (simple heuristic)
    # ------------------------------------------------------------------ #
    def get_feedback_analysis(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> FeedbackAnalysis:
        """
        Very simple feedback analysis using ratings and comments.
        """
        if not (period.start_date and period.end_date):
            raise errors.ValidationError(
                "Both start_date and end_date are required for feedback analysis"
            )

        start = period.start_date
        end = period.end_date

        records = self._store.list_feedback_for_hostel(
            hostel_id, start_date=start, end_date=end
        )

        total = len(records)
        if total == 0:
            return FeedbackAnalysis(
                hostel_id=hostel_id,
                analysis_period=period,
                positive_feedback_percentage=Decimal("0"),
                negative_feedback_percentage=Decimal("0"),
                common_complaints=[],
                common_compliments=[],
                items_to_keep=[],
                items_to_improve=[],
                items_to_remove=[],
            )

        pos = neg = 0
        positive_comments: List[str] = []
        negative_comments: List[str] = []

        for r in records:
            rating = int(r.get("rating", 0))
            comment = (r.get("comments") or "").strip()
            if rating >= 4:
                pos += 1
                if comment:
                    positive_comments.append(comment)
            elif rating <= 2:
                neg += 1
                if comment:
                    negative_comments.append(comment)

        positive_pct = (
            Decimal(str(pos)) / Decimal(str(total)) * Decimal("100")
            if total > 0
            else Decimal("0")
        )
        negative_pct = (
            Decimal(str(neg)) / Decimal(str(total)) * Decimal("100")
            if total > 0
            else Decimal("0")
        )

        def _top_strings(items: List[str], limit: int = 5) -> List[str]:
            if not items:
                return []
            counts = Counter(items)
            return [s for s, _ in counts.most_common(limit)]

        common_complaints = _top_strings(negative_comments)
        common_compliments = _top_strings(positive_comments)

        # Without per-item feedback, we cannot reliably recommend items to keep/improve/remove.
        return FeedbackAnalysis(
            hostel_id=hostel_id,
            analysis_period=period,
            positive_feedback_percentage=positive_pct,
            negative_feedback_percentage=negative_pct,
            common_complaints=common_complaints,
            common_compliments=common_compliments,
            items_to_keep=[],
            items_to_improve=[],
            items_to_remove=[],
        )