# --- File: C:\Hostel-Main\app\services\hostel\hostel_media_service.py ---
"""
Hostel media service for comprehensive media content management.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, BinaryIO
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hostel.hostel_media import HostelMedia, MediaCategory
from app.repositories.hostel.hostel_media_repository import (
    HostelMediaRepository,
    MediaCategoryRepository
)
from app.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    BusinessRuleViolationError,
    FileSizeLimitError
)
from app.services.base.base_service import BaseService
from app.utils.file_validators import validate_image, validate_video, validate_file_size
from app.utils.image_processor import resize_image, create_thumbnail, optimize_image


class HostelMediaService(BaseService):
    """
    Hostel media service for media content management.
    
    Handles media uploads, management, moderation, analytics,
    and storage optimization.
    """

    def __init__(self, session: AsyncSession, storage_service=None):
        super().__init__(session)
        self.media_repo = HostelMediaRepository(session)
        self.category_repo = MediaCategoryRepository(session)
        self.storage_service = storage_service  # Cloud storage service

    # ===== Media Upload and Management =====

    async def upload_media(
        self,
        hostel_id: UUID,
        file_data: BinaryIO,
        media_type: str,
        category: str,
        metadata: Dict[str, Any],
        uploaded_by: Optional[UUID] = None
    ) -> HostelMedia:
        """
        Upload media content with validation and processing.
        
        Args:
            hostel_id: Hostel UUID
            file_data: File binary data
            media_type: Media type (image, video, document)
            category: Media category
            metadata: Additional metadata
            uploaded_by: User ID uploading the media
            
        Returns:
            Created HostelMedia instance
            
        Raises:
            ValidationError: If validation fails
            FileSizeLimitError: If file size exceeds limit
        """
        # Validate media type
        valid_types = ['image', 'video', 'virtual_tour', 'document']
        if media_type not in valid_types:
            raise ValidationError(
                f"Invalid media type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Validate category
        category_obj = await self.category_repo.find_one_by_criteria({
            'name': category,
            'is_active': True
        })
        
        if not category_obj:
            raise ValidationError(f"Invalid or inactive category: {category}")
        
        # Check if media type is applicable for category
        if category_obj.applicable_media_types:
            if media_type not in category_obj.applicable_media_types:
                raise ValidationError(
                    f"Media type '{media_type}' not allowed for category '{category}'"
                )
        
        # Validate category limits
        limit_check = await self.category_repo.validate_category_limits(
            hostel_id,
            category
        )
        
        if not limit_check['can_add']:
            raise BusinessRuleViolationError(
                f"Category '{category}' has reached its limit of {limit_check['limit']} items"
            )
        
        # Validate file
        if media_type == 'image':
            validation_result = validate_image(file_data)
            if not validation_result['valid']:
                raise ValidationError(validation_result['error'])
        elif media_type == 'video':
            validation_result = validate_video(file_data)
            if not validation_result['valid']:
                raise ValidationError(validation_result['error'])
        
        # Check file size
        file_size = len(file_data.read())
        file_data.seek(0)  # Reset file pointer
        
        max_size = 10 * 1024 * 1024  # 10MB default
        if media_type == 'video':
            max_size = 100 * 1024 * 1024  # 100MB for videos
        
        if not validate_file_size(file_size, max_size):
            raise FileSizeLimitError(
                f"File size ({file_size} bytes) exceeds limit ({max_size} bytes)"
            )
        
        # Process image if needed
        processed_file = file_data
        thumbnail_url = None
        
        if media_type == 'image':
            # Optimize image
            processed_file = optimize_image(file_data)
            
            # Create thumbnail
            thumbnail_data = create_thumbnail(processed_file, size=(300, 300))
            
            # Upload thumbnail to storage
            if self.storage_service:
                thumbnail_url = await self.storage_service.upload(
                    thumbnail_data,
                    f"thumbnails/{hostel_id}/{metadata.get('title', 'thumb')}.jpg"
                )
        
        # Upload to storage
        file_url = None
        if self.storage_service:
            file_path = f"{media_type}s/{hostel_id}/{metadata.get('title', 'file')}"
            file_url = await self.storage_service.upload(processed_file, file_path)
        else:
            file_url = f"/media/temp/{hostel_id}/{metadata.get('title', 'file')}"
        
        # Create media record
        media_data = {
            'hostel_id': hostel_id,
            'media_type': media_type,
            'category': category,
            'file_url': file_url,
            'thumbnail_url': thumbnail_url,
            'file_size': file_size,
            'mime_type': metadata.get('mime_type'),
            'title': metadata.get('title'),
            'description': metadata.get('description'),
            'alt_text': metadata.get('alt_text'),
            'width': metadata.get('width'),
            'height': metadata.get('height'),
            'is_featured': metadata.get('is_featured', False),
            'is_cover': metadata.get('is_cover', False)
        }
        
        media = await self.media_repo.upload_media(
            hostel_id,
            media_data,
            uploaded_by
        )
        
        # Log event
        await self._log_event('media_uploaded', {
            'media_id': media.id,
            'hostel_id': hostel_id,
            'media_type': media_type,
            'category': category,
            'uploaded_by': uploaded_by
        })
        
        return media

    async def get_media_by_id(self, media_id: UUID) -> HostelMedia:
        """
        Get media by ID.
        
        Args:
            media_id: Media UUID
            
        Returns:
            HostelMedia instance
            
        Raises:
            ResourceNotFoundError: If media not found
        """
        media = await self.media_repo.get_by_id(media_id)
        if not media:
            raise ResourceNotFoundError(f"Media {media_id} not found")
        
        # Increment view count
        await self.media_repo.increment_views(media_id)
        
        return media

    async def update_media(
        self,
        media_id: UUID,
        update_data: Dict[str, Any],
        updated_by: Optional[UUID] = None
    ) -> HostelMedia:
        """
        Update media metadata.
        
        Args:
            media_id: Media UUID
            update_data: Fields to update
            updated_by: User ID performing update
            
        Returns:
            Updated HostelMedia instance
        """
        media = await self.get_media_by_id(media_id)
        
        # Validate updates
        if 'category' in update_data:
            category = await self.category_repo.find_one_by_criteria({
                'name': update_data['category'],
                'is_active': True
            })
            if not category:
                raise ValidationError(f"Invalid category: {update_data['category']}")
        
        # Update media
        updated_media = await self.media_repo.update(media_id, update_data)
        
        # Log event
        await self._log_event('media_updated', {
            'media_id': media_id,
            'updated_fields': list(update_data.keys()),
            'updated_by': updated_by
        })
        
        return updated_media

    async def delete_media(
        self,
        media_id: UUID,
        deleted_by: Optional[UUID] = None
    ) -> bool:
        """
        Delete media and associated files.
        
        Args:
            media_id: Media UUID
            deleted_by: User ID performing deletion
            
        Returns:
            True if successful
        """
        media = await self.get_media_by_id(media_id)
        
        # Delete from storage if available
        if self.storage_service:
            await self.storage_service.delete(media.file_url)
            if media.thumbnail_url:
                await self.storage_service.delete(media.thumbnail_url)
        
        # Delete from database
        await self.media_repo.delete(media_id)
        
        # Log event
        await self._log_event('media_deleted', {
            'media_id': media_id,
            'hostel_id': media.hostel_id,
            'deleted_by': deleted_by
        })
        
        return True

    # ===== Media Queries =====

    async def get_hostel_media(
        self,
        hostel_id: UUID,
        media_type: Optional[str] = None,
        category: Optional[str] = None,
        only_approved: bool = True
    ) -> List[HostelMedia]:
        """
        Get media for a hostel with filtering.
        
        Args:
            hostel_id: Hostel UUID
            media_type: Filter by media type
            category: Filter by category
            only_approved: Show only approved media
            
        Returns:
            List of media items
        """
        return await self.media_repo.find_by_hostel(
            hostel_id,
            media_type,
            category,
            include_inactive=not only_approved
        )

    async def get_gallery(
        self,
        hostel_id: UUID,
        limit: Optional[int] = None
    ) -> List[HostelMedia]:
        """
        Get gallery images for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            limit: Maximum number of images
            
        Returns:
            List of gallery images
        """
        return await self.media_repo.find_gallery_images(hostel_id, limit)

    async def get_featured_media(
        self,
        hostel_id: UUID,
        limit: int = 6
    ) -> List[HostelMedia]:
        """Get featured media for a hostel."""
        return await self.media_repo.find_featured_media(hostel_id, limit)

    async def get_cover_image(self, hostel_id: UUID) -> Optional[HostelMedia]:
        """
        Get cover/primary image for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Cover image or None
        """
        covers = await self.media_repo.find_cover_images(hostel_id)
        return covers[0] if covers else None

    # ===== Media Organization =====

    async def set_as_cover(
        self,
        media_id: UUID,
        set_by: Optional[UUID] = None
    ) -> HostelMedia:
        """
        Set media as cover image.
        
        Args:
            media_id: Media UUID
            set_by: User ID setting cover
            
        Returns:
            Updated HostelMedia instance
        """
        media = await self.media_repo.set_as_cover(media_id)
        
        # Log event
        await self._log_event('cover_image_set', {
            'media_id': media_id,
            'hostel_id': media.hostel_id,
            'set_by': set_by
        })
        
        return media

    async def reorder_media(
        self,
        hostel_id: UUID,
        category: str,
        media_order: List[UUID]
    ) -> List[HostelMedia]:
        """
        Reorder media within a category.
        
        Args:
            hostel_id: Hostel UUID
            category: Media category
            media_order: Ordered list of media UUIDs
            
        Returns:
            Reordered media list
        """
        return await self.media_repo.reorder_media(
            hostel_id,
            category,
            media_order
        )

    async def bulk_delete(
        self,
        media_ids: List[UUID],
        deleted_by: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Bulk delete multiple media items.
        
        Args:
            media_ids: List of media UUIDs
            deleted_by: User ID performing deletion
            
        Returns:
            Deletion summary
        """
        # Get media items for storage cleanup
        media_items = await self.media_repo.find_by_ids(media_ids)
        
        # Delete from storage
        if self.storage_service:
            for media in media_items:
                try:
                    await self.storage_service.delete(media.file_url)
                    if media.thumbnail_url:
                        await self.storage_service.delete(media.thumbnail_url)
                except Exception as e:
                    # Log but continue
                    await self._log_event('storage_delete_failed', {
                        'media_id': media.id,
                        'error': str(e)
                    })
        
        # Bulk delete from database
        deleted_count = await self.media_repo.bulk_delete_media(media_ids)
        
        return {
            'requested': len(media_ids),
            'deleted': deleted_count,
            'deleted_by': deleted_by
        }

    # ===== Moderation =====

    async def approve_media(
        self,
        media_id: UUID,
        approved_by: UUID
    ) -> HostelMedia:
        """
        Approve media for public display.
        
        Args:
            media_id: Media UUID
            approved_by: User ID approving the media
            
        Returns:
            Approved HostelMedia instance
        """
        media = await self.media_repo.approve_media(
            media_id,
            approved_by,
            datetime.utcnow()
        )
        
        # Log event
        await self._log_event('media_approved', {
            'media_id': media_id,
            'approved_by': approved_by
        })
        
        return media

    async def get_pending_approval(
        self,
        hostel_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[HostelMedia]:
        """
        Get media pending approval.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Maximum results
            
        Returns:
            List of media pending approval
        """
        return await self.media_repo.find_pending_approval(hostel_id, limit)

    async def bulk_approve(
        self,
        media_ids: List[UUID],
        approved_by: UUID
    ) -> List[HostelMedia]:
        """
        Bulk approve multiple media items.
        
        Args:
            media_ids: List of media UUIDs
            approved_by: User ID approving the media
            
        Returns:
            List of approved media
        """
        return await self.media_repo.bulk_approve_media(media_ids, approved_by)

    # ===== Analytics =====

    async def get_media_performance(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get media performance analytics.
        
        Args:
            hostel_id: Hostel UUID
            period_days: Analysis period in days
            
        Returns:
            Performance analytics
        """
        return await self.media_repo.get_media_performance(hostel_id, period_days)

    async def get_popular_media(
        self,
        hostel_id: UUID,
        limit: int = 10,
        metric: str = "view_count"
    ) -> List[HostelMedia]:
        """
        Get most popular media by specified metric.
        
        Args:
            hostel_id: Hostel UUID
            limit: Maximum results
            metric: Metric to sort by (view_count, click_count)
            
        Returns:
            List of popular media
        """
        valid_metrics = ['view_count', 'click_count']
        if metric not in valid_metrics:
            raise ValidationError(
                f"Invalid metric. Must be one of: {', '.join(valid_metrics)}"
            )
        
        return await self.media_repo.get_popular_media(hostel_id, limit, metric)

    async def get_storage_usage(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get storage usage statistics.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Storage usage statistics
        """
        return await self.media_repo.get_storage_usage(hostel_id)

    async def track_media_click(
        self,
        media_id: UUID
    ) -> None:
        """
        Track media click for analytics.
        
        Args:
            media_id: Media UUID
        """
        await self.media_repo.increment_clicks(media_id)

    # ===== Search =====

    async def search_media(
        self,
        hostel_id: UUID,
        search_query: str,
        media_type: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[HostelMedia]:
        """
        Search media with text query.
        
        Args:
            hostel_id: Hostel UUID
            search_query: Search text
            media_type: Optional media type filter
            category: Optional category filter
            
        Returns:
            List of matching media
        """
        return await self.media_repo.search_media(
            hostel_id,
            search_query,
            media_type,
            category
        )

    # ===== Category Management =====

    async def get_active_categories(self) -> List[MediaCategory]:
        """Get all active media categories."""
        return await self.category_repo.find_active_categories()

    async def get_categories_for_type(
        self,
        media_type: str
    ) -> List[MediaCategory]:
        """Get categories applicable to a media type."""
        return await self.category_repo.find_categories_for_media_type(media_type)

    # ===== Helper Methods =====

    async def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log service events for audit and analytics."""
        pass