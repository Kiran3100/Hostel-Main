from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_public import PublicHostelProfile
from app.services.hostel.hostel_service import HostelService

router = APIRouter(prefix="/hostels/public", tags=["hostels:public"])


def get_hostel_service(db: Session = Depends(deps.get_db)) -> HostelService:
    return HostelService(db=db)


@router.get(
    "/{slug}",
    response_model=PublicHostelProfile,
    summary="Get public hostel profile by slug",
)
def get_public_hostel(
    slug: str,
    service: HostelService = Depends(get_hostel_service),
) -> Any:
    # Assuming service has a get_by_slug method or similar logic
    # This might reuse get_detail internally but return public schema
    hostel = service.get_detail(slug)  
    if not hostel:
        raise HTTPException(status_code=404, detail="Hostel not found")
    return hostel