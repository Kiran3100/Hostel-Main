# app/services/mess/menu_feedback_service.py
"""
Menu Feedback Service

Handles feedback collection and analytics for mess menus:
- Submit feedback
- Get ratings summary
- Quality metrics & analysis
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.mess import MenuFeedbackRepository
from app.schemas.mess import (
    FeedbackRequest,
    FeedbackResponse,
    RatingsSummary,
    QualityMetrics,
    FeedbackAnalysis,
)
from app.core.exceptions import ValidationException


class MenuFeedbackService:
    """
    High-level service for menu feedback.
    """

    def __init__(self, feedback_repo: MenuFeedbackRepository) -> None:
        self.feedback_repo = feedback_repo

    def submit_feedback(
        self,
        db: Session,
        menu_id: UUID,
        student_id: UUID,
        request: FeedbackRequest,
    ) -> FeedbackResponse:
        payload = request.model_dump(exclude_none=True)
        payload.update({"menu_id": menu_id, "student_id": student_id})

        obj = self.feedback_repo.create_feedback(db, payload)
        return FeedbackResponse.model_validate(obj)

    def get_ratings_summary(
        self,
        db: Session,
        menu_id: UUID,
    ) -> RatingsSummary:
        data = self.feedback_repo.get_ratings_summary_for_menu(db, menu_id)
        if not data:
            return RatingsSummary(
                menu_id=menu_id,
                menu_date=None,
                total_feedbacks=0,
                overall_rating=0.0,
                median_rating=0.0,
                rating_distribution={},
                breakfast_rating=None,
                lunch_rating=None,
                dinner_rating=None,
                aspect_ratings={},
                would_recommend_percentage=0.0,
                top_positive_items=[],
                top_negative_items=[],
            )
        return RatingsSummary.model_validate(data)

    def get_quality_metrics(
        self,
        db: Session,
        hostel_id: UUID,
        start_date,
        end_date,
    ) -> QualityMetrics:
        data = self.feedback_repo.get_quality_metrics(
            db=db,
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        if not data:
            raise ValidationException("No quality metrics available")
        return QualityMetrics.model_validate(data)

    def get_feedback_analysis(
        self,
        db: Session,
        hostel_id: UUID,
        start_date,
        end_date,
    ) -> FeedbackAnalysis:
        data = self.feedback_repo.get_feedback_analysis(
            db=db,
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        if not data:
            raise ValidationException("No feedback analysis available")
        return FeedbackAnalysis.model_validate(data)