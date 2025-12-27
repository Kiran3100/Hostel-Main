from typing import Any, List

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.api import deps
# Assuming schemas exist in app.schemas.hostel or similar
from app.schemas.hostel.hostel_base import HostelAmenity  # adjust schema import
from app.services.hostel.hostel_amenity_service import HostelAmenityService

router = APIRouter(prefix="/hostels/amenities", tags=["hostels:amenities"])


def get_amenity_service(db: Session = Depends(deps.get_db)) -> HostelAmenityService:
    return HostelAmenityService(db=db)


@router.post(
    "",
    response_model=HostelAmenity,  # Replace with appropriate schema
    status_code=status.HTTP_201_CREATED,
    summary="Add amenity to hostel",
)
def create_amenity(
    payload: Any,  # Replace with AmenityCreate schema
    _admin=Depends(deps.get_admin_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> Any:
    return service.create_amenity(payload)


@router.get(
    "",
    response_model=List[HostelAmenity],  # Replace with appropriate schema
    summary="List amenities",
)
def list_amenities(
    hostel_id: str = Query(...),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> Any:
    return service.list_amenities(hostel_id=hostel_id)


@router.put(
    "/{amenity_id}",
    summary="Update amenity",
)
def update_amenity(
    amenity_id: str,
    payload: Any,  # Replace with AmenityUpdate schema
    _admin=Depends(deps.get_admin_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> Any:
    return service.update_amenity(amenity_id, payload)


@router.delete(
    "/{amenity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete amenity",
)
def delete_amenity(
    amenity_id: str,
    _admin=Depends(deps.get_admin_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> Any:
    service.delete_amenity(amenity_id)
    return None


@router.post(
    "/{amenity_id}/book",
    summary="Book an amenity",
)
def book_amenity(
    amenity_id: str,
    payload: Any,  # Replace with AmenityBookingRequest schema
    current_user=Depends(deps.get_current_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> Any:
    return service.book_amenity(amenity_id, payload, user_id=current_user.id)