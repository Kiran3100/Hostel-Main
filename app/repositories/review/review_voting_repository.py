"""
Review Voting Repository - Helpfulness voting and engagement tracking.

Implements voting operations, helpfulness scoring, and engagement analytics.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session

from app.models.review.review_voting import (
    ReviewVote,
    ReviewHelpfulnessScore,
    ReviewEngagement,
)
from app.models.common.enums import VoteType
from app.repositories.base import BaseRepository, PaginatedResult


class ReviewVotingRepository(BaseRepository[ReviewVote]):
    """
    Repository for review voting and engagement operations.
    
    Manages helpfulness voting, Wilson score calculations,
    and comprehensive engagement tracking.
    """
    
    def __init__(self, session: Session):
        """
        Initialize review voting repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ReviewVote, session)
    
    # ==================== Vote Operations ====================
    
    def cast_vote(
        self,
        review_id: UUID,
        voter_id: UUID,
        vote_type: VoteType,
        feedback: Optional[str] = None,
        vote_weight: Decimal = Decimal('1.0'),
        is_verified_voter: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ReviewVote:
        """
        Cast or update vote on review.
        
        Args:
            review_id: Review being voted on
            voter_id: User casting vote
            vote_type: Vote type (helpful/not_helpful)
            feedback: Optional feedback with vote
            vote_weight: Weight of vote (for credibility-based weighting)
            is_verified_voter: Whether voter is verified
            ip_address: Voter IP address
            user_agent: Voter user agent
            
        Returns:
            Created or updated vote
        """
        # Check for existing vote
        existing_vote = self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id,
            ReviewVote.voter_id == voter_id
        ).first()
        
        if existing_vote:
            # Update existing vote
            old_vote_type = existing_vote.vote_type
            existing_vote.change_vote(vote_type)
            if feedback:
                existing_vote.feedback = feedback
            
            self.session.commit()
            self.session.refresh(existing_vote)
            
            # Update helpfulness score
            self._update_helpfulness_score(review_id)
            
            return existing_vote
        
        # Create new vote
        vote = ReviewVote(
            review_id=review_id,
            voter_id=voter_id,
            vote_type=vote_type,
            feedback=feedback,
            vote_weight=vote_weight,
            is_verified_voter=is_verified_voter,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.session.add(vote)
        self.session.commit()
        self.session.refresh(vote)
        
        # Update helpfulness score
        self._update_helpfulness_score(review_id)
        
        return vote
    
    def remove_vote(
        self,
        review_id: UUID,
        voter_id: UUID
    ) -> bool:
        """
        Remove vote from review.
        
        Args:
            review_id: Review ID
            voter_id: Voter ID
            
        Returns:
            True if vote was removed
        """
        vote = self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id,
            ReviewVote.voter_id == voter_id
        ).first()
        
        if not vote:
            return False
        
        self.session.delete(vote)
        self.session.commit()
        
        # Update helpfulness score
        self._update_helpfulness_score(review_id)
        
        return True
    
    def get_user_vote(
        self,
        review_id: UUID,
        voter_id: UUID
    ) -> Optional[ReviewVote]:
        """
        Get user's vote on review.
        
        Args:
            review_id: Review ID
            voter_id: Voter ID
            
        Returns:
            Vote if exists, None otherwise
        """
        return self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id,
            ReviewVote.voter_id == voter_id
        ).first()
    
    def get_review_votes(
        self,
        review_id: UUID,
        vote_type: Optional[VoteType] = None
    ) -> List[ReviewVote]:
        """
        Get all votes for review.
        
        Args:
            review_id: Review ID
            vote_type: Optional vote type filter
            
        Returns:
            List of votes
        """
        query = self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id
        )
        
        if vote_type:
            query = query.filter(ReviewVote.vote_type == vote_type)
        
        return query.order_by(desc(ReviewVote.created_at)).all()
    
    def get_vote_statistics(
        self,
        review_id: UUID
    ) -> Dict[str, Any]:
        """
        Get vote statistics for review.
        
        Args:
            review_id: Review ID
            
        Returns:
            Dictionary with vote statistics
        """
        helpful_count = self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id,
            ReviewVote.vote_type == VoteType.HELPFUL
        ).count()
        
        not_helpful_count = self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id,
            ReviewVote.vote_type == VoteType.NOT_HELPFUL
        ).count()
        
        total_votes = helpful_count + not_helpful_count
        
        verified_votes = self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id,
            ReviewVote.is_verified_voter == True
        ).count()
        
        return {
            'helpful_count': helpful_count,
            'not_helpful_count': not_helpful_count,
            'total_votes': total_votes,
            'verified_votes': verified_votes,
            'helpfulness_percentage': (helpful_count / total_votes * 100) if total_votes > 0 else 0
        }
    
    # ==================== Helpfulness Score Operations ====================
    
    def get_helpfulness_score(
        self,
        review_id: UUID
    ) -> Optional[ReviewHelpfulnessScore]:
        """
        Get helpfulness score for review.
        
        Args:
            review_id: Review ID
            
        Returns:
            Helpfulness score if exists
        """
        return self.session.query(ReviewHelpfulnessScore).filter(
            ReviewHelpfulnessScore.review_id == review_id
        ).first()
    
    def calculate_wilson_score(
        self,
        review_id: UUID,
        confidence: float = 0.95
    ) -> ReviewHelpfulnessScore:
        """
        Calculate and update Wilson score for review.
        
        Args:
            review_id: Review ID
            confidence: Confidence level for Wilson score
            
        Returns:
            Updated helpfulness score
        """
        # Get or create helpfulness score
        score = self.get_helpfulness_score(review_id)
        if not score:
            score = ReviewHelpfulnessScore(review_id=review_id)
            self.session.add(score)
        
        # Get vote counts
        helpful_count = self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id,
            ReviewVote.vote_type == VoteType.HELPFUL
        ).count()
        
        not_helpful_count = self.session.query(ReviewVote).filter(
            ReviewVote.review_id == review_id,
            ReviewVote.vote_type == VoteType.NOT_HELPFUL
        ).count()
        
        # Update counts and calculate scores
        score.update_counts(helpful_count, not_helpful_count)
        
        self.session.commit()
        self.session.refresh(score)
        
        return score
    
    def get_top_helpful_reviews(
        self,
        hostel_id: Optional[UUID] = None,
        limit: int = 10
    ) -> List[ReviewHelpfulnessScore]:
        """
        Get top helpful reviews by Wilson score.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Maximum number of results
            
        Returns:
            List of top helpful reviews
        """
        query = self.session.query(ReviewHelpfulnessScore)
        
        if hostel_id:
            from app.models.review import Review
            query = query.join(Review).filter(Review.hostel_id == hostel_id)
        
        return query.order_by(
            desc(ReviewHelpfulnessScore.wilson_score)
        ).limit(limit).all()
    
    def update_helpfulness_rankings(
        self,
        hostel_id: Optional[UUID] = None
    ):
        """
        Update helpfulness rankings for reviews.
        
        Args:
            hostel_id: Optional hostel filter
        """
        from app.models.review import Review
        
        query = self.session.query(ReviewHelpfulnessScore)
        
        if hostel_id:
            query = query.join(Review).filter(Review.hostel_id == hostel_id)
        
        # Get all scores ordered by Wilson score
        scores = query.order_by(
            desc(ReviewHelpfulnessScore.wilson_score)
        ).all()
        
        # Update rankings
        for rank, score in enumerate(scores, start=1):
            if hostel_id:
                score.hostel_rank = rank
            else:
                score.global_rank = rank
        
        self.session.commit()
    
    # ==================== Engagement Operations ====================
    
    def track_view(
        self,
        review_id: UUID,
        viewer_id: Optional[UUID] = None,
        is_unique: bool = False
    ) -> ReviewEngagement:
        """
        Track review view.
        
        Args:
            review_id: Review being viewed
            viewer_id: Optional viewer ID
            is_unique: Whether this is a unique view
            
        Returns:
            Updated engagement record
        """
        engagement = self._get_or_create_engagement(review_id)
        engagement.increment_view(is_unique)
        
        self.session.commit()
        self.session.refresh(engagement)
        
        return engagement
    
    def track_read_time(
        self,
        review_id: UUID,
        read_time_seconds: float
    ) -> ReviewEngagement:
        """
        Track time spent reading review.
        
        Args:
            review_id: Review ID
            read_time_seconds: Time spent reading in seconds
            
        Returns:
            Updated engagement record
        """
        engagement = self._get_or_create_engagement(review_id)
        engagement.add_read_time(read_time_seconds)
        
        self.session.commit()
        self.session.refresh(engagement)
        
        return engagement
    
    def track_share(
        self,
        review_id: UUID
    ) -> ReviewEngagement:
        """
        Track review share.
        
        Args:
            review_id: Review ID
            
        Returns:
            Updated engagement record
        """
        engagement = self._get_or_create_engagement(review_id)
        engagement.share_count += 1
        
        self.session.commit()
        self.session.refresh(engagement)
        
        return engagement
    
    def track_bookmark(
        self,
        review_id: UUID
    ) -> ReviewEngagement:
        """
        Track review bookmark.
        
        Args:
            review_id: Review ID
            
        Returns:
            Updated engagement record
        """
        engagement = self._get_or_create_engagement(review_id)
        engagement.bookmark_count += 1
        
        self.session.commit()
        self.session.refresh(engagement)
        
        return engagement
    
    def track_booking_influence(
        self,
        review_id: UUID
    ) -> ReviewEngagement:
        """
        Track booking influenced by review.
        
        Args:
            review_id: Review ID
            
        Returns:
            Updated engagement record
        """
        engagement = self._get_or_create_engagement(review_id)
        engagement.influenced_bookings += 1
        
        self.session.commit()
        self.session.refresh(engagement)
        
        return engagement
    
    def track_inquiry_influence(
        self,
        review_id: UUID
    ) -> ReviewEngagement:
        """
        Track inquiry influenced by review.
        
        Args:
            review_id: Review ID
            
        Returns:
            Updated engagement record
        """
        engagement = self._get_or_create_engagement(review_id)
        engagement.influenced_inquiries += 1
        
        self.session.commit()
        self.session.refresh(engagement)
        
        return engagement
    
    def get_engagement_metrics(
        self,
        review_id: UUID
    ) -> Optional[ReviewEngagement]:
        """
        Get engagement metrics for review.
        
        Args:
            review_id: Review ID
            
        Returns:
            Engagement record if exists
        """
        return self.session.query(ReviewEngagement).filter(
            ReviewEngagement.review_id == review_id
        ).first()
    
    def calculate_engagement_score(
        self,
        review_id: UUID
    ) -> ReviewEngagement:
        """
        Calculate engagement score for review.
        
        Args:
            review_id: Review ID
            
        Returns:
            Updated engagement record
        """
        engagement = self._get_or_create_engagement(review_id)
        engagement.calculate_engagement_score()
        
        self.session.commit()
        self.session.refresh(engagement)
        
        return engagement
    
    def get_most_engaged_reviews(
        self,
        hostel_id: Optional[UUID] = None,
        limit: int = 10
    ) -> List[ReviewEngagement]:
        """
        Get most engaged reviews.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Maximum number of results
            
        Returns:
            List of most engaged reviews
        """
        query = self.session.query(ReviewEngagement)
        
        if hostel_id:
            from app.models.review import Review
            query = query.join(Review).filter(Review.hostel_id == hostel_id)
        
        return query.order_by(
            desc(ReviewEngagement.engagement_score)
        ).limit(limit).all()
    
    # ==================== Helper Methods ====================
    
    def _update_helpfulness_score(self, review_id: UUID):
        """Update helpfulness score after vote change."""
        self.calculate_wilson_score(review_id)
    
    def _get_or_create_engagement(
        self,
        review_id: UUID
    ) -> ReviewEngagement:
        """Get or create engagement record."""
        engagement = self.session.query(ReviewEngagement).filter(
            ReviewEngagement.review_id == review_id
        ).first()
        
        if not engagement:
            engagement = ReviewEngagement(review_id=review_id)
            self.session.add(engagement)
        
        return engagement