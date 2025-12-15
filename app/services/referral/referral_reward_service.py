# app/services/referral/referral_reward_service.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.transactions import ReferralRepository
from app.schemas.referral.referral_rewards import (
    RewardConfig,
    RewardTracking,
    PayoutRequest,
    PayoutRequestResponse,
)
from app.services.common import UnitOfWork, errors


class RewardConfigStore(Protocol):
    """
    Storage abstraction for global RewardConfig.
    """

    def get_config(self) -> Optional[dict]: ...
    def save_config(self, data: dict) -> None: ...


class PayoutStore(Protocol):
    """
    Storage abstraction for payout requests.

    Expected record shape (example):

        {
            "payout_request_id": UUID,
            "user_id": UUID,
            "amount": Decimal,
            "payout_method": PaymentMethod,
            "status": str,
            "requested_at": datetime,
            "processed_at": datetime | None,
            "failure_reason": str | None,
        }
    """

    def save_payout_request(self, record: dict) -> dict: ...
    def get_payout_request(self, payout_request_id: UUID) -> Optional[dict]: ...
    def update_payout_request(self, payout_request_id: UUID, data: dict) -> dict: ...


class ReferralRewardService:
    """
    Referral reward management:

    - Get/set RewardConfig
    - Compute RewardTracking for a user based on Referral records
    - Create payout requests
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        config_store: RewardConfigStore,
        payout_store: PayoutStore,
    ) -> None:
        self._session_factory = session_factory
        self._config_store = config_store
        self._payout_store = payout_store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_referral_repo(self, uow: UnitOfWork) -> ReferralRepository:
        return uow.get_repo(ReferralRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self) -> RewardConfig:
        record = self._config_store.get_config()
        if record:
            return RewardConfig.model_validate(record)
        cfg = RewardConfig()
        self._config_store.save_config(cfg.model_dump())
        return cfg

    def set_config(self, cfg: RewardConfig) -> None:
        self._config_store.save_config(cfg.model_dump())

    # ------------------------------------------------------------------ #
    # Tracking
    # ------------------------------------------------------------------ #
    def get_tracking_for_user(self, user_id: UUID) -> RewardTracking:
        """
        Aggregate rewards for a referrer using Referral records.

        - total_rewards_earned: sum of all referrer_reward_amount
        - total_rewards_paid: approximated based on reward_status strings
        - pending_rewards: earned - paid
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_referral_repo(uow)
            recs = repo.list_for_referrer(user_id)

        total_earned = Decimal("0")
        total_paid = Decimal("0")
        by_program: Dict[str, Decimal] = {}

        for r in recs:
            amt = r.referrer_reward_amount or Decimal("0")
            total_earned += amt

            prog_key = str(r.program_id)
            by_program[prog_key] = by_program.get(prog_key, Decimal("0")) + amt

            status_obj = getattr(r, "referrer_reward_status", None)
            status_str = getattr(status_obj, "value", str(status_obj)).lower() if status_obj is not None else ""
            if status_str in {"paid", "completed", "settled"}:
                total_paid += amt

        pending = total_earned - total_paid

        return RewardTracking(
            user_id=user_id,
            total_rewards_earned=total_earned,
            total_rewards_paid=total_paid,
            pending_rewards=pending,
            rewards_by_program=by_program,
        )

    # ------------------------------------------------------------------ #
    # Payouts
    # ------------------------------------------------------------------ #
    def request_payout(self, req: PayoutRequest) -> PayoutRequestResponse:
        """
        Create a payout request, ensuring:

        - requested amount <= pending_rewards
        - requested amount >= min_payout_amount
        """
        cfg = self.get_config()
        tracking = self.get_tracking_for_user(req.user_id)

        if req.amount > tracking.pending_rewards:
            raise errors.ValidationError("Requested amount exceeds pending rewards")

        if req.amount < cfg.min_payout_amount:
            raise errors.ValidationError(
                f"Minimum payout amount is {cfg.min_payout_amount}"
            )

        now = self._now()
        payout_id = uuid4()

        record = {
            "payout_request_id": payout_id,
            "user_id": req.user_id,
            "amount": req.amount,
            "payout_method": req.payout_method,
            "status": "pending",
            "requested_at": now,
            "processed_at": None,
            "failure_reason": None,
            "payout_details": req.payout_details,
        }
        self._payout_store.save_payout_request(record)

        return PayoutRequestResponse(
            payout_request_id=payout_id,
            user_id=req.user_id,
            amount=req.amount,
            payout_method=req.payout_method,
            status="pending",
            requested_at=now,
            processed_at=None,
            failure_reason=None,
        )