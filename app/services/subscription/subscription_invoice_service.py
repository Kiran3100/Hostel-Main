"""
Subscription Invoice Service

Manages invoices generated for subscription billing cycles.

Improvements:
- Enhanced validation and error handling
- Added invoice numbering logic
- Improved payment tracking
- Better status transition validation
- Added bulk operations support
- Enhanced logging and audit trail
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.subscription import SubscriptionInvoiceRepository
from app.schemas.subscription import (
    GenerateInvoiceRequest,
    InvoiceInfo,
    InvoiceStatus,
)
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SubscriptionInvoiceService:
    """
    High-level service for subscription invoices.

    Responsibilities:
    - Generate invoices from billing cycles
    - Retrieve/list/search invoices
    - Update invoice status (paid, cancelled, refunded)
    - Handle partial payments
    - Generate invoice numbers
    - Track payment history
    """

    # Constants
    DECIMAL_PLACES = 2
    DEFAULT_PAYMENT_TERMS_DAYS = 30
    
    def __init__(
        self,
        invoice_repo: SubscriptionInvoiceRepository,
    ) -> None:
        """
        Initialize the invoice service.

        Args:
            invoice_repo: Repository for invoice data access

        Raises:
            ValueError: If repository is None
        """
        if not invoice_repo:
            raise ValueError("Invoice repository is required")
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

        Args:
            db: Database session
            request: Invoice generation request with all required data

        Returns:
            InvoiceInfo with generated invoice details

        Raises:
            ValidationException: If validation fails
        """
        # Validate request
        self._validate_invoice_request(request)

        try:
            # Prepare invoice data
            data = request.model_dump(exclude_none=True)
            
            # Add system-generated fields
            data["invoice_number"] = self._generate_invoice_number(db)
            data["status"] = InvoiceStatus.DRAFT.value
            data["generated_at"] = datetime.utcnow()
            
            # Set default due date if not provided
            if "due_date" not in data or not data["due_date"]:
                data["due_date"] = datetime.utcnow() + timedelta(
                    days=self.DEFAULT_PAYMENT_TERMS_DAYS
                )

            # Create invoice
            obj = self.invoice_repo.create_invoice(db, data)
            
            logger.info(
                f"Generated invoice {obj.invoice_number} for subscription "
                f"{request.subscription_id}: {request.total_amount} {request.currency}"
            )
            
            return InvoiceInfo.model_validate(obj)

        except Exception as e:
            logger.error(
                f"Failed to generate invoice for subscription {request.subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to generate invoice: {str(e)}")

    def generate_invoices_batch(
        self,
        db: Session,
        requests: List[GenerateInvoiceRequest],
    ) -> List[InvoiceInfo]:
        """
        Generate multiple invoices in batch.

        Args:
            db: Database session
            requests: List of invoice generation requests

        Returns:
            List of generated InvoiceInfo objects
        """
        if not requests:
            return []

        generated_invoices = []
        failed_requests = []

        for request in requests:
            try:
                invoice = self.generate_invoice(db, request)
                generated_invoices.append(invoice)
            except ValidationException as e:
                logger.warning(
                    f"Failed to generate invoice for subscription {request.subscription_id}: {str(e)}"
                )
                failed_requests.append((request, str(e)))

        if failed_requests:
            logger.warning(f"Batch generation completed with {len(failed_requests)} failures")

        return generated_invoices

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_invoice(
        self,
        db: Session,
        invoice_id: UUID,
    ) -> InvoiceInfo:
        """
        Retrieve an invoice by ID.

        Args:
            db: Database session
            invoice_id: UUID of the invoice

        Returns:
            InvoiceInfo

        Raises:
            ValidationException: If invoice not found
        """
        obj = self.invoice_repo.get_by_id(db, invoice_id)
        if not obj:
            logger.warning(f"Invoice not found: {invoice_id}")
            raise ValidationException(f"Invoice not found with ID: {invoice_id}")
        
        return InvoiceInfo.model_validate(obj)

    def get_invoice_by_number(
        self,
        db: Session,
        invoice_number: str,
    ) -> Optional[InvoiceInfo]:
        """
        Retrieve an invoice by invoice number.

        Args:
            db: Database session
            invoice_number: Invoice number

        Returns:
            InvoiceInfo or None if not found
        """
        obj = self.invoice_repo.get_by_invoice_number(db, invoice_number)
        return InvoiceInfo.model_validate(obj) if obj else None

    def list_invoices_for_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        status: Optional[InvoiceStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InvoiceInfo]:
        """
        List invoices for a subscription with optional filters.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            status: Optional status filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of InvoiceInfo objects
        """
        objs = self.invoice_repo.get_by_subscription_id(
            db,
            subscription_id=subscription_id,
            status=status.value if status else None,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
        return [InvoiceInfo.model_validate(o) for o in objs]

    def list_invoices_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        status: Optional[InvoiceStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InvoiceInfo]:
        """
        List invoices for a hostel with optional filters.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            status: Optional status filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of InvoiceInfo objects
        """
        objs = self.invoice_repo.get_by_hostel_id(
            db,
            hostel_id=hostel_id,
            status=status.value if status else None,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
        return [InvoiceInfo.model_validate(o) for o in objs]

    def search_invoices(
        self,
        db: Session,
        search_term: Optional[str] = None,
        status: Optional[InvoiceStatus] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        overdue_only: bool = False,
    ) -> List[InvoiceInfo]:
        """
        Search invoices with multiple filters.

        Args:
            db: Database session
            search_term: Search in invoice number or description
            status: Filter by status
            min_amount: Minimum invoice amount
            max_amount: Maximum invoice amount
            overdue_only: Only return overdue invoices

        Returns:
            List of matching InvoiceInfo objects
        """
        objs = self.invoice_repo.search_invoices(
            db,
            search_term=search_term,
            status=status.value if status else None,
            min_amount=min_amount,
            max_amount=max_amount,
            overdue_only=overdue_only,
        )
        return [InvoiceInfo.model_validate(o) for o in objs]

    def get_overdue_invoices(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> List[InvoiceInfo]:
        """
        Get all overdue invoices, optionally filtered by hostel.

        Args:
            db: Database session
            hostel_id: Optional hostel ID filter

        Returns:
            List of overdue InvoiceInfo objects
        """
        return self.search_invoices(
            db,
            overdue_only=True,
            status=InvoiceStatus.PENDING,
        )

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
        payment_method: Optional[str] = None,
    ) -> InvoiceInfo:
        """
        Mark an invoice as paid or partially paid.

        Args:
            db: Database session
            invoice_id: UUID of the invoice
            amount_paid: Amount paid (can be partial)
            payment_reference: Optional payment reference/transaction ID
            paid_at: Optional payment timestamp (defaults to now)
            payment_method: Optional payment method

        Returns:
            Updated InvoiceInfo

        Raises:
            ValidationException: If invoice not found or validation fails
        """
        obj = self.invoice_repo.get_by_id(db, invoice_id)
        if not obj:
            raise ValidationException(f"Invoice not found with ID: {invoice_id}")

        # Validate amount
        if amount_paid <= 0:
            raise ValidationException("Payment amount must be positive")

        total_amount = Decimal(str(obj.total_amount))
        paid_amount = Decimal(str(amount_paid))
        previous_paid = Decimal(str(obj.amount_paid or 0))

        if previous_paid + paid_amount > total_amount:
            raise ValidationException(
                f"Payment amount ({amount_paid}) exceeds outstanding balance "
                f"({float(total_amount - previous_paid)})"
            )

        try:
            updated = self.invoice_repo.mark_paid(
                db,
                obj,
                amount_paid=float(paid_amount),
                payment_reference=payment_reference,
                paid_at=paid_at or datetime.utcnow(),
                payment_method=payment_method,
            )
            
            logger.info(
                f"Invoice {obj.invoice_number} payment recorded: "
                f"{amount_paid} {obj.currency}. Reference: {payment_reference}"
            )
            
            return InvoiceInfo.model_validate(updated)

        except Exception as e:
            logger.error(f"Failed to mark invoice {invoice_id} as paid: {str(e)}")
            raise ValidationException(f"Failed to update invoice: {str(e)}")

    def update_invoice_status(
        self,
        db: Session,
        invoice_id: UUID,
        status: InvoiceStatus,
        reason: Optional[str] = None,
    ) -> InvoiceInfo:
        """
        Update invoice status to cancelled/refunded/etc.

        Args:
            db: Database session
            invoice_id: UUID of the invoice
            status: New invoice status
            reason: Optional reason for status change

        Returns:
            Updated InvoiceInfo

        Raises:
            ValidationException: If invoice not found or invalid transition
        """
        obj = self.invoice_repo.get_by_id(db, invoice_id)
        if not obj:
            raise ValidationException(f"Invoice not found with ID: {invoice_id}")

        # Validate status transition
        current_status = InvoiceStatus(obj.status)
        self._validate_status_transition(current_status, status)

        update_data = {
            "status": status.value,
            "status_reason": reason,
        }

        # Add timestamps for specific statuses
        if status == InvoiceStatus.CANCELLED:
            update_data["cancelled_at"] = datetime.utcnow()
        elif status == InvoiceStatus.REFUNDED:
            update_data["refunded_at"] = datetime.utcnow()
        elif status == InvoiceStatus.SENT:
            update_data["sent_at"] = datetime.utcnow()

        try:
            updated = self.invoice_repo.update(db, obj, data=update_data)
            
            logger.info(
                f"Invoice {obj.invoice_number} status updated to {status.value}. "
                f"Reason: {reason or 'N/A'}"
            )
            
            return InvoiceInfo.model_validate(updated)

        except Exception as e:
            logger.error(
                f"Failed to update invoice {invoice_id} status to {status.value}: {str(e)}"
            )
            raise ValidationException(f"Failed to update invoice status: {str(e)}")

    def void_invoice(
        self,
        db: Session,
        invoice_id: UUID,
        reason: str,
    ) -> InvoiceInfo:
        """
        Void an invoice (mark as cancelled with specific reason).

        Args:
            db: Database session
            invoice_id: UUID of the invoice
            reason: Reason for voiding

        Returns:
            Updated InvoiceInfo
        """
        return self.update_invoice_status(
            db,
            invoice_id=invoice_id,
            status=InvoiceStatus.VOID,
            reason=reason,
        )

    # -------------------------------------------------------------------------
    # Analytics and reporting
    # -------------------------------------------------------------------------

    def get_invoice_summary(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get summary statistics for invoices.

        Args:
            db: Database session
            hostel_id: Optional hostel ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with invoice statistics
        """
        try:
            summary = self.invoice_repo.get_invoice_summary(
                db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )
            
            logger.debug(f"Generated invoice summary for hostel {hostel_id or 'all'}")
            return summary

        except Exception as e:
            logger.error(f"Error generating invoice summary: {str(e)}")
            return {}

    def get_total_revenue(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Decimal:
        """
        Calculate total revenue from paid invoices.

        Args:
            db: Database session
            hostel_id: Optional hostel ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Total revenue as Decimal
        """
        paid_invoices = self.list_invoices_for_hostel(
            db,
            hostel_id=hostel_id,
            status=InvoiceStatus.PAID,
            start_date=start_date,
            end_date=end_date,
        ) if hostel_id else []

        total = sum(
            (Decimal(str(inv.total_amount)) for inv in paid_invoices),
            Decimal("0.00")
        )
        
        return total

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_invoice_request(self, request: GenerateInvoiceRequest) -> None:
        """
        Validate invoice generation request.

        Args:
            request: Invoice generation request

        Raises:
            ValidationException: If validation fails
        """
        if request.total_amount <= 0:
            raise ValidationException("Invoice total amount must be positive")

        if request.subtotal and request.subtotal < 0:
            raise ValidationException("Invoice subtotal cannot be negative")

        if request.tax_amount and request.tax_amount < 0:
            raise ValidationException("Tax amount cannot be negative")

        if not request.currency or len(request.currency) != 3:
            raise ValidationException("Invalid currency code")

    def _generate_invoice_number(self, db: Session) -> str:
        """
        Generate a unique invoice number.

        Args:
            db: Database session

        Returns:
            Generated invoice number
        """
        # Use timestamp + counter for uniqueness
        now = datetime.utcnow()
        prefix = f"INV-{now.year}{now.month:02d}"
        
        # Get count of invoices for this month
        count = self.invoice_repo.get_invoice_count_for_period(
            db,
            year=now.year,
            month=now.month,
        )
        
        invoice_number = f"{prefix}-{count + 1:06d}"
        
        logger.debug(f"Generated invoice number: {invoice_number}")
        return invoice_number

    def _validate_status_transition(
        self,
        current_status: InvoiceStatus,
        new_status: InvoiceStatus,
    ) -> None:
        """
        Validate if an invoice status transition is allowed.

        Args:
            current_status: Current invoice status
            new_status: Desired new status

        Raises:
            ValidationException: If transition is not allowed
        """
        # Define allowed transitions
        allowed_transitions = {
            InvoiceStatus.DRAFT: {
                InvoiceStatus.PENDING,
                InvoiceStatus.SENT,
                InvoiceStatus.CANCELLED,
                InvoiceStatus.VOID,
            },
            InvoiceStatus.PENDING: {
                InvoiceStatus.SENT,
                InvoiceStatus.PAID,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.CANCELLED,
                InvoiceStatus.VOID,
            },
            InvoiceStatus.SENT: {
                InvoiceStatus.PAID,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.CANCELLED,
                InvoiceStatus.VOID,
            },
            InvoiceStatus.PARTIALLY_PAID: {
                InvoiceStatus.PAID,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.REFUNDED,
            },
            InvoiceStatus.PAID: {
                InvoiceStatus.REFUNDED,
            },
            InvoiceStatus.OVERDUE: {
                InvoiceStatus.PAID,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.CANCELLED,
                InvoiceStatus.VOID,
            },
            InvoiceStatus.CANCELLED: set(),  # Terminal state
            InvoiceStatus.REFUNDED: set(),  # Terminal state
            InvoiceStatus.VOID: set(),  # Terminal state
        }

        if new_status not in allowed_transitions.get(current_status, set()):
            raise ValidationException(
                f"Invalid invoice status transition from {current_status.value} "
                f"to {new_status.value}"
            )