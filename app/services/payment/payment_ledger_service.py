"""
Payment Ledger Service.

Double-entry bookkeeping service for maintaining financial records
with automated posting, balance calculations, and reconciliation.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LedgerError, LedgerValidationError
from app.models.payment.payment import Payment
from app.models.payment.payment_ledger import (
    LedgerEntryType,
    PaymentLedger,
    TransactionType,
)
from app.repositories.payment.payment_ledger_repository import (
    PaymentLedgerRepository,
)


class PaymentLedgerService:
    """
    Service for payment ledger operations.
    
    Implements double-entry bookkeeping principles:
    - Every transaction has equal debits and credits
    - Maintains running balances
    - Supports reversal and adjustments
    - Provides audit trail
    """

    def __init__(
        self,
        session: AsyncSession,
        ledger_repo: PaymentLedgerRepository,
    ):
        """Initialize ledger service."""
        self.session = session
        self.ledger_repo = ledger_repo

    # ==================== Posting Operations ====================

    async def post_payment_created(
        self,
        payment: Payment,
        posted_by: UUID,
    ) -> PaymentLedger:
        """
        Post ledger entry when payment is created.
        
        Creates a DEBIT entry (amount owed by student).
        
        Args:
            payment: Payment record
            posted_by: User posting the entry
            
        Returns:
            Created ledger entry
        """
        try:
            # Create debit entry (negative amount - student owes money)
            entry = await self.ledger_repo.create_ledger_entry(
                student_id=payment.student_id,
                hostel_id=payment.hostel_id,
                posted_by=posted_by,
                entry_type=LedgerEntryType.DEBIT,
                transaction_type=self._map_payment_type_to_transaction_type(
                    payment.payment_type
                ),
                amount=-abs(payment.amount),  # Debit (negative)
                description=f"Payment created: {payment.payment_reference} - {payment.payment_type.value}",
                payment_id=payment.id,
                payment_reference=payment.payment_reference,
                transaction_date=payment.created_at.date(),
            )
            
            return entry
            
        except Exception as e:
            raise LedgerError(f"Failed to post payment created: {str(e)}")

    async def post_payment_completed(
        self,
        payment: Payment,
        posted_by: UUID,
    ) -> PaymentLedger:
        """
        Post ledger entry when payment is completed.
        
        Creates a CREDIT entry (payment received).
        
        Args:
            payment: Payment record
            posted_by: User posting the entry
            
        Returns:
            Created ledger entry
        """
        try:
            # Create credit entry (positive amount - payment received)
            entry = await self.ledger_repo.create_ledger_entry(
                student_id=payment.student_id,
                hostel_id=payment.hostel_id,
                posted_by=posted_by,
                entry_type=LedgerEntryType.CREDIT,
                transaction_type=TransactionType.PAYMENT,
                amount=abs(payment.amount),  # Credit (positive)
                description=f"Payment completed: {payment.payment_reference} via {payment.payment_method.value}",
                payment_id=payment.id,
                payment_reference=payment.payment_reference,
                transaction_date=payment.paid_at.date() if payment.paid_at else date.today(),
            )
            
            return entry
            
        except Exception as e:
            raise LedgerError(f"Failed to post payment completed: {str(e)}")

    async def post_refund(
        self,
        payment: Payment,
        refund_amount: Decimal,
        posted_by: UUID,
        refund_reference: str,
        notes: Optional[str] = None,
    ) -> PaymentLedger:
        """
        Post ledger entry for refund.
        
        Creates a DEBIT entry (refund given to student).
        
        Args:
            payment: Original payment
            refund_amount: Amount being refunded
            posted_by: User posting the entry
            refund_reference: Refund reference number
            notes: Additional notes
            
        Returns:
            Created ledger entry
        """
        try:
            # Validate refund amount
            if refund_amount > payment.amount:
                raise LedgerValidationError(
                    f"Refund amount {refund_amount} exceeds payment amount {payment.amount}"
                )
            
            # Create debit entry (negative - money going out)
            entry = await self.ledger_repo.create_ledger_entry(
                student_id=payment.student_id,
                hostel_id=payment.hostel_id,
                posted_by=posted_by,
                entry_type=LedgerEntryType.DEBIT,
                transaction_type=TransactionType.REFUND,
                amount=-abs(refund_amount),  # Debit (negative)
                description=f"Refund: {refund_reference} for payment {payment.payment_reference}",
                payment_id=payment.id,
                payment_reference=payment.payment_reference,
                notes=notes,
            )
            
            return entry
            
        except LedgerValidationError:
            raise
        except Exception as e:
            raise LedgerError(f"Failed to post refund: {str(e)}")

    async def post_adjustment(
        self,
        student_id: UUID,
        hostel_id: UUID,
        amount: Decimal,
        reason: str,
        posted_by: UUID,
        is_credit: bool = True,
        payment_id: Optional[UUID] = None,
    ) -> PaymentLedger:
        """
        Post manual adjustment to ledger.
        
        Used for corrections, waivers, late fees, etc.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            amount: Adjustment amount
            reason: Reason for adjustment
            posted_by: User posting the entry
            is_credit: True for credit adjustment, False for debit
            payment_id: Related payment (if any)
            
        Returns:
            Created ledger entry
        """
        try:
            entry_type = LedgerEntryType.CREDIT if is_credit else LedgerEntryType.DEBIT
            entry_amount = abs(amount) if is_credit else -abs(amount)
            
            entry = await self.ledger_repo.create_ledger_entry(
                student_id=student_id,
                hostel_id=hostel_id,
                posted_by=posted_by,
                entry_type=entry_type,
                transaction_type=TransactionType.ADJUSTMENT,
                amount=entry_amount,
                description=f"Manual adjustment: {reason}",
                payment_id=payment_id,
            )
            
            return entry
            
        except Exception as e:
            raise LedgerError(f"Failed to post adjustment: {str(e)}")

    async def post_late_fee(
        self,
        student_id: UUID,
        hostel_id: UUID,
        late_fee_amount: Decimal,
        payment_id: UUID,
        posted_by: UUID,
    ) -> PaymentLedger:
        """
        Post late fee charge.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            late_fee_amount: Late fee amount
            payment_id: Related payment
            posted_by: User posting the entry
            
        Returns:
            Created ledger entry
        """
        try:
            entry = await self.ledger_repo.create_ledger_entry(
                student_id=student_id,
                hostel_id=hostel_id,
                posted_by=posted_by,
                entry_type=LedgerEntryType.DEBIT,
                transaction_type=TransactionType.LATE_FEE,
                amount=-abs(late_fee_amount),  # Debit (student owes)
                description=f"Late fee charged for overdue payment",
                payment_id=payment_id,
            )
            
            return entry
            
        except Exception as e:
            raise LedgerError(f"Failed to post late fee: {str(e)}")

    async def post_waiver(
        self,
        student_id: UUID,
        hostel_id: UUID,
        waiver_amount: Decimal,
        reason: str,
        posted_by: UUID,
        approved_by: UUID,
    ) -> PaymentLedger:
        """
        Post fee waiver.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            waiver_amount: Amount waived
            reason: Waiver reason
            posted_by: User posting the entry
            approved_by: User who approved waiver
            
        Returns:
            Created ledger entry
        """
        try:
            entry = await self.ledger_repo.create_ledger_entry(
                student_id=student_id,
                hostel_id=hostel_id,
                posted_by=posted_by,
                entry_type=LedgerEntryType.CREDIT,
                transaction_type=TransactionType.WAIVER,
                amount=abs(waiver_amount),  # Credit (reduces what student owes)
                description=f"Fee waiver: {reason}",
                notes=f"Approved by: {approved_by}",
                metadata={"approved_by": str(approved_by)},
            )
            
            return entry
            
        except Exception as e:
            raise LedgerError(f"Failed to post waiver: {str(e)}")

    async def post_discount(
        self,
        student_id: UUID,
        hostel_id: UUID,
        discount_amount: Decimal,
        discount_type: str,
        posted_by: UUID,
    ) -> PaymentLedger:
        """
        Post discount.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            discount_amount: Discount amount
            discount_type: Type of discount
            posted_by: User posting the entry
            
        Returns:
            Created ledger entry
        """
        try:
            entry = await self.ledger_repo.create_ledger_entry(
                student_id=student_id,
                hostel_id=hostel_id,
                posted_by=posted_by,
                entry_type=LedgerEntryType.CREDIT,
                transaction_type=TransactionType.DISCOUNT,
                amount=abs(discount_amount),  # Credit
                description=f"Discount applied: {discount_type}",
            )
            
            return entry
            
        except Exception as e:
            raise LedgerError(f"Failed to post discount: {str(e)}")

    # ==================== Reversal Operations ====================

    async def reverse_entry(
        self,
        entry_id: UUID,
        posted_by: UUID,
        reversal_reason: str,
    ) -> tuple[PaymentLedger, PaymentLedger]:
        """
        Reverse a ledger entry.
        
        Creates opposite entry to cancel out the original.
        
        Args:
            entry_id: Entry to reverse
            posted_by: User performing reversal
            reversal_reason: Reason for reversal
            
        Returns:
            Tuple of (original_entry, reversal_entry)
        """
        try:
            original_entry, reversal_entry = await self.ledger_repo.reverse_entry(
                entry_id=entry_id,
                posted_by=posted_by,
                reversal_reason=reversal_reason,
            )
            
            return original_entry, reversal_entry
            
        except Exception as e:
            raise LedgerError(f"Failed to reverse entry: {str(e)}")

    # ==================== Balance Operations ====================

    async def get_student_balance(
        self,
        student_id: UUID,
        hostel_id: UUID,
    ) -> dict[str, Any]:
        """
        Get current balance for a student.
        
        Returns:
            {
                "student_id": "...",
                "balance": 5000.00,
                "balance_type": "credit" or "debit",
                "last_updated": "2024-01-15T10:30:00",
            }
        """
        balance = await self.ledger_repo.get_student_balance(
            student_id=student_id,
            hostel_id=hostel_id,
        )
        
        balance_type = "credit" if balance >= 0 else "debit"
        
        return {
            "student_id": str(student_id),
            "hostel_id": str(hostel_id),
            "balance": float(abs(balance)),
            "balance_type": balance_type,
            "is_in_arrears": balance < 0,
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def get_student_ledger(
        self,
        student_id: UUID,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_reversed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentLedger]:
        """
        Get ledger entries for a student.
        
        Returns chronological list of all ledger entries.
        """
        return await self.ledger_repo.get_student_ledger(
            student_id=student_id,
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            include_reversed=include_reversed,
            limit=limit,
            offset=offset,
        )

    async def get_hostel_ledger(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_type: Optional[TransactionType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentLedger]:
        """Get ledger entries for a hostel."""
        return await self.ledger_repo.get_hostel_ledger(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=transaction_type,
            limit=limit,
            offset=offset,
        )

    # ==================== Reporting ====================

    async def get_financial_summary(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """
        Get financial summary for a period.
        
        Returns total debits, credits, and net balance.
        """
        return await self.ledger_repo.calculate_financial_summary(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_transaction_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get breakdown by transaction type."""
        return await self.ledger_repo.get_transaction_breakdown(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_student_balances(
        self,
        hostel_id: UUID,
        min_balance: Optional[Decimal] = None,
        max_balance: Optional[Decimal] = None,
    ) -> list[dict[str, Any]]:
        """Get balances for all students in hostel."""
        return await self.ledger_repo.get_student_balances(
            hostel_id=hostel_id,
            min_balance=min_balance,
            max_balance=max_balance,
        )

    # ==================== Reconciliation ====================

    async def reconcile_ledger(
        self,
        hostel_id: UUID,
        reconciled_by: UUID,
        reconciliation_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Reconcile ledger for a hostel.
        
        Marks all entries up to date as reconciled.
        """
        return await self.ledger_repo.perform_ledger_reconciliation(
            hostel_id=hostel_id,
            reconciled_by=reconciled_by,
            reconciliation_date=reconciliation_date,
        )

    async def detect_discrepancies(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """
        Detect ledger discrepancies.
        
        Finds balance calculation errors, missing entries, etc.
        """
        return await self.ledger_repo.detect_reconciliation_discrepancies(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    # ==================== Helper Methods ====================

    def _map_payment_type_to_transaction_type(
        self,
        payment_type,
    ) -> TransactionType:
        """Map payment type to transaction type."""
        # This is a simple mapping - adjust based on your enums
        mapping = {
            "monthly_rent": TransactionType.PAYMENT,
            "mess_fee": TransactionType.FEE_CHARGE,
            "security_deposit": TransactionType.PAYMENT,
            "maintenance": TransactionType.FE_CHARGE,
        }
        
        return mapping.get(
            payment_type.value if hasattr(payment_type, 'value') else payment_type,
            TransactionType.PAYMENT
        )