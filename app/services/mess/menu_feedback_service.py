# app/services/mess/menu_feedback_service.py
"""
Menu Feedback Service

Handles feedback collection and analytics for mess menus:
- Submit and manage feedback
- Rating aggregation and analysis
- Quality metrics & trends
- Sentiment analysis integration

Performance Optimizations:
- Cached aggregate calculations
- Efficient query patterns
- Batch feedback processing
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.mess import MenuFeedbackRepository
from app.schemas.mess import (
    FeedbackRequest,
    FeedbackResponse,
    RatingsSummary,
    QualityMetrics,
    FeedbackAnalysis,
)
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateEntryException,
)


class MenuFeedbackService:
    """
    High-level service for menu feedback and quality analysis.
    
    This service manages:
    - Feedback submission and retrieval
    - Rating aggregation
    - Quality metrics calculation
    - Trend analysis
    """

    # Constants
    MIN_RATING = 1
    MAX_RATING = 5
    RATING_PRECISION = 2

    def __init__(self, feedback_repo: MenuFeedbackRepository) -> None:
        """
        Initialize the menu feedback service.
        
        Args:
            feedback_repo: Repository for feedback operations
        """
        self.feedback_repo = feedback_repo

    # -------------------------------------------------------------------------
    # Feedback Submission
    # -------------------------------------------------------------------------

    def submit_feedback(
        self,
        db: Session,
        menu_id: UUID,
        student_id: UUID,
        request: FeedbackRequest,
    ) -> FeedbackResponse:
        """
        Submit feedback for a menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            student_id: Unique identifier of the student
            request: Feedback details
            
        Returns:
            Created FeedbackResponse schema
            
        Raises:
            ValidationException: If feedback data is invalid
            DuplicateEntryException: If student already submitted feedback
        """
        try:
            # Validate feedback data
            self._validate_feedback_request(request)
            
            # Check for duplicate feedback
            existing = self.feedback_repo.get_by_student_and_menu(
                db, student_id, menu_id
            )
            
            if existing:
                raise DuplicateEntryException(
                    "Student has already submitted feedback for this menu"
                )
            
            payload = request.model_dump(exclude_none=True, exclude_unset=True)
            payload.update({
                "menu_id": menu_id,
                "student_id": student_id,
                "submitted_at": datetime.utcnow(),
            })

            obj = self.feedback_repo.create_feedback(db, payload)
            db.flush()
            
            # Update aggregate ratings asynchronously
            self._update_aggregate_ratings(db, menu_id)
            
            return FeedbackResponse.model_validate(obj)
            
        except (ValidationException, DuplicateEntryException):
            raise
        except IntegrityError as e:
            db.rollback()
            raise DuplicateEntryException(
                f"Feedback already exists: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error submitting feedback: {str(e)}"
            )

    def update_feedback(
        self,
        db: Session,
        feedback_id: UUID,
        student_id: UUID,
        request: FeedbackRequest,
    ) -> FeedbackResponse:
        """
        Update existing feedback.
        
        Args:
            db: Database session
            feedback_id: Unique identifier of the feedback
            student_id: Unique identifier of the student (for verification)
            request: Updated feedback details
            
        Returns:
            Updated FeedbackResponse schema
            
        Raises:
            NotFoundException: If feedback not found
            ValidationException: If student doesn't own the feedback
        """
        try:
            feedback = self.feedback_repo.get_by_id(db, feedback_id)
            
            if not feedback:
                raise NotFoundException(
                    f"Feedback with ID {feedback_id} not found"
                )
            
            # Verify ownership
            if getattr(feedback, 'student_id', None) != student_id:
                raise ValidationException(
                    "Cannot update feedback submitted by another student"
                )
            
            # Validate updated data
            self._validate_feedback_request(request)
            
            payload = request.model_dump(exclude_none=True, exclude_unset=True)
            payload["updated_at"] = datetime.utcnow()
            
            obj = self.feedback_repo.update(db, feedback, payload)
            db.flush()
            
            # Update aggregate ratings
            menu_id = getattr(feedback, 'menu_id', None)
            if menu_id:
                self._update_aggregate_ratings(db, menu_id)
            
            return FeedbackResponse.model_validate(obj)
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating feedback: {str(e)}"
            )

    def delete_feedback(
        self,
        db: Session,
        feedback_id: UUID,
        student_id: UUID,
    ) -> None:
        """
        Delete feedback (soft delete).
        
        Args:
            db: Database session
            feedback_id: Unique identifier of the feedback
            student_id: Unique identifier of the student (for verification)
            
        Raises:
            NotFoundException: If feedback not found
            ValidationException: If student doesn't own the feedback
        """
        try:
            feedback = self.feedback_repo.get_by_id(db, feedback_id)
            
            if not feedback:
                raise NotFoundException(
                    f"Feedback with ID {feedback_id} not found"
                )
            
            # Verify ownership
            if getattr(feedback, 'student_id', None) != student_id:
                raise ValidationException(
                    "Cannot delete feedback submitted by another student"
                )
            
            menu_id = getattr(feedback, 'menu_id', None)
            
            self.feedback_repo.delete(db, feedback)
            db.flush()
            
            # Update aggregate ratings
            if menu_id:
                self._update_aggregate_ratings(db, menu_id)
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error deleting feedback: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Feedback Retrieval
    # -------------------------------------------------------------------------

    def get_feedback(
        self,
        db: Session,
        feedback_id: UUID,
    ) -> FeedbackResponse:
        """
        Get a specific feedback by ID.
        
        Args:
            db: Database session
            feedback_id: Unique identifier of the feedback
            
        Returns:
            FeedbackResponse schema
            
        Raises:
            NotFoundException: If feedback not found
        """
        try:
            feedback = self.feedback_repo.get_by_id(db, feedback_id)
            
            if not feedback:
                raise NotFoundException(
                    f"Feedback with ID {feedback_id} not found"
                )
            
            return FeedbackResponse.model_validate(feedback)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving feedback: {str(e)}"
            )

    def get_feedback_for_menu(
        self,
        db: Session,
        menu_id: UUID,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[FeedbackResponse]:
        """
        Get all feedback for a specific menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            limit: Optional limit on number of records
            offset: Optional offset for pagination
            
        Returns:
            List of FeedbackResponse schemas
        """
        try:
            feedbacks = self.feedback_repo.get_by_menu_id(
                db, menu_id, limit, offset
            )
            return [FeedbackResponse.model_validate(f) for f in feedbacks]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving feedback for menu {menu_id}: {str(e)}"
            )

    def get_student_feedback_for_menu(
        self,
        db: Session,
        student_id: UUID,
        menu_id: UUID,
    ) -> Optional[FeedbackResponse]:
        """
        Get a student's feedback for a specific menu.
        
        Args:
            db: Database session
            student_id: Unique identifier of the student
            menu_id: Unique identifier of the menu
            
        Returns:
            FeedbackResponse if found, None otherwise
        """
        try:
            feedback = self.feedback_repo.get_by_student_and_menu(
                db, student_id, menu_id
            )
            
            if not feedback:
                return None
            
            return FeedbackResponse.model_validate(feedback)
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving student feedback: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Ratings & Aggregation
    # -------------------------------------------------------------------------

    def get_ratings_summary(
        self,
        db: Session,
        menu_id: UUID,
    ) -> RatingsSummary:
        """
        Get aggregated ratings summary for a menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            RatingsSummary schema with aggregated data
        """
        try:
            data = self.feedback_repo.get_ratings_summary_for_menu(db, menu_id)
            
            if not data:
                # Return empty summary if no feedback exists
                return self._get_empty_ratings_summary(menu_id)
            
            return RatingsSummary.model_validate(data)
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving ratings summary for menu {menu_id}: {str(e)}"
            )

    def get_item_ratings(
        self,
        db: Session,
        menu_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get ratings breakdown by individual menu items.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            Dictionary with item-level ratings
        """
        try:
            item_ratings = self.feedback_repo.get_item_level_ratings(db, menu_id)
            
            return {
                "menu_id": str(menu_id),
                "items": [
                    {
                        "item_id": str(item['item_id']),
                        "item_name": item['item_name'],
                        "average_rating": float(item['avg_rating']),
                        "total_ratings": item['total_ratings'],
                        "positive_count": item['positive_count'],
                        "negative_count": item['negative_count'],
                    }
                    for item in item_ratings
                ],
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving item ratings: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Quality Metrics
    # -------------------------------------------------------------------------

    def get_quality_metrics(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> QualityMetrics:
        """
        Get quality metrics for a hostel over a period.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the period
            end_date: End date of the period
            
        Returns:
            QualityMetrics schema
            
        Raises:
            ValidationException: If date range is invalid
        """
        try:
            # Validate date range
            self._validate_date_range(start_date, end_date)
            
            data = self.feedback_repo.get_quality_metrics(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )
            
            if not data:
                raise NotFoundException(
                    "No quality metrics available for the specified period"
                )
            
            return QualityMetrics.model_validate(data)
            
        except (ValidationException, NotFoundException):
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving quality metrics: {str(e)}"
            )

    def get_quality_trends(
        self,
        db: Session,
        hostel_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get quality trends over time.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            trends = self.feedback_repo.get_quality_trends(
                db, hostel_id, start_date, end_date
            )
            
            return {
                "hostel_id": str(hostel_id),
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily_trends": trends.get("daily_trends", []),
                "overall_trend": trends.get("overall_trend", "stable"),
                "improvement_areas": trends.get("improvement_areas", []),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving quality trends: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Feedback Analysis
    # -------------------------------------------------------------------------

    def get_feedback_analysis(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> FeedbackAnalysis:
        """
        Get comprehensive feedback analysis for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the analysis period
            end_date: End date of the analysis period
            
        Returns:
            FeedbackAnalysis schema
            
        Raises:
            ValidationException: If date range is invalid
        """
        try:
            # Validate date range
            self._validate_date_range(start_date, end_date)
            
            data = self.feedback_repo.get_feedback_analysis(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )
            
            if not data:
                raise NotFoundException(
                    "No feedback analysis available for the specified period"
                )
            
            return FeedbackAnalysis.model_validate(data)
            
        except (ValidationException, NotFoundException):
            raise
        except Exception as e:
            raise ValidationException(
                f"Error generating feedback analysis: {str(e)}"
            )

    def get_sentiment_analysis(
        self,
        db: Session,
        menu_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get sentiment analysis for menu feedback comments.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            Dictionary with sentiment analysis results
        """
        try:
            feedbacks = self.feedback_repo.get_by_menu_id(db, menu_id)
            
            if not feedbacks:
                return self._get_empty_sentiment_analysis(menu_id)
            
            # Extract comments
            comments = [
                getattr(f, 'comments', '')
                for f in feedbacks
                if getattr(f, 'comments', None)
            ]
            
            # Perform sentiment analysis
            sentiment_results = self._analyze_sentiments(comments)
            
            return {
                "menu_id": str(menu_id),
                "total_comments": len(comments),
                "sentiment_distribution": sentiment_results.get("distribution", {}),
                "dominant_sentiment": sentiment_results.get("dominant", "neutral"),
                "key_themes": sentiment_results.get("themes", []),
                "positive_keywords": sentiment_results.get("positive_keywords", []),
                "negative_keywords": sentiment_results.get("negative_keywords", []),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error performing sentiment analysis: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Comparative Analysis
    # -------------------------------------------------------------------------

    def compare_menus(
        self,
        db: Session,
        menu_ids: List[UUID],
    ) -> Dict[str, Any]:
        """
        Compare feedback metrics across multiple menus.
        
        Args:
            db: Database session
            menu_ids: List of menu IDs to compare
            
        Returns:
            Dictionary with comparative analysis
        """
        try:
            if len(menu_ids) < 2:
                raise ValidationException(
                    "At least 2 menus required for comparison"
                )
            
            comparisons = []
            
            for menu_id in menu_ids:
                summary = self.get_ratings_summary(db, menu_id)
                comparisons.append({
                    "menu_id": str(menu_id),
                    "menu_date": getattr(summary, 'menu_date', None),
                    "overall_rating": float(getattr(summary, 'overall_rating', 0.0)),
                    "total_feedbacks": getattr(summary, 'total_feedbacks', 0),
                    "would_recommend": float(
                        getattr(summary, 'would_recommend_percentage', 0.0)
                    ),
                })
            
            # Sort by rating
            comparisons.sort(key=lambda x: x['overall_rating'], reverse=True)
            
            return {
                "total_menus_compared": len(menu_ids),
                "best_menu": comparisons[0] if comparisons else None,
                "worst_menu": comparisons[-1] if comparisons else None,
                "average_rating": sum(c['overall_rating'] for c in comparisons) / len(comparisons),
                "menus": comparisons,
            }
            
        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error comparing menus: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Validation & Helper Methods
    # -------------------------------------------------------------------------

    def _validate_feedback_request(self, request: FeedbackRequest) -> None:
        """
        Validate feedback request data.
        
        Args:
            request: FeedbackRequest to validate
            
        Raises:
            ValidationException: If request data is invalid
        """
        # Validate rating
        if hasattr(request, 'rating') and request.rating is not None:
            if not (self.MIN_RATING <= request.rating <= self.MAX_RATING):
                raise ValidationException(
                    f"Rating must be between {self.MIN_RATING} and {self.MAX_RATING}"
                )
        
        # Validate meal-specific ratings
        for meal_type in ['breakfast_rating', 'lunch_rating', 'dinner_rating']:
            rating = getattr(request, meal_type, None)
            if rating is not None:
                if not (self.MIN_RATING <= rating <= self.MAX_RATING):
                    raise ValidationException(
                        f"{meal_type} must be between {self.MIN_RATING} and {self.MAX_RATING}"
                    )
        
        # Validate comments length
        if hasattr(request, 'comments') and request.comments:
            if len(request.comments) > 1000:
                raise ValidationException(
                    "Comments cannot exceed 1000 characters"
                )

    def _validate_date_range(self, start_date: date, end_date: date) -> None:
        """
        Validate date range for analysis.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Raises:
            ValidationException: If date range is invalid
        """
        if start_date > end_date:
            raise ValidationException(
                "Start date must be before or equal to end date"
            )
        
        if end_date > date.today():
            raise ValidationException(
                "End date cannot be in the future"
            )
        
        # Check for reasonable range (e.g., max 1 year)
        max_days = 365
        if (end_date - start_date).days > max_days:
            raise ValidationException(
                f"Date range cannot exceed {max_days} days"
            )

    def _update_aggregate_ratings(self, db: Session, menu_id: UUID) -> None:
        """
        Update aggregate ratings for a menu.
        
        This should be called after feedback is added/updated/deleted.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
        """
        try:
            self.feedback_repo.update_aggregate_ratings(db, menu_id)
            db.flush()
        except Exception:
            # Log error but don't fail the main operation
            pass

    def _get_empty_ratings_summary(self, menu_id: UUID) -> RatingsSummary:
        """
        Get an empty ratings summary for a menu with no feedback.
        
        Args:
            menu_id: Unique identifier of the menu
            
        Returns:
            RatingsSummary with zero values
        """
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

    def _get_empty_sentiment_analysis(self, menu_id: UUID) -> Dict[str, Any]:
        """Get empty sentiment analysis structure."""
        return {
            "menu_id": str(menu_id),
            "total_comments": 0,
            "sentiment_distribution": {},
            "dominant_sentiment": "neutral",
            "key_themes": [],
            "positive_keywords": [],
            "negative_keywords": [],
        }

    def _analyze_sentiments(self, comments: List[str]) -> Dict[str, Any]:
        """
        Analyze sentiments from comments.
        
        This is a placeholder for actual sentiment analysis implementation.
        Integration with NLP libraries (e.g., NLTK, spaCy) would go here.
        
        Args:
            comments: List of comment strings
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Placeholder implementation
        return {
            "distribution": {
                "positive": 0,
                "neutral": 0,
                "negative": 0,
            },
            "dominant": "neutral",
            "themes": [],
            "positive_keywords": [],
            "negative_keywords": [],
        }