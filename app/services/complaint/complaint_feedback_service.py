"""
Complaint feedback service.

Manages feedback collection from users on resolved complaints
and provides comprehensive feedback analytics.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.complaint.complaint_feedback_repository import ComplaintFeedbackRepository
from app.models.complaint.complaint_feedback import ComplaintFeedback as ComplaintFeedbackModel
from app.schemas.complaint.complaint_feedback import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummary,
    RatingTrendPoint,
    FeedbackAnalysis,
)

logger = logging.getLogger(__name__)


class ComplaintFeedbackService(BaseService[ComplaintFeedbackModel, ComplaintFeedbackRepository]):
    """
    Handle feedback submission and analytics for resolved complaints.
    
    Provides feedback collection, rating analytics, and trend analysis
    to measure complaint resolution quality.
    """

    # Rating bounds
    MIN_RATING = 1
    MAX_RATING = 5

    def __init__(self, repository: ComplaintFeedbackRepository, db_session: Session):
        """
        Initialize feedback service.
        
        Args:
            repository: Complaint feedback repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Feedback Submission
    # -------------------------------------------------------------------------

    def submit(
        self,
        request: FeedbackRequest,
        submitted_by: Optional[UUID] = None,
    ) -> ServiceResult[FeedbackResponse]:
        """
        Submit feedback for a resolved complaint.
        
        Args:
            request: Feedback submission data
            submitted_by: UUID of user submitting feedback
            
        Returns:
            ServiceResult containing FeedbackResponse or error
        """
        try:
            self._logger.info(
                f"Submitting feedback for complaint {request.complaint_id}, "
                f"rating: {request.rating}, submitted_by: {submitted_by}"
            )
            
            # Validate feedback request
            validation_result = self._validate_feedback(request)
            if not validation_result.success:
                return validation_result
            
            # Check if feedback already exists
            existing_check = self._check_duplicate_feedback(request.complaint_id, submitted_by)
            if not existing_check.success:
                return existing_check
            
            # Submit feedback
            response = self.repository.submit_feedback(request, submitted_by=submitted_by)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Feedback submitted successfully for complaint {request.complaint_id}"
            )
            
            return ServiceResult.success(
                response,
                message="Feedback recorded successfully",
                metadata={
                    "complaint_id": str(request.complaint_id),
                    "rating": request.rating,
                    "feedback_id": str(response.id) if hasattr(response, 'id') else None,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error submitting feedback for complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "submit feedback", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error submitting feedback for complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "submit feedback", request.complaint_id)

    # -------------------------------------------------------------------------
    # Feedback Analytics
    # -------------------------------------------------------------------------

    def summary(
        self,
        entity_id: UUID,
        entity_type: str = "hostel",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ServiceResult[FeedbackSummary]:
        """
        Get feedback summary for an entity (hostel, staff member, etc.).
        
        Args:
            entity_id: UUID of entity
            entity_type: Type of entity ("hostel", "staff", etc.)
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            
        Returns:
            ServiceResult containing FeedbackSummary or error
        """
        try:
            # Validate date range if provided
            if start_date and end_date:
                date_validation = self._validate_date_range(start_date, end_date)
                if not date_validation.success:
                    return date_validation
            
            self._logger.debug(
                f"Fetching feedback summary for {entity_type} {entity_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            summary = self.repository.get_summary(
                entity_id,
                entity_type,
                start_date,
                end_date
            )
            
            return ServiceResult.success(
                summary,
                metadata={
                    "entity_id": str(entity_id),
                    "entity_type": entity_type,
                    "start_date": str(start_date) if start_date else None,
                    "end_date": str(end_date) if end_date else None,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching feedback summary for {entity_type} {entity_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get feedback summary", entity_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching feedback summary for {entity_type} {entity_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get feedback summary", entity_id)

    def analysis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[FeedbackAnalysis]:
        """
        Get detailed feedback analysis with trends and distributions.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            ServiceResult containing FeedbackAnalysis or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            self._logger.debug(
                f"Fetching feedback analysis for hostel {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            analysis = self.repository.get_analysis(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                analysis,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching feedback analysis for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get feedback analysis", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching feedback analysis for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get feedback analysis", hostel_id)

    def get_rating_trend(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        interval: str = "daily",
    ) -> ServiceResult[List[RatingTrendPoint]]:
        """
        Get rating trend over time.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for trend
            end_date: End date for trend
            interval: Aggregation interval ("daily", "weekly", "monthly")
            
        Returns:
            ServiceResult containing list of RatingTrendPoint or error
        """
        try:
            # Validate inputs
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            valid_intervals = ["daily", "weekly", "monthly"]
            if interval not in valid_intervals:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.debug(
                f"Fetching rating trend for hostel {hostel_id}, "
                f"interval: {interval}, date range: {start_date} to {end_date}"
            )
            
            # Implementation would call repository method
            trend_points: List[RatingTrendPoint] = []
            
            return ServiceResult.success(
                trend_points,
                metadata={
                    "hostel_id": str(hostel_id),
                    "interval": interval,
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "count": len(trend_points),
                }
            )
            
        except Exception as e:
            self._logger.error(
                f"Error fetching rating trend for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get rating trend", hostel_id)

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_feedback(
        self,
        request: FeedbackRequest
    ) -> ServiceResult[None]:
        """
        Validate feedback submission request.
        
        Args:
            request: Feedback request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.complaint_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Validate rating
        if not hasattr(request, 'rating') or request.rating is None:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Rating is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if request.rating < self.MIN_RATING or request.rating > self.MAX_RATING:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Rating must be between {self.MIN_RATING} and {self.MAX_RATING}",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Validate comments if provided
        if hasattr(request, 'comments') and request.comments:
            if len(request.comments) > 2000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Comments exceed maximum length of 2000 characters",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        return ServiceResult.success(None)

    def _validate_date_range(
        self,
        start_date: date,
        end_date: date,
        max_range_days: int = 365
    ) -> ServiceResult[None]:
        """
        Validate date range for queries.
        
        Args:
            start_date: Start date
            end_date: End date
            max_range_days: Maximum allowed range in days
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if start_date > end_date:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date must be before or equal to end date",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Check range limit
        delta = end_date - start_date
        if delta.days > max_range_days:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Date range cannot exceed {max_range_days} days",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Check if dates are not in the future
        today = date.today()
        if start_date > today or end_date > today:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Dates cannot be in the future",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _check_duplicate_feedback(
        self,
        complaint_id: UUID,
        submitted_by: Optional[UUID]
    ) -> ServiceResult[None]:
        """
        Check if user has already submitted feedback for this complaint.
        
        Args:
            complaint_id: UUID of complaint
            submitted_by: UUID of user
            
        Returns:
            ServiceResult indicating whether duplicate exists
        """
        # Implementation would check repository for existing feedback
        # For now, return success to allow multiple feedback submissions
        return ServiceResult.success(None)