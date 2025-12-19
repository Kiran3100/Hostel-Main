# --- File: payment_ledger_repository.py ---
"""
Payment Ledger Repository.

Double-entry bookkeeping with automated reconciliation, 
financial reporting, and audit compliance.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment.payment_ledger import (
    LedgerEntryType,
    PaymentLedger,
    TransactionType,
)
from app.repositories.base.base_repository import BaseRepository


class PaymentLedgerRepository(BaseRepository[PaymentLedger]):
    """Repository for payment ledger operations."""

    def __init__(self, session: AsyncSession):
        """Initialize payment ledger repository."""
        super().__init__(PaymentLedger, session)

    # ==================== Core Ledger Operations ====================

    async def create_ledger_entry(
        self,
        student_id: UUID,
        hostel_id: UUID,
        posted_by: UUID,
        entry_type: LedgerEntryType,
        transaction_type: TransactionType,
        amount: Decimal,
        description: str,
        transaction_date: date | None = None,
        payment_id: UUID | None = None,
        payment_reference: str | None = None,
        metadata: dict | None = None,
    ) -> PaymentLedger:
        """
        Create a new ledger entry.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            posted_by: User who posted the entry
            entry_type: Type of ledger entry
            transaction_type: Type of transaction
            amount: Transaction amount (positive for credit, negative for debit)
            description: Entry description
            transaction_date: Date of transaction
            payment_id: Optional payment ID
            payment_reference: Optional payment reference
            metadata: Additional metadata
            
        Returns:
            Created ledger entry
        """
        # Get current balance
        current_balance = await self.get_student_balance(student_id, hostel_id)
        
        # Calculate new balance
        new_balance = current_balance + amount
        
        # Generate entry reference
        entry_reference = await self._generate_entry_reference(hostel_id)
        
        entry_data = {
            "student_id": student_id,
            "hostel_id": hostel_id,
            "posted_by": posted_by,
            "payment_id": payment_id,
            "entry_reference": entry_reference,
            "entry_type": entry_type,
            "transaction_type": transaction_type,
            "amount": amount,
            "balance_before": current_balance,
            "balance_after": new_balance,
            "transaction_date": transaction_date or date.today(),
            "posted_at": datetime.utcnow(),
            "payment_reference": payment_reference,
            "description": description,
            "metadata": metadata or {},
        }
        
        return await self.create(entry_data)

    async def create_double_entry(
        self,
        student_id: UUID,
        hostel_id: UUID,
        posted_by: UUID,
        transaction_type: TransactionType,
        amount: Decimal,
        description: str,
        payment_id: UUID | None = None,
        payment_reference: str | None = None,
        metadata: dict | None = None,
    ) -> tuple[PaymentLedger, PaymentLedger]:
        """
        Create double-entry ledger entries (debit and credit).
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            posted_by: User who posted
            transaction_type: Type of transaction
            amount: Transaction amount (positive)
            description: Entry description
            payment_id: Optional payment ID
            payment_reference: Optional payment reference
            metadata: Additional metadata
            
        Returns:
            Tuple of (debit_entry, credit_entry)
        """
        # Create debit entry (negative amount)
        debit_entry = await self.create_ledger_entry(
            student_id=student_id,
            hostel_id=hostel_id,
            posted_by=posted_by,
            entry_type=LedgerEntryType.DEBIT,
            transaction_type=transaction_type,
            amount=-abs(amount),
            description=f"Debit: {description}",
            payment_id=payment_id,
            payment_reference=payment_reference,
            metadata=metadata,
        )
        
        # Create credit entry (positive amount)
        credit_entry = await self.create_ledger_entry(
            student_id=student_id,
            hostel_id=hostel_id,
            posted_by=posted_by,
            entry_type=LedgerEntryType.CREDIT,
            transaction_type=transaction_type,
            amount=abs(amount),
            description=f"Credit: {description}",
            payment_id=payment_id,
            payment_reference=payment_reference,
            metadata=metadata,
        )
        
        return debit_entry, credit_entry

    async def reverse_entry(
        self,
        entry_id: UUID,
        posted_by: UUID,
        reversal_reason: str,
    ) -> tuple[PaymentLedger, PaymentLedger]:
        """
        Reverse a ledger entry.
        
        Args:
            entry_id: Entry ID to reverse
            posted_by: User posting the reversal
            reversal_reason: Reason for reversal
            
        Returns:
            Tuple of (original_entry, reversal_entry)
        """
        # Get original entry
        original_entry = await self.get_by_id(entry_id)
        if not original_entry:
            raise ValueError(f"Ledger entry not found: {entry_id}")
        
        if original_entry.is_reversed:
            raise ValueError(f"Entry already reversed: {entry_id}")
        
        # Create reversal entry with opposite amount
        reversal_entry = await self.create_ledger_entry(
            student_id=original_entry.student_id,
            hostel_id=original_entry.hostel_id,
            posted_by=posted_by,
            entry_type=LedgerEntryType.REVERSAL,
            transaction_type=original_entry.transaction_type,
            amount=-original_entry.amount,
            description=f"Reversal of {original_entry.entry_reference}: {reversal_reason}",
            metadata={"original_entry_id": str(entry_id), "reversal_reason": reversal_reason},
        )
        
        # Mark original entry as reversed
        await self.update(entry_id, {
            "is_reversed": True,
            "reversed_at": datetime.utcnow(),
            "reversal_entry_id": reversal_entry.id,
            "reversal_reason": reversal_reason,
        })
        
        # Refresh original entry
        original_entry = await self.get_by_id(entry_id)
        
        return original_entry, reversal_entry

    async def mark_reconciled(
        self,
        entry_id: UUID,
        reconciled_by: UUID,
    ) -> PaymentLedger:
        """
        Mark ledger entry as reconciled.
        
        Args:
            entry_id: Entry ID
            reconciled_by: User who reconciled
            
        Returns:
            Updated entry
        """
        update_data = {
            "is_reconciled": True,
            "reconciled_at": datetime.utcnow(),
            "reconciled_by": reconciled_by,
        }
        
        return await self.update(entry_id, update_data)

    # ==================== Query Methods ====================

    async def get_student_balance(
        self,
        student_id: UUID,
        hostel_id: UUID,
    ) -> Decimal:
        """
        Get current balance for a student.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            
        Returns:
            Current balance
        """
        query = select(func.coalesce(func.sum(PaymentLedger.amount), 0)).where(
            PaymentLedger.student_id == student_id,
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        balance = result.scalar()
        
        return Decimal(str(balance)) if balance is not None else Decimal("0")

    async def get_student_ledger(
        self,
        student_id: UUID,
        hostel_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        include_reversed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentLedger]:
        """
        Get ledger entries for a student.
        
        Args:
            student_id: Student ID
            hostel_id: Optional hostel ID filter
            start_date: Start date filter
            end_date: End date filter
            include_reversed: Include reversed entries
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of ledger entries
        """
        query = select(PaymentLedger).where(
            PaymentLedger.student_id == student_id,
            PaymentLedger.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(PaymentLedger.hostel_id == hostel_id)
        
        if not include_reversed:
            query = query.where(PaymentLedger.is_reversed == False)
        
        if start_date:
            query = query.where(PaymentLedger.transaction_date >= start_date)
        
        if end_date:
            query = query.where(PaymentLedger.transaction_date <= end_date)
        
        query = query.order_by(
            PaymentLedger.transaction_date.desc(),
            PaymentLedger.posted_at.desc()
        ).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_hostel_ledger(
        self,
        hostel_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        transaction_type: TransactionType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentLedger]:
        """
        Get ledger entries for a hostel.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date filter
            end_date: End date filter
            transaction_type: Transaction type filter
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of ledger entries
        """
        query = select(PaymentLedger).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        )
        
        if start_date:
            query = query.where(PaymentLedger.transaction_date >= start_date)
        
        if end_date:
            query = query.where(PaymentLedger.transaction_date <= end_date)
        
        if transaction_type:
            query = query.where(PaymentLedger.transaction_type == transaction_type)
        
        query = query.order_by(
            PaymentLedger.transaction_date.desc(),
            PaymentLedger.posted_at.desc()
        ).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_payment(
        self,
        payment_id: UUID,
    ) -> list[PaymentLedger]:
        """
        Find ledger entries for a payment.
        
        Args:
            payment_id: Payment ID
            
        Returns:
            List of ledger entries
        """
        query = select(PaymentLedger).where(
            PaymentLedger.payment_id == payment_id,
            PaymentLedger.deleted_at.is_(None),
        ).order_by(PaymentLedger.posted_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_unreconciled_entries(
        self,
        hostel_id: UUID | None = None,
        older_than_days: int = 7,
    ) -> list[PaymentLedger]:
        """
        Find unreconciled ledger entries.
        
        Args:
            hostel_id: Optional hostel ID filter
            older_than_days: Entries older than specified days
            
        Returns:
            List of unreconciled entries
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        
        query = select(PaymentLedger).where(
            PaymentLedger.is_reconciled == False,
            PaymentLedger.is_reversed == False,
            PaymentLedger.posted_at < cutoff_date,
            PaymentLedger.deleted_at.is_(None),
        )
        
        if hostel_id:
            query = query.where(PaymentLedger.hostel_id == hostel_id)
        
        query = query.order_by(PaymentLedger.posted_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics Methods ====================

    async def calculate_financial_summary(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """
        Calculate financial summary for a period.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Financial summary
        """
        # Total debits
        debit_query = select(
            func.count(PaymentLedger.id).label("count"),
            func.sum(PaymentLedger.amount).label("total"),
        ).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.entry_type == LedgerEntryType.DEBIT,
            PaymentLedger.transaction_date >= start_date,
            PaymentLedger.transaction_date <= end_date,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        )
        debit_result = await self.session.execute(debit_query)
        debit_row = debit_result.one()
        
        # Total credits
        credit_query = select(
            func.count(PaymentLedger.id).label("count"),
            func.sum(PaymentLedger.amount).label("total"),
        ).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.entry_type == LedgerEntryType.CREDIT,
            PaymentLedger.transaction_date >= start_date,
            PaymentLedger.transaction_date <= end_date,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        )
        credit_result = await self.session.execute(credit_query)
        credit_row = credit_result.one()
        
        # Net balance
        net_query = select(
            func.sum(PaymentLedger.amount)
        ).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.transaction_date >= start_date,
            PaymentLedger.transaction_date <= end_date,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        )
        net_result = await self.session.execute(net_query)
        net_balance = net_result.scalar() or Decimal("0")
        
        return {
            "total_debits": float(abs(debit_row.total or Decimal("0"))),
            "debit_count": debit_row.count or 0,
            "total_credits": float(credit_row.total or Decimal("0")),
            "credit_count": credit_row.count or 0,
            "net_balance": float(net_balance),
        }

    async def get_transaction_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """
        Get transaction breakdown by type.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Transaction breakdown
        """
        query = select(
            PaymentLedger.transaction_type,
            func.count(PaymentLedger.id).label("count"),
            func.sum(PaymentLedger.amount).label("total_amount"),
        ).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.transaction_date >= start_date,
            PaymentLedger.transaction_date <= end_date,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        ).group_by(PaymentLedger.transaction_type)
        
        result = await self.session.execute(query)
        
        return [
            {
                "transaction_type": row.transaction_type.value,
                "count": row.count,
                "total_amount": float(row.total_amount or Decimal("0")),
            }
            for row in result.all()
        ]

    async def get_student_balances(
        self,
        hostel_id: UUID,
        min_balance: Decimal | None = None,
        max_balance: Decimal | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get balances for all students in a hostel.
        
        Args:
            hostel_id: Hostel ID
            min_balance: Minimum balance filter
            max_balance: Maximum balance filter
            
        Returns:
            List of student balances
        """
        # Subquery to calculate balances
        balance_subquery = select(
            PaymentLedger.student_id,
            func.sum(PaymentLedger.amount).label("balance"),
        ).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        ).group_by(PaymentLedger.student_id).subquery()
        
        query = select(balance_subquery)
        
        if min_balance is not None:
            query = query.where(balance_subquery.c.balance >= min_balance)
        
        if max_balance is not None:
            query = query.where(balance_subquery.c.balance <= max_balance)
        
        query = query.order_by(balance_subquery.c.balance.desc())
        
        result = await self.session.execute(query)
        
        return [
            {
                "student_id": str(row.student_id),
                "balance": float(row.balance or Decimal("0")),
            }
            for row in result.all()
        ]

    async def get_daily_balances(
        self,
        student_id: UUID,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """
        Get daily balance progression for a student.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Daily balance progression
        """
        query = select(
            PaymentLedger.transaction_date,
            func.sum(PaymentLedger.amount).label("daily_change"),
            func.max(PaymentLedger.balance_after).label("closing_balance"),
        ).where(
            PaymentLedger.student_id == student_id,
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.transaction_date >= start_date,
            PaymentLedger.transaction_date <= end_date,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        ).group_by(PaymentLedger.transaction_date).order_by(PaymentLedger.transaction_date)
        
        result = await self.session.execute(query)
        
        return [
            {
                "date": row.transaction_date.isoformat(),
                "daily_change": float(row.daily_change or Decimal("0")),
                "closing_balance": float(row.closing_balance or Decimal("0")),
            }
            for row in result.all()
        ]

    # ==================== Reconciliation Methods ====================

    async def perform_ledger_reconciliation(
        self,
        hostel_id: UUID,
        reconciled_by: UUID,
        reconciliation_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Perform ledger reconciliation for a hostel.
        
        Args:
            hostel_id: Hostel ID
            reconciled_by: User performing reconciliation
            reconciliation_date: Date to reconcile up to
            
        Returns:
            Reconciliation results
        """
        target_date = reconciliation_date or date.today()
        
        # Get unreconciled entries
        unreconciled_entries = await self.find_unreconciled_entries(
            hostel_id=hostel_id,
            older_than_days=0,
        )
        
        # Filter by date
        entries_to_reconcile = [
            entry for entry in unreconciled_entries
            if entry.transaction_date <= target_date
        ]
        
        # Mark entries as reconciled
        reconciled_count = 0
        for entry in entries_to_reconcile:
            await self.mark_reconciled(entry.id, reconciled_by)
            reconciled_count += 1
        
        # Calculate totals
        total_amount = sum(entry.amount for entry in entries_to_reconcile)
        
        return {
            "reconciliation_date": target_date.isoformat(),
            "entries_reconciled": reconciled_count,
            "total_amount": float(total_amount),
            "reconciled_by": str(reconciled_by),
            "reconciled_at": datetime.utcnow().isoformat(),
        }

    async def detect_reconciliation_discrepancies(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """
        Detect discrepancies in ledger entries.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            List of discrepancies found
        """
        discrepancies = []
        
        # Get all entries in period
        entries = await self.get_hostel_ledger(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )
        
        # Check balance calculations
        for i, entry in enumerate(entries):
            expected_balance = entry.balance_before + entry.amount
            if abs(expected_balance - entry.balance_after) > Decimal("0.01"):
                discrepancies.append({
                    "entry_id": str(entry.id),
                    "entry_reference": entry.entry_reference,
                    "type": "balance_mismatch",
                    "expected_balance": float(expected_balance),
                    "actual_balance": float(entry.balance_after),
                    "difference": float(expected_balance - entry.balance_after),
                })
        
        return discrepancies

    # ==================== Helper Methods ====================

    async def _generate_entry_reference(self, hostel_id: UUID) -> str:
        """Generate unique entry reference."""
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        query = select(func.count(PaymentLedger.id)).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.posted_at >= today_start,
        )
        
        result = await self.session.execute(query)
        count = result.scalar() or 0
        
        # Format: LED-YYYYMMDD-NNNN
        return f"LED-{date.today().strftime('%Y%m%d')}-{count + 1:04d}"