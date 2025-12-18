# --- File: C:\Hostel-Main\app\models\audit\audit_log.py ---
"""
Audit log model for comprehensive system activity tracking.

Tracks all system actions including user activities, data changes,
and system events with full context and metadata.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Index, Integer, String, Text,
    Enum as SQLEnum, ForeignKey, JSON, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, INET
from sqlalchemy.orm import relationship, validates

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin
from app.schemas.common.enums import AuditActionCategory, UserRole


class AuditLog(BaseModel, TimestampMixin):
    """
    Comprehensive audit log for all system actions.
    
    Provides complete audit trail with full context, change tracking,
    and metadata for compliance, security, and analytics.
    """
    
    __tablename__ = "audit_logs"
    
    # Primary key
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )
    
    # Actor information
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed the action"
    )
    user_role = Column(
        SQLEnum(UserRole, name="user_role_enum", create_type=True),
        nullable=True,
        index=True,
        comment="User role at time of action"
    )
    user_email = Column(
        String(255),
        nullable=True,
        index=True,
        comment="User email for reference"
    )
    impersonator_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User impersonating (if applicable)"
    )
    
    # Action details
    action_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Specific action identifier"
    )
    action_category = Column(
        SQLEnum(AuditActionCategory, name="audit_action_category_enum", create_type=True),
        nullable=False,
        index=True,
        comment="High-level action category"
    )
    action_description = Column(
        Text,
        nullable=False,
        comment="Human-readable action description"
    )
    
    # Entity information
    entity_type = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of entity affected"
    )
    entity_id = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Primary key of affected entity"
    )
    entity_name = Column(
        String(255),
        nullable=True,
        comment="Display name of entity"
    )
    
    # Related entity (for relationships)
    related_entity_type = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of related entity"
    )
    related_entity_id = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of related entity"
    )
    
    # Organizational context
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Hostel context"
    )
    hostel_name = Column(
        String(255),
        nullable=True,
        comment="Hostel name for display"
    )
    
    # Change tracking
    old_values = Column(
        JSONB,
        nullable=True,
        comment="Previous values (for update/delete)"
    )
    new_values = Column(
        JSONB,
        nullable=True,
        comment="New values (for create/update)"
    )
    
    # Request context
    ip_address = Column(
        INET,
        nullable=True,
        index=True,
        comment="IP address of request"
    )
    user_agent = Column(
        String(500),
        nullable=True,
        comment="User agent string"
    )
    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Request/trace ID for correlation"
    )
    session_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="User session identifier"
    )
    
    # Context metadata (replaces separate AuditContext)
    context_metadata = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional context (geo, device, API details)"
    )
    
    # Status and result
    status = Column(
        String(20),
        nullable=False,
        default="success",
        index=True,
        comment="Action outcome status"
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if status is failure"
    )
    
    # Security and compliance
    is_sensitive = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Contains sensitive information"
    )
    retention_days = Column(
        Integer,
        nullable=True,
        comment="Retention period in days"
    )
    compliance_tags = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="Compliance framework tags"
    )
    
    # Computed severity level (stored for performance)
    severity_level = Column(
        String(20),
        nullable=False,
        default="low",
        index=True,
        comment="Severity level (critical/high/medium/low/info)"
    )
    requires_review = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Requires manual review"
    )
    
    # Relationships
    user = relationship(
        "User",
        foreign_keys=[user_id],
        backref="audit_logs"
    )
    impersonator = relationship(
        "User",
        foreign_keys=[impersonator_id],
        backref="impersonated_actions"
    )
    hostel = relationship(
        "Hostel",
        backref="audit_logs"
    )
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_audit_user_created', 'user_id', 'created_at'),
        Index('idx_audit_entity_created', 'entity_type', 'entity_id', 'created_at'),
        Index('idx_audit_hostel_created', 'hostel_id', 'created_at'),
        Index('idx_audit_action_created', 'action_type', 'created_at'),
        Index('idx_audit_category_created', 'action_category', 'created_at'),
        Index('idx_audit_status_created', 'status', 'created_at'),
        Index('idx_audit_severity_created', 'severity_level', 'created_at'),
        Index('idx_audit_review_created', 'requires_review', 'created_at'),
        Index('idx_audit_sensitive', 'is_sensitive', 'created_at'),
        Index('idx_audit_ip_created', 'ip_address', 'created_at'),
        Index('idx_audit_request_id', 'request_id'),
        Index('idx_audit_session_id', 'session_id'),
        # Composite indexes for common queries
        Index('idx_audit_user_action_created', 'user_id', 'action_type', 'created_at'),
        Index('idx_audit_entity_action_created', 'entity_type', 'entity_id', 'action_type', 'created_at'),
        # GIN indexes for JSONB columns
        Index('idx_audit_old_values_gin', 'old_values', postgresql_using='gin'),
        Index('idx_audit_new_values_gin', 'new_values', postgresql_using='gin'),
        Index('idx_audit_context_gin', 'context_metadata', postgresql_using='gin'),
        Index('idx_audit_compliance_gin', 'compliance_tags', postgresql_using='gin'),
        # Constraints
        CheckConstraint(
            "status IN ('success', 'failure', 'partial', 'pending')",
            name='ck_audit_status'
        ),
        CheckConstraint(
            "severity_level IN ('critical', 'high', 'medium', 'low', 'info')",
            name='ck_audit_severity'
        ),
        CheckConstraint(
            "retention_days IS NULL OR retention_days > 0",
            name='ck_audit_retention_positive'
        ),
        {'comment': 'Comprehensive audit trail for all system actions'}
    )
    
    @validates('action_type')
    def validate_action_type(self, key: str, value: str) -> str:
        """Validate action type format."""
        if not value or len(value.strip()) == 0:
            raise ValueError("action_type cannot be empty")
        if len(value) > 100:
            raise ValueError("action_type too long (max 100 characters)")
        return value.strip()
    
    @validates('action_description')
    def validate_action_description(self, key: str, value: str) -> str:
        """Validate action description."""
        if not value or len(value.strip()) == 0:
            raise ValueError("action_description cannot be empty")
        if len(value) > 2000:
            raise ValueError("action_description too long (max 2000 characters)")
        return value.strip()
    
    @validates('ip_address')
    def validate_ip_address(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate IP address format."""
        if value is None:
            return value
        # PostgreSQL INET type handles validation
        return value
    
    @validates('user_agent')
    def validate_user_agent(self, key: str, value: Optional[str]) -> Optional[str]:
        """Sanitize user agent string."""
        if value is None:
            return value
        # Remove control characters
        import re
        sanitized = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', value)
        sanitized = ' '.join(sanitized.split())
        return sanitized[:500] if sanitized else None
    
    def get_changed_fields(self) -> List[str]:
        """Get list of fields that were changed."""
        if not self.old_values or not self.new_values:
            return []
        
        changed = []
        all_keys = set(self.old_values.keys()) | set(self.new_values.keys())
        
        for key in all_keys:
            old = self.old_values.get(key)
            new = self.new_values.get(key)
            if old != new:
                changed.append(key)
        
        return changed
    
    def to_log_message(self) -> str:
        """Generate structured log message."""
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
        
        if self.ip_address:
            parts.append(f"IP: {self.ip_address}")
        
        return " | ".join(parts)
    
    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, "
            f"action_type='{self.action_type}', "
            f"user_id={self.user_id}, "
            f"status='{self.status}', "
            f"created_at={self.created_at})>"
        )


