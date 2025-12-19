# Complete Implementation: announcement_tracking_repository.py

Here's the **comprehensive and production-ready** implementation of the announcement tracking repository with all advanced features:

---

## File: announcement_tracking_repository.py

```python
"""
Announcement Tracking Repository

Comprehensive engagement tracking with read receipts, acknowledgments, 
reading time analytics, and behavioral insights.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal
from collections import defaultdict
import statistics

from sqlalchemy import and_, or_, func, select, desc, case, extract
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select

from app.models.announcement import (
    AnnouncementView,
    ReadReceipt,
    Acknowledgment,
    EngagementMetric,
    ReadingTimeAnalytic,
    Announcement,
    AnnouncementRecipient,
)
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)


class AnnouncementTrackingRepository(BaseRepository[AnnouncementView]):
    """
    Repository for announcement engagement tracking.
    
    Provides comprehensive tracking capabilities including:
    - View and reading behavior tracking
    - Read receipt management
    - Acknowledgment processing
    - Real-time engagement metrics
    - Reading time analytics
    - Behavioral pattern analysis
    - Student engagement profiling
    - Performance benchmarking
    """
    
    def __init__(self, session: Session):
        super().__init__(AnnouncementView, session)
    
    # ==================== View Tracking ====================
    
    def record_view(
        self,
        announcement_id: UUID,
        student_id: UUID,
        device_type: Optional[str] = None,
        source: str = "app",
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> AnnouncementView:
        """
        Record a student viewing an announcement.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            device_type: Device type (mobile, web, tablet, desktop)
            source: Access source (app, email, push_notification, web)
            session_id: User session identifier
            ip_address: IP address
            user_agent: User agent string
            metadata: Additional metadata
            
        Returns:
            Created view record
        """
        # Validate device type
        if device_type and device_type not in ['mobile', 'web', 'tablet', 'desktop']:
            raise ValidationError(f"Invalid device type: {device_type}")
        
        # Check if this is a repeat view in same session
        existing_view = None
        if session_id:
            existing_view = (
                self.session.query(AnnouncementView)
                .filter(
                    AnnouncementView.announcement_id == announcement_id,
                    AnnouncementView.student_id == student_id,
                    AnnouncementView.session_id == session_id
                )
                .first()
            )
        
        if existing_view:
            # Increment view count for this session
            existing_view.view_count += 1
            self.session.flush()
            return existing_view
        
        view = AnnouncementView(
            announcement_id=announcement_id,
            student_id=student_id,
            viewed_at=datetime.utcnow(),
            device_type=device_type,
            source=source,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            view_count=1,
            metadata=metadata or {}
        )
        
        self.session.add(view)
        self.session.flush()
        
        return view
    
    def update_reading_metrics(
        self,
        view_id: UUID,
        reading_time_seconds: int,
        scroll_percentage: int,
        clicked_links: bool = False,
        downloaded_attachments: bool = False,
        shared: bool = False
    ) -> AnnouncementView:
        """
        Update reading behavior metrics for a view.
        
        Args:
            view_id: View record UUID
            reading_time_seconds: Time spent reading
            scroll_percentage: Scroll completion percentage
            clicked_links: Whether user clicked links
            downloaded_attachments: Whether user downloaded attachments
            shared: Whether user shared
            
        Returns:
            Updated view record
        """
        view = self.session.get(AnnouncementView, view_id)
        if not view:
            raise ResourceNotFoundError(f"View record {view_id} not found")
        
        # Validate metrics
        if reading_time_seconds < 0 or reading_time_seconds > 3600:
            raise ValidationError("Reading time must be between 0 and 3600 seconds")
        
        if scroll_percentage < 0 or scroll_percentage > 100:
            raise ValidationError("Scroll percentage must be between 0 and 100")
        
        view.reading_time_seconds = reading_time_seconds
        view.scroll_percentage = scroll_percentage
        view.clicked_links = clicked_links
        view.downloaded_attachments = downloaded_attachments
        view.shared = shared
        
        # Auto-create read receipt if user scrolled significantly
        if scroll_percentage >= 90:
            self.mark_as_read(
                announcement_id=view.announcement_id,
                student_id=view.student_id,
                reading_time_seconds=reading_time_seconds,
                scroll_percentage=scroll_percentage,
                device_type=view.device_type,
                source=view.source
            )
        
        self.session.flush()
        return view
    
    def record_engagement_action(
        self,
        view_id: UUID,
        action_type: str,
        action_details: Optional[Dict] = None
    ) -> AnnouncementView:
        """
        Record specific engagement action.
        
        Args:
            view_id: View record UUID
            action_type: Action type (link_click, download, share, etc.)
            action_details: Action details
            
        Returns:
            Updated view record
        """
        view = self.session.get(AnnouncementView, view_id)
        if not view:
            raise ResourceNotFoundError(f"View record {view_id} not found")
        
        # Update flags based on action
        if action_type == 'link_click':
            view.clicked_links = True
        elif action_type == 'download':
            view.downloaded_attachments = True
        elif action_type == 'share':
            view.shared = True
        
        # Store action in metadata
        if not view.metadata:
            view.metadata = {}
        if 'actions' not in view.metadata:
            view.metadata['actions'] = []
        
        view.metadata['actions'].append({
            'type': action_type,
            'timestamp': datetime.utcnow().isoformat(),
            'details': action_details
        })
        
        # Mark as modified for SQLAlchemy to detect JSONB change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(view, 'metadata')
        
        self.session.flush()
        return view
    
    # ==================== Read Receipt Management ====================
    
    def mark_as_read(
        self,
        announcement_id: UUID,
        student_id: UUID,
        reading_time_seconds: Optional[int] = None,
        scroll_percentage: Optional[int] = None,
        device_type: Optional[str] = None,
        source: str = "app"
    ) -> ReadReceipt:
        """
        Confirm that a student has read an announcement.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            reading_time_seconds: Time spent reading
            scroll_percentage: Scroll completion
            device_type: Device used
            source: Access source
            
        Returns:
            Created or updated read receipt
        """
        # Check if receipt already exists
        receipt = (
            self.session.query(ReadReceipt)
            .filter(
                ReadReceipt.announcement_id == announcement_id,
                ReadReceipt.student_id == student_id
            )
            .first()
        )
        
        if receipt:
            # Update existing receipt (in case of re-read)
            if reading_time_seconds:
                receipt.reading_time_seconds = reading_time_seconds
            if scroll_percentage:
                receipt.scroll_percentage = scroll_percentage
            
            # Update completion status
            if scroll_percentage and scroll_percentage >= 90:
                receipt.completed_reading = True
            
            self.session.flush()
            return receipt
        
        # Calculate time from delivery to read
        from app.models.announcement import AnnouncementDelivery
        delivery = (
            self.session.query(AnnouncementDelivery)
            .filter(
                AnnouncementDelivery.announcement_id == announcement_id,
                AnnouncementDelivery.recipient_id == student_id
            )
            .first()
        )
        
        now = datetime.utcnow()
        time_to_read = None
        delivered_at = None
        
        if delivery and delivery.delivered_at:
            delivered_at = delivery.delivered_at
            time_diff = now - delivery.delivered_at
            time_to_read = int(time_diff.total_seconds())
        
        # Create new receipt
        receipt = ReadReceipt(
            announcement_id=announcement_id,
            student_id=student_id,
            read_at=now,
            device_type=device_type,
            source=source,
            reading_time_seconds=reading_time_seconds,
            scroll_percentage=scroll_percentage,
            completed_reading=(scroll_percentage >= 90) if scroll_percentage else False,
            delivered_at=delivered_at,
            time_to_read_seconds=time_to_read,
            is_first_read=True
        )
        
        self.session.add(receipt)
        
        # Update announcement read count
        announcement = self.session.get(Announcement, announcement_id)
        if announcement:
            announcement.read_count += 1
        
        # Update recipient status
        recipient = (
            self.session.query(AnnouncementRecipient)
            .filter(
                AnnouncementRecipient.announcement_id == announcement_id,
                AnnouncementRecipient.student_id == student_id
            )
            .first()
        )
        
        if recipient:
            recipient.is_read = True
            recipient.read_at = now
        
        self.session.flush()
        return receipt
    
    def bulk_mark_as_read(
        self,
        announcement_id: UUID,
        student_ids: List[UUID]
    ) -> int:
        """
        Bulk mark multiple students as having read announcement.
        
        Args:
            announcement_id: Announcement UUID
            student_ids: List of student UUIDs
            
        Returns:
            Number of receipts created
        """
        count = 0
        for student_id in student_ids:
            try:
                self.mark_as_read(announcement_id, student_id)
                count += 1
            except Exception as e:
                # Log error but continue
                print(f"Error marking as read for student {student_id}: {e}")
                continue
        
        return count
    
    # ==================== Acknowledgment Management ====================
    
    def acknowledge_announcement(
        self,
        announcement_id: UUID,
        student_id: UUID,
        acknowledgment_note: Optional[str] = None,
        action_taken: Optional[str] = None,
        device_type: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Acknowledgment:
        """
        Submit student acknowledgment for announcement.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            acknowledgment_note: Optional note from student
            action_taken: Description of action taken
            device_type: Device used
            ip_address: IP address
            
        Returns:
            Created acknowledgment
        """
        announcement = self.session.get(Announcement, announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        if not announcement.requires_acknowledgment:
            raise BusinessLogicError(
                "This announcement does not require acknowledgment"
            )
        
        # Check if already acknowledged
        existing = (
            self.session.query(Acknowledgment)
            .filter(
                Acknowledgment.announcement_id == announcement_id,
                Acknowledgment.student_id == student_id
            )
            .first()
        )
        
        if existing:
            raise BusinessLogicError(
                "Student has already acknowledged this announcement"
            )
        
        # Check if student has read the announcement
        read_receipt = (
            self.session.query(ReadReceipt)
            .filter(
                ReadReceipt.announcement_id == announcement_id,
                ReadReceipt.student_id == student_id
            )
            .first()
        )
        
        # Calculate delivery time
        from app.models.announcement import AnnouncementDelivery
        delivery = (
            self.session.query(AnnouncementDelivery)
            .filter(
                AnnouncementDelivery.announcement_id == announcement_id,
                AnnouncementDelivery.recipient_id == student_id
            )
            .first()
        )
        
        now = datetime.utcnow()
        time_to_ack = None
        delivered_at = None
        
        if delivery and delivery.delivered_at:
            delivered_at = delivery.delivered_at
            time_diff = now - delivery.delivered_at
            time_to_ack = int(time_diff.total_seconds())
        
        # Check if on time
        on_time = True
        if announcement.acknowledgment_deadline:
            on_time = now <= announcement.acknowledgment_deadline
        
        ack = Acknowledgment(
            announcement_id=announcement_id,
            student_id=student_id,
            acknowledged_at=now,
            acknowledgment_note=acknowledgment_note,
            action_taken=action_taken,
            deadline=announcement.acknowledgment_deadline,
            on_time=on_time,
            delivered_at=delivered_at,
            time_to_acknowledge_seconds=time_to_ack,
            read_before_acknowledge=read_receipt is not None,
            read_at=read_receipt.read_at if read_receipt else None,
            ip_address=ip_address,
            device_type=device_type
        )
        
        self.session.add(ack)
        
        # Update announcement acknowledged count
        announcement.acknowledged_count += 1
        
        # Update recipient status
        recipient = (
            self.session.query(AnnouncementRecipient)
            .filter(
                AnnouncementRecipient.announcement_id == announcement_id,
                AnnouncementRecipient.student_id == student_id
            )
            .first()
        )
        
        if recipient:
            recipient.is_acknowledged = True
            recipient.acknowledged_at = now
        
        self.session.flush()
        return ack
    
    def verify_acknowledgment(
        self,
        acknowledgment_id: UUID,
        verified_by_id: UUID,
        verification_notes: Optional[str] = None
    ) -> Acknowledgment:
        """
        Verify acknowledgment (for action-required announcements).
        
        Args:
            acknowledgment_id: Acknowledgment UUID
            verified_by_id: Verifier user UUID
            verification_notes: Verification notes
            
        Returns:
            Updated acknowledgment
        """
        ack = self.session.get(Acknowledgment, acknowledgment_id)
        if not ack:
            raise ResourceNotFoundError(
                f"Acknowledgment {acknowledgment_id} not found"
            )
        
        ack.action_verified = True
        ack.verified_by_id = verified_by_id
        ack.verified_at = datetime.utcnow()
        ack.verification_notes = verification_notes
        
        self.session.flush()
        return ack
    
    # ==================== Engagement Metrics ====================
    
    def calculate_engagement_metrics(
        self,
        announcement_id: UUID
    ) -> EngagementMetric:
        """
        Calculate and store comprehensive engagement metrics.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Calculated engagement metrics
        """
        announcement = self.session.get(Announcement, announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        # Get or create metric record
        metric = (
            self.session.query(EngagementMetric)
            .filter(EngagementMetric.announcement_id == announcement_id)
            .first()
        )
        
        if not metric:
            metric = EngagementMetric(announcement_id=announcement_id)
            self.session.add(metric)
        
        # Total recipients
        total_recipients = announcement.total_recipients or 1
        metric.total_recipients = total_recipients
        
        # Delivery metrics
        from app.models.announcement import AnnouncementDelivery
        delivered_count = (
            self.session.query(func.count(AnnouncementDelivery.id))
            .filter(
                AnnouncementDelivery.announcement_id == announcement_id,
                AnnouncementDelivery.is_delivered == True
            )
            .scalar()
        ) or 0
        
        metric.delivered_count = delivered_count
        metric.delivery_rate = Decimal(
            str(round((delivered_count / total_recipients * 100), 2))
        ) if total_recipients > 0 else Decimal('0.00')
        
        # View metrics
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
        
        metric.view_count = total_views
        metric.unique_readers = unique_viewers
        
        # Read metrics
        read_count = (
            self.session.query(func.count(ReadReceipt.id))
            .filter(ReadReceipt.announcement_id == announcement_id)
            .scalar()
        ) or 0
        
        metric.unique_readers = read_count  # Override with actual read count
        metric.read_rate = Decimal(
            str(round((read_count / total_recipients * 100), 2))
        ) if total_recipients > 0 else Decimal('0.00')
        
        # Reading depth metrics
        avg_reading_time = (
            self.session.query(func.avg(ReadReceipt.reading_time_seconds))
            .filter(ReadReceipt.announcement_id == announcement_id)
            .scalar()
        )
        
        avg_scroll = (
            self.session.query(func.avg(ReadReceipt.scroll_percentage))
            .filter(ReadReceipt.announcement_id == announcement_id)
            .scalar()
        )
        
        completed_count = (
            self.session.query(func.count(ReadReceipt.id))
            .filter(
                ReadReceipt.announcement_id == announcement_id,
                ReadReceipt.completed_reading == True
            )
            .scalar()
        ) or 0
        
        metric.average_reading_time_seconds = (
            Decimal(str(round(avg_reading_time, 2))) if avg_reading_time else None
        )
        metric.average_scroll_percentage = (
            Decimal(str(round(avg_scroll, 2))) if avg_scroll else None
        )
        metric.completion_rate = Decimal(
            str(round((completed_count / read_count * 100), 2))
        ) if read_count > 0 else Decimal('0.00')
        
        # Acknowledgment metrics
        if announcement.requires_acknowledgment:
            metric.requires_acknowledgment = True
            
            total_acks = (
                self.session.query(func.count(Acknowledgment.id))
                .filter(Acknowledgment.announcement_id == announcement_id)
                .scalar()
            ) or 0
            
            on_time_acks = (
                self.session.query(func.count(Acknowledgment.id))
                .filter(
                    Acknowledgment.announcement_id == announcement_id,
                    Acknowledgment.on_time == True
                )
                .scalar()
            ) or 0
            
            late_acks = total_acks - on_time_acks
            
            metric.acknowledged_count = total_acks
            metric.on_time_acknowledgments = on_time_acks
            metric.late_acknowledgments = late_acks
            metric.acknowledgment_rate = Decimal(
                str(round((total_acks / total_recipients * 100), 2))
            ) if total_recipients > 0 else Decimal('0.00')
        
        # Timing metrics
        avg_time_to_read = (
            self.session.query(func.avg(ReadReceipt.time_to_read_seconds))
            .filter(ReadReceipt.announcement_id == announcement_id)
            .scalar()
        )
        
        if avg_time_to_read:
            metric.average_time_to_read_hours = Decimal(
                str(round(avg_time_to_read / 3600, 2))
            )
        
        if announcement.requires_acknowledgment:
            avg_time_to_ack = (
                self.session.query(func.avg(Acknowledgment.time_to_acknowledge_seconds))
                .filter(Acknowledgment.announcement_id == announcement_id)
                .scalar()
            )
            
            if avg_time_to_ack:
                metric.average_time_to_acknowledge_hours = Decimal(
                    str(round(avg_time_to_ack / 3600, 2))
                )
        
        # Channel breakdown
        channel_stats = (
            self.session.query(
                AnnouncementDelivery.channel,
                func.count(AnnouncementDelivery.id)
            )
            .filter(
                AnnouncementDelivery.announcement_id == announcement_id,
                AnnouncementDelivery.is_delivered == True
            )
            .group_by(AnnouncementDelivery.channel)
            .all()
        )
        
        for channel, count in channel_stats:
            if channel == 'email':
                metric.email_delivered = count
            elif channel == 'sms':
                metric.sms_delivered = count
            elif channel == 'push':
                metric.push_delivered = count
            elif channel == 'in_app':
                metric.in_app_delivered = count
        
        # Device breakdown
        device_stats = (
            self.session.query(
                AnnouncementView.device_type,
                func.count(AnnouncementView.id)
            )
            .filter(AnnouncementView.announcement_id == announcement_id)
            .group_by(AnnouncementView.device_type)
            .all()
        )
        
        for device, count in device_stats:
            if device == 'mobile':
                metric.mobile_views = count
            elif device == 'web':
                metric.web_views = count
            elif device == 'tablet':
                metric.tablet_views = count
            elif device == 'desktop':
                metric.desktop_views = count
        
        # Interaction metrics
        metric.link_clicks = (
            self.session.query(func.count(AnnouncementView.id))
            .filter(
                AnnouncementView.announcement_id == announcement_id,
                AnnouncementView.clicked_links == True
            )
            .scalar()
        ) or 0
        
        metric.attachment_downloads = (
            self.session.query(func.count(AnnouncementView.id))
            .filter(
                AnnouncementView.announcement_id == announcement_id,
                AnnouncementView.downloaded_attachments == True
            )
            .scalar()
        ) or 0
        
        metric.shares = (
            self.session.query(func.count(AnnouncementView.id))
            .filter(
                AnnouncementView.announcement_id == announcement_id,
                AnnouncementView.shared == True
            )
            .scalar()
        ) or 0
        
        # Calculate overall engagement score
        metric.engagement_score = self._calculate_engagement_score(
            announcement, metric
        )
        
        metric.last_calculated_at = datetime.utcnow()
        
        self.session.flush()
        return metric
    
    def generate_reading_time_analytics(
        self,
        announcement_id: UUID
    ) -> ReadingTimeAnalytic:
        """
        Generate detailed reading time analytics.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Reading time analytics
        """
        # Get all reading times
        reading_times = (
            self.session.query(ReadReceipt.reading_time_seconds)
            .filter(
                ReadReceipt.announcement_id == announcement_id,
                ReadReceipt.reading_time_seconds.isnot(None)
            )
            .all()
        )
        
        if not reading_times:
            return None
        
        time_list = [t[0] for t in reading_times]
        
        # Get or create analytics record
        analytic = (
            self.session.query(ReadingTimeAnalytic)
            .filter(ReadingTimeAnalytic.announcement_id == announcement_id)
            .first()
        )
        
        if not analytic:
            analytic = ReadingTimeAnalytic(announcement_id=announcement_id)
            self.session.add(analytic)
        
        # Basic statistics
        analytic.total_readers = len(time_list)
        analytic.average_reading_time_seconds = Decimal(
            str(round(statistics.mean(time_list), 2))
        )
        analytic.median_reading_time_seconds = Decimal(
            str(round(statistics.median(time_list), 2))
        )
        analytic.min_reading_time_seconds = min(time_list)
        analytic.max_reading_time_seconds = max(time_list)
        
        # Reader classification
        quick = [t for t in time_list if t < 30]
        normal = [t for t in time_list if 30 <= t <= 120]
        thorough = [t for t in time_list if t > 120]
        
        analytic.quick_readers = len(quick)
        analytic.normal_readers = len(normal)
        analytic.thorough_readers = len(thorough)
        
        total = len(time_list)
        analytic.quick_readers_percentage = Decimal(
            str(round((len(quick) / total * 100), 2))
        )
        analytic.normal_readers_percentage = Decimal(
            str(round((len(normal) / total * 100), 2))
        )
        analytic.thorough_readers_percentage = Decimal(
            str(round((len(thorough) / total * 100), 2))
        )
        
        # Time distribution by hour
        hourly_distribution = (
            self.session.query(
                extract('hour', ReadReceipt.read_at).label('hour'),
                func.count(ReadReceipt.id).label('count')
            )
            .filter(ReadReceipt.announcement_id == announcement_id)
            .group_by('hour')
            .all()
        )
        
        analytic.reads_by_hour = {
            int(hour): count for hour, count in hourly_distribution
        }
        
        # Device-based reading time
        mobile_times = (
            self.session.query(func.avg(ReadReceipt.reading_time_seconds))
            .filter(
                ReadReceipt.announcement_id == announcement_id,
                ReadReceipt.device_type == 'mobile',
                ReadReceipt.reading_time_seconds.isnot(None)
            )
            .scalar()
        )
        
        web_times = (
            self.session.query(func.avg(ReadReceipt.reading_time_seconds))
            .filter(
                ReadReceipt.announcement_id == announcement_id,
                ReadReceipt.device_type == 'web',
                ReadReceipt.reading_time_seconds.isnot(None)
            )
            .scalar()
        )
        
        if mobile_times:
            analytic.mobile_avg_time = Decimal(str(round(mobile_times, 2)))
        if web_times:
            analytic.web_avg_time = Decimal(str(round(web_times, 2)))
        
        analytic.last_calculated_at = datetime.utcnow()
        
        self.session.flush()
        return analytic
    
    # ==================== Query Operations ====================
    
    def get_student_read_announcements(
        self,
        student_id: UUID,
        limit: int = 50
    ) -> List[ReadReceipt]:
        """
        Get announcements read by student.
        
        Args:
            student_id: Student UUID
            limit: Maximum results
            
        Returns:
            List of read receipts
        """
        query = (
            select(ReadReceipt)
            .where(ReadReceipt.student_id == student_id)
            .order_by(ReadReceipt.read_at.desc())
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_student_acknowledgments(
        self,
        student_id: UUID,
        pending_only: bool = False
    ) -> List[Acknowledgment]:
        """
        Get acknowledgments by student.
        
        Args:
            student_id: Student UUID
            pending_only: Only pending acknowledgments
            
        Returns:
            List of acknowledgments
        """
        query = select(Acknowledgment).where(
            Acknowledgment.student_id == student_id
        )
        
        if pending_only:
            # Get announcements requiring acknowledgment but not yet done
            acknowledged_ids = (
                select(Acknowledgment.announcement_id)
                .where(Acknowledgment.student_id == student_id)
            )
            
            query = (
                select(Announcement)
                .join(AnnouncementRecipient)
                .where(
                    AnnouncementRecipient.student_id == student_id,
                    Announcement.requires_acknowledgment == True,
                    Announcement.is_published == True,
                    ~Announcement.id.in_(acknowledged_ids)
                )
            )
        else:
            query = query.order_by(Acknowledgment.acknowledged_at.desc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_pending_acknowledgments(
        self,
        announcement_id: UUID
    ) -> List[User]:
        """
        Find students who haven't acknowledged yet.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            List of students pending acknowledgment
        """
        acknowledged_subq = (
            select(Acknowledgment.student_id)
            .where(Acknowledgment.announcement_id == announcement_id)
        )
        
        query = (
            select(User)
            .join(AnnouncementRecipient, User.id == AnnouncementRecipient.student_id)
            .where(
                AnnouncementRecipient.announcement_id == announcement_id,
                ~User.id.in_(acknowledged_subq)
            )
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_overdue_acknowledgments(
        self,
        announcement_id: UUID
    ) -> List[User]:
        """
        Find students with overdue acknowledgments.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            List of students with overdue acknowledgments
        """
        announcement = self.session.get(Announcement, announcement_id)
        if not announcement or not announcement.acknowledgment_deadline:
            return []
        
        now = datetime.utcnow()
        if now <= announcement.acknowledgment_deadline:
            return []
        
        # Get pending students
        return self.get_pending_acknowledgments(announcement_id)
    
    def get_student_engagement_profile(
        self,
        student_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate student engagement profile.
        
        Args:
            student_id: Student UUID
            days: Number of days to analyze
            
        Returns:
            Engagement profile dictionary
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total announcements targeted to student
        total_targeted = (
            self.session.query(func.count(AnnouncementRecipient.id))
            .filter(
                AnnouncementRecipient.student_id == student_id,
                AnnouncementRecipient.created_at >= cutoff_date
            )
            .scalar()
        ) or 0
        
        # Read count
        read_count = (
            self.session.query(func.count(ReadReceipt.id))
            .filter(
                ReadReceipt.student_id == student_id,
                ReadReceipt.read_at >= cutoff_date
            )
            .scalar()
        ) or 0
        
        # Acknowledgment metrics
        total_acks = (
            self.session.query(func.count(Acknowledgment.id))
            .filter(
                Acknowledgment.student_id == student_id,
                Acknowledgment.acknowledged_at >= cutoff_date
            )
            .scalar()
        ) or 0
        
        on_time_acks = (
            self.session.query(func.count(Acknowledgment.id))
            .filter(
                Acknowledgment.student_id == student_id,
                Acknowledgment.acknowledged_at >= cutoff_date,
                Acknowledgment.on_time == True
            )
            .scalar()
        ) or 0
        
        # Average reading time
        avg_reading_time = (
            self.session.query(func.avg(ReadReceipt.reading_time_seconds))
            .filter(
                ReadReceipt.student_id == student_id,
                ReadReceipt.read_at >= cutoff_date
            )
            .scalar()
        ) or 0
        
        # Preferred device
        device_usage = (
            self.session.query(
                AnnouncementView.device_type,
                func.count(AnnouncementView.id)
            )
            .filter(
                AnnouncementView.student_id == student_id,
                AnnouncementView.viewed_at >= cutoff_date
            )
            .group_by(AnnouncementView.device_type)
            .all()
        )
        
        preferred_device = None
        if device_usage:
            preferred_device = max(device_usage, key=lambda x: x[1])[0]
        
        # Calculate engagement rate
        engagement_rate = (
            (read_count / total_targeted * 100)
            if total_targeted > 0 else 0
        )
        
        # Calculate compliance rate
        compliance_rate = (
            (on_time_acks / total_acks * 100)
            if total_acks > 0 else 0
        )
        
        return {
            'student_id': str(student_id),
            'period_days': days,
            'total_announcements': total_targeted,
            'read_count': read_count,
            'engagement_rate': round(engagement_rate, 2),
            'acknowledgments_total': total_acks,
            'acknowledgments_on_time': on_time_acks,
            'compliance_rate': round(compliance_rate, 2),
            'average_reading_time_seconds': round(avg_reading_time, 2),
            'preferred_device': preferred_device,
            'device_usage': {device: count for device, count in device_usage},
        }
    
    def get_announcement_timeline(
        self,
        announcement_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get complete engagement timeline for announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            List of timeline events
        """
        timeline = []
        
        # Get announcement creation
        announcement = self.session.get(Announcement, announcement_id)
        if announcement:
            timeline.append({
                'event': 'created',
                'timestamp': announcement.created_at,
                'actor': str(announcement.created_by_id),
            })
            
            if announcement.published_at:
                timeline.append({
                    'event': 'published',
                    'timestamp': announcement.published_at,
                    'actor': str(announcement.published_by_id),
                })
        
        # Get views
        views = (
            self.session.query(AnnouncementView)
            .filter(AnnouncementView.announcement_id == announcement_id)
            .order_by(AnnouncementView.viewed_at)
            .all()
        )
        
        for view in views:
            timeline.append({
                'event': 'viewed',
                'timestamp': view.viewed_at,
                'actor': str(view.student_id),
                'device': view.device_type,
                'source': view.source,
            })
        
        # Get reads
        reads = (
            self.session.query(ReadReceipt)
            .filter(ReadReceipt.announcement_id == announcement_id)
            .order_by(ReadReceipt.read_at)
            .all()
        )
        
        for read in reads:
            timeline.append({
                'event': 'read',
                'timestamp': read.read_at,
                'actor': str(read.student_id),
                'reading_time': read.reading_time_seconds,
            })
        
        # Get acknowledgments
        acks = (
            self.session.query(Acknowledgment)
            .filter(Acknowledgment.announcement_id == announcement_id)
            .order_by(Acknowledgment.acknowledged_at)
            .all()
        )
        
        for ack in acks:
            timeline.append({
                'event': 'acknowledged',
                'timestamp': ack.acknowledged_at,
                'actor': str(ack.student_id),
                'on_time': ack.on_time,
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    # ==================== Analytics & Insights ====================
    
    def compare_announcement_performance(
        self,
        announcement_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        Compare performance across multiple announcements.
        
        Args:
            announcement_ids: List of announcement UUIDs
            
        Returns:
            Comparative performance data
        """
        comparison = {}
        
        for announcement_id in announcement_ids:
            metric = (
                self.session.query(EngagementMetric)
                .filter(EngagementMetric.announcement_id == announcement_id)
                .first()
            )
            
            if not metric:
                # Calculate if not exists
                metric = self.calculate_engagement_metrics(announcement_id)
            
            announcement = self.session.get(Announcement, announcement_id)
            
            comparison[str(announcement_id)] = {
                'title': announcement.title if announcement else 'Unknown',
                'category': announcement.category.value if announcement else None,
                'read_rate': float(metric.read_rate),
                'acknowledgment_rate': float(metric.acknowledgment_rate),
                'engagement_score': float(metric.engagement_score),
                'average_reading_time': float(metric.average_reading_time_seconds or 0),
            }
        
        return comparison
    
    def identify_low_engagement_students(
        self,
        hostel_id: UUID,
        threshold_percentage: float = 50.0,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Identify students with low engagement rates.
        
        Args:
            hostel_id: Hostel UUID
            threshold_percentage: Engagement threshold
            days: Period to analyze
            
        Returns:
            List of low-engagement students
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all students in hostel
        students = (
            self.session.query(User)
            .join(Room, User.room_id == Room.id)
            .filter(Room.hostel_id == hostel_id)
            .all()
        )
        
        low_engagement = []
        
        for student in students:
            profile = self.get_student_engagement_profile(student.id, days)
            
            if profile['engagement_rate'] < threshold_percentage:
                low_engagement.append({
                    'student_id': str(student.id),
                    'student_name': student.full_name,
                    'engagement_rate': profile['engagement_rate'],
                    'total_announcements': profile['total_announcements'],
                    'read_count': profile['read_count'],
                })
        
        # Sort by engagement rate ascending
        low_engagement.sort(key=lambda x: x['engagement_rate'])
        
        return low_engagement
    
    # ==================== Helper Methods ====================
    
    def _calculate_engagement_score(
        self,
        announcement: Announcement,
        metric: EngagementMetric
    ) -> Decimal:
        """
        Calculate overall engagement score (0-100).
        
        Weighted formula:
        - 30% delivery rate
        - 30% read rate
        - 20% completion rate
        - 20% acknowledgment rate (if required)
        """
        delivery_weight = 0.3
        read_weight = 0.3
        completion_weight = 0.2
        ack_weight = 0.2
        
        score = (
            float(metric.delivery_rate) * delivery_weight +
            float(metric.read_rate) * read_weight +
            float(metric.completion_rate) * completion_weight
        )
        
        if announcement.requires_acknowledgment:
            score += float(metric.acknowledgment_rate) * ack_weight
        else:
            # Redistribute ack weight to other metrics
            score += float(metric.read_rate) * ack_weight
        
        return Decimal(str(round(score, 2)))
