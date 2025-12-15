# app/services/notification/routing_service.py
from __future__ import annotations

from typing import Dict, List, Optional, Protocol
from uuid import UUID

from app.schemas.notification.notification_routing import (
    RoutingConfig,
    RoutingRule,
    NotificationRoute,
)
from app.schemas.common.enums import Priority
from app.services.common import errors


class RoutingStore(Protocol):
    """
    Storage abstraction for routing configs per hostel.
    """

    def get_routing_config(self, hostel_id: UUID) -> Optional[dict]: ...
    def save_routing_config(self, hostel_id: UUID, data: dict) -> None: ...


class RoutingService:
    """
    Notification routing:

    - Manage RoutingConfig per hostel
    - Determine a NotificationRoute for a given event
    """

    def __init__(self, store: RoutingStore) -> None:
        self._store = store

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self, hostel_id: UUID) -> RoutingConfig:
        record = self._store.get_routing_config(hostel_id)
        if record:
            return RoutingConfig.model_validate(record)
        # default routing with no rules
        cfg = RoutingConfig(
            id=None,
            created_at=None,
            updated_at=None,
            hostel_id=hostel_id,
            rules=[],
            enable_escalation=True,
            escalation_timeout_hours=24,
        )
        self._store.save_routing_config(hostel_id, cfg.model_dump())
        return cfg

    def set_config(self, cfg: RoutingConfig) -> None:
        self._store.save_routing_config(cfg.hostel_id, cfg.model_dump())

    # ------------------------------------------------------------------ #
    # Route resolution
    # ------------------------------------------------------------------ #
    def determine_route(
        self,
        *,
        notification_id: UUID,
        hostel_id: UUID,
        event_type: str,
        priority: Optional[Priority] = None,
    ) -> NotificationRoute:
        """
        Build a simple NotificationRoute:

        - Filter rules by event_type (and priority, if provided)
        - Uses specific_users as primary_recipients
        - Does not yet expand recipient_roles to actual user IDs
        """
        cfg = self.get_config(hostel_id)
        primary: List[UUID] = []
        cc: List[UUID] = []
        recipient_channels: Dict[UUID, List[str]] = {}

        for rule in cfg.rules:
            if not rule.is_active:
                continue
            if rule.event_type != event_type:
                continue
            if priority and rule.priority and rule.priority != priority:
                continue

            for uid in rule.specific_users:
                if uid not in primary:
                    primary.append(uid)
                    recipient_channels[uid] = list(rule.channels)

        return NotificationRoute(
            notification_id=notification_id,
            primary_recipients=primary,
            cc_recipients=cc,
            recipient_channels=recipient_channels,
            escalation_enabled=cfg.enable_escalation,
            escalation_path=None,
        )