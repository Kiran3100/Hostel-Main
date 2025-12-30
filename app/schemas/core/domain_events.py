"""
Domain event schemas for event-driven architecture.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DomainEventType(str, Enum):
    """Types of domain events."""
    
    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    
    # Booking events
    BOOKING_CREATED = "booking.created"
    BOOKING_UPDATED = "booking.updated"
    BOOKING_CANCELLED = "booking.cancelled"
    BOOKING_CONFIRMED = "booking.confirmed"
    
    # Room events
    ROOM_CREATED = "room.created"
    ROOM_UPDATED = "room.updated"
    ROOM_DELETED = "room.deleted"
    ROOM_STATUS_CHANGED = "room.status_changed"
    
    # Payment events
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    
    # Notification events
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"
    
    # Admin events
    ADMIN_ACTION = "admin.action"
    SYSTEM_EVENT = "system.event"


class EventMetadata(BaseModel):
    """Metadata for domain events."""
    
    user_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    additional_data: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
                "correlation_id": "123e4567-e89b-12d3-a456-426614174001",
                "causation_id": "123e4567-e89b-12d3-a456-426614174002",
                "additional_data": {}
            }
        }


class BaseDomainEvent(BaseModel):
    """Base class for all domain events."""
    
    event_id: UUID = Field(default_factory=uuid4)
    event_type: DomainEventType
    aggregate_id: UUID
    aggregate_type: str
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1, ge=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "123e4567-e89b-12d3-a456-426614174000",
                "event_type": "user.created",
                "aggregate_id": "123e4567-e89b-12d3-a456-426614174001",
                "aggregate_type": "User",
                "occurred_at": "2025-12-29T16:07:29.048000",
                "version": 1,
                "payload": {
                    "username": "john_doe",
                    "email": "john@example.com"
                },
                "metadata": {
                    "user_id": "123e4567-e89b-12d3-a456-426614174002",
                    "ip_address": "192.168.1.1"
                }
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseDomainEvent":
        """Create event from dictionary."""
        return cls(**data)