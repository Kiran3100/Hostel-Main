"""
Event system for the hostel management application.
"""

from .event_bus import EventBus, event_bus, publish_event, emit_event, subscribe_to_event
from .base_event import BaseEvent, UserEvent, BookingEvent, RoomEvent
from .event_handlers import EventHandler, AsyncEventHandler, SyncEventHandler, EventHandlerRegistry

__all__ = [
    "EventBus",
    "event_bus",
    "publish_event",
    "emit_event", 
    "subscribe_to_event",
    "BaseEvent",
    "UserEvent",
    "BookingEvent", 
    "RoomEvent",
    "EventHandler",
    "AsyncEventHandler",
    "SyncEventHandler",
    "EventHandlerRegistry"
]