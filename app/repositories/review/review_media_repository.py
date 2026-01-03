"""
Review Media Repository - Media attachment management.

Implements media upload, processing, moderation, and analytics.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.review.review_media import (
    ReviewMedia,
    ReviewMediaProcessing,
)
from app.repositories.base import BaseRepository, PaginatedResult


class ReviewMediaRepository(BaseRepository[ReviewMedia]):
    """
    Repository for review media operations.
    
    Manages media uploads, processing, moderation, and analytics.
    """
    
    def __init__(self, session: Session):
        """
        Initialize review media repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ReviewMedia, session)
    
    # ==================== Media CRUD Operations ====================
    
    def create_media(
        self,
        review_id: UUID,
        media_type: str,
        original_url: str,
        file_size_bytes: int,
        mime_type: str,
        original_filename: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration_seconds: Optional[Decimal] = None,
        caption: Optional[str] = None,
        alt_text: Optional[str] = None,
        display_order: int = 0,
        uploaded_by: Optional[UUID] = None,
        upload_ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReviewMedia:
        """
        Create media attachment for review.
        
        Args:
            review_id: Review ID
            media_type: Type of media (photo/video)
            original_url: URL to original file
            file_size_bytes: File size in bytes
            mime_type: MIME type
            original_filename: Original filename
            width: Image width (for photos)
            height: Image height (for photos)
            duration_seconds: Video duration (for videos)
            caption: Media caption
            alt_text: Alternative text for accessibility
            display_order: Display order in review
            uploaded_by: User who uploaded
            upload_ip_address: IP address of uploader
            metadata: Additional metadata
            
        Returns:
            Created media entity
        """
        media = ReviewMedia(
            review_id=review_id,
            media_type=media_type,
            original_url=original_url,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            original_filename=original_filename,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            caption=caption,
            alt_text=alt_text,
            display_order=display_order,
            uploaded_by=uploaded_by,
            upload_ip_address=upload_ip_address,
            metadata=metadata
        )
        
        self.session.add(media)
        self.session.commit()
        self.session.refresh(media)
        
        # Create processing log
        self._create_processing_log(media.id)
        
        return media
    
    def update_media(
        self,
        media_id: UUID,
        updates: Dict[str, Any]
    ) -> ReviewMedia:
        """
        Update media entity.
        
        Args:
            media_id: Media to update
            updates: Fields to update
            
        Returns:
            Updated media
        """
        media = self.find_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        for field, value in updates.items():
            if hasattr(media, field):
                setattr(media, field, value)
        
        self.session.commit()
        self.session.refresh(media)
        
        return media
    
    def delete_media(
        self,
        media_id: UUID,
        soft: bool = True
    ) -> bool:
        """
        Delete media.
        
        Args:
            media_id: Media to delete
            soft: Whether to soft delete
            
        Returns:
            True if deleted
        """
        if soft:
            return self.soft_delete(media_id)
        else:
            media = self.find_by_id(media_id)
            if not media:
                return False
            
            self.session.delete(media)
            self.session.commit()
            return True
    
    # ==================== Query Operations ====================
    
    def get_review_media(
        self,
        review_id: UUID,
        media_type: Optional[str] = None,
        approved_only: bool = False
    ) -> List[ReviewMedia]:
        """
        Get media for specific review.
        
        Args:
            review_id: Review ID
            media_type: Optional media type filter
            approved_only: Whether to only return approved media
            
        Returns:
            List of media attachments
        """
        query = self.session.query(ReviewMedia).filter(
            ReviewMedia.review_id == review_id,
            ReviewMedia.deleted_at.is_(None)
        )
        
        if media_type:
            query = query.filter(ReviewMedia.media_type == media_type)
        
        if approved_only:
            query = query.filter(
                ReviewMedia.is_approved == True,
                ReviewMedia.is_visible == True
            )
        
        return query.order_by(asc(ReviewMedia.display_order)).all()
    
    def get_pending_moderation(
        self,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[ReviewMedia]:
        """
        Get media pending moderation.
        
        Args:
            pagination: Pagination parameters
            
        Returns:
            Paginated pending media
        """
        query = self.session.query(ReviewMedia).filter(
            ReviewMedia.moderation_status == 'pending',
            ReviewMedia.is_processed == True,
            ReviewMedia.deleted_at.is_(None)
        )
        
        query = query.order_by(asc(ReviewMedia.created_at))
        
        return self._paginate_query(query, pagination)
    
    def get_flagged_media(
        self,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[ReviewMedia]:
        """
        Get flagged media.
        
        Args:
            pagination: Pagination parameters
            
        Returns:
            Paginated flagged media
        """
        query = self.session.query(ReviewMedia).filter(
            ReviewMedia.moderation_status == 'flagged',
            ReviewMedia.deleted_at.is_(None)
        )
        
        query = query.order_by(desc(ReviewMedia.moderated_at))
        
        return self._paginate_query(query, pagination)
    
    def get_processing_queue(
        self,
        limit: int = 100
    ) -> List[ReviewMedia]:
        """
        Get media in processing queue.
        
        Args:
            limit: Maximum number of items
            
        Returns:
            List of media to process
        """
        return self.session.query(ReviewMedia).filter(
            ReviewMedia.is_processed == False,
            ReviewMedia.processing_status.in_(['pending', 'processing']),
            ReviewMedia.deleted_at.is_(None)
        ).order_by(asc(ReviewMedia.created_at)).limit(limit).all()
    
    # ==================== Processing Operations ====================
    
    def mark_processing_started(
        self,
        media_id: UUID
    ) -> ReviewMedia:
        """
        Mark media processing as started.
        
        Args:
            media_id: Media ID
            
        Returns:
            Updated media
        """
        media = self.find_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        media.processing_status = 'processing'
        
        # Update processing log
        processing = self._get_processing_log(media_id)
        if processing:
            processing.mark_started()
        
        self.session.commit()
        self.session.refresh(media)
        
        return media
    
    def mark_processing_completed(
        self,
        media_id: UUID,
        processed_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        variants: Optional[Dict[str, str]] = None
    ) -> ReviewMedia:
        """
        Mark media processing as completed.
        
        Args:
            media_id: Media ID
            processed_url: URL to processed file
            thumbnail_url: URL to thumbnail
            variants: URLs to various size variants
            
        Returns:
            Updated media
        """
        media = self.find_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        media.mark_as_processed(processed_url)
        if thumbnail_url:
            media.thumbnail_url = thumbnail_url
        
        # Update processing log
        processing = self._get_processing_log(media_id)
        if processing:
            processing.mark_completed()
            if variants:
                processing.variants_generated = variants
        
        self.session.commit()
        self.session.refresh(media)
        
        return media
    
    def mark_processing_failed(
        self,
        media_id: UUID,
        error: str
    ) -> ReviewMedia:
        """
        Mark media processing as failed.
        
        Args:
            media_id: Media ID
            error: Error message
            
        Returns:
            Updated media
        """
        media = self.find_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        media.mark_processing_failed(error)
        
        # Update processing log
        processing = self._get_processing_log(media_id)
        if processing:
            processing.add_error(error)
            processing.increment_retry()
        
        self.session.commit()
        self.session.refresh(media)
        
        return media
    
    def update_processing_step(
        self,
        media_id: UUID,
        step_name: str,
        step_time_ms: Optional[int] = None
    ):
        """
        Update processing step.
        
        Args:
            media_id: Media ID
            step_name: Name of processing step
            step_time_ms: Time taken for step in milliseconds
        """
        processing = self._get_processing_log(media_id)
        if processing:
            processing.add_step(step_name)
            
            if step_time_ms:
                if step_name == 'upload':
                    processing.upload_time_ms = step_time_ms
                elif step_name == 'processing':
                    processing.processing_time_ms = step_time_ms
            
            self.session.commit()
    
    # ==================== Moderation Operations ====================
    
    def approve_media(
        self,
        media_id: UUID,
        admin_id: UUID,
        notes: Optional[str] = None
    ) -> ReviewMedia:
        """
        Approve media for display.
        
        Args:
            media_id: Media to approve
            admin_id: Admin approving
            notes: Optional approval notes
            
        Returns:
            Approved media
        """
        media = self.find_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        media.approve(admin_id, notes)
        
        self.session.commit()
        self.session.refresh(media)
        
        return media
    
    def reject_media(
        self,
        media_id: UUID,
        admin_id: UUID,
        notes: str
    ) -> ReviewMedia:
        """
        Reject media.
        
        Args:
            media_id: Media to reject
            admin_id: Admin rejecting
            notes: Rejection reason
            
        Returns:
            Rejected media
        """
        media = self.find_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        media.reject(admin_id, notes)
        
        self.session.commit()
        self.session.refresh(media)
        
        return media
    
    def flag_media(
        self,
        media_id: UUID,
        admin_id: UUID,
        notes: str
    ) -> ReviewMedia:
        """
        Flag media for review.
        
        Args:
            media_id: Media to flag
            admin_id: Admin flagging
            notes: Flag reason
            
        Returns:
            Flagged media
        """
        media = self.find_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        media.flag(admin_id, notes)
        
        self.session.commit()
        self.session.refresh(media)
        
        return media
    
    def update_content_analysis(
        self,
        media_id: UUID,
        has_inappropriate_content: bool,
        content_safety_score: Decimal,
        detected_labels: List[str]
    ) -> ReviewMedia:
        """
        Update AI content analysis results.
        
        Args:
            media_id: Media ID
            has_inappropriate_content: Whether inappropriate content detected
            content_safety_score: Safety score (0-1)
            detected_labels: List of detected content labels
            
        Returns:
            Updated media
        """
        media = self.find_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        media.has_inappropriate_content = has_inappropriate_content
        media.content_safety_score = content_safety_score
        media.detected_labels = detected_labels
        
        # Update processing log
        processing = self._get_processing_log(media_id)
        if processing:
            processing.safety_analysis_completed = True
            if has_inappropriate_content:
                processing.safety_flags = detected_labels
        
        self.session.commit()
        self.session.refresh(media)
        
        return media
    
    # ==================== Analytics ====================
    
    def get_media_statistics(
        self,
        review_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get media statistics.
        
        Args:
            review_id: Optional review filter
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Media statistics
        """
        query = self.session.query(ReviewMedia).filter(
            ReviewMedia.deleted_at.is_(None)
        )
        
        if review_id:
            query = query.filter(ReviewMedia.review_id == review_id)
        
        if start_date:
            query = query.filter(ReviewMedia.created_at >= start_date)
        
        if end_date:
            query = query.filter(ReviewMedia.created_at <= end_date)
        
        total_media = query.count()
        
        # Type breakdown
        photos = query.filter(ReviewMedia.media_type == 'photo').count()
        videos = query.filter(ReviewMedia.media_type == 'video').count()
        
        # Moderation breakdown
        approved = query.filter(ReviewMedia.is_approved == True).count()
        pending = query.filter(ReviewMedia.moderation_status == 'pending').count()
        rejected = query.filter(ReviewMedia.moderation_status == 'rejected').count()
        flagged = query.filter(ReviewMedia.moderation_status == 'flagged').count()
        
        # Processing breakdown
        processed = query.filter(ReviewMedia.is_processed == True).count()
        processing = query.filter(ReviewMedia.processing_status == 'processing').count()
        failed = query.filter(ReviewMedia.processing_status == 'failed').count()
        
        # Content safety
        inappropriate = query.filter(ReviewMedia.has_inappropriate_content == True).count()
        
        # Average file size
        avg_size = query.with_entities(
            func.avg(ReviewMedia.file_size_bytes)
        ).scalar()
        
        return {
            'total_media': total_media,
            'photos': photos,
            'videos': videos,
            'approved': approved,
            'pending_moderation': pending,
            'rejected': rejected,
            'flagged': flagged,
            'processed': processed,
            'processing': processing,
            'failed_processing': failed,
            'inappropriate_content': inappropriate,
            'average_file_size_bytes': int(avg_size or 0),
            'approval_rate': (approved / total_media * 100) if total_media > 0 else 0
        }
    
    def get_processing_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get processing performance statistics.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Processing statistics
        """
        query = self.session.query(ReviewMediaProcessing)
        
        if start_date:
            query = query.filter(ReviewMediaProcessing.created_at >= start_date)
        
        if end_date:
            query = query.filter(ReviewMediaProcessing.created_at <= end_date)
        
        stats = query.with_entities(
            func.avg(ReviewMediaProcessing.total_time_ms).label('avg_total_time'),
            func.avg(ReviewMediaProcessing.upload_time_ms).label('avg_upload_time'),
            func.avg(ReviewMediaProcessing.processing_time_ms).label('avg_processing_time'),
            func.avg(ReviewMediaProcessing.compression_ratio).label('avg_compression'),
            func.count(ReviewMediaProcessing.id).label('total_processed')
        ).first()
        
        # Count failures
        total_retries = query.with_entities(
            func.sum(ReviewMediaProcessing.retry_count)
        ).scalar()
        
        return {
            'total_processed': stats.total_processed or 0,
            'average_total_time_ms': float(stats.avg_total_time or 0),
            'average_upload_time_ms': float(stats.avg_upload_time or 0),
            'average_processing_time_ms': float(stats.avg_processing_time or 0),
            'average_compression_ratio': float(stats.avg_compression or 0),
            'total_retries': int(total_retries or 0)
        }
    
    def increment_view_count(
        self,
        media_id: UUID
    ):
        """
        Increment media view count.
        
        Args:
            media_id: Media ID
        """
        media = self.find_by_id(media_id)
        if media:
            media.increment_view()
            self.session.commit()
    
    # ==================== Helper Methods ====================
    
    def _create_processing_log(self, media_id: UUID) -> ReviewMediaProcessing:
        """Create processing log for media."""
        processing = ReviewMediaProcessing(media_id=media_id)
        self.session.add(processing)
        self.session.commit()
        return processing
    
    def _get_processing_log(self, media_id: UUID) -> Optional[ReviewMediaProcessing]:
        """Get processing log for media."""
        return self.session.query(ReviewMediaProcessing).filter(
            ReviewMediaProcessing.media_id == media_id
        ).first()
    
    def _paginate_query(
        self,
        query,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult:
        """Paginate query results."""
        if not pagination:
            pagination = {'page': 1, 'per_page': 20}
        
        page = pagination.get('page', 1)
        per_page = pagination.get('per_page', 20)
        
        total = query.count()
        items = query.limit(per_page).offset((page - 1) * per_page).all()
        
        return PaginatedResult(
            items=items,
            total_count=total,
            page=page,
            page_size=per_page
        )