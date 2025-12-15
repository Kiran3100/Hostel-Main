# api/v1/mess/approval.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.mess.menu_approval import (
    MenuApprovalRequest,
    MenuApprovalResponse,
    ApprovalWorkflow,
    BulkApproval,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.mess import MessMenuService

router = APIRouter(prefix="/approval")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/menus/{menu_id}",
    response_model=MenuApprovalResponse,
    summary="Approve or reject a mess menu",
)
async def approve_menu(
    menu_id: UUID = Path(..., description="Mess menu ID"),
    payload: MenuApprovalRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> MenuApprovalResponse:
    """
    Approve or reject a mess menu according to MenuApprovalRequest.

    The request typically contains approver info, decision, and notes.
    """
    service = MessMenuService(uow)
    try:
        return service.approve_menu(
            menu_id=menu_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/menus/{menu_id}/workflow",
    response_model=ApprovalWorkflow,
    summary="Get approval workflow for a mess menu",
)
async def get_menu_approval_workflow(
    menu_id: UUID = Path(..., description="Mess menu ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalWorkflow:
    """
    Retrieve the approval workflow/timeline for a given mess menu.
    """
    service = MessMenuService(uow)
    try:
        return service.get_approval_workflow(menu_id=menu_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=List[MenuApprovalResponse],
    summary="Bulk approve/reject mess menus",
)
async def bulk_approve_menus(
    payload: BulkApproval,
    uow: UnitOfWork = Depends(get_uow),
) -> List[MenuApprovalResponse]:
    """
    Bulk approval or rejection of multiple mess menus in one request.
    """
    service = MessMenuService(uow)
    try:
        return service.bulk_approve(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)