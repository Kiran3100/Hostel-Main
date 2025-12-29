"""
Event bus implementation for the hostel management system.
"""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from .base_event import BaseEvent
from .event_handlers import EventHandler, EventHandlerRegistry, AsyncEventHandler, SyncEventHandler

logger = logging.getLogger(__name__)


class EventBus:
    """
    Event bus for handling application events.
    """
    
    def __init__(self):
        self._registry = EventHandlerRegistry()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event type.
        
        Args:
            event_type: The type of event to subscribe to
            handler: The handler function (can be sync or async)
        """
        if asyncio.iscoroutinefunction(handler):
            event_handler = AsyncEventHandler(handler)
        else:
            event_handler = SyncEventHandler(handler)
        
        self._registry.register(event_type, event_handler)
        logger.info(f"Registered handler for event type: {event_type}")
    
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Unsubscribe a handler from an event type.
        
        Args:
            event_type: The type of event to unsubscribe from
            handler: The handler to remove
        """
        self._registry.unregister(event_type, handler)
        logger.info(f"Unregistered handler for event type: {event_type}")
    
    async def publish(self, event: BaseEvent) -> None:
        """
        Publish an event to the bus.
        
        Args:
            event: The event to publish
        """
        logger.debug(f"Publishing event: {event}")
        await self._queue.put(event)
    
    async def emit(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit an event by type and data.
        
        Args:
            event_type: The type of event to emit
            data: Optional data for the event
        """
        event = BaseEvent(event_type, data)
        await self.publish(event)
    
    async def start(self) -> None:
        """Start the event bus worker."""
        if self._running:
            logger.warning("Event bus is already running")
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Stop the event bus worker."""
        if not self._running:
            logger.warning("Event bus is not running")
            return
        
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Event bus stopped")
    
    async def _worker(self) -> None:
        """Worker coroutine to process events."""
        logger.info("Event bus worker started")
        
        while self._running:
            try:
                # Wait for an event with a timeout
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_event(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event bus worker: {str(e)}")
        
        logger.info("Event bus worker stopped")
    
    async def _process_event(self, event: BaseEvent) -> None:
        """
        Process an event by calling all registered handlers.
        
        Args:
            event: The event to process
        """
        handlers = self._registry.get_handlers(event.event_type)
        
        if not handlers:
            logger.debug(f"No handlers found for event type: {event.event_type}")
            return
        
        logger.debug(f"Processing event {event} with {len(handlers)} handlers")
        
        # Process all handlers concurrently
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(handler.handle(event))
            tasks.append(task)
        
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
                event.processed = True
                logger.debug(f"Event {event} processed successfully")
            except Exception as e:
                logger.error(f"Error processing event {event}: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the event bus."""
        return {
            "running": self._running,
            "queue_size": self._queue.qsize() if hasattr(self._queue, 'qsize') else 0,
            "registered_handlers": {
                event_type: len(handlers) 
                for event_type, handlers in self._registry._handlers.items()
            }
        }


# Global event bus instance
event_bus = EventBus()


# Convenience functions
async def publish_event(event: BaseEvent) -> None:
    """Publish an event to the global event bus."""
    await event_bus.publish(event)


async def emit_event(event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
    """Emit an event to the global event bus."""
    await event_bus.emit(event_type, data)


def subscribe_to_event(event_type: str, handler: Callable) -> None:
    """Subscribe to an event type on the global event bus."""
    event_bus.subscribe(event_type, handler)