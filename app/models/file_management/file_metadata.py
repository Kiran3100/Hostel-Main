"""
File Metadata Models

Rich metadata storage, tagging, access control, versioning,
and analytics for comprehensive file organization.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.file_management.file_upload import FileUpload
    from app.models.user.user import User

__all__ = [
    "FileTag",
    "FileAccess",
    "FileVersion",
    "FileAnalytics",
    "FileAccessLog",
    "FileFavorite",
]


class FileTag(BaseModel, TimestampModel, UUIDMixin):
    """
    File tagging system for organization.
    
    Enables flexible categorization and organization of files
    with hierarchical tag support.
    """

    __tablename__ = "file_tags"

    # Tag identification
    tag_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Tag name (normalized)",
    )
    tag_type: Mapped[str] = mapped_column(
        String(50),
        default="user",
        nullable=False,
        comment="Tag type: user, system, auto",
    )

    # Hierarchy
    parent_tag_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("file_tags.id", ondelete="CASCADE"),
        nullable=True,
        comment="Parent tag for hierarchy",
    )

    # Tag metadata
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Tag description",
    )
    color: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Tag color (hex code)",
    )
    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Tag icon identifier",
    )

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of files with this tag",
    )

    # Owner (for user tags)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="User who created tag (if user tag)",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether tag is active",
    )

    # Relationships
    parent: Mapped[Optional["FileTag"]] = relationship(
        "FileTag",
        remote_side="FileTag.id",
        back_populates="children",
    )
    children: Mapped[List["FileTag"]] = relationship(
        "FileTag",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    __table_args__ = (
        Index("idx_file_tag_name_type", "tag_name", "tag_type"),
        Index("idx_file_tag_usage", "usage_count"),
    )

    def __repr__(self) -> str:
        return f"<FileTag(name={self.tag_name}, type={self.tag_type})>"


class FileAccess(BaseModel, TimestampModel, UUIDMixin):
    """
    File access control and permissions.
    
    Manages granular access permissions for files with
    role-based and user-specific controls.
    """

    __tablename__ = "file_access"

    # File reference
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Controlled file",
    )

    # Access control type
    access_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Access type: user, role, group, public",
    )

    # Subject (who has access)
    subject_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Subject type: user, role, hostel, student",
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="Subject identifier",
    )

    # Permissions
    can_view: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="View permission",
    )
    can_download: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Download permission",
    )
    can_edit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Edit permission",
    )
    can_delete: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Delete permission",
    )
    can_share: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Share permission",
    )

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Access expiration timestamp",
    )
    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether access has expired",
    )

    # Grant information
    granted_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who granted access",
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Access grant timestamp",
    )

    # Revocation
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether access was revoked",
    )
    revoked_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who revoked access",
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Revocation timestamp",
    )
    revocation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for revocation",
    )

    # Relationships
    file: Mapped["FileUpload"] = relationship(
        "FileUpload",
        back_populates="access_controls",
    )
    granted_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[granted_by_user_id],
    )
    revoked_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[revoked_by_user_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "file_id",
            "subject_type",
            "subject_id",
            name="uq_file_access_subject",
        ),
        Index("idx_file_access_subject", "subject_type", "subject_id"),
        Index("idx_file_access_expires", "expires_at", "is_expired"),
        Index("idx_file_access_revoked", "is_revoked"),
    )

    def __repr__(self) -> str:
        return f"<FileAccess(file_id={self.file_id}, subject={self.subject_type}:{self.subject_id})>"


class FileVersion(BaseModel, TimestampModel, UUIDMixin):
    """
    File version control and history.
    
    Tracks file versions with complete change history
    and rollback capabilities.
    """

    __tablename__ = "file_versions"

    # File reference
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Versioned file",
    )

    # Version information
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Version number (incremental)",
    )
    version_label: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Version label (e.g., 'v1.0', 'draft', 'final')",
    )

    # Version storage
    storage_key: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
        comment="Storage path/key for this version",
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Version file size",
    )
    checksum: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="Version checksum",
    )

    # Change information
    change_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Change type: upload, edit, replace, restore",
    )
    change_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of changes",
    )
    change_summary: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured change summary",
    )

    # Version creator
    created_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who created this version",
    )

    # Status
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this is the current version",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether version is deleted",
    )

    # Metadata
    version_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Version-specific metadata",
    )

    # Relationships
    file: Mapped["FileUpload"] = relationship(
        "FileUpload",
        back_populates="versions",
    )
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    __table_args__ = (
        UniqueConstraint("file_id", "version_number", name="uq_file_version_number"),
        Index("idx_file_version_current", "file_id", "is_current"),
    )

    def __repr__(self) -> str:
        return f"<FileVersion(file_id={self.file_id}, version={self.version_number})>"


class FileAnalytics(BaseModel, TimestampModel, UUIDMixin):
    """
    File usage analytics and optimization.
    
    Tracks file usage patterns, performance metrics,
    and optimization opportunities.
    """

    __tablename__ = "file_analytics"

    # File reference
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Analyzed file",
    )

    # Access metrics
    total_views: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total view count",
    )
    total_downloads: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total download count",
    )
    unique_viewers: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Unique viewer count",
    )
    unique_downloaders: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Unique downloader count",
    )

    # Time-based metrics
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last view timestamp",
    )
    last_downloaded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last download timestamp",
    )
    first_viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="First view timestamp",
    )

    # Popularity metrics
    popularity_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Calculated popularity score",
    )
    trending_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Trending score (recent activity weighted)",
    )

    # Engagement metrics
    average_view_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Average view duration",
    )
    bounce_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Percentage of quick exits",
    )

    # Performance metrics
    average_load_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Average load time in milliseconds",
    )
    error_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Access error rate",
    )

    # Storage optimization
    storage_efficiency_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Storage efficiency score (0-100)",
    )
    compression_ratio: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Compression ratio if optimized",
    )

    # Recommendations
    optimization_recommendations: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Optimization recommendations",
    )

    # Time periods
    views_today: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Views in last 24 hours",
    )
    views_this_week: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Views in last 7 days",
    )
    views_this_month: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Views in last 30 days",
    )

    # Last calculation
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Last analytics calculation timestamp",
    )

    # Relationships
    file: Mapped["FileUpload"] = relationship(
        "FileUpload",
        back_populates="analytics",
    )

    __table_args__ = (
        Index("idx_file_analytics_popularity", "popularity_score"),
        Index("idx_file_analytics_trending", "trending_score"),
    )

    def __repr__(self) -> str:
        return f"<FileAnalytics(file_id={self.file_id}, views={self.total_views}, downloads={self.total_downloads})>"


class FileAccessLog(BaseModel, TimestampModel, UUIDMixin):
    """
    File access audit log entry.
    
    Comprehensive logging of file access events for
    security, analytics, and compliance.
    """

    __tablename__ = "file_access_logs"

    # File reference
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Accessed file",
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="File storage key at time of access",
    )

    # Access details
    accessed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who accessed (NULL for anonymous/public)",
    )
    access_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Access type: view, download, edit, delete, share",
    )
    access_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Access method: web, api, mobile_app, integration",
    )

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        index=True,
        comment="Client IP address (IPv4/IPv6)",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Client user agent string",
    )
    referrer: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="HTTP referrer",
    )

    # Device information
    device_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Device type: desktop, mobile, tablet",
    )
    browser: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Browser name and version",
    )
    operating_system: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Operating system",
    )

    # Geo-location
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2),
        nullable=True,
        index=True,
        comment="ISO country code",
    )
    country_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country name",
    )
    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City name",
    )
    region: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Region/state",
    )

    # Access timing
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Access timestamp",
    )
    session_duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Session duration (for view events)",
    )

    # Response details
    success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether access was successful",
    )
    status_code: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP status code",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if access failed",
    )

    # Performance
    response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Response time in milliseconds",
    )
    bytes_transferred: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Bytes transferred (for downloads)",
    )

    # Additional context
    access_context: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional access context",
    )

    # Relationships
    file: Mapped["FileUpload"] = relationship(
        "FileUpload",
        back_populates="access_logs",
    )
    accessed_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[accessed_by_user_id],
    )

    __table_args__ = (
        Index("idx_file_access_log_file_time", "file_id", "accessed_at"),
        Index("idx_file_access_log_user_time", "accessed_by_user_id", "accessed_at"),
        Index("idx_file_access_log_type_success", "access_type", "success"),
        Index("idx_file_access_log_ip", "ip_address"),
        Index("idx_file_access_log_country", "country_code"),
    )

    def __repr__(self) -> str:
        return f"<FileAccessLog(file_id={self.file_id}, type={self.access_type}, success={self.success})>"


class FileFavorite(BaseModel, TimestampModel, UUIDMixin):
    """
    User favorite files tracking.
    
    Enables users to mark files as favorites for quick access.
    """

    __tablename__ = "file_favorites"

    # File reference
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Favorited file",
    )

    # User reference
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who favorited",
    )

    # Favorite details
    favorited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Favorite timestamp",
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Personal note about the file",
    )

    # Organization
    folder_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User's favorite folder",
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="User's personal tags",
    )

    # Access tracking
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last access via favorite",
    )
    access_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Access count via favorite",
    )

    # Relationships
    file: Mapped["FileUpload"] = relationship(
        "FileUpload",
        back_populates="favorites",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="favorite_files",
    )

    __table_args__ = (
        UniqueConstraint("file_id", "user_id", name="uq_file_favorite_user"),
        Index("idx_file_favorite_user_time", "user_id", "favorited_at"),
    )

    def __repr__(self) -> str:
        return f"<FileFavorite(file_id={self.file_id}, user_id={self.user_id})>"