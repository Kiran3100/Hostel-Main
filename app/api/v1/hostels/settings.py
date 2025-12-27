from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_admin import HostelSettings
from app.services.hostel.hostel_settings_service import HostelSettingsService

router = APIRouter(prefix="/hostels/settings", tags=["hostels:settings"])


def get_settings_service(db: Session = Depends(deps.get_db)) -> HostelSettingsService:
    return HostelSettingsService(db=db)


@router.get(
    "/{hostel_id}",
    response_model=HostelSettings,
    summary="Get hostel settings",
)
def get_settings(
    hostel_id: str,
    _admin=Depends(deps.get_admin_user),
    service: HostelSettingsService = Depends(get_settings_service),
) -> Any:
    return service.get_settings(hostel_id)


@router.put(
    "/{hostel_id}",
    response_model=HostelSettings,
    summary="Update hostel settings",
)
def update_settings(
    hostel_id: str,
    payload: HostelSettings,
    _admin=Depends(deps.get_admin_user),
    service: HostelSettingsService = Depends(get_settings_service),
) -> Any:
    return service.update_settings(hostel_id, payload)