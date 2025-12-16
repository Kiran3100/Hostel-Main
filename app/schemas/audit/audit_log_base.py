# --- File: app/schemas/audit/audit_log_base.py ---
"""
Base schemas for audit log entries with enhanced validation.

Provides core audit logging functionality for tracking all system actions
including user activities, data changes, and system events with comprehensive
metadata and traceability.
"""

from datetime import datetime
from typing import Any, Dict, Union, List
from ipaddress import IPv4Address, IPv6Address, ip_address
import re

from pydantic import Field, field_validator, computed_field, model_validator
from uuid import UUID

from app.schemas.common.base import BaseSchema, BaseCreateSchema
from app.schemas.common.enums import AuditActionCategory, UserRole

__all__ = [
    "AuditLogBase",
    "AuditLogCreate",
    "AuditContext",
    "ChangeDetail",
]


class AuditContext(BaseSchema):
    """
    Contextual information for audit events.
    
    Provides additional metadata about the environment
    and circumstances of the audited action.
    """
    
    # Request context
    request_id: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Unique request/trace ID for correlation"
    )
    session_id: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="User session identifier"
    )
    
    # Network context
    ip_address: Union[str, None] = Field(
        default=None,
        max_length=45,
        description="IP address (IPv4 or IPv6)"
    )
    user_agent: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="User-Agent string from request"
    )
    
    # Geographic context
    country_code: Union[str, None] = Field(
        default=None,
        pattern=r"^[A-Z]{2}$",
        description="ISO 3166-1 alpha-2 country code"
    )
    region: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Geographic region/state"
    )
    city: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="City name"
    )
    
    # Device context
    device_type: Union[str, None] = Field(
        default=None,
        pattern="^(desktop|mobile|tablet|api|system)$",
        description="Type of device used"
    )
    platform: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Operating system/platform"
    )
    
    # API context
    api_version: Union[str, None] = Field(
        default=None,
        max_length=20,
        description="API version used"
    )
    endpoint: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="API endpoint accessed"
    )
    http_method: Union[str, None] = Field(
        default=None,
        pattern="^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)$",
        description="HTTP method used"
    )
    
    # Additional metadata
    custom_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom metadata"
    )
    
    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate IP address format."""
        if v is None:
            return v
        
        try:
            # This will raise ValueError if invalid
            ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address format: {v}")
    
    @field_validator("user_agent")
    @classmethod
    def validate_user_agent(cls, v: Union[str, None]) -> Union[str, None]:
        """Sanitize and validate user agent string."""
        if v is None:
            return v
        
        # Remove control characters and excessive whitespace
        sanitized = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', v)
        sanitized = ' '.join(sanitized.split())
        
        return sanitized[:500]  # Enforce max length
    
    @computed_field
    @property
    def is_mobile(self) -> bool:
        """Determine if request came from mobile device."""
        if not self.user_agent:
            return False
        
        mobile_patterns = [
            r'Mobile', r'Android', r'iPhone', r'iPad',
            r'Windows Phone', r'BlackBerry'
        ]
        
        return any(
            re.search(pattern, self.user_agent, re.IGNORECASE)
            for pattern in mobile_patterns
        )
    
    @computed_field
    @property
    def browser_name(self) -> Union[str, None]:
        """Extract browser name from user agent."""
        if not self.user_agent:
            return None
        
        browsers = {
            'Chrome': r'Chrome/[\d.]+',
            'Firefox': r'Firefox/[\d.]+',
            'Safari': r'Safari/[\d.]+',
            'Edge': r'Edg/[\d.]+',
            'Opera': r'Opera/[\d.]+',
        }
        
        for name, pattern in browsers.items():
            if re.search(pattern, self.user_agent, re.IGNORECASE):
                return name
        
        return "Unknown"


class ChangeDetail(BaseSchema):
    """
    Detailed information about a specific field change.
    
    Provides granular tracking of what changed, from what value,
    and to what value for audit trails.
    """
    
    field_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the field that changed"
    )
    field_type: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Data type of the field"
    )
    old_value: Union[Any, None] = Field(
        default=None,
        description="Previous value before change"
    )
    new_value: Union[Any, None] = Field(
        default=None,
        description="New value after change"
    )
    change_type: str = Field(
        ...,
        pattern="^(created|updated|deleted|restored)$",
        description="Type of change operation"
    )
    is_sensitive: bool = Field(
        default=False,
        description="Whether this field contains sensitive data"
    )
    
    @computed_field
    @property
    def has_actual_change(self) -> bool:
        """Check if there's an actual value change."""
        if self.change_type in ['created', 'deleted', 'restored']:
            return True
        return self.old_value != self.new_value
    
    @computed_field
    @property
    def display_value(self) -> str:
        """Get safe display value (masks sensitive data)."""
        if self.is_sensitive:
            return "***REDACTED***"
        
        if self.change_type == "created":
            return f"Created: {self.new_value}"
        elif self.change_type == "deleted":
            return f"Deleted: {self.old_value}"
        elif self.change_type == "restored":
            return f"Restored: {self.new_value}"
        else:
            return f"{self.old_value} → {self.new_value}"


