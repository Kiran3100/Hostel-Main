"""
Review Voting Service

Enhanced helpfulness voting system with fraud detection,
rate limiting, and comprehensive analytics.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.review import ReviewVotingRepository
from app.schemas.review import (
    VoteRequest,
    VoteResponse,
    RemoveVote,
    VoteHistory,
    VoteHistoryItem,
    VotingStats,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
    DatabaseException,
    RateLimitException,
)
from app.core1.cache import cache_result, invalidate_cache
from app.core1.metrics import track_performance

logger = logging.getLogger(__name__)


class ReviewVotingService:
    """
    High-level service for review helpfulness voting.

    Features:
    - Vote casting with validation
    - Vote modification and removal
    - Fraud detection via rate limiting
    - Comprehensive voting analytics
    - User voting history
    """

    # Valid vote values
    VALID_VOTE_VALUES = {'helpful', 'not_helpful'}
    
    # Rate limiting: max votes per user per hour
    MAX_VOTES_PER_HOUR = 50
    
    # Cache TTL for vote stats
    STATS_CACHE_TTL = 300

    def __init__(self, voting_repo: ReviewVotingRepository) -> None:
        """
        Initialize ReviewVotingService.

        Args:
            voting_repo: Repository for voting operations

        Raises:
            ValueError: If repository is None
        """
        if not voting_repo:
            raise ValueError("VotingRepository cannot be None")

        self.voting_repo = voting_repo
        logger.info("ReviewVotingService initialized")

    # -------------------------------------------------------------------------
    # Voting operations
    # -------------------------------------------------------------------------

    @track_performance("voting.cast_vote")
    @invalidate_cache(patterns=["vote_stats:*", "review_detail:*"])
    def cast_vote(
        self,
        db: Session,
        user_id: UUID,
        request: VoteRequest,
    ) -> VoteResponse:
        """
        Submit or update a vote on a review.

        Enforces:
        - Vote value validation
        - Rate limiting
        - Self-voting prevention
        - Review existence

        Args:
            db: Database session
            user_id: UUID of voting user
            request: Vote request data

        Returns:
            VoteResponse with vote result

        Raises:
            ValidationException: If vote data is invalid
            BusinessLogicException: If user attempts to vote on own review
            RateLimitException: If rate limit exceeded
            NotFoundException: If review not found
            DatabaseException: If database operation fails
        """
        try:
            logger.info(
                f"Casting vote: user={user_id}, review={request.review_id}, "
                f"value={request.value}"
            )

            # Validate request
            self._validate_vote_request(request)

            # Check rate limit
            self._check_rate_limit(db, user_id)

            # Prevent self-voting
            self._prevent_self_voting(db, user_id, request.review_id)

            # Cast vote
            result = self.voting_repo.cast_vote(
                db=db,
                review_id=request.review_id,
                user_id=user_id,
                value=request.value,
            )

            response = VoteResponse.model_validate(result)

            logger.info(
                f"Vote cast successfully: review={request.review_id}, "
                f"helpful_count={response.helpful_count}, "
                f"not_helpful_count={response.not_helpful_count}"
            )

            return response

        except (ValidationException, BusinessLogicException, RateLimitException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error casting vote: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to cast vote") from e

    @track_performance("voting.remove_vote")
    @invalidate_cache(patterns=["vote_stats:*", "review_detail:*"])
    def remove_vote(
        self,
        db: Session,
        user_id: UUID,
        request: RemoveVote,
    ) -> None:
        """
        Remove previously cast vote.

        Args:
            db: Database session
            user_id: UUID of user removing vote
            request: Remove vote request

        Raises:
            ValidationException: If request is invalid
            NotFoundException: If vote not found
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Removing vote: user={user_id}, review={request.review_id}")

            if not request.review_id:
                raise ValidationException("Review ID is required")

            # Check if vote exists
            existing_vote = self.voting_repo.get_user_vote(
                db, user_id, request.review_id
            )

            if not existing_vote:
                logger.warning(
                    f"Vote not found for removal: user={user_id}, "
                    f"review={request.review_id}"
                )
                raise NotFoundException("Vote not found")

            # Remove vote
            self.voting_repo.remove_vote(
                db=db,
                review_id=request.review_id,
                user_id=user_id,
            )

            logger.info(f"Vote removed successfully: review={request.review_id}")

        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error removing vote: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to remove vote") from e

    # -------------------------------------------------------------------------
    # History & analytics
    # -------------------------------------------------------------------------

    @track_performance("voting.get_vote_history")
    @cache_result(ttl=60, key_prefix="vote_history")
    def get_vote_history(
        self,
        db: Session,
        user_id: UUID,
        limit: Optional[int] = 100,
    ) -> VoteHistory:
        """
        Get a user's complete voting history.

        Args:
            db: Database session
            user_id: UUID of user
            limit: Maximum votes to return

        Returns:
            VoteHistory object

        Raises:
            ValidationException: If parameters are invalid
            DatabaseException: If database error occurs
        """
        try:
            if limit and (limit < 1 or limit > 1000):
                raise ValidationException("Limit must be between 1 and 1000")

            logger.debug(f"Fetching vote history for user {user_id}")

            objs = self.voting_repo.get_votes_by_user(db, user_id, limit=limit)
            items = [VoteHistoryItem.model_validate(o) for o in objs]

            history = VoteHistory(
                user_id=user_id,
                votes=items,
                total_votes=len(items),
            )

            logger.info(f"Retrieved {len(items)} votes for user {user_id}")

            return history

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching vote history: {str(e)}")
            raise DatabaseException("Failed to fetch vote history") from e

    @track_performance("voting.get_hostel_stats")
    @cache_result(ttl=300, key_prefix="vote_stats")
    def get_voting_stats_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> VotingStats:
        """
        Get aggregated voting statistics for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel

        Returns:
            VotingStats object

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching voting stats for hostel {hostel_id}")

            data = self.voting_repo.get_hostel_voting_stats(db, hostel_id)

            if not data:
                logger.info(f"No voting data for hostel {hostel_id}, returning empty stats")
                return VotingStats(
                    hostel_id=hostel_id,
                    total_votes=0,
                    helpful_votes=0,
                    not_helpful_votes=0,
                    avg_helpfulness_score=0.0,
                    unique_voters=0,
                )

            stats = VotingStats.model_validate(data)

            logger.info(
                f"Stats retrieved: total={stats.total_votes}, "
                f"helpful={stats.helpful_votes}, score={stats.avg_helpfulness_score:.2f}"
            )

            return stats

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching voting stats: {str(e)}")
            raise DatabaseException("Failed to fetch voting stats") from e

    @track_performance("voting.get_review_votes")
    def get_review_vote_details(
        self,
        db: Session,
        review_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get detailed voting information for a specific review.

        Args:
            db: Database session
            review_id: UUID of review

        Returns:
            Dictionary with vote counts and breakdown

        Raises:
            NotFoundException: If review not found
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching vote details for review {review_id}")

            data = self.voting_repo.get_review_vote_details(db, review_id)

            if not data:
                raise NotFoundException(f"Review {review_id} not found")

            logger.info(f"Vote details retrieved for review {review_id}")

            return data

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching review votes: {str(e)}")
            raise DatabaseException("Failed to fetch review vote details") from e

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_vote_request(self, request: VoteRequest) -> None:
        """
        Validate vote request.

        Args:
            request: Vote request

        Raises:
            ValidationException: If validation fails
        """
        if not request.review_id:
            raise ValidationException("Review ID is required")

        if not request.value:
            raise ValidationException("Vote value is required")

        if request.value not in self.VALID_VOTE_VALUES:
            raise ValidationException(
                f"Invalid vote value. Must be one of: {', '.join(self.VALID_VOTE_VALUES)}"
            )

    def _check_rate_limit(self, db: Session, user_id: UUID) -> None:
        """
        Check if user has exceeded voting rate limit.

        Args:
            db: Database session
            user_id: User UUID

        Raises:
            RateLimitException: If rate limit exceeded
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        recent_votes = self.voting_repo.count_recent_votes(
            db, user_id, since=cutoff_time
        )

        if recent_votes >= self.MAX_VOTES_PER_HOUR:
            logger.warning(
                f"Rate limit exceeded for user {user_id}: "
                f"{recent_votes} votes in last hour"
            )
            raise RateLimitException(
                f"Voting rate limit exceeded. Maximum {self.MAX_VOTES_PER_HOUR} "
                f"votes per hour allowed."
            )

    def _prevent_self_voting(
        self,
        db: Session,
        user_id: UUID,
        review_id: UUID,
    ) -> None:
        """
        Prevent users from voting on their own reviews.

        Args:
            db: Database session
            user_id: User UUID
            review_id: Review UUID

        Raises:
            BusinessLogicException: If user attempts to vote on own review
        """
        is_own_review = self.voting_repo.is_user_review_author(
            db, user_id, review_id
        )

        if is_own_review:
            logger.warning(
                f"User {user_id} attempted to vote on own review {review_id}"
            )
            raise BusinessLogicException("You cannot vote on your own review")