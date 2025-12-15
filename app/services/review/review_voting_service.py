# app/services/review/review_voting_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from math import sqrt
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import ReviewRepository
from app.repositories.core import HostelRepository
from app.schemas.common.enums import VoteType
from app.schemas.review.review_voting import (
    VoteRequest,
    VoteResponse,
    HelpfulnessScore,
    VoteHistory,
    VoteHistoryItem,
    RemoveVote,
)
from app.services.common import UnitOfWork, errors


class VoteStore(Protocol):
    """
    Storage for per-user votes on reviews.

    Expected record shape:

        {
            "review_id": UUID,
            "voter_id": UUID,
            "vote_type": "helpful" | "not_helpful",
            "voted_at": datetime,
        }
    """

    def get_vote(self, review_id: UUID, voter_id: UUID) -> Optional[dict]: ...
    def save_vote(self, record: dict) -> None: ...
    def delete_vote(self, review_id: UUID, voter_id: UUID) -> None: ...
    def list_votes_for_review(self, review_id: UUID) -> List[dict]: ...
    def list_votes_for_user(self, user_id: UUID) -> List[dict]: ...


class ReviewVotingService:
    """
    Review helpfulness voting:

    - Cast/modify votes (helpful / not_helpful)
    - Remove vote
    - Compute HelpfulnessScore with Wilson score
    - User voting history
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: VoteStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_review_repo(self, uow: UnitOfWork) -> ReviewRepository:
        return uow.get_repo(ReviewRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Voting
    # ------------------------------------------------------------------ #
    def vote(self, data: VoteRequest) -> VoteResponse:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)

            r = review_repo.get(data.review_id)
            if r is None:
                raise errors.NotFoundError(f"Review {data.review_id} not found")

            existing = self._store.get_vote(data.review_id, data.voter_id)
            vote_type_str = data.vote_type.value if hasattr(data.vote_type, "value") else str(data.vote_type)

            # Adjust counts
            if existing:
                old_type = existing["vote_type"]
                if old_type == vote_type_str:
                    # No-op
                    return VoteResponse(
                        review_id=data.review_id,
                        vote_type=data.vote_type,
                        helpful_count=r.helpful_count,
                        not_helpful_count=r.not_helpful_count,
                        message="Vote unchanged",
                    )
                # Switch vote
                if old_type == "helpful":
                    r.helpful_count = max(0, r.helpful_count - 1)  # type: ignore[attr-defined]
                else:
                    r.not_helpful_count = max(0, r.not_helpful_count - 1)  # type: ignore[attr-defined]
            # Apply new vote
            if vote_type_str == "helpful":
                r.helpful_count = r.helpful_count + 1  # type: ignore[attr-defined]
            else:
                r.not_helpful_count = r.not_helpful_count + 1  # type: ignore[attr-defined]

            record = {
                "review_id": data.review_id,
                "voter_id": data.voter_id,
                "vote_type": vote_type_str,
                "voted_at": self._now(),
            }
            self._store.save_vote(record)
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return VoteResponse(
            review_id=data.review_id,
            vote_type=data.vote_type,
            helpful_count=r.helpful_count,
            not_helpful_count=r.not_helpful_count,
            message="Vote recorded",
        )

    def remove_vote(self, data: RemoveVote) -> VoteResponse:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)

            r = review_repo.get(data.review_id)
            if r is None:
                raise errors.NotFoundError(f"Review {data.review_id} not found")

            existing = self._store.get_vote(data.review_id, data.voter_id)
            if not existing:
                raise errors.NotFoundError("Vote not found")

            if existing["vote_type"] == "helpful":
                r.helpful_count = max(0, r.helpful_count - 1)  # type: ignore[attr-defined]
            else:
                r.not_helpful_count = max(0, r.not_helpful_count - 1)  # type: ignore[attr-defined]

            self._store.delete_vote(data.review_id, data.voter_id)
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        # Return current counts (vote_type not really relevant here)
        return VoteResponse(
            review_id=data.review_id,
            vote_type=VoteType.HELPFUL,  # placeholder
            helpful_count=r.helpful_count,
            not_helpful_count=r.not_helpful_count,
            message="Vote removed",
        )

    # ------------------------------------------------------------------ #
    # Scores
    # ------------------------------------------------------------------ #
    def get_helpfulness_score(self, review_id: UUID) -> HelpfulnessScore:
        votes = self._store.list_votes_for_review(review_id)
        helpful = sum(1 for v in votes if v.get("vote_type") == "helpful")
        not_helpful = sum(1 for v in votes if v.get("vote_type") == "not_helpful")
        total = helpful + not_helpful

        if total == 0:
            return HelpfulnessScore(
                review_id=review_id,
                helpful_count=0,
                not_helpful_count=0,
                total_votes=0,
                helpfulness_percentage=Decimal("0"),
                helpfulness_score=Decimal("0"),
            )

        pct = Decimal(str(helpful)) / Decimal(str(total)) * Decimal("100")

        # Wilson score for lower bound of helpfulness
        phat = helpful / total
        z = 1.96
        wilson = (
            phat
            + z * z / (2 * total)
            - z * sqrt(
                phat * (1 - phat) / total + z * z / (4 * total * total)
            )
        ) / (1 + z * z / total)
        score = Decimal(str(wilson))

        return HelpfulnessScore(
            review_id=review_id,
            helpful_count=helpful,
            not_helpful_count=not_helpful,
            total_votes=total,
            helpfulness_percentage=pct,
            helpfulness_score=score,
        )

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #
    def get_vote_history(self, user_id: UUID, *, limit: int = 10) -> VoteHistory:
        with UnitOfWork(self._session_factory) as uow:
            votes = self._store.list_votes_for_user(user_id)
            review_repo = self._get_review_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            votes_sorted = sorted(votes, key=lambda v: v.get("voted_at"), reverse=True)
            votes_subset = votes_sorted[:limit]

            items: List[VoteHistoryItem] = []
            helpful_votes = not_helpful_votes = 0

            cache_hostel: Dict[UUID, str] = {}

            for v in votes_subset:
                rid = v["review_id"]
                r = review_repo.get(rid)
                if not r:
                    continue
                hid = r.hostel_id
                if hid not in cache_hostel:
                    h = hostel_repo.get(hid)
                    cache_hostel[hid] = h.name if h else ""
                hostel_name = cache_hostel[hid]

                vt = v["vote_type"]
                if vt == "helpful":
                    helpful_votes += 1
                else:
                    not_helpful_votes += 1
                items.append(
                    VoteHistoryItem(
                        review_id=rid,
                        hostel_id=hid,
                        hostel_name=hostel_name,
                        review_title=r.title,
                        review_rating=r.overall_rating,
                        vote_type=VoteType.HELPFUL if vt == "helpful" else VoteType.NOT_HELPFUL,
                        voted_at=v["voted_at"],
                    )
                )

        total_votes = len(votes)
        return VoteHistory(
            user_id=user_id,
            total_votes=total_votes,
            helpful_votes=helpful_votes,
            not_helpful_votes=not_helpful_votes,
            recent_votes=items,
        )