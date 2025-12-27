"""
Review Incentive Service

Enhanced incentive management with flexible rules,
fraud detection, and comprehensive tracking.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.referral import RewardTrackingRepository
from app.schemas.review import ReviewDetail
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    DatabaseException,
)
from app.core1.metrics import track_performance

logger = logging.getLogger(__name__)


class ReviewIncentiveService:
    """
    High-level service for review incentives and rewards.

    Features:
    - Configurable reward rules
    - Fraud detection
    - Multi-tier rewards
    - Comprehensive tracking
    """

    # Reward configuration
    MIN_RATING_FOR_REWARD = 3
    MIN_TEXT_LENGTH_FOR_REWARD = 100
    BASE_REWARD_POINTS = 10
    BONUS_POINTS_5_STAR = 10
    BONUS_POINTS_DETAILED = 5
    
    # Anti-fraud
    MAX_REWARDS_PER_USER_PER_DAY = 3
    MIN_HOURS_BETWEEN_REVIEWS = 1

    def __init__(self, reward_tracking_repo: RewardTrackingRepository) -> None:
        """
        Initialize ReviewIncentiveService.

        Args:
            reward_tracking_repo: Repository for reward tracking

        Raises:
            ValueError: If repository is None
        """
        if not reward_tracking_repo:
            raise ValueError("RewardTrackingRepository cannot be None")

        self.reward_tracking_repo = reward_tracking_repo
        logger.info("ReviewIncentiveService initialized")

    # -------------------------------------------------------------------------
    # Reward operations
    # -------------------------------------------------------------------------

    @track_performance("incentive.should_reward")
    def should_reward_for_review(
        self,
        review: ReviewDetail,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if review qualifies for reward.

        Rules:
        - Review must be published
        - Not deleted
        - Rating >= minimum threshold
        - Text length meets minimum
        - Content appears genuine

        Args:
            review: Review to evaluate

        Returns:
            Tuple of (should_reward, reason)
        """
        # Check publication status
        if review.status != "published":
            return False, "Review not published"

        if review.is_deleted:
            return False, "Review is deleted"

        # Check rating
        if review.rating < self.MIN_RATING_FOR_REWARD:
            return False, f"Rating below minimum ({self.MIN_RATING_FOR_REWARD})"

        # Check text length
        if not review.text or len(review.text.strip()) < self.MIN_TEXT_LENGTH_FOR_REWARD:
            return (
                False,
                f"Review text too short (minimum {self.MIN_TEXT_LENGTH_FOR_REWARD} characters)",
            )

        # Basic spam detection
        if self._appears_spam(review):
            return False, "Review appears to be spam"

        logger.info(f"Review {review.id} qualifies for reward")
        return True, None

    @track_performance("incentive.award_incentive")
    def award_incentive_for_review(
        self,
        db: Session,
        user_id: UUID,
        review: ReviewDetail,
    ) -> Dict[str, Any]:
        """
        Award incentive for a review if eligible.

        Includes fraud detection and rate limiting.

        Args:
            db: Database session
            user_id: UUID of user
            review: Review object

        Returns:
            Dictionary with reward details

        Raises:
            BusinessLogicException: If fraud detected or rate limit exceeded
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Processing reward for review {review.id}, user {user_id}")

            # Check eligibility
            should_reward, reason = self.should_reward_for_review(review)
            if not should_reward:
                logger.info(f"Review {review.id} not eligible: {reason}")
                return {
                    "reward_granted": False,
                    "reason": reason,
                    "points_awarded": 0,
                }

            # Anti-fraud checks
            self._check_fraud_indicators(db, user_id)

            # Calculate reward amount
            points = self._calculate_reward_points(review)

            # Award reward
            tracking = self.reward_tracking_repo.add_review_reward(
                db=db,
                user_id=user_id,
                review_id=review.id,
                points=points,
            )

            result = {
                "reward_granted": True,
                "points_awarded": points,
                "total_available_for_payout": float(tracking.available_for_payout),
                "breakdown": self._get_points_breakdown(review, points),
            }

            logger.info(
                f"Reward awarded: {points} points to user {user_id} "
                f"for review {review.id}"
            )

            return result

        except BusinessLogicException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error awarding incentive: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to award incentive") from e

    @track_performance("incentive.get_user_rewards")
    def get_user_reward_summary(
        self,
        db: Session,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get reward summary for a user.

        Args:
            db: Database session
            user_id: UUID of user

        Returns:
            Dictionary with reward summary

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching reward summary for user {user_id}")

            summary = self.reward_tracking_repo.get_user_reward_summary(db, user_id)

            logger.info(
                f"Reward summary for user {user_id}: "
                f"{summary.get('total_points', 0)} total points"
            )

            return summary

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching reward summary: {str(e)}")
            raise DatabaseException("Failed to fetch reward summary") from e

    @track_performance("incentive.get_reward_history")
    def get_reward_history(
        self,
        db: Session,
        user_id: UUID,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get reward history for a user.

        Args:
            db: Database session
            user_id: UUID of user
            limit: Maximum records to return

        Returns:
            List of reward history records

        Raises:
            ValidationException: If limit is invalid
            DatabaseException: If database error occurs
        """
        try:
            if limit < 1 or limit > 500:
                raise ValidationException("Limit must be between 1 and 500")

            logger.debug(f"Fetching reward history for user {user_id}")

            history = self.reward_tracking_repo.get_reward_history(
                db, user_id, limit=limit
            )

            logger.info(f"Retrieved {len(history)} reward records for user {user_id}")

            return history

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching reward history: {str(e)}")
            raise DatabaseException("Failed to fetch reward history") from e

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _calculate_reward_points(self, review: ReviewDetail) -> int:
        """
        Calculate reward points for a review.

        Args:
            review: Review object

        Returns:
            Total points to award
        """
        points = self.BASE_REWARD_POINTS

        # Bonus for 5-star review
        if review.rating == 5:
            points += self.BONUS_POINTS_5_STAR
            logger.debug(f"Added {self.BONUS_POINTS_5_STAR} points for 5-star rating")

        # Bonus for detailed ratings
        if (
            review.detailed_ratings
            and hasattr(review.detailed_ratings, 'cleanliness')
            and review.detailed_ratings.cleanliness >= 4
        ):
            points += self.BONUS_POINTS_DETAILED
            logger.debug(f"Added {self.BONUS_POINTS_DETAILED} points for detailed ratings")

        # Bonus for media attachments
        if hasattr(review, 'media_count') and review.media_count > 0:
            media_bonus = min(review.media_count * 2, 10)  # Max 10 bonus points
            points += media_bonus
            logger.debug(f"Added {media_bonus} points for {review.media_count} media items")

        # Bonus for verified stay
        if hasattr(review, 'is_verified') and review.is_verified:
            points += 5
            logger.debug("Added 5 points for verified stay")

        return points

    def _get_points_breakdown(
        self,
        review: ReviewDetail,
        total_points: int,
    ) -> Dict[str, int]:
        """
        Get breakdown of how points were calculated.

        Args:
            review: Review object
            total_points: Total points awarded

        Returns:
            Dictionary with points breakdown
        """
        breakdown = {"base": self.BASE_REWARD_POINTS}

        if review.rating == 5:
            breakdown["five_star_bonus"] = self.BONUS_POINTS_5_STAR

        if (
            review.detailed_ratings
            and hasattr(review.detailed_ratings, 'cleanliness')
            and review.detailed_ratings.cleanliness >= 4
        ):
            breakdown["detailed_ratings_bonus"] = self.BONUS_POINTS_DETAILED

        if hasattr(review, 'media_count') and review.media_count > 0:
            breakdown["media_bonus"] = min(review.media_count * 2, 10)

        if hasattr(review, 'is_verified') and review.is_verified:
            breakdown["verified_stay_bonus"] = 5

        return breakdown

    def _check_fraud_indicators(self, db: Session, user_id: UUID) -> None:
        """
        Check for fraud indicators.

        Args:
            db: Database session
            user_id: User UUID

        Raises:
            BusinessLogicException: If fraud detected
        """
        # Check daily limit
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        rewards_today = self.reward_tracking_repo.count_rewards_since(
            db, user_id, since=today_start
        )

        if rewards_today >= self.MAX_REWARDS_PER_USER_PER_DAY:
            logger.warning(
                f"Daily reward limit exceeded for user {user_id}: "
                f"{rewards_today} rewards today"
            )
            raise BusinessLogicException(
                f"Maximum {self.MAX_REWARDS_PER_USER_PER_DAY} rewards per day allowed"
            )

        # Check time between reviews
        cutoff = datetime.utcnow() - timedelta(hours=self.MIN_HOURS_BETWEEN_REVIEWS)
        recent_rewards = self.reward_tracking_repo.count_rewards_since(
            db, user_id, since=cutoff
        )

        if recent_rewards > 0:
            logger.warning(
                f"User {user_id} attempting multiple rewards within "
                f"{self.MIN_HOURS_BETWEEN_REVIEWS} hour(s)"
            )
            raise BusinessLogicException(
                f"Please wait at least {self.MIN_HOURS_BETWEEN_REVIEWS} hour(s) "
                f"between review rewards"
            )

    def _appears_spam(self, review: ReviewDetail) -> bool:
        """
        Basic spam detection.

        Args:
            review: Review object

        Returns:
            True if appears to be spam, False otherwise
        """
        if not review.text:
            return False

        text = review.text.lower()

        # Check for repetitive characters
        if any(char * 5 in text for char in 'abcdefghijklmnopqrstuvwxyz'):
            logger.debug("Spam indicator: repetitive characters")
            return True

        # Check for common spam phrases
        spam_phrases = ['click here', 'buy now', 'limited offer', 'act now']
        if any(phrase in text for phrase in spam_phrases):
            logger.debug("Spam indicator: spam phrases detected")
            return True

        # Check for excessive caps
        if sum(1 for c in review.text if c.isupper()) > len(review.text) * 0.5:
            logger.debug("Spam indicator: excessive capitals")
            return True

        return False