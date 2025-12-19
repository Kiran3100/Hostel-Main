# --- File: complaint_feedback_repository.py ---
"""
Complaint feedback repository with satisfaction tracking and sentiment analysis.

Handles feedback collection, rating analysis, and satisfaction metrics
for complaint resolution quality monitoring.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.complaint.complaint_feedback import ComplaintFeedback
from app.models.complaint.complaint import Complaint
from app.repositories.base.base_repository import BaseRepository


class ComplaintFeedbackRepository(BaseRepository[ComplaintFeedback]):
    """
    Complaint feedback repository with satisfaction analytics.
    
    Provides feedback management, rating analysis, and sentiment tracking
    for service quality improvement.
    """

    def __init__(self, session: Session):
        """
        Initialize complaint feedback repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ComplaintFeedback, session)

    # ==================== CRUD Operations ====================

    def create_feedback(
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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ComplaintFeedback:
        """
        Create new complaint feedback.
        
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
            metadata: Additional metadata
            
        Returns:
            Created feedback instance
        """
        feedback = ComplaintFeedback(
            complaint_id=complaint_id,
            submitted_by=submitted_by,
            submitted_at=datetime.now(timezone.utc),
            rating=rating,
            feedback_text=feedback_text,
            issue_resolved_satisfactorily=issue_resolved_satisfactorily,
            response_time_satisfactory=response_time_satisfactory,
            staff_helpful=staff_helpful,
            would_recommend=would_recommend,
            resolution_quality_rating=resolution_quality_rating,
            communication_rating=communication_rating,
            professionalism_rating=professionalism_rating,
            improvement_suggestions=improvement_suggestions,
            positive_aspects=positive_aspects,
            metadata=metadata or {},
        )
        
        # Calculate sentiment (simplified)
        sentiment_score, sentiment_label = self._calculate_sentiment(
            rating=rating,
            feedback_text=feedback_text,
            satisfaction_flags=[
                issue_resolved_satisfactorily,
                response_time_satisfactory,
                staff_helpful,
            ],
        )
        
        feedback.sentiment_score = sentiment_score
        feedback.sentiment_label = sentiment_label
        
        # Check if follow-up needed
        feedback.follow_up_required = self._check_follow_up_needed(
            rating=rating,
            issue_resolved_satisfactorily=issue_resolved_satisfactorily,
            sentiment_label=sentiment_label,
        )
        
        return self.create(feedback)

    def verify_feedback(
        self,
        feedback_id: str,
        verified_by: str,
    ) -> Optional[ComplaintFeedback]:
        """
        Verify feedback as authentic.
        
        Args:
            feedback_id: Feedback identifier
            verified_by: User verifying feedback
            
        Returns:
            Updated feedback or None
        """
        update_data = {
            "is_verified": True,
            "verified_at": datetime.now(timezone.utc),
            "verified_by": verified_by,
        }
        
        return self.update(feedback_id, update_data)

    # ==================== Query Operations ====================

    def find_by_complaint(
        self,
        complaint_id: str,
    ) -> Optional[ComplaintFeedback]:
        """
        Find feedback for a specific complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Feedback instance or None
        """
        query = select(ComplaintFeedback).where(
            ComplaintFeedback.complaint_id == complaint_id
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_by_hostel(
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
        Find feedback for hostel complaints.
        
        Args:
            hostel_id: Hostel identifier
            verified_only: Only verified feedback
            min_rating: Minimum rating filter
            max_rating: Maximum rating filter
            date_from: Start date filter
            date_to: End date filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of feedback records
        """
        query = (
            select(ComplaintFeedback)
            .join(Complaint)
            .where(Complaint.hostel_id == hostel_id)
        )
        
        if verified_only:
            query = query.where(ComplaintFeedback.is_verified == True)
        
        if min_rating is not None:
            query = query.where(ComplaintFeedback.rating >= min_rating)
        
        if max_rating is not None:
            query = query.where(ComplaintFeedback.rating <= max_rating)
        
        if date_from:
            query = query.where(ComplaintFeedback.submitted_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintFeedback.submitted_at <= date_to)
        
        query = query.order_by(desc(ComplaintFeedback.submitted_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_sentiment(
        self,
        sentiment_label: str,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintFeedback]:
        """
        Find feedback by sentiment classification.
        
        Args:
            sentiment_label: Sentiment (POSITIVE, NEGATIVE, NEUTRAL)
            hostel_id: Optional hostel filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of feedback with matching sentiment
        """
        query = select(ComplaintFeedback).where(
            ComplaintFeedback.sentiment_label == sentiment_label
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        query = query.order_by(desc(ComplaintFeedback.submitted_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_requiring_follow_up(
        self,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintFeedback]:
        """
        Find feedback requiring follow-up action.
        
        Args:
            hostel_id: Optional hostel filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of feedback needing follow-up
        """
        query = select(ComplaintFeedback).where(
            ComplaintFeedback.follow_up_required == True
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        query = query.order_by(desc(ComplaintFeedback.submitted_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics ====================

    def get_satisfaction_metrics(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate satisfaction metrics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with satisfaction metrics
        """
        query = select(ComplaintFeedback)
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(ComplaintFeedback.submitted_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintFeedback.submitted_at <= date_to)
        
        result = self.session.execute(query)
        feedbacks = list(result.scalars().all())
        
        if not feedbacks:
            return {
                "total_feedback": 0,
                "average_rating": None,
                "satisfaction_rate": 0,
                "nps_score": None,
            }
        
        total = len(feedbacks)
        
        # Average rating
        avg_rating = sum(f.rating for f in feedbacks) / total
        
        # Satisfaction rate (ratings 4-5)
        satisfied = len([f for f in feedbacks if f.rating >= 4])
        satisfaction_rate = (satisfied / total * 100)
        
        # NPS calculation
        promoters = len([f for f in feedbacks if f.would_recommend is True])
        detractors = len([f for f in feedbacks if f.would_recommend is False])
        nps_responses = promoters + detractors
        nps_score = (
            ((promoters - detractors) / nps_responses * 100)
            if nps_responses > 0 else None
        )
        
        # Satisfaction breakdown
        satisfaction_breakdown = {
            "issue_resolved": len([f for f in feedbacks if f.issue_resolved_satisfactorily]) / total * 100,
            "response_time": len([f for f in feedbacks if f.response_time_satisfactory]) / total * 100,
            "staff_helpful": len([f for f in feedbacks if f.staff_helpful]) / total * 100,
        }
        
        # Rating distribution
        rating_dist = {}
        for i in range(1, 6):
            rating_dist[i] = len([f for f in feedbacks if f.rating == i])
        
        # Sentiment distribution
        sentiment_dist = {
            "POSITIVE": len([f for f in feedbacks if f.sentiment_label == "POSITIVE"]),
            "NEGATIVE": len([f for f in feedbacks if f.sentiment_label == "NEGATIVE"]),
            "NEUTRAL": len([f for f in feedbacks if f.sentiment_label == "NEUTRAL"]),
        }
        
        return {
            "total_feedback": total,
            "average_rating": round(avg_rating, 2),
            "satisfaction_rate": round(satisfaction_rate, 2),
            "nps_score": round(nps_score, 2) if nps_score is not None else None,
            "satisfaction_breakdown": satisfaction_breakdown,
            "rating_distribution": rating_dist,
            "sentiment_distribution": sentiment_dist,
        }

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
            Dictionary with average detailed ratings
        """
        query = select(ComplaintFeedback)
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(ComplaintFeedback.submitted_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintFeedback.submitted_at <= date_to)
        
        result = self.session.execute(query)
        feedbacks = list(result.scalars().all())
        
        # Filter feedbacks with detailed ratings
        resolution_ratings = [
            f.resolution_quality_rating for f in feedbacks
            if f.resolution_quality_rating is not None
        ]
        
        communication_ratings = [
            f.communication_rating for f in feedbacks
            if f.communication_rating is not None
        ]
        
        professionalism_ratings = [
            f.professionalism_rating for f in feedbacks
            if f.professionalism_rating is not None
        ]
        
        return {
            "resolution_quality": (
                round(sum(resolution_ratings) / len(resolution_ratings), 2)
                if resolution_ratings else None
            ),
            "communication": (
                round(sum(communication_ratings) / len(communication_ratings), 2)
                if communication_ratings else None
            ),
            "professionalism": (
                round(sum(professionalism_ratings) / len(professionalism_ratings), 2)
                if professionalism_ratings else None
            ),
        }

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
            List of daily feedback metrics
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        query = (
            select(
                func.date(ComplaintFeedback.submitted_at).label("date"),
                func.count(ComplaintFeedback.id).label("count"),
                func.avg(ComplaintFeedback.rating).label("avg_rating"),
            )
            .where(ComplaintFeedback.submitted_at >= start_date)
            .group_by(func.date(ComplaintFeedback.submitted_at))
            .order_by(func.date(ComplaintFeedback.submitted_at))
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        return [
            {
                "date": row.date.isoformat(),
                "total_feedback": row.count,
                "average_rating": round(float(row.avg_rating), 2),
            }
            for row in result
        ]

    # ==================== Helper Methods ====================

    def _calculate_sentiment(
        self,
        rating: int,
        feedback_text: Optional[str],
        satisfaction_flags: List[bool],
    ) -> Tuple[float, str]:
        """
        Calculate sentiment score and label.
        
        Args:
            rating: Overall rating
            feedback_text: Feedback text
            satisfaction_flags: List of satisfaction booleans
            
        Returns:
            Tuple of (sentiment_score, sentiment_label)
        """
        # Rating-based score (-1 to 1)
        rating_score = (rating - 3) / 2  # Maps 1->-1, 3->0, 5->1
        
        # Satisfaction flags score
        satisfaction_score = (
            (sum(satisfaction_flags) / len(satisfaction_flags) - 0.5) * 2
            if satisfaction_flags else 0
        )
        
        # Combined score (weighted average)
        sentiment_score = (rating_score * 0.6 + satisfaction_score * 0.4)
        
        # Classify sentiment
        if sentiment_score > 0.3:
            sentiment_label = "POSITIVE"
        elif sentiment_score < -0.3:
            sentiment_label = "NEGATIVE"
        else:
            sentiment_label = "NEUTRAL"
        
        return round(sentiment_score, 2), sentiment_label

    def _check_follow_up_needed(
        self,
        rating: int,
        issue_resolved_satisfactorily: bool,
        sentiment_label: str,
    ) -> bool:
        """
        Determine if follow-up is needed.
        
        Args:
            rating: Overall rating
            issue_resolved_satisfactorily: Resolution satisfaction
            sentiment_label: Sentiment classification
            
        Returns:
            True if follow-up needed
        """
        # Low rating requires follow-up
        if rating <= 2:
            return True
        
        # Issue not resolved satisfactorily
        if not issue_resolved_satisfactorily:
            return True
        
        # Negative sentiment
        if sentiment_label == "NEGATIVE":
            return True
        
        return False