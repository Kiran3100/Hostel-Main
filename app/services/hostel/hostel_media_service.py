# --- File: C:\Hostel-Main\app\services\hostel\hostel_media_service.py ---
"""
Hostel media service (images/videos/virtual tours/documents).

Manages all media assets associated with hostels including upload tracking,
categorization, metadata management, and storage integration.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
import logging
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.hostel import HostelMediaRepository
from app.models.hostel.hostel_media import (
    HostelMedia as HostelMediaModel,
    MediaCategory as MediaCategoryModel
)
from app.schemas.hostel.hostel_media import (
    MediaCreate,
    MediaUpdate,
)
from app.services.hostel.constants import (
    ERROR_MEDIA_NOT_FOUND,
    SUCCESS_MEDIA_ADDED,
    SUCCESS_MEDIA_UPDATED,
    SUCCESS_MEDIA_DELETED,
)

logger = logging.getLogger(__name__)


class HostelMediaService(BaseService[HostelMediaModel, HostelMediaRepository]):
    """
    Manage hostel media assets, categories, and metadata.
    
    Provides functionality for:
    - Media upload and management
    - Categorization and tagging
    - Metadata extraction and storage
    - Integration with storage services
    - Media validation and optimization
    """

    # Supported media types
    SUPPORTED_IMAGE_TYPES = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    SUPPORTED_VIDEO_TYPES = {'mp4', 'webm', 'mov', 'avi'}
    SUPPORTED_DOCUMENT_TYPES = {'pdf', 'doc', 'docx', 'txt'}
    
    # Size limits (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
    MAX_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5 MB

    def __init__(self, repository: HostelMediaRepository, db_session: Session):
        """
        Initialize hostel media service.
        
        Args:
            repository: Hostel media repository instance
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self._media_cache: Dict[UUID, HostelMediaModel] = {}

    # =========================================================================
    # Media CRUD Operations
    # =========================================================================

    def add_media(
        self,
        hostel_id: UUID,
        request: MediaCreate,
        uploaded_by: Optional[UUID] = None,
        validate_file: bool = True,
    ) -> ServiceResult[HostelMediaModel]:
        """
        Add new media to a hostel with validation.
        
        Args:
            hostel_id: UUID of the hostel
            request: Media creation request
            uploaded_by: UUID of the user uploading the media
            validate_file: Whether to validate file type and size
            
        Returns:
            ServiceResult containing created media or error
        """
        try:
            logger.info(
                f"Adding media to hostel {hostel_id}: "
                f"type={request.media_type}, category={request.category}"
            )
            
            # Validate media
            if validate_file:
                validation_error = self._validate_media(request)
                if validation_error:
                    return validation_error
            
            # Create media record
            media = self.repository.add_media(hostel_id, request)
            self.db.flush()
            
            # Extract and store metadata if available
            if hasattr(request, 'file_path') and request.file_path:
                metadata = self._extract_metadata(request.file_path, request.media_type)
                if metadata:
                    media.metadata = metadata
            
            self.db.commit()
            
            logger.info(f"Media added successfully: {media.id}")
            return ServiceResult.success(media, message=SUCCESS_MEDIA_ADDED)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error adding media: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Media with this URL already exists",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "add hostel media", hostel_id)

    def update_media(
        self,
        media_id: UUID,
        request: MediaUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelMediaModel]:
        """
        Update existing media information.
        
        Args:
            media_id: UUID of the media to update
            request: Update request with fields to modify
            updated_by: UUID of the user performing the update
            
        Returns:
            ServiceResult containing updated media or error
        """
        try:
            logger.info(f"Updating media: {media_id}")
            
            # Check existence
            existing = self.repository.get_by_id(media_id)
            if not existing:
                return self._not_found_error(ERROR_MEDIA_NOT_FOUND, media_id)
            
            # Validate update
            validation_error = self._validate_media_update(request, existing)
            if validation_error:
                return validation_error
            
            # Perform update
            media = self.repository.update_media(media_id, request)
            self.db.flush()
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(media_id)
            
            logger.info(f"Media updated successfully: {media_id}")
            return ServiceResult.success(media, message=SUCCESS_MEDIA_UPDATED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update hostel media", media_id)

    def delete_media(
        self,
        media_id: UUID,
        delete_from_storage: bool = False,
        deleted_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Delete media with optional storage cleanup.
        
        Args:
            media_id: UUID of the media to delete
            delete_from_storage: Whether to delete the file from storage
            deleted_by: UUID of the user performing the deletion
            
        Returns:
            ServiceResult containing success status or error
        """
        try:
            logger.info(
                f"Deleting media: {media_id} "
                f"(delete_from_storage={delete_from_storage})"
            )
            
            # Get media details before deletion
            media = self.repository.get_by_id(media_id)
            if not media:
                return self._not_found_error(ERROR_MEDIA_NOT_FOUND, media_id)
            
            # Delete from storage if requested
            if delete_from_storage and media.url:
                deletion_success = self._delete_from_storage(media.url)
                if not deletion_success:
                    logger.warning(
                        f"Failed to delete media from storage: {media.url}"
                    )
            
            # Delete from database
            success = self.repository.delete_media(
                media_id,
                delete_from_storage=False  # Already handled above
            )
            self.db.flush()
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(media_id)
            
            logger.info(f"Media deleted successfully: {media_id}")
            return ServiceResult.success(success, message=SUCCESS_MEDIA_DELETED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete hostel media", media_id)

    def list_media(
        self,
        hostel_id: UUID,
        category: Optional[str] = None,
        media_type: Optional[str] = None,
        is_primary: Optional[bool] = None,
        tags: Optional[List[str]] = None,
    ) -> ServiceResult[List[HostelMediaModel]]:
        """
        List media for a hostel with advanced filtering.
        
        Args:
            hostel_id: UUID of the hostel
            category: Filter by media category
            media_type: Filter by media type (image, video, document)
            is_primary: Filter by primary status
            tags: Filter by tags (media must have all specified tags)
            
        Returns:
            ServiceResult containing list of media with metadata
        """
        try:
            logger.info(
                f"Listing media for hostel {hostel_id}: "
                f"category={category}, type={media_type}, "
                f"primary={is_primary}, tags={tags}"
            )
            
            # Fetch media
            items = self.repository.list_media(
                hostel_id,
                category=category,
                media_type=media_type,
                is_primary=is_primary,
                tags=tags
            )
            
            # Prepare metadata
            metadata = {
                "count": len(items),
                "hostel_id": str(hostel_id),
                "filters": {
                    "category": category,
                    "media_type": media_type,
                    "is_primary": is_primary,
                    "tags": tags,
                }
            }
            
            # Group by category for convenience
            grouped = {}
            for item in items:
                cat = item.category or "uncategorized"
                if cat not in grouped:
                    grouped[cat] = []
                grouped[cat].append(item)
            
            metadata["grouped_count"] = {k: len(v) for k, v in grouped.items()}
            
            return ServiceResult.success(items, metadata=metadata)
            
        except Exception as e:
            return self._handle_exception(e, "list hostel media", hostel_id)

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def bulk_add_media(
        self,
        hostel_id: UUID,
        media_list: List[MediaCreate],
        uploaded_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Add multiple media items in a single transaction.
        
        Args:
            hostel_id: UUID of the hostel
            media_list: List of media creation requests
            uploaded_by: UUID of the user uploading the media
            
        Returns:
            ServiceResult containing results summary
        """
        try:
            logger.info(f"Bulk adding {len(media_list)} media items to hostel {hostel_id}")
            
            added_media = []
            failed_items = []
            
            for idx, media_request in enumerate(media_list):
                try:
                    # Validate each item
                    validation_error = self._validate_media(media_request)
                    if validation_error:
                        failed_items.append({
                            "index": idx,
                            "reason": validation_error.error.message
                        })
                        continue
                    
                    # Add media
                    media = self.repository.add_media(hostel_id, media_request)
                    added_media.append(media)
                    
                except Exception as e:
                    logger.error(f"Failed to add media at index {idx}: {str(e)}")
                    failed_items.append({
                        "index": idx,
                        "reason": str(e)
                    })
            
            self.db.commit()
            
            result = {
                "total_requested": len(media_list),
                "successfully_added": len(added_media),
                "failed": len(failed_items),
                "added_media_ids": [str(m.id) for m in added_media],
                "failed_items": failed_items
            }
            
            logger.info(
                f"Bulk media upload completed: "
                f"{len(added_media)}/{len(media_list)} successful"
            )
            
            return ServiceResult.success(
                result,
                message=f"Added {len(added_media)} media items"
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "bulk add hostel media", hostel_id)

    def set_primary_media(
        self,
        hostel_id: UUID,
        media_id: UUID,
        category: Optional[str] = None,
    ) -> ServiceResult[HostelMediaModel]:
        """
        Set a media item as primary for a hostel or category.
        
        Args:
            hostel_id: UUID of the hostel
            media_id: UUID of the media to set as primary
            category: Optional category to set primary for
            
        Returns:
            ServiceResult containing updated media or error
        """
        try:
            logger.info(
                f"Setting primary media {media_id} for hostel {hostel_id}, "
                f"category={category}"
            )
            
            # Verify media belongs to hostel
            media = self.repository.get_by_id(media_id)
            if not media or media.hostel_id != hostel_id:
                return self._not_found_error(ERROR_MEDIA_NOT_FOUND, media_id)
            
            # Clear existing primary status
            self.repository.clear_primary_media(hostel_id, category)
            
            # Set new primary
            media.is_primary = True
            self.db.flush()
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(media_id)
            
            logger.info(f"Primary media set: {media_id}")
            return ServiceResult.success(
                media,
                message="Primary media updated successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "set primary media", media_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_media(
        self,
        request: MediaCreate
    ) -> Optional[ServiceResult[HostelMediaModel]]:
        """
        Validate media creation request.
        
        Args:
            request: Media creation request
            
        Returns:
            ServiceResult with error if validation fails, None otherwise
        """
        # Validate URL
        if not request.url or len(request.url.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Media URL is required",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        # Validate media type
        if hasattr(request, 'media_type') and request.media_type:
            file_ext = Path(request.url).suffix.lower().lstrip('.')
            
            if request.media_type == 'image':
                if file_ext not in self.SUPPORTED_IMAGE_TYPES:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Unsupported image type: {file_ext}",
                            severity=ErrorSeverity.ERROR,
                            details={"supported": list(self.SUPPORTED_IMAGE_TYPES)}
                        )
                    )
            elif request.media_type == 'video':
                if file_ext not in self.SUPPORTED_VIDEO_TYPES:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Unsupported video type: {file_ext}",
                            severity=ErrorSeverity.ERROR,
                            details={"supported": list(self.SUPPORTED_VIDEO_TYPES)}
                        )
                    )
            elif request.media_type == 'document':
                if file_ext not in self.SUPPORTED_DOCUMENT_TYPES:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Unsupported document type: {file_ext}",
                            severity=ErrorSeverity.ERROR,
                            details={"supported": list(self.SUPPORTED_DOCUMENT_TYPES)}
                        )
                    )
        
        # Validate file size if provided
        if hasattr(request, 'file_size') and request.file_size:
            max_size = self._get_max_size(request.media_type)
            if request.file_size > max_size:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"File size exceeds maximum allowed ({max_size} bytes)",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "file_size": request.file_size,
                            "max_size": max_size
                        }
                    )
                )
        
        return None

    def _validate_media_update(
        self,
        request: MediaUpdate,
        existing: HostelMediaModel
    ) -> Optional[ServiceResult[HostelMediaModel]]:
        """
        Validate media update request.
        
        Args:
            request: Media update request
            existing: Existing media model
            
        Returns:
            ServiceResult with error if validation fails, None otherwise
        """
        # Add custom validation logic here
        if request.url is not None and len(request.url.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Media URL cannot be empty",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        return None

    def _extract_metadata(
        self,
        file_path: str,
        media_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from media file.
        
        Args:
            file_path: Path to the media file
            media_type: Type of media (image, video, document)
            
        Returns:
            Dictionary of metadata or None
        """
        try:
            # This is a placeholder for actual metadata extraction
            # In a real implementation, you would use libraries like:
            # - PIL/Pillow for images
            # - ffmpeg-python for videos
            # - PyPDF2 for documents
            
            metadata = {
                "extracted_at": datetime.utcnow().isoformat(),
                "file_path": file_path,
            }
            
            # Add type-specific metadata extraction here
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {str(e)}")
            return None

    def _delete_from_storage(self, url: str) -> bool:
        """
        Delete media file from storage service.
        
        Args:
            url: URL of the media to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # This is a placeholder for actual storage deletion
            # In a real implementation, you would integrate with:
            # - AWS S3
            # - Google Cloud Storage
            # - Azure Blob Storage
            # - Local file system
            
            logger.info(f"Deleting media from storage: {url}")
            
            # Implement actual deletion logic here
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting from storage: {str(e)}")
            return False

    def _get_max_size(self, media_type: str) -> int:
        """
        Get maximum allowed file size for media type.
        
        Args:
            media_type: Type of media
            
        Returns:
            Maximum size in bytes
        """
        size_map = {
            'image': self.MAX_IMAGE_SIZE,
            'video': self.MAX_VIDEO_SIZE,
            'document': self.MAX_DOCUMENT_SIZE,
        }
        return size_map.get(media_type, self.MAX_DOCUMENT_SIZE)

    def _not_found_error(
        self,
        message: str,
        entity_id: UUID
    ) -> ServiceResult[HostelMediaModel]:
        """
        Create a standardized not found error response.
        
        Args:
            message: Error message
            entity_id: ID of the entity not found
            
        Returns:
            ServiceResult with not found error
        """
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.NOT_FOUND,
                message=message,
                severity=ErrorSeverity.ERROR,
                details={"entity_id": str(entity_id)}
            )
        )

    def _invalidate_cache(self, media_id: UUID) -> None:
        """
        Clear cached data for specific media.
        
        Args:
            media_id: UUID of the media
        """
        if media_id in self._media_cache:
            del self._media_cache[media_id]
            logger.debug(f"Media cache invalidated: {media_id}")

    def clear_cache(self) -> None:
        """Clear all cached media data."""
        self._media_cache.clear()
        logger.info("All media cache cleared")