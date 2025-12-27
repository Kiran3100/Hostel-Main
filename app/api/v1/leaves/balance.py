from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.leave.leave_balance import (
    LeaveBalanceSummary,
    # Maybe LeaveAdjustment schema for manual corrections
)
from app.services.leave.leave_balance_service import LeaveBalanceService

router = APIRouter(prefix="/leaves/balance", tags=["leaves:balance"])


def get_balance_service(db: Session = Depends(deps.get_db)) -> LeaveBalanceService:
    return LeaveBalanceService(db=db)


@router.get(
    "/summary",
    response_model=LeaveBalanceSummary,
    summary="Get leave balance summary",
)
def get_balance_summary(
    student_id: str = Query(None),
    current_user=Depends(deps.get_current_user),
    service: LeaveBalanceService = Depends(get_balance_service),
) -> Any:
    """
    Get balance summary for a student.
    If student_id not provided, defaults to current_user if they are a student.
    """
    target_id = student_id or current_user.id
    return service.get_balance_summary(student_id=target_id)


@router.post(
    "/adjust",
    summary="Manually adjust leave balance (Admin)",
)
def adjust_balance(
    student_id: str,
    leave_type: str,
    days: int,
    reason: str,
    _admin=Depends(deps.get_admin_user),
    service: LeaveBalanceService = Depends(get_balance_service),
) -> Any:
    return service.adjust_balance(
        student_id=student_id,
        leave_type=leave_type,
        days=days,
        reason=reason,
        actor_id=_admin.id,
    )


@router.get(
    "/usage",
    summary="Get detailed usage history",
)
def list_usage_details(
    student_id: str = Query(None),
    current_user=Depends(deps.get_current_user),
    service: LeaveBalanceService = Depends(get_balance_service),
) -> Any:
    target_id = student_id or current_user.id
    return service.list_usage_details(student_id=target_id)