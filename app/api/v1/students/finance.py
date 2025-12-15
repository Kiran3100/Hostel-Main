# app/api/v1/students/finance.py
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.student import StudentFinanceService
from app.schemas.student.student_dashboard import StudentFinancialSummary
from app.schemas.student.student_response import StudentFinancialInfo
from . import CurrentUser, get_current_user, get_current_student

router = APIRouter(tags=["Students - Finance"])


def _get_service(session: Session) -> StudentFinanceService:
    uow = UnitOfWork(session)
    return StudentFinanceService(uow)


@router.get("/me/summary", response_model=StudentFinancialSummary)
def get_my_financial_summary(
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> StudentFinancialSummary:
    """
    Financial summary for the authenticated student (due/overdue/next due).

    Expected service method:
        get_summary_for_user(user_id: UUID) -> StudentFinancialSummary
    """
    service = _get_service(session)
    return service.get_summary_for_user(user_id=current_user.id)


@router.get("/{student_id}/summary", response_model=StudentFinancialSummary)
def get_financial_summary_for_student(
    student_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> StudentFinancialSummary:
    """
    Admin endpoint: financial summary for a specific student.

    Expected service method:
        get_summary_for_student(student_id: UUID) -> StudentFinancialSummary
    """
    service = _get_service(session)
    return service.get_summary_for_student(student_id=student_id)


@router.get("/{student_id}/detail", response_model=StudentFinancialInfo)
def get_financial_detail_for_student(
    student_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> StudentFinancialInfo:
    """
    Admin endpoint: detailed financial info for a specific student.

    Expected service method:
        get_financial_info(student_id: UUID) -> StudentFinancialInfo
    """
    service = _get_service(session)
    return service.get_financial_info(student_id=student_id)