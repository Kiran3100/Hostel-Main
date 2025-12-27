"""
Announcement Scheduling Repository

Advanced scheduling with recurring patterns, queue management, and execution tracking.
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import pytz

from sqlalchemy import and_, or_, func, select, case
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import Select

from app.models.announcement import (
    AnnouncementSchedule,
    RecurringAnnouncement,
    ScheduleExecution,
    PublishQueue,
    Announcement,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.core1.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)


class AnnouncementSchedulingRepository(BaseRepository[AnnouncementSchedule]):
    """
    Repository for announcement scheduling.
    
    Provides comprehensive scheduling capabilities including:
    - One-time and recurring schedules
    - Timezone-aware scheduling
    - Queue management
    - Execution tracking
    - SLA monitoring
    - Auto-expiry management
    """
    
    def __init__(self, session: Session):
        super().__init__(AnnouncementSchedule, session)
    
    # ==================== Schedule Management ====================
    
    def create_schedule(
        self,
        announcement_id: UUID,
        scheduled_by_id: UUID,
        publish_at: datetime,
        timezone: str = 'UTC',
        auto_expire: bool = False,
        expire_after_hours: Optional[int] = None,
        **kwargs
    ) -> AnnouncementSchedule:
        """
        Create announcement schedule.
        
        Args:
            announcement_id: Announcement UUID
            scheduled_by_id: User creating schedule
            publish_at: Publication datetime
            timezone: Timezone for scheduling
            auto_expire: Enable auto-expiry
            expire_after_hours: Hours until expiry
            **kwargs: Additional schedule parameters
            
        Returns:
            Created schedule
        """
        # Validate timezone
        try:
            tz = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            raise ValidationError(f"Invalid timezone: {timezone}")
        
        # Calculate expiry if auto-expire enabled
        calculated_expire_at = None
        if auto_expire and expire_after_hours:
            calculated_expire_at = publish_at + timedelta(hours=expire_after_hours)
        
        # Calculate SLA deadline (default 1 hour before publish)
        sla_deadline = publish_at - timedelta(hours=1)
        
        schedule = AnnouncementSchedule(
            announcement_id=announcement_id,
            scheduled_by_id=scheduled_by_id,
            scheduled_publish_at=publish_at,
            timezone=timezone,
            auto_expire=auto_expire,
            expire_after_hours=expire_after_hours,
            calculated_expire_at=calculated_expire_at,
            next_publish_at=publish_at,
            sla_deadline=sla_deadline,
            **kwargs
        )
        
        self.session.add(schedule)
        self.session.flush()
        
        # Add to publish queue
        self._add_to_publish_queue(schedule)
        
        return schedule
    
    def create_recurring_schedule(
        self,
        announcement_id: UUID,
        scheduled_by_id: UUID,
        first_publish_at: datetime,
        recurrence_pattern: str,
        timezone: str = 'UTC',
        end_date: Optional[datetime] = None,
        max_occurrences: Optional[int] = None,
        **kwargs
    ) -> AnnouncementSchedule:
        """
        Create recurring announcement schedule.
        
        Args:
            announcement_id: Announcement UUID
            scheduled_by_id: User creating schedule
            first_publish_at: First publication datetime
            recurrence_pattern: Pattern (daily, weekly, monthly)
            timezone: Timezone for scheduling
            end_date: When recurrence ends
            max_occurrences: Maximum occurrences
            **kwargs: Additional parameters
            
        Returns:
            Created recurring schedule
        """
        if recurrence_pattern not in ['daily', 'weekly', 'biweekly', 'monthly']:
            raise ValidationError(f"Invalid recurrence pattern: {recurrence_pattern}")
        
        if not end_date and not max_occurrences:
            raise ValidationError(
                "Either end_date or max_occurrences must be specified"
            )
        
        schedule = self.create_schedule(
            announcement_id=announcement_id,
            scheduled_by_id=scheduled_by_id,
            publish_at=first_publish_at,
            timezone=timezone,
            is_recurring=True,
            recurrence_pattern=recurrence_pattern,
            recurrence_end_date=end_date,
            max_occurrences=max_occurrences,
            **kwargs
        )
        
        return schedule
    
    def update_schedule(
        self,
        schedule_id: UUID,
        new_publish_at: Optional[datetime] = None,
        **updates
    ) -> AnnouncementSchedule:
        """
        Update scheduled announcement.
        
        Args:
            schedule_id: Schedule UUID
            new_publish_at: New publication time
            **updates: Additional field updates
            
        Returns:
            Updated schedule
        """
        schedule = self.find_by_id(schedule_id)
        if not schedule:
            raise ResourceNotFoundError(f"Schedule {schedule_id} not found")
        
        if schedule.status != 'pending':
            raise BusinessLogicError(
                f"Cannot update schedule in {schedule.status} status"
            )
        
        if new_publish_at:
            schedule.scheduled_publish_at = new_publish_at
            schedule.next_publish_at = new_publish_at
            
            # Update queue
            self._update_publish_queue(schedule)
        
        # Apply other updates
        for key, value in updates.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)
        
        self.session.flush()
        return schedule
    
    def cancel_schedule(
        self,
        schedule_id: UUID,
        cancelled_by_id: UUID,
        reason: Optional[str] = None
    ) -> AnnouncementSchedule:
        """
        Cancel scheduled announcement.
        
        Args:
            schedule_id: Schedule UUID
            cancelled_by_id: User cancelling
            reason: Cancellation reason
            
        Returns:
            Cancelled schedule
        """
        schedule = self.find_by_id(schedule_id)
        if not schedule:
            raise ResourceNotFoundError(f"Schedule {schedule_id} not found")
        
        if schedule.status == 'published':
            raise BusinessLogicError("Cannot cancel already published schedule")
        
        schedule.is_cancelled = True
        schedule.cancelled_at = datetime.utcnow()
        schedule.cancelled_by_id = cancelled_by_id
        schedule.cancellation_reason = reason
        schedule.status = 'cancelled'
        
        # Remove from publish queue
        self._remove_from_publish_queue(schedule.announcement_id)
        
        self.session.flush()
        return schedule
    
    # ==================== Recurring Announcements ====================
    
    def create_recurring_announcement(
        self,
        hostel_id: UUID,
        created_by_id: UUID,
        title_template: str,
        content_template: str,
        recurrence_pattern: str,
        publish_time: time,
        start_date: datetime,
        timezone: str = 'UTC',
        **kwargs
    ) -> RecurringAnnouncement:
        """
        Create recurring announcement template.
        
        Args:
            hostel_id: Hostel UUID
            created_by_id: Creator user UUID
            title_template: Title template
            content_template: Content template
            recurrence_pattern: Recurrence pattern
            publish_time: Time of day to publish
            start_date: Start date
            timezone: Timezone
            **kwargs: Additional parameters
            
        Returns:
            Created recurring announcement
        """
        recurring = RecurringAnnouncement(
            hostel_id=hostel_id,
            created_by_id=created_by_id,
            title_template=title_template,
            content_template=content_template,
            recurrence_pattern=recurrence_pattern,
            publish_time=publish_time,
            start_date=start_date,
            timezone=timezone,
            **kwargs
        )
        
        # Calculate next publish time
        recurring.next_publish_at = self._calculate_next_occurrence(
            start_date, publish_time, recurrence_pattern, timezone
        )
        
        self.session.add(recurring)
        self.session.flush()
        
        return recurring
    
    def process_due_recurring_announcements(
        self,
        batch_size: int = 50
    ) -> List[Announcement]:
        """
        Process recurring announcements that are due.
        
        Args:
            batch_size: Maximum to process
            
        Returns:
            List of created announcements
        """
        now = datetime.utcnow()
        
        # Find due recurring announcements
        due_recurring = (
            self.session.query(RecurringAnnouncement)
            .filter(
                RecurringAnnouncement.is_active == True,
                RecurringAnnouncement.is_paused == False,
                RecurringAnnouncement.next_publish_at <= now
            )
            .limit(batch_size)
            .all()
        )
        
        created_announcements = []
        
        for recurring in due_recurring:
            # Create announcement from template
            announcement = self._create_from_recurring_template(recurring)
            created_announcements.append(announcement)
            
            # Update recurring announcement
            recurring.total_published += 1
            recurring.last_published_at = now
            
            # Calculate next occurrence
            if self._should_continue_recurrence(recurring):
                recurring.next_publish_at = self._calculate_next_occurrence(
                    recurring.next_publish_at,
                    recurring.publish_time,
                    recurring.recurrence_pattern,
                    recurring.timezone
                )
            else:
                # End of recurrence
                recurring.is_active = False
                recurring.next_publish_at = None
            
            # Track generated announcement
            if not recurring.generated_announcement_ids:
                recurring.generated_announcement_ids = []
            recurring.generated_announcement_ids.append(announcement.id)
        
        self.session.flush()
        return created_announcements
    
    # ==================== Queue Management ====================
    
    def get_pending_publications(
        self,
        limit: int = 100,
        priority_threshold: int = 0
    ) -> List[PublishQueue]:
        """
        Get pending publications from queue.
        
        Args:
            limit: Maximum items to return
            priority_threshold: Minimum priority level
            
        Returns:
            List of queue items
        """
        now = datetime.utcnow()
        
        query = (
            select(PublishQueue)
            .where(
                PublishQueue.status == 'pending',
                PublishQueue.scheduled_publish_at <= now,
                PublishQueue.priority >= priority_threshold
            )
            .order_by(
                PublishQueue.is_urgent.desc(),
                PublishQueue.priority.desc(),
                PublishQueue.scheduled_publish_at.asc()
            )
            .limit(limit)
        )
        
        # Check for expired locks
        query = query.where(
            or_(
                PublishQueue.lock_expires_at.is_(None),
                PublishQueue.lock_expires_at < now
            )
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def acquire_queue_lock(
        self,
        queue_id: UUID,
        worker_id: str,
        lock_duration_minutes: int = 5
    ) -> Optional[PublishQueue]:
        """
        Acquire lock on queue item for processing.
        
        Args:
            queue_id: Queue item UUID
            worker_id: Worker identifier
            lock_duration_minutes: Lock duration
            
        Returns:
            Locked queue item or None if already locked
        """
        queue_item = self.session.get(PublishQueue, queue_id)
        if not queue_item:
            return None
        
        now = datetime.utcnow()
        
        # Check if already locked by another worker
        if queue_item.lock_expires_at and queue_item.lock_expires_at > now:
            if queue_item.worker_id != worker_id:
                return None
        
        # Acquire lock
        queue_item.worker_id = worker_id
        queue_item.lock_acquired_at = now
        queue_item.lock_expires_at = now + timedelta(minutes=lock_duration_minutes)
        queue_item.status = 'processing'
        queue_item.processing_started_at = now
        
        self.session.flush()
        return queue_item
    
    def complete_queue_item(
        self,
        queue_id: UUID,
        success: bool = True,
        error: Optional[str] = None
    ) -> PublishQueue:
        """
        Mark queue item as completed.
        
        Args:
            queue_id: Queue item UUID
            success: Whether processing succeeded
            error: Error message if failed
            
        Returns:
            Updated queue item
        """
        queue_item = self.session.get(PublishQueue, queue_id)
        if not queue_item:
            raise ResourceNotFoundError(f"Queue item {queue_id} not found")
        
        now = datetime.utcnow()
        
        if success:
            queue_item.status = 'completed'
            queue_item.processing_completed_at = now
        else:
            queue_item.status = 'failed'
            queue_item.last_error = error
            
            # Add to error history
            if not queue_item.error_history:
                queue_item.error_history = []
            queue_item.error_history.append({
                'timestamp': now.isoformat(),
                'error': error,
                'retry_count': queue_item.retry_count
            })
            
            # Schedule retry if under limit
            if queue_item.retry_count < queue_item.max_retries:
                queue_item.retry_count += 1
                retry_delay = self._calculate_retry_delay(queue_item.retry_count)
                queue_item.next_retry_at = now + retry_delay
                queue_item.status = 'pending'
        
        # Release lock
        queue_item.worker_id = None
        queue_item.lock_acquired_at = None
        queue_item.lock_expires_at = None
        
        self.session.flush()
        return queue_item
    
    # ==================== Execution Tracking ====================
    
    def record_execution(
        self,
        schedule_id: UUID,
        announcement_id: UUID,
        scheduled_for: datetime,
        status: str,
        published: bool = False,
        recipients_count: int = 0,
        error_message: Optional[str] = None
    ) -> ScheduleExecution:
        """
        Record schedule execution.
        
        Args:
            schedule_id: Schedule UUID
            announcement_id: Announcement UUID
            scheduled_for: Scheduled time
            status: Execution status
            published: Whether published
            recipients_count: Number of recipients
            error_message: Error if failed
            
        Returns:
            Created execution record
        """
        start_time = datetime.utcnow()
        
        execution = ScheduleExecution(
            schedule_id=schedule_id,
            announcement_id=announcement_id,
            scheduled_for=scheduled_for,
            executed_at=start_time,
            status=status,
            published=published,
            recipients_count=recipients_count,
            error_message=error_message
        )
        
        self.session.add(execution)
        self.session.flush()
        
        # Update schedule
        schedule = self.session.get(AnnouncementSchedule, schedule_id)
        if schedule:
            schedule.last_executed_at = start_time
            schedule.execution_count += 1
            
            if status == 'failed':
                schedule.failure_count += 1
                schedule.last_failure_at = start_time
                schedule.last_failure_reason = error_message
            
            if published and schedule.is_recurring:
                schedule.occurrences_completed += 1
                
                # Calculate next occurrence
                if self._should_continue_schedule(schedule):
                    schedule.next_publish_at = self._calculate_next_occurrence(
                        schedule.next_publish_at,
                        schedule.scheduled_publish_at.time(),
                        schedule.recurrence_pattern,
                        schedule.timezone
                    )
                else:
                    schedule.status = 'completed'
        
        self.session.flush()
        return execution
    
    def get_execution_history(
        self,
        schedule_id: UUID,
        limit: int = 50
    ) -> List[ScheduleExecution]:
        """
        Get execution history for schedule.
        
        Args:
            schedule_id: Schedule UUID
            limit: Maximum records
            
        Returns:
            List of execution records
        """
        query = (
            select(ScheduleExecution)
            .where(ScheduleExecution.schedule_id == schedule_id)
            .order_by(ScheduleExecution.executed_at.desc())
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    # ==================== SLA Monitoring ====================
    
    def check_sla_breaches(
        self,
        hostel_id: Optional[UUID] = None
    ) -> List[AnnouncementSchedule]:
        """
        Find schedules that have breached SLA.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of schedules with SLA breach
        """
        now = datetime.utcnow()
        
        query = (
            select(AnnouncementSchedule)
            .join(Announcement)
            .where(
                AnnouncementSchedule.status == 'pending',
                AnnouncementSchedule.sla_deadline < now,
                AnnouncementSchedule.sla_breached == False
            )
        )
        
        if hostel_id:
            query = query.where(Announcement.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        breached_schedules = list(result.scalars().all())
        
        # Mark as breached
        for schedule in breached_schedules:
            schedule.sla_breached = True
        
        self.session.flush()
        return breached_schedules
    
    # ==================== Query Operations ====================
    
    def find_by_announcement(
        self,
        announcement_id: UUID
    ) -> Optional[AnnouncementSchedule]:
        """Find schedule for announcement."""
        return (
            self.session.query(AnnouncementSchedule)
            .filter(AnnouncementSchedule.announcement_id == announcement_id)
            .first()
        )
    
    def find_upcoming_schedules(
        self,
        hostel_id: UUID,
        hours_ahead: int = 24,
        limit: int = 50
    ) -> List[AnnouncementSchedule]:
        """
        Find upcoming scheduled announcements.
        
        Args:
            hostel_id: Hostel UUID
            hours_ahead: Hours to look ahead
            limit: Maximum results
            
        Returns:
            List of upcoming schedules
        """
        now = datetime.utcnow()
        end_time = now + timedelta(hours=hours_ahead)
        
        query = (
            select(AnnouncementSchedule)
            .join(Announcement)
            .where(
                Announcement.hostel_id == hostel_id,
                AnnouncementSchedule.status == 'pending',
                AnnouncementSchedule.next_publish_at.between(now, end_time)
            )
            .order_by(AnnouncementSchedule.next_publish_at.asc())
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_recurring_announcements(
        self,
        hostel_id: UUID,
        active_only: bool = True
    ) -> List[RecurringAnnouncement]:
        """Find recurring announcement templates."""
        query = (
            select(RecurringAnnouncement)
            .where(RecurringAnnouncement.hostel_id == hostel_id)
        )
        
        if active_only:
            query = query.where(RecurringAnnouncement.is_active == True)
        
        query = query.order_by(RecurringAnnouncement.next_publish_at.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    # ==================== Helper Methods ====================
    
    def _add_to_publish_queue(
        self,
        schedule: AnnouncementSchedule
    ) -> PublishQueue:
        """Add schedule to publish queue."""
        # Check if already in queue
        existing = (
            self.session.query(PublishQueue)
            .filter(PublishQueue.announcement_id == schedule.announcement_id)
            .first()
        )
        
        if existing:
            # Update existing
            existing.scheduled_publish_at = schedule.scheduled_publish_at
            existing.schedule_id = schedule.id
            return existing
        
        # Determine priority
        announcement = self.session.get(Announcement, schedule.announcement_id)
        priority = 10 if announcement.priority.value == 'high' else 5
        
        queue_item = PublishQueue(
            announcement_id=schedule.announcement_id,
            schedule_id=schedule.id,
            scheduled_publish_at=schedule.scheduled_publish_at,
            priority=priority,
            is_urgent=announcement.is_urgent,
        )
        
        self.session.add(queue_item)
        self.session.flush()
        return queue_item
    
    def _update_publish_queue(
        self,
        schedule: AnnouncementSchedule
    ) -> None:
        """Update queue item with new schedule."""
        queue_item = (
            self.session.query(PublishQueue)
            .filter(PublishQueue.announcement_id == schedule.announcement_id)
            .first()
        )
        
        if queue_item:
            queue_item.scheduled_publish_at = schedule.scheduled_publish_at
            self.session.flush()
    
    def _remove_from_publish_queue(
        self,
        announcement_id: UUID
    ) -> None:
        """Remove announcement from publish queue."""
        queue_item = (
            self.session.query(PublishQueue)
            .filter(PublishQueue.announcement_id == announcement_id)
            .first()
        )
        
        if queue_item:
            queue_item.status = 'cancelled'
            self.session.flush()
    
    def _calculate_next_occurrence(
        self,
        current_time: datetime,
        publish_time: time,
        pattern: str,
        timezone_str: str
    ) -> datetime:
        """Calculate next occurrence for recurring pattern."""
        tz = pytz.timezone(timezone_str)
        
        # Localize current time
        if current_time.tzinfo is None:
            current_time = tz.localize(current_time)
        
        # Calculate next occurrence
        if pattern == 'daily':
            next_date = current_time.date() + timedelta(days=1)
        elif pattern == 'weekly':
            next_date = current_time.date() + timedelta(weeks=1)
        elif pattern == 'biweekly':
            next_date = current_time.date() + timedelta(weeks=2)
        elif pattern == 'monthly':
            # Same day next month
            month = current_time.month + 1
            year = current_time.year
            if month > 12:
                month = 1
                year += 1
            try:
                next_date = current_time.date().replace(year=year, month=month)
            except ValueError:
                # Handle day overflow (e.g., Jan 31 -> Feb 28)
                next_date = current_time.date().replace(
                    year=year, month=month, day=1
                ) + timedelta(days=27)
                while next_date.month != month:
                    next_date -= timedelta(days=1)
        else:
            raise ValidationError(f"Invalid recurrence pattern: {pattern}")
        
        # Combine date and time
        next_datetime = tz.localize(
            datetime.combine(next_date, publish_time)
        )
        
        return next_datetime
    
    def _should_continue_recurrence(
        self,
        recurring: RecurringAnnouncement
    ) -> bool:
        """Check if recurrence should continue."""
        # Check end date
        if recurring.end_date:
            if datetime.utcnow() >= recurring.end_date:
                return False
        
        # Check max occurrences
        if recurring.max_occurrences:
            if recurring.total_published >= recurring.max_occurrences:
                return False
        
        return True
    
    def _should_continue_schedule(
        self,
        schedule: AnnouncementSchedule
    ) -> bool:
        """Check if recurring schedule should continue."""
        if not schedule.is_recurring:
            return False
        
        # Check end date
        if schedule.recurrence_end_date:
            if datetime.utcnow() >= schedule.recurrence_end_date:
                return False
        
        # Check max occurrences
        if schedule.max_occurrences:
            if schedule.occurrences_completed >= schedule.max_occurrences:
                return False
        
        return True
    
    def _create_from_recurring_template(
        self,
        recurring: RecurringAnnouncement
    ) -> Announcement:
        """Create announcement from recurring template."""
        from app.models.announcement import Announcement
        
        # Process templates (simple variable substitution)
        now = datetime.utcnow()
        title = recurring.title_template.replace('{date}', now.strftime('%Y-%m-%d'))
        content = recurring.content_template.replace('{date}', now.strftime('%Y-%m-%d'))
        
        announcement = Announcement(
            hostel_id=recurring.hostel_id,
            created_by_id=recurring.created_by_id,
            title=title,
            content=content,
            category=recurring.metadata.get('category', 'general'),
            priority=recurring.metadata.get('priority', 'medium'),
            target_audience=recurring.target_audience,
            target_room_ids=recurring.target_room_ids,
            target_floor_numbers=recurring.target_floor_numbers,
            send_push=recurring.send_push,
            send_email=recurring.send_email,
            send_sms=recurring.send_sms,
            is_published=True,
            published_at=now,
            published_by_id=recurring.created_by_id,
        )
        
        self.session.add(announcement)
        self.session.flush()
        return announcement
    
    def _calculate_retry_delay(self, retry_count: int) -> timedelta:
        """Calculate exponential backoff delay."""
        # Exponential backoff: 2^retry_count minutes
        delay_minutes = 2 ** retry_count
        return timedelta(minutes=min(delay_minutes, 60))  # Max 1 hour