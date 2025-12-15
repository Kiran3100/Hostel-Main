# app/services/subscription/subscription_billing_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, List, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.transactions import SubscriptionRepository, SubscriptionPlanRepository
from app.schemas.subscription.subscription_billing import (
    BillingCycleInfo,
    GenerateInvoiceRequest,
    InvoiceInfo,
)
from app.schemas.common.enums import BillingCycle
from app.services.common import UnitOfWork, errors


class InvoiceStore(Protocol):
    """
    Storage abstraction for invoices.

    Expected record keys:

        {
            "invoice_id": UUID,
            "subscription_id": UUID,
            "hostel_id": UUID,
            "invoice_number": str,
            "invoice_date": date,
            "due_date": date,
            "amount": Decimal,
            "currency": str,
            "status": str,  # draft|issued|paid|overdue|cancelled
            "invoice_url": str | None,
        }
    """

    def save_invoice(self, record: dict) -> dict: ...
    def get_invoice(self, invoice_id: UUID) -> Optional[dict]: ...
    def list_invoices_for_subscription(self, subscription_id: UUID) -> List[dict]: ...


class SubscriptionBillingService:
    """
    Subscription billing:

    - Provide BillingCycleInfo for a subscription
    - Generate an invoice for a billing date
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        invoice_store: InvoiceStore,
    ) -> None:
        self._session_factory = session_factory
        self._invoice_store = invoice_store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_sub_repo(self, uow: UnitOfWork) -> SubscriptionRepository:
        return uow.get_repo(SubscriptionRepository)

    def _get_plan_repo(self, uow: UnitOfWork) -> SubscriptionPlanRepository:
        return uow.get_repo(SubscriptionPlanRepository)

    # ------------------------------------------------------------------ #
    # Billing cycle
    # ------------------------------------------------------------------ #
    def get_billing_cycle_info(
        self,
        subscription_id: UUID,
        *,
        as_of: Optional[date] = None,
    ) -> BillingCycleInfo:
        """
        Compute a simple BillingCycleInfo for a subscription.

        Currently uses the full subscription start/end as the cycle period.
        """
        with UnitOfWork(self._session_factory) as uow:
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)

            sub = sub_repo.get(subscription_id)
            if sub is None:
                raise errors.NotFoundError(f"Subscription {subscription_id} not found")

            plan = plan_repo.get(sub.plan_id)
            plan_name = plan.display_name if plan else ""

        cycle_start = sub.start_date
        cycle_end = sub.end_date
        billing_cycle_str = sub.billing_cycle.value if hasattr(sub.billing_cycle, "value") else str(sub.billing_cycle)

        info = BillingCycleInfo(
            subscription_id=sub.id,
            hostel_id=sub.hostel_id,
            plan_name=plan_name,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            billing_cycle=billing_cycle_str,
            amount=sub.amount,
            currency=sub.currency,
            next_billing_date=sub.next_billing_date or cycle_end,
            auto_renew=sub.auto_renew,
        )
        return info

    # ------------------------------------------------------------------ #
    # Invoice generation
    # ------------------------------------------------------------------ #
    def generate_invoice(self, req: GenerateInvoiceRequest) -> InvoiceInfo:
        """
        Generate and persist an invoice for the given subscription & billing_date.
        """
        with UnitOfWork(self._session_factory) as uow:
            sub_repo = self._get_sub_repo(uow)

            sub = sub_repo.get(req.subscription_id)
            if sub is None:
                raise errors.NotFoundError(f"Subscription {req.subscription_id} not found")

        amount = req.amount_override or sub.amount  # type: ignore[attr-defined]
        invoice_id = uuid4()
        invoice_number = f"INV-{sub.id}-{req.billing_date.isoformat()}"  # type: ignore[attr-defined]
        due_date = req.billing_date

        record = {
            "invoice_id": invoice_id,
            "subscription_id": sub.id,      # type: ignore[attr-defined]
            "hostel_id": sub.hostel_id,     # type: ignore[attr-defined]
            "invoice_number": invoice_number,
            "invoice_date": req.billing_date,
            "due_date": due_date,
            "amount": amount,
            "currency": sub.currency,       # type: ignore[attr-defined]
            "status": "issued",
            "invoice_url": None,
        }
        saved = self._invoice_store.save_invoice(record)

        return InvoiceInfo.model_validate(saved)