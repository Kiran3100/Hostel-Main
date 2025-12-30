"""
User-related domain events.
"""

from typing import Dict, Any
from uuid import UUID

from app.schemas.core.domain_events import BaseDomainEvent, DomainEventType


class UserCreatedEvent(BaseDomainEvent):
    """Event fired when a user is created."""
    
    def __init__(self, user_id: UUID, payload: Dict[str, Any], **kwargs):
        super().__init__(
            event_type=DomainEventType.USER_CREATED,
            aggregate_id=user_id,
            aggregate_type="User",
            payload=payload,
            **kwargs
        )


class UserUpdatedEvent(BaseDomainEvent):
    """Event fired when a user is updated."""
    
    def __init__(self, user_id: UUID, payload: Dict[str, Any], **kwargs):
        super().__init__(
            event_type=DomainEventType.USER_UPDATED,
            aggregate_id=user_id,
            aggregate_type="User",
            payload=payload,
            **kwargs
        )


class UserDeletedEvent(BaseDomainEvent):
    """Event fired when a user is deleted."""
    
    def __init__(self, user_id: UUID, payload: Dict[str, Any], **kwargs):
        super().__init__(
            event_type=DomainEventType.USER_DELETED,
            aggregate_id=user_id,
            aggregate_type="User",
            payload=payload,
            **kwargs
        )