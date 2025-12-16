# --- File: app/schemas/notification/notification_routing.py ---
"""
Notification routing schemas.

This module provides schemas for routing notifications to appropriate
recipients with hierarchical escalation and rule-based routing.
"""

from datetime import datetime
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import Priority, UserRole

__all__ = [
    "RoutingConfig",
    "RoutingRule",
    "HierarchicalRouting",
    "EscalationRouting",
    "EscalationLevel",
    "NotificationRoute",
    "RoutingCondition",
]


class RoutingCondition(BaseSchema):
    """
    Condition for routing rule matching.

    Defines when a routing rule should be applied.
    """

    # Event matching
    event_type: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Event type to match (e.g., 'complaint', 'payment')",
    )
    event_category: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Event category",
    )

    # Priority matching
    priority: Union[Priority, None] = Field(
        default=None,
        description="Priority level to match",
    )
    min_priority: Union[Priority, None] = Field(
        default=None,
        description="Minimum priority level",
    )

    # Entity matching
    hostel_id: Union[UUID, None] = Field(
        default=None,
        description="Specific hostel ID",
    )
    room_id: Union[UUID, None] = Field(
        default=None,
        description="Specific room ID",
    )

    # Time-based
    time_of_day_start: Union[str, None] = Field(
        default=None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Start time for time-based routing (HH:MM)",
    )
    time_of_day_end: Union[str, None] = Field(
        default=None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="End time for time-based routing (HH:MM)",
    )

    # Custom attributes
    custom_attributes: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom attribute matching",
    )


class RoutingRule(BaseSchema):
    """
    Individual routing rule configuration.

    Defines how notifications should be routed based on conditions.
    """

    rule_id: Union[UUID, None] = Field(
        default=None,
        description="Rule ID (auto-generated if not provided)",
    )
    rule_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Human-readable rule name",
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Rule description",
    )

    # Priority (for rule ordering)
    rule_priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Rule priority (higher = evaluated first)",
    )

    # Conditions
    conditions: RoutingCondition = Field(
        default_factory=RoutingCondition,
        description="Conditions for this rule",
    )

    # Recipients
    recipient_roles: List[UserRole] = Field(
        default_factory=list,
        description="User roles to notify",
    )
    specific_users: List[UUID] = Field(
        default_factory=list,
        description="Specific user IDs to notify",
    )
    recipient_groups: List[str] = Field(
        default_factory=list,
        description="User groups to notify",
    )

    # Channels
    channels: List[str] = Field(
        ...,
        min_length=1,
        description="Notification channels to use",
    )

    # Template
    template_code: Union[str, None] = Field(
        default=None,
        description="Template to use for this rule",
    )

    # Settings
    is_active: bool = Field(
        default=True,
        description="Whether rule is active",
    )
    stop_on_match: bool = Field(
        default=False,
        description="Stop processing rules after this one matches",
    )

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: List[str]) -> List[str]:
        """Validate and deduplicate channels."""
        valid_channels = ["email", "sms", "push"]
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f"Invalid channel: {channel}")
        return list(set(v))  # Remove duplicates

    @model_validator(mode="after")
    def validate_recipients(self) -> "RoutingRule":
        """Ensure at least one recipient is specified."""
        if not any([
            self.recipient_roles,
            self.specific_users,
            self.recipient_groups,
        ]):
            raise ValueError(
                "At least one recipient (roles, users, or groups) must be specified"
            )
        return self


class RoutingConfig(BaseSchema):
    """
    Complete routing configuration for a hostel.

    Defines all routing rules and escalation settings.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID for this routing config",
    )

    # Routing rules
    rules: List[RoutingRule] = Field(
        default_factory=list,
        description="List of routing rules (evaluated in order)",
    )

    # Default routing
    default_recipient_roles: List[UserRole] = Field(
        default_factory=lambda: [UserRole.HOSTEL_ADMIN],
        description="Default recipients if no rules match",
    )
    default_channels: List[str] = Field(
        default_factory=lambda: ["email"],
        description="Default notification channels",
    )

    # Escalation settings
    enable_escalation: bool = Field(
        default=True,
        description="Enable automatic escalation",
    )
    escalation_timeout_hours: int = Field(
        default=24,
        ge=1,
        le=168,  # 1 week max
        description="Hours before escalating unhandled notifications",
    )

    # Settings
    is_active: bool = Field(
        default=True,
        description="Whether routing config is active",
    )

    @field_validator("rules")
    @classmethod
    def sort_rules_by_priority(cls, v: List[RoutingRule]) -> List[RoutingRule]:
        """Sort rules by priority (highest first)."""
        return sorted(v, key=lambda r: r.rule_priority, reverse=True)


class EscalationLevel(BaseSchema):
    """
    Single level in an escalation chain.

    Defines recipients and timing for one escalation level.
    """

    level: int = Field(
        ...,
        ge=1,
        le=10,
        description="Escalation level (1 = first, higher = later)",
    )
    level_name: str = Field(
        ...,
        max_length=100,
        description="Level name (e.g., 'Supervisor', 'Admin', 'Manager')",
    )

    # Recipients
    recipients: List[UUID] = Field(
        ...,
        min_length=1,
        description="User IDs to notify at this level",
    )
    recipient_roles: List[UserRole] = Field(
        default_factory=list,
        description="User roles to notify at this level",
    )

    # Timing
    escalate_after_hours: int = Field(
        ...,
        ge=1,
        le=168,
        description="Hours to wait before escalating to this level",
    )

    # Channels
    channels: List[str] = Field(
        ...,
        min_length=1,
        description="Notification channels for this level",
    )

    # Template
    template_code: Union[str, None] = Field(
        default=None,
        description="Template for escalation notification",
    )

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: List[str]) -> List[str]:
        """Validate channels."""
        valid_channels = ["email", "sms", "push"]
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f"Invalid channel: {channel}")
        return list(set(v))


class HierarchicalRouting(BaseSchema):
    """
    Hierarchical notification routing configuration.

    Defines multi-level routing with fallback recipients.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    event_type: str = Field(
        ...,
        max_length=100,
        description="Event type this routing applies to",
    )

    # Routing hierarchy
    primary_recipients: List[UUID] = Field(
        ...,
        min_length=1,
        description="Primary recipients (e.g., supervisors)",
    )
    secondary_recipients: List[UUID] = Field(
        default_factory=list,
        description="Secondary recipients (e.g., admins)",
    )
    tertiary_recipients: List[UUID] = Field(
        default_factory=list,
        description="Tertiary recipients (e.g., super admin)",
    )

    # Escalation timing
    escalate_to_secondary_after_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours before escalating to secondary",
    )
    escalate_to_tertiary_after_hours: int = Field(
        default=48,
        ge=1,
        le=336,  # 2 weeks
        description="Hours before escalating to tertiary",
    )

    # Channels by level
    primary_channels: List[str] = Field(
        default_factory=lambda: ["email", "push"],
        description="Channels for primary recipients",
    )
    secondary_channels: List[str] = Field(
        default_factory=lambda: ["email", "sms", "push"],
        description="Channels for secondary recipients",
    )
    tertiary_channels: List[str] = Field(
        default_factory=lambda: ["email", "sms", "push"],
        description="Channels for tertiary recipients",
    )

    # Settings
    is_active: bool = Field(
        default=True,
        description="Whether routing is active",
    )


