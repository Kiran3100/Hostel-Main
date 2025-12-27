from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.fee_structure import (
    FeeStructureCreate,
    FeeStructureUpdate,
    FeeStructureResponse,
    FeeStructureList,
    FeeDetail,
    ChargeComponent,  # Assuming a schema for charge component exists
    DiscountConfiguration,  # Assuming a schema for discount exists
)
from app.services.fee_structure.fee_structure_service import FeeStructureService
from app.services.fee_structure.charge_component_service import ChargeComponentService

router = APIRouter(prefix="/fee-structures", tags=["fee-structures"])


def get_fee_service(db: Session = Depends(deps.get_db)) -> FeeStructureService:
    return FeeStructureService(db=db)


def get_charge_service(db: Session = Depends(deps.get_db)) -> ChargeComponentService:
    return ChargeComponentService(db=db)


# ---------------------------------------------------------------------------
# Fee Structure CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=FeeStructureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create fee structure",
)
def create_fee_structure(
    payload: FeeStructureCreate,
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    return service.create_structure(payload, creator_id=_admin.id)


@router.get(
    "/{structure_id}",
    response_model=FeeDetail,
    summary="Get fee structure details",
)
def get_fee_structure(
    structure_id: str,
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    structure = service.get_structure_by_id(structure_id)
    if not structure:
        raise HTTPException(status_code=404, detail="Fee structure not found")
    return structure


@router.put(
    "/{structure_id}",
    response_model=FeeStructureResponse,
    summary="Update fee structure",
)
def update_fee_structure(
    structure_id: str,
    payload: FeeStructureUpdate,
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    return service.update_structure(structure_id, payload, updater_id=_admin.id)


@router.delete(
    "/{structure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete fee structure",
)
def delete_fee_structure(
    structure_id: str,
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    service.delete_structure(structure_id)
    return None


@router.get(
    "",
    response_model=FeeStructureList,
    summary="List fee structures",
)
def list_fee_structures(
    hostel_id: str = Query(..., description="Hostel ID"),
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    return service.list_structures(hostel_id=hostel_id, pagination=pagination)


# ---------------------------------------------------------------------------
# Charge Components & Discounts
# ---------------------------------------------------------------------------


@router.get(
    "/{structure_id}/components",
    response_model=List[ChargeComponent],
    summary="List charge components for a structure",
)
def list_components(
    structure_id: str,
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    return service.list_components(structure_id=structure_id)


@router.post(
    "/{structure_id}/components",
    response_model=ChargeComponent,
    status_code=status.HTTP_201_CREATED,
    summary="Add charge component to structure",
)
def add_component(
    structure_id: str,
    payload: ChargeComponent,  # Adjust schema if needed (e.g. ComponentCreate)
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    return service.create_component(structure_id=structure_id, payload=payload)


@router.get(
    "/discounts",
    response_model=List[DiscountConfiguration],
    summary="List discount configurations",
)
def list_discounts(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    return service.list_discounts(hostel_id=hostel_id)