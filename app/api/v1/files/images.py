from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.file_management import (
    ImageUploadInitRequest,
    ImageUploadInitResponse,
    ImageProcessingResult,
    ImageVariant,
)
from app.services.file_management.image_processing_service import ImageProcessingService

router = APIRouter(prefix="/images", tags=["files:images"])


def get_image_service(db: Session = Depends(deps.get_db)) -> ImageProcessingService:
    return ImageProcessingService(db=db)


@router.post(
    "/init",
    response_model=ImageUploadInitResponse,
    summary="Initialize image upload with processing options",
)
def init_image_upload(
    payload: ImageUploadInitRequest,
    current_user=Depends(deps.get_current_user),
    service: ImageProcessingService = Depends(get_image_service),
) -> Any:
    return service.init_image_upload(payload, user_id=current_user.id)


@router.post(
    "/{file_id}/process",
    response_model=ImageProcessingResult,
    summary="Trigger image processing (resize/optimize)",
)
def process_image(
    file_id: str,
    # Optional specific processing options if overriding defaults
    current_user=Depends(deps.get_current_user),
    service: ImageProcessingService = Depends(get_image_service),
) -> Any:
    return service.process_image(file_id, user_id=current_user.id)


@router.get(
    "/{file_id}/variants",
    response_model=List[ImageVariant],
    summary="List generated variants for an image",
)
def list_image_variants(
    file_id: str,
    current_user=Depends(deps.get_current_user),
    service: ImageProcessingService = Depends(get_image_service),
) -> Any:
    return service.list_variants(file_id)