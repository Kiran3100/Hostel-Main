# app/services/payment/payment_reporting_service.py
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Callable, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.schemas.common.enums import PaymentStatus
from app.schemas.payment.payment_filters import PaymentReportRequest
from app.services.common import UnitOfWork, errors


class PaymentReportingService:
    """
    Payment reporting and aggregation:

    - Build grouped aggregates for PaymentReportRequest
      (by day/week/month/payment_type/payment_method).
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def build_report(self, req: PaymentReportRequest) -> Dict[str, object]:
        """
        Return a simple dict-based report structure for the given request.

        Structure example:
        {
            "hostel_id": ...,
            "period": {"from": ..., "to": ...},
            "group_by": "day",
            "totals": {...},
            "groups": [
                {"key": "...", "total_amount": ..., "count": ..., "completed": ...},
                ...
            ],
        }
        """
        if req.date_from > req.date_to:
            raise errors.ValidationError("date_from must be <= date_to")

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_payment_repo(uow)

            filters: Dict[str, object] = {}
            if req.hostel_id:
                filters["hostel_id"] = req.hostel_id
            if req.payment_types:
                filters["payment_type"] = req.payment_types
            if req.payment_methods:
                filters["payment_method"] = req.payment_methods

            payments = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

        # Time filter on paid_at or created_at
        in_period = []
        for p in payments:
            d = p.paid_at.date() if p.paid_at else p.created_at.date()
            if req.date_from <= d <= req.date_to:
                in_period.append(p)

        total_amount = Decimal("0")
        total_count = 0
        total_completed = 0

        for p in in_period:
            total_amount += p.amount
            total_count += 1
            if p.payment_status == PaymentStatus.COMPLETED:
                total_completed += 1

        groups = self._group_payments(in_period, req.group_by)

        return {
            "hostel_id": req.hostel_id,
            "period": {"from": req.date_from, "to": req.date_to},
            "group_by": req.group_by,
            "totals": {
                "total_amount": total_amount,
                "total_count": total_count,
                "completed_count": total_completed,
            },
            "groups": groups,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _group_payments(self, payments: List, group_by: str) -> List[Dict[str, object]]:
        buckets: Dict[str, Dict[str, object]] = {}

        for p in payments:
            d = p.paid_at.date() if p.paid_at else p.created_at.date()
            if group_by == "day":
                key = d.isoformat()
            elif group_by == "week":
                iso_year, iso_week, _ = d.isocalendar()
                key = f"{iso_year}-W{iso_week:02d}"
            elif group_by == "month":
                key = d.strftime("%Y-%m")
            elif group_by == "payment_type":
                key = p.payment_type.value if hasattr(p.payment_type, "value") else str(p.payment_type)
            elif group_by == "payment_method":
                key = p.payment_method.value if hasattr(p.payment_method, "value") else str(p.payment_method)
            else:
                key = "other"

            bucket = buckets.setdefault(
                key,
                {
                    "key": key,
                    "total_amount": Decimal("0"),
                    "count": 0,
                    "completed": 0,
                },
            )
            bucket["total_amount"] += p.amount
            bucket["count"] += 1
            if p.payment_status == PaymentStatus.COMPLETED:
                bucket["completed"] += 1

        return list(buckets.values())