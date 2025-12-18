# app/models/mess/mess_menu.py
"""
Mess Menu SQLAlchemy Models.

Complete menu management system with meal details, versioning,
publishing, and availability tracking.
"""

from datetime import date, datetime, time
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, SoftDeleteModel
from app.models.base.mixins import AuditMixin, TimestampMixin, UUIDMixin
from app.models.common.enums import MealType

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.mess.meal_item import MealItem
    from app.models.mess.menu_approval import MenuApproval
    from app.models.mess.menu_feedback import MenuFeedback
    from app.models.mess.menu_planning import MenuTemplate
    from app.models.user.user import User

__all__ = [
    "MessMenu",
    "MenuCycle",
    "MenuVersion",
    "MenuPublishing",
    "MenuAvailability",
]


class MessMenu(BaseModel, UUIDMixin, TimestampMixin, AuditMixin, SoftDeleteModel):
    """
    Core mess menu entity for daily menu management.
    
    Manages complete menu information for all meals of the day with
    dietary options, special occasions, and publication tracking.
    
    Relationships:
        - Hostel: Many-to-one (hostel_id)
        - User: Many-to-one for creator (created_by)
        - MenuApproval: One-to-many for approval workflow
        - MenuFeedback: One-to-many for student feedback
        - MenuVersion: One-to-many for version history
    """

    __tablename__ = "mess_menus"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Core menu information
    menu_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Monday, Tuesday, etc.",
    )

    # Meal items (stored as ARRAY for PostgreSQL)
    breakfast_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    lunch_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    snacks_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    dinner_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Meal timings
    breakfast_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    lunch_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    snacks_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    dinner_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )

    # Special menu flags
    is_special_menu: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    special_occasion: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    special_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Dietary options availability
    vegetarian_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    non_vegetarian_available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    vegan_available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    jain_available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Publication and approval
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Notification settings
    send_notification: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notification_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Statistics (denormalized for performance)
    total_items_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    average_rating: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        index=True,
    )
    total_feedback_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Version control
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    
    # Template reference (if created from template)
    template_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("menu_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Additional metadata
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    tags: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="mess_menus",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_menus",
    )
    publisher: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[published_by],
        back_populates="published_menus",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="approved_menus",
    )
    
    feedbacks: Mapped[List["MenuFeedback"]] = relationship(
        "MenuFeedback",
        back_populates="menu",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[List["MenuApproval"]] = relationship(
        "MenuApproval",
        back_populates="menu",
        cascade="all, delete-orphan",
    )
    versions: Mapped[List["MenuVersion"]] = relationship(
        "MenuVersion",
        back_populates="menu",
        cascade="all, delete-orphan",
        order_by="MenuVersion.version_number.desc()",
    )
    availability: Mapped[Optional["MenuAvailability"]] = relationship(
        "MenuAvailability",
        back_populates="menu",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Indexes for performance
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "menu_date",
            name="uq_hostel_menu_date",
        ),
        Index("ix_menu_date_range", "menu_date"),
        Index("ix_menu_published_date", "is_published", "menu_date"),
        Index("ix_menu_hostel_date", "hostel_id", "menu_date"),
        Index("ix_menu_special", "is_special_menu", "menu_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MessMenu(id={self.id}, hostel_id={self.hostel_id}, "
            f"date={self.menu_date}, published={self.is_published})>"
        )

    @property
    def total_items(self) -> int:
        """Calculate total items across all meals."""
        return (
            len(self.breakfast_items or [])
            + len(self.lunch_items or [])
            + len(self.snacks_items or [])
            + len(self.dinner_items or [])
        )

    @property
    def is_complete(self) -> bool:
        """Check if menu has all main meals."""
        return bool(
            self.breakfast_items
            and (self.lunch_items or self.dinner_items)
        )

    @property
    def approval_status(self) -> str:
        """Get approval status label."""
        if self.is_approved:
            return "approved"
        elif self.is_published:
            return "published_without_approval"
        else:
            return "pending"

    def update_statistics(self) -> None:
        """Update denormalized statistics."""
        self.total_items_count = self.total_items


class MenuCycle(BaseModel, UUIDMixin, TimestampMixin):
    """
    Weekly or monthly menu cycles for recurring patterns.
    
    Stores menu patterns that repeat on a regular cycle for
    efficient menu planning and predictability.
    """

    __tablename__ = "menu_cycles"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Cycle information
    cycle_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    cycle_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="weekly, bi_weekly, monthly",
    )
    cycle_duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Cycle dates
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # Cycle configuration
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    auto_create_menus: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Menu pattern (JSON structure)
    menu_pattern: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Day-wise menu structure",
    )

    # Statistics
    times_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    average_rating: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="menu_cycles",
    )

    __table_args__ = (
        Index("ix_cycle_active", "hostel_id", "is_active"),
        Index("ix_cycle_dates", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuCycle(id={self.id}, name={self.cycle_name}, "
            f"type={self.cycle_type})>"
        )


class MenuVersion(BaseModel, UUIDMixin, TimestampMixin):
    """
    Menu version history for tracking changes.
    
    Maintains complete audit trail of menu modifications
    with before/after snapshots.
    """

    __tablename__ = "menu_versions"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Version information
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    version_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="create, update, publish, approve",
    )

    # Change tracking
    changed_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    change_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Version data snapshot (complete menu state)
    menu_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete menu data at this version",
    )

    # Changes made
    changes_summary: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Summary of changes from previous version",
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="versions",
    )
    changed_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="menu_version_changes",
    )

    __table_args__ = (
        UniqueConstraint(
            "menu_id",
            "version_number",
            name="uq_menu_version",
        ),
        Index("ix_version_menu", "menu_id", "version_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuVersion(id={self.id}, menu_id={self.menu_id}, "
            f"version={self.version_number})>"
        )


class MenuPublishing(BaseModel, UUIDMixin, TimestampMixin):
    """
    Menu publishing workflow and distribution tracking.
    
    Manages the publication process including scheduling,
    distribution channels, and delivery confirmation.
    """

    __tablename__ = "menu_publishing"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    # Publishing configuration
    publish_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="immediate, scheduled, recurring",
    )
    scheduled_publish_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Distribution channels
    publish_to_app: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    publish_to_email: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    publish_to_sms: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    publish_to_notice_board: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Publishing status
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Distribution tracking
    total_recipients: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    successful_deliveries: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    failed_deliveries: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Engagement metrics
    total_views: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    unique_viewers: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Distribution details
    distribution_log: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed distribution tracking",
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="publishing",
    )
    publisher: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="published_menu_records",
    )

    __table_args__ = (
        Index("ix_publishing_status", "is_published", "published_at"),
        Index("ix_publishing_scheduled", "scheduled_publish_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuPublishing(id={self.id}, menu_id={self.menu_id}, "
            f"published={self.is_published})>"
        )

    @property
    def delivery_success_rate(self) -> float:
        """Calculate delivery success rate."""
        if self.total_recipients == 0:
            return 0.0
        return (self.successful_deliveries / self.total_recipients) * 100


class MenuAvailability(BaseModel, UUIDMixin, TimestampMixin):
    """
    Real-time menu availability tracking.
    
    Tracks actual availability of menu items throughout the day,
    allowing for dynamic updates when items run out.
    """

    __tablename__ = "menu_availability"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    # Meal-wise availability
    breakfast_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    breakfast_unavailable_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    breakfast_service_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    breakfast_service_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    lunch_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    lunch_unavailable_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    lunch_service_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lunch_service_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    snacks_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    snacks_unavailable_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    snacks_service_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    snacks_service_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    dinner_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    dinner_unavailable_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    dinner_service_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dinner_service_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Overall availability
    is_fully_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    last_updated_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Notifications
    shortage_alert_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Availability notes
    availability_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="availability",
    )
    updated_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="menu_availability_updates",
    )

    def __repr__(self) -> str:
        return (
            f"<MenuAvailability(id={self.id}, menu_id={self.menu_id}, "
            f"fully_available={self.is_fully_available})>"
        )

    def mark_item_unavailable(self, meal_type: str, item_name: str) -> None:
        """Mark specific item as unavailable for a meal."""
        if meal_type == "breakfast":
            if item_name not in self.breakfast_unavailable_items:
                self.breakfast_unavailable_items.append(item_name)
        elif meal_type == "lunch":
            if item_name not in self.lunch_unavailable_items:
                self.lunch_unavailable_items.append(item_name)
        elif meal_type == "snacks":
            if item_name not in self.snacks_unavailable_items:
                self.snacks_unavailable_items.append(item_name)
        elif meal_type == "dinner":
            if item_name not in self.dinner_unavailable_items:
                self.dinner_unavailable_items.append(item_name)
        
        self.update_overall_availability()

    def update_overall_availability(self) -> None:
        """Update overall availability status."""
        self.is_fully_available = all([
            self.breakfast_available,
            self.lunch_available,
            self.snacks_available,
            self.dinner_available,
            len(self.breakfast_unavailable_items) == 0,
            len(self.lunch_unavailable_items) == 0,
            len(self.snacks_unavailable_items) == 0,
            len(self.dinner_unavailable_items) == 0,
        ])


# SQLAlchemy event listeners for automated behavior
@event.listens_for(MessMenu, "before_insert")
@event.listens_for(MessMenu, "before_update")
def update_menu_statistics(mapper, connection, target):
    """Automatically update statistics before save."""
    target.update_statistics()


@event.listens_for(MessMenu, "after_insert")
def create_menu_version_on_create(mapper, connection, target):
    """Create initial version record on menu creation."""
    from sqlalchemy import insert
    
    version_data = {
        "id": uuid4(),
        "menu_id": target.id,
        "version_number": 1,
        "version_type": "create",
        "changed_by": target.created_by,
        "menu_snapshot": {
            "breakfast_items": target.breakfast_items,
            "lunch_items": target.lunch_items,
            "snacks_items": target.snacks_items,
            "dinner_items": target.dinner_items,
            "is_special_menu": target.is_special_menu,
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    connection.execute(
        insert(MenuVersion.__table__).values(version_data)
    )