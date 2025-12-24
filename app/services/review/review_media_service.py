"""
Review Media Service

Manages media attached to reviews (photos, videos).
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.review import ReviewMediaRepository
from app.schemas.review_media import (  # assuming schemas module alias
    ReviewMedia,  # if your schemas are in app.schemas.review, adjust import
)
from app.core.exceptions import ValidationException


class ReviewMediaService:
    """
    High-level service for review media.

    Responsibilities:
    - Attach/upload media for a review
    - List media for a review
    - Mark media processed/flagged
    """

    def __init__(self, media_repo: ReviewMediaRepository) -> None:
        self.media_repo = media_repo

    def list_media_for_review(
        self,
        db: Session,
        review_id: UUID,
    ) -> List[ReviewMedia]:
        objs = self.media_repo.get_by_review_id(db, review_id)
        return [ReviewMedia.model_validate(o) for o in objs]

    def attach_media(
        self,
        db: Session,
        review_id: UUID,
        file_upload_id: UUID,
        media_type: str,
    ) -> ReviewMedia:
        """
        Register a media file for a review.

        Actual file storage should already have happened via file_management.
        """
        obj = self.media_repo.create(
            db,
            data={
                "review_id": review_id,
                "file_upload_id": file_upload_id,
                "media_type": media_type,
            },
        )
        return ReviewMedia.model_validate(obj)

    def mark_media_processed(
        self,
        db: Session,
        media_id: UUID,
        success: bool,
        error_message: str | None = None,
    ) -> ReviewMedia:
        media = self.media_repo.get_by_id(db, media_id)
        if not media:
            raise ValidationException("Review media not found")

        updated = self.media_repo.mark_processing_result(
            db=db,
            media=media,
            success=success,
            error_message=error_message,
        )
        return ReviewMedia.model_validate(updated)