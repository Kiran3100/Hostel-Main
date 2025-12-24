"""
Review Voting Service

Handles helpful/not-helpful voting on reviews.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.review import ReviewVotingRepository
from app.schemas.review import (
    VoteRequest,
    VoteResponse,
    RemoveVote,
    VoteHistory,
    VoteHistoryItem,
    VotingStats,
)
from app.core.exceptions import ValidationException, BusinessLogicException


class ReviewVotingService:
    """
    High-level service for review helpfulness voting.

    Responsibilities:
    - Cast/replace a vote
    - Remove a vote
    - Retrieve voting history
    - Get voting stats per hostel
    """

    def __init__(self, voting_repo: ReviewVotingRepository) -> None:
        self.voting_repo = voting_repo

    def cast_vote(
        self,
        db: Session,
        user_id: UUID,
        request: VoteRequest,
    ) -> VoteResponse:
        """
        Submit or update a vote on a review.
        """
        if request.value not in ("helpful", "not_helpful"):
            raise ValidationException("Invalid vote value")

        result = self.voting_repo.cast_vote(
            db=db,
            review_id=request.review_id,
            user_id=user_id,
            value=request.value,
        )
        return VoteResponse.model_validate(result)

    def remove_vote(
        self,
        db: Session,
        user_id: UUID,
        request: RemoveVote,
    ) -> None:
        """
        Remove previously cast vote.
        """
        self.voting_repo.remove_vote(
            db=db,
            review_id=request.review_id,
            user_id=user_id,
        )

    def get_vote_history(
        self,
        db: Session,
        user_id: UUID,
    ) -> VoteHistory:
        """
        Get a user's complete voting history.
        """
        objs = self.voting_repo.get_votes_by_user(db, user_id)
        items = [VoteHistoryItem.model_validate(o) for o in objs]
        return VoteHistory(
            user_id=user_id,
            votes=items,
        )

    def get_voting_stats_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> VotingStats:
        data = self.voting_repo.get_hostel_voting_stats(db, hostel_id)
        if not data:
            # Return default object if no stats
            return VotingStats(
                hostel_id=hostel_id,
                total_votes=0,
                helpful_votes=0,
                not_helpful_votes=0,
                avg_helpfulness_score=0.0,
            )
        return VotingStats.model_validate(data)