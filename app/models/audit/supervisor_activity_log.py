# --- File: C:\Hostel-Main\app\models\audit\supervisor_activity_log.py ---
"""
Supervisor activity audit log model.

Tracks supervisor activities including task management,
student interactions, facility oversight, and performance metrics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Index, Integer, String, Text, Numeric,
    Enum as SQLEnum, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, INET
from sqlalchemy.orm import relationship, validates

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin
from app.schemas.audit.supervisor_activity_log import SupervisorActionCategory


class SupervisorActivityLog(BaseModel, TimestampMixin):
    """
    Comprehensive tracking of supervisor activities.
    
    Records all supervisor actions for accountability,
    performance monitoring, and audit trails.
    """
    
    __tablename__ = "supervisor_activity_logs"
    
    # Primary key
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )
    
    # Actor
    supervisor_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor performing the action"
    )
    supervisor_name = Column(
        String(255),
        nullable=True,
        comment="Supervisor name for display"
    )
    
    # Context
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel where action occurred"
    )
    hostel_name = Column(
        String(255),
        nullable=True,
        comment="Hostel name for display"
    )
    
    # Action details
    action_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Specific action identifier"
    )
    action_category = Column(
        SQLEnum(SupervisorActionCategory, name="supervisor_action_category_enum", create_type=True),
        nullable=False,
        index=True,
        comment="High-level action category"
    )
    action_description = Column(
        Text,
        nullable=False,
        comment="Human-readable action description"
    )
    
    # Entity affected
    entity_type = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Entity type affected"
    )
    entity_id = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the entity affected"
    )
    entity_name = Column(
        String(255),
        nullable=True,
        comment="Display name of affected entity"
    )
    
    # Related entities
    related_student_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Student involved in the action"
    )
    related_room_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Room involved in the action"
    )
    
    # Action outcome
    status = Column(
        String(20),
        nullable=False,
        default="completed",
        index=True,
        comment="Status of the action"
    )
    outcome = Column(
        String(500),
        nullable=True,
        comment="Brief outcome description"
    )
    
    # Additional data
    metadata = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Extra details/context for the action"
    )
    
    # Performance metrics
    time_taken_minutes = Column(
        Integer,
        nullable=True,
        comment="Time taken to complete (minutes)"
    )
    priority_level = Column(
        String(20),
        nullable=True,
        index=True,
        comment="Priority level of the action"
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
        comment="User-Agent string"
    )
    device_type = Column(
        String(20),
        nullable=True,
        index=True,
        comment="Device type used"
    )
    
    # Location (for field activities)
    location = Column(
        String(255),
        nullable=True,
        comment="Physical location where action was performed"
    )
    gps_coordinates = Column(
        String(50),
        nullable=True,
        comment="GPS coordinates (latitude,longitude)"
    )
    
    # Shift context
    shift_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("supervisor_shifts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Shift during which action occurred"
    )
    shift_type = Column(
        String(20),
        nullable=True,
        index=True,
        comment="Type of shift"
    )
    
    # Quality indicators (stored as numeric for decimal precision)
    quality_score = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Quality score for the action (0-5)"
    )
    student_feedback_score = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Student feedback score (0-5)"
    )
    
    # Computed efficiency score (stored for performance)
    efficiency_score = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Efficiency score (0-100)"
    )
    
    # Follow-up
    requires_follow_up = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Requires follow-up action"
    )
    follow_up_date = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When follow-up is due"
    )
    follow_up_completed = Column(
        Boolean,
        nullable=True,
        comment="Whether follow-up was completed"
    )
    
    # Relationships
    supervisor = relationship(
        "User",
        foreign_keys=[supervisor_id],
        backref="supervisor_activities"
    )
    hostel = relationship(
        "Hostel",
        backref="supervisor_activities"
    )
    related_student = relationship(
        "User",
        foreign_keys=[related_student_id],
        backref="related_supervisor_activities"
    )
    related_room = relationship(
        "Room",
        backref="supervisor_activities"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_sup_activity_supervisor_created', 'supervisor_id', 'created_at'),
        Index('idx_sup_activity_hostel_created', 'hostel_id', 'created_at'),
        Index('idx_sup_activity_action_created', 'action_type', 'created_at'),
        Index('idx_sup_activity_category_created', 'action_category', 'created_at'),
        Index('idx_sup_activity_status_created', 'status', 'created_at'),
        Index('idx_sup_activity_priority_created', 'priority_level', 'created_at'),
        Index('idx_sup_activity_entity_created', 'entity_type', 'entity_id', 'created_at'),
        Index('idx_sup_activity_shift', 'shift_id', 'created_at'),
        Index('idx_sup_activity_follow_up', 'requires_follow_up', 'follow_up_date'),
        Index('idx_sup_activity_student', 'related_student_id', 'created_at'),
        Index('idx_sup_activity_room', 'related_room_id', 'created_at'),
        # Composite indexes
        Index('idx_sup_activity_sup_cat_created', 'supervisor_id', 'action_category', 'created_at'),
        Index('idx_sup_activity_hostel_cat_created', 'hostel_id', 'action_category', 'created_at'),
        # GIN indexes
        Index('idx_sup_activity_metadata_gin', 'metadata', postgresql_using='gin'),
        # Constraints
        CheckConstraint(
            "status IN ('completed', 'pending', 'failed', 'cancelled')",
            name='ck_sup_activity_status'
        ),
        CheckConstraint(
            "priority_level IS NULL OR priority_level IN ('low', 'medium', 'high', 'urgent', 'critical')",
            name='ck_sup_activity_priority'
        ),
        CheckConstraint(
            "device_type IS NULL OR device_type IN ('mobile', 'tablet', 'desktop', 'other')",
            name='ck_sup_activity_device'
        ),
        CheckConstraint(
            "shift_type IS NULL OR shift_type IN ('morning', 'afternoon', 'evening', 'night')",
            name='ck_sup_activity_shift_type'
        ),
        CheckConstraint(
            "time_taken_minutes IS NULL OR time_taken_minutes >= 0",
            name='ck_sup_activity_time_positive'
        ),
        CheckConstraint(
            "time_taken_minutes IS NULL OR time_taken_minutes <= 1440",
            name='ck_sup_activity_time_max'
        ),
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 5)",
            name='ck_sup_activity_quality_range'
        ),
        CheckConstraint(
            "student_feedback_score IS NULL OR (student_feedback_score >= 0 AND student_feedback_score <= 5)",
            name='ck_sup_activity_feedback_range'
        ),
        CheckConstraint(
            "efficiency_score IS NULL OR (efficiency_score >= 0 AND efficiency_score <= 100)",
            name='ck_sup_activity_efficiency_range'
        ),
        CheckConstraint(
            "gps_coordinates IS NULL OR gps_coordinates ~ '^-?\\d+\\.\\d+,-?\\d+\\.\\d+$'",
            name='ck_sup_activity_gps_format'
        ),
        {'comment': 'Comprehensive supervisor activity tracking'}
    )
    
    @validates('time_taken_minutes')
    def validate_time_taken(self, key: str, value: Optional[int]) -> Optional[int]:
        """Validate time taken is reasonable."""
        if value is not None and value > 1440:
            raise ValueError("time_taken_minutes cannot exceed 1440 (24 hours)")
        if value is not None and value < 0:
            raise ValueError("time_taken_minutes cannot be negative")
        return value
    
    @validates('quality_score', 'student_feedback_score')
    def validate_score(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate score is in valid range."""
        if value is not None:
            if value < 0 or value > 5:
                raise ValueError(f"{key} must be between 0 and 5")
        return value
    
    @validates('gps_coordinates')
    def validate_gps(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate GPS coordinate format."""
        if value is None:
            return value
        
        import re
        if not re.match(r'^-?\d+\.\d+,-?\d+\.\d+$', value):
            raise ValueError("Invalid GPS coordinate format (expected: latitude,longitude)")
        
        return value
    
    def is_overdue(self) -> bool:
        """Check if follow-up is overdue."""
        if not self.requires_follow_up or not self.follow_up_date:
            return False
        
        if self.follow_up_completed:
            return False
        
        return datetime.utcnow() > self.follow_up_date.replace(tzinfo=None)
    
    def __repr__(self) -> str:
        return (
            f"<SupervisorActivityLog(id={self.id}, "
            f"supervisor_id={self.supervisor_id}, "
            f"action_type='{self.action_type}', "
            f"status='{self.status}')>"
        )