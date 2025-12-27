from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    ResolutionRequest,
    ResolutionResponse,
    ResolutionUpdate,
    ReopenRequest,
    CloseRequest,
)
from app.services.complaint.complaint_resolution_service import ComplaintResolutionService

router = APIRouter(prefix="/complaints/resolution", tags=["complaints:resolution"])


def get_resolution_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintResolutionService:
    return ComplaintResolutionService(db=db)


@router.post(
    "/{complaint_id}/resolve",
    response_model=ResolutionResponse,
    summary="Resolve complaint",
)
def resolve_complaint(
    complaint_id: str,
    payload: ResolutionRequest,
    _supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    return service.resolve(
        complaint_id=complaint_id, payload=payload, resolver_id=_supervisor.id
    )


@router.put(
    "/{complaint_id}/resolve",
    response_model=ResolutionResponse,
    summary="Update resolution",
)
def update_resolution(
    complaint_id: str,
    payload: ResolutionUpdate,
    _supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    return service.update_resolution(
        complaint_id=complaint_id, payload=payload, user_id=_supervisor.id
    )


@router.post(
    "/{complaint_id}/reopen",
    response_model=ResolutionResponse,  # or ComplaintDetail
    summary="Reopen complaint",
)
def reopen_complaint(
    complaint_id: str,
    payload: ReopenRequest,
    current_user=Depends(deps.get_current_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    return service.reopen(
        complaint_id=complaint_id, payload=payload, user_id=current_user.id
    )


@router.post(
    "/{complaint_id}/close",
    summary="Close complaint (final)",
)
def close_complaint(
    complaint_id: str,
    payload: CloseRequest,
    current_user=Depends(deps.get_current_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    return service.close(
        complaint_id=complaint_id, payload=payload, user_id=current_user.id
    )