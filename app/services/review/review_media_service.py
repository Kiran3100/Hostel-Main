"""
Review Media Service

Enhanced media management with validation, processing tracking,
and comprehensive error handling.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.review import ReviewMediaRepository
from app.schemas.review_media import ReviewMedia
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    DatabaseException,
    BusinessLogicException,
)
from app.core.cache import cache_result, invalidate_cache
from app.core.metrics import track_performance

logger = logging.getLogger(__name__)


class ReviewMediaService:
    """
    High-level service for review media management.

    Features:
    - Media attachment with validation
    - Processing status tracking
    - Media type validation
    - Comprehensive error handling
    """

    # Valid media types
    VALID_MEDIA_TYPES = {'image', 'video'}
    
    # Maximum media per review
    MAX_MEDIA_PER_REVIEW = 10

    def __init__(self, media_repo: ReviewMediaRepository) -> None:
        """
        Initialize ReviewMediaService.

        Args:
            media_repo: Repository for media operations

        Raises:
            ValueError: If repository is None
        """
        if not media_repo:
            raise ValueError("MediaRepository cannot be None")

        self.media_repo = media_repo
        logger.info("ReviewMediaService initialized")

    # -------------------------------------------------------------------------
    # Media operations
    # -------------------------------------------------------------------------

    @track_performance("media.list_for_review")
    @cache_result(ttl=300, key_prefix="review_media")
    def list_media_for_review(
        self,
        db: Session,
        review_id: UUID,
        include_deleted: bool = False,
    ) -> List[ReviewMedia]:
        """
        List all media for a review.

        Args:
            db: Database session
            review_id: UUID of review
            include_deleted: Whether to include soft-deleted media

        Returns:
            List of ReviewMedia objects

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(
                f"Listing media for review {review_id}, "
                f"include_deleted={include_deleted}"
            )

            objs = self.media_repo.get_by_review_id(
                db, review_id, include_deleted=include_deleted
            )

            media_list = [ReviewMedia.model_validate(o) for o in objs]

            logger.info(f"Retrieved {len(media_list)} media items for review {review_id}")

            return media_list

        except SQLAlchemyError as e:
            logger.error(f"Database error listing media: {str(e)}")
            raise DatabaseException("Failed to list review media") from e

    @track_performance("media.attach")
    @invalidate_cache(patterns=["review_media:*", "review_detail:*"])
    def attach_media(
        self,
        db: Session,
        review_id: UUID,
        file_upload_id: UUID,
        media_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReviewMedia:
        """
        Register a media file for a review.

        File storage should already have happened via file_management service.

        Args:
            db: Database session
            review_id: UUID of review
            file_upload_id: UUID of uploaded file
            media_type: Type of media ('image' or 'video')
            metadata: Optional metadata dictionary

        Returns:
            Created ReviewMedia object

        Raises:
            ValidationException: If media type is invalid or limit exceeded
            NotFoundException: If review or file not found
            DatabaseException: If database operation fails
        """
        try:
            logger.info(
                f"Attaching media to review {review_id}: "
                f"type={media_type}, file={file_upload_id}"
            )

            # Validate media type
            self._validate_media_type(media_type)

            # Check media limit
            self._check_media_limit(db, review_id)

            # Verify file exists
            self._verify_file_exists(db, file_upload_id)

            # Create media record
            obj = self.media_repo.create(
                db,
                data={
                    "review_id": review_id,
                    "file_upload_id": file_upload_id,
                    "media_type": media_type,
                    "metadata": metadata or {},
                    "processing_status": "pending",
                },
            )

            media = ReviewMedia.model_validate(obj)

            logger.info(f"Media attached successfully: id={media.id}")

            return media

        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error attaching media: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to attach media") from e

    @track_performance("media.mark_processed")
    @invalidate_cache(patterns=["review_media:*"])
    def mark_media_processed(
        self,
        db: Session,
        media_id: UUID,
        success: bool,
        error_message: Optional[str] = None,
        processed_url: Optional[str] = None,
    ) -> ReviewMedia:
        """
        Mark media processing as complete or failed.

        Args:
            db: Database session
            media_id: UUID of media
            success: Whether processing succeeded
            error_message: Optional error message if failed
            processed_url: Optional URL of processed media

        Returns:
            Updated ReviewMedia object

        Raises:
            NotFoundException: If media not found
            DatabaseException: If database operation fails
        """
        try:
            logger.info(
                f"Marking media {media_id} processed: success={success}"
            )

            media = self.media_repo.get_by_id(db, media_id)
            if not media:
                logger.warning(f"Media not found: {media_id}")
                raise NotFoundException(f"Media {media_id} not found")

            updated = self.media_repo.mark_processing_result(
                db=db,
                media=media,
                success=success,
                error_message=error_message,
                processed_url=processed_url,
            )

            result = ReviewMedia.model_validate(updated)

            logger.info(
                f"Media {media_id} marked as "
                f"{'processed' if success else 'failed'}"
            )

            return result

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error marking media processed: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to update media status") from e

    @track_performance("media.delete")
    @invalidate_cache(patterns=["review_media:*", "review_detail:*"])
    def delete_media(
        self,
        db: Session,
        media_id: UUID,
    ) -> None:
        """
        Soft-delete a media item.

        Args:
            db: Database session
            media_id: UUID of media to delete

        Raises:
            NotFoundException: If media not found
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Deleting media {media_id}")

            media = self.media_repo.get_by_id(db, media_id)
            if not media:
                raise NotFoundException(f"Media {media_id} not found")

            self.media_repo.soft_delete(db, media)

            logger.info(f"Media {media_id} deleted successfully")

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting media: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to delete media") from e

    @track_performance("media.get_processing_stats")
    def get_processing_stats(
        self,
        db: Session,
        review_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get media processing statistics.

        Args:
            db: Database session
            review_id: Optional review UUID to filter stats

        Returns:
            Dictionary with processing statistics

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching processing stats for review: {review_id}")

            stats = self.media_repo.get_processing_stats(db, review_id)

            logger.info(f"Processing stats retrieved: {stats}")

            return stats

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching processing stats: {str(e)}")
            raise DatabaseException("Failed to fetch processing stats") from e

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_media_type(self, media_type: str) -> None:
        """
        Validate media type.

        Args:
            media_type: Media type string

        Raises:
            ValidationException: If media type is invalid
        """
        if not media_type or media_type not in self.VALID_MEDIA_TYPES:
            raise ValidationException(
                f"Invalid media type. Must be one of: {', '.join(self.VALID_MEDIA_TYPES)}"
            )

    def _check_media_limit(self, db: Session, review_id: UUID) -> None:
        """
        Check if review has reached media limit.

        Args:
            db: Database session
            review_id: Review UUID

        Raises:
            BusinessLogicException: If limit exceeded
        """
        current_count = self.media_repo.count_media_for_review(db, review_id)

        if current_count >= self.MAX_MEDIA_PER_REVIEW:
            logger.warning(
                f"Media limit reached for review {review_id}: "
                f"{current_count}/{self.MAX_MEDIA_PER_REVIEW}"
            )
            raise BusinessLogicException(
                f"Maximum {self.MAX_MEDIA_PER_REVIEW} media items allowed per review"
            )

    def _verify_file_exists(self, db: Session, file_upload_id: UUID) -> None:
        """
        Verify uploaded file exists.

        Args:
            db: Database session
            file_upload_id: File upload UUID

        Raises:
            NotFoundException: If file not found
        """
        file_exists = self.media_repo.verify_file_upload(db, file_upload_id)

        if not file_exists:
            logger.warning(f"File upload not found: {file_upload_id}")
            raise NotFoundException(f"File upload {file_upload_id} not found")