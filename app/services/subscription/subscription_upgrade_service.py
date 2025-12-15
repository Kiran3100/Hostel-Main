# app/services/subscription/subscription_upgrade_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import SubscriptionRepository, SubscriptionPlanRepository
from app.schemas.subscription.subscription_upgrade import (
    UpgradeRequest,
    UpgradePreview,
)
from app.schemas.subscription.subscription_response import SubscriptionResponse
from app.services.common import UnitOfWork, errors


class SubscriptionUpgradeService:
    """
    Handle subscription upgrade/downgrade:

    - Preview cost impact (proration) of changing plans.
    - Apply the new plan to the Subscription (without billing integration).
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_sub_repo(self, uow: UnitOfWork) -> SubscriptionRepository:
        return uow.get_repo(SubscriptionRepository)

    def _get_plan_repo(self, uow: UnitOfWork) -> SubscriptionPlanRepository:
        return uow.get_repo(SubscriptionPlanRepository)

    # ------------------------------------------------------------------ #
    # Preview
    # ------------------------------------------------------------------ #
    def preview_upgrade(self, req: UpgradeRequest) -> UpgradePreview:
        with UnitOfWork(self._session_factory) as uow:
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)

            sub = sub_repo.get_active_for_hostel(req.hostel_id, as_of=req.effective_from)
            if not sub:
                raise errors.NotFoundError(f"No active subscription for hostel {req.hostel_id}")

            if sub.plan_id != req.current_plan_id:
                # Allow but warn logically; for now, we just ignore mismatch.
                pass

            current_plan = plan_repo.get(sub.plan_id)
            new_plan = plan_repo.get(req.new_plan_id)
            if not current_plan or not new_plan:
                raise errors.NotFoundError("Current or new plan not found")

            current_amount = self._amount_for_cycle(current_plan, req.billing_cycle)
            new_amount = self._amount_for_cycle(new_plan, req.billing_cycle)

            # Simple proration based on days remaining in subscription term
            total_days = (sub.end_date - sub.start_date).days or 1  # type: ignore[attr-defined]
            remaining_days = (sub.end_date - req.effective_from).days  # type: ignore[attr-defined]
            remaining_ratio = Decimal(str(max(0, remaining_days))) / Decimal(str(total_days))

            diff = new_amount - current_amount
            if diff > 0:
                prorated_charge = diff * remaining_ratio
                prorated_refund = Decimal("0")
            else:
                prorated_charge = Decimal("0")
                prorated_refund = abs(diff) * remaining_ratio

        message = "Upgrade preview" if diff >= 0 else "Downgrade preview"

        return UpgradePreview(
            current_plan_name=current_plan.display_name,
            new_plan_name=new_plan.display_name,
            current_amount=current_amount,
            new_amount=new_amount,
            prorated_charge=prorated_charge.quantize(Decimal("0.01")),
            prorated_refund=prorated_refund.quantize(Decimal("0.01")),
            effective_from=req.effective_from,
            message=message,
        )

    def _amount_for_cycle(self, plan, billing_cycle) -> Decimal:
        if billing_cycle.name == "MONTHLY":
            return plan.price_monthly
        if billing_cycle.name == "YEARLY":
            return plan.price_yearly
        # Default to monthly
        return plan.price_monthly

    # ------------------------------------------------------------------ #
    # Apply upgrade
    # ------------------------------------------------------------------ #
    def apply_upgrade(self, req: UpgradeRequest) -> SubscriptionResponse:
        """
        Apply upgrade to Subscription: switch plan + billing_cycle/amount.

        NOTE:
        - Does not create billing records; caller should handle charging/refunding
          based on preview_upgrade.
        """
        from app.schemas.subscription.subscription_response import SubscriptionResponse as SubRespSchema

        preview = self.preview_upgrade(req)

        with UnitOfWork(self._session_factory) as uow:
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)

            sub = sub_repo.get_active_for_hostel(req.hostel_id, as_of=req.effective_from)
            if not sub:
                raise errors.NotFoundError(f"No active subscription for hostel {req.hostel_id}")

            new_plan = plan_repo.get(req.new_plan_id)
            if not new_plan:
                raise errors.NotFoundError(f"New plan {req.new_plan_id} not found")

            # Update subscription
            sub.plan_id = req.new_plan_id  # type: ignore[attr-defined]
            sub.billing_cycle = req.billing_cycle  # type: ignore[attr-defined]
            sub.amount = preview.new_amount  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        # Use SubscriptionService for consistent mapping if desired;
        # here we construct a minimal SubscriptionResponse-like object.
        return SubRespSchema(
            id=sub.id,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            hostel_id=sub.hostel_id,
            hostel_name="",  # could be filled via HostelRepository if needed
            plan_id=sub.plan_id,
            plan_name=new_plan.plan_name,
            display_name=new_plan.display_name,
            plan_type=new_plan.plan_type,
            subscription_reference=sub.subscription_reference,
            billing_cycle=sub.billing_cycle,
            amount=sub.amount,
            currency=sub.currency,
            start_date=sub.start_date,
            end_date=sub.end_date,
            auto_renew=sub.auto_renew,
            next_billing_date=sub.next_billing_date,
            status=sub.status,
            trial_end_date=None,
            last_payment_date=None,
            last_payment_amount=None,
        )