# --- File: C:\Hostel-Main\app\models\notification\notification_routing.py ---
"""
Notification routing and escalation models.

Manages intelligent notification routing with role-based delivery,
hierarchical escalation, and conditional routing rules.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, SoftDeleteMixin
from app.schemas.common.enums import Priority, UserRole

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.notification.notification import Notification


class RoutingRule(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Notification routing rules.
    
    Defines how notifications should be routed based on conditions
    like event type, priority, hostel, and other attributes.
    """

    __tablename__ = "notification_routing_rules"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Rule metadata
    rule_name = Column(
        String(100),
        nullable=False,
        comment="Human-readable rule name",
    )
    description = Column(
        Text,
        nullable=True,
        comment="Rule description and purpose",
    )
    rule_priority = Column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="Rule priority (higher = evaluated first)",
    )

    # Hostel scope
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Hostel this rule applies to (null = all hostels)",
    )

    # Conditions (JSON for flexibility)
    conditions = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Routing conditions (event_type, priority, etc.)",
    )

    # Recipients
    recipient_roles = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="User roles to notify",
    )
    specific_users = Column(
        ARRAY(PG_UUID),
        nullable=False,
        default=list,
        comment="Specific user IDs to notify",
    )
    recipient_groups = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="User groups to notify",
    )

    # Channels
    channels = Column(
        ARRAY(String),
        nullable=False,
        comment="Notification channels to use (email, sms, push)",
    )

    # Template
    template_code = Column(
        String(100),
        nullable=True,
        comment="Template to use for this rule",
    )

    # Settings
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether rule is active",
    )
    stop_on_match = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Stop processing rules after this one matches",
    )

    # Relationships
    hostel = relationship(
        "Hostel",
        backref="routing_rules",
    )

    __table_args__ = (
        Index(
            "ix_routing_rules_hostel_active_priority",
            "hostel_id",
            "is_active",
            "rule_priority",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RoutingRule(name={self.rule_name}, "
            f"priority={self.rule_priority}, active={self.is_active})>"
        )


class EscalationPath(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Escalation path configuration.
    
    Defines multi-level escalation workflow for unhandled or
    critical notifications with time-based triggers.
    """

    __tablename__ = "notification_escalation_paths"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Path metadata
    path_name = Column(
        String(100),
        nullable=False,
        comment="Escalation path name",
    )
    description = Column(
        Text,
        nullable=True,
        comment="Path description",
    )

    # Scope
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Hostel this path applies to (null = all hostels)",
    )
    event_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Event type this escalation applies to",
    )

    # Escalation levels (ordered hierarchy)
    levels = Column(
        JSONB,
        nullable=False,
        comment="Escalation levels configuration",
    )

    # Settings
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether escalation path is active",
    )
    auto_escalate = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Automatically escalate based on timing",
    )

    # Relationships
    hostel = relationship(
        "Hostel",
        backref="escalation_paths",
    )

    escalations = relationship(
        "NotificationEscalation",
        back_populates="escalation_path",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_escalation_paths_hostel_event_active",
            "hostel_id",
            "event_type",
            "is_active",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<EscalationPath(name={self.path_name}, "
            f"event_type={self.event_type})>"
        )


class NotificationEscalation(BaseModel, TimestampMixin):
    """
    Active notification escalation tracking.
    
    Tracks escalation state for individual notifications with
    current level and escalation history.
    """

    __tablename__ = "notification_escalations"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # References
    notification_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    escalation_path_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notification_escalation_paths.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Current state
    current_level = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Current escalation level (0 = not escalated)",
    )
    max_level = Column(
        Integer,
        nullable=False,
        comment="Maximum escalation level in path",
    )

    # Timing
    last_escalated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last escalation occurred",
    )
    next_escalation_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When next escalation should occur",
    )

    # Status
    is_resolved = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether notification has been resolved",
    )
    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was resolved",
    )
    resolved_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who resolved the notification",
    )

    # Escalation history
    escalation_history = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="History of escalation events",
    )

    # Relationships
    notification = relationship(
        "Notification",
        backref="escalation",
    )
    escalation_path = relationship(
        "EscalationPath",
        back_populates="escalations",
    )
    resolved_by = relationship(
        "User",
        foreign_keys=[resolved_by_id],
    )

    __table_args__ = (
        Index(
            "ix_notification_escalations_unresolved",
            "is_resolved",
            "next_escalation_at",
            postgresql_where="is_resolved = FALSE",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationEscalation(notification_id={self.notification_id}, "
            f"level={self.current_level}/{self.max_level}, resolved={self.is_resolved})>"
        )


class NotificationRoute(BaseModel, TimestampMixin):
    """
    Notification routing decision record.
    
    Stores the final routing decision for each notification
    for audit and analytics purposes.
    """

    __tablename__ = "notification_routes"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Reference to notification
    notification_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Matched rule
    matched_rule_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notification_routing_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Routing rule that matched",
    )
    matched_rule_name = Column(
        String(100),
        nullable=True,
        comment="Name of matched rule (cached)",
    )

    # Recipients
    primary_recipients = Column(
        ARRAY(PG_UUID),
        nullable=False,
        comment="Primary notification recipients (user IDs)",
    )
    cc_recipients = Column(
        ARRAY(PG_UUID),
        nullable=False,
        default=list,
        comment="CC recipients",
    )

    # Channels
    channels = Column(
        ARRAY(String),
        nullable=False,
        comment="Channels used for delivery",
    )

    # Template
    template_code = Column(
        String(100),
        nullable=True,
        comment="Template used",
    )

    # Escalation
    escalation_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether escalation is enabled",
    )
    escalation_path_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notification_escalation_paths.id", ondelete="SET NULL"),
        nullable=True,
        comment="Escalation path if enabled",
    )

    # Metadata
    routing_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional routing metadata",
    )

    # Relationships
    notification = relationship(
        "Notification",
        backref="route",
    )
    matched_rule = relationship(
        "RoutingRule",
        foreign_keys=[matched_rule_id],
    )
    escalation_path = relationship(
        "EscalationPath",
        foreign_keys=[escalation_path_id],
    )

    __table_args__ = (
        Index(
            "ix_notification_routes_rule",
            "matched_rule_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationRoute(notification_id={self.notification_id}, "
            f"rule={self.matched_rule_name}, channels={self.channels})>"
        )