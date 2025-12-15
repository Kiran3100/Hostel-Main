# app/services/payment/payment_ledger_service.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.repositories.core import HostelRepository, StudentRepository, UserRepository
from app.schemas.common.enums import PaymentStatus
from app.schemas.payment.payment_ledger import (
    LedgerEntry,
    LedgerSummary,
    AccountStatement,
    TransactionHistory,
    TransactionItem,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork, errors


class PaymentLedgerService:
    """
    Ledger-style views derived from payments:

    - Generate ledger entries & summaries per student
    - Produce account statements for periods
    - Simple transaction history
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Ledger summary
    # ------------------------------------------------------------------ #
    def get_ledger_summary(self, student_id: UUID, hostel_id: UUID) -> LedgerSummary:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            student_repo = self._get_student_repo(uow)

            student = student_repo.get(student_id)
            if not student or student.hostel_id != hostel_id:
                raise errors.NotFoundError("Student/hostel mismatch or not found")

            payments = pay_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"student_id": student_id, "hostel_id": hostel_id},
            )

        total_payments = Decimal("0")
        last_tx_date: Optional[date] = None

        for p in payments:
            if p.payment_status == PaymentStatus.COMPLETED and p.paid_at:
                total_payments += p.amount
                d = p.paid_at.date()
                if not last_tx_date or d > last_tx_date:
                    last_tx_date = d

        current_balance = Decimal("0") - total_payments
        total_charges = Decimal("0")
        total_refunds = Decimal("0")
        total_due = Decimal("0")
        overdue_amount = Decimal("0")

        last_payment_date = last_tx_date
        last_payment_amount = total_payments if last_tx_date else None

        return LedgerSummary(
            student_id=student_id,
            student_name=student.user.full_name if getattr(student, "user", None) else "",
            hostel_id=hostel_id,
            current_balance=current_balance,
            total_charges=total_charges,
            total_payments=total_payments,
            total_refunds=total_refunds,
            total_due=total_due,
            overdue_amount=overdue_amount,
            last_transaction_date=last_tx_date,
            last_payment_date=last_payment_date,
        )

    # ------------------------------------------------------------------ #
    # Account statement
    # ------------------------------------------------------------------ #
    def get_account_statement(
        self,
        student_id: UUID,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> AccountStatement:
        if not (period.start_date and period.end_date):
            raise errors.ValidationError(
                "Both start_date and end_date are required for account statement"
            )
        start = period.start_date
        end = period.end_date

        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)

            student = student_repo.get(student_id)
            if not student or student.hostel_id != hostel_id:
                raise errors.NotFoundError("Student/hostel mismatch or not found")

            hostel = hostel_repo.get(hostel_id)
            if not hostel:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            payments = pay_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"student_id": student_id, "hostel_id": hostel_id},
            )

        # Opening balance assumed 0 for simplicity
        opening_balance = Decimal("0")
        balance = opening_balance

        entries: List[LedgerEntry] = []
        total_debits = Decimal("0")
        total_credits = Decimal("0")

        seq = sorted(
            [p for p in payments if p.paid_at and start <= p.paid_at.date() <= end],
            key=lambda p: p.paid_at,
        )

        for p in seq:
            amount = p.amount
            balance_before = balance
            balance_after = balance_before + amount * Decimal("-1")
            balance = balance_after

            entry = LedgerEntry(
                id=p.id,
                created_at=p.created_at,
                updated_at=p.updated_at,
                student_id=student_id,
                hostel_id=hostel_id,
                entry_date=p.paid_at.date() if p.paid_at else start,
                entry_type="credit",
                transaction_type=p.payment_type.value if hasattr(p.payment_type, "value") else str(p.payment_type),
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                payment_id=p.id,
                payment_reference=str(p.id),
                description="Payment received",
                created_by=None,
                notes=None,
            )
            entries.append(entry)
            total_credits += amount

        closing_balance = balance

        return AccountStatement(
            student_id=student_id,
            student_name=student.user.full_name if getattr(student, "user", None) else "",
            hostel_id=hostel_id,
            hostel_name=hostel.name,
            statement_period_start=start,
            statement_period_end=end,
            generated_at=self._now(),
            opening_balance=opening_balance,
            entries=entries,
            total_debits=total_debits,
            total_credits=total_credits,
            closing_balance=closing_balance,
            pdf_url=None,
        )

    # ------------------------------------------------------------------ #
    # Transaction history
    # ------------------------------------------------------------------ #
    def get_transaction_history(
        self,
        student_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> TransactionHistory:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)

            payments = pay_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"student_id": student_id},
                order_by=[pay_repo.model.created_at.desc()],  # type: ignore[attr-defined]
            )

        total = len(payments)
        start_ix = (page - 1) * page_size
        end_ix = start_ix + page_size
        subset = payments[start_ix:end_ix]

        balance = Decimal("0")
        items: List[TransactionItem] = []
        for p in reversed(subset):  # chronological
            amount = p.amount
            balance = balance - amount
            items.append(
                TransactionItem(
                    transaction_id=p.id,
                    transaction_date=p.paid_at or p.created_at,
                    transaction_type=p.payment_type.value if hasattr(p.payment_type, "value") else str(p.payment_type),
                    amount=amount,
                    balance_after=balance,
                    description="Payment",
                    payment_reference=str(p.id),
                    status=p.payment_status.value if hasattr(p.payment_status, "value") else str(p.payment_status),
                )
            )

        return TransactionHistory(
            student_id=student_id,
            transactions=items,
            total_transactions=total,
            page=page,
            page_size=page_size,
        )