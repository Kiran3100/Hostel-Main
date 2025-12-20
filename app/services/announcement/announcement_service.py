"""
Announcement Service

Core announcement business logic service providing complete lifecycle management,
content operations, and orchestration across the announcement domain.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, Field

from app.repositories.announcement import (
    AnnouncementRepository,
    AnnouncementAggregateRepository,
)
from app.models.base.enums import (
    AnnouncementCategory,
    AnnouncementStatus,
    Priority,
    TargetAudience,
)
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    PermissionError,
    BusinessLogicError,
)
from app.core.events import EventPublisher
from app.core.cache import CacheManager


# ==================== DTOs ====================

class CreateAnnouncementDTO(BaseModel):
    """DTO for creating announcement."""
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=10)
    category: AnnouncementCategory
    priority: Priority = Priority.MEDIUM
    target_audience: TargetAudience = TargetAudience.ALL
    
    # Targeting
    target_room_ids: Optional[List[UUID]] = None
    target_student_ids: Optional[List[UUID]] = None
    target_floor_numbers: Optional[List[int]] = None
    
    # Delivery settings
    send_email: bool = False
    send_sms: bool = False
    send_push: bool = True
    
    # Flags
    is_urgent: bool = False
    is_pinned: bool = False
    
    # Acknowledgment
    requires_acknowledgment: bool = False
    acknowledgment_deadline: Optional[datetime] = None
    
    # Approval
    requires_approval: bool = False
    
    # Expiry
    expires_at: Optional[datetime] = None
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('acknowledgment_deadline')
    def validate_acknowledgment_deadline(cls, v, values):
        if values.get('requires_acknowledgment') and not v:
            raise ValueError('Acknowledgment deadline required when acknowledgment is required')
        if v and v <= datetime.utcnow():
            raise ValueError('Acknowledgment deadline must be in the future')
        return v
    
    @validator('expires_at')
    def validate_expires_at(cls, v):
        if v and v <= datetime.utcnow():
            raise ValueError('Expiry date must be in the future')
        return v
    
    @validator('target_room_ids')
    def validate_room_targeting(cls, v, values):
        if values.get('target_audience') == TargetAudience.SPECIFIC_ROOMS and not v:
            raise ValueError('Room IDs required for SPECIFIC_ROOMS targeting')
        return v
    
    @validator('target_student_ids')
    def validate_student_targeting(cls, v, values):
        if values.get('target_audience') == TargetAudience.SPECIFIC_STUDENTS and not v:
            raise ValueError('Student IDs required for SPECIFIC_STUDENTS targeting')
        return v


class UpdateAnnouncementDTO(BaseModel):
    """DTO for updating announcement."""
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    content: Optional[str] = Field(None, min_length=10)
    category: Optional[AnnouncementCategory] = None
    priority: Optional[Priority] = None
    is_urgent: Optional[bool] = None
    is_pinned: Optional[bool] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = 'forbid'


class PublishAnnouncementDTO(BaseModel):
    """DTO for publishing announcement."""
    scheduled_for: Optional[datetime] = None
    
    @validator('scheduled_for')
    def validate_scheduled_for(cls, v):
        if v and v <= datetime.utcnow():
            raise ValueError('Scheduled time must be in the future')
        return v


class ArchiveAnnouncementDTO(BaseModel):
    """DTO for archiving announcement."""
    reason: Optional[str] = Field(None, max_length=500)


class BulkActionDTO(BaseModel):
    """DTO for bulk operations."""
    announcement_ids: List[UUID] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., regex='^(archive|delete|publish|pin|unpin)$')


@dataclass
class UserContext:
    """User context for permission checking."""
    user_id: UUID
    role: str
    hostel_id: UUID
    permissions: List[str]
    
    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions or self.role == 'admin'
    
    def can_create_announcement(self) -> bool:
        return self.role in ['admin', 'supervisor']
    
    def can_publish_announcement(self) -> bool:
        return self.role in ['admin', 'supervisor']
    
    def can_approve_announcement(self) -> bool:
        return self.role == 'admin'


@dataclass
class ServiceResult:
    """Standard service result wrapper."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def ok(cls, data: Any = None, **metadata) -> 'ServiceResult':
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, error_code: str = None, **metadata) -> 'ServiceResult':
        return cls(success=False, error=error, error_code=error_code, metadata=metadata)