class EntityChangeLog(BaseModel, TimestampMixin):
    """
    Detailed field-level change tracking for entities.
    
    Provides granular change history for individual fields
    with before/after values and metadata.
    """
    
    __tablename__ = "entity_change_logs"
    
    # Primary key
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )
    
    # Link to audit log
    audit_log_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("audit_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to main audit log entry"
    )
    
    # Entity information
    entity_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of entity"
    )
    entity_id = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Entity primary key"
    )
    
    # Field change details
    field_name = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Name of the field that changed"
    )
    field_type = Column(
        String(50),
        nullable=True,
        comment="Data type of the field"
    )
    old_value = Column(
        JSONB,
        nullable=True,
        comment="Previous value before change"
    )
    new_value = Column(
        JSONB,
        nullable=True,
        comment="New value after change"
    )
    change_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Type of change operation"
    )
    
    # Security
    is_sensitive = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Contains sensitive data"
    )
    
    # Metadata
    change_metadata = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional change metadata"
    )
    
    # Relationships
    audit_log = relationship(
        "AuditLog",
        backref="change_details"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_change_audit_log', 'audit_log_id'),
        Index('idx_change_entity', 'entity_type', 'entity_id', 'created_at'),
        Index('idx_change_field', 'entity_type', 'field_name', 'created_at'),
        Index('idx_change_type', 'change_type', 'created_at'),
        # GIN indexes for JSONB
        Index('idx_change_old_value_gin', 'old_value', postgresql_using='gin'),
        Index('idx_change_new_value_gin', 'new_value', postgresql_using='gin'),
        Index('idx_change_metadata_gin', 'change_metadata', postgresql_using='gin'),
        # Constraints
        CheckConstraint(
            "change_type IN ('created', 'updated', 'deleted', 'restored')",
            name='ck_change_type'
        ),
        {'comment': 'Granular field-level change tracking'}
    )
    
    def has_actual_change(self) -> bool:
        """Check if there's an actual value change."""
        if self.change_type in ['created', 'deleted', 'restored']:
            return True
        return self.old_value != self.new_value
    
    def get_display_value(self) -> str:
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
    
    def __repr__(self) -> str:
        return (
            f"<EntityChangeLog(id={self.id}, "
            f"entity_type='{self.entity_type}', "
            f"field_name='{self.field_name}', "
            f"change_type='{self.change_type}')>"
        )