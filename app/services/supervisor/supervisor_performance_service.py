"""
Supervisor Performance Service

Handles performance metrics, reports, and reviews with comprehensive analytics.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorPerformanceRepository
from app.schemas.common import DateRangeFilter
from app.schemas.supervisor import (
    PerformanceMetrics,
    PerformanceReport,
    PerformanceReview,
)
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SupervisorPerformanceService:
    """
    High-level service for supervisor performance analytics.

    Responsibilities:
    - Retrieve metrics for a given period
    - Generate comprehensive performance reports
    - Create/list/update performance reviews
    - Calculate performance scores and ratings
    - Track performance trends

    Example:
        >>> service = SupervisorPerformanceService(performance_repo)
        >>> metrics = service.get_performance_metrics(db, supervisor_id, period)
        >>> report = service.get_performance_report(db, supervisor_id, period)
    """

    def __init__(
        self,
        performance_repo: SupervisorPerformanceRepository,
    ) -> None:
        """
        Initialize the supervisor performance service.

        Args:
            performance_repo: Repository for performance operations
        """
        if not performance_repo:
            raise ValueError("performance_repo cannot be None")
            
        self.performance_repo = performance_repo

    # -------------------------------------------------------------------------
    # Metrics Operations
    # -------------------------------------------------------------------------

    def get_performance_metrics(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
    ) -> PerformanceMetrics:
        """
        Get summarized performance metrics for a supervisor and period.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            period: Date range filter

        Returns:
            PerformanceMetrics: Performance metrics summary

        Raises:
            ValidationException: If validation fails or no metrics available

        Example:
            >>> period = DateRangeFilter(
            ...     start_date=datetime(2024, 1, 1).date(),
            ...     end_date=datetime(2024, 1, 31).date()
            ... )
            >>> metrics = service.get_performance_metrics(db, supervisor_id, period)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not period:
            raise ValidationException("Period filter is required")
        
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")
        
        if period.start_date > period.end_date:
            raise ValidationException("start_date cannot be after end_date")

        try:
            logger.info(
                f"Getting performance metrics for supervisor: {supervisor_id}, "
                f"period: {period.start_date} to {period.end_date}"
            )
            
            metrics_dict = self.performance_repo.get_metrics(
                db=db,
                supervisor_id=supervisor_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not metrics_dict:
                logger.warning(
                    f"No performance metrics available for supervisor: {supervisor_id}"
                )
                raise ValidationException(
                    f"No performance metrics available for supervisor {supervisor_id} "
                    f"in the specified period"
                )
            
            logger.info(
                f"Successfully retrieved performance metrics for: {supervisor_id}"
            )
            return PerformanceMetrics.model_validate(metrics_dict)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get performance metrics for {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to retrieve performance metrics: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Reports Operations
    # -------------------------------------------------------------------------

    def get_performance_report(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
        include_detailed_breakdown: bool = True,
    ) -> PerformanceReport:
        """
        Build a comprehensive performance report for a supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            period: Date range filter
            include_detailed_breakdown: Whether to include detailed breakdowns

        Returns:
            PerformanceReport: Comprehensive performance report

        Raises:
            ValidationException: If validation fails or report cannot be built

        Example:
            >>> report = service.get_performance_report(
            ...     db, supervisor_id, period, include_detailed_breakdown=True
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not period:
            raise ValidationException("Period filter is required")
        
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")
        
        if period.start_date > period.end_date:
            raise ValidationException("start_date cannot be after end_date")

        try:
            logger.info(
                f"Building performance report for supervisor: {supervisor_id}, "
                f"period: {period.start_date} to {period.end_date}"
            )
            
            report_dict = self.performance_repo.build_performance_report(
                db=db,
                supervisor_id=supervisor_id,
                start_date=period.start_date,
                end_date=period.end_date,
                include_detailed_breakdown=include_detailed_breakdown,
            )
            
            if not report_dict:
                logger.warning(
                    f"No performance report available for supervisor: {supervisor_id}"
                )
                raise ValidationException(
                    f"No performance report available for supervisor {supervisor_id} "
                    f"in the specified period"
                )
            
            logger.info(
                f"Successfully built performance report for: {supervisor_id}"
            )
            return PerformanceReport.model_validate(report_dict)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to build performance report for {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to build performance report: {str(e)}"
            )

    def export_performance_report(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
        format: str = "pdf",
    ) -> Dict[str, Any]:
        """
        Export performance report in specified format.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            period: Date range filter
            format: Export format ("pdf", "excel", "csv")

        Returns:
            Dict[str, Any]: Export metadata including file path/URL

        Raises:
            ValidationException: If validation fails

        Example:
            >>> export_data = service.export_performance_report(
            ...     db, supervisor_id, period, format="pdf"
            ... )
        """
        if format not in ["pdf", "excel", "csv"]:
            raise ValidationException("Format must be one of: pdf, excel, csv")

        try:
            logger.info(
                f"Exporting performance report for supervisor: {supervisor_id}, "
                f"format: {format}"
            )
            
            report = self.get_performance_report(db, supervisor_id, period)
            
            export_result = self.performance_repo.export_report(
                db=db,
                report_data=report.model_dump(),
                format=format,
            )
            
            logger.info(
                f"Successfully exported performance report for: {supervisor_id}"
            )
            return export_result
            
        except Exception as e:
            logger.error(f"Failed to export performance report: {str(e)}")
            raise ValidationException(f"Failed to export report: {str(e)}")

    # -------------------------------------------------------------------------
    # Reviews Operations
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

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor being reviewed
            reviewer_id: UUID of the reviewer
            review: Performance review data

        Returns:
            PerformanceReview: Created review object

        Raises:
            ValidationException: If validation fails

        Example:
            >>> review = PerformanceReview(
            ...     rating=4.5,
            ...     comments="Excellent performance",
            ...     review_period_start=start_date,
            ...     review_period_end=end_date
            ... )
            >>> created = service.create_performance_review(
            ...     db, supervisor_id, reviewer_id, review
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not reviewer_id:
            raise ValidationException("Reviewer ID is required")
        
        if not review:
            raise ValidationException("Review data is required")

        try:
            logger.info(
                f"Creating performance review for supervisor: {supervisor_id}, "
                f"reviewer: {reviewer_id}"
            )
            
            payload = review.model_dump(exclude_none=True)
            payload["supervisor_id"] = supervisor_id
            payload["reviewer_id"] = reviewer_id
            payload["review_date"] = datetime.utcnow()

            obj = self.performance_repo.create_review(db, payload)
            
            logger.info(
                f"Successfully created performance review for: {supervisor_id}"
            )
            return PerformanceReview.model_validate(obj)
            
        except Exception as e:
            logger.error(
                f"Failed to create performance review for {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to create performance review: {str(e)}"
            )

    def update_performance_review(
        self,
        db: Session,
        review_id: UUID,
        update_data: Dict[str, Any],
    ) -> PerformanceReview:
        """
        Update an existing performance review.

        Args:
            db: Database session
            review_id: UUID of the review to update
            update_data: Partial update data

        Returns:
            PerformanceReview: Updated review object

        Raises:
            ValidationException: If validation fails or review not found

        Example:
            >>> updated = service.update_performance_review(
            ...     db, review_id, {"rating": 5.0, "comments": "Outstanding"}
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not review_id:
            raise ValidationException("Review ID is required")
        
        if not update_data:
            raise ValidationException("Update data is required")

        try:
            logger.info(f"Updating performance review: {review_id}")
            
            review = self.performance_repo.get_review_by_id(db, review_id)
            if not review:
                logger.warning(f"Performance review not found: {review_id}")
                raise ValidationException(
                    f"Performance review not found with ID: {review_id}"
                )

            update_data["updated_at"] = datetime.utcnow()
            updated = self.performance_repo.update_review(
                db, review, update_data
            )
            
            logger.info(f"Successfully updated performance review: {review_id}")
            return PerformanceReview.model_validate(updated)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to update performance review {review_id}: {str(e)}")
            raise ValidationException(
                f"Failed to update performance review: {str(e)}"
            )

    def list_performance_reviews(
        self,
        db: Session,
        supervisor_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[PerformanceReview]:
        """
        List all reviews for a supervisor with pagination.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[PerformanceReview]: List of performance reviews

        Raises:
            ValidationException: If validation fails

        Example:
            >>> reviews = service.list_performance_reviews(
            ...     db, supervisor_id, skip=0, limit=10
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if skip < 0:
            raise ValidationException("Skip parameter cannot be negative")
        
        if limit <= 0 or limit > 100:
            raise ValidationException("Limit must be between 1 and 100")

        try:
            logger.debug(
                f"Listing performance reviews for supervisor: {supervisor_id}, "
                f"skip: {skip}, limit: {limit}"
            )
            
            objs = self.performance_repo.get_reviews_for_supervisor(
                db, supervisor_id, skip=skip, limit=limit
            )
            
            logger.debug(
                f"Found {len(objs)} performance reviews for: {supervisor_id}"
            )
            return [PerformanceReview.model_validate(o) for o in objs]
            
        except Exception as e:
            logger.error(
                f"Failed to list performance reviews for {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to list performance reviews: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Analytics Operations
    # -------------------------------------------------------------------------

    def get_performance_trends(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
        metric_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get performance trends over time.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            period: Date range filter
            metric_type: Optional specific metric to analyze

        Returns:
            Dict[str, Any]: Trend data with time series

        Example:
            >>> trends = service.get_performance_trends(
            ...     db, supervisor_id, period, metric_type="complaint_resolution"
            ... )
        """
        if not db or not supervisor_id or not period:
            raise ValidationException("Required parameters missing")

        try:
            logger.debug(
                f"Getting performance trends for supervisor: {supervisor_id}"
            )
            
            trends = self.performance_repo.get_performance_trends(
                db=db,
                supervisor_id=supervisor_id,
                start_date=period.start_date,
                end_date=period.end_date,
                metric_type=metric_type,
            )
            
            return trends or {}
            
        except Exception as e:
            logger.error(f"Failed to get performance trends: {str(e)}")
            raise ValidationException(f"Failed to retrieve performance trends: {str(e)}")

    def calculate_overall_rating(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
    ) -> float:
        """
        Calculate overall performance rating for a supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            period: Date range filter

        Returns:
            float: Overall rating score (0-5)

        Example:
            >>> rating = service.calculate_overall_rating(db, supervisor_id, period)
        """
        if not db or not supervisor_id or not period:
            return 0.0
        
        try:
            metrics = self.get_performance_metrics(db, supervisor_id, period)
            
            # Calculate weighted average of different metric components
            weights = {
                "complaint_resolution_score": 0.3,
                "attendance_score": 0.2,
                "maintenance_score": 0.2,
                "communication_score": 0.15,
                "leadership_score": 0.15,
            }
            
            total_score = 0.0
            total_weight = 0.0
            
            metrics_dict = metrics.model_dump()
            for metric_key, weight in weights.items():
                if metric_key in metrics_dict and metrics_dict[metric_key] is not None:
                    total_score += metrics_dict[metric_key] * weight
                    total_weight += weight
            
            if total_weight > 0:
                return round(total_score / total_weight, 2)
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate overall rating: {str(e)}")
            return 0.0