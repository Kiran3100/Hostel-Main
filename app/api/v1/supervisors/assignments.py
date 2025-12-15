# app/api/v1/supervisors/assignments.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.supervisor import SupervisorAssignmentService
from app.schemas.supervisor.supervisor_assignment import (
    SupervisorAssignment,
    AssignmentRequest,
    AssignmentUpdate,
    RevokeAssignmentRequest,
    AssignmentTransfer,
)
from . import CurrentUser, get_current_user, get_current_supervisor

router = APIRouter(tags=["Supervisors - Assignments"])


def _get_service(session: Session) -> SupervisorAssignmentService:
    uow = UnitOfWork(session)
    return SupervisorAssignmentService(uow)


@router.get("/me", response_model=List[SupervisorAssignment])
def list_my_assignments(
    current_user: CurrentUser = Depends(get_current_supervisor),
    session: Session = Depends(get_session),
) -> List[SupervisorAssignment]:
    """
    List hostel assignments for the authenticated supervisor.

    Expected service method:
        list_assignments_for_user(user_id: UUID) -> list[SupervisorAssignment]
    """
    service = _get_service(session)
    return service.list_assignments_for_user(user_id=current_user.id)


@router.get("/{supervisor_id}", response_model=List[SupervisorAssignment])
def list_assignments_for_supervisor(
    supervisor_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[SupervisorAssignment]:
    """
    List hostel assignments for the given supervisor.

    Expected service method:
        list_assignments_for_supervisor(supervisor_id: UUID) -> list[SupervisorAssignment]
    """
    service = _get_service(session)
    return service.list_assignments_for_supervisor(supervisor_id=supervisor_id)


@router.post(
    "",
    response_model=SupervisorAssignment,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    payload: AssignmentRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorAssignment:
    """
    Create a new supervisor↔hostel assignment.

    Expected service method:
        create_assignment(data: AssignmentRequest) -> SupervisorAssignment
    """
    service = _get_service(session)
    return service.create_assignment(data=payload)


@router.patch(
    "/{assignment_id}",
    response_model=SupervisorAssignment,
)
def update_assignment(
    assignment_id: UUID,
    payload: AssignmentUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorAssignment:
    """
    Update an existing assignment (role, dates, flags, etc.).

    Expected service method:
        update_assignment(assignment_id: UUID, data: AssignmentUpdate) -> SupervisorAssignment
    """
    service = _get_service(session)
    return service.update_assignment(
        assignment_id=assignment_id,
        data=payload,
    )


@router.post(
    "/{assignment_id}/revoke",
    response_model=SupervisorAssignment,
)
def revoke_assignment(
    assignment_id: UUID,
    payload: RevokeAssignmentRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorAssignment:
    """
    Revoke an assignment with a given reason.

    Expected service method:
        revoke_assignment(assignment_id: UUID, data: RevokeAssignmentRequest) -> SupervisorAssignment
    """
    service = _get_service(session)
    return service.revoke_assignment(
        assignment_id=assignment_id,
        data=payload,
    )


@router.post(
    "/transfer",
    response_model=SupervisorAssignment,
)
def transfer_assignment(
    payload: AssignmentTransfer,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorAssignment:
    """
    Transfer a supervisor from one hostel to another.

    Expected service method:
        transfer_assignment(data: AssignmentTransfer) -> SupervisorAssignment
    """
    service = _get_service(session)
    return service.transfer_assignment(data=payload)