# ==================== Service ====================

class AnnouncementService:
    """
    Core announcement business logic service.
    
    Provides comprehensive announcement management including:
    - CRUD operations with business validation
    - Content lifecycle management (draft -> published -> archived)
    - Permission and authorization checking
    - Version control and audit trail
    - Event publishing for integrations
    - Cache management for performance
    - Template-based creation
    - Bulk operations
    """
    
    def __init__(
        self,
        session: Session,
        event_publisher: Optional[EventPublisher] = None,
        cache_manager: Optional[CacheManager] = None
    ):
        self.session = session
        self.repository = AnnouncementRepository(session)
        self.aggregate_repository = AnnouncementAggregateRepository(session)
        self.event_publisher = event_publisher or EventPublisher()
        self.cache = cache_manager or CacheManager()
    
    # ==================== Create Operations ====================
    
    def create_announcement(
        self,
        dto: CreateAnnouncementDTO,
        user_context: UserContext
    ) -> ServiceResult:
        """
        Create new announcement with complete workflow setup.
        
        Args:
            dto: Announcement creation data
            user_context: User context for permissions
            
        Returns:
            ServiceResult with created announcement
        """
        try:
            # Permission check
            if not user_context.can_create_announcement():
                return ServiceResult.fail(
                    "Insufficient permissions to create announcement",
                    error_code="PERMISSION_DENIED"
                )
            
            # Business validation
            validation_result = self._validate_creation(dto, user_context)
            if not validation_result.success:
                return validation_result
            
            # Create announcement with targeting
            result = self.aggregate_repository.create_complete_announcement(
                hostel_id=user_context.hostel_id,
                created_by_id=user_context.user_id,
                announcement_data={
                    'title': dto.title,
                    'content': dto.content,
                    'category': dto.category,
                    'priority': dto.priority,
                    'is_urgent': dto.is_urgent,
                    'is_pinned': dto.is_pinned,
                    'send_email': dto.send_email,
                    'send_sms': dto.send_sms,
                    'send_push': dto.send_push,
                    'requires_acknowledgment': dto.requires_acknowledgment,
                    'acknowledgment_deadline': dto.acknowledgment_deadline,
                    'requires_approval': dto.requires_approval or (user_context.role == 'supervisor'),
                    'expires_at': dto.expires_at,
                    'metadata': dto.metadata,
                },
                targeting_data={
                    'target_type': dto.target_audience,
                    'room_ids': dto.target_room_ids,
                    'student_ids': dto.target_student_ids,
                    'floor_numbers': dto.target_floor_numbers,
                }
            )
            
            announcement = result['announcement']
            
            # Commit transaction
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('announcement.created', {
                'announcement_id': str(announcement.id),
                'title': announcement.title,
                'category': announcement.category.value,
                'created_by': str(user_context.user_id),
                'hostel_id': str(user_context.hostel_id),
                'requires_approval': announcement.requires_approval,
                'target_recipients': result['reach']['actual_recipients'],
            })
            
            # Invalidate cache
            self._invalidate_announcement_caches(user_context.hostel_id)
            
            return ServiceResult.ok(
                data={
                    'announcement': self._serialize_announcement(announcement),
                    'target_reach': result['reach'],
                    'approval_required': announcement.requires_approval,
                },
                announcement_id=str(announcement.id),
                status=announcement.status.value
            )
            
        except ValidationError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="VALIDATION_ERROR")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(
                f"Failed to create announcement: {str(e)}",
                error_code="CREATE_FAILED"
            )
    
    def create_from_template(
        self,
        template_id: UUID,
        overrides: Optional[Dict[str, Any]],
        user_context: UserContext
    ) -> ServiceResult:
        """
        Create announcement from template.
        
        Args:
            template_id: Template announcement UUID
            overrides: Field overrides
            user_context: User context
            
        Returns:
            ServiceResult with created announcement
        """
        try:
            # Permission check
            if not user_context.can_create_announcement():
                return ServiceResult.fail(
                    "Insufficient permissions",
                    error_code="PERMISSION_DENIED"
                )
            
            # Create from template
            announcement = self.repository.create_from_template(
                template_id=template_id,
                hostel_id=user_context.hostel_id,
                created_by_id=user_context.user_id,
                overrides=overrides
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('announcement.created_from_template', {
                'announcement_id': str(announcement.id),
                'template_id': str(template_id),
                'created_by': str(user_context.user_id),
            })
            
            return ServiceResult.ok(
                data=self._serialize_announcement(announcement),
                announcement_id=str(announcement.id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="TEMPLATE_NOT_FOUND")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="CREATE_FAILED")
    
    # ==================== Read Operations ====================
    
    def get_announcement(
        self,
        announcement_id: UUID,
        user_context: UserContext,
        include_details: bool = True
    ) -> ServiceResult:
        """
        Get announcement by ID with permission checking.
        
        Args:
            announcement_id: Announcement UUID
            user_context: User context
            include_details: Include related data
            
        Returns:
            ServiceResult with announcement data
        """
        try:
            # Check cache first
            cache_key = f"announcement:{announcement_id}"
            cached = self.cache.get(cache_key)
            if cached and not include_details:
                return ServiceResult.ok(data=cached)
            
            # Fetch from database
            if include_details:
                announcement = self.repository.find_by_id_with_details(announcement_id)
            else:
                announcement = self.repository.find_by_id(announcement_id)
            
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Permission check - must be in same hostel
            if announcement.hostel_id != user_context.hostel_id:
                return ServiceResult.fail(
                    "Access denied",
                    error_code="PERMISSION_DENIED"
                )
            
            # Serialize and cache
            data = self._serialize_announcement(announcement, include_details)
            self.cache.set(cache_key, data, ttl=300)  # 5 minutes
            
            return ServiceResult.ok(data=data)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_FAILED")
    
    def list_announcements(
        self,
        user_context: UserContext,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        include_archived: bool = False
    ) -> ServiceResult:
        """
        List announcements with filtering and pagination.
        
        Args:
            user_context: User context
            filters: Filter criteria
            page: Page number
            page_size: Items per page
            include_archived: Include archived
            
        Returns:
            ServiceResult with paginated announcements
        """
        try:
            from app.repositories.base.pagination import PaginationParams
            from app.repositories.base.filtering import FilterCriteria
            
            # Build filter criteria
            filter_criteria = FilterCriteria()
            if filters:
                if 'category' in filters:
                    filter_criteria.category = AnnouncementCategory(filters['category'])
                if 'priority' in filters:
                    filter_criteria.priority = Priority(filters['priority'])
                if 'status' in filters:
                    filter_criteria.status = AnnouncementStatus(filters['status'])
                if 'is_urgent' in filters:
                    filter_criteria.is_urgent = filters['is_urgent']
                if 'is_pinned' in filters:
                    filter_criteria.is_pinned = filters['is_pinned']
                if 'date_from' in filters:
                    filter_criteria.date_from = filters['date_from']
                if 'date_to' in filters:
                    filter_criteria.date_to = filters['date_to']
            
            # Pagination params
            pagination = PaginationParams(page=page, page_size=page_size)
            
            # Fetch announcements
            result = self.repository.find_by_hostel(
                hostel_id=user_context.hostel_id,
                filters=filter_criteria,
                pagination=pagination,
                include_archived=include_archived
            )
            
            return ServiceResult.ok(data={
                'items': [self._serialize_announcement(a, False) for a in result.items],
                'total': result.total,
                'page': result.page,
                'page_size': result.page_size,
                'total_pages': result.total_pages,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="LIST_FAILED")
    
    def get_active_announcements(
        self,
        user_context: UserContext,
        page: int = 1,
        page_size: int = 20
    ) -> ServiceResult:
        """
        Get currently active announcements.
        
        Args:
            user_context: User context
            page: Page number
            page_size: Items per page
            
        Returns:
            ServiceResult with active announcements
        """
        try:
            from app.repositories.base.pagination import PaginationParams
            
            pagination = PaginationParams(page=page, page_size=page_size)
            
            result = self.repository.find_active_by_hostel(
                hostel_id=user_context.hostel_id,
                pagination=pagination
            )
            
            return ServiceResult.ok(data={
                'items': [self._serialize_announcement(a, False) for a in result.items],
                'total': result.total,
                'page': result.page,
                'page_size': result.page_size,
                'total_pages': result.total_pages,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_FAILED")
    
    def search_announcements(
        self,
        search_term: str,
        user_context: UserContext,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> ServiceResult:
        """
        Full-text search announcements.
        
        Args:
            search_term: Search query
            user_context: User context
            filters: Additional filters
            page: Page number
            page_size: Items per page
            
        Returns:
            ServiceResult with search results
        """
        try:
            from app.repositories.base.pagination import PaginationParams
            from app.repositories.base.filtering import FilterCriteria
            
            # Validate search term
            if not search_term or len(search_term) < 2:
                return ServiceResult.fail(
                    "Search term must be at least 2 characters",
                    error_code="INVALID_SEARCH"
                )
            
            filter_criteria = FilterCriteria()
            if filters:
                # Apply filters similar to list_announcements
                pass
            
            pagination = PaginationParams(page=page, page_size=page_size)
            
            result = self.repository.search_announcements(
                hostel_id=user_context.hostel_id,
                search_term=search_term,
                filters=filter_criteria,
                pagination=pagination
            )
            
            return ServiceResult.ok(data={
                'items': [self._serialize_announcement(a, False) for a in result.items],
                'total': result.total,
                'page': result.page,
                'page_size': result.page_size,
                'total_pages': result.total_pages,
                'search_term': search_term,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="SEARCH_FAILED")
    
    # ==================== Update Operations ====================
    
    def update_announcement(
        self,
        announcement_id: UUID,
        dto: UpdateAnnouncementDTO,
        user_context: UserContext
    ) -> ServiceResult:
        """
        Update announcement content.
        
        Args:
            announcement_id: Announcement UUID
            dto: Update data
            user_context: User context
            
        Returns:
            ServiceResult with updated announcement
        """
        try:
            # Fetch announcement
            announcement = self.repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Permission check
            if announcement.hostel_id != user_context.hostel_id:
                return ServiceResult.fail(
                    "Access denied",
                    error_code="PERMISSION_DENIED"
                )
            
            # Creator or admin can update
            if announcement.created_by_id != user_context.user_id and user_context.role != 'admin':
                return ServiceResult.fail(
                    "Only creator or admin can update announcement",
                    error_code="PERMISSION_DENIED"
                )
            
            # Cannot update published announcements
            if announcement.is_published:
                return ServiceResult.fail(
                    "Cannot update published announcement",
                    error_code="INVALID_STATE"
                )
            
            # Update content
            if dto.title or dto.content:
                announcement = self.repository.update_content(
                    announcement_id=announcement_id,
                    title=dto.title,
                    content=dto.content,
                    modified_by_id=user_context.user_id,
                    change_summary="Manual update"
                )
            
            # Update other fields
            update_data = dto.dict(exclude_unset=True, exclude={'title', 'content'})
            for field, value in update_data.items():
                if hasattr(announcement, field):
                    setattr(announcement, field, value)
            
            announcement.updated_at = datetime.utcnow()
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('announcement.updated', {
                'announcement_id': str(announcement_id),
                'updated_by': str(user_context.user_id),
                'fields_updated': list(update_data.keys()),
            })
            
            # Invalidate cache
            self.cache.delete(f"announcement:{announcement_id}")
            
            return ServiceResult.ok(
                data=self._serialize_announcement(announcement),
                announcement_id=str(announcement_id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="UPDATE_FAILED")
    
    def publish_announcement(
        self,
        announcement_id: UUID,
        dto: Optional[PublishAnnouncementDTO],
        user_context: UserContext
    ) -> ServiceResult:
        """
        Publish announcement immediately or schedule for later.
        
        Args:
            announcement_id: Announcement UUID
            dto: Publication settings
            user_context: User context
            
        Returns:
            ServiceResult with publication status
        """
        try:
            # Fetch announcement
            announcement = self.repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Permission check
            if not user_context.can_publish_announcement():
                return ServiceResult.fail(
                    "Insufficient permissions to publish",
                    error_code="PERMISSION_DENIED"
                )
            
            if announcement.hostel_id != user_context.hostel_id:
                return ServiceResult.fail(
                    "Access denied",
                    error_code="PERMISSION_DENIED"
                )
            
            # Check if requires approval
            if announcement.requires_approval:
                from app.repositories.announcement import AnnouncementApprovalRepository
                approval_repo = AnnouncementApprovalRepository(self.session)
                approval = approval_repo.find_by_announcement(announcement_id)
                
                if not approval or approval.approval_status != 'approved':
                    return ServiceResult.fail(
                        "Announcement requires approval before publishing",
                        error_code="APPROVAL_REQUIRED"
                    )
            
            # Determine publication method
            scheduled_for = dto.scheduled_for if dto else None
            
            if scheduled_for:
                # Schedule for later
                announcement = self.repository.publish_announcement(
                    announcement_id=announcement_id,
                    published_by_id=user_context.user_id,
                    scheduled_for=scheduled_for
                )
                
                self.session.commit()
                
                self.event_publisher.publish('announcement.scheduled', {
                    'announcement_id': str(announcement_id),
                    'scheduled_for': scheduled_for.isoformat(),
                    'scheduled_by': str(user_context.user_id),
                })
                
                return ServiceResult.ok(
                    data={'status': 'scheduled', 'scheduled_for': scheduled_for},
                    announcement_id=str(announcement_id)
                )
            else:
                # Publish immediately
                announcement = self.repository.publish_announcement(
                    announcement_id=announcement_id,
                    published_by_id=user_context.user_id
                )
                
                # Initialize delivery
                delivery_result = self.aggregate_repository.initialize_delivery(
                    announcement_id=announcement_id
                )
                
                self.session.commit()
                
                self.event_publisher.publish('announcement.published', {
                    'announcement_id': str(announcement_id),
                    'title': announcement.title,
                    'published_by': str(user_context.user_id),
                    'total_recipients': delivery_result['total_recipients'],
                    'channels': delivery_result['channels'],
                })
                
                return ServiceResult.ok(
                    data={
                        'status': 'published',
                        'published_at': announcement.published_at,
                        'delivery': delivery_result,
                    },
                    announcement_id=str(announcement_id)
                )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="PUBLISH_FAILED")
    
    def unpublish_announcement(
        self,
        announcement_id: UUID,
        reason: Optional[str],
        user_context: UserContext
    ) -> ServiceResult:
        """
        Unpublish (retract) announcement.
        
        Args:
            announcement_id: Announcement UUID
            reason: Unpublish reason
            user_context: User context
            
        Returns:
            ServiceResult
        """
        try:
            announcement = self.repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Permission check - only admin
            if user_context.role != 'admin':
                return ServiceResult.fail(
                    "Only admin can unpublish announcements",
                    error_code="PERMISSION_DENIED"
                )
            
            announcement = self.repository.unpublish_announcement(
                announcement_id=announcement_id,
                reason=reason
            )
            
            self.session.commit()
            
            self.event_publisher.publish('announcement.unpublished', {
                'announcement_id': str(announcement_id),
                'unpublished_by': str(user_context.user_id),
                'reason': reason,
            })
            
            return ServiceResult.ok(
                data={'status': 'unpublished'},
                announcement_id=str(announcement_id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="UNPUBLISH_FAILED")
    
    def pin_announcement(
        self,
        announcement_id: UUID,
        pinned: bool,
        user_context: UserContext
    ) -> ServiceResult:
        """
        Pin or unpin announcement.
        
        Args:
            announcement_id: Announcement UUID
            pinned: Pin status
            user_context: User context
            
        Returns:
            ServiceResult
        """
        try:
            announcement = self.repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            if announcement.hostel_id != user_context.hostel_id:
                return ServiceResult.fail(
                    "Access denied",
                    error_code="PERMISSION_DENIED"
                )
            
            announcement = self.repository.pin_announcement(
                announcement_id=announcement_id,
                pinned=pinned
            )
            
            self.session.commit()
            
            self.event_publisher.publish(
                'announcement.pinned' if pinned else 'announcement.unpinned',
                {
                    'announcement_id': str(announcement_id),
                    'actioned_by': str(user_context.user_id),
                }
            )
            
            return ServiceResult.ok(
                data={'is_pinned': pinned},
                announcement_id=str(announcement_id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="PIN_FAILED")
    
    def mark_urgent(
        self,
        announcement_id: UUID,
        urgent: bool,
        user_context: UserContext
    ) -> ServiceResult:
        """
        Mark announcement as urgent or normal.
        
        Args:
            announcement_id: Announcement UUID
            urgent: Urgent status
            user_context: User context
            
        Returns:
            ServiceResult
        """
        try:
            announcement = self.repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            if announcement.hostel_id != user_context.hostel_id:
                return ServiceResult.fail(
                    "Access denied",
                    error_code="PERMISSION_DENIED"
                )
            
            announcement = self.repository.mark_urgent(
                announcement_id=announcement_id,
                urgent=urgent
            )
            
            self.session.commit()
            
            return ServiceResult.ok(
                data={'is_urgent': urgent},
                announcement_id=str(announcement_id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="UPDATE_FAILED")
    
    # ==================== Delete/Archive Operations ====================
    
    def archive_announcement(
        self,
        announcement_id: UUID,
        dto: ArchiveAnnouncementDTO,
        user_context: UserContext
    ) -> ServiceResult:
        """
        Archive announcement.
        
        Args:
            announcement_id: Announcement UUID
            dto: Archive data
            user_context: User context
            
        Returns:
            ServiceResult
        """
        try:
            announcement = self.repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            if announcement.hostel_id != user_context.hostel_id:
                return ServiceResult.fail(
                    "Access denied",
                    error_code="PERMISSION_DENIED"
                )
            
            announcement = self.repository.archive_announcement(
                announcement_id=announcement_id,
                archived_by_id=user_context.user_id,
                reason=dto.reason
            )
            
            self.session.commit()
            
            self.event_publisher.publish('announcement.archived', {
                'announcement_id': str(announcement_id),
                'archived_by': str(user_context.user_id),
                'reason': dto.reason,
            })
            
            return ServiceResult.ok(
                data={'status': 'archived'},
                announcement_id=str(announcement_id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="ARCHIVE_FAILED")
    
    def delete_announcement(
        self,
        announcement_id: UUID,
        user_context: UserContext,
        permanent: bool = False
    ) -> ServiceResult:
        """
        Delete announcement (soft or hard).
        
        Args:
            announcement_id: Announcement UUID
            user_context: User context
            permanent: Permanent deletion flag
            
        Returns:
            ServiceResult
        """
        try:
            announcement = self.repository.find_by_id(announcement_id, include_deleted=True)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Only admin can delete
            if user_context.role != 'admin':
                return ServiceResult.fail(
                    "Only admin can delete announcements",
                    error_code="PERMISSION_DENIED"
                )
            
            if permanent:
                # Hard delete
                self.repository.delete(announcement)
            else:
                # Soft delete
                self.repository.soft_delete(announcement)
            
            self.session.commit()
            
            self.event_publisher.publish('announcement.deleted', {
                'announcement_id': str(announcement_id),
                'deleted_by': str(user_context.user_id),
                'permanent': permanent,
            })
            
            return ServiceResult.ok(
                data={'status': 'deleted', 'permanent': permanent},
                announcement_id=str(announcement_id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="DELETE_FAILED")
    
    # ==================== Bulk Operations ====================
    
    def bulk_action(
        self,
        dto: BulkActionDTO,
        user_context: UserContext
    ) -> ServiceResult:
        """
        Perform bulk action on multiple announcements.
        
        Args:
            dto: Bulk action data
            user_context: User context
            
        Returns:
            ServiceResult with operation results
        """
        try:
            results = {
                'success': [],
                'failed': [],
            }
            
            for announcement_id in dto.announcement_ids:
                try:
                    if dto.action == 'archive':
                        result = self.archive_announcement(
                            announcement_id,
                            ArchiveAnnouncementDTO(),
                            user_context
                        )
                    elif dto.action == 'delete':
                        result = self.delete_announcement(
                            announcement_id,
                            user_context
                        )
                    elif dto.action == 'pin':
                        result = self.pin_announcement(
                            announcement_id,
                            True,
                            user_context
                        )
                    elif dto.action == 'unpin':
                        result = self.pin_announcement(
                            announcement_id,
                            False,
                            user_context
                        )
                    else:
                        continue
                    
                    if result.success:
                        results['success'].append(str(announcement_id))
                    else:
                        results['failed'].append({
                            'id': str(announcement_id),
                            'error': result.error
                        })
                        
                except Exception as e:
                    results['failed'].append({
                        'id': str(announcement_id),
                        'error': str(e)
                    })
            
            return ServiceResult.ok(data=results)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="BULK_ACTION_FAILED")
    
    # ==================== Analytics & Reports ====================
    
    def get_announcement_statistics(
        self,
        user_context: UserContext,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ServiceResult:
        """
        Get announcement statistics for hostel.
        
        Args:
            user_context: User context
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            ServiceResult with statistics
        """
        try:
            stats = self.repository.get_announcement_statistics(
                hostel_id=user_context.hostel_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return ServiceResult.ok(data=stats)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="STATS_FAILED")
    
    def get_dashboard_metrics(
        self,
        user_context: UserContext
    ) -> ServiceResult:
        """
        Get real-time dashboard metrics.
        
        Args:
            user_context: User context
            
        Returns:
            ServiceResult with dashboard data
        """
        try:
            metrics = self.aggregate_repository.get_hostel_dashboard_metrics(
                hostel_id=user_context.hostel_id
            )
            
            return ServiceResult.ok(data=metrics)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="METRICS_FAILED")
    
    def get_performance_report(
        self,
        announcement_id: UUID,
        user_context: UserContext
    ) -> ServiceResult:
        """
        Get detailed performance report for announcement.
        
        Args:
            announcement_id: Announcement UUID
            user_context: User context
            
        Returns:
            ServiceResult with performance data
        """
        try:
            announcement = self.repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            if announcement.hostel_id != user_context.hostel_id:
                return ServiceResult.fail(
                    "Access denied",
                    error_code="PERMISSION_DENIED"
                )
            
            metrics = self.repository.get_performance_metrics(announcement_id)
            
            return ServiceResult.ok(data=metrics)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="REPORT_FAILED")
    
    # ==================== Helper Methods ====================
    
    def _validate_creation(
        self,
        dto: CreateAnnouncementDTO,
        user_context: UserContext
    ) -> ServiceResult:
        """Validate announcement creation."""
        # Additional business validation
        if dto.requires_approval and not user_context.can_approve_announcement():
            # Supervisor creating announcement requiring approval is OK
            pass
        
        # Validate targeting
        if dto.target_audience == TargetAudience.SPECIFIC_ROOMS:
            if not dto.target_room_ids:
                return ServiceResult.fail(
                    "Room IDs required for room-specific targeting",
                    error_code="INVALID_TARGETING"
                )
        
        return ServiceResult.ok()
    
    def _serialize_announcement(
        self,
        announcement,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """Serialize announcement to dictionary."""
        data = {
            'id': str(announcement.id),
            'hostel_id': str(announcement.hostel_id),
            'title': announcement.title,
            'content': announcement.content,
            'category': announcement.category.value,
            'priority': announcement.priority.value,
            'status': announcement.status.value,
            'is_urgent': announcement.is_urgent,
            'is_pinned': announcement.is_pinned,
            'is_published': announcement.is_published,
            'is_archived': announcement.is_archived,
            'is_active': announcement.is_active,
            'is_expired': announcement.is_expired,
            'requires_acknowledgment': announcement.requires_acknowledgment,
            'total_recipients': announcement.total_recipients,
            'read_count': announcement.read_count,
            'acknowledged_count': announcement.acknowledged_count,
            'engagement_rate': float(announcement.engagement_rate),
            'read_percentage': announcement.read_percentage,
            'acknowledgment_percentage': announcement.acknowledgment_percentage,
            'created_at': announcement.created_at.isoformat(),
            'updated_at': announcement.updated_at.isoformat() if announcement.updated_at else None,
            'published_at': announcement.published_at.isoformat() if announcement.published_at else None,
            'expires_at': announcement.expires_at.isoformat() if announcement.expires_at else None,
        }
        
        if include_details:
            data.update({
                'created_by': {
                    'id': str(announcement.created_by.id),
                    'name': announcement.created_by.full_name,
                } if announcement.created_by else None,
                'target_audience': announcement.target_audience.value,
                'send_email': announcement.send_email,
                'send_sms': announcement.send_sms,
                'send_push': announcement.send_push,
                'metadata': announcement.metadata,
            })
        
        return data
    
    def _invalidate_announcement_caches(self, hostel_id: UUID):
        """Invalidate announcement-related caches."""
        self.cache.delete_pattern(f"announcements:hostel:{hostel_id}:*")