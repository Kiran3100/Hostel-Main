"""
Announcement Tracking Service

Engagement tracking and analytics service providing comprehensive
tracking of views, reads, acknowledgments, and behavioral insights.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, Field

from app.repositories.announcement import (
    AnnouncementTrackingRepository,
    AnnouncementRepository,
)
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)
from app.core.events import EventPublisher


# ==================== DTOs ====================

class RecordViewDTO(BaseModel):
    """DTO for recording view."""
    device_type: Optional[str] = Field(None, regex='^(mobile|web|tablet|desktop)$')
    source: str = Field('app', regex='^(app|email|push_notification|web)$')
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateReadingMetricsDTO(BaseModel):
    """DTO for updating reading metrics."""
    reading_time_seconds: int = Field(..., ge=0, le=3600)
    scroll_percentage: int = Field(..., ge=0, le=100)
    clicked_links: bool = False
    downloaded_attachments: bool = False
    shared: bool = False


class RecordEngagementActionDTO(BaseModel):
    """DTO for recording engagement action."""
    action_type: str = Field(..., regex='^(link_click|download|share|reaction)$')
    action_details: Optional[Dict[str, Any]] = None


class MarkAsReadDTO(BaseModel):
    """DTO for marking as read."""
    reading_time_seconds: Optional[int] = Field(None, ge=0, le=3600)
    scroll_percentage: Optional[int] = Field(None, ge=0, le=100)
    device_type: Optional[str] = None
    source: str = 'app'


class AcknowledgeAnnouncementDTO(BaseModel):
    """DTO for acknowledging announcement."""
    acknowledgment_note: Optional[str] = Field(None, max_length=500)
    action_taken: Optional[str] = Field(None, max_length=500)
    device_type: Optional[str] = None
    ip_address: Optional[str] = None


class VerifyAcknowledgmentDTO(BaseModel):
    """DTO for verifying acknowledgment."""
    verification_notes: Optional[str] = Field(None, max_length=500)


class GetEngagementProfileDTO(BaseModel):
    """DTO for getting engagement profile."""
    days: int = Field(30, ge=1, le=365)


class IdentifyLowEngagementDTO(BaseModel):
    """DTO for identifying low engagement students."""
    threshold_percentage: float = Field(50.0, ge=0.0, le=100.0)
    days: int = Field(30, ge=1, le=365)


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

class AnnouncementTrackingService:
    """
    Engagement tracking and analytics service.
    
    Provides comprehensive tracking capabilities including:
    - View and reading behavior tracking
    - Read receipt management
    - Acknowledgment processing and verification
    - Real-time engagement metrics calculation
    - Reading time analytics
    - Behavioral pattern analysis
    - Student engagement profiling
    - Performance benchmarking and comparison
    """
    
    def __init__(
        self,
        session: Session,
        event_publisher: Optional[EventPublisher] = None
    ):
        self.session = session
        self.repository = AnnouncementTrackingRepository(session)
        self.announcement_repository = AnnouncementRepository(session)
        self.event_publisher = event_publisher or EventPublisher()
    
    # ==================== View Tracking ====================
    
    def record_view(
        self,
        announcement_id: UUID,
        student_id: UUID,
        dto: RecordViewDTO
    ) -> ServiceResult:
        """
        Record student viewing announcement.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            dto: View data
            
        Returns:
            ServiceResult with view record
        """
        try:
            # Validate announcement exists
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Record view
            view = self.repository.record_view(
                announcement_id=announcement_id,
                student_id=student_id,
                device_type=dto.device_type,
                source=dto.source,
                session_id=dto.session_id,
                ip_address=dto.ip_address,
                user_agent=dto.user_agent,
                metadata=dto.metadata
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('announcement.viewed', {
                'announcement_id': str(announcement_id),
                'student_id': str(student_id),
                'device_type': dto.device_type,
                'source': dto.source,
                'view_count': view.view_count,
            })
            
            return ServiceResult.ok(
                data=self._serialize_view(view),
                view_id=str(view.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="VIEW_RECORD_FAILED")
    
    def update_reading_metrics(
        self,
        view_id: UUID,
        dto: UpdateReadingMetricsDTO
    ) -> ServiceResult:
        """
        Update reading behavior metrics for a view.
        
        Args:
            view_id: View record UUID
            dto: Reading metrics
            
        Returns:
            ServiceResult with updated view
        """
        try:
            view = self.repository.update_reading_metrics(
                view_id=view_id,
                reading_time_seconds=dto.reading_time_seconds,
                scroll_percentage=dto.scroll_percentage,
                clicked_links=dto.clicked_links,
                downloaded_attachments=dto.downloaded_attachments,
                shared=dto.shared
            )
            
            self.session.commit()
            
            # Publish event if significant engagement
            if dto.scroll_percentage >= 90:
                self.event_publisher.publish('announcement.read_completed', {
                    'announcement_id': str(view.announcement_id),
                    'student_id': str(view.student_id),
                    'reading_time': dto.reading_time_seconds,
                })
            
            return ServiceResult.ok(
                data=self._serialize_view(view),
                view_id=str(view_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except ValidationError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="VALIDATION_ERROR")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="UPDATE_FAILED")
    
    def record_engagement_action(
        self,
        view_id: UUID,
        dto: RecordEngagementActionDTO
    ) -> ServiceResult:
        """
        Record specific engagement action.
        
        Args:
            view_id: View record UUID
            dto: Action data
            
        Returns:
            ServiceResult with updated view
        """
        try:
            view = self.repository.record_engagement_action(
                view_id=view_id,
                action_type=dto.action_type,
                action_details=dto.action_details
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('engagement.action_recorded', {
                'view_id': str(view_id),
                'announcement_id': str(view.announcement_id),
                'student_id': str(view.student_id),
                'action_type': dto.action_type,
            })
            
            return ServiceResult.ok(
                data=self._serialize_view(view),
                view_id=str(view_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="ACTION_RECORD_FAILED")
    
    # ==================== Read Receipt Management ====================
    
    def mark_as_read(
        self,
        announcement_id: UUID,
        student_id: UUID,
        dto: MarkAsReadDTO
    ) -> ServiceResult:
        """
        Mark announcement as read by student.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            dto: Read data
            
        Returns:
            ServiceResult with read receipt
        """
        try:
            receipt = self.repository.mark_as_read(
                announcement_id=announcement_id,
                student_id=student_id,
                reading_time_seconds=dto.reading_time_seconds,
                scroll_percentage=dto.scroll_percentage,
                device_type=dto.device_type,
                source=dto.source
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('announcement.read', {
                'announcement_id': str(announcement_id),
                'student_id': str(student_id),
                'reading_time': dto.reading_time_seconds,
                'completed': receipt.completed_reading,
            })
            
            # Trigger metric recalculation
            self._schedule_metric_update(announcement_id)
            
            return ServiceResult.ok(
                data=self._serialize_receipt(receipt),
                receipt_id=str(receipt.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="MARK_READ_FAILED")
    
    def bulk_mark_as_read(
        self,
        announcement_id: UUID,
        student_ids: List[UUID]
    ) -> ServiceResult:
        """
        Bulk mark announcement as read for multiple students.
        
        Args:
            announcement_id: Announcement UUID
            student_ids: List of student UUIDs
            
        Returns:
            ServiceResult with count
        """
        try:
            count = self.repository.bulk_mark_as_read(
                announcement_id=announcement_id,
                student_ids=student_ids
            )
            
            self.session.commit()
            
            # Trigger metric recalculation
            self._schedule_metric_update(announcement_id)
            
            return ServiceResult.ok(data={
                'marked_count': count,
                'total_requested': len(student_ids),
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="BULK_MARK_FAILED")
    
    def get_student_read_announcements(
        self,
        student_id: UUID,
        limit: int = 50
    ) -> ServiceResult:
        """
        Get announcements read by student.
        
        Args:
            student_id: Student UUID
            limit: Maximum results
            
        Returns:
            ServiceResult with read receipts
        """
        try:
            receipts = self.repository.get_student_read_announcements(
                student_id=student_id,
                limit=limit
            )
            
            return ServiceResult.ok(data={
                'receipts': [self._serialize_receipt(r) for r in receipts],
                'total': len(receipts),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_FAILED")
    
    # ==================== Acknowledgment Management ====================
    
    def acknowledge_announcement(
        self,
        announcement_id: UUID,
        student_id: UUID,
        dto: AcknowledgeAnnouncementDTO
    ) -> ServiceResult:
        """
        Submit student acknowledgment for announcement.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            dto: Acknowledgment data
            
        Returns:
            ServiceResult with acknowledgment
        """
        try:
            acknowledgment = self.repository.acknowledge_announcement(
                announcement_id=announcement_id,
                student_id=student_id,
                acknowledgment_note=dto.acknowledgment_note,
                action_taken=dto.action_taken,
                device_type=dto.device_type,
                ip_address=dto.ip_address
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('announcement.acknowledged', {
                'announcement_id': str(announcement_id),
                'student_id': str(student_id),
                'on_time': acknowledgment.on_time,
                'has_action': bool(dto.action_taken),
            })
            
            # Trigger metric recalculation
            self._schedule_metric_update(announcement_id)
            
            return ServiceResult.ok(
                data=self._serialize_acknowledgment(acknowledgment),
                acknowledgment_id=str(acknowledgment.id)
            )
            
        except BusinessLogicError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="ALREADY_ACKNOWLEDGED")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="ACKNOWLEDGE_FAILED")
    
    def verify_acknowledgment(
        self,
        acknowledgment_id: UUID,
        verified_by_id: UUID,
        dto: VerifyAcknowledgmentDTO
    ) -> ServiceResult:
        """
        Verify acknowledgment (for action-required announcements).
        
        Args:
            acknowledgment_id: Acknowledgment UUID
            verified_by_id: Verifier user UUID
            dto: Verification data
            
        Returns:
            ServiceResult with verified acknowledgment
        """
        try:
            acknowledgment = self.repository.verify_acknowledgment(
                acknowledgment_id=acknowledgment_id,
                verified_by_id=verified_by_id,
                verification_notes=dto.verification_notes
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('acknowledgment.verified', {
                'acknowledgment_id': str(acknowledgment_id),
                'student_id': str(acknowledgment.student_id),
                'verified_by': str(verified_by_id),
            })
            
            return ServiceResult.ok(
                data=self._serialize_acknowledgment(acknowledgment),
                acknowledgment_id=str(acknowledgment_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="VERIFICATION_FAILED")
    
    def get_pending_acknowledgments(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Get students who haven't acknowledged yet.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with pending students
        """
        try:
            students = self.repository.get_pending_acknowledgments(announcement_id)
            
            return ServiceResult.ok(data={
                'pending_students': [
                    {
                        'student_id': str(s.id),
                        'name': s.full_name,
                        'email': s.email,
                        'room': s.room.room_number if s.room else None,
                    }
                    for s in students
                ],
                'total': len(students),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_FAILED")
    
    def get_overdue_acknowledgments(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Get students with overdue acknowledgments.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with overdue students
        """
        try:
            students = self.repository.get_overdue_acknowledgments(announcement_id)
            
            return ServiceResult.ok(data={
                'overdue_students': [
                    {
                        'student_id': str(s.id),
                        'name': s.full_name,
                        'email': s.email,
                        'room': s.room.room_number if s.room else None,
                    }
                    for s in students
                ],
                'total': len(students),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_FAILED")
    
    # ==================== Engagement Metrics ====================
    
    def calculate_engagement_metrics(
        self,
        announcement_id: UUID,
        force_recalculate: bool = False
    ) -> ServiceResult:
        """
        Calculate comprehensive engagement metrics.
        
        Args:
            announcement_id: Announcement UUID
            force_recalculate: Force recalculation
            
        Returns:
            ServiceResult with metrics
        """
        try:
            metric = self.repository.calculate_engagement_metrics(announcement_id)
            
            self.session.commit()
            
            return ServiceResult.ok(
                data=self._serialize_engagement_metric(metric),
                metric_id=str(metric.id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="CALCULATION_FAILED")
    
    def generate_reading_time_analytics(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Generate detailed reading time analytics.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with analytics
        """
        try:
            analytic = self.repository.generate_reading_time_analytics(announcement_id)
            
            if not analytic:
                return ServiceResult.fail(
                    "Insufficient data for analytics",
                    error_code="INSUFFICIENT_DATA"
                )
            
            self.session.commit()
            
            return ServiceResult.ok(
                data=self._serialize_reading_analytic(analytic),
                analytic_id=str(analytic.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="ANALYTICS_FAILED")
    
    def get_announcement_timeline(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Get complete engagement timeline for announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with timeline
        """
        try:
            timeline = self.repository.get_announcement_timeline(announcement_id)
            
            return ServiceResult.ok(data={
                'timeline': timeline,
                'total_events': len(timeline),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="TIMELINE_FAILED")
    
    # ==================== Student Engagement ====================
    
    def get_student_engagement_profile(
        self,
        student_id: UUID,
        dto: GetEngagementProfileDTO
    ) -> ServiceResult:
        """
        Generate student engagement profile.
        
        Args:
            student_id: Student UUID
            dto: Profile request data
            
        Returns:
            ServiceResult with engagement profile
        """
        try:
            profile = self.repository.get_student_engagement_profile(
                student_id=student_id,
                days=dto.days
            )
            
            # Add engagement level classification
            profile['engagement_level'] = self._classify_engagement_level(
                profile['engagement_rate']
            )
            
            return ServiceResult.ok(data=profile)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="PROFILE_FAILED")
    
    def identify_low_engagement_students(
        self,
        hostel_id: UUID,
        dto: IdentifyLowEngagementDTO
    ) -> ServiceResult:
        """
        Identify students with low engagement rates.
        
        Args:
            hostel_id: Hostel UUID
            dto: Identification criteria
            
        Returns:
            ServiceResult with low engagement students
        """
        try:
            students = self.repository.identify_low_engagement_students(
                hostel_id=hostel_id,
                threshold_percentage=dto.threshold_percentage,
                days=dto.days
            )
            
            # Publish alert if significant number
            if len(students) > 10:
                self.event_publisher.publish('engagement.low_engagement_alert', {
                    'hostel_id': str(hostel_id),
                    'count': len(students),
                    'threshold': dto.threshold_percentage,
                })
            
            return ServiceResult.ok(data={
                'low_engagement_students': students,
                'total': len(students),
                'threshold': dto.threshold_percentage,
                'period_days': dto.days,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="IDENTIFICATION_FAILED")
    
    # ==================== Performance Comparison ====================
    
    def compare_announcement_performance(
        self,
        announcement_ids: List[UUID]
    ) -> ServiceResult:
        """
        Compare performance across multiple announcements.
        
        Args:
            announcement_ids: List of announcement UUIDs
            
        Returns:
            ServiceResult with comparative data
        """
        try:
            if len(announcement_ids) > 10:
                return ServiceResult.fail(
                    "Maximum 10 announcements can be compared",
                    error_code="TOO_MANY_ITEMS"
                )
            
            comparison = self.repository.compare_announcement_performance(
                announcement_ids=announcement_ids
            )
            
            return ServiceResult.ok(data={
                'comparison': comparison,
                'announcements_compared': len(announcement_ids),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="COMPARISON_FAILED")
    
    def get_engagement_leaderboard(
        self,
        hostel_id: UUID,
        days: int = 30,
        limit: int = 10
    ) -> ServiceResult:
        """
        Get student engagement leaderboard.
        
        Args:
            hostel_id: Hostel UUID
            days: Period in days
            limit: Top N students
            
        Returns:
            ServiceResult with leaderboard
        """
        try:
            # Get all students and their engagement profiles
            from app.models.user.user import User
            from app.models.room.room import Room
            
            students = (
                self.session.query(User)
                .join(Room, User.room_id == Room.id)
                .filter(Room.hostel_id == hostel_id)
                .all()
            )
            
            leaderboard = []
            
            for student in students:
                profile = self.repository.get_student_engagement_profile(
                    student_id=student.id,
                    days=days
                )
                
                leaderboard.append({
                    'student_id': str(student.id),
                    'name': student.full_name,
                    'engagement_rate': profile['engagement_rate'],
                    'total_announcements': profile['total_announcements'],
                    'read_count': profile['read_count'],
                    'acknowledgments_total': profile['acknowledgments_total'],
                    'compliance_rate': profile['compliance_rate'],
                })
            
            # Sort by engagement rate
            leaderboard.sort(key=lambda x: x['engagement_rate'], reverse=True)
            
            return ServiceResult.ok(data={
                'leaderboard': leaderboard[:limit],
                'total_students': len(students),
                'period_days': days,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="LEADERBOARD_FAILED")
    
    # ==================== Real-time Analytics ====================
    
    def get_real_time_engagement(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Get real-time engagement data for announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with real-time data
        """
        try:
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Get latest metrics
            from app.models.announcement import EngagementMetric
            metric = (
                self.session.query(EngagementMetric)
                .filter(EngagementMetric.announcement_id == announcement_id)
                .first()
            )
            
            # Get recent views (last hour)
            from app.models.announcement import AnnouncementView
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)
            recent_views = (
                self.session.query(AnnouncementView)
                .filter(
                    AnnouncementView.announcement_id == announcement_id,
                    AnnouncementView.viewed_at >= recent_cutoff
                )
                .count()
            )
            
            return ServiceResult.ok(data={
                'announcement_id': str(announcement_id),
                'total_recipients': announcement.total_recipients,
                'read_count': announcement.read_count,
                'acknowledged_count': announcement.acknowledged_count,
                'engagement_rate': float(announcement.engagement_rate),
                'recent_views_last_hour': recent_views,
                'metrics': self._serialize_engagement_metric(metric) if metric else None,
                'timestamp': datetime.utcnow().isoformat(),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="REAL_TIME_FETCH_FAILED")
    
    # ==================== Helper Methods ====================
    
    def _schedule_metric_update(self, announcement_id: UUID):
        """Schedule async metric recalculation."""
        # This would integrate with background task queue
        self.event_publisher.publish('metrics.update_requested', {
            'announcement_id': str(announcement_id),
        })
    
    def _classify_engagement_level(self, engagement_rate: float) -> str:
        """Classify engagement level."""
        if engagement_rate >= 80:
            return 'excellent'
        elif engagement_rate >= 60:
            return 'good'
        elif engagement_rate >= 40:
            return 'fair'
        elif engagement_rate >= 20:
            return 'poor'
        else:
            return 'very_poor'
    
    def _serialize_view(self, view) -> Dict[str, Any]:
        """Serialize view to dictionary."""
        return {
            'id': str(view.id),
            'announcement_id': str(view.announcement_id),
            'student_id': str(view.student_id),
            'viewed_at': view.viewed_at.isoformat(),
            'device_type': view.device_type,
            'source': view.source,
            'reading_time_seconds': view.reading_time_seconds,
            'scroll_percentage': view.scroll_percentage,
            'clicked_links': view.clicked_links,
            'downloaded_attachments': view.downloaded_attachments,
            'shared': view.shared,
            'view_count': view.view_count,
        }
    
    def _serialize_receipt(self, receipt) -> Dict[str, Any]:
        """Serialize read receipt to dictionary."""
        return {
            'id': str(receipt.id),
            'announcement_id': str(receipt.announcement_id),
            'student_id': str(receipt.student_id),
            'read_at': receipt.read_at.isoformat(),
            'device_type': receipt.device_type,
            'source': receipt.source,
            'reading_time_seconds': receipt.reading_time_seconds,
            'scroll_percentage': receipt.scroll_percentage,
            'completed_reading': receipt.completed_reading,
            'time_to_read_seconds': receipt.time_to_read_seconds,
            'is_first_read': receipt.is_first_read,
        }
    
    def _serialize_acknowledgment(self, ack) -> Dict[str, Any]:
        """Serialize acknowledgment to dictionary."""
        return {
            'id': str(ack.id),
            'announcement_id': str(ack.announcement_id),
            'student_id': str(ack.student_id),
            'acknowledged_at': ack.acknowledged_at.isoformat(),
            'acknowledgment_note': ack.acknowledgment_note,
            'action_taken': ack.action_taken,
            'on_time': ack.on_time,
            'deadline': ack.deadline.isoformat() if ack.deadline else None,
            'time_to_acknowledge_seconds': ack.time_to_acknowledge_seconds,
            'read_before_acknowledge': ack.read_before_acknowledge,
            'action_verified': ack.action_verified,
            'verified_by_id': str(ack.verified_by_id) if ack.verified_by_id else None,
            'verified_at': ack.verified_at.isoformat() if ack.verified_at else None,
        }
    
    def _serialize_engagement_metric(self, metric) -> Dict[str, Any]:
        """Serialize engagement metric to dictionary."""
        return {
            'id': str(metric.id),
            'announcement_id': str(metric.announcement_id),
            'total_recipients': metric.total_recipients,
            'delivered_count': metric.delivered_count,
            'delivery_rate': float(metric.delivery_rate),
            'unique_readers': metric.unique_readers,
            'read_rate': float(metric.read_rate),
            'acknowledged_count': metric.acknowledged_count,
            'acknowledgment_rate': float(metric.acknowledgment_rate),
            'engagement_score': float(metric.engagement_score),
            'average_reading_time_seconds': float(metric.average_reading_time_seconds or 0),
            'completion_rate': float(metric.completion_rate),
            'last_calculated_at': metric.last_calculated_at.isoformat(),
        }
    
    def _serialize_reading_analytic(self, analytic) -> Dict[str, Any]:
        """Serialize reading time analytic to dictionary."""
        return {
            'id': str(analytic.id),
            'announcement_id': str(analytic.announcement_id),
            'total_readers': analytic.total_readers,
            'average_reading_time_seconds': float(analytic.average_reading_time_seconds),
            'median_reading_time_seconds': float(analytic.median_reading_time_seconds),
            'min_reading_time_seconds': analytic.min_reading_time_seconds,
            'max_reading_time_seconds': analytic.max_reading_time_seconds,
            'quick_readers': analytic.quick_readers,
            'normal_readers': analytic.normal_readers,
            'thorough_readers': analytic.thorough_readers,
            'quick_readers_percentage': float(analytic.quick_readers_percentage),
            'normal_readers_percentage': float(analytic.normal_readers_percentage),
            'thorough_readers_percentage': float(analytic.thorough_readers_percentage),
            'reads_by_hour': analytic.reads_by_hour,
            'last_calculated_at': analytic.last_calculated_at.isoformat(),
        }