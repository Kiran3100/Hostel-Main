# app/services/payment/refund_service.py
from __future__ import annotations

from datetime import datetime, timezone, date
from decimal import Decimal
from typing import List, Optional, Protocol
from uuid import UUID, uuid4

from app.repositories.transactions import PaymentRepository
from app.schemas.payment.payment_refund import (
    RefundRequest,
    RefundResponse,
    RefundStatus,
    RefundApproval,
    RefundList,
    RefundListItem,
)
from app.services.common import UnitOfWork, errors
from sqlalchemy.orm import Session


class RefundStore(Protocol):
    """
    Storage for refund records.

    Expected record keys (example):
        {
            "refund_id": UUID,
            "payment_id": UUID,
            "payment_reference": str,
            "refund_amount": Decimal,
            "refund_status": str,
            "refund_method": str,
            "refund_reference": str | None,
            "requested_at": datetime,
            "processed_at": datetime | None,
            "completed_at": datetime | None,
            "estimated_completion_date": date | None,
            "refunded_to": str,
        }
    """

    def save_refund(self, record: dict) -> dict: ...
    def get_refund(self, refund_id: UUID) -> Optional[dict]: ...
    def update_refund(self, refund_id: UUID, data: dict) -> dict: ...
    def list_refunds(self) -> List[dict]: ...


class RefundService:
    """
    Refund management:

    - Create refund requests
    - Track refund status
    - Approve/reject refunds
    - Simple listing
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: RefundStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    # ------------------------------------------------------------------ #
    # Create / approve
    # ------------------------------------------------------------------ #
    def create_refund(self, data: RefundRequest) -> RefundResponse:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)

            p = pay_repo.get(data.payment_id)
            if p is None:
                raise errors.NotFoundError(f"Payment {data.payment_id} not found")

            if data.refund_amount > p.amount:
                raise errors.ValidationError("Refund amount cannot exceed payment amount")

            refund_id = uuid4()
            now = self._now()

            record = {
                "refund_id": refund_id,
                "payment_id": p.id,
                "payment_reference": str(p.id),
                "refund_amount": data.refund_amount,
                "refund_status": "pending",
                "refund_method": data.refund_method,
                "refund_reference": None,
                "requested_at": now,
                "processed_at": None,
                "completed_at": None,
                "estimated_completion_date": None,
                "refunded_to": "original_source",
            }
            self._store.save_refund(record)

        return RefundResponse(
            id=refund_id,
            created_at=now,
            updated_at=now,
            refund_id=refund_id,
            payment_id=p.id,
            payment_reference=str(p.id),
            refund_amount=data.refund_amount,
            refund_status="pending",
            refund_method=data.refund_method,
            refund_reference=None,
            requested_at=now,
            processed_at=None,
            completed_at=None,
            estimated_completion_date=None,
            refunded_to="original_source",
            message="Refund request created",
        )

    def approve_refund(self, data: RefundApproval) -> RefundStatus:
        record = self._store.get_refund(data.refund_id)
        if not record:
            raise errors.NotFoundError(f"Refund {data.refund_id} not found")

        now = self._now()

        if not data.approved:
            record["refund_status"] = "failed"
            record["failure_reason"] = data.rejection_reason or "Refund rejected"
            record["completed_at"] = now
        else:
            record["refund_status"] = "processing"
            record["processing_started_at"] = now

        self._store.update_refund(data.refund_id, record)

        return RefundStatus(
            refund_id=data.refund_id,
            payment_reference=record["payment_reference"],
            refund_amount=record["refund_amount"],
            currency="INR",
            status=record["refund_status"],
            requested_at=record["requested_at"],
            processing_started_at=record.get("processing_started_at"),
            completed_at=record.get("completed_at"),
            days_since_request=(now.date() - record["requested_at"].date()).days,
            failure_reason=record.get("failure_reason"),
            next_action=None,
            expected_completion_date=record.get("estimated_completion_date"),
        )

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_refunds(self) -> RefundList:
        records = self._store.list_refunds()
        total_amount = sum(
            Decimal(str(r.get("refund_amount"))) for r in records
        ) if records else Decimal("0")

        items: List[RefundListItem] = []
        for r in records:
            items.append(
                RefundListItem(
                    refund_id=r["refund_id"],
                    payment_reference=r["payment_reference"],
                    student_name="",
                    refund_amount=r["refund_amount"],
                    status=r["refund_status"],
                    requested_at=r["requested_at"],
                    completed_at=r.get("completed_at"),
                )
            )

        return RefundList(
            total_refunds=len(records),
            total_amount_refunded=total_amount,
            refunds=items,
        )