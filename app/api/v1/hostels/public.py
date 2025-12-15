from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.hostel.hostel_public import (
    PublicHostelCard,
    PublicHostelProfile,
    PublicHostelList,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.hostel_public import HostelIndexService, PublicHostelService

router = APIRouter(prefix="/public")


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
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/featured",
    response_model=PublicHostelList,
    summary="List featured hostels (public)",
)
async def list_featured_hostels(
    uow: UnitOfWork = Depends(get_uow),
) -> PublicHostelList:
    """
    Return a list of featured hostels for the public landing page.
    """
    service = HostelIndexService(uow)
    try:
        return service.list_featured()
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/newest",
    response_model=PublicHostelList,
    summary="List newest hostels (public)",
)
async def list_newest_hostels(
    uow: UnitOfWork = Depends(get_uow),
) -> PublicHostelList:
    """
    Return a list of newest hostels for the public landing page.
    """
    service = HostelIndexService(uow)
    try:
        return service.list_newest()
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{slug}",
    response_model=PublicHostelProfile,
    summary="Get public hostel profile by slug",
)
async def get_public_hostel_profile(
    slug: str = Path(..., description="Hostel slug"),
    uow: UnitOfWork = Depends(get_uow),
) -> PublicHostelProfile:
    """
    Retrieve a public-facing hostel profile by slug (for visitors).
    """
    service = PublicHostelService(uow)
    try:
        return service.get_public_profile(slug=slug)
    except ServiceError as exc:
        raise _map_service_error(exc)