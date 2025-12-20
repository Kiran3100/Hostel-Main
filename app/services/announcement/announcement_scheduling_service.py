"""
Announcement Scheduling Service

Scheduling and timing service providing comprehensive scheduling capabilities
including one-time schedules, recurring patterns, and queue management.
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass
import pytz

from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, Field

from app.repositories.announcement import (
    AnnouncementSchedulingRepository,
    AnnouncementRepository,
)
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)
from app.core.events import EventPublisher
from app.core.tasks import BackgroundTaskManager


# ==================== DTOs ====================

class CreateScheduleDTO(BaseModel):
    """DTO for creating schedule."""
    publish_at: datetime
    timezone: str = "UTC"
    auto_expire: bool = False
    expire_after_hours: Optional[int] = Field(None, ge=1, le=720)  # Max 30 days
    
    @validator('publish_at')
    def validate_publish_time(cls, v):
        if v <= datetime.utcnow():
            raise ValueError('Publication time must be in the future')
        return v
    
    @validator('timezone')
    def validate_timezone(cls, v):
        try:
            pytz.timezone(v)
        except pytz.UnknownTimeZoneError:
            raise ValueError(f'Invalid timezone: {v}')
        return v
    
    @validator('expire_after_hours')
    def validate_expiry(cls, v, values):
        if values.get('auto_expire') and not v:
            raise ValueError('expire_after_hours required when auto_expire is True')
        return v


class CreateRecurringScheduleDTO(BaseModel):
    """DTO for creating recurring schedule."""
    first_publish_at: datetime
    recurrence_pattern: str = Field(..., regex='^(daily|weekly|biweekly|monthly)$')
    timezone: str = "UTC"
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = Field(None, ge=1, le=365)
    weekdays: Optional[List[int]] = Field(None, min_items=1, max_items=7)
    
    @validator('first_publish_at')
    def validate_first_publish(cls, v):
        if v <= datetime.utcnow():
            raise ValueError('First publication time must be in the future')
        return v
    
    @validator('weekdays')
    def validate_weekdays(cls, v):
        if v:
            for day in v:
                if day < 0 or day > 6:
                    raise ValueError('Weekdays must be between 0 (Monday) and 6 (Sunday)')
        return v
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and values.get('first_publish_at'):
            if v <= values['first_publish_at']:
                raise ValueError('End date must be after first publication')
        return v


class UpdateScheduleDTO(BaseModel):
    """DTO for updating schedule."""
    new_publish_at: Optional[datetime] = None
    timezone: Optional[str] = None
    auto_expire: Optional[bool] = None
    expire_after_hours: Optional[int] = None


class CreateRecurringTemplateDTO(BaseModel):
    """DTO for creating recurring announcement template."""
    title_template: str = Field(..., min_length=3, max_length=255)
    content_template: str = Field(..., min_length=10)
    recurrence_pattern: str = Field(..., regex='^(daily|weekly|biweekly|monthly)$')
    publish_time: str = Field(..., regex='^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')  # HH:MM
    start_date: datetime
    timezone: str = "UTC"
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
    target_audience: str = "all"
    target_room_ids: Optional[List[UUID]] = None
    target_floor_numbers: Optional[List[int]] = None
    send_push: bool = True
    send_email: bool = False
    send_sms: bool = False
    metadata: Optional[Dict[str, Any]] = None


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

class AnnouncementSchedulingService:
    """
    Announcement scheduling and timing service.
    
    Provides comprehensive scheduling capabilities including:
    - One-time scheduled publications
    - Recurring announcement patterns
    - Timezone-aware scheduling
    - Queue management
    - Background job coordination
    - SLA monitoring
    - Execution tracking
    """
    
    def __init__(
        self,
        session: Session,
        event_publisher: Optional[EventPublisher] = None,
        task_manager: Optional[BackgroundTaskManager] = None
    ):
        self.session = session
        self.repository = AnnouncementSchedulingRepository(session)
        self.announcement_repository = AnnouncementRepository(session)
        self.event_publisher = event_publisher or EventPublisher()
        self.task_manager = task_manager or BackgroundTaskManager()
    
    # ==================== Schedule Management ====================
    
    def create_schedule(
        self,
        announcement_id: UUID,
        dto: CreateScheduleDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Create schedule for announcement publication.
        
        Args:
            announcement_id: Announcement UUID
            dto: Schedule configuration
            user_id: User creating schedule
            
        Returns:
            ServiceResult with schedule data
        """
        try:
            # Validate announcement
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            if announcement.is_published:
                return ServiceResult.fail(
                    "Cannot schedule already published announcement",
                    error_code="INVALID_STATE"
                )
            
            # Create schedule
            schedule = self.repository.create_schedule(
                announcement_id=announcement_id,
                scheduled_by_id=user_id,
                publish_at=dto.publish_at,
                timezone=dto.timezone,
                auto_expire=dto.auto_expire,
                expire_after_hours=dto.expire_after_hours
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('schedule.created', {
                'schedule_id': str(schedule.id),
                'announcement_id': str(announcement_id),
                'publish_at': dto.publish_at.isoformat(),
                'timezone': dto.timezone,
            })
            
            # Schedule background job
            self._schedule_publication_job(schedule)
            
            return ServiceResult.ok(
                data=self._serialize_schedule(schedule),
                schedule_id=str(schedule.id)
            )
            
        except ValidationError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="VALIDATION_ERROR")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="SCHEDULE_CREATE_FAILED")
    
    def create_recurring_schedule(
        self,
        announcement_id: UUID,
        dto: CreateRecurringScheduleDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Create recurring schedule for announcement.
        
        Args:
            announcement_id: Announcement UUID
            dto: Recurring schedule configuration
            user_id: User creating schedule
            
        Returns:
            ServiceResult with schedule data
        """
        try:
            # Validate
            if not dto.end_date and not dto.max_occurrences:
                return ServiceResult.fail(
                    "Either end_date or max_occurrences must be specified",
                    error_code="VALIDATION_ERROR"
                )
            
            # Create schedule
            schedule = self.repository.create_recurring_schedule(
                announcement_id=announcement_id,
                scheduled_by_id=user_id,
                first_publish_at=dto.first_publish_at,
                recurrence_pattern=dto.recurrence_pattern,
                timezone=dto.timezone,
                end_date=dto.end_date,
                max_occurrences=dto.max_occurrences
            )
            
            self.session.commit()
            
            self.event_publisher.publish('schedule.recurring_created', {
                'schedule_id': str(schedule.id),
                'announcement_id': str(announcement_id),
                'pattern': dto.recurrence_pattern,
                'first_publish_at': dto.first_publish_at.isoformat(),
            })
            
            return ServiceResult.ok(
                data=self._serialize_schedule(schedule),
                schedule_id=str(schedule.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="RECURRING_SCHEDULE_FAILED")
    
    def update_schedule(
        self,
        schedule_id: UUID,
        dto: UpdateScheduleDTO
    ) -> ServiceResult:
        """
        Update existing schedule.
        
        Args:
            schedule_id: Schedule UUID
            dto: Update data
            
        Returns:
            ServiceResult with updated schedule
        """
        try:
            updates = dto.dict(exclude_unset=True)
            
            schedule = self.repository.update_schedule(
                schedule_id=schedule_id,
                **updates
            )
            
            self.session.commit()
            
            self.event_publisher.publish('schedule.updated', {
                'schedule_id': str(schedule_id),
                'updates': list(updates.keys()),
            })
            
            return ServiceResult.ok(
                data=self._serialize_schedule(schedule),
                schedule_id=str(schedule_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except BusinessLogicError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="INVALID_STATE")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="UPDATE_FAILED")
    
    def cancel_schedule(
        self,
        schedule_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> ServiceResult:
        """
        Cancel scheduled announcement.
        
        Args:
            schedule_id: Schedule UUID
            user_id: User cancelling
            reason: Cancellation reason
            
        Returns:
            ServiceResult
        """
        try:
            schedule = self.repository.cancel_schedule(
                schedule_id=schedule_id,
                cancelled_by_id=user_id,
                reason=reason
            )
            
            self.session.commit()
            
            self.event_publisher.publish('schedule.cancelled', {
                'schedule_id': str(schedule_id),
                'cancelled_by': str(user_id),
                'reason': reason,
            })
            
            return ServiceResult.ok(
                data={'status': 'cancelled'},
                schedule_id=str(schedule_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="CANCEL_FAILED")
    
    # ==================== Recurring Templates ====================
    
    def create_recurring_template(
        self,
        hostel_id: UUID,
        dto: CreateRecurringTemplateDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Create recurring announcement template.
        
        Args:
            hostel_id: Hostel UUID
            dto: Template configuration
            user_id: User creating template
            
        Returns:
            ServiceResult with template data
        """
        try:
            # Parse publish time
            hour, minute = map(int, dto.publish_time.split(':'))
            publish_time = time(hour, minute)
            
            # Create template
            recurring = self.repository.create_recurring_announcement(
                hostel_id=hostel_id,
                created_by_id=user_id,
                title_template=dto.title_template,
                content_template=dto.content_template,
                recurrence_pattern=dto.recurrence_pattern,
                publish_time=publish_time,
                start_date=dto.start_date,
                timezone=dto.timezone,
                end_date=dto.end_date,
                max_occurrences=dto.max_occurrences,
                target_audience=dto.target_audience,
                target_room_ids=dto.target_room_ids,
                target_floor_numbers=dto.target_floor_numbers,
                send_push=dto.send_push,
                send_email=dto.send_email,
                send_sms=dto.send_sms,
                metadata=dto.metadata
            )
            
            self.session.commit()
            
            self.event_publisher.publish('recurring_template.created', {
                'template_id': str(recurring.id),
                'hostel_id': str(hostel_id),
                'pattern': dto.recurrence_pattern,
            })
            
            return ServiceResult.ok(
                data=self._serialize_recurring(recurring),
                template_id=str(recurring.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="TEMPLATE_CREATE_FAILED")
    
    def list_recurring_templates(
        self,
        hostel_id: UUID,
        active_only: bool = True
    ) -> ServiceResult:
        """
        List recurring templates for hostel.
        
        Args:
            hostel_id: Hostel UUID
            active_only: Only active templates
            
        Returns:
            ServiceResult with templates
        """
        try:
            templates = self.repository.find_recurring_announcements(
                hostel_id=hostel_id,
                active_only=active_only
            )
            
            return ServiceResult.ok(data={
                'templates': [self._serialize_recurring(t) for t in templates],
                'total': len(templates),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="LIST_FAILED")
    
    def pause_recurring_template(
        self,
        template_id: UUID
    ) -> ServiceResult:
        """
        Pause recurring template.
        
        Args:
            template_id: Template UUID
            
        Returns:
            ServiceResult
        """
        try:
            from app.models.announcement import RecurringAnnouncement
            
            template = self.session.get(RecurringAnnouncement, template_id)
            if not template:
                return ServiceResult.fail(
                    f"Template {template_id} not found",
                    error_code="NOT_FOUND"
                )
            
            template.is_paused = True
            template.paused_at = datetime.utcnow()
            
            self.session.commit()
            
            return ServiceResult.ok(data={'status': 'paused'})
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="PAUSE_FAILED")
    
    def resume_recurring_template(
        self,
        template_id: UUID
    ) -> ServiceResult:
        """
        Resume paused recurring template.
        
        Args:
            template_id: Template UUID
            
        Returns:
            ServiceResult
        """
        try:
            from app.models.announcement import RecurringAnnouncement
            
            template = self.session.get(RecurringAnnouncement, template_id)
            if not template:
                return ServiceResult.fail(
                    f"Template {template_id} not found",
                    error_code="NOT_FOUND"
                )
            
            template.is_paused = False
            template.paused_at = None
            
            self.session.commit()
            
            return ServiceResult.ok(data={'status': 'active'})
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="RESUME_FAILED")
    
    # ==================== Background Processing ====================
    
    def process_due_publications(
        self,
        batch_size: int = 50
    ) -> ServiceResult:
        """
        Process all due scheduled publications (background job).
        
        Args:
            batch_size: Maximum to process
            
        Returns:
            ServiceResult with processing results
        """
        try:
            from app.repositories.announcement import AnnouncementAggregateRepository
            
            aggregate_repo = AnnouncementAggregateRepository(self.session)
            
            result = aggregate_repo.process_scheduled_publications(
                batch_size=batch_size
            )
            
            self.session.commit()
            
            # Publish metrics event
            self.event_publisher.publish('publications.processed', {
                'total_processed': result['total_processed'],
                'published': result['published'],
                'failed': result['failed'],
            })
            
            return ServiceResult.ok(data=result)
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="PROCESSING_FAILED")
    
    def process_recurring_announcements(
        self,
        batch_size: int = 50
    ) -> ServiceResult:
        """
        Process due recurring announcements (background job).
        
        Args:
            batch_size: Maximum to process
            
        Returns:
            ServiceResult with processing results
        """
        try:
            created = self.repository.process_due_recurring_announcements(
                batch_size=batch_size
            )
            
            self.session.commit()
            
            self.event_publisher.publish('recurring.processed', {
                'created_count': len(created),
                'announcements': [str(a.id) for a in created],
            })
            
            return ServiceResult.ok(data={
                'created_count': len(created),
                'announcements': [
                    {
                        'id': str(a.id),
                        'title': a.title,
                        'published_at': a.published_at.isoformat() if a.published_at else None,
                    }
                    for a in created
                ],
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="RECURRING_PROCESSING_FAILED")
    
    # ==================== Queue Management ====================
    
    def get_publish_queue(
        self,
        limit: int = 100,
        priority_threshold: int = 0
    ) -> ServiceResult:
        """
        Get pending publications from queue.
        
        Args:
            limit: Maximum items
            priority_threshold: Minimum priority
            
        Returns:
            ServiceResult with queue items
        """
        try:
            queue_items = self.repository.get_pending_publications(
                limit=limit,
                priority_threshold=priority_threshold
            )
            
            return ServiceResult.ok(data={
                'items': [self._serialize_queue_item(item) for item in queue_items],
                'total': len(queue_items),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="QUEUE_FETCH_FAILED")
    
    # ==================== Monitoring ====================
    
    def get_upcoming_schedules(
        self,
        hostel_id: UUID,
        hours_ahead: int = 24,
        limit: int = 50
    ) -> ServiceResult:
        """
        Get upcoming scheduled announcements.
        
        Args:
            hostel_id: Hostel UUID
            hours_ahead: Hours to look ahead
            limit: Maximum results
            
        Returns:
            ServiceResult with upcoming schedules
        """
        try:
            schedules = self.repository.find_upcoming_schedules(
                hostel_id=hostel_id,
                hours_ahead=hours_ahead,
                limit=limit
            )
            
            return ServiceResult.ok(data={
                'schedules': [self._serialize_schedule(s) for s in schedules],
                'total': len(schedules),
                'hours_ahead': hours_ahead,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_UPCOMING_FAILED")
    
    def check_sla_breaches(
        self,
        hostel_id: Optional[UUID] = None
    ) -> ServiceResult:
        """
        Check for SLA breaches in scheduling.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            ServiceResult with breached schedules
        """
        try:
            breached = self.repository.check_sla_breaches(hostel_id=hostel_id)
            
            if breached:
                self.event_publisher.publish('sla.breached', {
                    'count': len(breached),
                    'schedules': [str(s.id) for s in breached],
                })
            
            return ServiceResult.ok(data={
                'breached_count': len(breached),
                'schedules': [self._serialize_schedule(s) for s in breached],
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="SLA_CHECK_FAILED")
    
    def get_execution_history(
        self,
        schedule_id: UUID,
        limit: int = 50
    ) -> ServiceResult:
        """
        Get execution history for schedule.
        
        Args:
            schedule_id: Schedule UUID
            limit: Maximum records
            
        Returns:
            ServiceResult with execution history
        """
        try:
            history = self.repository.get_execution_history(
                schedule_id=schedule_id,
                limit=limit
            )
            
            return ServiceResult.ok(data={
                'executions': [self._serialize_execution(e) for e in history],
                'total': len(history),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="HISTORY_FETCH_FAILED")
    
    # ==================== Helper Methods ====================
    
    def _schedule_publication_job(self, schedule):
        """Schedule background job for publication."""
        self.task_manager.schedule_task(
            task_name='publish_scheduled_announcement',
            run_at=schedule.next_publish_at,
            params={
                'schedule_id': str(schedule.id),
                'announcement_id': str(schedule.announcement_id),
            }
        )
    
    def _serialize_schedule(self, schedule) -> Dict[str, Any]:
        """Serialize schedule to dictionary."""
        return {
            'id': str(schedule.id),
            'announcement_id': str(schedule.announcement_id),
            'scheduled_publish_at': schedule.scheduled_publish_at.isoformat(),
            'next_publish_at': schedule.next_publish_at.isoformat() if schedule.next_publish_at else None,
            'timezone': schedule.timezone,
            'is_recurring': schedule.is_recurring,
            'recurrence_pattern': schedule.recurrence_pattern,
            'status': schedule.status,
            'execution_count': schedule.execution_count,
            'occurrences_completed': schedule.occurrences_completed,
            'is_cancelled': schedule.is_cancelled,
            'sla_deadline': schedule.sla_deadline.isoformat() if schedule.sla_deadline else None,
            'sla_breached': schedule.sla_breached,
            'created_at': schedule.created_at.isoformat(),
        }
    
    def _serialize_recurring(self, recurring) -> Dict[str, Any]:
        """Serialize recurring template to dictionary."""
        return {
            'id': str(recurring.id),
            'hostel_id': str(recurring.hostel_id),
            'title_template': recurring.title_template,
            'content_template': recurring.content_template,
            'recurrence_pattern': recurring.recurrence_pattern,
            'publish_time': recurring.publish_time.isoformat(),
            'timezone': recurring.timezone,
            'is_active': recurring.is_active,
            'is_paused': recurring.is_paused,
            'next_publish_at': recurring.next_publish_at.isoformat() if recurring.next_publish_at else None,
            'total_published': recurring.total_published,
            'created_at': recurring.created_at.isoformat(),
        }
    
    def _serialize_queue_item(self, item) -> Dict[str, Any]:
        """Serialize queue item to dictionary."""
        return {
            'id': str(item.id),
            'announcement_id': str(item.announcement_id),
            'scheduled_publish_at': item.scheduled_publish_at.isoformat(),
            'priority': item.priority,
            'is_urgent': item.is_urgent,
            'status': item.status,
            'retry_count': item.retry_count,
            'worker_id': item.worker_id,
        }
    
    def _serialize_execution(self, execution) -> Dict[str, Any]:
        """Serialize execution to dictionary."""
        return {
            'id': str(execution.id),
            'schedule_id': str(execution.schedule_id),
            'scheduled_for': execution.scheduled_for.isoformat(),
            'executed_at': execution.executed_at.isoformat(),
            'status': execution.status,
            'published': execution.published,
            'recipients_count': execution.recipients_count,
            'error_message': execution.error_message,
        }