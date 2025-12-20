"""
Announcement Delivery Service

Multi-channel delivery orchestration service providing comprehensive
delivery management across email, SMS, push, and in-app channels.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass
import asyncio

from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, Field

from app.repositories.announcement import (
    AnnouncementDeliveryRepository,
    AnnouncementRepository,
    AnnouncementTargetingRepository,
)
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)
from app.core.events import EventPublisher
from app.integrations.email import EmailProvider
from app.integrations.sms import SMSProvider
from app.integrations.push import PushNotificationProvider


# ==================== DTOs ====================

class InitializeDeliveryDTO(BaseModel):
    """DTO for initializing delivery."""
    channels: Optional[List[str]] = None
    batch_size: int = Field(100, ge=10, le=1000)
    priority: int = Field(0, ge=0, le=10)
    
    @validator('channels')
    def validate_channels(cls, v):
        if v:
            valid_channels = ['email', 'sms', 'push', 'in_app']
            for channel in v:
                if channel not in valid_channels:
                    raise ValueError(f'Invalid channel: {channel}')
        return v


class RetryDeliveryDTO(BaseModel):
    """DTO for retrying failed delivery."""
    max_retries: int = Field(3, ge=1, le=10)
    use_fallback_channel: bool = True


class ChannelConfigurationDTO(BaseModel):
    """DTO for configuring delivery channel."""
    channel_type: str = Field(..., regex='^(email|sms|push|in_app)$')
    provider_name: str
    provider_config: Dict[str, Any]
    max_per_minute: Optional[int] = Field(None, ge=1)
    max_per_hour: Optional[int] = Field(None, ge=1)
    max_per_day: Optional[int] = Field(None, ge=1)
    priority: int = Field(0, ge=0, le=10)
    fallback_channel_id: Optional[UUID] = None


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

class AnnouncementDeliveryService:
    """
    Multi-channel delivery orchestration service.
    
    Provides comprehensive delivery management including:
    - Multi-channel delivery (email, SMS, push, in-app)
    - Batch processing and queue management
    - Delivery failure handling with retry logic
    - External provider integration (SendGrid, Twilio, FCM)
    - Channel optimization and selection
    - Rate limiting and throttling
    - Performance tracking and analytics
    """
    
    def __init__(
        self,
        session: Session,
        event_publisher: Optional[EventPublisher] = None,
        email_provider: Optional[EmailProvider] = None,
        sms_provider: Optional[SMSProvider] = None,
        push_provider: Optional[PushNotificationProvider] = None
    ):
        self.session = session
        self.repository = AnnouncementDeliveryRepository(session)
        self.announcement_repository = AnnouncementRepository(session)
        self.targeting_repository = AnnouncementTargetingRepository(session)
        self.event_publisher = event_publisher or EventPublisher()
        
        # External providers
        self.email_provider = email_provider or EmailProvider()
        self.sms_provider = sms_provider or SMSProvider()
        self.push_provider = push_provider or PushNotificationProvider()
    
    # ==================== Delivery Initialization ====================
    
    def initialize_delivery(
        self,
        announcement_id: UUID,
        dto: Optional[InitializeDeliveryDTO] = None
    ) -> ServiceResult:
        """
        Initialize delivery for announcement.
        
        Args:
            announcement_id: Announcement UUID
            dto: Delivery configuration
            
        Returns:
            ServiceResult with delivery initialization data
        """
        try:
            # Validate announcement
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            if not announcement.is_published:
                return ServiceResult.fail(
                    "Cannot initialize delivery for unpublished announcement",
                    error_code="INVALID_STATE"
                )
            
            # Get target audience
            reach = self.targeting_repository.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=False
            )
            
            student_ids = [UUID(sid) for sid in reach['student_ids']]
            
            if not student_ids:
                return ServiceResult.fail(
                    "No recipients to deliver to",
                    error_code="NO_RECIPIENTS"
                )
            
            # Determine channels
            channels = dto.channels if dto and dto.channels else []
            if not channels:
                if announcement.send_push:
                    channels.append('push')
                if announcement.send_email:
                    channels.append('email')
                if announcement.send_sms:
                    channels.append('sms')
                if 'in_app' not in channels:
                    channels.append('in_app')
            
            batch_size = dto.batch_size if dto else 100
            
            # Create delivery batches and records
            batches_created = 0
            deliveries_created = 0
            
            for channel in channels:
                num_batches = (len(student_ids) + batch_size - 1) // batch_size
                
                for batch_num in range(num_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min(start_idx + batch_size, len(student_ids))
                    batch_student_ids = student_ids[start_idx:end_idx]
                    
                    # Create batch
                    batch = self.repository.create_delivery_batch(
                        announcement_id=announcement_id,
                        channel=channel,
                        batch_number=batch_num + 1,
                        total_recipients=len(batch_student_ids)
                    )
                    batches_created += 1
                    
                    # Create delivery records
                    deliveries = self.repository.create_bulk_deliveries(
                        announcement_id=announcement_id,
                        recipient_ids=batch_student_ids,
                        channels=[channel],
                        batch_id=batch.id
                    )
                    deliveries_created += len(deliveries)
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('delivery.initialized', {
                'announcement_id': str(announcement_id),
                'total_recipients': len(student_ids),
                'channels': channels,
                'batches_created': batches_created,
                'deliveries_created': deliveries_created,
            })
            
            # Start processing asynchronously
            self._schedule_batch_processing(announcement_id)
            
            return ServiceResult.ok(data={
                'total_recipients': len(student_ids),
                'channels': channels,
                'batches_created': batches_created,
                'deliveries_created': deliveries_created,
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="INITIALIZATION_FAILED")
    
    # ==================== Batch Processing ====================
    
    def process_delivery_batch(
        self,
        batch_id: UUID,
        worker_id: str = 'default_worker'
    ) -> ServiceResult:
        """
        Process delivery batch.
        
        Args:
            batch_id: Batch UUID
            worker_id: Worker identifier
            
        Returns:
            ServiceResult with processing results
        """
        try:
            from app.models.announcement import DeliveryBatch
            
            # Start processing
            batch = self.repository.process_batch(
                batch_id=batch_id,
                worker_id=worker_id
            )
            
            self.session.commit()
            
            # Get pending deliveries
            deliveries = self.repository.find_pending_deliveries(
                channel=batch.channel,
                limit=batch.total_recipients
            )
            
            # Filter by batch
            batch_deliveries = [d for d in deliveries if d.batch_id == batch_id]
            
            sent_count = 0
            failed_count = 0
            
            # Process each delivery
            for delivery in batch_deliveries:
                try:
                    result = self._send_via_channel(
                        delivery=delivery,
                        channel=batch.channel
                    )
                    
                    if result['success']:
                        self.repository.mark_delivered(
                            delivery_id=delivery.id,
                            delivered_at=datetime.utcnow()
                        )
                        sent_count += 1
                    else:
                        self.repository.mark_failed(
                            delivery_id=delivery.id,
                            failure_reason=result.get('error', 'Unknown error'),
                            failure_code=result.get('error_code')
                        )
                        failed_count += 1
                        
                except Exception as e:
                    self.repository.mark_failed(
                        delivery_id=delivery.id,
                        failure_reason=str(e)
                    )
                    failed_count += 1
            
            # Complete batch
            self.repository.complete_batch(
                batch_id=batch_id,
                sent_count=sent_count,
                failed_count=failed_count
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('batch.processed', {
                'batch_id': str(batch_id),
                'sent': sent_count,
                'failed': failed_count,
                'total': sent_count + failed_count,
            })
            
            return ServiceResult.ok(data={
                'batch_id': str(batch_id),
                'sent': sent_count,
                'failed': failed_count,
                'total_processed': sent_count + failed_count,
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="BATCH_PROCESSING_FAILED")
    
    def process_all_pending_batches(
        self,
        limit: int = 10
    ) -> ServiceResult:
        """
        Process all pending delivery batches (background job).
        
        Args:
            limit: Maximum batches to process
            
        Returns:
            ServiceResult with processing summary
        """
        try:
            from app.models.announcement import DeliveryBatch
            
            # Get pending batches
            pending_batches = (
                self.session.query(DeliveryBatch)
                .filter(DeliveryBatch.status == 'pending')
                .order_by(
                    DeliveryBatch.scheduled_at.asc()
                )
                .limit(limit)
                .all()
            )
            
            results = []
            
            for batch in pending_batches:
                result = self.process_delivery_batch(
                    batch_id=batch.id,
                    worker_id='background_worker'
                )
                results.append({
                    'batch_id': str(batch.id),
                    'success': result.success,
                    'data': result.data if result.success else None,
                    'error': result.error if not result.success else None,
                })
            
            return ServiceResult.ok(data={
                'batches_processed': len(results),
                'results': results,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="BATCH_PROCESSING_FAILED")
    
    # ==================== Channel-Specific Delivery ====================
    
    def send_email_notifications(
        self,
        announcement_id: UUID,
        recipient_ids: List[UUID]
    ) -> ServiceResult:
        """
        Send email notifications for announcement.
        
        Args:
            announcement_id: Announcement UUID
            recipient_ids: List of recipient UUIDs
            
        Returns:
            ServiceResult with send results
        """
        try:
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            sent = []
            failed = []
            
            for recipient_id in recipient_ids:
                try:
                    # Get recipient
                    from app.models.user.user import User
                    recipient = self.session.get(User, recipient_id)
                    
                    if not recipient or not recipient.email:
                        failed.append({
                            'recipient_id': str(recipient_id),
                            'error': 'No email address'
                        })
                        continue
                    
                    # Send email
                    result = self.email_provider.send_email(
                        to_email=recipient.email,
                        subject=announcement.title,
                        html_content=announcement.content,
                        from_name='Hostel Management'
                    )
                    
                    if result['success']:
                        sent.append(str(recipient_id))
                    else:
                        failed.append({
                            'recipient_id': str(recipient_id),
                            'error': result.get('error')
                        })
                        
                except Exception as e:
                    failed.append({
                        'recipient_id': str(recipient_id),
                        'error': str(e)
                    })
            
            # Update announcement
            if sent:
                announcement.email_sent_at = datetime.utcnow()
                self.session.commit()
            
            return ServiceResult.ok(data={
                'sent_count': len(sent),
                'failed_count': len(failed),
                'sent': sent,
                'failed': failed,
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="EMAIL_SEND_FAILED")
    
    def send_sms_notifications(
        self,
        announcement_id: UUID,
        recipient_ids: List[UUID]
    ) -> ServiceResult:
        """
        Send SMS notifications for announcement.
        
        Args:
            announcement_id: Announcement UUID
            recipient_ids: List of recipient UUIDs
            
        Returns:
            ServiceResult with send results
        """
        try:
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Truncate content for SMS (max 160 chars)
            sms_content = announcement.title[:160]
            
            sent = []
            failed = []
            
            for recipient_id in recipient_ids:
                try:
                    from app.models.user.user import User
                    recipient = self.session.get(User, recipient_id)
                    
                    if not recipient or not recipient.phone:
                        failed.append({
                            'recipient_id': str(recipient_id),
                            'error': 'No phone number'
                        })
                        continue
                    
                    # Send SMS
                    result = self.sms_provider.send_sms(
                        to_phone=recipient.phone,
                        message=sms_content
                    )
                    
                    if result['success']:
                        sent.append(str(recipient_id))
                    else:
                        failed.append({
                            'recipient_id': str(recipient_id),
                            'error': result.get('error')
                        })
                        
                except Exception as e:
                    failed.append({
                        'recipient_id': str(recipient_id),
                        'error': str(e)
                    })
            
            # Update announcement
            if sent:
                announcement.sms_sent_at = datetime.utcnow()
                self.session.commit()
            
            return ServiceResult.ok(data={
                'sent_count': len(sent),
                'failed_count': len(failed),
                'sent': sent,
                'failed': failed,
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="SMS_SEND_FAILED")
    
    def send_push_notifications(
        self,
        announcement_id: UUID,
        recipient_ids: List[UUID]
    ) -> ServiceResult:
        """
        Send push notifications for announcement.
        
        Args:
            announcement_id: Announcement UUID
            recipient_ids: List of recipient UUIDs
            
        Returns:
            ServiceResult with send results
        """
        try:
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            sent = []
            failed = []
            
            for recipient_id in recipient_ids:
                try:
                    from app.models.user.user import User
                    recipient = self.session.get(User, recipient_id)
                    
                    if not recipient:
                        failed.append({
                            'recipient_id': str(recipient_id),
                            'error': 'Recipient not found'
                        })
                        continue
                    
                    # Get device tokens from user metadata
                    device_tokens = recipient.metadata.get('device_tokens', []) if recipient.metadata else []
                    
                    if not device_tokens:
                        failed.append({
                            'recipient_id': str(recipient_id),
                            'error': 'No device tokens'
                        })
                        continue
                    
                    # Send push notification
                    result = self.push_provider.send_push(
                        device_tokens=device_tokens,
                        title=announcement.title,
                        body=announcement.content[:200],  # Truncate
                        data={
                            'announcement_id': str(announcement_id),
                            'type': 'announcement',
                        }
                    )
                    
                    if result['success']:
                        sent.append(str(recipient_id))
                    else:
                        failed.append({
                            'recipient_id': str(recipient_id),
                            'error': result.get('error')
                        })
                        
                except Exception as e:
                    failed.append({
                        'recipient_id': str(recipient_id),
                        'error': str(e)
                    })
            
            # Update announcement
            if sent:
                announcement.push_sent_at = datetime.utcnow()
                self.session.commit()
            
            return ServiceResult.ok(data={
                'sent_count': len(sent),
                'failed_count': len(failed),
                'sent': sent,
                'failed': failed,
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="PUSH_SEND_FAILED")
    
    # ==================== Failure Handling ====================
    
    def retry_failed_deliveries(
        self,
        announcement_id: UUID,
        dto: Optional[RetryDeliveryDTO] = None
    ) -> ServiceResult:
        """
        Retry failed deliveries for announcement.
        
        Args:
            announcement_id: Announcement UUID
            dto: Retry configuration
            
        Returns:
            ServiceResult with retry results
        """
        try:
            failed_deliveries = self.repository.find_failed_deliveries(
                announcement_id=announcement_id,
                permanent_only=False
            )
            
            retried = []
            still_failed = []
            
            for delivery in failed_deliveries:
                # Check retry limit
                max_retries = dto.max_retries if dto else 3
                if delivery.retry_count >= max_retries:
                    still_failed.append(str(delivery.id))
                    continue
                
                try:
                    # Retry delivery
                    result = self._send_via_channel(
                        delivery=delivery,
                        channel=delivery.channel
                    )
                    
                    if result['success']:
                        self.repository.mark_delivered(
                            delivery_id=delivery.id,
                            delivered_at=datetime.utcnow()
                        )
                        retried.append(str(delivery.id))
                    else:
                        # Try fallback if configured
                        if dto and dto.use_fallback_channel:
                            fallback_result = self._try_fallback_channel(delivery)
                            if fallback_result['success']:
                                retried.append(str(delivery.id))
                            else:
                                still_failed.append(str(delivery.id))
                        else:
                            still_failed.append(str(delivery.id))
                            
                except Exception as e:
                    still_failed.append(str(delivery.id))
            
            self.session.commit()
            
            return ServiceResult.ok(data={
                'total_failed': len(failed_deliveries),
                'retried_success': len(retried),
                'still_failed': len(still_failed),
                'retried': retried,
                'failed': still_failed,
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="RETRY_FAILED")
    
    # ==================== Channel Configuration ====================
    
    def configure_channel(
        self,
        hostel_id: UUID,
        dto: ChannelConfigurationDTO
    ) -> ServiceResult:
        """
        Configure delivery channel.
        
        Args:
            hostel_id: Hostel UUID
            dto: Channel configuration
            
        Returns:
            ServiceResult with channel data
        """
        try:
            channel = self.repository.configure_delivery_channel(
                hostel_id=hostel_id,
                channel_type=dto.channel_type,
                provider_name=dto.provider_name,
                provider_config=dto.provider_config,
                max_per_minute=dto.max_per_minute,
                max_per_hour=dto.max_per_hour,
                max_per_day=dto.max_per_day,
                priority=dto.priority,
                fallback_channel_id=dto.fallback_channel_id
            )
            
            self.session.commit()
            
            return ServiceResult.ok(
                data=self._serialize_channel(channel),
                channel_id=str(channel.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="CHANNEL_CONFIG_FAILED")
    
    # ==================== Analytics ====================
    
    def get_delivery_statistics(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Get delivery statistics for announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with statistics
        """
        try:
            stats = self.repository.get_delivery_statistics(announcement_id)
            
            return ServiceResult.ok(data=stats)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="STATS_FAILED")
    
    # ==================== Helper Methods ====================
    
    def _send_via_channel(
        self,
        delivery,
        channel: str
    ) -> Dict[str, Any]:
        """Send via specific channel."""
        try:
            if channel == 'email':
                if not delivery.recipient_email:
                    return {'success': False, 'error': 'No email address'}
                
                announcement = self.session.get(
                    self.announcement_repository.model,
                    delivery.announcement_id
                )
                
                return self.email_provider.send_email(
                    to_email=delivery.recipient_email,
                    subject=announcement.title,
                    html_content=announcement.content,
                    from_name='Hostel Management'
                )
                
            elif channel == 'sms':
                if not delivery.recipient_phone:
                    return {'success': False, 'error': 'No phone number'}
                
                announcement = self.session.get(
                    self.announcement_repository.model,
                    delivery.announcement_id
                )
                
                return self.sms_provider.send_sms(
                    to_phone=delivery.recipient_phone,
                    message=announcement.title[:160]
                )
                
            elif channel == 'push':
                if not delivery.recipient_device_token:
                    return {'success': False, 'error': 'No device token'}
                
                announcement = self.session.get(
                    self.announcement_repository.model,
                    delivery.announcement_id
                )
                
                return self.push_provider.send_push(
                    device_tokens=[delivery.recipient_device_token],
                    title=announcement.title,
                    body=announcement.content[:200],
                    data={'announcement_id': str(delivery.announcement_id)}
                )
                
            elif channel == 'in_app':
                # In-app notification is just marking as delivered
                return {'success': True}
            
            else:
                return {'success': False, 'error': f'Unknown channel: {channel}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _try_fallback_channel(self, delivery) -> Dict[str, Any]:
        """Try fallback channel for failed delivery."""
        # Get channel configuration
        from app.models.announcement import DeliveryChannel
        
        channel_config = (
            self.session.query(DeliveryChannel)
            .filter(
                DeliveryChannel.channel_type == delivery.channel,
                DeliveryChannel.is_enabled == True
            )
            .first()
        )
        
        if not channel_config or not channel_config.fallback_channel_id:
            return {'success': False, 'error': 'No fallback configured'}
        
        fallback_config = self.session.get(
            DeliveryChannel,
            channel_config.fallback_channel_id
        )
        
        if not fallback_config:
            return {'success': False, 'error': 'Fallback channel not found'}
        
        # Try fallback
        return self._send_via_channel(delivery, fallback_config.channel_type)
    
    def _schedule_batch_processing(self, announcement_id: UUID):
        """Schedule background batch processing."""
        # This would integrate with Celery or similar
        pass
    
    def _serialize_channel(self, channel) -> Dict[str, Any]:
        """Serialize channel to dictionary."""
        return {
            'id': str(channel.id),
            'hostel_id': str(channel.hostel_id),
            'channel_type': channel.channel_type,
            'provider_name': channel.provider_name,
            'is_enabled': channel.is_enabled,
            'priority': channel.priority,
            'max_per_minute': channel.max_per_minute,
            'max_per_hour': channel.max_per_hour,
            'max_per_day': channel.max_per_day,
            'is_healthy': channel.is_healthy,
            'created_at': channel.created_at.isoformat(),
        }