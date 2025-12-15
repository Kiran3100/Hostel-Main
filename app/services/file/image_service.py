# app/services/file/image_service.py
from __future__ import annotations

from typing import Optional, List

from app.schemas.file import (
    ImageUploadInitRequest,
    ImageUploadInitResponse,
    ImageProcessingResult,
    ImageVariant,
    FileUploadInitRequest,
)
from app.services.file.file_service import FileService


class ImageService:
    """
    Image upload helper on top of the generic FileService.

    Responsibilities:
    - Validate & initialize image uploads using ImageUploadInitRequest
    - Delegate actual upload handling to FileService
    - Optionally assemble ImageProcessingResult for post-processing flows
    """

    def __init__(self, file_service: FileService) -> None:
        self._file_service = file_service

    # ------------------------------------------------------------------ #
    # Upload init
    # ------------------------------------------------------------------ #
    def init_image_upload(
        self,
        req: ImageUploadInitRequest,
        *,
        folder: Optional[str] = None,
        is_public: bool = True,
    ) -> ImageUploadInitResponse:
        """
        Initialize an image upload by mapping to FileUploadInitRequest.
        """
        # Simple folder heuristic if not given
        effective_folder = folder
        if not effective_folder:
            if req.hostel_id:
                effective_folder = f"hostels/{req.hostel_id}/images"
            else:
                effective_folder = "images"

        file_req = FileUploadInitRequest(
            filename=req.filename,
            content_type=req.content_type,
            size_bytes=req.size_bytes,
            folder=effective_folder,
            uploaded_by_user_id=req.uploaded_by_user_id,
            hostel_id=req.hostel_id,
            category="image",
            tags=[req.usage],
            is_public=is_public,
        )
        base_resp = self._file_service.init_upload(file_req)
        # Reuse same fields; ImageUploadInitResponse extends FileUploadInitResponse
        return ImageUploadInitResponse.model_validate(base_resp.model_dump())

    # ------------------------------------------------------------------ #
    # Post-processing result assembly
    # ------------------------------------------------------------------ #
    def build_processing_result(
        self,
        *,
        storage_key: str,
        original_url: str,
        variants: List[ImageVariant],
    ) -> ImageProcessingResult:
        """
        Convenience helper to create ImageProcessingResult after an image
        processing pipeline has generated variants.

        This does not persist anything by itself; persistence is left
        to the caller if needed.
        """
        return ImageProcessingResult(
            storage_key=storage_key,
            original_url=original_url,
            variants=variants,
        )