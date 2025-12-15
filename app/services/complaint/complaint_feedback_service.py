# app/services/complaint/complaint_feedback_service.py
from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Protocol, List, Optional
from uuid import UUID

from app.schemas.complaint import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummary,
    FeedbackAnalysis,
    RatingTrendPoint,
)
from app.schemas.common.filters import DateRangeFilter


class FeedbackStore(Protocol):
    """
    Abstract storage for complaint feedback.

    Each implementation should persist feedback records and allow querying.
    """

    def save_feedback(self, record: dict) -> None: ...
    def list_feedback_for_complaint(self, complaint_id: UUID) -> List[dict]: ...
    def list_feedback_for_scope(
        self,
        *,
        entity_id: UUID,
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> List[dict]: ...


class ComplaintFeedbackService:
    """
    Manage feedback on resolved complaints.

    NOTE:
    - This service is storage-agnostic; you need to provide a FeedbackStore.
    """

    def __init__(self, store: FeedbackStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Submit feedback
    # ------------------------------------------------------------------ #
    def submit_feedback(
        self,
        data: FeedbackRequest,
        *,
        submitted_by: UUID,
        submitted_by_name: str,
    ) -> FeedbackResponse:
        record = {
            "complaint_id": str(data.complaint_id),
            "rating": data.rating,
            "feedback": data.feedback,
            "issue_resolved_satisfactorily": data.issue_resolved_satisfactorily,
            "response_time_satisfactory": data.response_time_satisfactory,
            "staff_helpful": data.staff_helpful,
            "would_recommend": data.would_recommend,
            "submitted_by": str(submitted_by),
            "submitted_at": self._now(),
        }
        self._store.save_feedback(record)

        return FeedbackResponse(
            id=None,
            created_at=record["submitted_at"],
            updated_at=record["submitted_at"],
            complaint_id=data.complaint_id,
            complaint_number="",
            rating=data.rating,
            feedback=data.feedback,
            submitted_by=submitted_by,
            submitted_at=record["submitted_at"],
            message="Feedback submitted successfully",
        )

    # ------------------------------------------------------------------ #
    # Summary / analysis (hostel or supervisor)
    # ------------------------------------------------------------------ #
    def get_summary(
        self,
        entity_id: UUID,
        entity_type: str,
        period_start: date,
        period_end: date,
    ) -> FeedbackSummary:
        records = self._store.list_feedback_for_scope(
            entity_id=entity_id,
            from_date=period_start,
            to_date=period_end,
        )
        total = len(records)
        if total == 0:
            return FeedbackSummary(
                entity_id=entity_id,
                entity_type=entity_type,
                period_start=period_start,
                period_end=period_end,
                total_feedbacks=0,
                average_rating=0,
                rating_5_count=0,
                rating_4_count=0,
                rating_3_count=0,
                rating_2_count=0,
                rating_1_count=0,
                resolution_satisfaction_rate=0,
                response_time_satisfaction_rate=0,
                staff_helpfulness_rate=0,
                recommendation_rate=0,
                positive_feedback_count=0,
                negative_feedback_count=0,
                common_themes=[],
            )

        rating_counts = {i: 0 for i in range(1, 6)}
        sum_ratings = 0
        res_sat = 0
        resp_time_sat = 0
        staff_help = 0
        recommend = 0

        for r in records:
            rating = int(r.get("rating", 0))
            if rating in rating_counts:
                rating_counts[rating] += 1
                sum_ratings += rating
            if r.get("issue_resolved_satisfactorily"):
                res_sat += 1
            if r.get("response_time_satisfactory"):
                resp_time_sat += 1
            if r.get("staff_helpful"):
                staff_help += 1
            if r.get("would_recommend"):
                recommend += 1

        avg_rating = sum_ratings / total if total > 0 else 0
        pct = lambda x: (x / total * 100) if total > 0 else 0

        return FeedbackSummary(
            entity_id=entity_id,
            entity_type=entity_type,
            period_start=period_start,
            period_end=period_end,
            total_feedbacks=total,
            average_rating=avg_rating,
            rating_5_count=rating_counts[5],
            rating_4_count=rating_counts[4],
            rating_3_count=rating_counts[3],
            rating_2_count=rating_counts[2],
            rating_1_count=rating_counts[1],
            resolution_satisfaction_rate=pct(res_sat),
            response_time_satisfaction_rate=pct(resp_time_sat),
            staff_helpfulness_rate=pct(staff_help),
            recommendation_rate=pct(recommend),
            positive_feedback_count=0,
            negative_feedback_count=0,
            common_themes=[],
        )

    def get_analysis(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> FeedbackAnalysis:
        records = self._store.list_feedback_for_scope(
            entity_id=hostel_id,
            from_date=period.start_date,
            to_date=period.end_date,
        )
        total = len(records)
        if total == 0:
            return FeedbackAnalysis(
                hostel_id=hostel_id,
                period_start=period.start_date,
                period_end=period.end_date,
                rating_trend=[],
                feedback_by_category={},
                feedback_by_priority={},
                avg_rating_quick_response=0,
                avg_rating_slow_response=0,
            )

        # Simplified analysis, extend as needed
        return FeedbackAnalysis(
            hostel_id=hostel_id,
            period_start=period.start_date,
            period_end=period.end_date,
            rating_trend=[],
            feedback_by_category={},
            feedback_by_priority={},
            avg_rating_quick_response=0,
            avg_rating_slow_response=0,
        )