# --- File: app/schemas/review/review_voting.py ---
"""
Review voting (helpful/not helpful) schemas.

Handles review helpfulness voting and engagement metrics.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- Rating fields use max_digits=2, decimal_places=1 for 1.0-5.0 range
- Percentage fields use max_digits=5, decimal_places=2 for 0.00-100.00 range
- Score fields use max_digits=7, decimal_places=6 for Wilson score precision
- Average fields use appropriate precision for statistical calculations
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from math import sqrt
from typing import Annotated, List, Optional

from pydantic import Field, computed_field
from uuid import UUID

from app.schemas.common.base import BaseSchema, BaseCreateSchema, BaseResponseSchema
from app.schemas.common.enums import VoteType

__all__ = [
    "VoteRequest",
    "VoteResponse",
    "HelpfulnessScore",
    "VoteHistory",
    "VoteHistoryItem",
    "RemoveVote",
    "VotingStats",
]


class VoteRequest(BaseCreateSchema):
    """
    Submit vote on review helpfulness.
    
    Allows users to indicate if a review was helpful.
    """
    
    review_id: UUID = Field(..., description="Review to vote on")
    voter_id: UUID = Field(..., description="User casting the vote")
    
    vote_type: VoteType = Field(
        ...,
        description="Vote type: helpful or not_helpful",
    )
    
    # Optional feedback
    feedback: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional feedback about why vote was cast",
    )


class VoteResponse(BaseSchema):
    """
    Response after vote submission.
    
    Returns updated vote counts.
    """
    
    review_id: UUID = Field(..., description="Voted review ID")
    vote_type: VoteType = Field(..., description="Vote that was cast")
    
    # Updated counts
    helpful_count: int = Field(..., ge=0, description="Updated helpful count")
    not_helpful_count: int = Field(..., ge=0, description="Updated not helpful count")
    
    # User's current vote status
    user_vote: Optional[VoteType] = Field(
        default=None,
        description="User's current vote (may differ if changed)",
    )
    
    message: str = Field(
        ...,
        description="Result message",
        examples=["Vote recorded successfully", "Vote updated"],
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def total_votes(self) -> int:
        """Total votes on the review."""
        return self.helpful_count + self.not_helpful_count
    
    @computed_field  # type: ignore[misc]
    @property
    def helpfulness_percentage(self) -> Decimal:
        """Percentage of helpful votes."""
        if self.total_votes == 0:
            return Decimal("0")
        return Decimal(str(round((self.helpful_count / self.total_votes) * 100, 2)))


class HelpfulnessScore(BaseSchema):
    """
    Helpfulness score for review ranking.
    
    Uses Wilson score for statistically sound ranking.
    """
    
    review_id: UUID = Field(..., description="Review ID")
    
    # Raw counts
    helpful_count: int = Field(..., ge=0, description="Helpful votes")
    not_helpful_count: int = Field(..., ge=0, description="Not helpful votes")
    total_votes: int = Field(..., ge=0, description="Total votes")
    
    # Percentage with proper constraints
    helpfulness_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of helpful votes",
        ),
    ]
    
    # Wilson score for ranking with high precision
    helpfulness_score: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("1"),
            max_digits=7,
            decimal_places=6,
            description="Wilson score for ranking (0-1)",
        ),
    ]
    
    # Rank among hostel's reviews
    rank: Optional[int] = Field(
        default=None,
        ge=1,
        description="Rank among reviews for this hostel",
    )
    
    @classmethod
    def calculate_wilson_score(
        cls,
        helpful: int,
        total: int,
        confidence: float = 0.95,
    ) -> Decimal:
        """
        Calculate Wilson score for review ranking.
        
        Wilson score provides a statistically robust way to rank items
        by positive/negative votes, handling the case where items with
        few votes aren't artificially ranked higher than those with many.
        
        Args:
            helpful: Number of helpful votes
            total: Total number of votes
            confidence: Confidence level (default 0.95 for 95%)
            
        Returns:
            Wilson score as Decimal (0-1)
        """
        if total == 0:
            return Decimal("0")
        
        # Z-score for confidence level (1.96 for 95%)
        z = 1.96 if confidence == 0.95 else 1.645  # 90% confidence
        
        phat = helpful / total
        
        denominator = 1 + (z * z / total)
        numerator = (
            phat
            + (z * z / (2 * total))
            - z * sqrt((phat * (1 - phat) + z * z / (4 * total)) / total)
        )
        
        score = numerator / denominator
        return Decimal(str(round(max(0, min(1, score)), 6)))


class VoteHistoryItem(BaseSchema):
    """
    Individual vote in user's history.
    """
    
    review_id: UUID = Field(..., description="Review that was voted on")
    hostel_id: UUID = Field(..., description="Hostel of the review")
    hostel_name: str = Field(..., description="Hostel name")
    
    review_title: str = Field(..., description="Review title")
    review_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1"),
            le=Decimal("5"),
            max_digits=2,
            decimal_places=1,
            description="Review's overall rating",
        ),
    ]
    
    vote_type: VoteType = Field(..., description="How user voted")
    voted_at: datetime = Field(..., description="When vote was cast")
    
    @computed_field  # type: ignore[misc]
    @property
    def days_ago(self) -> int:
        """Days since vote was cast."""
        delta = datetime.utcnow() - self.voted_at
        return delta.days


class VoteHistory(BaseSchema):
    """
    User's complete voting history.
    
    Tracks all votes cast by a user.
    """
    
    user_id: UUID = Field(..., description="User ID")
    
    # Aggregate stats
    total_votes: int = Field(..., ge=0, description="Total votes cast")
    helpful_votes: int = Field(..., ge=0, description="Helpful votes cast")
    not_helpful_votes: int = Field(..., ge=0, description="Not helpful votes cast")
    
    # Recent activity
    recent_votes: List[VoteHistoryItem] = Field(
        default_factory=list,
        max_length=20,
        description="Most recent votes (max 20)",
    )
    
    # Voting patterns
    most_voted_hostels: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Hostels where user votes most",
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def helpful_vote_percentage(self) -> Decimal:
        """Percentage of helpful votes vs total."""
        if self.total_votes == 0:
            return Decimal("0")
        return Decimal(
            str(round((self.helpful_votes / self.total_votes) * 100, 2))
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def voting_tendency(self) -> str:
        """
        User's voting tendency.
        
        Returns: positive, balanced, or critical
        """
        percentage = float(self.helpful_vote_percentage)
        if percentage >= 70:
            return "positive"
        elif percentage >= 40:
            return "balanced"
        else:
            return "critical"


class RemoveVote(BaseCreateSchema):
    """
    Remove previously cast vote.
    
    Allows users to change their mind about a vote.
    """
    
    review_id: UUID = Field(..., description="Review to remove vote from")
    voter_id: UUID = Field(..., description="User removing their vote")
    
    reason: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional reason for removing vote",
    )


class VotingStats(BaseSchema):
    """
    Voting statistics for a hostel's reviews.
    
    Provides insights into review engagement.
    """
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    
    # Aggregate metrics
    total_votes: int = Field(..., ge=0, description="Total votes across all reviews")
    total_helpful: int = Field(..., ge=0, description="Total helpful votes")
    total_not_helpful: int = Field(..., ge=0, description="Total not helpful votes")
    
    # Per-review metrics
    total_reviews: int = Field(..., ge=0, description="Total reviews")
    reviews_with_votes: int = Field(..., ge=0, description="Reviews that have votes")
    
    # Statistical metrics with proper precision
    average_votes_per_review: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            max_digits=8,
            decimal_places=2,
            description="Average votes per review",
        ),
    ]
    average_helpfulness: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Average helpfulness percentage across reviews",
        ),
    ]
    
    # Top reviews
    most_helpful_review_id: Optional[UUID] = Field(
        default=None,
        description="Review with highest helpfulness score",
    )
    most_voted_review_id: Optional[UUID] = Field(
        default=None,
        description="Review with most total votes",
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def engagement_rate(self) -> Decimal:
        """Percentage of reviews that have votes."""
        if self.total_reviews == 0:
            return Decimal("0")
        return Decimal(
            str(round((self.reviews_with_votes / self.total_reviews) * 100, 2))
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def overall_sentiment(self) -> str:
        """
        Overall voting sentiment.
        
        Returns: positive, neutral, or negative
        """
        if self.total_votes == 0:
            return "neutral"
        
        helpful_ratio = self.total_helpful / self.total_votes
        if helpful_ratio >= 0.7:
            return "positive"
        elif helpful_ratio >= 0.4:
            return "neutral"
        else:
            return "negative"