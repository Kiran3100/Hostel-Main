# app/services/student/student_finance_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.repositories.core import StudentRepository
from app.schemas.common.enums import PaymentStatus
from app.schemas.student.student_dashboard import StudentFinancialSummary
from app.schemas.student.student_response import StudentFinancialInfo
from app.services.common import UnitOfWork, errors


class StudentFinanceService:
    """
    Student-level financial data:

    - StudentFinancialSummary (for dashboard)
    - StudentFinancialInfo (detailed, for admin views)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _today(self) -> date:
        return date.today()

    # ------------------------------------------------------------------ #
    # Summary for dashboard
    # ------------------------------------------------------------------ #
    def get_financial_summary(self, student_id: UUID) -> StudentFinancialSummary:
        today = self._today()

        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            student_repo = self._get_student_repo(uow)

            s = student_repo.get(student_id)
            if s is None:
                raise errors.NotFoundError(f"Student {student_id} not found")

            payments = pay_repo.list_for_student(student_id)

        amount_due = Decimal("0")
        amount_overdue = Decimal("0")
        next_due_date: Optional[date] = None

        for p in payments:
            if p.payment_status == PaymentStatus.PENDING:
                amount_due += p.amount
                if p.due_date and p.due_date < today:
                    amount_overdue += p.amount
                if p.due_date:
                    if not next_due_date or p.due_date < next_due_date:
                        next_due_date = p.due_date

        days_until_due = (
            (next_due_date - today).days if next_due_date else None
        )

        status_str = "current"
        if amount_overdue > 0:
            status_str = "overdue"
        elif amount_due > 0:
            status_str = "due_soon"

        return StudentFinancialSummary(
            monthly_rent=s.monthly_rent_amount or Decimal("0"),
            next_due_date=next_due_date or today,
            amount_due=amount_due,
            amount_overdue=amount_overdue,
            advance_balance=Decimal("0"),
            security_deposit=s.security_deposit_amount or Decimal("0"),
            mess_charges=Decimal("0"),
            mess_balance=Decimal("0"),
            payment_status=status_str,
            days_until_due=days_until_due,
        )

    # ------------------------------------------------------------------ #
    # Detailed info
    # ------------------------------------------------------------------ #
    def get_financial_info(self, student_id: UUID) -> StudentFinancialInfo:
        today = self._today()

        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            student_repo = self._get_student_repo(uow)

            s = student_repo.get(student_id)
            if s is None or not getattr(s, "user", None):
                raise errors.NotFoundError(f"Student {student_id} not found")

            payments = pay_repo.list_for_student(student_id)

        total_paid = Decimal("0")
        total_due = Decimal("0")
        overdue_amount = Decimal("0")
        advance_amount = Decimal("0")
        last_payment_date: Optional[date] = None
        next_due_date: Optional[date] = None

        for p in payments:
            if p.payment_status == PaymentStatus.COMPLETED and p.paid_at:
                total_paid += p.amount
                d = p.paid_at.date()
                if not last_payment_date or d > last_payment_date:
                    last_payment_date = d
            elif p.payment_status == PaymentStatus.PENDING:
                total_due += p.amount
                if p.due_date and p.due_date < today:
                    overdue_amount += p.amount
                if p.due_date:
                    if not next_due_date or p.due_date < next_due_date:
                        next_due_date = p.due_date

        return StudentFinancialInfo(
            student_id=student_id,
            student_name=s.user.full_name,
            monthly_rent_amount=s.monthly_rent_amount or Decimal("0"),
            security_deposit_amount=s.security_deposit_amount or Decimal("0"),
            security_deposit_paid=False,
            security_deposit_refundable=s.security_deposit_amount or Decimal("0"),
            total_paid=total_paid,
            total_due=total_due,
            last_payment_date=last_payment_date,
            next_due_date=next_due_date,
            overdue_amount=overdue_amount,
            advance_amount=advance_amount,
            mess_charges_monthly=Decimal("0"),
            mess_balance=Decimal("0"),
        )