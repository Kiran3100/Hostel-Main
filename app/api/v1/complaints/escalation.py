# api/v1/complaints/escalation.py

from datetime import date
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.complaint.complaint_escalation import (
    EscalationRequest,
    EscalationResponse,
    EscalationHistory,
    AutoEscalationRule,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.complaint import ComplaintEscalationService

router = APIRouter(prefix="/escalation")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.post(
    "/{complaint_id}",
    response_model=EscalationResponse,
    summary="Escalate a complaint",
)
async def escalate_complaint(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: EscalationRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> EscalationResponse:
    """
    Manually escalate a complaint according to escalation rules.
    """
    service = ComplaintEscalationService(uow)
    try:
        return service.escalate(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{complaint_id}/history",
    response_model=EscalationHistory,
    summary="Get complaint escalation history",
)
async def get_escalation_history(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> EscalationHistory:
    """
    Retrieve the full escalation history for a complaint.
    """
    service = ComplaintEscalationService(uow)
    try:
        return service.get_history(complaint_id=complaint_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/rules/{hostel_id}",
    response_model=AutoEscalationRule,
    summary="Get auto-escalation rules for a hostel",
)
async def get_auto_escalation_rules(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AutoEscalationRule:
    """
    Fetch SLA-based auto-escalation rules for a hostel.
    """
    service = ComplaintEscalationService(uow)
    try:
        return service.get_rules(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/rules/{hostel_id}",
    response_model=AutoEscalationRule,
    summary="Update auto-escalation rules for a hostel",
)
async def update_auto_escalation_rules(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: AutoEscalationRule = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AutoEscalationRule:
    """
    Create or update SLA-based auto-escalation rules for a hostel.
    """
    service = ComplaintEscalationService(uow)
    try:
        return service.update_rules(
            hostel_id=hostel_id,
            rules=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)