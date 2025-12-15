# app/api/v1/supervisors/supervisors.py

from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.supervisor import SupervisorService
from app.schemas.supervisor.supervisor_base import (
    SupervisorCreate,
    SupervisorUpdate,
    SupervisorStatusUpdate,
    SupervisorReassignment,
)
from app.schemas.supervisor.supervisor_response import (
    SupervisorDetail,
    SupervisorListItem,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Supervisors"])


def _get_service(session: Session) -> SupervisorService:
    """Helper to construct SupervisorService with a UnitOfWork."""
    uow = UnitOfWork(session)
    return SupervisorService(uow)


@router.get("/", response_model=List[SupervisorListItem])
def list_supervisors(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Filter supervisors by hostel_id (optional)",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[SupervisorListItem]:
    """
    List supervisors, optionally filtered by hostel.

    Expected service method:
        list_supervisors(hostel_id: Union[UUID, None]) -> list[SupervisorListItem]
    """
    service = _get_service(session)
    return service.list_supervisors(hostel_id=hostel_id)


@router.get("/{supervisor_id}", response_model=SupervisorDetail)
def get_supervisor(
    supervisor_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorDetail:
    """
    Get detailed information for a single supervisor.

    Expected service method:
        get_supervisor_detail(supervisor_id: UUID) -> SupervisorDetail
    """
    service = _get_service(session)
    return service.get_supervisor_detail(supervisor_id=supervisor_id)


@router.post(
    "/",
    response_model=SupervisorDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_supervisor(
    payload: SupervisorCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorDetail:
    """
    Create a new supervisor.

    Expected service method:
        create_supervisor(data: SupervisorCreate) -> SupervisorDetail
    """
    service = _get_service(session)
    return service.create_supervisor(data=payload)


@router.patch("/{supervisor_id}", response_model=SupervisorDetail)
def update_supervisor(
    supervisor_id: UUID,
    payload: SupervisorUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorDetail:
    """
    Update supervisor details.

    Expected service method:
        update_supervisor(supervisor_id: UUID, data: SupervisorUpdate) -> SupervisorDetail
    """
    service = _get_service(session)
    return service.update_supervisor(
        supervisor_id=supervisor_id,
        data=payload,
    )


@router.patch("/{supervisor_id}/status", response_model=SupervisorDetail)
def update_supervisor_status(
    supervisor_id: UUID,
    payload: SupervisorStatusUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorDetail:
    """
    Update supervisor status (active/suspended/etc.).

    Expected service method:
        update_supervisor_status(supervisor_id: UUID, data: SupervisorStatusUpdate) -> SupervisorDetail
    """
    service = _get_service(session)
    return service.update_supervisor_status(
        supervisor_id=supervisor_id,
        data=payload,
    )


@router.post("/{supervisor_id}/reassign", response_model=SupervisorDetail)
def reassign_supervisor(
    supervisor_id: UUID,
    payload: SupervisorReassignment,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorDetail:
    """
    Reassign a supervisor (e.g., move primary hostel).

    Expected service method:
        reassign_supervisor(supervisor_id: UUID, data: SupervisorReassignment) -> SupervisorDetail
    """
    service = _get_service(session)
    return service.reassign_supervisor(
        supervisor_id=supervisor_id,
        data=payload,
    )