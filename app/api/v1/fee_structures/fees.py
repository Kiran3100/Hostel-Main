# api/v1/fee_structures/fees.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.fee_structure.fee_base import (
    FeeStructureCreate,
    FeeStructureUpdate,
)
from app.schemas.fee_structure.fee_response import (
    FeeStructureResponse,
    FeeStructureList,
    FeeDetail,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.fee_structure import FeeStructureService

router = APIRouter(prefix="/fees")


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


@router.get(
    "/",
    response_model=FeeStructureList,
    summary="List fee structures for a hostel",
)
async def list_fee_structures(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeeStructureList:
    """
    List all fee structures configured for a given hostel.
    """
    service = FeeStructureService(uow)
    try:
        return service.list_fee_structures(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/",
    response_model=FeeStructureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a fee structure",
)
async def create_fee_structure(
    payload: FeeStructureCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> FeeStructureResponse:
    """
    Create a new fee structure (per hostel and room type).

    Typically includes rent, security deposit, mess and utility configuration.
    """
    service = FeeStructureService(uow)
    try:
        return service.create_fee_structure(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{fee_id}",
    response_model=FeeStructureResponse,
    summary="Get fee structure details",
)
async def get_fee_structure(
    fee_id: UUID = Path(..., description="Fee structure ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeeStructureResponse:
    """
    Retrieve a single fee structure row.
    """
    service = FeeStructureService(uow)
    try:
        return service.get_fee_structure(fee_id=fee_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{fee_id}",
    response_model=FeeStructureResponse,
    summary="Update a fee structure",
)
async def update_fee_structure(
    fee_id: UUID = Path(..., description="Fee structure ID"),
    payload: FeeStructureUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> FeeStructureResponse:
    """
    Partially update a fee structure (amounts, mess, utilities, effective dates, etc.).
    """
    service = FeeStructureService(uow)
    try:
        return service.update_fee_structure(
            fee_id=fee_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{fee_id}/deactivate",
    response_model=FeeStructureResponse,
    summary="Deactivate a fee structure",
)
async def deactivate_fee_structure(
    fee_id: UUID = Path(..., description="Fee structure ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeeStructureResponse:
    """
    Mark a fee structure as inactive (effective_to, is_active=false), without deleting it.
    """
    service = FeeStructureService(uow)
    try:
        return service.deactivate_fee_structure(fee_id=fee_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{fee_id}/detail",
    response_model=FeeDetail,
    summary="Get fee detail (first-month and recurring totals)",
)
async def get_fee_detail(
    fee_id: UUID = Path(..., description="Fee structure ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeeDetail:
    """
    Get a derived view for a fee structure, including first-month and recurring totals.
    """
    service = FeeStructureService(uow)
    try:
        return service.get_fee_detail(fee_id=fee_id)
    except ServiceError as exc:
        raise _map_service_error(exc)