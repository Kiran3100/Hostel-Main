"""
Subscription Invoice Repository.

Manages invoice generation, tracking, payment processing,
and invoice-related operations.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.subscription.subscription_invoice import SubscriptionInvoice
from app.schemas.subscription.subscription_billing import InvoiceStatus


class SubscriptionInvoiceRepository:
    """
    Repository for subscription invoice operations.

    Provides methods for invoice management, payment tracking,
    and invoice analytics.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ==================== CREATE OPERATIONS ====================

    def create_invoice(
        self,
        invoice_data: Dict[str, Any],
    ) -> SubscriptionInvoice:
        """
        Create new subscription invoice.

        Args:
            invoice_data: Invoice configuration data

        Returns:
            Created invoice
        """
        invoice = SubscriptionInvoice(**invoice_data)
        self.db.add(invoice)
        self.db.flush()
        return invoice

    def generate_invoice_number(self, prefix: str = "INV") -> str:
        """
        Generate unique invoice number.

        Args:
            prefix: Invoice number prefix

        Returns:
            Unique invoice number
        """
        year = datetime.now().year
        
        # Get count of invoices for current year
        year_start = date(year, 1, 1)
        count_query = select(func.count(SubscriptionInvoice.id)).where(
            SubscriptionInvoice.invoice_date >= year_start
        )
        count = self.db.execute(count_query).scalar() or 0
        
        # Generate invoice number: INV-2024-000001
        invoice_number = f"{prefix}-{year}-{str(count + 1).zfill(6)}"
        
        # Check if exists and increment if necessary
        while self.get_by_invoice_number(invoice_number):
            count += 1
            invoice_number = f"{prefix}-{year}-{str(count + 1).zfill(6)}"
        
        return invoice_number

    def create_subscription_invoice(
        self,
        subscription_id: UUID,
        hostel_id: UUID,
        subtotal: Decimal,
        tax_amount: Decimal = Decimal("0.00"),
        discount_amount: Decimal = Decimal("0.00"),
        due_days: int = 7,
        billing_period_start: Optional[date] = None,
        billing_period_end: Optional[date] = None,
        notes: Optional[str] = None,
        discount_reason: Optional[str] = None,
    ) -> SubscriptionInvoice:
        """
        Create invoice for subscription.

        Args:
            subscription_id: Subscription ID
            hostel_id: Hostel ID
            subtotal: Invoice subtotal
            tax_amount: Tax amount
            discount_amount: Discount amount
            due_days: Days until due
            billing_period_start: Billing period start
            billing_period_end: Billing period end
            notes: Invoice notes
            discount_reason: Reason for discount

        Returns:
            Created invoice
        """
        invoice_number = self.generate_invoice_number()
        invoice_date = date.today()
        due_date = invoice_date + timedelta(days=due_days)
        
        amount = subtotal - discount_amount + tax_amount
        amount_due = amount
        
        invoice_data = {
            "subscription_id": subscription_id,
            "hostel_id": hostel_id,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "tax_amount": tax_amount,
            "amount": amount,
            "amount_paid": Decimal("0.00"),
            "amount_due": amount_due,
            "status": InvoiceStatus.DRAFT,
            "billing_period_start": billing_period_start,
            "billing_period_end": billing_period_end,
            "notes": notes,
            "discount_reason": discount_reason,
        }
        
        return self.create_invoice(invoice_data)

    # ==================== READ OPERATIONS ====================

    def get_by_id(
        self,
        invoice_id: UUID,
    ) -> Optional[SubscriptionInvoice]:
        """
        Get invoice by ID.

        Args:
            invoice_id: Invoice ID

        Returns:
            Invoice if found
        """
        query = (
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.id == invoice_id)
            .options(joinedload(SubscriptionInvoice.subscription))
        )
        
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_invoice_number(
        self,
        invoice_number: str,
    ) -> Optional[SubscriptionInvoice]:
        """
        Get invoice by invoice number.

        Args:
            invoice_number: Invoice number

        Returns:
            Invoice if found
        """
        query = (
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.invoice_number == invoice_number)
            .options(joinedload(SubscriptionInvoice.subscription))
        )
        
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_subscription(
        self,
        subscription_id: UUID,
        status: Optional[InvoiceStatus] = None,
    ) -> List[SubscriptionInvoice]:
        """
        Get all invoices for subscription.

        Args:
            subscription_id: Subscription ID
            status: Filter by invoice status

        Returns:
            List of invoices
        """
        query = (
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.subscription_id == subscription_id)
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.invoice_date.desc())
        )
        
        if status:
            query = query.where(SubscriptionInvoice.status == status)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_by_hostel(
        self,
        hostel_id: UUID,
        status: Optional[InvoiceStatus] = None,
        limit: Optional[int] = None,
    ) -> List[SubscriptionInvoice]:
        """
        Get invoices for hostel.

        Args:
            hostel_id: Hostel ID
            status: Filter by invoice status
            limit: Maximum number of results

        Returns:
            List of invoices
        """
        query = (
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.hostel_id == hostel_id)
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.invoice_date.desc())
        )
        
        if status:
            query = query.where(SubscriptionInvoice.status == status)
        
        if limit:
            query = query.limit(limit)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_by_status(
        self,
        status: InvoiceStatus,
        limit: Optional[int] = None,
    ) -> List[SubscriptionInvoice]:
        """
        Get invoices by status.

        Args:
            status: Invoice status
            limit: Maximum number of results

        Returns:
            List of invoices
        """
        query = (
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.status == status)
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.invoice_date.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_overdue_invoices(self) -> List[SubscriptionInvoice]:
        """
        Get all overdue invoices.

        Returns:
            List of overdue invoices
        """
        today = date.today()
        
        query = (
            select(SubscriptionInvoice)
            .where(
                and_(
                    SubscriptionInvoice.status.in_([
                        InvoiceStatus.PENDING,
                        InvoiceStatus.SENT,
                    ]),
                    SubscriptionInvoice.due_date < today,
                )
            )
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.due_date)
        )
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_due_soon(
        self,
        days: int = 7,
    ) -> List[SubscriptionInvoice]:
        """
        Get invoices due within specified days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of invoices due soon
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        query = (
            select(SubscriptionInvoice)
            .where(
                and_(
                    SubscriptionInvoice.status.in_([
                        InvoiceStatus.PENDING,
                        InvoiceStatus.SENT,
                    ]),
                    SubscriptionInvoice.due_date >= today,
                    SubscriptionInvoice.due_date <= end_date,
                )
            )
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.due_date)
        )
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_unpaid_invoices(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[SubscriptionInvoice]:
        """
        Get all unpaid invoices.

        Args:
            hostel_id: Optional hostel ID filter

        Returns:
            List of unpaid invoices
        """
        query = (
            select(SubscriptionInvoice)
            .where(
                SubscriptionInvoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.SENT,
                    InvoiceStatus.OVERDUE,
                ])
            )
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.due_date)
        )
        
        if hostel_id:
            query = query.where(SubscriptionInvoice.hostel_id == hostel_id)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_paid_invoices(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SubscriptionInvoice]:
        """
        Get paid invoices.

        Args:
            hostel_id: Optional hostel ID filter
            start_date: Filter by payment date start
            end_date: Filter by payment date end

        Returns:
            List of paid invoices
        """
        query = (
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.status == InvoiceStatus.PAID)
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.payment_date.desc())
        )
        
        if hostel_id:
            query = query.where(SubscriptionInvoice.hostel_id == hostel_id)
        
        if start_date:
            query = query.where(SubscriptionInvoice.payment_date >= start_date)
        
        if end_date:
            query = query.where(SubscriptionInvoice.payment_date <= end_date)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_partially_paid_invoices(self) -> List[SubscriptionInvoice]:
        """
        Get invoices that are partially paid.

        Returns:
            List of partially paid invoices
        """
        query = (
            select(SubscriptionInvoice)
            .where(
                and_(
                    SubscriptionInvoice.amount_paid > Decimal("0.00"),
                    SubscriptionInvoice.amount_due > Decimal("0.00"),
                    SubscriptionInvoice.status != InvoiceStatus.PAID,
                )
            )
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.invoice_date.desc())
        )
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_draft_invoices(self) -> List[SubscriptionInvoice]:
        """
        Get all draft invoices.

        Returns:
            List of draft invoices
        """
        query = (
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.status == InvoiceStatus.DRAFT)
            .options(joinedload(SubscriptionInvoice.subscription))
            .order_by(SubscriptionInvoice.created_at.desc())
        )
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    # ==================== UPDATE OPERATIONS ====================

    def update_invoice(
        self,
        invoice_id: UUID,
        update_data: Dict[str, Any],
    ) -> Optional[SubscriptionInvoice]:
        """
        Update invoice details.

        Args:
            invoice_id: Invoice ID
            update_data: Updated data

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        for key, value in update_data.items():
            if hasattr(invoice, key):
                setattr(invoice, key, value)
        
        invoice.updated_at = datetime.utcnow()
        self.db.flush()
        return invoice

    def update_status(
        self,
        invoice_id: UUID,
        status: InvoiceStatus,
    ) -> Optional[SubscriptionInvoice]:
        """
        Update invoice status.

        Args:
            invoice_id: Invoice ID
            status: New status

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        invoice.status = status
        invoice.updated_at = datetime.utcnow()
        
        self.db.flush()
        return invoice

    def mark_as_sent(
        self,
        invoice_id: UUID,
    ) -> Optional[SubscriptionInvoice]:
        """
        Mark invoice as sent.

        Args:
            invoice_id: Invoice ID

        Returns:
            Updated invoice
        """
        return self.update_status(invoice_id, InvoiceStatus.SENT)

    def mark_as_paid(
        self,
        invoice_id: UUID,
        payment_date: Optional[date] = None,
        payment_reference: Optional[str] = None,
        payment_method: Optional[str] = None,
    ) -> Optional[SubscriptionInvoice]:
        """
        Mark invoice as paid.

        Args:
            invoice_id: Invoice ID
            payment_date: Payment date
            payment_reference: Payment reference
            payment_method: Payment method

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        invoice.status = InvoiceStatus.PAID
        invoice.payment_date = payment_date or date.today()
        invoice.payment_reference = payment_reference
        invoice.payment_method = payment_method
        invoice.amount_paid = invoice.amount
        invoice.amount_due = Decimal("0.00")
        invoice.updated_at = datetime.utcnow()
        
        self.db.flush()
        return invoice

    def record_partial_payment(
        self,
        invoice_id: UUID,
        payment_amount: Decimal,
        payment_date: Optional[date] = None,
        payment_reference: Optional[str] = None,
        payment_method: Optional[str] = None,
    ) -> Optional[SubscriptionInvoice]:
        """
        Record partial payment for invoice.

        Args:
            invoice_id: Invoice ID
            payment_amount: Payment amount
            payment_date: Payment date
            payment_reference: Payment reference
            payment_method: Payment method

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        invoice.amount_paid += payment_amount
        invoice.amount_due = invoice.amount - invoice.amount_paid
        
        if invoice.amount_due <= Decimal("0.00"):
            invoice.status = InvoiceStatus.PAID
            invoice.amount_due = Decimal("0.00")
        else:
            invoice.status = InvoiceStatus.PENDING
        
        invoice.payment_date = payment_date or date.today()
        invoice.payment_reference = payment_reference
        invoice.payment_method = payment_method
        invoice.updated_at = datetime.utcnow()
        
        self.db.flush()
        return invoice

    def mark_as_overdue(
        self,
        invoice_id: UUID,
    ) -> Optional[SubscriptionInvoice]:
        """
        Mark invoice as overdue.

        Args:
            invoice_id: Invoice ID

        Returns:
            Updated invoice
        """
        return self.update_status(invoice_id, InvoiceStatus.OVERDUE)

    def cancel_invoice(
        self,
        invoice_id: UUID,
        reason: Optional[str] = None,
    ) -> Optional[SubscriptionInvoice]:
        """
        Cancel invoice.

        Args:
            invoice_id: Invoice ID
            reason: Cancellation reason

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        invoice.status = InvoiceStatus.CANCELLED
        if reason:
            invoice.notes = f"{invoice.notes or ''}\nCancellation reason: {reason}".strip()
        invoice.updated_at = datetime.utcnow()
        
        self.db.flush()
        return invoice

    def void_invoice(
        self,
        invoice_id: UUID,
        reason: Optional[str] = None,
    ) -> Optional[SubscriptionInvoice]:
        """
        Void invoice.

        Args:
            invoice_id: Invoice ID
            reason: Void reason

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        invoice.status = InvoiceStatus.VOID
        if reason:
            invoice.notes = f"{invoice.notes or ''}\nVoid reason: {reason}".strip()
        invoice.updated_at = datetime.utcnow()
        
        self.db.flush()
        return invoice

    def apply_discount(
        self,
        invoice_id: UUID,
        discount_amount: Decimal,
        discount_reason: Optional[str] = None,
    ) -> Optional[SubscriptionInvoice]:
        """
        Apply discount to invoice.

        Args:
            invoice_id: Invoice ID
            discount_amount: Discount amount
            discount_reason: Reason for discount

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        invoice.discount_amount = discount_amount
        invoice.discount_reason = discount_reason
        
        # Recalculate amounts
        invoice.amount = invoice.subtotal - invoice.discount_amount + invoice.tax_amount
        invoice.amount_due = invoice.amount - invoice.amount_paid
        invoice.updated_at = datetime.utcnow()
        
        self.db.flush()
        return invoice

    def update_urls(
        self,
        invoice_id: UUID,
        invoice_url: Optional[str] = None,
        payment_url: Optional[str] = None,
    ) -> Optional[SubscriptionInvoice]:
        """
        Update invoice and payment URLs.

        Args:
            invoice_id: Invoice ID
            invoice_url: Invoice view/download URL
            payment_url: Payment URL

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        if invoice_url is not None:
            invoice.invoice_url = invoice_url
        if payment_url is not None:
            invoice.payment_url = payment_url
        
        invoice.updated_at = datetime.utcnow()
        self.db.flush()
        return invoice

    def extend_due_date(
        self,
        invoice_id: UUID,
        new_due_date: date,
        reason: Optional[str] = None,
    ) -> Optional[SubscriptionInvoice]:
        """
        Extend invoice due date.

        Args:
            invoice_id: Invoice ID
            new_due_date: New due date
            reason: Reason for extension

        Returns:
            Updated invoice
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        old_due_date = invoice.due_date
        invoice.due_date = new_due_date
        
        if reason:
            note = f"Due date extended from {old_due_date} to {new_due_date}. Reason: {reason}"
            invoice.notes = f"{invoice.notes or ''}\n{note}".strip()
        
        invoice.updated_at = datetime.utcnow()
        self.db.flush()
        return invoice

    # ==================== DELETE OPERATIONS ====================

    def delete_invoice(
        self,
        invoice_id: UUID,
    ) -> bool:
        """
        Delete invoice (hard delete).

        Args:
            invoice_id: Invoice ID

        Returns:
            True if deleted
        """
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return False
        
        # Only allow deletion of draft invoices
        if invoice.status != InvoiceStatus.DRAFT:
            return False
        
        self.db.delete(invoice)
        self.db.flush()
        return True

    # ==================== ANALYTICS & REPORTING ====================

    def get_invoice_statistics(self) -> Dict[str, Any]:
        """
        Get overall invoice statistics.

        Returns:
            Dictionary with invoice statistics
        """
        total_invoices = self.db.query(func.count(SubscriptionInvoice.id)).scalar()
        
        paid_invoices = (
            self.db.query(func.count(SubscriptionInvoice.id))
            .filter(SubscriptionInvoice.status == InvoiceStatus.PAID)
            .scalar()
        )
        
        overdue_invoices = (
            self.db.query(func.count(SubscriptionInvoice.id))
            .filter(SubscriptionInvoice.status == InvoiceStatus.OVERDUE)
            .scalar()
        )
        
        pending_invoices = (
            self.db.query(func.count(SubscriptionInvoice.id))
            .filter(
                SubscriptionInvoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.SENT,
                ])
            )
            .scalar()
        )
        
        total_billed = (
            self.db.query(func.sum(SubscriptionInvoice.amount))
            .scalar() or Decimal("0.00")
        )
        
        total_paid = (
            self.db.query(func.sum(SubscriptionInvoice.amount_paid))
            .scalar() or Decimal("0.00")
        )
        
        total_outstanding = (
            self.db.query(func.sum(SubscriptionInvoice.amount_due))
            .filter(
                SubscriptionInvoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.SENT,
                    InvoiceStatus.OVERDUE,
                ])
            )
            .scalar() or Decimal("0.00")
        )
        
        return {
            "total_invoices": total_invoices,
            "paid_invoices": paid_invoices,
            "overdue_invoices": overdue_invoices,
            "pending_invoices": pending_invoices,
            "total_billed": float(total_billed),
            "total_paid": float(total_paid),
            "total_outstanding": float(total_outstanding),
            "collection_rate": (
                float(total_paid / total_billed * 100) if total_billed > 0 else 0
            ),
        }

    def get_revenue_by_period(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get revenue statistics for period.

        Args:
            start_date: Period start date
            end_date: Period end date

        Returns:
            Revenue statistics
        """
        invoices_query = select(SubscriptionInvoice).where(
            and_(
                SubscriptionInvoice.payment_date >= start_date,
                SubscriptionInvoice.payment_date <= end_date,
                SubscriptionInvoice.status == InvoiceStatus.PAID,
            )
        )
        
        result = self.db.execute(invoices_query)
        invoices = list(result.scalars().all())
        
        total_revenue = sum(inv.amount for inv in invoices)
        invoice_count = len(invoices)
        average_invoice = total_revenue / invoice_count if invoice_count > 0 else Decimal("0.00")
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_revenue": float(total_revenue),
            "invoice_count": invoice_count,
            "average_invoice_amount": float(average_invoice),
        }

    def get_outstanding_by_hostel(
        self,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get outstanding invoice summary for hostel.

        Args:
            hostel_id: Hostel ID

        Returns:
            Outstanding summary
        """
        unpaid = self.get_unpaid_invoices(hostel_id)
        
        total_outstanding = sum(inv.amount_due for inv in unpaid)
        overdue_amount = sum(
            inv.amount_due for inv in unpaid if inv.is_overdue
        )
        
        oldest_unpaid = min(
            (inv.invoice_date for inv in unpaid),
            default=None
        )
        
        return {
            "hostel_id": str(hostel_id),
            "total_outstanding": float(total_outstanding),
            "overdue_amount": float(overdue_amount),
            "unpaid_invoice_count": len(unpaid),
            "overdue_invoice_count": sum(1 for inv in unpaid if inv.is_overdue),
            "oldest_unpaid_date": str(oldest_unpaid) if oldest_unpaid else None,
        }

    def get_payment_collection_metrics(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get payment collection metrics.

        Args:
            days: Number of days to analyze

        Returns:
            Collection metrics
        """
        start_date = date.today() - timedelta(days=days)
        
        # Invoices issued in period
        issued_query = select(SubscriptionInvoice).where(
            and_(
                SubscriptionInvoice.invoice_date >= start_date,
                SubscriptionInvoice.status != InvoiceStatus.DRAFT,
            )
        )
        result = self.db.execute(issued_query)
        issued_invoices = list(result.scalars().all())
        
        # Paid invoices in period
        paid_invoices = [inv for inv in issued_invoices if inv.status == InvoiceStatus.PAID]
        
        # Calculate metrics
        total_issued = len(issued_invoices)
        total_paid = len(paid_invoices)
        
        total_issued_amount = sum(inv.amount for inv in issued_invoices)
        total_collected = sum(inv.amount_paid for inv in issued_invoices)
        
        # Average days to payment
        days_to_payment = []
        for inv in paid_invoices:
            if inv.payment_date and inv.invoice_date:
                days = (inv.payment_date - inv.invoice_date).days
                days_to_payment.append(days)
        
        avg_days_to_payment = (
            sum(days_to_payment) / len(days_to_payment)
            if days_to_payment else 0
        )
        
        return {
            "period_days": days,
            "total_invoices_issued": total_issued,
            "total_invoices_paid": total_paid,
            "collection_rate": (total_paid / total_issued * 100) if total_issued > 0 else 0,
            "total_issued_amount": float(total_issued_amount),
            "total_collected": float(total_collected),
            "collection_efficiency": (
                float(total_collected / total_issued_amount * 100)
                if total_issued_amount > 0 else 0
            ),
            "average_days_to_payment": avg_days_to_payment,
        }

    # ==================== BATCH OPERATIONS ====================

    def batch_mark_overdue(self) -> int:
        """
        Batch mark overdue invoices.

        Returns:
            Number of invoices marked as overdue
        """
        overdue = self.get_overdue_invoices()
        count = 0
        
        for invoice in overdue:
            if invoice.status in [InvoiceStatus.PENDING, InvoiceStatus.SENT]:
                invoice.status = InvoiceStatus.OVERDUE
                invoice.updated_at = datetime.utcnow()
                count += 1
        
        self.db.flush()
        return count

    def batch_send_invoices(
        self,
        invoice_ids: List[UUID],
    ) -> int:
        """
        Batch mark invoices as sent.

        Args:
            invoice_ids: List of invoice IDs

        Returns:
            Number of invoices marked as sent
        """
        count = 0
        for invoice_id in invoice_ids:
            if self.mark_as_sent(invoice_id):
                count += 1
        return count

    # ==================== SEARCH & FILTERING ====================

    def search_invoices(
        self,
        search_term: Optional[str] = None,
        status: Optional[InvoiceStatus] = None,
        subscription_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        invoice_date_from: Optional[date] = None,
        invoice_date_to: Optional[date] = None,
        due_date_from: Optional[date] = None,
        due_date_to: Optional[date] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[SubscriptionInvoice]:
        """
        Search invoices with multiple filters.

        Args:
            search_term: Search in invoice number
            status: Filter by status
            subscription_id: Filter by subscription
            hostel_id: Filter by hostel
            invoice_date_from: Invoice date range start
            invoice_date_to: Invoice date range end
            due_date_from: Due date range start
            due_date_to: Due date range end
            min_amount: Minimum amount
            max_amount: Maximum amount
            limit: Maximum results
            offset: Results offset

        Returns:
            List of matching invoices
        """
        query = select(SubscriptionInvoice).options(
            joinedload(SubscriptionInvoice.subscription)
        )
        
        conditions = []
        
        if search_term:
            search_pattern = f"%{search_term}%"
            conditions.append(
                SubscriptionInvoice.invoice_number.ilike(search_pattern)
            )
        
        if status:
            conditions.append(SubscriptionInvoice.status == status)
        
        if subscription_id:
            conditions.append(SubscriptionInvoice.subscription_id == subscription_id)
        
        if hostel_id:
            conditions.append(SubscriptionInvoice.hostel_id == hostel_id)
        
        if invoice_date_from:
            conditions.append(SubscriptionInvoice.invoice_date >= invoice_date_from)
        
        if invoice_date_to:
            conditions.append(SubscriptionInvoice.invoice_date <= invoice_date_to)
        
        if due_date_from:
            conditions.append(SubscriptionInvoice.due_date >= due_date_from)
        
        if due_date_to:
            conditions.append(SubscriptionInvoice.due_date <= due_date_to)
        
        if min_amount is not None:
            conditions.append(SubscriptionInvoice.amount >= min_amount)
        
        if max_amount is not None:
            conditions.append(SubscriptionInvoice.amount <= max_amount)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(SubscriptionInvoice.invoice_date.desc())
        
        if limit:
            query = query.limit(limit)
        
        if offset:
            query = query.offset(offset)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def count_invoices(
        self,
        status: Optional[InvoiceStatus] = None,
        hostel_id: Optional[UUID] = None,
    ) -> int:
        """
        Count invoices with filters.

        Args:
            status: Filter by status
            hostel_id: Filter by hostel

        Returns:
            Count of matching invoices
        """
        query = select(func.count(SubscriptionInvoice.id))
        
        conditions = []
        
        if status:
            conditions.append(SubscriptionInvoice.status == status)
        
        if hostel_id:
            conditions.append(SubscriptionInvoice.hostel_id == hostel_id)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        return self.db.execute(query).scalar()