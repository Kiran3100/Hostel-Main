"""
Announcement targeting models.

This module defines models for managing announcement targeting
rules and audience selection.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.enums import RoomType, TargetAudience
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.announcement.announcement import Announcement
    from app.models.user.user import User

__all__ = [
    "AnnouncementTarget",
    "TargetingRule",
    "TargetAudienceCache",
    "BulkTargetingRule",
]


class AnnouncementTarget(UUIDMixin, TimestampModel, BaseModel):
    """
    Announcement targeting configuration.
    
    Defines who should receive the announcement based on
    various targeting criteria.
    """
    
    __tablename__ = "announcement_targets"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the targeting",
    )
    
    # Target Type
    target_type: Mapped[TargetAudience] = mapped_column(
        Enum(TargetAudience, name="target_audience_enum"),
        nullable=False,
        index=True,
        comment="Type of targeting strategy",
    )
    
    # Specific Targets
    room_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Specific room UUIDs to target",
    )
    floor_numbers: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer),
        nullable=True,
        comment="Specific floor numbers to target",
    )
    student_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Specific student UUIDs to target",
    )
    
    # Exclusions
    exclude_student_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Students to exclude from targeting",
    )
    exclude_room_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Rooms to exclude from targeting",
    )
    
    # Selection Criteria
    include_active_students: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Include students with active status",
    )
    include_inactive_students: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Include students with inactive status",
    )
    include_notice_period_students: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Include students in notice period",
    )
    
    # Room Type Filters
    room_types: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Filter by room types",
    )
    
    # Calculated Recipients
    estimated_recipients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Estimated number of recipients",
    )
    actual_recipients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Actual number of recipients after calculation",
    )
    
    # Validation
    is_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether targeting has been validated",
    )
    validation_errors: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Any validation errors or warnings",
    )
    validated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When targeting was last validated",
    )
    
    # Metadata (renamed from metadata to avoid SQLAlchemy conflict)
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional targeting metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="targets",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="select",
    )
    rules: Mapped[List["TargetingRule"]] = relationship(
        "TargetingRule",
        back_populates="target",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_announcement_targets_announcement", "announcement_id"),
        Index("ix_announcement_targets_type", "target_type"),
        CheckConstraint(
            "estimated_recipients >= 0",
            name="ck_announcement_targets_estimated_recipients",
        ),
        CheckConstraint(
            "actual_recipients >= 0",
            name="ck_announcement_targets_actual_recipients",
        ),
        {"comment": "Announcement targeting configuration"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnnouncementTarget(id={self.id}, announcement_id={self.announcement_id}, "
            f"type={self.target_type.value}, recipients={self.actual_recipients})>"
        )


class TargetingRule(UUIDMixin, TimestampModel, BaseModel):
    """
    Individual targeting rules.
    
    Defines specific rules that determine which students
    should receive the announcement.
    """
    
    __tablename__ = "announcement_targeting_rules"
    
    # Foreign Keys
    target_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_targets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated targeting configuration",
    )
    
    # Rule Definition
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of rule (room_type, floor, status, custom)",
    )
    rule_field: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Field to evaluate",
    )
    rule_operator: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Comparison operator (equals, in, contains, etc.)",
    )
    rule_value: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Value to compare against",
    )
    
    # Rule Priority and Logic
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Rule evaluation priority",
    )
    is_inclusion: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is an inclusion or exclusion rule",
    )
    
    # Rule Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether rule is currently active",
    )
    
    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable rule description",
    )
    
    # Relationships
    target: Mapped["AnnouncementTarget"] = relationship(
        "AnnouncementTarget",
        back_populates="rules",
    )
    
    __table_args__ = (
        Index("ix_targeting_rules_target", "target_id"),
        Index("ix_targeting_rules_type", "rule_type"),
        Index("ix_targeting_rules_priority", "priority"),
        CheckConstraint(
            "priority >= 0",
            name="ck_targeting_rules_priority_positive",
        ),
        {"comment": "Individual targeting rules for announcements"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<TargetingRule(id={self.id}, target_id={self.target_id}, "
            f"type={self.rule_type}, field={self.rule_field})>"
        )


class TargetAudienceCache(UUIDMixin, TimestampModel, BaseModel):
    """
    Cached audience calculation results.
    
    Stores pre-calculated recipient lists for performance
    optimization and consistency.
    """
    
    __tablename__ = "announcement_target_audience_cache"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    target_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_targets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated targeting configuration",
    )
    
    # Cached Data
    student_ids: Mapped[List[UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        comment="Calculated list of student UUIDs",
    )
    total_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total number of students in cache",
    )
    
    # Breakdown by Category
    breakdown_by_room: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Student count by room",
    )
    breakdown_by_floor: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Student count by floor",
    )
    
    # Cache Metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When cache was calculated",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When cache expires",
    )
    is_stale: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether cache is stale and needs refresh",
    )
    
    # Cache Version
    cache_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Cache version for invalidation",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    target: Mapped["AnnouncementTarget"] = relationship(
        "AnnouncementTarget",
        lazy="select",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "target_id",
            name="uq_target_audience_cache_announcement_target",
        ),
        Index("ix_target_audience_cache_announcement", "announcement_id"),
        Index("ix_target_audience_cache_expires_at", "expires_at"),
        Index("ix_target_audience_cache_stale", "is_stale"),
        CheckConstraint(
            "total_count >= 0",
            name="ck_target_audience_cache_count_positive",
        ),
        {"comment": "Cached audience calculation results"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<TargetAudienceCache(id={self.id}, announcement_id={self.announcement_id}, "
            f"count={self.total_count}, stale={self.is_stale})>"
        )


class BulkTargetingRule(UUIDMixin, TimestampModel, BaseModel):
    """
    Bulk targeting with multiple rule combinations.
    
    Allows complex targeting scenarios requiring multiple
    rule combinations with AND/OR logic.
    """
    
    __tablename__ = "announcement_bulk_targeting_rules"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the bulk rule",
    )
    
    # Rule Configuration
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Descriptive name for the rule set",
    )
    combine_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="union",
        comment="How to combine rules (union, intersection)",
    )
    
    # Targeting Configurations (array of target IDs)
    target_ids: Mapped[List[UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        comment="List of targeting configuration IDs",
    )
    
    # Global Exclusions
    global_exclude_student_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Students to exclude from final result",
    )
    
    # Results
    final_student_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Final calculated student list",
    )
    final_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Final recipient count",
    )
    
    # Processing Status
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether bulk targeting has been processed",
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When bulk targeting was processed",
    )
    
    # Metadata (renamed from metadata to avoid SQLAlchemy conflict)
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_bulk_targeting_rules_announcement", "announcement_id"),
        Index("ix_bulk_targeting_rules_processed", "is_processed"),
        CheckConstraint(
            "final_count >= 0",
            name="ck_bulk_targeting_rules_count_positive",
        ),
        CheckConstraint(
            "combine_mode IN ('union', 'intersection')",
            name="ck_bulk_targeting_rules_combine_mode",
        ),
        {"comment": "Bulk targeting with multiple rule combinations"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<BulkTargetingRule(id={self.id}, name='{self.rule_name}', "
            f"announcement_id={self.announcement_id}, count={self.final_count})>"
        )