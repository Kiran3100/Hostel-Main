# app/services/subscription/subscription_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import SubscriptionRepository, SubscriptionPlanRepository
from app.repositories.core import HostelRepository
from app.schemas.subscription.subscription_base import (
    SubscriptionCreate,
    SubscriptionUpdate,
)
from app.schemas.subscription.subscription_response import (
    SubscriptionResponse,
    BillingHistory,
    BillingHistoryItem,
)
from app.services.common import UnitOfWork, errors


class SubscriptionService:
    """
    Hostel subscription management:

    - Create / update subscription records
    - Get subscription detail
    - Get active subscription for a hostel
    - (Skeleton) billing history placeholder
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

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        sub,
        *,
        hostel_name: str,
        plan,
    ) -> SubscriptionResponse:
        return SubscriptionResponse(
            id=sub.id,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            hostel_id=sub.hostel_id,
            hostel_name=hostel_name,
            plan_id=sub.plan_id,
            plan_name=plan.plan_name if plan else "",
            display_name=plan.display_name if plan else "",
            plan_type=plan.plan_type if plan else None,
            subscription_reference=sub.subscription_reference,
            billing_cycle=sub.billing_cycle,
            amount=sub.amount,
            currency=sub.currency,
            start_date=sub.start_date,
            end_date=sub.end_date,
            auto_renew=sub.auto_renew,
            next_billing_date=sub.next_billing_date,
            status=sub.status,
            trial_end_date=None,           # not stored in model
            last_payment_date=None,        # can be wired via PaymentRepository
            last_payment_amount=None,      # can be wired via PaymentRepository
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_subscription(self, data: SubscriptionCreate) -> SubscriptionResponse:
        with UnitOfWork(self._session_factory) as uow:
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            plan = plan_repo.get(data.plan_id)
            if plan is None:
                raise errors.NotFoundError(f"SubscriptionPlan {data.plan_id} not found")

            payload = data.model_dump(exclude={"trial_end_date"}, exclude_unset=True)
            sub = sub_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self._to_response(sub, hostel_name=hostel.name, plan=plan)

    def update_subscription(self, subscription_id: UUID, data: SubscriptionUpdate) -> SubscriptionResponse:
        with UnitOfWork(self._session_factory) as uow:
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            sub = sub_repo.get(subscription_id)
            if sub is None:
                raise errors.NotFoundError(f"Subscription {subscription_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(sub, field) and field != "id":
                    setattr(sub, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            hostel = hostel_repo.get(sub.hostel_id)
            plan = plan_repo.get(sub.plan_id)
            uow.commit()

            hostel_name = hostel.name if hostel else ""
            return self._to_response(sub, hostel_name=hostel_name, plan=plan)

    def get_subscription(self, subscription_id: UUID) -> SubscriptionResponse:
        with UnitOfWork(self._session_factory) as uow:
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            sub = sub_repo.get(subscription_id)
            if sub is None:
                raise errors.NotFoundError(f"Subscription {subscription_id} not found")

            hostel = hostel_repo.get(sub.hostel_id)
            plan = plan_repo.get(sub.plan_id)
            hostel_name = hostel.name if hostel else ""
            return self._to_response(sub, hostel_name=hostel_name, plan=plan)

    # ------------------------------------------------------------------ #
    # Active subscription
    # ------------------------------------------------------------------ #
    def get_active_for_hostel(self, hostel_id: UUID, as_of: Optional[date] = None) -> Optional[SubscriptionResponse]:
        with UnitOfWork(self._session_factory) as uow:
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            sub = sub_repo.get_active_for_hostel(hostel_id, as_of=as_of)
            if not sub:
                return None

            hostel = hostel_repo.get(sub.hostel_id)
            plan = plan_repo.get(sub.plan_id)
            hostel_name = hostel.name if hostel else ""
            return self._to_response(sub, hostel_name=hostel_name, plan=plan)

    # ------------------------------------------------------------------ #
    # Billing history (placeholder)
    # ------------------------------------------------------------------ #
    def get_billing_history(self, subscription_id: UUID) -> BillingHistory:
        """
        Placeholder: returns an empty BillingHistory.

        For a real implementation, this should be wired to invoices/payments
        generated per billing cycle.
        """
        return BillingHistory(
            subscription_id=subscription_id,
            hostel_id=UUID(int=0),
            items=[],
            total_billed=Decimal("0"),
            total_paid=Decimal("0"),
            total_outstanding=Decimal("0"),
        )