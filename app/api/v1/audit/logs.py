# api/v1/audit/logs.py

from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.audit.audit_log_base import AuditLogCreate
from app.schemas.audit.audit_log_response import AuditLogResponse, AuditLogDetail
from app.schemas.audit.audit_filters import AuditFilterParams
from app.schemas.audit.audit_reports import EntityChangeHistory
from app.schemas.common.pagination import PaginatedResponse
from app.services.common.unit_of_work import UnitOfWork
from app.services.audit import AuditLogService, EntityHistoryService

router = APIRouter(prefix="/logs")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.post(
    "/",
    response_model=AuditLogDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create an audit log entry",
)
async def create_audit_log(
    payload: AuditLogCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> AuditLogDetail:
    """
    Create a new audit log entry.

    In most cases, business services log actions internally, but this endpoint
    can be used for manual/debug logging or integrations.
    """
    service = AuditLogService(uow)
    try:
        return service.log_action(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/",
    response_model=PaginatedResponse[AuditLogResponse],
    summary="List audit logs with filters",
)
async def list_audit_logs(
    filters: AuditFilterParams = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedResponse[AuditLogResponse]:
    """
    List audit logs with flexible filters (user, role, hostel, entity, action, time range)
    and pagination parameters.
    """
    service = AuditLogService(uow)
    try:
        return service.list_logs(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{log_id}",
    response_model=AuditLogDetail,
    summary="Get audit log details",
)
async def get_audit_log(
    log_id: UUID = Path(..., description="Audit log ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AuditLogDetail:
    """
    Retrieve detailed information for a single audit log entry.
    """
    service = AuditLogService(uow)
    try:
        return service.get_log(log_id=log_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/entity/{entity_type}/{entity_id}/history",
    response_model=EntityChangeHistory,
    summary="Get change history for an entity",
)
async def get_entity_change_history(
    entity_type: str = Path(..., description="Entity type (e.g. hostel, student, complaint)"),
    entity_id: UUID = Path(..., description="Entity ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> EntityChangeHistory:
    """
    Build a change history for a specific entity from its audit log entries.
    """
    service = EntityHistoryService(uow)
    try:
        return service.get_entity_history(
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)