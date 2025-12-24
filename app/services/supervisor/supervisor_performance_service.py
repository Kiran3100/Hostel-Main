"""
Supervisor Performance Service

Handles performance metrics, reports, and reviews.
"""

from __future__ import annotations

from uuid import UUID
from typing import List

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorPerformanceRepository
from app.schemas.common import DateRangeFilter
from app.schemas.supervisor import (
    PerformanceMetrics,
    PerformanceReport,
    PerformanceReview,
)
from app.core.exceptions import ValidationException


class SupervisorPerformanceService:
    """
    High-level service for supervisor performance analytics.

    Responsibilities:
    - Retrieve metrics for a given period
    - Generate performance reports
    - Create/list performance reviews
    """

    def __init__(
        self,
        performance_repo: SupervisorPerformanceRepository,
    ) -> None:
        self.performance_repo = performance_repo

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def get_performance_metrics(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
    ) -> PerformanceMetrics:
        """
        Get summarized performance metrics for a supervisor and period.
        """
        metrics_dict = self.performance_repo.get_metrics(
            db=db,
            supervisor_id=supervisor_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not metrics_dict:
            raise ValidationException("No performance metrics available")
        return PerformanceMetrics.model_validate(metrics_dict)

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    def get_performance_report(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
    ) -> PerformanceReport:
        """
        Build a comprehensive performance report for a supervisor.
        """
        report_dict = self.performance_repo.build_performance_report(
            db=db,
            supervisor_id=supervisor_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not report_dict:
            raise ValidationException("No performance report available")
        return PerformanceReport.model_validate(report_dict)

    # -------------------------------------------------------------------------
    # Reviews
    # -------------------------------------------------------------------------

    def create_performance_review(
        self,
        db: Session,
        supervisor_id: UUID,
        reviewer_id: UUID,
        review: PerformanceReview,
    ) -> PerformanceReview:
        """
        Persist a completed performance review.
        """
        payload = review.model_dump(exclude_none=True)
        payload["supervisor_id"] = supervisor_id
        payload["reviewer_id"] = reviewer_id

        obj = self.performance_repo.create_review(db, payload)
        return PerformanceReview.model_validate(obj)

    def list_performance_reviews(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> List[PerformanceReview]:
        """
        List all reviews for a supervisor.
        """
        objs = self.performance_repo.get_reviews_for_supervisor(db, supervisor_id)
        return [PerformanceReview.model_validate(o) for o in objs]