class EscalationRouting(BaseCreateSchema):
    """
    Escalation routing for a specific notification.

    Defines the escalation path and current state.
    """

    notification_id: UUID = Field(
        ...,
        description="Notification ID",
    )

    # Escalation chain
    escalation_chain: List[EscalationLevel] = Field(
        ...,
        min_length=1,
        description="Escalation levels in order",
    )

    # Current state
    current_level: int = Field(
        default=0,
        ge=0,
        description="Current escalation level (0 = not escalated)",
    )
    last_escalated_at: Union[datetime, None] = Field(
        default=None,
        description="When last escalation occurred",
    )

    # Settings
    auto_escalate: bool = Field(
        default=True,
        description="Automatically escalate based on timing",
    )
    is_resolved: bool = Field(
        default=False,
        description="Whether notification has been resolved",
    )

    @field_validator("escalation_chain")
    @classmethod
    def validate_escalation_levels(
        cls,
        v: List[EscalationLevel],
    ) -> List[EscalationLevel]:
        """Validate escalation levels are sequential and sorted."""
        if not v:
            raise ValueError("At least one escalation level required")

        # Check levels are sequential
        levels = [level.level for level in v]
        if levels != list(range(1, len(levels) + 1)):
            raise ValueError("Escalation levels must be sequential starting from 1")

        # Sort by level
        return sorted(v, key=lambda x: x.level)

    @field_validator("escalation_chain")
    @classmethod
    def validate_escalation_timing(
        cls,
        v: List[EscalationLevel],
    ) -> List[EscalationLevel]:
        """Validate escalation timing is increasing."""
        hours = [level.escalate_after_hours for level in v]
        if hours != sorted(hours):
            raise ValueError(
                "Escalation hours must increase with each level"
            )
        return v


class NotificationRoute(BaseSchema):
    """
    Determined notification route.

    Represents the final routing decision for a notification.
    """

    notification_id: UUID = Field(
        ...,
        description="Notification ID",
    )

    # Matched rule
    matched_rule_id: Union[UUID, None] = Field(
        default=None,
        description="ID of routing rule that matched",
    )
    matched_rule_name: Union[str, None] = Field(
        default=None,
        description="Name of matched routing rule",
    )

    # Recipients
    primary_recipients: List[UUID] = Field(
        ...,
        min_length=1,
        description="Primary notification recipients",
    )
    cc_recipients: List[UUID] = Field(
        default_factory=list,
        description="CC recipients",
    )

    # Channels by recipient
    recipient_channels: Dict[UUID, List[str]] = Field(
        default_factory=dict,
        description="Notification channels for each recipient",
    )

    # Template
    template_code: Union[str, None] = Field(
        default=None,
        description="Template to use",
    )

    # Escalation
    escalation_enabled: bool = Field(
        default=False,
        description="Whether escalation is enabled",
    )
    escalation_path: Union[List[EscalationLevel], None] = Field(
        default=None,
        description="Escalation levels if enabled",
    )

    # Metadata
    routing_metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional routing metadata",
    )

    # Timing
    routed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When routing was determined",
    )

    @field_validator("recipient_channels")
    @classmethod
    def validate_recipient_channels(
        cls,
        v: Dict[UUID, List[str]],
    ) -> Dict[UUID, List[str]]:
        """Validate channels for each recipient."""
        valid_channels = {"email", "sms", "push"}
        for user_id, channels in v.items():
            for channel in channels:
                if channel not in valid_channels:
                    raise ValueError(
                        f"Invalid channel '{channel}' for user {user_id}"
                    )
        return v