class AuditLogBase(BaseSchema):
    """
    Base audit log entry schema.
    
    Comprehensive audit logging for all system actions with full
    context, change tracking, and metadata support.
    """
    
    # Actor information
    user_id: Union[UUID, None] = Field(
        default=None,
        description="ID of user who performed the action"
    )
    user_role: Union[UserRole, None] = Field(
        default=None,
        description="Role of the user at time of action"
    )
    user_email: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Email of the user (for reference)"
    )
    impersonator_id: Union[UUID, None] = Field(
        default=None,
        description="ID of user impersonating (if applicable)"
    )
    
    # Action details
    action_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Specific action identifier (e.g., 'booking.created')"
    )
    action_category: AuditActionCategory = Field(
        ...,
        description="High-level action category"
    )
    action_description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Human-readable description of the action"
    )
    
    # Entity information
    entity_type: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Type of entity affected (e.g., 'Booking', 'Payment')"
    )
    entity_id: Union[UUID, None] = Field(
        default=None,
        description="Primary key of the affected entity"
    )
    entity_name: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Display name/identifier of the entity"
    )
    
    # Related entity (for relationships)
    related_entity_type: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Type of related entity"
    )
    related_entity_id: Union[UUID, None] = Field(
        default=None,
        description="ID of related entity"
    )
    
    # Organizational context
    hostel_id: Union[UUID, None] = Field(
        default=None,
        description="Hostel context (if applicable)"
    )
    hostel_name: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Hostel name for display"
    )
    
    # Change tracking
    old_values: Union[Dict[str, Any], None] = Field(
        default=None,
        description="Previous values (for update/delete actions)"
    )
    new_values: Union[Dict[str, Any], None] = Field(
        default=None,
        description="New values (for create/update actions)"
    )
    change_details: Union[List[ChangeDetail], None] = Field(
        default=None,
        description="Detailed field-level changes"
    )
    
    # Request context
    context: Union[AuditContext, None] = Field(
        default=None,
        description="Contextual information about the action"
    )
    
    # Legacy fields for backward compatibility
    ip_address: Union[str, None] = Field(
        default=None,
        description="IP address (deprecated: use context.ip_address)"
    )
    user_agent: Union[str, None] = Field(
        default=None,
        description="User agent (deprecated: use context.user_agent)"
    )
    request_id: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Request ID (deprecated: use context.request_id)"
    )
    
    # Status and result
    status: str = Field(
        default="success",
        pattern="^(success|failure|partial|pending)$",
        description="Outcome status of the action"
    )
    error_message: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Error message if status is failure"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the action occurred"
    )
    
    # Security and compliance
    is_sensitive: bool = Field(
        default=False,
        description="Whether this log contains sensitive information"
    )
    retention_days: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Number of days to retain this log entry"
    )
    compliance_tags: List[str] = Field(
        default_factory=list,
        description="Compliance framework tags (GDPR, HIPAA, etc.)"
    )
    
    @model_validator(mode='after')
    def validate_change_tracking(self) -> 'AuditLogBase':
        """Validate change tracking fields are consistent."""
        
        # For update actions, we should have old and new values
        if 'update' in self.action_type.lower():
            if self.old_values is None and self.new_values is None:
                # Warning: update action without change tracking
                pass
        
        # For create actions, we should have new values
        if 'create' in self.action_type.lower():
            if self.new_values is None:
                # Warning: create action without new values
                pass
        
        # For delete actions, we should have old values
        if 'delete' in self.action_type.lower():
            if self.old_values is None:
                # Warning: delete action without old values
                pass
        
        return self
    
    @model_validator(mode='after')
    def migrate_legacy_fields(self) -> 'AuditLogBase':
        """Migrate legacy fields to context object."""
        
        # If context doesn't exist but legacy fields do, create context
        if self.context is None and any([
            self.ip_address,
            self.user_agent,
            self.request_id
        ]):
            self.context = AuditContext(
                ip_address=self.ip_address,
                user_agent=self.user_agent,
                request_id=self.request_id
            )
        
        return self
    
    @computed_field
    @property
    def severity_level(self) -> str:
        """
        Determine severity level of the audit event.
        
        Returns:
            'critical', 'high', 'medium', 'low', or 'info'
        """
        critical_actions = [
            'authentication.failed_multiple',
            'authorization.access_denied',
            'user_management.deleted',
            'payment.refunded',
            'configuration.security_changed'
        ]
        
        high_actions = [
            'authentication.login',
            'authentication.logout',
            'user_management.created',
            'user_management.role_changed',
            'payment.created'
        ]
        
        if self.status == 'failure':
            return 'high'
        
        if self.action_type in critical_actions:
            return 'critical'
        
        if self.action_type in high_actions:
            return 'high'
        
        if self.action_category in [
            AuditActionCategory.AUTHENTICATION,
            AuditActionCategory.AUTHORIZATION,
            AuditActionCategory.USER_MANAGEMENT
        ]:
            return 'medium'
        
        return 'low'
    
    @computed_field
    @property
    def requires_review(self) -> bool:
        """Determine if this audit event requires manual review."""
        return (
            self.severity_level in ['critical', 'high'] or
            self.status == 'failure' or
            self.impersonator_id is not None or
            self.is_sensitive
        )
    
    @computed_field
    @property
    def changed_fields(self) -> List[str]:
        """Get list of fields that were changed."""
        if self.change_details:
            return [
                detail.field_name
                for detail in self.change_details
                if detail.has_actual_change
            ]
        
        if self.old_values and self.new_values:
            changed = []
            for key in set(self.old_values.keys()) | set(self.new_values.keys()):
                old = self.old_values.get(key)
                new = self.new_values.get(key)
                if old != new:
                    changed.append(key)
            return changed
        
        return []
    
    def to_log_message(self) -> str:
        """
        Generate structured log message.
        
        Returns:
            Human-readable log message string
        """
        parts = [
            f"[{self.action_category.value.upper()}]",
            f"Action: {self.action_type}",
        ]
        
        if self.user_id:
            parts.append(f"User: {self.user_id}")
        
        if self.entity_type and self.entity_id:
            parts.append(f"Entity: {self.entity_type}#{self.entity_id}")
        
        if self.hostel_id:
            parts.append(f"Hostel: {self.hostel_id}")
        
        parts.append(f"Status: {self.status}")
        
        if self.context and self.context.ip_address:
            parts.append(f"IP: {self.context.ip_address}")
        
        return " | ".join(parts)


