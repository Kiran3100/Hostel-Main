# app/services/payment/payment_ledger_service.py
"""
Payment Ledger Service

Manages financial ledger entries and account statements.
Provides double-entry bookkeeping for payment transactions.
"""

from __future__ import annotations

from uuid import UUID
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentLedgerRepository, PaymentRepository
from app.schemas.common import DateRangeFilter
from app.schemas.payment import (
    LedgerEntry,
    AccountStatement,
    BalanceAdjustment,
    WriteOff,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.core1.logging import LoggingContext, logger


class PaymentLedgerService:
    """
    High-level service for payment ledger and account statements.

    Responsibilities:
    - Record ledger entries for all payment transactions
    - Generate account statements with filtering
    - Apply balance adjustments with proper authorization
    - Handle write-offs with audit trail
    - Maintain ledger integrity and balance consistency
    """

    __slots__ = ("ledger_repo", "payment_repo")

    def __init__(
        self,
        ledger_repo: PaymentLedgerRepository,
        payment_repo: PaymentRepository,
    ) -> None:
        self.ledger_repo = ledger_repo
        self.payment_repo = payment_repo

    # -------------------------------------------------------------------------
    # Account statements
    # -------------------------------------------------------------------------

    def get_account_statement_for_student(
        self,
        db: Session,
        student_id: UUID,
        period: Optional[DateRangeFilter] = None,
        include_adjustments: bool = True,
        include_writeoffs: bool = True,
    ) -> AccountStatement:
        """
        Generate account statement for a student.

        Args:
            db: Database session
            student_id: Student UUID
            period: Optional date range filter
            include_adjustments: Include manual adjustments
            include_writeoffs: Include write-offs

        Returns:
            AccountStatement with ledger entries and summary

        Raises:
            NotFoundException: If no ledger data found
        """
        with LoggingContext(student_id=str(student_id)):
            data = self.ledger_repo.get_student_statement(
                db=db,
                student_id=student_id,
                start_date=period.start_date if period else None,
                end_date=period.end_date if period else None,
                include_adjustments=include_adjustments,
                include_writeoffs=include_writeoffs,
            )

            if not data:
                logger.warning(f"No ledger data found for student: {student_id}")
                raise NotFoundException(
                    f"No ledger data found for student: {student_id}"
                )

            statement = AccountStatement.model_validate(data)

            # Verify ledger balance integrity
            self._verify_statement_integrity(statement)

            logger.info(
                f"Generated statement for student: {student_id}",
                extra={
                    "student_id": str(student_id),
                    "entries_count": len(statement.entries),
                    "balance": float(statement.current_balance),
                },
            )

            return statement

    def get_account_statement_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        period: Optional[DateRangeFilter] = None,
        include_adjustments: bool = True,
        include_writeoffs: bool = True,
    ) -> AccountStatement:
        """
        Generate account statement for a hostel (all students).

        Args:
            db: Database session
            hostel_id: Hostel UUID
            period: Optional date range filter
            include_adjustments: Include manual adjustments
            include_writeoffs: Include write-offs

        Returns:
            AccountStatement with aggregated ledger entries

        Raises:
            NotFoundException: If no ledger data found
        """
        with LoggingContext(hostel_id=str(hostel_id)):
            data = self.ledger_repo.get_hostel_statement(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date if period else None,
                end_date=period.end_date if period else None,
                include_adjustments=include_adjustments,
                include_writeoffs=include_writeoffs,
            )

            if not data:
                logger.warning(f"No ledger data found for hostel: {hostel_id}")
                raise NotFoundException(
                    f"No ledger data found for hostel: {hostel_id}"
                )

            statement = AccountStatement.model_validate(data)

            logger.info(
                f"Generated statement for hostel: {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "entries_count": len(statement.entries),
                    "balance": float(statement.current_balance),
                },
            )

            return statement

    def _verify_statement_integrity(self, statement: AccountStatement) -> None:
        """
        Verify that statement balances are consistent.

        Raises:
            BusinessLogicException: If integrity check fails
        """
        calculated_balance = statement.opening_balance

        for entry in statement.entries:
            if entry.entry_type == "debit":
                calculated_balance -= entry.amount
            else:  # credit
                calculated_balance += entry.amount

        # Allow small rounding differences (< 0.01)
        difference = abs(calculated_balance - statement.current_balance)
        if difference > Decimal("0.01"):
            logger.error(
                f"Statement balance mismatch: calculated={calculated_balance}, "
                f"recorded={statement.current_balance}, difference={difference}"
            )
            raise BusinessLogicException(
                "Statement balance integrity check failed"
            )

    # -------------------------------------------------------------------------
    # Ledger entries
    # -------------------------------------------------------------------------

    def get_ledger_entry(
        self,
        db: Session,
        entry_id: UUID,
    ) -> LedgerEntry:
        """
        Retrieve a single ledger entry by ID.

        Args:
            db: Database session
            entry_id: Ledger entry UUID

        Returns:
            LedgerEntry details

        Raises:
            NotFoundException: If entry not found
        """
        obj = self.ledger_repo.get_by_id(db, entry_id)
        if not obj:
            raise NotFoundException(f"Ledger entry not found: {entry_id}")

        return LedgerEntry.model_validate(obj)

    def list_ledger_entries(
        self,
        db: Session,
        student_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        entry_type: Optional[str] = None,
        period: Optional[DateRangeFilter] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> List[LedgerEntry]:
        """
        List ledger entries with filtering.

        Args:
            db: Database session
            student_id: Optional student filter
            hostel_id: Optional hostel filter
            entry_type: Optional entry type filter (debit/credit)
            period: Optional date range filter
            page: Page number
            page_size: Items per page

        Returns:
            List of LedgerEntry objects
        """
        filters = {}
        if student_id:
            filters["student_id"] = student_id
        if hostel_id:
            filters["hostel_id"] = hostel_id
        if entry_type:
            filters["entry_type"] = entry_type
        if period:
            filters["start_date"] = period.start_date
            filters["end_date"] = period.end_date

        result = self.ledger_repo.list_entries(
            db=db,
            filters=filters,
            page=page,
            page_size=page_size,
        )

        return [LedgerEntry.model_validate(obj) for obj in result["items"]]

    # -------------------------------------------------------------------------
    # Balance adjustments
    # -------------------------------------------------------------------------

    def apply_balance_adjustment(
        self,
        db: Session,
        request: BalanceAdjustment,
        applied_by: UUID,
    ) -> LedgerEntry:
        """
        Apply a manual balance adjustment to a student account.

        This should be used for:
        - Correcting errors
        - Applying credits/discounts
        - Manual reconciliation

        Requires proper authorization and creates audit trail.

        Args:
            db: Database session
            request: Balance adjustment details
            applied_by: UUID of user applying the adjustment

        Returns:
            LedgerEntry for the adjustment

        Raises:
            ValidationException: If adjustment is invalid
            BusinessLogicException: If adjustment violates business rules
        """
        self._validate_balance_adjustment(request)

        payload = request.model_dump(exclude_none=True)
        payload["applied_by"] = applied_by
        payload["applied_at"] = datetime.utcnow()

        with LoggingContext(
            student_id=str(request.student_id),
            adjustment_amount=float(request.amount),
        ):
            try:
                obj = self.ledger_repo.apply_balance_adjustment(db, payload)

                logger.info(
                    f"Balance adjustment applied: {obj.id}",
                    extra={
                        "entry_id": str(obj.id),
                        "student_id": str(request.student_id),
                        "amount": float(request.amount),
                        "type": request.adjustment_type,
                        "applied_by": str(applied_by),
                    },
                )

                return LedgerEntry.model_validate(obj)

            except Exception as e:
                logger.error(f"Failed to apply balance adjustment: {str(e)}")
                raise BusinessLogicException(
                    f"Failed to apply balance adjustment: {str(e)}"
                )

    def _validate_balance_adjustment(self, request: BalanceAdjustment) -> None:
        """Validate balance adjustment request."""
        if request.amount <= 0:
            raise ValidationException("Adjustment amount must be positive")

        if not request.reason or len(request.reason.strip()) < 10:
            raise ValidationException(
                "Adjustment reason must be at least 10 characters"
            )

        if request.adjustment_type not in {"credit", "debit"}:
            raise ValidationException(
                f"Invalid adjustment type: {request.adjustment_type}"
            )

    def reverse_balance_adjustment(
        self,
        db: Session,
        entry_id: UUID,
        reversal_reason: str,
        reversed_by: UUID,
    ) -> LedgerEntry:
        """
        Reverse a previous balance adjustment.

        Creates a new ledger entry that reverses the original.

        Args:
            db: Database session
            entry_id: Original adjustment entry ID
            reversal_reason: Reason for reversal
            reversed_by: UUID of user performing reversal

        Returns:
            LedgerEntry for the reversal

        Raises:
            NotFoundException: If original entry not found
            BusinessLogicException: If entry cannot be reversed
        """
        original = self.ledger_repo.get_by_id(db, entry_id)
        if not original:
            raise NotFoundException(f"Ledger entry not found: {entry_id}")

        if original.entry_category != "adjustment":
            raise BusinessLogicException(
                "Only adjustment entries can be reversed"
            )

        if original.is_reversed:
            raise BusinessLogicException("Entry has already been reversed")

        with LoggingContext(entry_id=str(entry_id)):
            # Create reversal entry
            reversal_payload = {
                "student_id": original.student_id,
                "hostel_id": original.hostel_id,
                "amount": original.amount,
                "entry_type": "credit" if original.entry_type == "debit" else "debit",
                "entry_category": "adjustment_reversal",
                "description": f"Reversal of adjustment {entry_id}: {reversal_reason}",
                "reference_id": original.id,
                "applied_by": reversed_by,
                "applied_at": datetime.utcnow(),
            }

            reversal = self.ledger_repo.create_entry(db, reversal_payload)

            # Mark original as reversed
            self.ledger_repo.update(
                db,
                original,
                data={
                    "is_reversed": True,
                    "reversed_by": reversed_by,
                    "reversed_at": datetime.utcnow(),
                },
            )

            logger.info(
                f"Balance adjustment reversed: {entry_id}",
                extra={
                    "original_entry_id": str(entry_id),
                    "reversal_entry_id": str(reversal.id),
                },
            )

            return LedgerEntry.model_validate(reversal)

    # -------------------------------------------------------------------------
    # Write-offs
    # -------------------------------------------------------------------------

    def apply_write_off(
        self,
        db: Session,
        request: WriteOff,
        applied_by: UUID,
    ) -> LedgerEntry:
        """
        Write off uncollectible amount.

        This permanently removes the amount from accounts receivable.
        Should only be used after proper collection procedures.

        Args:
            db: Database session
            request: Write-off details
            applied_by: UUID of user applying write-off

        Returns:
            LedgerEntry for the write-off

        Raises:
            ValidationException: If write-off is invalid
            BusinessLogicException: If write-off violates business rules
        """
        self._validate_write_off(request)

        payload = request.model_dump(exclude_none=True)
        payload["applied_by"] = applied_by
        payload["applied_at"] = datetime.utcnow()

        with LoggingContext(
            student_id=str(request.student_id),
            writeoff_amount=float(request.amount),
        ):
            try:
                obj = self.ledger_repo.apply_write_off(db, payload)

                logger.warning(
                    f"Write-off applied: {obj.id}",
                    extra={
                        "entry_id": str(obj.id),
                        "student_id": str(request.student_id),
                        "amount": float(request.amount),
                        "reason": request.reason,
                        "applied_by": str(applied_by),
                    },
                )

                return LedgerEntry.model_validate(obj)

            except Exception as e:
                logger.error(f"Failed to apply write-off: {str(e)}")
                raise BusinessLogicException(f"Failed to apply write-off: {str(e)}")

    def _validate_write_off(self, request: WriteOff) -> None:
        """Validate write-off request."""
        if request.amount <= 0:
            raise ValidationException("Write-off amount must be positive")

        if not request.reason or len(request.reason.strip()) < 20:
            raise ValidationException(
                "Write-off reason must be at least 20 characters"
            )

        if not request.approval_reference:
            raise ValidationException(
                "Approval reference is required for write-offs"
            )

    # -------------------------------------------------------------------------
    # Balance queries
    # -------------------------------------------------------------------------

    def get_current_balance(
        self,
        db: Session,
        student_id: UUID,
    ) -> Decimal:
        """
        Get current account balance for a student.

        Args:
            db: Database session
            student_id: Student UUID

        Returns:
            Current balance (positive = credit, negative = debit)
        """
        balance = self.ledger_repo.get_current_balance(db, student_id)
        return Decimal(str(balance))

    def get_balance_at_date(
        self,
        db: Session,
        student_id: UUID,
        as_of_date: date,
    ) -> Decimal:
        """
        Get account balance as of a specific date.

        Args:
            db: Database session
            student_id: Student UUID
            as_of_date: Date for balance calculation

        Returns:
            Balance as of the specified date
        """
        balance = self.ledger_repo.get_balance_at_date(
            db, student_id, as_of_date
        )
        return Decimal(str(balance))

    def get_receivables_summary(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get summary of accounts receivable for a hostel.

        Args:
            db: Database session
            hostel_id: Hostel UUID

        Returns:
            Summary with total receivables, overdue amounts, etc.
        """
        return self.ledger_repo.get_receivables_summary(db, hostel_id)