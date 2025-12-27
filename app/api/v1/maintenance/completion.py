from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_completion import (
    CompletionRequest,
    CompletionResponse,
    QualityCheck,
    CompletionCertificate,
)
from app.services.maintenance.maintenance_completion_service import (
    MaintenanceCompletionService,
)

router = APIRouter(prefix="/completion", tags=["maintenance:completion"])


def get_completion_service(
    db: Session = Depends(deps.get_db),
) -> MaintenanceCompletionService:
    return MaintenanceCompletionService(db=db)


@router.post(
    "/{request_id}",
    response_model=CompletionResponse,
    summary="Record completion",
)
def record_completion(
    request_id: str,
    payload: CompletionRequest,
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    return service.record_completion(
        request_id=request_id, payload=payload, actor_id=_supervisor.id
    )


@router.post(
    "/{request_id}/quality-check",
    summary="Record quality check",
)
def record_quality_check(
    request_id: str,
    payload: QualityCheck,
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    return service.record_quality_check(
        request_id=request_id, payload=payload, actor_id=_supervisor.id
    )


@router.get(
    "/{request_id}/certificate",
    response_model=CompletionCertificate,
    summary="Generate completion certificate",
)
def get_completion_certificate(
    request_id: str,
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    return service.generate_completion_certificate(request_id)