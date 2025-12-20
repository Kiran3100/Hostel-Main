"""
Complaint feedback and satisfaction tracking service.

Handles feedback collection, rating analysis, sentiment tracking,
and satisfaction metrics for service quality improvement.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.complaint.complaint_feedback import ComplaintFeedback
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_feedback_repository import (
    ComplaintFeedbackRepository,
)
from app.core.exceptions import (
    BusinessLogicError,
    NotFoundError,
    ValidationError,
)


class ComplaintFeedbackService:
    """
    Complaint feedback and satisfaction service.
    
    Manages feedback collection, rating analysis, and satisfaction
    tracking for complaint resolution quality monitoring.
    """

    def __init__(self, session: Session):
        """
        Initialize feedback service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)
        self.feedback_repo = ComplaintFeedbackRepository(session)

    # ==================== Feedback Creation ====================

    def submit_feedback(
        self,
        complaint_id: str,
        submitted_by: str,
        rating: int,
        issue_resolved_satisfactorily: bool,
        response_time_satisfactory: bool,
        staff_helpful: bool,
        feedback_text: Optional[str] = None,
        would_recommend: Optional[bool] = None,
        resolution_quality_rating: Optional[int] = None,
        communication_rating: Optional[int] = None,
        professionalism_rating: Optional[int] = None,
        improvement_suggestions: Optional[str] = None,
        positive_aspects: Optional[str] = None,
    ) -> ComplaintFeedback:
        """
        Submit feedback for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            submitted_by: User submitting feedback
            rating: Overall rating (1-5)
            issue_resolved_satisfactorily: Resolution satisfaction
            response_time_satisfactory: Response time satisfaction
            staff_helpful: Staff helpfulness
            feedback_text: Detailed feedback
            would_recommend: Recommendation flag
            resolution_quality_rating: Resolution quality (1-5)
            communication_rating: Communication quality (1-5)
            professionalism_rating: Professionalism (1-5)
            improvement_suggestions: Improvement suggestions
            positive_aspects: Positive feedback
            
        Returns:
            Created feedback instance
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If feedback data invalid
            BusinessLogicError: If feedback already exists
        """
        # Verify complaint exists and is resolved
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        from app.models.base.enums import ComplaintStatus
        if complaint.status not in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]:
            raise BusinessLogicError("Feedback can only be submitted for resolved complaints")
        
        # Check if feedback already exists
        existing = self.feedback_repo.find_by_complaint(complaint_id)
        if existing:
            raise BusinessLogicError("Feedback already submitted for this complaint")
        
        # Validate rating
        if not (1 <= rating <= 5):
            raise ValidationError("Rating must be between 1 and 5")
        
        # Validate detailed ratings if provided
        if resolution_quality_rating and not (1 <= resolution_quality_rating <= 5):
            raise ValidationError("Resolution quality rating must be between 1 and 5")
        
        if communication_rating and not (1 <= communication_rating <= 5):
            raise ValidationError("Communication rating must be between 1 and 5")
        
        if professionalism_rating and not (1 <= professionalism_rating <= 5):
            raise ValidationError("Professionalism rating must be between 1 and 5")
        
        # Create feedback
        feedback = self.feedback_repo.create_feedback(
            complaint_id=complaint_id,
            submitted_by=submitted_by,
            rating=rating,
            issue_resolved_satisfactorily=issue_resolved_satisfactorily,
            response_time_satisfactory=response_time_satisfactory,
            staff_helpful=staff_helpful,
            feedback_text=feedback_text,
            would_recommend=would_recommend,
            resolution_quality_rating=resolution_quality_rating,
            communication_rating=communication_rating,
            professionalism_rating=professionalism_rating,
            improvement_suggestions=improvement_suggestions,
            positive_aspects=positive_aspects,
        )
        
        # Update complaint with feedback info
        self.complaint_repo.update(complaint_id, {
            "student_feedback": feedback_text,
            "student_rating": rating,
            "feedback_submitted_at": datetime.now(timezone.utc),
        })
        
        self.session.commit()
        self.session.refresh(feedback)
        
        # Check if follow-up needed
        if feedback.follow_up_required:
            self._trigger_follow_up_workflow(feedback)
        
        return feedback

    def update_feedback(
        self,
        feedback_id: str,
        user_id: str,
        rating: Optional[int] = None,
        feedback_text: Optional[str] = None,
        resolution_quality_rating: Optional[int] = None,
        communication_rating: Optional[int] = None,
        professionalism_rating: Optional[int] = None,
        improvement_suggestions: Optional[str] = None,
        positive_aspects: Optional[str] = None,
    ) -> ComplaintFeedback:
        """
        Update existing feedback.
        
        Args:
            feedback_id: Feedback identifier
            user_id: User updating feedback
            rating: Updated overall rating
            feedback_text: Updated feedback text
            resolution_quality_rating: Updated resolution rating
            communication_rating: Updated communication rating
            professionalism_rating: Updated professionalism rating
            improvement_suggestions: Updated suggestions
            positive_aspects: Updated positive aspects
            
        Returns:
            Updated feedback
            
        Raises:
            NotFoundError: If feedback not found
            BusinessLogicError: If update not allowed
        """
        feedback = self.feedback_repo.find_by_id(feedback_id)
        if not feedback:
            raise NotFoundError(f"Feedback {feedback_id} not found")
        
        # Verify user submitted the feedback
        if feedback.submitted_by != user_id:
            raise BusinessLogicError("Only feedback submitter can update")
        
        # Prepare update data
        update_data = {}
        
        if rating is not None:
            if not (1 <= rating <= 5):
                raise ValidationError("Rating must be between 1 and 5")
            update_data["rating"] = rating
        
        if feedback_text is not None:
            update_data["feedback_text"] = feedback_text
        
        if resolution_quality_rating is not None:
            if not (1 <= resolution_quality_rating <= 5):
                raise ValidationError("Resolution quality rating must be between 1 and 5")
            update_data["resolution_quality_rating"] = resolution_quality_rating
        
        if communication_rating is not None:
            if not (1 <= communication_rating <= 5):
                raise ValidationError("Communication rating must be between 1 and 5")
            update_data["communication_rating"] = communication_rating
        
        if professionalism_rating is not None:
            if not (1 <= professionalism_rating <= 5):
                raise ValidationError("Professionalism rating must be between 1 and 5")
            update_data["professionalism_rating"] = professionalism_rating
        
        if improvement_suggestions is not None:
            update_data["improvement_suggestions"] = improvement_suggestions
        
        if positive_aspects is not None:
            update_data["positive_aspects"] = positive_aspects
        
        # Update feedback
        updated = self.feedback_repo.update(feedback_id, update_data)
        
        self.session.commit()
        self.session.refresh(updated)
        
        return updated

    # ==================== Verification ====================

    def verify_feedback(
        self,
        feedback_id: str,
        verified_by: str,
    ) -> ComplaintFeedback:
        """
        Verify feedback as authentic.
        
        Args:
            feedback_id: Feedback identifier
            verified_by: User verifying feedback
            
        Returns:
            Verified feedback
            
        Raises:
            NotFoundError: If feedback not found
        """
        feedback = self.feedback_repo.find_by_id(feedback_id)
        if not feedback:
            raise NotFoundError(f"Feedback {feedback_id} not found")
        
        if feedback.is_verified:
            raise BusinessLogicError("Feedback already verified")
        
        verified = self.feedback_repo.verify_feedback(
            feedback_id=feedback_id,
            verified_by=verified_by,
        )
        
        self.session.commit()
        self.session.refresh(verified)
        
        return verified

    # ==================== Query Operations ====================

    def get_feedback(
        self,
        feedback_id: str,
    ) -> Optional[ComplaintFeedback]:
        """
        Get feedback by ID.
        
        Args:
            feedback_id: Feedback identifier
            
        Returns:
            Feedback instance or None
        """
        return self.feedback_repo.find_by_id(feedback_id)

    def get_complaint_feedback(
        self,
        complaint_id: str,
    ) -> Optional[ComplaintFeedback]:
        """
        Get feedback for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Feedback instance or None
        """
        return self.feedback_repo.find_by_complaint(complaint_id)

    def has_feedback(
        self,
        complaint_id: str,
    ) -> bool:
        """
        Check if complaint has feedback.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            True if feedback exists
        """
        return self.feedback_repo.find_by_complaint(complaint_id) is not None

    def get_hostel_feedback(
        self,
        hostel_id: str,
        verified_only: bool = False,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintFeedback]:
        """
        Get feedback for hostel complaints.
        
        Args:
            hostel_id: Hostel identifier
            verified_only: Only verified feedback
            min_rating: Minimum rating filter
            max_rating: Maximum rating filter
            date_from: Start date filter
            date_to: End date filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of feedback records
        """
        return self.feedback_repo.find_by_hostel(
            hostel_id=hostel_id,
            verified_only=verified_only,
            min_rating=min_rating,
            max_rating=max_rating,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )

    def get_feedback_by_sentiment(
        self,
        sentiment_label: str,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintFeedback]:
        """
        Get feedback by sentiment.
        
        Args:
            sentiment_label: POSITIVE, NEGATIVE, NEUTRAL
            hostel_id: Optional hostel filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of feedback with sentiment
        """
        return self.feedback_repo.find_by_sentiment(
            sentiment_label=sentiment_label,
            hostel_id=hostel_id,
            skip=skip,
            limit=limit,
        )

    def get_feedback_requiring_follow_up(
        self,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintFeedback]:
        """
        Get feedback requiring follow-up.
        
        Args:
            hostel_id: Optional hostel filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of feedback needing follow-up
        """
        return self.feedback_repo.find_requiring_follow_up(
            hostel_id=hostel_id,
            skip=skip,
            limit=limit,
        )

    # ==================== Analytics ====================

    def get_satisfaction_metrics(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get satisfaction metrics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Satisfaction metrics dictionary
        """
        return self.feedback_repo.get_satisfaction_metrics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_detailed_ratings(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Get average detailed ratings.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Detailed ratings averages
        """
        return self.feedback_repo.get_detailed_ratings(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_feedback_trends(
        self,
        hostel_id: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get feedback trends over time.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Daily feedback metrics
        """
        return self.feedback_repo.get_feedback_trends(
            hostel_id=hostel_id,
            days=days,
        )

    def get_nps_score(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Calculate Net Promoter Score (NPS).
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            NPS score (-100 to 100) or None
        """
        metrics = self.get_satisfaction_metrics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        return metrics.get("nps_score")

    def get_satisfaction_summary(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive satisfaction summary.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Satisfaction summary
        """
        metrics = self.get_satisfaction_metrics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        detailed_ratings = self.get_detailed_ratings(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        return {
            "overall_metrics": metrics,
            "detailed_ratings": detailed_ratings,
        }

    # ==================== Reports ====================

    def get_low_rating_feedback(
        self,
        hostel_id: Optional[str] = None,
        rating_threshold: int = 2,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintFeedback]:
        """
        Get low-rated feedback for attention.
        
        Args:
            hostel_id: Optional hostel filter
            rating_threshold: Maximum rating to include
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of low-rated feedback
        """
        return self.feedback_repo.find_by_hostel(
            hostel_id=hostel_id,
            max_rating=rating_threshold,
            skip=skip,
            limit=limit,
        )

    def get_improvement_suggestions(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all improvement suggestions from feedback.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            List of feedback with suggestions
        """
        feedbacks = self.feedback_repo.find_by_hostel(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
            limit=1000,
        )
        
        suggestions = []
        for feedback in feedbacks:
            if feedback.improvement_suggestions:
                suggestions.append({
                    "complaint_id": feedback.complaint_id,
                    "rating": feedback.rating,
                    "suggestion": feedback.improvement_suggestions,
                    "submitted_at": feedback.submitted_at,
                })
        
        return suggestions

    def get_positive_feedback_highlights(
        self,
        hostel_id: Optional[str] = None,
        min_rating: int = 4,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get positive feedback highlights.
        
        Args:
            hostel_id: Optional hostel filter
            min_rating: Minimum rating for positive
            date_from: Start date filter
            date_to: End date filter
            limit: Maximum highlights
            
        Returns:
            List of positive highlights
        """
        feedbacks = self.feedback_repo.find_by_hostel(
            hostel_id=hostel_id,
            min_rating=min_rating,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        
        highlights = []
        for feedback in feedbacks:
            if feedback.positive_aspects:
                highlights.append({
                    "complaint_id": feedback.complaint_id,
                    "rating": feedback.rating,
                    "highlight": feedback.positive_aspects,
                    "submitted_at": feedback.submitted_at,
                })
        
        return highlights

    # ==================== Helper Methods ====================

    def _trigger_follow_up_workflow(
        self,
        feedback: ComplaintFeedback,
    ) -> None:
        """
        Trigger follow-up workflow for feedback.
        
        Args:
            feedback: Feedback instance
        """
        # Would integrate with workflow/notification service
        print(f"Triggering follow-up for feedback {feedback.id}")
        
        # Could create a task, send notification, etc.
        # For low ratings, might want to alert management
        if feedback.rating <= 2:
            print(f"ALERT: Low rating feedback ({feedback.rating}) for complaint {feedback.complaint_id}")

    def analyze_feedback_sentiment(
        self,
        feedback_id: str,
    ) -> Dict[str, Any]:
        """
        Analyze feedback sentiment (placeholder for ML integration).
        
        Args:
            feedback_id: Feedback identifier
            
        Returns:
            Sentiment analysis results
        """
        feedback = self.feedback_repo.find_by_id(feedback_id)
        if not feedback:
            return {}
        
        # Placeholder - would integrate with actual sentiment analysis
        return {
            "sentiment_score": feedback.sentiment_score,
            "sentiment_label": feedback.sentiment_label,
            "confidence": 0.85,  # Mock confidence score
        }