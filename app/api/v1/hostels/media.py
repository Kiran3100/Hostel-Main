from typing import Any, List

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.api import deps
# Using generic Any or Dict for schema placeholders; replace with HostelMediaUpdate/Response schemas
from app.services.hostel.hostel_media_service import HostelMediaService

router = APIRouter(prefix="/hostels/media", tags=["hostels:media"])


def get_media_service(db: Session = Depends(deps.get_db)) -> HostelMediaService:
    return HostelMediaService(db=db)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Add media to hostel",
)
def add_media(
    hostel_id: str = Query(...),
    payload: Any,  # Replace with MediaAdd schema
    _admin=Depends(deps.get_admin_user),
    service: HostelMediaService = Depends(get_media_service),
) -> Any:
    return service.add_media(hostel_id, payload)


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete media",
)
def delete_media(
    media_id: str,
    _admin=Depends(deps.get_admin_user),
    service: HostelMediaService = Depends(get_media_service),
) -> Any:
    service.delete_media(media_id)
    return None


@router.get(
    "",
    response_model=List[Any],  # Replace with MediaResponse schema
    summary="List hostel media",
)
def list_media(
    hostel_id: str = Query(...),
    service: HostelMediaService = Depends(get_media_service),
) -> Any:
    return service.list_media(hostel_id)