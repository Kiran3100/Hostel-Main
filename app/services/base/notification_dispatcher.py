# notification_dispatcher.py

from typing import Dict, List, Any, Optional, Union, Type
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import asyncio
from enum import Enum
import uuid
from abc import ABC, abstractmethod

class NotificationPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3
    CRITICAL = 4

class NotificationChannel(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"
    SLACK = "slack"

class NotificationStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"

@dataclass
class NotificationTemplate:
    """Template for notification content"""
    template_id: str
    channel: NotificationChannel
    subject: str
    content: str
    variables: List[str]
    metadata: Dict[str, Any]
    version: str = "1.0"

    def render(self, data: Dict[str, Any]) -> str:
        """Render template with data"""
        content = self.content
        for var in self.variables:
            if var in data:
                content = content.replace(f"{{{var}}}", str(data[var]))
        return content

@dataclass
class Notification:
    """Core notification entity"""
    notification_id: str
    template_id: str
    recipient_id: str
    channel: NotificationChannel
    priority: NotificationPriority
    subject: str
    content: str
    status: NotificationStatus
    metadata: Dict[str, Any]
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        template_id: str,
        recipient_id: str,
        channel: NotificationChannel,
        priority: NotificationPriority,
        subject: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[datetime] = None
    ) -> 'Notification':
        return cls(
            notification_id=str(uuid.uuid4()),
            template_id=template_id,
            recipient_id=recipient_id,
            channel=channel,
            priority=priority,
            subject=subject,
            content=content,
            status=NotificationStatus.PENDING,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
            scheduled_for=scheduled_for
        )

class NotificationBuilder:
    """Builds notifications from templates"""
    
    def __init__(self):
        self._templates: Dict[str, NotificationTemplate] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_template(self, template: NotificationTemplate) -> None:
        """Register a notification template"""
        self._templates[template.template_id] = template
        self.logger.info(f"Registered template: {template.template_id}")

    async def build_notification(
        self,
        template_id: str,
        recipient_id: str,
        data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[datetime] = None
    ) -> Notification:
        """Build notification from template"""
        template = self._templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        content = template.render(data)
        
        return Notification.create(
            template_id=template_id,
            recipient_id=recipient_id,
            channel=template.channel,
            priority=priority,
            subject=template.subject,
            content=content,
            metadata=metadata,
            scheduled_for=scheduled_for
        )

class NotificationRouter:
    """Routes notifications to appropriate channels"""
    
    def __init__(self):
        self._routes: Dict[NotificationChannel, List[str]] = {}
        self._fallbacks: Dict[NotificationChannel, NotificationChannel] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_route(
        self,
        channel: NotificationChannel,
        provider_id: str
    ) -> None:
        """Add routing configuration"""
        if channel not in self._routes:
            self._routes[channel] = []
        self._routes[channel].append(provider_id)
        self.logger.info(f"Added route: {channel.value} -> {provider_id}")

    def set_fallback(
        self,
        primary: NotificationChannel,
        fallback: NotificationChannel
    ) -> None:
        """Set fallback channel"""
        self._fallbacks[primary] = fallback
        self.logger.info(
            f"Set fallback: {primary.value} -> {fallback.value}"
        )

    async def get_route(
        self,
        notification: Notification
    ) -> Optional[str]:
        """Get provider for notification"""
        routes = self._routes.get(notification.channel, [])
        if not routes:
            fallback = self._fallbacks.get(notification.channel)
            if fallback:
                routes = self._routes.get(fallback, [])
        
        return routes[0] if routes else None

class NotificationQueue:
    """Manages notification queue and processing"""
    
    def __init__(self):
        self._queues: Dict[NotificationPriority, asyncio.PriorityQueue] = {
            priority: asyncio.PriorityQueue()
            for priority in NotificationPriority
        }
        self.logger = logging.getLogger(self.__class__.__name__)

    async def enqueue(self, notification: Notification) -> None:
        """Add notification to queue"""
        queue = self._queues[notification.priority]
        await queue.put((notification.priority.value, notification))
        notification.status = NotificationStatus.QUEUED
        self.logger.debug(
            f"Queued notification: {notification.notification_id}"
        )

    async def dequeue(self) -> Optional[Notification]:
        """Get next notification from queue"""
        for priority in sorted(
            NotificationPriority,
            key=lambda x: x.value,
            reverse=True
        ):
            queue = self._queues[priority]
            if not queue.empty():
                _, notification = await queue.get()
                return notification
        return None

    def size(self) -> Dict[NotificationPriority, int]:
        """Get queue sizes"""
        return {
            priority: queue.qsize()
            for priority, queue in self._queues.items()
        }

