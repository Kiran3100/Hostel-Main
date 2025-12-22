# event_dispatcher.py

from typing import Dict, List, Any, Callable, Optional, Type
from dataclasses import dataclass
from datetime import datetime
import uuid
import logging
import asyncio
from enum import Enum
import json

class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

@dataclass
class DomainEvent:
    """Base class for domain events"""
    event_id: str
    event_type: str
    timestamp: datetime
    source: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    priority: EventPriority = EventPriority.NORMAL
    version: str = "1.0"

    @classmethod
    def create(
        cls,
        event_type: str,
        data: Dict[str, Any],
        source: str,
        priority: EventPriority = EventPriority.NORMAL
    ) -> 'DomainEvent':
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            source=source,
            data=data,
            metadata={},
            priority=priority
        )

    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps({
            'event_id': self.event_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'data': self.data,
            'metadata': self.metadata,
            'priority': self.priority.name,
            'version': self.version
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'DomainEvent':
        """Create event from JSON string"""
        data = json.loads(json_str)
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['priority'] = EventPriority[data['priority']]
        return cls(**data)

class EventHandler:
    """Base class for event handlers"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def handle(self, event: DomainEvent) -> None:
        """Handle an event"""
        try:
            await self._pre_handle(event)
            await self._handle_event(event)
            await self._post_handle(event)
        except Exception as e:
            self.logger.error(f"Error handling event {event.event_id}: {str(e)}")
            raise

    async def _pre_handle(self, event: DomainEvent) -> None:
        """Pre-handling hook"""
        pass

    async def _handle_event(self, event: DomainEvent) -> None:
        """Main event handling logic"""
        raise NotImplementedError

    async def _post_handle(self, event: DomainEvent) -> None:
        """Post-handling hook"""
        pass

class EventSubscriber:
    """Manages event subscriptions"""
    
    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler
    ) -> None:
        """Subscribe a handler to an event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        self.logger.info(f"Subscribed {handler.__class__.__name__} to {event_type}")

    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler
    ) -> None:
        """Unsubscribe a handler from an event type"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
            self.logger.info(f"Unsubscribed {handler.__class__.__name__} from {event_type}")

    async def notify(self, event: DomainEvent) -> None:
        """Notify all handlers of an event"""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                self.logger.error(
                    f"Handler {handler.__class__.__name__} failed for event {event.event_id}: {str(e)}"
                )

class EventQueue:
    """Queue for async event processing"""
    
    def __init__(self, max_size: int = 1000):
        self.queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=max_size)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def push(self, event: DomainEvent) -> None:
        """Push event to queue"""
        await self.queue.put(event)
        self.logger.debug(f"Queued event: {event.event_id}")

    async def pop(self) -> DomainEvent:
        """Pop event from queue"""
        event = await self.queue.get()
        self.logger.debug(f"Dequeued event: {event.event_id}")
        return event

    def size(self) -> int:
        """Get current queue size"""
        return self.queue.qsize()

class EventPublisher:
    """Publishes events to subscribers"""
    
    def __init__(self):
        self.subscriber = EventSubscriber()
        self.queue = EventQueue()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event"""
        await self.queue.push(event)
        self.logger.info(f"Published event: {event.event_id}")

    async def start_processing(self) -> None:
        """Start event processing"""
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        self.logger.info("Started event processing")

    async def stop_processing(self) -> None:
        """Stop event processing"""
        self._running = False
        if self._processor_task:
            await self._processor_task
        self.logger.info("Stopped event processing")

    async def _process_events(self) -> None:
        """Process events from queue"""
        while self._running:
            try:
                event = await self.queue.pop()
                await self.subscriber.notify(event)
            except Exception as e:
                self.logger.error(f"Error processing event: {str(e)}")

class EventDispatcher:
    """Main event dispatching interface"""
    
    def __init__(self):
        self.publisher = EventPublisher()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def dispatch(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: str,
        priority: EventPriority = EventPriority.NORMAL
    ) -> None:
        """Dispatch a new event"""
        event = DomainEvent.create(event_type, data, source, priority)
        await self.publisher.publish(event)

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler
    ) -> None:
        """Subscribe to events"""
        self.publisher.subscriber.subscribe(event_type, handler)

    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler
    ) -> None:
        """Unsubscribe from events"""
        self.publisher.subscriber.unsubscribe(event_type, handler)

    async def start(self) -> None:
        """Start event processing"""
        await self.publisher.start_processing()

    async def stop(self) -> None:
        """Stop event processing"""
        await self.publisher.stop_processing()