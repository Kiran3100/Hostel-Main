# app/services/review/review_moderation_service.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import ReviewRepository
from app.repositories.core import HostelRepository, UserRepository
from app.schemas.review.review_moderation import (
    ModerationRequest,
    ModerationResponse,
    ModerationQueue,
    PendingReview,
    BulkModeration,
    ModerationStats,
)
from app.services.common import UnitOfWork, errors


class ModerationStore(Protocol):
    """
    Storage for review moderation metadata not present in the Review model.

    Expected record keys (example):
        {
            "review_id": UUID,
            "moderation_status": "pending|approved|rejected|flagged",
            "rejection_reason": str | None,
            "flag_reason": str | None,
            "flag_details": str | None,
            "moderator_notes": str | None,
            "flag_count": int,
            "spam_score": Decimal | None,
            "sentiment_score": Decimal | None,
            "submitted_at": datetime,
            "moderated_at": datetime | None,
            "moderated_by": UUID | None,
            "moderated_by_name": str | None,
        }
    """

    def get_metadata(self, review_id: UUID) -> Optional[dict]: ...
    def save_metadata(self, review_id: UUID, data: dict) -> None: ...


class ReviewModerationService:
    """
    Review moderation:

    - Approve/reject/flag/unflag reviews
    - Build moderation queue
    - Moderation statistics
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: ModerationStore,
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

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    def _ensure_meta(self, review_id: UUID) -> dict:
        meta = self._store.get_metadata(review_id)
        if meta:
            return meta
        now = self._now()
        meta = {
            "review_id": review_id,
            "moderation_status": "pending",
            "rejection_reason": None,
            "flag_reason": None,
            "flag_details": None,
            "moderator_notes": None,
            "flag_count": 0,
            "spam_score": None,
            "sentiment_score": None,
            "submitted_at": now,
            "moderated_at": None,
            "moderated_by": None,
            "moderated_by_name": None,
        }
        self._store.save_metadata(review_id, meta)
        return meta

    # ------------------------------------------------------------------ #
    # Moderate
    # ------------------------------------------------------------------ #
    def moderate(
        self,
        data: ModerationRequest,
        *,
        moderator_id: UUID,
    ) -> ModerationResponse:
        """
        Apply a moderation action to a review.
        """
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            user_repo = self._get_user_repo(uow)

            r = review_repo.get(data.review_id)
            if r is None:
                raise errors.NotFoundError(f"Review {data.review_id} not found")

            moderator = user_repo.get(moderator_id)
            moderator_name = moderator.full_name if moderator else ""

            meta = self._ensure_meta(r.id)
            now = self._now()

            action = data.action
            if action == "approve":
                r.is_approved = True  # type: ignore[attr-defined]
                r.is_flagged = False  # type: ignore[attr-defined]
                meta["moderation_status"] = "approved"
                meta["rejection_reason"] = None
            elif action == "reject":
                r.is_approved = False  # type: ignore[attr-defined]
                meta["moderation_status"] = "rejected"
                meta["rejection_reason"] = data.rejection_reason
            elif action == "flag":
                r.is_flagged = True  # type: ignore[attr-defined]
                meta["moderation_status"] = "flagged"
                meta["flag_reason"] = data.flag_reason
                meta["flag_details"] = data.flag_details
                meta["flag_count"] = int(meta.get("flag_count", 0)) + 1
            elif action == "unflag":
                r.is_flagged = False  # type: ignore[attr-defined]
                meta["moderation_status"] = "approved" if r.is_approved else "pending"
                meta["flag_reason"] = None
                meta["flag_details"] = None
            else:
                raise errors.ValidationError("Unknown moderation action")

            meta["moderated_at"] = now
            meta["moderated_by"] = moderator_id
            meta["moderated_by_name"] = moderator_name
            meta["moderator_notes"] = data.moderator_notes

            self._store.save_metadata(r.id, meta)
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return ModerationResponse(
            review_id=r.id,
            action_taken=action,
            moderated_by=moderator_id,
            moderated_by_name=moderator_name,
            moderated_at=now,
            reviewer_notified=False,
            message=f"Review {action}d successfully",
        )

    def bulk_moderate(
        self,
        data: BulkModeration,
        *,
        moderator_id: UUID,
    ) -> List[ModerationResponse]:
        responses: List[ModerationResponse] = []
        for rid in data.review_ids:
            req = ModerationRequest(
                review_id=rid,
                action=data.action,
                rejection_reason=data.reason,
                flag_reason=None,
                flag_details=None,
                moderator_notes=data.reason,
            )
            responses.append(self.moderate(req, moderator_id=moderator_id))
        return responses

    # ------------------------------------------------------------------ #
    # Queue
    # ------------------------------------------------------------------ #
    def get_moderation_queue(
        self,
        *,
        hostel_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> ModerationQueue:
        """
        Build a simple moderation queue:

        - Pending or flagged reviews.
        """
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            filters: Dict[str, object] = {}
            if hostel_id:
                filters["hostel_id"] = hostel_id

            recs = review_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

            pending: List[PendingReview] = []
            total_pending = flagged = auto_approved = 0

            for r in recs:
                meta = self._ensure_meta(r.id)
                status = meta.get("moderation_status", "pending")
                if status == "pending" or status == "flagged":
                    total_pending += 1
                if status == "flagged":
                    flagged += 1
                if status == "approved" and meta.get("moderated_by") is None:
                    auto_approved += 1

                if len(pending) >= limit:
                    continue

                hostel = hostel_repo.get(r.hostel_id)
                hostel_name = hostel.name if hostel else ""

                reviewer = user_repo.get(r.reviewer_id)
                reviewer_name = reviewer.full_name if reviewer else ""

                excerpt = (r.review_text or "")[:200]
                pending.append(
                    PendingReview(
                        review_id=r.id,
                        hostel_id=r.hostel_id,
                        hostel_name=hostel_name,
                        reviewer_id=r.reviewer_id,  
                        reviewer_name=reviewer_name,
                        overall_rating=r.overall_rating,
                        title=r.title,
                        review_excerpt=excerpt,
                        is_verified_stay=r.is_verified_stay,
                        is_flagged=r.is_flagged,
                        flag_count=int(meta.get("flag_count", 0)),
                        submitted_at=r.created_at,
                        spam_score=meta.get("spam_score"),
                        sentiment_score=meta.get("sentiment_score"),
                    )
                )

        return ModerationQueue(
            hostel_id=hostel_id,
            total_pending=total_pending,
            flagged_reviews=flagged,
            auto_approved=auto_approved,
            high_priority=flagged,
            pending_reviews=pending,
        )

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def get_moderation_stats(
        self,
        *,
        hostel_id: Optional[get_moderation_statsUUID],
        period_start: date,
        period_end: date,
    ) -> ModerationStats:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)

            filters: Dict[str, object] = {}
            if hostel_id:
                filters["hostel_id"] = hostel_id

            recs = review_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

        total = auto_approved = manually_approved = rejected = flagged = 0
        moderation_times: List[float] = []
        moderations_by_user: Dict[str, int] = {}

        for r in recs:
            if not (period_start <= r.created_at.date() <= period_end):
                continue
            total += 1
            meta = self._ensure_meta(r.id)
            status = meta.get("moderation_status", "pending")
            mod_at = meta.get("moderated_at")
            mod_by = meta.get("moderated_by")
            sub_at = meta.get("submitted_at", r.created_at)

            if status == "approved":
                if mod_by is None:
                    auto_approved += 1
                else:
                    manually_approved += 1
            elif status == "rejected":
                rejected += 1
            elif status == "flagged":
                flagged += 1

            if mod_at:
                hours = (mod_at - sub_at).total_seconds() / 3600.0
                moderation_times.append(hours)
            if mod_by:
                key = str(mod_by)
                moderations_by_user[key] = moderations_by_user.get(key, 0) + 1
        if total > 0:
            approval_rate = Decimal(str((auto_approved + manually_approved) * 100 / total))
            rejection_rate = Decimal(str(rejected * 100 / total))
        else:
            approval_rate = Decimal("0")
            rejection_rate = Decimal("0")

        avg_time = (
            Decimal(str(sum(moderation_times) / len(moderation_times)))
            if moderation_times
            else Decimal("0")
        )

        return ModerationStats(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            total_reviews=total,
            auto_approved=auto_approved,
            manually_approved=manually_approved,
            rejected=rejected,
            flagged=flagged,
            average_moderation_time_hours=avg_time,
            median_moderation_time_hours=None,
            moderations_by_user=moderations_by_user,
            approval_rate=approval_rate,
            rejection_rate=rejection_rate,
            auto_approval_accuracy=None,
        )