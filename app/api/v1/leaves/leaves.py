from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.leave.leave_application import (
    LeaveApplicationRequest,
    LeaveCancellationRequest,
)
from app.schemas.leave.leave_response import (
    LeaveDetail,
    LeaveResponse,
    LeaveListItem,
    LeaveSummary,
)
from app.services.leave.leave_application_service import LeaveApplicationService

router = APIRouter(prefix="/leaves", tags=["leaves"])


def get_leave_service(db: Session = Depends(deps.get_db)) -> LeaveApplicationService:
    return LeaveApplicationService(db=db)


@router.post(
    "",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for leave",
)
def apply_leave(
    payload: LeaveApplicationRequest,
    current_student=Depends(deps.get_student_user),
    service: LeaveApplicationService = Depends(get_leave_service),
) -> Any:
    """
    Student submits a leave application.
    """
    # Enforce student ID consistency if passed in payload vs token
    if payload.student_id and payload.student_id != current_student.id:
        raise HTTPException(
            status_code=403, detail="Cannot apply for another student"
        )
    # If not passed, use current_student.id
    if not payload.student_id:
        payload.student_id = current_student.id

    return service.apply(payload)


@router.get(
    "/{leave_id}",
    response_model=LeaveDetail,
    summary="Get leave application details",
)
def get_leave_detail(
    leave_id: str,
    current_user=Depends(deps.get_current_user),
    service: LeaveApplicationService = Depends(get_leave_service),
) -> Any:
    """
    Get full details of a leave application.
    Service should handle permission checks (student owns it OR user is admin/supervisor).
    """
    return service.get_detail(leave_id, user_id=current_user.id)


@router.post(
    "/{leave_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel leave application",
)
def cancel_leave(
    leave_id: str,
    payload: LeaveCancellationRequest,
    current_user=Depends(deps.get_current_user),
    service: LeaveApplicationService = Depends(get_leave_service),
) -> Any:
    service.cancel(leave_id, payload, user_id=current_user.id)
    return {"detail": "Leave application cancelled"}


@router.get(
    "",
    response_model=List[LeaveListItem],
    summary="List leave applications",
)
def list_leaves(
    # Filters could be complex; simplified here or use a FilterParams schema
    student_id: str = Query(None, description="Filter by student ID"),
    hostel_id: str = Query(None, description="Filter by hostel ID"),
    status: str = Query(None, description="Filter by status"),
    pagination=Depends(deps.get_pagination_params),
    current_user=Depends(deps.get_current_user),
    service: LeaveApplicationService = Depends(get_leave_service),
) -> Any:
    # If student, force filter to self
    if current_user.role == "student":
        student_id = current_user.id

    if student_id:
        return service.list_for_student(student_id, pagination=pagination)
    
    # Otherwise assume admin/supervisor listing for hostel
    if not hostel_id:
        # Fallback or error if admin doesn't provide hostel context
        pass 
        
    return service.list_for_hostel(
        hostel_id=hostel_id, status=status, pagination=pagination
    )


@router.get(
    "/summary/stats",
    response_model=LeaveSummary,
    summary="Get leave summary statistics",
)
def get_leave_summary(
    hostel_id: str = Query(...),
    current_user=Depends(deps.get_current_user),
    service: LeaveApplicationService = Depends(get_leave_service),
) -> Any:
    return service.summary(hostel_id=hostel_id)