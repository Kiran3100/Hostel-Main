# app/services/payment/payment_service.py
"""
Payment Service

Core payment orchestration for:
- Creating manual (offline) payments
- Retrieving and listing payments
- High-level summary per student/hostel
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentRepository, PaymentAggregateRepository
from app.schemas.payment import (
    ManualPaymentRequest,
    PaymentResponse,
    PaymentDetail,
    PaymentListItem,
    PaymentSummary,
    PaymentFilterParams,
    PaymentSortOptions,
)
from app.core.exceptions import ValidationException
from app.models.base.enums import PaymentStatus


class PaymentService:
    """
    High-level orchestration for payments.

    Delegates persistence and heavy querying to PaymentRepository and
    analytics/summary to PaymentAggregateRepository.
    """

    def __init__(
        self,
        payment_repo: PaymentRepository,
        aggregate_repo: PaymentAggregateRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # Manual payments (offline)
    # -------------------------------------------------------------------------

    def record_manual_payment(
        self,
        db: Session,
        request: ManualPaymentRequest,
    ) -> PaymentResponse:
        """
        Record an offline/manual payment (cash/cheque/bank transfer).

        The repository is responsible for:
        - Creating Payment entity
        - Validating method-specific fields (cheque/bank details)
        - Setting appropriate status (e.g. COMPLETED for cash)
        """
        payload = request.model_dump(exclude_none=True)
        obj = self.payment_repo.create_manual_payment(db, payload)
        return PaymentResponse.model_validate(obj)

    # -------------------------------------------------------------------------
    # Retrieval & listing
    # -------------------------------------------------------------------------

    def get_payment(
        self,
        db: Session,
        payment_id: UUID,
    ) -> PaymentDetail:
        obj = self.payment_repo.get_by_id(db, payment_id)
        if not obj:
            raise ValidationException("Payment not found")
        return PaymentDetail.model_validate(obj)

    def list_payments_for_student(
        self,
        db: Session,
        student_id: UUID,
        filters: Optional[PaymentFilterParams] = None,
        sort: Optional[PaymentSortOptions] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[PaymentListItem], int]:
        """
        List payments for a student with filtering/sorting/pagination.
        """
        filters_dict = filters.model_dump(exclude_none=True) if filters else {}
        sort_dict = sort.model_dump(exclude_none=True) if sort else {}

        result = self.payment_repo.search_payments_for_student(
            db=db,
            student_id=student_id,
            filters=filters_dict,
            sort=sort_dict,
            page=page,
            page_size=page_size,
        )
        items = [PaymentListItem.model_validate(o) for o in result["items"]]
        total = result["total"]
        return items, total

    def list_payments_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        filters: Optional[PaymentFilterParams] = None,
        sort: Optional[PaymentSortOptions] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[PaymentListItem], int]:
        filters_dict = filters.model_dump(exclude_none=True) if filters else {}
        sort_dict = sort.model_dump(exclude_none=True) if sort else {}

        result = self.payment_repo.search_payments_for_hostel(
            db=db,
            hostel_id=hostel_id,
            filters=filters_dict,
            sort=sort_dict,
            page=page,
            page_size=page_size,
        )
        items = [PaymentListItem.model_validate(o) for o in result["items"]]
        total = result["total"]
        return items, total

    # -------------------------------------------------------------------------
    # Status updates
    # -------------------------------------------------------------------------

    def mark_payment_status(
        self,
        db: Session,
        payment_id: UUID,
        status: PaymentStatus,
        failure_reason: Optional[str] = None,
    ) -> PaymentResponse:
        """
        Update payment status.

        Typically called from gateway or reconciliation flows.
        """
        obj = self.payment_repo.get_by_id(db, payment_id)
        if not obj:
            raise ValidationException("Payment not found")

        updated = self.payment_repo.update(
            db,
            obj,
            data={
                "status": status.value,
                "failure_reason": failure_reason,
            },
        )
        return PaymentResponse.model_validate(updated)

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------

    def get_student_payment_summary(
        self,
        db: Session,
        student_id: UUID,
    ) -> PaymentSummary:
        data = self.aggregate_repo.get_student_payment_summary(db, student_id)
        if not data:
            # Provide default empty summary
            return PaymentSummary(
                student_id=student_id,
                total_paid=0.0,
                total_pending=0.0,
                total_overdue=0.0,
                last_payment_date=None,
                last_payment_amount=0.0,
                next_due_date=None,
                next_due_amount=0.0,
                total_payments=0,
                completed_payments=0,
                pending_payments=0,
            )
        return PaymentSummary.model_validate(data)

    def get_hostel_payment_summary(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> PaymentSummary:
        data = self.aggregate_repo.get_hostel_payment_summary(db, hostel_id)
        if not data:
            return PaymentSummary(
                hostel_id=hostel_id,
                total_paid=0.0,
                total_pending=0.0,
                total_overdue=0.0,
                last_payment_date=None,
                last_payment_amount=0.0,
                next_due_date=None,
                next_due_amount=0.0,
                total_payments=0,
                completed_payments=0,
                pending_payments=0,
            )
        return PaymentSummary.model_validate(data)