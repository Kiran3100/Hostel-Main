"""
Subscription Invoice Service

Manages invoices generated for subscription billing cycles.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.subscription import SubscriptionInvoiceRepository
from app.schemas.subscription import (
    GenerateInvoiceRequest,
    InvoiceInfo,
    InvoiceStatus,
)
from app.core.exceptions import ValidationException


class SubscriptionInvoiceService:
    """
    High-level service for subscription invoices.

    Responsibilities:
    - Generate invoices from billing cycles
    - Retrieve/list/search invoices
    - Update invoice status (paid, cancelled, refunded)
    """

    def __init__(
        self,
        invoice_repo: SubscriptionInvoiceRepository,
    ) -> None:
        self.invoice_repo = invoice_repo

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    def generate_invoice(
        self,
        db: Session,
        request: GenerateInvoiceRequest,
    ) -> InvoiceInfo:
        """
        Generate an invoice for a subscription billing cycle.

        The repository encapsulates pro-rating / tax calculations.
        """
        data = request.model_dump(exclude_none=True)
        obj = self.invoice_repo.create_invoice(db, data)
        return InvoiceInfo.model_validate(obj)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_invoice(
        self,
        db: Session,
        invoice_id: UUID,
    ) -> InvoiceInfo:
        obj = self.invoice_repo.get_by_id(db, invoice_id)
        if not obj:
            raise ValidationException("Invoice not found")
        return InvoiceInfo.model_validate(obj)

    def list_invoices_for_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        status: Optional[InvoiceStatus] = None,
    ) -> List[InvoiceInfo]:
        objs = self.invoice_repo.get_by_subscription_id(
            db,
            subscription_id=subscription_id,
            status=status.value if status else None,
        )
        return [InvoiceInfo.model_validate(o) for o in objs]

    def list_invoices_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        status: Optional[InvoiceStatus] = None,
    ) -> List[InvoiceInfo]:
        objs = self.invoice_repo.get_by_hostel_id(
            db,
            hostel_id=hostel_id,
            status=status.value if status else None,
        )
        return [InvoiceInfo.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Status updates
    # -------------------------------------------------------------------------

    def mark_invoice_paid(
        self,
        db: Session,
        invoice_id: UUID,
        amount_paid: float,
        payment_reference: Optional[str] = None,
        paid_at: Optional[datetime] = None,
    ) -> InvoiceInfo:
        """
        Mark an invoice as paid (or partially paid depending on amount).
        """
        obj = self.invoice_repo.get_by_id(db, invoice_id)
        if not obj:
            raise ValidationException("Invoice not found")

        updated = self.invoice_repo.mark_paid(
            db,
            obj,
            amount_paid=amount_paid,
            payment_reference=payment_reference,
            paid_at=paid_at or datetime.utcnow(),
        )
        return InvoiceInfo.model_validate(updated)

    def update_invoice_status(
        self,
        db: Session,
        invoice_id: UUID,
        status: InvoiceStatus,
        reason: Optional[str] = None,
    ) -> InvoiceInfo:
        """
        Update invoice status to cancelled/refunded/etc.
        """
        obj = self.invoice_repo.get_by_id(db, invoice_id)
        if not obj:
            raise ValidationException("Invoice not found")

        updated = self.invoice_repo.update(
            db,
            obj,
            data={
                "status": status.value,
                "status_reason": reason,
            },
        )
        return InvoiceInfo.model_validate(updated)