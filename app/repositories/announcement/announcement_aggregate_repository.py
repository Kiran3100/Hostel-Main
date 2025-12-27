"""
Announcement Aggregate Repository

High-level orchestrator for complex announcement operations involving 
multiple sub-repositories and cross-cutting concerns.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.announcement import (
    Announcement,
    AnnouncementTarget,
    AnnouncementSchedule,
    AnnouncementApproval,
    AnnouncementDelivery,
    AnnouncementRecipient,
    EngagementMetric,
)
from app.models.base.enums import (
    AnnouncementCategory,
    AnnouncementStatus,
    Priority,
    TargetAudience,
)
from app.repositories.announcement.announcement_repository import AnnouncementRepository
from app.repositories.announcement.announcement_targeting_repository import AnnouncementTargetingRepository
from app.repositories.announcement.announcement_scheduling_repository import AnnouncementSchedulingRepository
from app.repositories.announcement.announcement_approval_repository import AnnouncementApprovalRepository
from app.repositories.announcement.announcement_delivery_repository import AnnouncementDeliveryRepository
from app.repositories.announcement.announcement_tracking_repository import AnnouncementTrackingRepository
from app.core1.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)


class AnnouncementAggregateRepository:
    """
    Orchestrator repository for the Announcement module.
    
    Coordinates complex workflows across multiple repositories:
    - Complete announcement lifecycle management
    - Multi-step creation workflows
    - Approval and publication pipelines
    - Batch delivery orchestration
    - Cross-module analytics
    - Data synchronization
    - Cleanup and maintenance
    """
    
    def __init__(self, session: Session):
        self.session = session
        
        # Initialize sub-repositories
        self.announcements = AnnouncementRepository(session)
        self.targeting = AnnouncementTargetingRepository(session)
        self.scheduling = AnnouncementSchedulingRepository(session)
        self.approval = AnnouncementApprovalRepository(session)
        self.delivery = AnnouncementDeliveryRepository(session)
        self.tracking = AnnouncementTrackingRepository(session)
    
    # ==================== Complete Workflows ====================
    
    def create_complete_announcement(
        self,
        hostel_id: UUID,
        created_by_id: UUID,
        announcement_data: Dict[str, Any],
        targeting_data: Dict[str, Any],
        schedule_data: Optional[Dict[str, Any]] = None,
        approval_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create complete announcement with targeting, scheduling, and approval.
        
        This is a transactional workflow that creates all related entities
        in a single operation.
        
        Args:
            hostel_id: Hostel UUID
            created_by_id: Creator user UUID
            announcement_data: Core announcement fields
            targeting_data: Targeting configuration
            schedule_data: Optional scheduling configuration
            approval_data: Optional approval configuration
            
        Returns:
            Dictionary with created entities
        """
        try:
            # 1. Create core announcement
            announcement = self.announcements.create_draft(
                hostel_id=hostel_id,
                created_by_id=created_by_id,
                **announcement_data
            )
            
            # 2. Setup targeting
            target = self.targeting.build_audience_segment(
                announcement_id=announcement.id,
                created_by_id=created_by_id,
                **targeting_data
            )
            
            # 3. Calculate target reach
            reach = self.targeting.calculate_target_reach(
                announcement_id=announcement.id,
                update_cache=True
            )
            
            # Update announcement with recipient count
            announcement.total_recipients = reach['actual_recipients']
            
            # 4. Setup scheduling (if provided)
            schedule = None
            if schedule_data:
                if schedule_data.get('is_recurring'):
                    schedule = self.scheduling.create_recurring_schedule(
                        announcement_id=announcement.id,
                        scheduled_by_id=created_by_id,
                        **schedule_data
                    )
                else:
                    schedule = self.scheduling.create_schedule(
                        announcement_id=announcement.id,
                        scheduled_by_id=created_by_id,
                        **schedule_data
                    )
            
            # 5. Setup approval workflow (if required)
            approval = None
            if approval_data or announcement.requires_approval:
                approval = self.approval.create_approval_request(
                    announcement_id=announcement.id,
                    requested_by_id=created_by_id,
                    **(approval_data or {})
                )
            
            self.session.flush()
            
            return {
                'announcement': announcement,
                'target': target,
                'reach': reach,
                'schedule': schedule,
                'approval': approval,
                'success': True,
                'message': 'Announcement created successfully'
            }
            
        except Exception as e:
            self.session.rollback()
            raise BusinessLogicError(
                f"Failed to create complete announcement: {str(e)}"
            )
    
    def process_approval_and_publish(
        self,
        announcement_id: UUID,
        approved_by_id: UUID,
        approval_notes: Optional[str] = None,
        publish_immediately: bool = True
    ) -> Dict[str, Any]:
        """
        Process approval and optionally publish announcement.
        
        Args:
            announcement_id: Announcement UUID
            approved_by_id: Approver user UUID
            approval_notes: Approval notes
            publish_immediately: Whether to publish immediately
            
        Returns:
            Dictionary with approval and publication results
        """
        try:
            # 1. Get approval request
            approval_request = self.approval.find_by_announcement(announcement_id)
            if not approval_request:
                raise ResourceNotFoundError(
                    f"No approval request found for announcement {announcement_id}"
                )
            
            # 2. Approve announcement
            approval = self.approval.approve_announcement(
                approval_id=approval_request.id,
                approved_by_id=approved_by_id,
                approval_notes=approval_notes,
                auto_publish=publish_immediately
            )
            
            # 3. Publish if requested
            published = False
            if publish_immediately:
                announcement = self.announcements.publish_announcement(
                    announcement_id=announcement_id,
                    published_by_id=approved_by_id
                )
                published = True
                
                # 4. Initialize delivery
                delivery_result = self.initialize_delivery(announcement_id)
            else:
                delivery_result = None
            
            self.session.flush()
            
            return {
                'approval': approval,
                'published': published,
                'delivery_initialized': delivery_result is not None,
                'delivery_result': delivery_result,
                'success': True,
                'message': 'Announcement approved and published successfully' if published else 'Announcement approved'
            }
            
        except Exception as e:
            self.session.rollback()
            raise BusinessLogicError(
                f"Failed to process approval: {str(e)}"
            )
    
    def initialize_delivery(
        self,
        announcement_id: UUID,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Initialize delivery for published announcement.
        
        Creates delivery records and batches for all recipients
        across all configured channels.
        
        Args:
            announcement_id: Announcement UUID
            batch_size: Number of recipients per batch
            
        Returns:
            Delivery initialization results
        """
        try:
            announcement = self.announcements.find_by_id(announcement_id)
            if not announcement:
                raise ResourceNotFoundError(
                    f"Announcement {announcement_id} not found"
                )
            
            if not announcement.is_published:
                raise BusinessLogicError(
                    "Cannot initialize delivery for unpublished announcement"
                )
            
            # 1. Get target audience
            reach = self.targeting.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=False
            )
            
            student_ids = [UUID(sid) for sid in reach['student_ids']]
            
            if not student_ids:
                return {
                    'success': True,
                    'message': 'No recipients to deliver to',
                    'total_recipients': 0,
                    'channels': [],
                    'batches_created': 0
                }
            
            # 2. Determine delivery channels
            channels = []
            if announcement.send_push:
                channels.append('push')
            if announcement.send_email:
                channels.append('email')
            if announcement.send_sms:
                channels.append('sms')
            
            # Always include in-app
            if 'in_app' not in channels:
                channels.append('in_app')
            
            # 3. Create recipient records
            self._create_recipient_records(announcement_id, student_ids)
            
            # 4. Create delivery batches and records
            batches_created = 0
            deliveries_created = 0
            
            for channel in channels:
                # Split recipients into batches
                num_batches = (len(student_ids) + batch_size - 1) // batch_size
                
                for batch_num in range(num_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min(start_idx + batch_size, len(student_ids))
                    batch_student_ids = student_ids[start_idx:end_idx]
                    
                    # Create batch
                    batch = self.delivery.create_delivery_batch(
                        announcement_id=announcement_id,
                        channel=channel,
                        batch_number=batch_num + 1,
                        total_recipients=len(batch_student_ids)
                    )
                    batches_created += 1
                    
                    # Create delivery records
                    deliveries = self.delivery.create_bulk_deliveries(
                        announcement_id=announcement_id,
                        recipient_ids=batch_student_ids,
                        channels=[channel],
                        batch_id=batch.id
                    )
                    deliveries_created += len(deliveries)
            
            self.session.flush()
            
            return {
                'success': True,
                'message': 'Delivery initialized successfully',
                'total_recipients': len(student_ids),
                'channels': channels,
                'batches_created': batches_created,
                'deliveries_created': deliveries_created
            }
            
        except Exception as e:
            self.session.rollback()
            raise BusinessLogicError(
                f"Failed to initialize delivery: {str(e)}"
            )
    
    def process_scheduled_publications(
        self,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Process all due scheduled publications.
        
        Args:
            batch_size: Maximum number to process
            
        Returns:
            Processing results
        """
        try:
            # 1. Get pending publications from queue
            pending = self.scheduling.get_pending_publications(
                limit=batch_size
            )
            
            published_count = 0
            failed_count = 0
            results = []
            
            for queue_item in pending:
                try:
                    # 2. Acquire lock
                    locked = self.scheduling.acquire_queue_lock(
                        queue_id=queue_item.id,
                        worker_id='scheduler_worker'
                    )
                    
                    if not locked:
                        continue
                    
                    # 3. Publish announcement
                    announcement = self.announcements.publish_announcement(
                        announcement_id=queue_item.announcement_id,
                        published_by_id=None  # System published
                    )
                    
                    # 4. Initialize delivery
                    delivery_result = self.initialize_delivery(
                        announcement_id=queue_item.announcement_id
                    )
                    
                    # 5. Mark queue item as complete
                    self.scheduling.complete_queue_item(
                        queue_id=queue_item.id,
                        success=True
                    )
                    
                    published_count += 1
                    results.append({
                        'announcement_id': str(queue_item.announcement_id),
                        'status': 'published',
                        'deliveries_created': delivery_result['deliveries_created']
                    })
                    
                except Exception as e:
                    # Mark as failed
                    self.scheduling.complete_queue_item(
                        queue_id=queue_item.id,
                        success=False,
                        error=str(e)
                    )
                    
                    failed_count += 1
                    results.append({
                        'announcement_id': str(queue_item.announcement_id),
                        'status': 'failed',
                        'error': str(e)
                    })
            
            self.session.flush()
            
            return {
                'success': True,
                'total_processed': len(pending),
                'published': published_count,
                'failed': failed_count,
                'results': results
            }
            
        except Exception as e:
            self.session.rollback()
            raise BusinessLogicError(
                f"Failed to process scheduled publications: {str(e)}"
            )
    
    def process_recurring_announcements(
        self,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Process due recurring announcements.
        
        Args:
            batch_size: Maximum number to process
            
        Returns:
            Processing results
        """
        try:
            # Process recurring templates
            created_announcements = self.scheduling.process_due_recurring_announcements(
                batch_size=batch_size
            )
            
            published_count = 0
            results = []
            
            for announcement in created_announcements:
                try:
                    # Initialize delivery for each created announcement
                    delivery_result = self.initialize_delivery(
                        announcement_id=announcement.id
                    )
                    
                    published_count += 1
                    results.append({
                        'announcement_id': str(announcement.id),
                        'title': announcement.title,
                        'status': 'published',
                        'recipients': delivery_result['total_recipients']
                    })
                    
                except Exception as e:
                    results.append({
                        'announcement_id': str(announcement.id),
                        'status': 'failed',
                        'error': str(e)
                    })
            
            self.session.flush()
            
            return {
                'success': True,
                'total_created': len(created_announcements),
                'published': published_count,
                'results': results
            }
            
        except Exception as e:
            self.session.rollback()
            raise BusinessLogicError(
                f"Failed to process recurring announcements: {str(e)}"
            )
    
    # ==================== Analytics & Reporting ====================
    
    def generate_comprehensive_report(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive announcement analytics report.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Comprehensive analytics report
        """
        # Default to last 30 days if not specified
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # 1. Basic announcement statistics
        announcement_stats = self.announcements.get_announcement_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # 2. Approval statistics
        approval_stats = self.approval.get_approval_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # 3. Top performing announcements
        top_performers = self.announcements.get_top_performing_announcements(
            hostel_id=hostel_id,
            limit=10,
            metric='engagement_rate'
        )
        
        # 4. Low engagement students
        low_engagement = self.tracking.identify_low_engagement_students(
            hostel_id=hostel_id,
            threshold_percentage=50.0,
            days=30
        )
        
        # 5. Channel performance
        channel_performance = self._analyze_channel_performance(
            hostel_id, start_date, end_date
        )
        
        # 6. Category breakdown
        category_performance = self._analyze_category_performance(
            hostel_id, start_date, end_date
        )
        
        return {
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'hostel_id': str(hostel_id),
            'announcement_statistics': announcement_stats,
            'approval_statistics': approval_stats,
            'top_performing_announcements': [
                {
                    'announcement_id': str(ann.id),
                    'title': ann.title,
                    'engagement_rate': float(metric)
                }
                for ann, metric in top_performers
            ],
            'low_engagement_students': low_engagement[:20],  # Top 20
            'channel_performance': channel_performance,
            'category_performance': category_performance,
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def get_hostel_dashboard_metrics(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get real-time dashboard metrics for hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dashboard metrics
        """
        now = datetime.utcnow()
        
        # Active announcements
        active_count = self.session.query(func.count(Announcement.id)).filter(
            Announcement.hostel_id == hostel_id,
            Announcement.is_published == True,
            Announcement.is_archived == False,
            Announcement.is_deleted == False,
            or_(
                Announcement.expires_at.is_(None),
                Announcement.expires_at > now
            )
        ).scalar() or 0
        
        # Pending approvals
        pending_approvals = self.session.query(
            func.count(AnnouncementApproval.id)
        ).join(Announcement).filter(
            Announcement.hostel_id == hostel_id,
            AnnouncementApproval.approval_status == 'pending'
        ).scalar() or 0
        
        # Urgent announcements
        urgent_count = self.session.query(
            func.count(Announcement.id)
        ).filter(
            Announcement.hostel_id == hostel_id,
            Announcement.is_urgent == True,
            Announcement.is_published == True,
            Announcement.is_deleted == False
        ).scalar() or 0
        
        # Pending acknowledgments
        pending_acks = self.session.query(
            func.count(AnnouncementRecipient.id)
        ).join(Announcement).filter(
            Announcement.hostel_id == hostel_id,
            Announcement.requires_acknowledgment == True,
            AnnouncementRecipient.is_acknowledged == False
        ).scalar() or 0
        
        # Average engagement rate (last 30 days)
        thirty_days_ago = now - timedelta(days=30)
        avg_engagement = self.session.query(
            func.avg(EngagementMetric.engagement_score)
        ).join(Announcement).filter(
            Announcement.hostel_id == hostel_id,
            Announcement.published_at >= thirty_days_ago
        ).scalar() or 0
        
        # Scheduled publications (next 24 hours)
        tomorrow = now + timedelta(hours=24)
        upcoming_scheduled = self.session.query(
            func.count(AnnouncementSchedule.id)
        ).join(Announcement).filter(
            Announcement.hostel_id == hostel_id,
            AnnouncementSchedule.status == 'pending',
            AnnouncementSchedule.next_publish_at.between(now, tomorrow)
        ).scalar() or 0
        
        return {
            'active_announcements': active_count,
            'urgent_announcements': urgent_count,
            'pending_approvals': pending_approvals,
            'pending_acknowledgments': pending_acks,
            'average_engagement_rate': round(float(avg_engagement), 2),
            'upcoming_scheduled': upcoming_scheduled,
            'timestamp': now.isoformat()
        }
    
    # ==================== Maintenance & Cleanup ====================
    
    def cleanup_expired_announcements(
        self,
        hostel_id: UUID,
        auto_archive: bool = True
    ) -> Dict[str, Any]:
        """
        Cleanup expired announcements.
        
        Args:
            hostel_id: Hostel UUID
            auto_archive: Whether to auto-archive expired
            
        Returns:
            Cleanup results
        """
        try:
            now = datetime.utcnow()
            
            # Find expired announcements
            expired = self.announcements.find_expiring_soon(
                hostel_id=hostel_id,
                hours=-1  # Already expired
            )
            
            archived_count = 0
            
            if auto_archive:
                # Archive expired announcements
                for announcement in expired:
                    if not announcement.is_archived:
                        self.announcements.archive_announcement(
                            announcement_id=announcement.id,
                            archived_by_id=None,  # System archived
                            reason="Automatically archived - expired"
                        )
                        archived_count += 1
            
            self.session.flush()
            
            return {
                'success': True,
                'expired_found': len(expired),
                'archived': archived_count,
                'timestamp': now.isoformat()
            }
            
        except Exception as e:
            self.session.rollback()
            raise BusinessLogicError(
                f"Failed to cleanup expired announcements: {str(e)}"
            )
    
    def recalculate_all_metrics(
        self,
        announcement_id: UUID
    ) -> Dict[str, Any]:
        """
        Recalculate all metrics for an announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Recalculation results
        """
        try:
            # 1. Update engagement metrics
            engagement = self.tracking.calculate_engagement_metrics(
                announcement_id=announcement_id
            )
            
            # 2. Update reading time analytics
            reading_analytics = self.tracking.generate_reading_time_analytics(
                announcement_id=announcement_id
            )
            
            # 3. Update announcement aggregate counts
            announcement = self.announcements.update_engagement_metrics(
                announcement_id=announcement_id
            )
            
            self.session.flush()
            
            return {
                'success': True,
                'announcement_id': str(announcement_id),
                'engagement_score': float(engagement.engagement_score),
                'read_rate': float(engagement.read_rate),
                'acknowledgment_rate': float(engagement.acknowledgment_rate),
                'average_reading_time': float(reading_analytics.average_reading_time_seconds) if reading_analytics else 0,
                'recalculated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.session.rollback()
            raise BusinessLogicError(
                f"Failed to recalculate metrics: {str(e)}"
            )
    
    # ==================== Helper Methods ====================
    
    def _create_recipient_records(
        self,
        announcement_id: UUID,
        student_ids: List[UUID]
    ) -> None:
        """Create recipient records for tracking."""
        for student_id in student_ids:
            recipient = AnnouncementRecipient(
                announcement_id=announcement_id,
                student_id=student_id,
                matched_by='targeted'
            )
            self.session.add(recipient)
    
    def _analyze_channel_performance(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze delivery channel performance."""
        channels = ['email', 'sms', 'push', 'in_app']
        performance = {}
        
        for channel in channels:
            total = self.session.query(
                func.count(AnnouncementDelivery.id)
            ).join(Announcement).filter(
                Announcement.hostel_id == hostel_id,
                AnnouncementDelivery.channel == channel,
                AnnouncementDelivery.created_at.between(start_date, end_date)
            ).scalar() or 0
            
            delivered = self.session.query(
                func.count(AnnouncementDelivery.id)
            ).join(Announcement).filter(
                Announcement.hostel_id == hostel_id,
                AnnouncementDelivery.channel == channel,
                AnnouncementDelivery.is_delivered == True,
                AnnouncementDelivery.created_at.between(start_date, end_date)
            ).scalar() or 0
            
            performance[channel] = {
                'total_sent': total,
                'delivered': delivered,
                'delivery_rate': round((delivered / total * 100), 2) if total > 0 else 0
            }
        
        return performance
    
    def _analyze_category_performance(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze performance by announcement category."""
        categories = self.session.query(
            Announcement.category,
            func.count(Announcement.id).label('count'),
            func.avg(EngagementMetric.engagement_score).label('avg_engagement')
        ).outerjoin(EngagementMetric).filter(
            Announcement.hostel_id == hostel_id,
            Announcement.created_at.between(start_date, end_date)
        ).group_by(Announcement.category).all()
        
        return {
            cat.value: {
                'count': count,
                'average_engagement': round(float(avg_eng or 0), 2)
            }
            for cat, count, avg_eng in categories
        }