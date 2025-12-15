# app/api/v1/payments/ledger.py
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.payment import PaymentLedgerService
from app.schemas.payment.payment_ledger import (
    LedgerSummary,
    AccountStatement,
    TransactionHistory,
)
from . import CurrentUser, get_current_user, get_current_admin_or_staff

router = APIRouter(tags=["Payments - Ledger"])


def _get_service(session: Session) -> PaymentLedgerService:
    uow = UnitOfWork(session)
    return PaymentLedgerService(uow)


@router.get("/students/{student_id}/summary", response_model=LedgerSummary)
def get_student_ledger_summary(
    student_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> LedgerSummary:
    """
    Get high-level ledger summary for a student.
    """
    service = _get_service(session)
    # Expected: get_ledger_summary(student_id: UUID) -> LedgerSummary
    return service.get_ledger_summary(student_id=student_id)


@router.get("/students/{student_id}/statement", response_model=AccountStatement)
def get_student_account_statement(
    student_id: UUID,
    start_date: Optional[date] = Query(
        None,
        description="Start date for the statement period (inclusive).",
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for the statement period (inclusive).",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> AccountStatement:
    """
    Get account statement for a student over a date range.
    """
    service = _get_service(session)
    # Expected:
    #   get_account_statement(student_id: UUID,
    #                         start_date: Optional[date],
    #                         end_date: Optional[date]) -> AccountStatement
    return service.get_account_statement(
        student_id=student_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/students/{student_id}/transactions", response_model=TransactionHistory)
def get_student_transaction_history(
    student_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> TransactionHistory:
    """
    Get full transaction history for a student.
    """
    service = _get_service(session)
    # Expected: get_transaction_history(student_id: UUID) -> TransactionHistory
    return service.get_transaction_history(student_id=student_id)


@router.get("/me/statement", response_model=AccountStatement)
def get_my_account_statement(
    start_date: Optional[date] = Query(
        None,
        description="Start date for the statement period (inclusive).",
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for the statement period (inclusive).",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AccountStatement:
    """
    Get an account statement for the authenticated user (if they are a student/payer).
    """
    service = _get_service(session)
    # Expected: get_account_statement_for_user(user_id: UUID, start_date, end_date) -> AccountStatement
    return service.get_account_statement_for_user(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
    )