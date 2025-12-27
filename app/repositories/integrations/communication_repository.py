"""
Communication Repository for multi-channel messaging management.

This repository handles all communication channels including email, SMS,
WhatsApp, push notifications, and in-app messaging with delivery tracking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4
from enum import Enum as PyEnum

from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.core1.exceptions import NotFoundException, ValidationException


class CommunicationChannel(str, PyEnum):
    """Communication channel enumeration."""
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH_NOTIFICATION = "push_notification"
    IN_APP = "in_app"
    VOICE_CALL = "voice_call"


class CommunicationStatus(str, PyEnum):
    """Communication delivery status."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"
    SPAM = "spam"


class CommunicationPriority(str, PyEnum):
    """Communication priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class CommunicationType(str, PyEnum):
    """Communication type categorization."""
    TRANSACTIONAL = "transactional"
    MARKETING = "marketing"
    NOTIFICATION = "notification"
    ALERT = "alert"
    REMINDER = "reminder"
    ANNOUNCEMENT = "announcement"


class CommunicationRepository(BaseRepository):
    """
    Repository for multi-channel communication management.
    
    Provides methods for sending messages across multiple channels,
    tracking delivery, managing templates, and analyzing engagement.
    """
    
    def __init__(self, session: Session):
        """Initialize communication repository."""
        self.session = session
    
    # ============================================================================
    # MESSAGE SENDING
    # ============================================================================
    
    async def send_message(
        self,
        channel: CommunicationChannel,
        recipient: Union[str, List[str]],
        content: Dict[str, Any],
        sender: Optional[str] = None,
        priority: CommunicationPriority = CommunicationPriority.MEDIUM,
        communication_type: CommunicationType = CommunicationType.NOTIFICATION,
        template_id: Optional[UUID] = None,
        scheduled_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send message through specified channel.
        
        Args:
            channel: Communication channel
            recipient: Recipient address(es)
            content: Message content
            sender: Sender identifier
            priority: Message priority
            communication_type: Type of communication
            template_id: Optional template ID
            scheduled_at: Optional scheduled send time
            metadata: Additional metadata
            audit_context: Audit information
            
        Returns:
            Message record with delivery information
        """
        # Handle multiple recipients
        recipients = recipient if isinstance(recipient, list) else [recipient]
        
        # Validate recipients
        await self._validate_recipients(channel, recipients)
        
        # Check opt-out status
        recipients = await self._filter_opted_out_recipients(
            channel,
            recipients,
            communication_type
        )
        
        if not recipients:
            raise ValidationException("All recipients have opted out")
        
        # Create message record
        message = {
            "id": uuid4(),
            "channel": channel,
            "recipients": recipients,
            "sender": sender,
            "subject": content.get("subject"),
            "body": content.get("body"),
            "html_body": content.get("html_body"),
            "attachments": content.get("attachments", []),
            "priority": priority,
            "communication_type": communication_type,
            "template_id": template_id,
            "status": CommunicationStatus.PENDING,
            "scheduled_at": scheduled_at or datetime.utcnow(),
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # If scheduled for future, queue it
        if scheduled_at and scheduled_at > datetime.utcnow():
            message["status"] = CommunicationStatus.QUEUED
            return message
        
        # Send immediately based on priority
        if priority == CommunicationPriority.URGENT:
            delivery_result = await self._send_immediately(message)
        else:
            delivery_result = await self._queue_for_delivery(message)
        
        message.update(delivery_result)
        
        return message
    
    async def send_bulk_messages(
        self,
        channel: CommunicationChannel,
        recipients: List[str],
        content: Dict[str, Any],
        batch_size: int = 100,
        delay_between_batches_seconds: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send messages to multiple recipients in batches.
        
        Args:
            channel: Communication channel
            recipients: List of recipient addresses
            content: Message content
            batch_size: Number of messages per batch
            delay_between_batches_seconds: Delay between batches
            **kwargs: Additional send_message arguments
            
        Returns:
            Bulk send summary
        """
        total_recipients = len(recipients)
        batches = [
            recipients[i:i + batch_size]
            for i in range(0, total_recipients, batch_size)
        ]
        
        results = {
            "total_recipients": total_recipients,
            "total_batches": len(batches),
            "successful": 0,
            "failed": 0,
            "queued": 0,
            "batch_results": []
        }
        
        for batch_num, batch in enumerate(batches, 1):
            batch_result = {
                "batch_number": batch_num,
                "recipients": len(batch),
                "successful": 0,
                "failed": 0
            }
            
            for recipient in batch:
                try:
                    message = await self.send_message(
                        channel=channel,
                        recipient=recipient,
                        content=content,
                        **kwargs
                    )
                    
                    if message["status"] in [
                        CommunicationStatus.SENT,
                        CommunicationStatus.DELIVERED
                    ]:
                        batch_result["successful"] += 1
                        results["successful"] += 1
                    elif message["status"] == CommunicationStatus.QUEUED:
                        results["queued"] += 1
                    else:
                        batch_result["failed"] += 1
                        results["failed"] += 1
                        
                except Exception as e:
                    batch_result["failed"] += 1
                    results["failed"] += 1
            
            results["batch_results"].append(batch_result)
            
            # Delay between batches
            if batch_num < len(batches):
                await self._delay(delay_between_batches_seconds)
        
        return results
    
    async def send_templated_message(
        self,
        template_id: UUID,
        recipient: Union[str, List[str]],
        variables: Dict[str, Any],
        channel: Optional[CommunicationChannel] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send message using template.
        
        Args:
            template_id: Template ID
            recipient: Recipient address(es)
            variables: Template variables
            channel: Optional channel override
            **kwargs: Additional send_message arguments
            
        Returns:
            Message record
        """
        template = await self.get_template_by_id(template_id)
        
        # Use template's default channel if not specified
        send_channel = channel or template["default_channel"]
        
        # Render template with variables
        content = await self._render_template(template, variables)
        
        return await self.send_message(
            channel=send_channel,
            recipient=recipient,
            content=content,
            template_id=template_id,
            communication_type=template["communication_type"],
            **kwargs
        )
    
    # ============================================================================
    # DELIVERY TRACKING
    # ============================================================================
    
    async def track_delivery_event(
        self,
        message_id: UUID,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Track delivery event for message.
        
        Args:
            message_id: Message ID
            event_type: Event type (sent, delivered, opened, clicked, etc.)
            event_data: Event-specific data
            
        Returns:
            Updated message status
        """
        message = await self.get_message_by_id(message_id)
        
        event = {
            "id": uuid4(),
            "message_id": message_id,
            "event_type": event_type,
            "event_data": event_data or {},
            "occurred_at": datetime.utcnow()
        }
        
        # Update message status based on event
        status_updates = {
            "sent": CommunicationStatus.SENT,
            "delivered": CommunicationStatus.DELIVERED,
            "opened": CommunicationStatus.READ,
            "read": CommunicationStatus.READ,
            "failed": CommunicationStatus.FAILED,
            "bounced": CommunicationStatus.BOUNCED,
            "spam": CommunicationStatus.SPAM
        }
        
        if event_type in status_updates:
            message["status"] = status_updates[event_type]
            message[f"{event_type}_at"] = datetime.utcnow()
        
        # Track engagement events
        if event_type in ["opened", "clicked", "replied"]:
            if "engagement_events" not in message:
                message["engagement_events"] = []
            message["engagement_events"].append(event)
        
        message["updated_at"] = datetime.utcnow()
        
        return message
    
    async def get_delivery_status(
        self,
        message_id: UUID
    ) -> Dict[str, Any]:
        """
        Get detailed delivery status for message.
        
        Args:
            message_id: Message ID
            
        Returns:
            Delivery status details
        """
        message = await self.get_message_by_id(message_id)
        
        delivery_timeline = []
        
        # Build timeline from message fields
        if message.get("queued_at"):
            delivery_timeline.append({
                "event": "queued",
                "timestamp": message["queued_at"]
            })
        
        if message.get("sent_at"):
            delivery_timeline.append({
                "event": "sent",
                "timestamp": message["sent_at"]
            })
        
        if message.get("delivered_at"):
            delivery_timeline.append({
                "event": "delivered",
                "timestamp": message["delivered_at"]
            })
        
        if message.get("opened_at"):
            delivery_timeline.append({
                "event": "opened",
                "timestamp": message["opened_at"]
            })
        
        return {
            "message_id": message_id,
            "current_status": message["status"],
            "delivery_timeline": sorted(
                delivery_timeline,
                key=lambda x: x["timestamp"]
            ),
            "engagement_events": message.get("engagement_events", []),
            "error_message": message.get("error_message"),
            "retry_count": message.get("retry_count", 0)
        }
    
    async def retry_failed_message(
        self,
        message_id: UUID,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Retry sending failed message.
        
        Args:
            message_id: Message ID
            max_retries: Maximum retry attempts
            
        Returns:
            Retry result
        """
        message = await self.get_message_by_id(message_id)
        
        if message["status"] not in [
            CommunicationStatus.FAILED,
            CommunicationStatus.BOUNCED
        ]:
            raise ValidationException(
                f"Cannot retry message with status: {message['status']}"
            )
        
        retry_count = message.get("retry_count", 0)
        
        if retry_count >= max_retries:
            raise ValidationException(
                f"Maximum retry attempts ({max_retries}) exceeded"
            )
        
        message["retry_count"] = retry_count + 1
        message["status"] = CommunicationStatus.PENDING
        message["last_retry_at"] = datetime.utcnow()
        
        # Attempt resend
        delivery_result = await self._send_immediately(message)
        message.update(delivery_result)
        
        return message
    
    # ============================================================================
    # TEMPLATE MANAGEMENT
    # ============================================================================
    
    async def create_template(
        self,
        name: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        channel: CommunicationChannel = CommunicationChannel.EMAIL,
        communication_type: CommunicationType = CommunicationType.NOTIFICATION,
        variables: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create message template.
        
        Args:
            name: Template name
            subject: Message subject template
            body: Message body template
            html_body: HTML body template
            channel: Default channel
            communication_type: Communication type
            variables: Template variables
            metadata: Additional metadata
            audit_context: Audit information
            
        Returns:
            Created template
        """
        template = {
            "id": uuid4(),
            "name": name,
            "subject": subject,
            "body": body,
            "html_body": html_body,
            "default_channel": channel,
            "communication_type": communication_type,
            "variables": variables or [],
            "metadata": metadata or {},
            "is_active": True,
            "version": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Validate template syntax
        await self._validate_template_syntax(template)
        
        return template
    
    async def update_template(
        self,
        template_id: UUID,
        update_data: Dict[str, Any],
        create_version: bool = True,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update message template.
        
        Args:
            template_id: Template ID
            update_data: Update data
            create_version: Whether to create new version
            audit_context: Audit information
            
        Returns:
            Updated template
        """
        template = await self.get_template_by_id(template_id)
        
        if create_version:
            # Archive current version
            await self._archive_template_version(template)
            update_data["version"] = template["version"] + 1
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Validate if template content changed
        if any(key in update_data for key in ["subject", "body", "html_body"]):
            test_template = {**template, **update_data}
            await self._validate_template_syntax(test_template)
        
        template.update(update_data)
        return template
    
    async def get_template_by_id(
        self,
        template_id: UUID
    ) -> Dict[str, Any]:
        """Get template by ID."""
        # Placeholder implementation
        return {
            "id": template_id,
            "name": "Welcome Email",
            "default_channel": CommunicationChannel.EMAIL,
            "communication_type": CommunicationType.TRANSACTIONAL
        }
    
    async def get_template_versions(
        self,
        template_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all versions of a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            List of template versions
        """
        # Placeholder implementation
        return []
    
    # ============================================================================
    # PREFERENCE MANAGEMENT
    # ============================================================================
    
    async def update_recipient_preferences(
        self,
        recipient: str,
        channel: CommunicationChannel,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update recipient communication preferences.
        
        Args:
            recipient: Recipient identifier
            channel: Communication channel
            preferences: Preference settings
            
        Returns:
            Updated preferences
        """
        preference_record = {
            "id": uuid4(),
            "recipient": recipient,
            "channel": channel,
            "opted_in": preferences.get("opted_in", True),
            "communication_types": preferences.get("communication_types", []),
            "frequency_limit": preferences.get("frequency_limit"),
            "preferred_time": preferences.get("preferred_time"),
            "language": preferences.get("language", "en"),
            "updated_at": datetime.utcnow()
        }
        
        return preference_record
    
    async def opt_out_recipient(
        self,
        recipient: str,
        channel: CommunicationChannel,
        communication_type: Optional[CommunicationType] = None
    ) -> Dict[str, Any]:
        """
        Opt out recipient from communications.
        
        Args:
            recipient: Recipient identifier
            channel: Communication channel
            communication_type: Specific type to opt out from
            
        Returns:
            Updated opt-out record
        """
        opt_out = {
            "id": uuid4(),
            "recipient": recipient,
            "channel": channel,
            "communication_type": communication_type,
            "opted_out_at": datetime.utcnow(),
            "is_global": communication_type is None
        }
        
        return opt_out
    
    async def opt_in_recipient(
        self,
        recipient: str,
        channel: CommunicationChannel,
        communication_type: Optional[CommunicationType] = None
    ) -> Dict[str, Any]:
        """
        Opt in recipient to communications.
        
        Args:
            recipient: Recipient identifier
            channel: Communication channel
            communication_type: Specific type to opt in to
            
        Returns:
            Updated opt-in record
        """
        opt_in = {
            "id": uuid4(),
            "recipient": recipient,
            "channel": channel,
            "communication_type": communication_type,
            "opted_in_at": datetime.utcnow()
        }
        
        return opt_in
    
    async def check_recipient_preferences(
        self,
        recipient: str,
        channel: CommunicationChannel
    ) -> Dict[str, Any]:
        """
        Check recipient communication preferences.
        
        Args:
            recipient: Recipient identifier
            channel: Communication channel
            
        Returns:
            Preference settings
        """
        # Placeholder implementation
        return {
            "recipient": recipient,
            "channel": channel,
            "opted_in": True,
            "can_send_marketing": True,
            "can_send_transactional": True,
            "preferred_time": None
        }
    
    # ============================================================================
    # ANALYTICS & REPORTING
    # ============================================================================
    
    async def get_communication_analytics(
        self,
        hostel_id: Optional[UUID] = None,
        channel: Optional[CommunicationChannel] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get communication analytics.
        
        Args:
            hostel_id: Optional hostel filter
            channel: Optional channel filter
            days: Time period in days
            
        Returns:
            Analytics data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Placeholder implementation
        return {
            "period_days": days,
            "total_sent": 0,
            "total_delivered": 0,
            "total_opened": 0,
            "total_clicked": 0,
            "total_failed": 0,
            "delivery_rate": 0,
            "open_rate": 0,
            "click_rate": 0,
            "bounce_rate": 0,
            "by_channel": {},
            "by_type": {},
            "engagement_trends": []
        }
    
    async def get_channel_performance(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get performance metrics by channel.
        
        Args:
            days: Time period in days
            
        Returns:
            Channel performance data
        """
        # Placeholder implementation
        return []
    
    async def get_template_performance(
        self,
        template_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get performance metrics for template.
        
        Args:
            template_id: Template ID
            days: Time period in days
            
        Returns:
            Template performance data
        """
        # Placeholder implementation
        return {
            "template_id": template_id,
            "total_sent": 0,
            "delivery_rate": 0,
            "open_rate": 0,
            "click_rate": 0,
            "conversion_rate": 0
        }
    
    async def get_engagement_metrics(
        self,
        recipient: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get engagement metrics.
        
        Args:
            recipient: Optional recipient filter
            days: Time period in days
            
        Returns:
            Engagement metrics
        """
        # Placeholder implementation
        return {
            "total_received": 0,
            "total_opened": 0,
            "total_clicked": 0,
            "avg_open_time_hours": 0,
            "engagement_score": 0,
            "preferred_channel": None
        }
    
    # ============================================================================
    # SCHEDULED MESSAGES
    # ============================================================================
    
    async def schedule_message(
        self,
        scheduled_at: datetime,
        **message_params
    ) -> Dict[str, Any]:
        """
        Schedule message for future delivery.
        
        Args:
            scheduled_at: Scheduled send time
            **message_params: Message parameters
            
        Returns:
            Scheduled message record
        """
        if scheduled_at <= datetime.utcnow():
            raise ValidationException("Scheduled time must be in the future")
        
        return await self.send_message(
            scheduled_at=scheduled_at,
            **message_params
        )
    
    async def get_scheduled_messages(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get scheduled messages.
        
        Args:
            from_date: Start date filter
            to_date: End date filter
            
        Returns:
            List of scheduled messages
        """
        # Placeholder implementation
        return []
    
    async def cancel_scheduled_message(
        self,
        message_id: UUID
    ) -> Dict[str, Any]:
        """
        Cancel scheduled message.
        
        Args:
            message_id: Message ID
            
        Returns:
            Cancelled message
        """
        message = await self.get_message_by_id(message_id)
        
        if message["status"] != CommunicationStatus.QUEUED:
            raise ValidationException(
                f"Cannot cancel message with status: {message['status']}"
            )
        
        message["status"] = CommunicationStatus.FAILED
        message["cancelled_at"] = datetime.utcnow()
        message["error_message"] = "Cancelled by user"
        
        return message
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    async def get_message_by_id(
        self,
        message_id: UUID
    ) -> Dict[str, Any]:
        """Get message by ID."""
        # Placeholder implementation
        return {
            "id": message_id,
            "channel": CommunicationChannel.EMAIL,
            "status": CommunicationStatus.SENT
        }
    
    async def _validate_recipients(
        self,
        channel: CommunicationChannel,
        recipients: List[str]
    ) -> None:
        """Validate recipient addresses."""
        if channel == CommunicationChannel.EMAIL:
            for recipient in recipients:
                if "@" not in recipient:
                    raise ValidationException(f"Invalid email: {recipient}")
        elif channel == CommunicationChannel.SMS:
            for recipient in recipients:
                if not recipient.replace("+", "").replace("-", "").isdigit():
                    raise ValidationException(f"Invalid phone number: {recipient}")
    
    async def _filter_opted_out_recipients(
        self,
        channel: CommunicationChannel,
        recipients: List[str],
        communication_type: CommunicationType
    ) -> List[str]:
        """Filter out recipients who have opted out."""
        # Placeholder - would check opt-out database
        return recipients
    
    async def _send_immediately(
        self,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send message immediately."""
        # Placeholder - would call actual delivery service
        return {
            "status": CommunicationStatus.SENT,
            "sent_at": datetime.utcnow(),
            "provider_message_id": str(uuid4())
        }
    
    async def _queue_for_delivery(
        self,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Queue message for delivery."""
        return {
            "status": CommunicationStatus.QUEUED,
            "queued_at": datetime.utcnow()
        }
    
    async def _render_template(
        self,
        template: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Render template with variables."""
        # Placeholder - would use template engine
        return {
            "subject": template["subject"],
            "body": template["body"],
            "html_body": template.get("html_body")
        }
    
    async def _validate_template_syntax(
        self,
        template: Dict[str, Any]
    ) -> None:
        """Validate template syntax."""
        # Placeholder - would validate template syntax
        pass
    
    async def _archive_template_version(
        self,
        template: Dict[str, Any]
    ) -> None:
        """Archive current template version."""
        pass
    
    async def _delay(
        self,
        seconds: int
    ) -> None:
        """Async delay."""
        import asyncio
        await asyncio.sleep(seconds)