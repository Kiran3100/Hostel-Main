# --- File: C:\Hostel-Main\app\models\notification\notification_template.py ---
"""
Notification template model for reusable message templates.

Supports variable substitution, versioning, and multi-language templates.
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, SoftDeleteMixin
from app.schemas.common.enums import NotificationType

if TYPE_CHECKING:
    from app.models.user.user import User


class NotificationTemplate(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Reusable notification templates with variable substitution.
    
    Supports multi-channel templates with rich content, versioning,
    and performance tracking for optimization.
    """

    __tablename__ = "notification_templates"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Template identification
    template_code = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique template identifier (e.g., 'booking_confirmation')",
    )
    template_name = Column(
        String(255),
        nullable=False,
        comment="Human-readable template name",
    )

    # Template type
    template_type = Column(
        Enum(NotificationType),
        nullable=False,
        index=True,
        comment="Notification channel this template is for",
    )

    # Content with variable support
    subject = Column(
        String(255),
        nullable=True,
        comment="Subject template (for email/push, supports {{variables}})",
    )
    body_template = Column(
        Text,
        nullable=False,
        comment="Body template with {{variable}} placeholders",
    )

    # Variables
    variables = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="List of required template variables",
    )
    optional_variables = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="List of optional template variables",
    )

    # Metadata
    category = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Template category for organization",
    )
    tags = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="Tags for template discovery",
    )

    # Settings
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether template is active and available for use",
    )
    description = Column(
        Text,
        nullable=True,
        comment="Template description and usage notes",
    )

    # Localization
    language = Column(
        String(5),
        nullable=False,
        default="en",
        index=True,
        comment="Template language code (e.g., 'en', 'hi')",
    )

    # Usage statistics
    usage_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times template has been used",
    )
    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When template was last used",
    )

    # Audit
    created_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the template",
    )

    # Relationships
    created_by = relationship(
        "User",
        foreign_keys=[created_by_id],
        backref="created_templates",
    )

    # Versions relationship
    versions = relationship(
        "NotificationTemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="NotificationTemplateVersion.version_number.desc()",
    )

    __table_args__ = (
        Index(
            "ix_templates_type_category_active",
            "template_type",
            "category",
            "is_active",
        ),
        Index(
            "ix_templates_usage",
            "usage_count",
            "last_used_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationTemplate(code={self.template_code}, "
            f"type={self.template_type.value}, active={self.is_active})>"
        )

    def increment_usage(self) -> None:
        """Increment usage count and update last_used_at."""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()


class NotificationTemplateVersion(BaseModel, TimestampMixin):
    """
    Template version history for audit and rollback.
    
    Maintains complete version history of templates with ability
    to compare versions and rollback changes.
    """

    __tablename__ = "notification_template_versions"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Reference to template
    template_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notification_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Version information
    version_number = Column(
        Integer,
        nullable=False,
        comment="Sequential version number",
    )
    version_name = Column(
        String(100),
        nullable=True,
        comment="Optional version name/tag",
    )

    # Snapshot of template content at this version
    subject = Column(String(255), nullable=True)
    body_template = Column(Text, nullable=False)
    variables = Column(ARRAY(String), nullable=False, default=list)
    optional_variables = Column(ARRAY(String), nullable=False, default=list)

    # Version metadata
    change_summary = Column(
        Text,
        nullable=True,
        comment="Summary of changes in this version",
    )
    changed_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    template = relationship(
        "NotificationTemplate",
        back_populates="versions",
    )
    changed_by = relationship(
        "User",
        foreign_keys=[changed_by_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "version_number",
            name="uq_template_version_number",
        ),
        Index(
            "ix_template_versions_template_created",
            "template_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationTemplateVersion(template_id={self.template_id}, "
            f"v{self.version_number})>"
        )