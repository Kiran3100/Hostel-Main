# app/services/review/hostel_response_service.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.content import ReviewRepository
from app.repositories.core import HostelRepository, UserRepository
from app.schemas.review.review_response_schema import (
    HostelResponseCreate,
    OwnerResponse,
    HostelResponseUpdate,
    ResponseGuidelines,
    ResponseStats,
)
from app.services.common import UnitOfWork, errors


class HostelResponseStore(Protocol):
    """
    Storage for hostel responses to reviews.

    Expected record shape:

        {
            "id": UUID,
            "review_id": UUID,
            "hostel_id": UUID,
            "response_text": str,
            "responded_by": UUID,
            "responded_by_name": str,
            "responded_by_role": str,
            "responded_at": datetime,
            "created_at": datetime,
            "updated_at": datetime,
        }
    """

    def save_response(self, record: dict) -> dict: ...
    def get_response_by_review(self, review_id: UUID) -> Optional[dict]: ...
    def get_response(self, response_id: UUID) -> Optional[dict]: ...
    def update_response(self, response_id: UUID, data: dict) -> dict: ...
    def list_responses_for_hostel(self, hostel_id: UUID) -> List[dict]: ...


class HostelResponseService:
    """
    Hostel/owner responses to reviews:

    - Create/update responses
    - Guidelines
    - Response statistics
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: HostelResponseStore,
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

    # ------------------------------------------------------------------ #
    # Guidelines
    # ------------------------------------------------------------------ #
    def get_guidelines(self) -> ResponseGuidelines:
        return ResponseGuidelines()

    # ------------------------------------------------------------------ #
    # Responses
    # ------------------------------------------------------------------ #
    def create_response(
        self,
        data: HostelResponseCreate,
        *,
        responded_by_role: str,
    ) -> OwnerResponse:
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            user_repo = self._get_user_repo(uow)

            r = review_repo.get(data.review_id)
            if r is None:
                raise errors.NotFoundError(f"Review {data.review_id} not found")

            user = user_repo.get(data.responded_by)
            responded_by_name = user.full_name if user else ""

            now = self._now()
            record = {
                "id": uuid4(),
                "review_id": data.review_id,
                "hostel_id": r.hostel_id,
                "response_text": data.response_text,
                "responded_by": data.responded_by,
                "responded_by_name": responded_by_name,
                "responded_by_role": responded_by_role,
                "responded_at": now,
                "created_at": now,
                "updated_at": now,
            }
            saved = self._store.save_response(record)

        return OwnerResponse(
            id=saved["id"],
            created_at=saved["created_at"],
            updated_at=saved["updated_at"],
            review_id=saved["review_id"],
            response_text=saved["response_text"],
            responded_by=saved["responded_by"],
            responded_by_name=saved["responded_by_name"],
            responded_by_role=saved["responded_by_role"],
            responded_at=saved["responded_at"],
        )

    def update_response(self, data: HostelResponseUpdate) -> OwnerResponse:
        record = self._store.get_response(data.response_id)
        if not record:
            raise errors.NotFoundError(f"Response {data.response_id} not found")

        record["response_text"] = data.response_text
        record["updated_at"] = self._now()
        updated = self._store.update_response(data.response_id, record)

        return OwnerResponse(
            id=updated["id"],
            created_at=updated["created_at"],
            updated_at=updated["updated_at"],
            review_id=updated["review_id"],
            response_text=updated["response_text"],
            responded_by=updated["responded_by"],
            responded_by_name=updated["responded_by_name"],
            responded_by_role=updated["responded_by_role"],
            responded_at=updated["responded_at"],
        )

    def get_response_for_review(self, review_id: UUID) -> Optional[OwnerResponse]:
        record = self._store.get_response_by_review(review_id)
        if not record:
            return None
        return OwnerResponse(
            id=record["id"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            review_id=record["review_id"],
            response_text=record["response_text"],
            responded_by=record["responded_by"],
            responded_by_name=record["responded_by_name"],
            responded_by_role=record["responded_by_role"],
            responded_at=record["responded_at"],
        )

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def get_stats(
        self,
        hostel_id: UUID,
        *,
        period_start: date,
        period_end: date,
    ) -> ResponseStats:
        """
        Compute ResponseStats using ReviewRepository + HostelResponseStore.
        """
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            reviews = review_repo.get_multi(
                skip=0,
                limit=None,
                filters={"hostel_id": hostel_id},
            )

        total_reviews = len(reviews)
        if total_reviews == 0:
            return ResponseStats(
                hostel_id=hostel_id,
                hostel_name=hostel.name,
                total_reviews=0,
                total_responses=0,
                response_rate=Decimal("0"),
                average_response_time_hours=Decimal("0"),
                median_response_time_hours=None,
                response_rate_5_star=Decimal("0"),
                response_rate_4_star=Decimal("0"),
                response_rate_3_star=Decimal("0"),
                response_rate_2_star=Decimal("0"),
                response_rate_1_star=Decimal("0"),
                average_response_length=0,
                pending_responses=0,
                oldest_unanswered_days=None,
            )

        responses = self._store.list_responses_for_hostel(hostel_id)
        total_responses = len(responses)

        def _pct(num: int, denom: int) -> Decimal:
            return (
                Decimal(str(num)) / Decimal(str(denom)) * Decimal("100")
                if denom > 0
                else Decimal("0")
            )

        # Average response time
        response_times: List[float] = []
        resp_by_review: Dict[UUID, dict] = {
            r["review_id"]: r for r in responses
        }

        by_rating_responses = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        by_rating_total = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for rv in reviews:
            d = rv.created_at.date()
            if not (period_start <= d <= period_end):
                continue

            val = int(round(float(rv.overall_rating)))
            val = min(5, max(1, val))
            by_rating_total[val] += 1

            resp = resp_by_review.get(rv.id)
            if resp:
                delta = resp["responded_at"] - rv.created_at
                response_times.append(delta.total_seconds() / 3600.0)
                by_rating_responses[val] += 1

        avg_hours = (
            Decimal(str(sum(response_times) / len(response_times)))
            if response_times
            else Decimal("0")
        )

        return ResponseStats(
            hostel_id=hostel_id,
            total_reviews=total_reviews,
            total_responses=total_responses,
            response_rate=_pct(total_responses, total_reviews),
            average_response_time_hours=avg_hours,
            response_rate_5_star=_pct(by_rating_responses[5], by_rating_total[5]),
            response_rate_4_star=_pct(by_rating_responses[4], by_rating_total[4]),
            response_rate_3_star=_pct(by_rating_responses[3], by_rating_total[3]),
            response_rate_2_star=_pct(by_rating_responses[2], by_rating_total[2]),
            response_rate_1_star=_pct(by_rating_responses[1], by_rating_total[1]),
        )