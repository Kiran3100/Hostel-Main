"""
Event handlers for the event system.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List
from .base_event import BaseEvent
import logging

logger = logging.getLogger(__name__)


class EventHandler(ABC):
    """Base class for event handlers."""
    
    @abstractmethod
    async def handle(self, event: BaseEvent) -> None:
        """Handle the event."""
        pass


class AsyncEventHandler(EventHandler):
    """Async event handler wrapper."""
    
    def __init__(self, handler_func: Callable):
        self.handler_func = handler_func
    
    async def handle(self, event: BaseEvent) -> None:
        """Handle the event asynchronously."""
        try:
            if hasattr(self.handler_func, '__call__'):
                await self.handler_func(event)
        except Exception as e:
            logger.error(f"Error handling event {event.event_type}: {str(e)}")
            raise


class SyncEventHandler(EventHandler):
    """Sync event handler wrapper."""
    
    def __init__(self, handler_func: Callable):
        self.handler_func = handler_func
    
    async def handle(self, event: BaseEvent) -> None:
        """Handle the event synchronously."""
        try:
            if hasattr(self.handler_func, '__call__'):
                self.handler_func(event)
        except Exception as e:
            logger.error(f"Error handling event {event.event_type}: {str(e)}")
            raise


class EventHandlerRegistry:
    """Registry for event handlers."""
    
    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}
    
    def register(self, event_type: str, handler: EventHandler) -> None:
        """Register an event handler."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def unregister(self, event_type: str, handler: EventHandler) -> None:
        """Unregister an event handler."""
        if event_type in self._handlers:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
    
    def get_handlers(self, event_type: str) -> List[EventHandler]:
        """Get handlers for an event type."""
        return self._handlers.get(event_type, [])
    
    def clear(self) -> None:
        """Clear all handlers."""
        self._handlers.clear()