class NotificationPrioritizer:
    """Handles notification prioritization"""
    
    def __init__(self):
        self._rules: Dict[str, callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_rule(
        self,
        rule_id: str,
        rule_func: callable
    ) -> None:
        """Add prioritization rule"""
        self._rules[rule_id] = rule_func
        self.logger.info(f"Added prioritization rule: {rule_id}")

    async def get_priority(
        self,
        notification: Notification
    ) -> NotificationPriority:
        """Calculate notification priority"""
        priority = notification.priority
        
        for rule_func in self._rules.values():
            try:
                new_priority = await rule_func(notification)
                if new_priority.value > priority.value:
                    priority = new_priority
            except Exception as e:
                self.logger.error(f"Priority rule error: {str(e)}")
        
        return priority

class NotificationDispatcher:
    """Main notification dispatch interface"""
    
    def __init__(self):
        self.builder = NotificationBuilder()
        self.router = NotificationRouter()
        self.queue = NotificationQueue()
        self.prioritizer = NotificationPrioritizer()
        self._providers: Dict[str, Any] = {}
        self._processing = False
        self._processor_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_provider(
        self,
        provider_id: str,
        provider: Any
    ) -> None:
        """Register notification provider"""
        self._providers[provider_id] = provider
        self.logger.info(f"Registered provider: {provider_id}")

    async def send_notification(
        self,
        template_id: str,
        recipient_id: str,
        data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[datetime] = None
    ) -> Notification:
        """Send a notification"""
        try:
            # Build notification
            notification = await self.builder.build_notification(
                template_id,
                recipient_id,
                data,
                priority,
                metadata,
                scheduled_for
            )
            
            # Calculate priority
            notification.priority = await self.prioritizer.get_priority(
                notification
            )
            
            # Queue notification
            await self.queue.enqueue(notification)
            
            return notification
        except Exception as e:
            self.logger.error(f"Send notification error: {str(e)}")
            raise

    async def start_processing(self) -> None:
        """Start notification processing"""
        self._processing = True
        self._processor_task = asyncio.create_task(self._process_notifications())
        self.logger.info("Started notification processing")

    async def stop_processing(self) -> None:
        """Stop notification processing"""
        self._processing = False
        if self._processor_task:
            await self._processor_task
        self.logger.info("Stopped notification processing")

    async def _process_notifications(self) -> None:
        """Process queued notifications"""
        while self._processing:
            try:
                notification = await self.queue.dequeue()
                if notification:
                    await self._send_notification(notification)
            except Exception as e:
                self.logger.error(f"Notification processing error: {str(e)}")
            await asyncio.sleep(0.1)

    async def _send_notification(self, notification: Notification) -> None:
        """Send notification through provider"""
        try:
            notification.status = NotificationStatus.SENDING
            
            # Get provider
            provider_id = await self.router.get_route(notification)
            if not provider_id:
                raise ValueError(
                    f"No provider for channel: {notification.channel.value}"
                )
            
            provider = self._providers.get(provider_id)
            if not provider:
                raise ValueError(f"Provider not found: {provider_id}")
            
            # Send notification
            await provider.send(notification)
            
            notification.status = NotificationStatus.DELIVERED
            notification.sent_at = datetime.utcnow()
            self.logger.info(
                f"Sent notification: {notification.notification_id}"
            )
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error = str(e)
            self.logger.error(
                f"Failed to send notification {notification.notification_id}: {str(e)}"
            )

    async def mark_read(
        self,
        notification_id: str,
        recipient_id: str
    ) -> None:
        """Mark notification as read"""
        # Implement read status tracking
        pass

    async def get_notifications(
        self,
        recipient_id: str,
        status: Optional[NotificationStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Notification]:
        """Get notifications for recipient"""
        # Implement notification retrieval
        return []

    async def get_notification(
        self,
        notification_id: str
    ) -> Optional[Notification]:
        """Get specific notification"""
        # Implement notification retrieval
        return None