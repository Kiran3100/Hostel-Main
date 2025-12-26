# app/services/payment/payment_ledger_service.py
"""
Payment Ledger Service

Manages financial ledger entries and account statements.
"""

from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentLedgerRepository, PaymentRepository
from app.schemas.common import DateRangeFilter
from app.schemas.payment import (
    LedgerEntry,
    AccountStatement,
    BalanceAdjustment,
    WriteOff,
)
from app.core.exceptions import ValidationException


class PaymentLedgerService:
    """
    High-level service for payment ledger and account statements.

    Responsibilities:
    - Record ledger entries when payments are created/refunded/write-off
    - Generate account statements
    - Apply balance adjustments and write-offs
    """

    def __init__(
        self,
        ledger_repo: PaymentLedgerRepository,
        payment_repo: PaymentRepository,
    ) -> None:
        self.ledger_repo = ledger_repo
        self.payment_repo = payment_repo

    # -------------------------------------------------------------------------
    # Statements
    # -------------------------------------------------------------------------

    def get_account_statement_for_student(
        self,
        db: Session,
        student_id: UUID,
        period: Optional[DateRangeFilter] = None,
    ) -> AccountStatement:
        data = self.ledger_repo.get_student_statement(
            db=db,
            student_id=student_id,
            start_date=period.start_date if period else None,
            end_date=period.end_date if period else None,
        )
        if not data:
            raise ValidationException("No ledger data for student")

        return AccountStatement.model_validate(data)

    def get_account_statement_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        period: Optional[DateRangeFilter] = None,
    ) -> AccountStatement:
        data = self.ledger_repo.get_hostel_statement(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date if period else None,
            end_date=period.end_date if period else None,
        )
        if not data:
            raise ValidationException("No ledger data for hostel")

        return AccountStatement.model_validate(data)

    # -------------------------------------------------------------------------
    # Adjustments & write-offs
    # -------------------------------------------------------------------------

    def apply_balance_adjustment(
        self,
        db: Session,
        request: BalanceAdjustment,
        applied_by: UUID,
    ) -> LedgerEntry:
        """
        Apply a manual balance adjustment to a student account.
        """
        payload = request.model_dump(exclude_none=True)
        payload["applied_by"] = applied_by

        obj = self.ledger_repo.apply_balance_adjustment(db, payload)
        return LedgerEntry.model_validate(obj)

    def apply_write_off(
        self,
        db: Session,
        request: WriteOff,
        applied_by: UUID,
    ) -> LedgerEntry:
        """
        Write off uncollectible amount.
        """
        payload = request.model_dump(exclude_none=True)
        payload["applied_by"] = applied_by

        obj = self.ledger_repo.apply_write_off(db, payload)
        return LedgerEntry.model_validate(obj)