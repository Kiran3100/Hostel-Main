from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    EscalationRequest,
    EscalationResponse,
    EscalationHistory,
    AutoEscalationRule,
)
from app.services.complaint.complaint_escalation_service import ComplaintEscalationService

router = APIRouter(prefix="/complaints/escalation", tags=["complaints:escalation"])


def get_escalation_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintEscalationService:
    return ComplaintEscalationService(db=db)


@router.post(
    "/{complaint_id}",
    response_model=EscalationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Escalate complaint",
)
def escalate_complaint(
    complaint_id: str,
    payload: EscalationRequest,
    current_user=Depends(deps.get_current_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    return service.escalate(
        complaint_id=complaint_id, payload=payload, user_id=current_user.id
    )


@router.get(
    "/{complaint_id}/history",
    response_model=EscalationHistory,
    summary="Get escalation history",
)
def get_escalation_history(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    return service.history(complaint_id)


@router.post(
    "/rules",
    response_model=AutoEscalationRule,
    summary="Set auto-escalation rule (admin)",
)
def set_auto_escalation_rule(
    payload: AutoEscalationRule,
    _admin=Depends(deps.get_admin_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    return service.set_auto_rule(payload)