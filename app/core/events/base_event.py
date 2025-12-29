"""
Base event class for the event system.
"""
from abc import ABC
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4


class BaseEvent(ABC):
    """Base class for all events in the system."""
    
    def __init__(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        self.event_id = str(uuid4())
        self.event_type = event_type
        self.data = data or {}
        self.timestamp = datetime.utcnow()
        self.processed = False
    
    def __str__(self) -> str:
        return f"{self.event_type}({self.event_id})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "processed": self.processed
        }


class UserEvent(BaseEvent):
    """Events related to user operations."""
    
    def __init__(self, event_type: str, user_id: int, data: Optional[Dict[str, Any]] = None):
        super().__init__(event_type, data)
        self.user_id = user_id
        if data:
            data["user_id"] = user_id


class BookingEvent(BaseEvent):
    """Events related to booking operations."""
    
    def __init__(self, event_type: str, booking_id: int, data: Optional[Dict[str, Any]] = None):
        super().__init__(event_type, data)
        self.booking_id = booking_id
        if data:
            data["booking_id"] = booking_id


class RoomEvent(BaseEvent):
    """Events related to room operations."""
    
    def __init__(self, event_type: str, room_id: int, data: Optional[Dict[str, Any]] = None):
        super().__init__(event_type, data)
        self.room_id = room_id
        if data:
            data["room_id"] = room_id