# --- File: C:\Hostel-Main\app\models\audit\entity_change_log.py ---
"""
Entity change log model for detailed field-level change tracking.

Provides granular change history for entities with before/after values,
change metadata, and comprehensive audit capabilities. This is a dedicated
model separate from the basic EntityChangeLog in audit_log.py for more
advanced change tracking scenarios.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Index, Integer, String, Text,
    ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, validates

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin


class EntityChangeLog(BaseModel, TimestampMixin):
    """
    Detailed field-level change tracking for entities.
    
    Provides granular change history for individual fields
    with before/after values, change context, and metadata.
    This is the primary model for entity change tracking.
    """
    
    __tablename__ = "entity_change_logs"
    
    # Primary key
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )
    
    # Link to audit log (optional - can exist independently)
    audit_log_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("audit_logs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Reference to main audit log entry"
    )
    
    # Entity information
    entity_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of entity (table name or model name)"
    )
    entity_id = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Entity primary key"
    )
    entity_display_name = Column(
        String(255),
        nullable=True,
        comment="Human-readable entity identifier"
    )
    
    # Field change details
    field_name = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Name of the field that changed"
    )
    field_display_name = Column(
        String(100),
        nullable=True,
        comment="Human-readable field name"
    )
    field_type = Column(
        String(50),
        nullable=True,
        comment="Data type of the field (string, integer, boolean, etc.)"
    )
    
    # Change values (stored as JSONB for flexibility)
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
    
    # Change operation
    change_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Type of change operation"
    )
    change_reason = Column(
        Text,
        nullable=True,
        comment="Reason for the change (if provided)"
    )
    
    # Actor information
    changed_by_user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who made the change"
    )
    changed_by_user_name = Column(
        String(255),
        nullable=True,
        comment="User name at time of change"
    )
    changed_by_user_role = Column(
        String(50),
        nullable=True,
        comment="User role at time of change"
    )
    
    # Change context
    change_source = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Source of change (web, api, import, system)"
    )
    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Request ID for correlation"
    )
    session_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="User session ID"
    )
    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP address of change origin"
    )
    
    # Security and compliance
    is_sensitive = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Contains sensitive data"
    )
    is_pii = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Contains personally identifiable information"
    )
    is_encrypted = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Values are encrypted"
    )
    
    # Metadata
    change_metadata = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional change metadata (context, validations, etc.)"
    )
    
    # Versioning
    version_number = Column(
        Integer,
        nullable=True,
        comment="Version number if entity supports versioning"
    )
    parent_change_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("entity_change_logs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent change for nested/related changes"
    )
    
    # Validation
    is_valid = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this change is still valid (not rolled back)"
    )
    invalidated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this change was invalidated"
    )
    invalidated_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who invalidated this change"
    )
    invalidation_reason = Column(
        Text,
        nullable=True,
        comment="Reason for invalidation"
    )
    
    # Change impact
    impact_score = Column(
        Integer,
        nullable=True,
        comment="Calculated impact score (0-100)"
    )
    requires_review = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Change requires manual review"
    )
    reviewed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When change was reviewed"
    )
    reviewed_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who reviewed the change"
    )
    
    # Relationships
    audit_log = relationship(
        "AuditLog",
        backref="entity_changes",
        foreign_keys=[audit_log_id]
    )
    changed_by_user = relationship(
        "User",
        foreign_keys=[changed_by_user_id],
        backref="entity_changes_made"
    )
    invalidated_by_user = relationship(
        "User",
        foreign_keys=[invalidated_by],
        backref="entity_changes_invalidated"
    )
    reviewed_by_user = relationship(
        "User",
        foreign_keys=[reviewed_by],
        backref="entity_changes_reviewed"
    )
    parent_change = relationship(
        "EntityChangeLog",
        remote_side=[id],
        backref="child_changes"
    )
    
    # Indexes for performance
    __table_args__ = (
        # Primary indexes
        Index('idx_entity_change_entity', 'entity_type', 'entity_id', 'created_at'),
        Index('idx_entity_change_field', 'entity_type', 'field_name', 'created_at'),
        Index('idx_entity_change_type', 'change_type', 'created_at'),
        Index('idx_entity_change_user', 'changed_by_user_id', 'created_at'),
        Index('idx_entity_change_audit', 'audit_log_id'),
        
        # Context indexes
        Index('idx_entity_change_source', 'change_source', 'created_at'),
        Index('idx_entity_change_request', 'request_id'),
        Index('idx_entity_change_session', 'session_id'),
        
        # Security indexes
        Index('idx_entity_change_sensitive', 'is_sensitive', 'created_at'),
        Index('idx_entity_change_pii', 'is_pii', 'created_at'),
        Index('idx_entity_change_review', 'requires_review', 'reviewed_at'),
        
        # Validity indexes
        Index('idx_entity_change_valid', 'is_valid', 'created_at'),
        Index('idx_entity_change_invalidated', 'invalidated_at'),
        
        # Composite indexes for common queries
        Index(
            'idx_entity_change_entity_field_created',
            'entity_type', 'entity_id', 'field_name', 'created_at'
        ),
        Index(
            'idx_entity_change_user_entity_created',
            'changed_by_user_id', 'entity_type', 'created_at'
        ),
        Index(
            'idx_entity_change_type_field_created',
            'entity_type', 'change_type', 'created_at'
        ),
        
        # GIN indexes for JSONB columns
        Index('idx_entity_change_old_value_gin', 'old_value', postgresql_using='gin'),
        Index('idx_entity_change_new_value_gin', 'new_value', postgresql_using='gin'),
        Index('idx_entity_change_metadata_gin', 'change_metadata', postgresql_using='gin'),
        
        # Constraints
        CheckConstraint(
            "change_type IN ('created', 'updated', 'deleted', 'restored', 'merged', 'split')",
            name='ck_entity_change_type'
        ),
        CheckConstraint(
            "change_source IS NULL OR change_source IN ('web', 'api', 'mobile', 'import', 'system', 'migration', 'sync')",
            name='ck_entity_change_source'
        ),
        CheckConstraint(
            "impact_score IS NULL OR (impact_score >= 0 AND impact_score <= 100)",
            name='ck_entity_change_impact_range'
        ),
        CheckConstraint(
            "NOT is_valid OR invalidated_at IS NULL",
            name='ck_entity_change_valid_no_invalidation'
        ),
        CheckConstraint(
            "is_valid OR invalidated_at IS NOT NULL",
            name='ck_entity_change_invalid_has_date'
        ),
        
        # Unique constraint for preventing duplicate change logs
        UniqueConstraint(
            'entity_type', 'entity_id', 'field_name', 'created_at', 'changed_by_user_id',
            name='uq_entity_change_duplicate_prevention'
        ),
        
        {'comment': 'Detailed field-level change tracking for entities'}
    )
    
    @validates('field_name')
    def validate_field_name(self, key: str, value: str) -> str:
        """Validate field name format."""
        if not value or len(value.strip()) == 0:
            raise ValueError("field_name cannot be empty")
        if len(value) > 100:
            raise ValueError("field_name too long (max 100 characters)")
        return value.strip()
    
    @validates('change_type')
    def validate_change_type(self, key: str, value: str) -> str:
        """Validate change type."""
        valid_types = ['created', 'updated', 'deleted', 'restored', 'merged', 'split']
        if value not in valid_types:
            raise ValueError(f"Invalid change_type: {value}. Must be one of {valid_types}")
        return value
    
    @validates('impact_score')
    def validate_impact_score(self, key: str, value: Optional[int]) -> Optional[int]:
        """Validate impact score range."""
        if value is not None:
            if value < 0 or value > 100:
                raise ValueError("impact_score must be between 0 and 100")
        return value
    
    def has_actual_change(self) -> bool:
        """
        Check if there's an actual value change.
        
        Returns:
            True if values actually changed, False otherwise
        """
        if self.change_type in ['created', 'deleted', 'restored']:
            return True
        
        return self.old_value != self.new_value
    
    def get_display_value(self, mask_sensitive: bool = True) -> str:
        """
        Get safe display value for the change.
        
        Args:
            mask_sensitive: Whether to mask sensitive data
            
        Returns:
            Human-readable change description
        """
        if mask_sensitive and self.is_sensitive:
            return "***REDACTED***"
        
        if self.change_type == "created":
            return f"Created: {self._format_value(self.new_value)}"
        elif self.change_type == "deleted":
            return f"Deleted: {self._format_value(self.old_value)}"
        elif self.change_type == "restored":
            return f"Restored: {self._format_value(self.new_value)}"
        else:
            old = self._format_value(self.old_value)
            new = self._format_value(self.new_value)
            return f"{old} → {new}"
    
    def _format_value(self, value: Any) -> str:
        """Format value for display."""
        if value is None:
            return "null"
        
        if isinstance(value, dict):
            return f"{{...}}"  # Simplified dict display
        elif isinstance(value, list):
            return f"[{len(value)} items]"
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, str) and len(value) > 50:
            return f"{value[:47]}..."
        else:
            return str(value)
    
    def invalidate(
        self,
        invalidated_by: UUID,
        reason: str,
        commit: bool = True
    ) -> "EntityChangeLog":
        """
        Invalidate this change (mark as rolled back).
        
        Args:
            invalidated_by: User ID who is invalidating
            reason: Reason for invalidation
            commit: Whether to commit to database
            
        Returns:
            Self for chaining
        """
        self.is_valid = False
        self.invalidated_at = datetime.utcnow()
        self.invalidated_by = invalidated_by
        self.invalidation_reason = reason
        
        return self
    
    def mark_reviewed(self, reviewed_by: UUID, commit: bool = True) -> "EntityChangeLog":
        """
        Mark change as reviewed.
        
        Args:
            reviewed_by: User ID who reviewed
            commit: Whether to commit to database
            
        Returns:
            Self for chaining
        """
        self.reviewed_at = datetime.utcnow()
        self.reviewed_by = reviewed_by
        
        return self
    
    def calculate_impact_score(self) -> int:
        """
        Calculate impact score for this change.
        
        Returns:
            Impact score (0-100)
        """
        score = 0
        
        # Base score by change type
        type_scores = {
            'created': 20,
            'updated': 10,
            'deleted': 50,
            'restored': 30,
            'merged': 40,
            'split': 40,
        }
        score += type_scores.get(self.change_type, 10)
        
        # Increase for sensitive/PII data
        if self.is_sensitive:
            score += 20
        if self.is_pii:
            score += 30
        
        # Increase for certain field types
        critical_fields = ['status', 'is_active', 'is_deleted', 'approved']
        if self.field_name.lower() in critical_fields:
            score += 20
        
        # Cap at 100
        self.impact_score = min(100, score)
        return self.impact_score
    
    @classmethod
    def get_entity_history(
        cls,
        db,
        entity_type: str,
        entity_id: UUID,
        field_name: Optional[str] = None,
        only_valid: bool = True,
        limit: int = 100
    ) -> List["EntityChangeLog"]:
        """
        Get change history for an entity.
        
        Args:
            db: Database session
            entity_type: Type of entity
            entity_id: Entity ID
            field_name: Optional specific field to filter
            only_valid: Only return valid (non-invalidated) changes
            limit: Maximum number of records
            
        Returns:
            List of change log entries
        """
        query = db.query(cls).filter(
            cls.entity_type == entity_type,
            cls.entity_id == entity_id
        )
        
        if field_name:
            query = query.filter(cls.field_name == field_name)
        
        if only_valid:
            query = query.filter(cls.is_valid == True)
        
        return query.order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_field_history(
        cls,
        db,
        entity_type: str,
        entity_id: UUID,
        field_name: str,
        only_valid: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get complete history of changes for a specific field.
        
        Args:
            db: Database session
            entity_type: Type of entity
            entity_id: Entity ID
            field_name: Field name
            only_valid: Only return valid changes
            
        Returns:
            List of dictionaries with change timeline
        """
        changes = cls.get_entity_history(
            db=db,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            only_valid=only_valid
        )
        
        return [
            {
                "timestamp": change.created_at,
                "old_value": change.old_value,
                "new_value": change.new_value,
                "changed_by": change.changed_by_user_name,
                "change_type": change.change_type,
                "reason": change.change_reason,
            }
            for change in changes
        ]
    
    @classmethod
    def create_change(
        cls,
        db,
        entity_type: str,
        entity_id: UUID,
        field_name: str,
        old_value: Any,
        new_value: Any,
        change_type: str,
        changed_by: Optional[UUID] = None,
        **kwargs
    ) -> "EntityChangeLog":
        """
        Create a new change log entry.
        
        Args:
            db: Database session
            entity_type: Type of entity
            entity_id: Entity ID
            field_name: Field that changed
            old_value: Previous value
            new_value: New value
            change_type: Type of change
            changed_by: User who made the change
            **kwargs: Additional fields
            
        Returns:
            Created EntityChangeLog instance
        """
        change = cls(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_type=change_type,
            changed_by_user_id=changed_by,
            **kwargs
        )
        
        # Calculate impact score
        change.calculate_impact_score()
        
        # Determine if review is required
        if change.impact_score and change.impact_score >= 50:
            change.requires_review = True
        
        db.add(change)
        db.flush()
        
        return change
    
    def to_dict(self, include_values: bool = True, mask_sensitive: bool = True) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Args:
            include_values: Whether to include old/new values
            mask_sensitive: Whether to mask sensitive data
            
        Returns:
            Dictionary representation
        """
        result = {
            "id": str(self.id),
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "field_name": self.field_name,
            "change_type": self.change_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "changed_by": self.changed_by_user_name,
            "is_valid": self.is_valid,
            "is_sensitive": self.is_sensitive,
            "impact_score": self.impact_score,
        }
        
        if include_values:
            if mask_sensitive and self.is_sensitive:
                result["old_value"] = "***REDACTED***"
                result["new_value"] = "***REDACTED***"
            else:
                result["old_value"] = self.old_value
                result["new_value"] = self.new_value
        
        return result
    
    def __repr__(self) -> str:
        return (
            f"<EntityChangeLog(id={self.id}, "
            f"entity_type='{self.entity_type}', "
            f"field_name='{self.field_name}', "
            f"change_type='{self.change_type}', "
            f"created_at={self.created_at})>"
        )


class EntityChangeHistory(BaseModel, TimestampMixin):
    """
    Aggregated change history summary for entities.
    
    Provides snapshot-based history tracking for complete
    entity state at different points in time.
    """
    
    __tablename__ = "entity_change_histories"
    
    # Primary key
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )
    
    # Entity identification
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
    
    # Snapshot data
    snapshot_data = Column(
        JSONB,
        nullable=False,
        comment="Complete entity state at this point"
    )
    snapshot_timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When this snapshot was taken"
    )
    
    # Version information
    version_number = Column(
        Integer,
        nullable=False,
        comment="Version number for this snapshot"
    )
    is_current_version = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Is this the current version"
    )
    
    # Change summary
    total_changes = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of changes to this version"
    )
    changed_fields = Column(
        JSONB,
        nullable=True,
        comment="List of fields changed in this version"
    )
    
    # Actor
    created_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created this version"
    )
    
    # Metadata
    change_summary = Column(
        Text,
        nullable=True,
        comment="Human-readable summary of changes"
    )
    tags = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="Tags for categorizing versions"
    )
    
    # Relationships
    creator = relationship(
        "User",
        backref="entity_history_snapshots"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_entity_history_entity', 'entity_type', 'entity_id', 'snapshot_timestamp'),
        Index('idx_entity_history_version', 'entity_type', 'entity_id', 'version_number'),
        Index('idx_entity_history_current', 'entity_type', 'entity_id', 'is_current_version'),
        Index('idx_entity_history_snapshot_gin', 'snapshot_data', postgresql_using='gin'),
        Index('idx_entity_history_fields_gin', 'changed_fields', postgresql_using='gin'),
        
        UniqueConstraint(
            'entity_type', 'entity_id', 'version_number',
            name='uq_entity_history_version'
        ),
        
        {'comment': 'Entity state snapshots for version history'}
    )
    
    def __repr__(self) -> str:
        return (
            f"<EntityChangeHistory(id={self.id}, "
            f"entity_type='{self.entity_type}', "
            f"version={self.version_number})>"
        )