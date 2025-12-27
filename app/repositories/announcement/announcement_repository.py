"""
Announcement Repository

Comprehensive announcement management with content lifecycle, audience targeting,
and effectiveness tracking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, case, exists, select
from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from sqlalchemy.sql import Select

from app.models.announcement import (
    Announcement,
    AnnouncementAttachment,
    AnnouncementVersion,
    AnnouncementRecipient,
)
from app.models.base.enums import (
    AnnouncementCategory,
    AnnouncementStatus,
    Priority,
    TargetAudience,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.repositories.base.filtering import FilterCriteria
from app.core1.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)


class ActiveAnnouncementsSpec(Specification):
    """Specification for active announcements."""
    
    def is_satisfied_by(self, announcement: Announcement) -> bool:
        return announcement.is_active
    
    def to_sqlalchemy(self) -> Any:
        now = datetime.utcnow()
        return and_(
            Announcement.is_published == True,
            Announcement.is_archived == False,
            Announcement.is_deleted == False,
            or_(
                Announcement.expires_at.is_(None),
                Announcement.expires_at > now
            )
        )


class UrgentAnnouncementsSpec(Specification):
    """Specification for urgent announcements."""
    
    def to_sqlalchemy(self) -> Any:
        return and_(
            Announcement.is_urgent == True,
            Announcement.is_published == True,
            Announcement.is_deleted == False,
        )


class RequiresAcknowledgmentSpec(Specification):
    """Specification for announcements requiring acknowledgment."""
    
    def to_sqlalchemy(self) -> Any:
        return and_(
            Announcement.requires_acknowledgment == True,
            Announcement.is_published == True,
        )


class AnnouncementRepository(BaseRepository[Announcement]):
    """
    Repository for announcement management.
    
    Provides comprehensive announcement operations including:
    - Content lifecycle management
    - Advanced search and filtering
    - Performance tracking
    - Version control
    - Archival and cleanup
    """
    
    def __init__(self, session: Session):
        super().__init__(Announcement, session)
    
    # ==================== Create Operations ====================
    
    def create_draft(
        self,
        hostel_id: UUID,
        created_by_id: UUID,
        title: str,
        content: str,
        category: AnnouncementCategory,
        priority: Priority = Priority.MEDIUM,
        **kwargs
    ) -> Announcement:
        """
        Create announcement draft with auto-save functionality.
        
        Args:
            hostel_id: Hostel UUID
            created_by_id: Creator user UUID
            title: Announcement title
            content: Announcement content
            category: Category enum
            priority: Priority level
            **kwargs: Additional announcement fields
            
        Returns:
            Created announcement draft
        """
        announcement = Announcement(
            hostel_id=hostel_id,
            created_by_id=created_by_id,
            title=title,
            content=content,
            category=category,
            priority=priority,
            status=AnnouncementStatus.DRAFT,
            version_number=1,
            **kwargs
        )
        
        self.session.add(announcement)
        self.session.flush()
        
        # Create initial version
        self._create_version(announcement, created_by_id, "Initial draft")
        
        return announcement
    
    def create_from_template(
        self,
        template_id: UUID,
        hostel_id: UUID,
        created_by_id: UUID,
        overrides: Optional[Dict[str, Any]] = None
    ) -> Announcement:
        """
        Create announcement from template.
        
        Args:
            template_id: Template announcement UUID
            hostel_id: Target hostel UUID
            created_by_id: Creator user UUID
            overrides: Field overrides for template
            
        Returns:
            New announcement based on template
        """
        template = self.find_by_id(template_id)
        if not template:
            raise ResourceNotFoundError(f"Template {template_id} not found")
        
        # Copy template fields
        announcement_data = {
            'title': template.title,
            'content': template.content,
            'category': template.category,
            'priority': template.priority,
            'target_audience': template.target_audience,
            'send_email': template.send_email,
            'send_sms': template.send_sms,
            'send_push': template.send_push,
            'requires_acknowledgment': template.requires_acknowledgment,
        }
        
        # Apply overrides
        if overrides:
            announcement_data.update(overrides)
        
        return self.create_draft(
            hostel_id=hostel_id,
            created_by_id=created_by_id,
            **announcement_data
        )
    
    # ==================== Read Operations ====================
    
    def find_by_id_with_details(
        self,
        announcement_id: UUID,
        include_deleted: bool = False
    ) -> Optional[Announcement]:
        """
        Find announcement with all related data eagerly loaded.
        
        Args:
            announcement_id: Announcement UUID
            include_deleted: Include soft-deleted records
            
        Returns:
            Announcement with relationships loaded or None
        """
        query = (
            select(Announcement)
            .where(Announcement.id == announcement_id)
            .options(
                joinedload(Announcement.hostel),
                joinedload(Announcement.created_by),
                joinedload(Announcement.published_by),
                selectinload(Announcement.attachments_rel),
                selectinload(Announcement.targets),
                selectinload(Announcement.recipients),
            )
        )
        
        if not include_deleted:
            query = query.where(Announcement.is_deleted == False)
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        filters: Optional[FilterCriteria] = None,
        pagination: Optional[PaginationParams] = None,
        include_archived: bool = False
    ) -> PaginatedResult[Announcement]:
        """
        Find announcements for a hostel with filtering and pagination.
        
        Args:
            hostel_id: Hostel UUID
            filters: Filter criteria
            pagination: Pagination parameters
            include_archived: Include archived announcements
            
        Returns:
            Paginated announcement results
        """
        query = (
            QueryBuilder(Announcement, self.session)
            .where(Announcement.hostel_id == hostel_id)
            .where(Announcement.is_deleted == False)
        )
        
        if not include_archived:
            query = query.where(Announcement.is_archived == False)
        
        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Default ordering
        query = query.order_by(
            Announcement.is_pinned.desc(),
            Announcement.is_urgent.desc(),
            Announcement.published_at.desc(),
            Announcement.created_at.desc()
        )
        
        return query.paginate(pagination or PaginationParams())
    
    def find_active_by_hostel(
        self,
        hostel_id: UUID,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[Announcement]:
        """
        Find active announcements for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            pagination: Pagination parameters
            
        Returns:
            Paginated active announcements
        """
        spec = ActiveAnnouncementsSpec()
        
        query = (
            QueryBuilder(Announcement, self.session)
            .where(Announcement.hostel_id == hostel_id)
            .where(spec.to_sqlalchemy())
            .order_by(
                Announcement.is_pinned.desc(),
                Announcement.is_urgent.desc(),
                Announcement.published_at.desc()
            )
        )
        
        return query.paginate(pagination or PaginationParams())
    
    def find_drafts_by_creator(
        self,
        created_by_id: UUID,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[Announcement]:
        """
        Find draft announcements by creator.
        
        Args:
            created_by_id: Creator user UUID
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated draft announcements
        """
        query = (
            QueryBuilder(Announcement, self.session)
            .where(Announcement.created_by_id == created_by_id)
            .where(Announcement.status == AnnouncementStatus.DRAFT)
            .where(Announcement.is_deleted == False)
        )
        
        if hostel_id:
            query = query.where(Announcement.hostel_id == hostel_id)
        
        query = query.order_by(Announcement.updated_at.desc())
        
        return query.paginate(pagination or PaginationParams())
    
    def find_urgent_announcements(
        self,
        hostel_id: UUID,
        limit: int = 10
    ) -> List[Announcement]:
        """
        Find urgent announcements for immediate attention.
        
        Args:
            hostel_id: Hostel UUID
            limit: Maximum number of results
            
        Returns:
            List of urgent announcements
        """
        spec = UrgentAnnouncementsSpec()
        
        query = (
            select(Announcement)
            .where(Announcement.hostel_id == hostel_id)
            .where(spec.to_sqlalchemy())
            .order_by(
                Announcement.priority.desc(),
                Announcement.published_at.desc()
            )
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_requiring_acknowledgment(
        self,
        hostel_id: UUID,
        student_id: Optional[UUID] = None,
        pending_only: bool = True
    ) -> List[Announcement]:
        """
        Find announcements requiring acknowledgment.
        
        Args:
            hostel_id: Hostel UUID
            student_id: Optional student filter
            pending_only: Only unacknowledged announcements
            
        Returns:
            List of announcements requiring acknowledgment
        """
        spec = RequiresAcknowledgmentSpec()
        
        query = (
            select(Announcement)
            .where(Announcement.hostel_id == hostel_id)
            .where(spec.to_sqlalchemy())
        )
        
        if student_id and pending_only:
            # Only announcements not yet acknowledged by this student
            from app.models.announcement import Acknowledgment
            
            acknowledged_subq = (
                select(Acknowledgment.announcement_id)
                .where(Acknowledgment.student_id == student_id)
            )
            
            query = query.where(
                ~Announcement.id.in_(acknowledged_subq)
            )
        
        query = query.order_by(
            Announcement.acknowledgment_deadline.asc().nullslast(),
            Announcement.published_at.desc()
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_expiring_soon(
        self,
        hostel_id: UUID,
        hours: int = 24
    ) -> List[Announcement]:
        """
        Find announcements expiring within specified hours.
        
        Args:
            hostel_id: Hostel UUID
            hours: Hours until expiration
            
        Returns:
            List of expiring announcements
        """
        now = datetime.utcnow()
        expiry_threshold = now + timedelta(hours=hours)
        
        query = (
            select(Announcement)
            .where(Announcement.hostel_id == hostel_id)
            .where(Announcement.is_published == True)
            .where(Announcement.is_deleted == False)
            .where(Announcement.expires_at.isnot(None))
            .where(Announcement.expires_at > now)
            .where(Announcement.expires_at <= expiry_threshold)
            .order_by(Announcement.expires_at.asc())
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def search_announcements(
        self,
        hostel_id: UUID,
        search_term: str,
        filters: Optional[FilterCriteria] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[Announcement]:
        """
        Full-text search with relevance ranking.
        
        Args:
            hostel_id: Hostel UUID
            search_term: Search query
            filters: Additional filters
            pagination: Pagination parameters
            
        Returns:
            Paginated search results
        """
        # PostgreSQL full-text search
        search_query = func.to_tsquery('english', search_term)
        
        query = (
            QueryBuilder(Announcement, self.session)
            .where(Announcement.hostel_id == hostel_id)
            .where(Announcement.is_deleted == False)
            .where(
                or_(
                    func.to_tsvector('english', Announcement.title)
                    .match(search_query),
                    func.to_tsvector('english', Announcement.content)
                    .match(search_query)
                )
            )
        )
        
        if filters:
            query = self._apply_filters(query, filters)
        
        # Relevance ranking
        title_rank = func.ts_rank(
            func.to_tsvector('english', Announcement.title),
            search_query
        )
        content_rank = func.ts_rank(
            func.to_tsvector('english', Announcement.content),
            search_query
        )
        
        query = query.order_by(
            (title_rank * 2 + content_rank).desc(),
            Announcement.published_at.desc()
        )
        
        return query.paginate(pagination or PaginationParams())
    
    # ==================== Update Operations ====================
    
    def update_content(
        self,
        announcement_id: UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
        modified_by_id: UUID = None,
        change_summary: Optional[str] = None
    ) -> Announcement:
        """
        Update announcement content with versioning.
        
        Args:
            announcement_id: Announcement UUID
            title: New title
            content: New content
            modified_by_id: User making changes
            change_summary: Summary of changes
            
        Returns:
            Updated announcement
        """
        announcement = self.find_by_id(announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        if announcement.is_published:
            raise BusinessLogicError(
                "Cannot edit published announcement. Create new version instead."
            )
        
        changed_fields = []
        
        if title and title != announcement.title:
            announcement.title = title
            changed_fields.append('title')
        
        if content and content != announcement.content:
            announcement.content = content
            changed_fields.append('content')
        
        if changed_fields:
            announcement.version_number += 1
            announcement.updated_at = datetime.utcnow()
            
            # Create version snapshot
            self._create_version(
                announcement,
                modified_by_id,
                change_summary or f"Updated {', '.join(changed_fields)}",
                changed_fields
            )
        
        self.session.flush()
        return announcement
    
    def publish_announcement(
        self,
        announcement_id: UUID,
        published_by_id: UUID,
        scheduled_for: Optional[datetime] = None
    ) -> Announcement:
        """
        Publish announcement immediately or schedule for later.
        
        Args:
            announcement_id: Announcement UUID
            published_by_id: Publisher user UUID
            scheduled_for: Optional scheduled publication time
            
        Returns:
            Published/scheduled announcement
        """
        announcement = self.find_by_id(announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        if announcement.is_published:
            raise BusinessLogicError("Announcement already published")
        
        if scheduled_for:
            # Schedule for future publication
            announcement.scheduled_publish_at = scheduled_for
            announcement.status = AnnouncementStatus.SCHEDULED
        else:
            # Publish immediately
            now = datetime.utcnow()
            announcement.is_published = True
            announcement.published_at = now
            announcement.published_by_id = published_by_id
            announcement.status = AnnouncementStatus.PUBLISHED
        
        self.session.flush()
        return announcement
    
    def unpublish_announcement(
        self,
        announcement_id: UUID,
        reason: Optional[str] = None
    ) -> Announcement:
        """
        Unpublish announcement (retract).
        
        Args:
            announcement_id: Announcement UUID
            reason: Reason for unpublishing
            
        Returns:
            Unpublished announcement
        """
        announcement = self.find_by_id(announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        if not announcement.is_published:
            raise BusinessLogicError("Announcement not published")
        
        announcement.is_published = False
        announcement.status = AnnouncementStatus.DRAFT
        announcement.metadata = announcement.metadata or {}
        announcement.metadata['unpublish_reason'] = reason
        announcement.metadata['unpublished_at'] = datetime.utcnow().isoformat()
        
        self.session.flush()
        return announcement
    
    def pin_announcement(
        self,
        announcement_id: UUID,
        pinned: bool = True
    ) -> Announcement:
        """
        Pin/unpin announcement to top of list.
        
        Args:
            announcement_id: Announcement UUID
            pinned: Pin status
            
        Returns:
            Updated announcement
        """
        announcement = self.find_by_id(announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        announcement.is_pinned = pinned
        self.session.flush()
        return announcement
    
    def mark_urgent(
        self,
        announcement_id: UUID,
        urgent: bool = True
    ) -> Announcement:
        """
        Mark announcement as urgent/normal.
        
        Args:
            announcement_id: Announcement UUID
            urgent: Urgent status
            
        Returns:
            Updated announcement
        """
        announcement = self.find_by_id(announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        announcement.is_urgent = urgent
        self.session.flush()
        return announcement
    
    def update_engagement_metrics(
        self,
        announcement_id: UUID
    ) -> Announcement:
        """
        Recalculate and update engagement metrics.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Updated announcement
        """
        announcement = self.find_by_id(announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        # Count reads
        from app.models.announcement import ReadReceipt
        read_count = (
            self.session.query(func.count(ReadReceipt.id))
            .filter(ReadReceipt.announcement_id == announcement_id)
            .scalar()
        ) or 0
        
        # Count acknowledgments if required
        acknowledged_count = 0
        if announcement.requires_acknowledgment:
            from app.models.announcement import Acknowledgment
            acknowledged_count = (
                self.session.query(func.count(Acknowledgment.id))
                .filter(Acknowledgment.announcement_id == announcement_id)
                .scalar()
            ) or 0
        
        # Update metrics
        announcement.read_count = read_count
        announcement.acknowledged_count = acknowledged_count
        
        # Calculate engagement rate
        if announcement.total_recipients > 0:
            if announcement.requires_acknowledgment:
                rate = (acknowledged_count / announcement.total_recipients) * 100
            else:
                rate = (read_count / announcement.total_recipients) * 100
            announcement.engagement_rate = Decimal(str(round(rate, 2)))
        
        self.session.flush()
        return announcement
    
    # ==================== Archive Operations ====================
    
    def archive_announcement(
        self,
        announcement_id: UUID,
        archived_by_id: UUID,
        reason: Optional[str] = None
    ) -> Announcement:
        """
        Archive announcement.
        
        Args:
            announcement_id: Announcement UUID
            archived_by_id: User archiving
            reason: Archive reason
            
        Returns:
            Archived announcement
        """
        announcement = self.find_by_id(announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        if announcement.is_archived:
            raise BusinessLogicError("Announcement already archived")
        
        now = datetime.utcnow()
        announcement.is_archived = True
        announcement.archived_at = now
        announcement.archived_by_id = archived_by_id
        announcement.status = AnnouncementStatus.ARCHIVED
        
        if reason:
            announcement.metadata = announcement.metadata or {}
            announcement.metadata['archive_reason'] = reason
        
        self.session.flush()
        return announcement
    
    def unarchive_announcement(
        self,
        announcement_id: UUID
    ) -> Announcement:
        """
        Restore announcement from archive.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Restored announcement
        """
        announcement = self.find_by_id(announcement_id, include_deleted=True)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        if not announcement.is_archived:
            raise BusinessLogicError("Announcement not archived")
        
        announcement.is_archived = False
        announcement.archived_at = None
        announcement.archived_by_id = None
        announcement.status = (
            AnnouncementStatus.PUBLISHED
            if announcement.is_published
            else AnnouncementStatus.DRAFT
        )
        
        self.session.flush()
        return announcement
    
    def bulk_archive_expired(
        self,
        hostel_id: UUID,
        archived_by_id: UUID
    ) -> int:
        """
        Bulk archive expired announcements.
        
        Args:
            hostel_id: Hostel UUID
            archived_by_id: User performing archive
            
        Returns:
            Number of announcements archived
        """
        now = datetime.utcnow()
        
        expired_announcements = (
            self.session.query(Announcement)
            .filter(
                Announcement.hostel_id == hostel_id,
                Announcement.is_deleted == False,
                Announcement.is_archived == False,
                Announcement.expires_at.isnot(None),
                Announcement.expires_at <= now
            )
            .all()
        )
        
        count = 0
        for announcement in expired_announcements:
            announcement.is_archived = True
            announcement.archived_at = now
            announcement.archived_by_id = archived_by_id
            announcement.status = AnnouncementStatus.ARCHIVED
            count += 1
        
        self.session.flush()
        return count
    
    # ==================== Statistics & Analytics ====================
    
    def get_announcement_statistics(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive announcement statistics.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Statistics dictionary
        """
        query = (
            select(Announcement)
            .where(Announcement.hostel_id == hostel_id)
            .where(Announcement.is_deleted == False)
        )
        
        if start_date:
            query = query.where(Announcement.created_at >= start_date)
        if end_date:
            query = query.where(Announcement.created_at <= end_date)
        
        # Total counts by status
        status_counts = (
            self.session.query(
                Announcement.status,
                func.count(Announcement.id)
            )
            .filter(Announcement.hostel_id == hostel_id)
            .filter(Announcement.is_deleted == False)
            .group_by(Announcement.status)
            .all()
        )
        
        # Category distribution
        category_counts = (
            self.session.query(
                Announcement.category,
                func.count(Announcement.id)
            )
            .filter(Announcement.hostel_id == hostel_id)
            .filter(Announcement.is_deleted == False)
            .group_by(Announcement.category)
            .all()
        )
        
        # Engagement metrics
        avg_engagement = (
            self.session.query(
                func.avg(Announcement.engagement_rate),
                func.avg(Announcement.read_count),
                func.avg(Announcement.acknowledged_count)
            )
            .filter(Announcement.hostel_id == hostel_id)
            .filter(Announcement.is_published == True)
            .filter(Announcement.is_deleted == False)
            .first()
        )
        
        return {
            'total_announcements': sum(count for _, count in status_counts),
            'status_breakdown': {
                status.value: count for status, count in status_counts
            },
            'category_breakdown': {
                category.value: count for category, count in category_counts
            },
            'average_engagement_rate': float(avg_engagement[0] or 0),
            'average_read_count': float(avg_engagement[1] or 0),
            'average_acknowledged_count': float(avg_engagement[2] or 0),
            'active_announcements': self._count_active(hostel_id),
            'urgent_announcements': self._count_urgent(hostel_id),
            'pending_acknowledgment': self._count_pending_acknowledgment(hostel_id),
        }
    
    def get_performance_metrics(
        self,
        announcement_id: UUID
    ) -> Dict[str, Any]:
        """
        Get detailed performance metrics for an announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Performance metrics dictionary
        """
        announcement = self.find_by_id(announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        # Read receipt analysis
        from app.models.announcement import ReadReceipt, AnnouncementView
        
        total_views = (
            self.session.query(func.count(AnnouncementView.id))
            .filter(AnnouncementView.announcement_id == announcement_id)
            .scalar()
        ) or 0
        
        unique_viewers = (
            self.session.query(func.count(func.distinct(AnnouncementView.student_id)))
            .filter(AnnouncementView.announcement_id == announcement_id)
            .scalar()
        ) or 0
        
        avg_reading_time = (
            self.session.query(func.avg(ReadReceipt.reading_time_seconds))
            .filter(ReadReceipt.announcement_id == announcement_id)
            .scalar()
        ) or 0
        
        return {
            'announcement_id': str(announcement_id),
            'total_recipients': announcement.total_recipients,
            'read_count': announcement.read_count,
            'read_percentage': announcement.read_percentage,
            'acknowledged_count': announcement.acknowledged_count,
            'acknowledgment_percentage': announcement.acknowledgment_percentage,
            'engagement_rate': float(announcement.engagement_rate),
            'total_views': total_views,
            'unique_viewers': unique_viewers,
            'average_reading_time_seconds': float(avg_reading_time),
            'is_active': announcement.is_active,
            'is_expired': announcement.is_expired,
        }
    
    def get_top_performing_announcements(
        self,
        hostel_id: UUID,
        limit: int = 10,
        metric: str = 'engagement_rate'
    ) -> List[Tuple[Announcement, float]]:
        """
        Get top performing announcements by metric.
        
        Args:
            hostel_id: Hostel UUID
            limit: Number of results
            metric: Performance metric to rank by
            
        Returns:
            List of (announcement, metric_value) tuples
        """
        metric_column = getattr(Announcement, metric, Announcement.engagement_rate)
        
        query = (
            select(Announcement, metric_column)
            .where(Announcement.hostel_id == hostel_id)
            .where(Announcement.is_published == True)
            .where(Announcement.is_deleted == False)
            .order_by(metric_column.desc())
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return [(row[0], float(row[1]) if row[1] else 0) for row in result]
    
    # ==================== Helper Methods ====================
    
    def _create_version(
        self,
        announcement: Announcement,
        modified_by_id: UUID,
        change_summary: str,
        changed_fields: Optional[List[str]] = None
    ) -> AnnouncementVersion:
        """Create version snapshot of announcement."""
        version = AnnouncementVersion(
            announcement_id=announcement.id,
            modified_by_id=modified_by_id,
            version_number=announcement.version_number,
            title=announcement.title,
            content=announcement.content,
            change_summary=change_summary,
            changed_fields=changed_fields,
            version_data={
                'title': announcement.title,
                'content': announcement.content,
                'category': announcement.category.value,
                'priority': announcement.priority.value,
                'target_audience': announcement.target_audience.value,
                'is_urgent': announcement.is_urgent,
                'is_pinned': announcement.is_pinned,
            }
        )
        
        self.session.add(version)
        return version
    
    def _apply_filters(
        self,
        query: QueryBuilder,
        filters: FilterCriteria
    ) -> QueryBuilder:
        """Apply filter criteria to query."""
        if filters.category:
            query = query.where(Announcement.category == filters.category)
        
        if filters.priority:
            query = query.where(Announcement.priority == filters.priority)
        
        if filters.status:
            query = query.where(Announcement.status == filters.status)
        
        if filters.is_urgent is not None:
            query = query.where(Announcement.is_urgent == filters.is_urgent)
        
        if filters.is_pinned is not None:
            query = query.where(Announcement.is_pinned == filters.is_pinned)
        
        if filters.date_from:
            query = query.where(Announcement.created_at >= filters.date_from)
        
        if filters.date_to:
            query = query.where(Announcement.created_at <= filters.date_to)
        
        return query
    
    def _count_active(self, hostel_id: UUID) -> int:
        """Count active announcements."""
        spec = ActiveAnnouncementsSpec()
        return (
            self.session.query(func.count(Announcement.id))
            .filter(Announcement.hostel_id == hostel_id)
            .filter(spec.to_sqlalchemy())
            .scalar()
        ) or 0
    
    def _count_urgent(self, hostel_id: UUID) -> int:
        """Count urgent announcements."""
        spec = UrgentAnnouncementsSpec()
        return (
            self.session.query(func.count(Announcement.id))
            .filter(Announcement.hostel_id == hostel_id)
            .filter(spec.to_sqlalchemy())
            .scalar()
        ) or 0
    
    def _count_pending_acknowledgment(self, hostel_id: UUID) -> int:
        """Count announcements with pending acknowledgments."""
        now = datetime.utcnow()
        return (
            self.session.query(func.count(Announcement.id))
            .filter(
                Announcement.hostel_id == hostel_id,
                Announcement.requires_acknowledgment == True,
                Announcement.is_published == True,
                Announcement.acknowledged_count < Announcement.total_recipients,
                or_(
                    Announcement.acknowledgment_deadline.is_(None),
                    Announcement.acknowledgment_deadline > now
                )
            )
            .scalar()
        ) or 0