class AuditLogCreate(AuditLogBase, BaseCreateSchema):
    """
    Payload for creating new audit log entries.
    
    Used by services and middleware to record audit events
    throughout the application lifecycle.
    """
    
    @classmethod
    def from_request(
        cls,
        action_type: str,
        action_category: AuditActionCategory,
        description: str,
        user_id: Union[UUID, None] = None,
        user_role: Union[UserRole, None] = None,
        entity_type: Union[str, None] = None,
        entity_id: Union[UUID, None] = None,
        hostel_id: Union[UUID, None] = None,
        old_values: Union[Dict[str, Any], None] = None,
        new_values: Union[Dict[str, Any], None] = None,
        request_context: Union[Dict[str, Any], None] = None,
        **kwargs
    ) -> "AuditLogCreate":
        """
        Factory method to create audit log from request context.
        
        Args:
            action_type: Type of action performed
            action_category: Category of the action
            description: Human-readable description
            user_id: User performing the action
            user_role: User's role
            entity_type: Type of entity affected
            entity_id: ID of entity affected
            hostel_id: Hostel context
            old_values: Previous values
            new_values: New values
            request_context: Request metadata (IP, user agent, etc.)
            **kwargs: Additional fields
            
        Returns:
            AuditLogCreate instance
        """
        context = None
        if request_context:
            context = AuditContext(**request_context)
        
        return cls(
            action_type=action_type,
            action_category=action_category,
            action_description=description,
            user_id=user_id,
            user_role=user_role,
            entity_type=entity_type,
            entity_id=entity_id,
            hostel_id=hostel_id,
            old_values=old_values,
            new_values=new_values,
            context=context,
            **kwargs
        )
    
    @classmethod
    def for_authentication(
        cls,
        user_id: UUID,
        action: str,
        success: bool,
        ip_address: Union[str, None] = None,
        user_agent: Union[str, None] = None,
        **kwargs
    ) -> "AuditLogCreate":
        """
        Create audit log for authentication event.
        
        Args:
            user_id: User attempting authentication
            action: Authentication action (login, logout, etc.)
            success: Whether authentication succeeded
            ip_address: IP address of request
            user_agent: User agent string
            **kwargs: Additional fields
            
        Returns:
            AuditLogCreate instance
        """
        context = AuditContext(
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return cls(
            user_id=user_id,
            action_type=f"authentication.{action}",
            action_category=AuditActionCategory.AUTHENTICATION,
            action_description=f"User {action} {'successful' if success else 'failed'}",
            status="success" if success else "failure",
            context=context,
            **kwargs
        )