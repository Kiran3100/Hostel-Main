"""
Review Incentive Service

Handles incentives for leaving reviews (e.g., reward points, coupons).
"""

from __future__ import annotations

from typing import Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.referral import RewardTrackingRepository  # adjust if needed
from app.schemas.review import ReviewDetail
from app.core.exceptions import ValidationException


class ReviewIncentiveService:
    """
    High-level service for review incentives.

    This is intentionally very thin and rule-based. The actual rewards
    system is encapsulated in RewardTrackingRepository.
    """

    def __init__(self, reward_tracking_repo: RewardTrackingRepository) -> None:
        self.reward_tracking_repo = reward_tracking_repo

    def should_reward_for_review(
        self,
        review: ReviewDetail,
    ) -> bool:
        """
        Simple rule: reward only if review is published, not deleted,
        rating >= 3, and content length above a threshold.
        """
        if review.status != "published":
            return False
        if review.is_deleted:
            return False
        if review.rating < 3:
            return False
        if not review.text or len(review.text.strip()) < 100:
            return False
        return True

    def award_incentive_for_review(
        self,
        db: Session,
        user_id: UUID,
        review: ReviewDetail,
    ) -> Dict[str, Any]:
        """
        Award incentive for a review if rules are met.

        Returns summary dict with whether reward was granted and amounts.
        """
        if not self.should_reward_for_review(review):
            return {"reward_granted": False, "reason": "Not eligible based on rules"}

        # Decide reward amount based on rating and length (example)
        base_points = 10
        if review.rating == 5:
            base_points += 10
        if review.detailed_ratings and review.detailed_ratings.cleanliness >= 4:
            base_points += 5

        tracking = self.reward_tracking_repo.add_review_reward(
            db=db,
            user_id=user_id,
            review_id=review.id,
            points=base_points,
        )

        return {
            "reward_granted": True,
            "points_awarded": base_points,
            "total_available_for_payout": float(tracking.available_for_payout),
        }