"""
Announcement Delivery Repository

Multi-channel delivery with optimization, failover, and performance tracking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal
from collections import defaultdict

from sqlalchemy import and_, or_, func, select, case
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select

from app.models.announcement import (
    AnnouncementDelivery,
    DeliveryChannel,
    DeliveryBatch,
    DeliveryFailure,
    DeliveryRetry,
    Announcement,
)
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.core1.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)


class AnnouncementDeliveryRepository(BaseRepository[AnnouncementDelivery]):
    """
    Repository for announcement delivery management.
    
    Provides comprehensive delivery capabilities including:
    - Multi-channel delivery (email, SMS, push, in-app)
    - Batch processing and queue management
    - Delivery failure handling and retry logic
    - Channel optimization and selection
    - Performance tracking and analytics
    - Rate limiting and throttling
    """
    
    def __init__(self, session: Session):
        super().__init__(AnnouncementDelivery, session)
    
    # ==================== Delivery Creation ====================
    
    def create_delivery(
        self,
        announcement_id: UUID,
        recipient_id: UUID,
        channel: str,
        scheduled_for: Optional[datetime] = None,
        batch_id: Optional[UUID] = None,
        **kwargs
    ) -> AnnouncementDelivery:
        """
        Create delivery record for announcement recipient.
        
        Args:
            announcement_id: Announcement UUID
            recipient_id: Recipient user UUID
            channel: Delivery channel
            scheduled_for: Scheduled delivery time
            batch_id: Associated batch UUID
            **kwargs: Additional delivery parameters
            
        Returns:
            Created delivery record
        """
        # Validate channel
        if channel not in ['email', 'sms', 'push', 'in_app']:
            raise ValidationError(f"Invalid delivery channel: {channel}")
        
        # Get recipient contact info
        recipient = self.session.get(User, recipient_id)
        if not recipient:
            raise ResourceNotFoundError(f"Recipient {recipient_id} not found")
        
        delivery = AnnouncementDelivery(
            announcement_id=announcement_id,
            recipient_id=recipient_id,
            channel=channel,
            scheduled_for=scheduled_for or datetime.utcnow(),
            batch_id=batch_id,
            recipient_email=recipient.email if channel == 'email' else None,
            recipient_phone=recipient.phone if channel == 'sms' else None,
            status='pending',
            **kwargs
        )
        
        self.session.add(delivery)
        self.session.flush()
        return delivery
    
    def create_bulk_deliveries(
        self,
        announcement_id: UUID,
        recipient_ids: List[UUID],
        channels: List[str],
        batch_id: Optional[UUID] = None
    ) -> List[AnnouncementDelivery]:
        """
        Create multiple delivery records efficiently.
        
        Args:
            announcement_id: Announcement UUID
            recipient_ids: List of recipient UUIDs
            channels: List of delivery channels
            batch_id: Associated batch UUID
            
        Returns:
            List of created deliveries
        """
        deliveries = []
        
        for recipient_id in recipient_ids:
            for channel in channels:
                try:
                    delivery = self.create_delivery(
                        announcement_id=announcement_id,
                        recipient_id=recipient_id,
                        channel=channel,
                        batch_id=batch_id
                    )
                    deliveries.append(delivery)
                except Exception as e:
                    # Log error but continue with other deliveries
                    print(f"Error creating delivery: {e}")
                    continue
        
        self.session.flush()
        return deliveries
    
    # ==================== Delivery Execution ====================
    
    def execute_delivery(
        self,
        delivery_id: UUID,
        provider: str,
        provider_message_id: Optional[str] = None,
        provider_response: Optional[Dict] = None
    ) -> AnnouncementDelivery:
        """
        Execute delivery and update status.
        
        Args:
            delivery_id: Delivery UUID
            provider: Service provider name
            provider_message_id: Provider's message ID
            provider_response: Provider response data
            
        Returns:
            Updated delivery record
        """
        delivery = self.find_by_id(delivery_id)
        if not delivery:
            raise ResourceNotFoundError(f"Delivery {delivery_id} not found")
        
        start_time = datetime.utcnow()
        
        delivery.status = 'processing'
        delivery.provider = provider
        delivery.provider_message_id = provider_message_id
        delivery.provider_response = provider_response
        
        self.session.flush()
        return delivery
    
    def mark_delivered(
        self,
        delivery_id: UUID,
        delivered_at: Optional[datetime] = None
    ) -> AnnouncementDelivery:
        """
        Mark delivery as successfully delivered.
        
        Args:
            delivery_id: Delivery UUID
            delivered_at: Delivery timestamp
            
        Returns:
            Updated delivery record
        """
        delivery = self.find_by_id(delivery_id)
        if not delivery:
            raise ResourceNotFoundError(f"Delivery {delivery_id} not found")
        
        now = delivered_at or datetime.utcnow()
        
        delivery.is_delivered = True
        delivery.delivered_at = now
        delivery.status = 'completed'
        
        if delivery.scheduled_for:
            time_diff = now - delivery.scheduled_for
            delivery.delivery_time_seconds = int(time_diff.total_seconds())
        
        self.session.flush()
        return delivery
    
    def mark_failed(
        self,
        delivery_id: UUID,
        failure_reason: str,
        failure_code: Optional[str] = None,
        is_permanent: bool = False
    ) -> AnnouncementDelivery:
        """
        Mark delivery as failed.
        
        Args:
            delivery_id: Delivery UUID
            failure_reason: Reason for failure
            failure_code: Error code
            is_permanent: Whether failure is permanent
            
        Returns:
            Updated delivery record
        """
        delivery = self.find_by_id(delivery_id)
        if not delivery:
            raise ResourceNotFoundError(f"Delivery {delivery_id} not found")
        
        delivery.status = 'failed'
        delivery.failure_reason = failure_reason
        delivery.failure_code = failure_code
        
        # Record failure
        self._record_failure(
            delivery=delivery,
            failure_reason=failure_reason,
            failure_code=failure_code,
            is_permanent=is_permanent
        )
        
        # Schedule retry if not permanent and under limit
        if not is_permanent and delivery.retry_count < delivery.max_retries:
            self._schedule_retry(delivery)
        
        self.session.flush()
        return delivery
    
    # ==================== Batch Processing ====================
    
    def create_delivery_batch(
        self,
        announcement_id: UUID,
        channel: str,
        batch_number: int,
        total_recipients: int,
        scheduled_at: Optional[datetime] = None
    ) -> DeliveryBatch:
        """
        Create delivery batch for processing.
        
        Args:
            announcement_id: Announcement UUID
            channel: Delivery channel
            batch_number: Batch sequence number
            total_recipients: Total recipients in batch
            scheduled_at: Scheduled processing time
            
        Returns:
            Created batch
        """
        batch = DeliveryBatch(
            announcement_id=announcement_id,
            batch_number=batch_number,
            batch_size=total_recipients,
            channel=channel,
            total_recipients=total_recipients,
            scheduled_at=scheduled_at or datetime.utcnow(),
            status='pending',
        )
        
        self.session.add(batch)
        self.session.flush()
        return batch
    
    def process_batch(
        self,
        batch_id: UUID,
        worker_id: str
    ) -> DeliveryBatch:
        """
        Process delivery batch.
        
        Args:
            batch_id: Batch UUID
            worker_id: Worker processing batch
            
        Returns:
            Updated batch
        """
        batch = self.session.get(DeliveryBatch, batch_id)
        if not batch:
            raise ResourceNotFoundError(f"Batch {batch_id} not found")
        
        if batch.status != 'pending':
            raise BusinessLogicError(
                f"Cannot process batch in {batch.status} status"
            )
        
        batch.status = 'processing'
        batch.started_at = datetime.utcnow()
        batch.worker_id = worker_id
        
        self.session.flush()
        return batch
    
    def complete_batch(
        self,
        batch_id: UUID,
        sent_count: int,
        failed_count: int
    ) -> DeliveryBatch:
        """
        Mark batch as completed.
        
        Args:
            batch_id: Batch UUID
            sent_count: Number successfully sent
            failed_count: Number failed
            
        Returns:
            Completed batch
        """
        batch = self.session.get(DeliveryBatch, batch_id)
        if not batch:
            raise ResourceNotFoundError(f"Batch {batch_id} not found")
        
        now = datetime.utcnow()
        
        batch.status = 'completed'
        batch.completed_at = now
        batch.processed_count = sent_count + failed_count
        batch.sent_count = sent_count
        batch.failed_count = failed_count
        
        if batch.started_at:
            duration = now - batch.started_at
            batch.processing_duration_seconds = int(duration.total_seconds())
            
            if sent_count > 0:
                batch.average_delivery_time_seconds = Decimal(
                    batch.processing_duration_seconds / sent_count
                )
        
        self.session.flush()
        return batch
    
    # ==================== Channel Management ====================
    
    def get_optimal_channel(
        self,
        announcement_id: UUID,
        recipient_id: UUID,
        preferred_channels: Optional[List[str]] = None
    ) -> str:
        """
        Determine optimal delivery channel for recipient.
        
        Args:
            announcement_id: Announcement UUID
            recipient_id: Recipient UUID
            preferred_channels: Preferred channel list
            
        Returns:
            Optimal channel name
        """
        announcement = self.session.get(Announcement, announcement_id)
        recipient = self.session.get(User, recipient_id)
        
        if not announcement or not recipient:
            return 'in_app'  # Default fallback
        
        # Get recipient preferences
        prefs = recipient.metadata.get('notification_preferences', {}) if recipient.metadata else {}
        
        # Build available channels based on announcement settings
        available_channels = []
        if announcement.send_push and prefs.get('push', True):
            available_channels.append('push')
        if announcement.send_email and prefs.get('email', True) and recipient.email:
            available_channels.append('email')
        if announcement.send_sms and prefs.get('sms', False) and recipient.phone:
            available_channels.append('sms')
        
        # Always include in-app
        available_channels.append('in_app')
        
        # Filter by preferred channels if specified
        if preferred_channels:
            available_channels = [
                ch for ch in available_channels if ch in preferred_channels
            ]
        
        if not available_channels:
            return 'in_app'
        
        # Get channel performance
        channel_performance = self._get_channel_performance(announcement.hostel_id)
        
        # Select channel with best performance
        best_channel = max(
            available_channels,
            key=lambda ch: channel_performance.get(ch, {}).get('success_rate', 0)
        )
        
        return best_channel
    
    def configure_delivery_channel(
        self,
        hostel_id: UUID,
        channel_type: str,
        provider_name: str,
        provider_config: Dict[str, Any],
        **kwargs
    ) -> DeliveryChannel:
        """
        Configure delivery channel.
        
        Args:
            hostel_id: Hostel UUID
            channel_type: Channel type
            provider_name: Provider name
            provider_config: Provider configuration
            **kwargs: Additional parameters
            
        Returns:
            Created/updated channel configuration
        """
        # Check for existing configuration
        existing = (
            self.session.query(DeliveryChannel)
            .filter(
                DeliveryChannel.hostel_id == hostel_id,
                DeliveryChannel.channel_type == channel_type,
                DeliveryChannel.provider_name == provider_name
            )
            .first()
        )
        
        if existing:
            existing.provider_config = provider_config
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            self.session.flush()
            return existing
        
        channel = DeliveryChannel(
            hostel_id=hostel_id,
            channel_type=channel_type,
            provider_name=provider_name,
            provider_config=provider_config,
            is_enabled=True,
            **kwargs
        )
        
        self.session.add(channel)
        self.session.flush()
        return channel
    
    # ==================== Query Operations ====================
    
    def find_pending_deliveries(
        self,
        channel: Optional[str] = None,
        limit: int = 100
    ) -> List[AnnouncementDelivery]:
        """
        Find pending deliveries ready for processing.
        
        Args:
            channel: Optional channel filter
            limit: Maximum results
            
        Returns:
            List of pending deliveries
        """
        now = datetime.utcnow()
        
        query = (
            select(AnnouncementDelivery)
            .where(
                AnnouncementDelivery.status == 'pending',
                or_(
                    AnnouncementDelivery.scheduled_for.is_(None),
                    AnnouncementDelivery.scheduled_for <= now
                ),
                or_(
                    AnnouncementDelivery.next_retry_at.is_(None),
                    AnnouncementDelivery.next_retry_at <= now
                )
            )
            .order_by(AnnouncementDelivery.scheduled_for.asc())
            .limit(limit)
        )
        
        if channel:
            query = query.where(AnnouncementDelivery.channel == channel)
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_failed_deliveries(
        self,
        announcement_id: Optional[UUID] = None,
        permanent_only: bool = False,
        limit: int = 100
    ) -> List[AnnouncementDelivery]:
        """
        Find failed deliveries.
        
        Args:
            announcement_id: Optional announcement filter
            permanent_only: Only permanent failures
            limit: Maximum results
            
        Returns:
            List of failed deliveries
        """
        query = (
            select(AnnouncementDelivery)
            .where(AnnouncementDelivery.status == 'failed')
            .order_by(AnnouncementDelivery.created_at.desc())
            .limit(limit)
        )
        
        if announcement_id:
            query = query.where(
                AnnouncementDelivery.announcement_id == announcement_id
            )
        
        if permanent_only:
            # Join with failures to filter permanent
            query = query.join(DeliveryFailure).where(
                DeliveryFailure.is_permanent == True
            )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_delivery_statistics(
        self,
        announcement_id: UUID
    ) -> Dict[str, Any]:
        """
        Get delivery statistics for announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Statistics dictionary
        """
        deliveries = (
            self.session.query(AnnouncementDelivery)
            .filter(AnnouncementDelivery.announcement_id == announcement_id)
            .all()
        )
        
        total = len(deliveries)
        delivered = sum(1 for d in deliveries if d.is_delivered)
        failed = sum(1 for d in deliveries if d.status == 'failed')
        pending = sum(1 for d in deliveries if d.status == 'pending')
        
        # Channel breakdown
        channel_stats = defaultdict(lambda: {'total': 0, 'delivered': 0, 'failed': 0})
        for d in deliveries:
            channel_stats[d.channel]['total'] += 1
            if d.is_delivered:
                channel_stats[d.channel]['delivered'] += 1
            elif d.status == 'failed':
                channel_stats[d.channel]['failed'] += 1
        
        # Calculate average delivery time
        delivered_with_time = [
            d for d in deliveries
            if d.is_delivered and d.delivery_time_seconds
        ]
        avg_delivery_time = (
            sum(d.delivery_time_seconds for d in delivered_with_time) / len(delivered_with_time)
            if delivered_with_time else 0
        )
        
        return {
            'total_deliveries': total,
            'delivered': delivered,
            'failed': failed,
            'pending': pending,
            'delivery_rate': (delivered / total * 100) if total > 0 else 0,
            'failure_rate': (failed / total * 100) if total > 0 else 0,
            'average_delivery_time_seconds': round(avg_delivery_time, 2),
            'channel_breakdown': dict(channel_stats),
        }
    
    # ==================== Helper Methods ====================
    
    def _record_failure(
        self,
        delivery: AnnouncementDelivery,
        failure_reason: str,
        failure_code: Optional[str],
        is_permanent: bool
    ) -> DeliveryFailure:
        """Record delivery failure."""
        failure = DeliveryFailure(
            delivery_id=delivery.id,
            announcement_id=delivery.announcement_id,
            recipient_id=delivery.recipient_id,
            channel=delivery.channel,
            failure_reason=failure_reason,
            failure_code=failure_code,
            failed_at=datetime.utcnow(),
            provider_name=delivery.provider,
            provider_error_message=delivery.provider_response.get('error') if delivery.provider_response else None,
            recipient_contact=(
                delivery.recipient_email if delivery.channel == 'email'
                else delivery.recipient_phone if delivery.channel == 'sms'
                else None
            ),
            is_permanent=is_permanent,
            is_temporary=not is_permanent,
        )
        
        self.session.add(failure)
        return failure
    
    def _schedule_retry(self, delivery: AnnouncementDelivery) -> DeliveryRetry:
        """Schedule delivery retry."""
        delivery.retry_count += 1
        
        # Calculate delay with exponential backoff
        delay_minutes = 2 ** delivery.retry_count  # 2, 4, 8, 16...
        delay = timedelta(minutes=min(delay_minutes, 60))  # Max 1 hour
        
        delivery.next_retry_at = datetime.utcnow() + delay
        delivery.status = 'pending'
        
        # Record retry
        retry = DeliveryRetry(
            delivery_id=delivery.id,
            retry_number=delivery.retry_count,
            retry_scheduled_at=delivery.next_retry_at,
            retry_strategy='exponential_backoff',
            delay_seconds=int(delay.total_seconds()),
            channel_used=delivery.channel,
            status='pending',
        )
        
        self.session.add(retry)
        return retry
    
    def _get_channel_performance(
        self,
        hostel_id: UUID
    ) -> Dict[str, Dict[str, float]]:
        """Get channel performance metrics."""
        channels = (
            self.session.query(DeliveryChannel)
            .filter(
                DeliveryChannel.hostel_id == hostel_id,
                DeliveryChannel.is_enabled == True
            )
            .all()
        )
        
        performance = {}
        for channel in channels:
            if channel.total_sent > 0:
                success_rate = (channel.total_delivered / channel.total_sent) * 100
            else:
                success_rate = 0
            
            performance[channel.channel_type] = {
                'success_rate': success_rate,
                'total_sent': channel.total_sent,
                'total_delivered': channel.total_delivered,
                'is_healthy': channel.is_healthy,
            }
        
        return performance