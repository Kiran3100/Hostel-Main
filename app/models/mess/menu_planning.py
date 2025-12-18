# app/models/mess/menu_planning.py
"""
Menu Planning SQLAlchemy Models.

Strategic menu planning with templates, weekly/monthly plans,
special occasion menus, and AI-powered suggestions.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, SoftDeleteModel
from app.models.base.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.mess.mess_menu import MessMenu
    from app.models.user.user import User

__all__ = [
    "MenuTemplate",
    "WeeklyMenuPlan",
    "MonthlyMenuPlan",
    "DailyMenuPlan",
    "SpecialOccasionMenu",
    "MenuSuggestion",
    "MenuPlanningRule",
    "SeasonalMenu",
]


class MenuTemplate(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Reusable menu template for recurring patterns.
    
    Stores standardized menu patterns that can be applied
    to multiple dates for efficient planning.
    """

    __tablename__ = "menu_templates"

    hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL means global template",
    )

    # Template identification
    template_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    template_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Template type and category
    template_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="weekly, festival, summer, winter, monsoon, exam_period, vacation, regular",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="budget_friendly, premium, healthy, traditional, fusion",
    )

    # Applicability
    applicable_season: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="spring, summer, monsoon, autumn, winter, all",
    )
    applicable_months: Mapped[List[str]] = mapped_column(
        ARRAY(String(20)),
        default=list,
        nullable=False,
    )
    applicable_days: Mapped[List[str]] = mapped_column(
        ARRAY(String(10)),
        default=list,
        nullable=False,
        comment="Monday, Tuesday, etc. Empty = all days",
    )

    # Menu structure (day-wise)
    daily_menus: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Day identifier -> DailyMenuPlan mapping",
    )

    # Dietary configuration
    vegetarian_menu: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    non_vegetarian_menu: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    vegan_options: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    jain_options: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Cost information
    estimated_daily_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Estimated cost per person per day",
    )
    estimated_weekly_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    cost_category: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="budget, standard, premium",
    )

    # Nutritional targets
    target_daily_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    protein_target_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    carbs_target_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    fat_target_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Template metadata
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Available to all hostels",
    )

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_used_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Performance metrics
    average_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Average rating when template was used",
    )
    total_ratings: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Tags for categorization
    tags: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Validity period
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Notes and instructions
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    preparation_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        back_populates="menu_templates",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_menu_templates",
    )
    weekly_plans: Mapped[List["WeeklyMenuPlan"]] = relationship(
        "WeeklyMenuPlan",
        back_populates="template",
    )

    __table_args__ = (
        Index("ix_template_active_type", "is_active", "template_type"),
        Index("ix_template_season", "applicable_season", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuTemplate(id={self.id}, name={self.template_name}, "
            f"type={self.template_type}, active={self.is_active})>"
        )

    @property
    def success_rate(self) -> float:
        """Calculate template success rate based on ratings."""
        if self.total_ratings == 0:
            return 0.0
        
        if self.average_rating:
            return float(self.average_rating) / 5.0 * 100
        return 0.0


class DailyMenuPlan(BaseModel, UUIDMixin, TimestampMixin):
    """
    Daily menu plan structure.
    
    Defines complete menu for all meals of a single day
    within planning context.
    """

    __tablename__ = "daily_menu_plans"

    # Parent plan reference
    weekly_plan_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("weekly_menu_plans.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    monthly_plan_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("monthly_menu_plans.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Date information
    plan_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # Meal items
    breakfast: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )
    lunch: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )
    snacks: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    dinner: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )

    # Meal timings
    breakfast_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    lunch_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    snacks_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    dinner_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    # Special menu
    is_special: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    special_occasion: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Cost estimates
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Nutritional estimates
    estimated_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    estimated_protein_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    estimated_carbs_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    estimated_fat_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Planning notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    preparation_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Status
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_finalized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Implementation tracking
    menu_created: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_menu_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    weekly_plan: Mapped[Optional["WeeklyMenuPlan"]] = relationship(
        "WeeklyMenuPlan",
        back_populates="daily_plans",
    )
    monthly_plan: Mapped[Optional["MonthlyMenuPlan"]] = relationship(
        "MonthlyMenuPlan",
        back_populates="daily_plans",
    )
    created_menu: Mapped[Optional["MessMenu"]] = relationship(
        "MessMenu",
        back_populates="planning_source",
    )

    __table_args__ = (
        Index("ix_daily_plan_date", "plan_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<DailyMenuPlan(id={self.id}, date={self.plan_date}, "
            f"special={self.is_special})>"
        )

    @property
    def total_items_count(self) -> int:
        """Calculate total items across all meals."""
        return (
            len(self.breakfast)
            + len(self.lunch)
            + len(self.snacks)
            + len(self.dinner)
        )


class WeeklyMenuPlan(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Complete weekly menu plan.
    
    Organizes daily menus for a full week with template
    and approval tracking.
    """

    __tablename__ = "weekly_menu_plans"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Week identification
    week_start_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    week_end_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
    )
    week_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Plan metadata
    plan_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Template reference
    template_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("menu_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_from_template: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Creator
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Cost estimates
    estimated_total_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    estimated_cost_per_person: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Nutritional summary
    average_daily_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Approval and status
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_finalized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    finalized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Implementation tracking
    menus_created: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    menus_created_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Performance tracking
    average_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    total_feedbacks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Additional metadata
    planning_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="weekly_menu_plans",
    )
    template: Mapped[Optional["MenuTemplate"]] = relationship(
        "MenuTemplate",
        back_populates="weekly_plans",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_weekly_plans",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="approved_weekly_plans",
    )
    daily_plans: Mapped[List["DailyMenuPlan"]] = relationship(
        "DailyMenuPlan",
        back_populates="weekly_plan",
        cascade="all, delete-orphan",
        order_by="DailyMenuPlan.plan_date.asc()",
    )

    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "week_start_date",
            name="uq_hostel_week",
        ),
        Index("ix_weekly_plan_year_week", "year", "week_number"),
        CheckConstraint(
            "week_number >= 1 AND week_number <= 53",
            name="ck_week_number_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<WeeklyMenuPlan(id={self.id}, hostel_id={self.hostel_id}, "
            f"week={self.week_number}/{self.year})>"
        )

    @property
    def completion_percentage(self) -> float:
        """Calculate plan completion percentage."""
        if not self.daily_plans:
            return 0.0
        
        total_days = 7
        planned_days = len(self.daily_plans)
        
        return (planned_days / total_days) * 100


class MonthlyMenuPlan(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Comprehensive monthly menu plan.
    
    Organizes weekly and daily plans for entire month with
    special occasion tracking.
    """

    __tablename__ = "monthly_menu_plans"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Month identification
    month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        index=True,
        comment="YYYY-MM format",
    )
    month_name: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Plan metadata
    plan_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Creator
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Budget
    total_budget: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    allocated_budget: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    budget_utilization_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Special occasions count
    special_occasions_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Approval
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Status
    is_finalized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    finalized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Implementation
    total_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    menus_created: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    completion_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    # Performance
    average_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    total_feedbacks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata
    planning_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="monthly_menu_plans",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_monthly_plans",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="approved_monthly_plans",
    )
    daily_plans: Mapped[List["DailyMenuPlan"]] = relationship(
        "DailyMenuPlan",
        back_populates="monthly_plan",
        cascade="all, delete-orphan",
        order_by="DailyMenuPlan.plan_date.asc()",
    )
    special_occasions: Mapped[List["SpecialOccasionMenu"]] = relationship(
        "SpecialOccasionMenu",
        back_populates="monthly_plan",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "month",
            name="uq_hostel_month",
        ),
        Index("ix_monthly_plan_year_month", "year", "month"),
    )

    def __repr__(self) -> str:
        return (
            f"<MonthlyMenuPlan(id={self.id}, hostel_id={self.hostel_id}, "
            f"month={self.month})>"
        )


class SpecialOccasionMenu(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Special occasion menu planning.
    
    Enhanced menus for festivals, celebrations, and special events
    with extended item lists and budget allocation.
    """

    __tablename__ = "special_occasion_menus"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    monthly_plan_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("monthly_menu_plans.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Occasion details
    occasion_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    occasion_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    occasion_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="festival, holiday, celebration, cultural_event, sports_event, founder_day, other",
    )
    occasion_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Enhanced menu
    breakfast: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )
    lunch: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )
    snacks: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    dinner: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )

    # Special items and extras
    special_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
        comment="Extra special delicacies",
    )
    desserts: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    beverages: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Budget
    budget: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    estimated_cost_per_person: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    expected_attendees: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Execution details
    decoration_theme: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    serving_style: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="buffet, table_service, plated, family_style",
    )
    special_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Notifications
    send_advance_notification: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notification_days_before: Mapped[int] = mapped_column(
        Integer,
        default=3,
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

    # Approval
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Implementation
    menu_created: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_menu_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Created by
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="special_occasion_menus",
    )
    monthly_plan: Mapped[Optional["MonthlyMenuPlan"]] = relationship(
        "MonthlyMenuPlan",
        back_populates="special_occasions",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_special_menus",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="approved_special_menus",
    )
    created_menu: Mapped[Optional["MessMenu"]] = relationship(
        "MessMenu",
        back_populates="special_occasion_source",
    )

    __table_args__ = (
        Index("ix_special_occasion_date", "occasion_date"),
        CheckConstraint(
            "notification_days_before >= 0 AND notification_days_before <= 30",
            name="ck_notification_days_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SpecialOccasionMenu(id={self.id}, occasion={self.occasion_name}, "
            f"date={self.occasion_date})>"
        )


class MenuSuggestion(BaseModel, UUIDMixin, TimestampMixin):
    """
    AI/system generated menu suggestions.
    
    Intelligent menu recommendations based on various factors
    including past ratings, seasonality, and nutrition.
    """

    __tablename__ = "menu_suggestions"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suggestion_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Suggested items
    suggested_breakfast: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )
    suggested_lunch: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )
    suggested_snacks: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    suggested_dinner: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )

    # Alternative suggestions
    alternative_breakfast: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    alternative_lunch: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    alternative_dinner: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Suggestion rationale
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    based_on: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
        comment="Factors: past_ratings, season, budget, nutrition, variety, etc.",
    )

    # Scoring
    variety_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        comment="0-10 scale",
    )
    nutrition_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        comment="0-10 scale",
    )
    cost_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        comment="0-10 scale",
    )
    popularity_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        comment="Based on past ratings, 0-10",
    )
    overall_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        comment="Weighted average, 0-10",
    )

    # Additional context
    seasonal_items_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    estimated_cost_per_person: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    estimated_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Nutritional balance
    protein_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    carbs_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    fat_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Suggestion metadata
    algorithm_version: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    confidence_level: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Confidence percentage 0-100",
    )

    # User interaction
    is_accepted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    accepted_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    is_dismissed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    dismissal_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Implementation tracking
    menu_created: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_menu_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="menu_suggestions",
    )
    accepted_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="accepted_menu_suggestions",
    )
    created_menu: Mapped[Optional["MessMenu"]] = relationship(
        "MessMenu",
        back_populates="suggestion_source",
    )

    __table_args__ = (
        CheckConstraint(
            "variety_score >= 0 AND variety_score <= 10",
            name="ck_variety_score_range",
        ),
        CheckConstraint(
            "nutrition_score >= 0 AND nutrition_score <= 10",
            name="ck_nutrition_score_range",
        ),
        CheckConstraint(
            "cost_score >= 0 AND cost_score <= 10",
            name="ck_cost_score_range",
        ),
        CheckConstraint(
            "popularity_score >= 0 AND popularity_score <= 10",
            name="ck_popularity_score_range",
        ),
        CheckConstraint(
            "overall_score >= 0 AND overall_score <= 10",
            name="ck_overall_score_range",
        ),
        Index("ix_suggestion_score", "overall_score", "suggestion_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuSuggestion(id={self.id}, hostel_id={self.hostel_id}, "
            f"date={self.suggestion_date}, score={self.overall_score})>"
        )

    @property
    def recommendation_strength(self) -> str:
        """Get recommendation strength label."""
        score = float(self.overall_score)

        if score >= 9:
            return "highly_recommended"
        elif score >= 7:
            return "recommended"
        elif score >= 5:
            return "moderate"
        else:
            return "consider_alternatives"


class MenuPlanningRule(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Menu planning rules and constraints.
    
    Defines business rules for automated menu planning
    including variety, nutrition, and budget constraints.
    """

    __tablename__ = "menu_planning_rules"

    hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL means global rule",
    )

    # Rule identification
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="variety, nutrition, budget, allergen, dietary, seasonal",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Rule configuration (JSON)
    rule_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    # Variety rules
    min_days_between_repeat: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum days before repeating same item",
    )
    max_repeats_per_week: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    avoid_consecutive_repeats: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Budget constraints
    max_cost_per_person_per_day: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    max_cost_per_meal: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Nutritional constraints
    min_daily_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    max_daily_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    min_protein_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Priority
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Higher = more important",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Applicability
    applies_to_templates: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    applies_to_suggestions: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Created by
    created_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        back_populates="menu_planning_rules",
    )

    __table_args__ = (
        Index("ix_planning_rule_active", "is_active", "rule_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuPlanningRule(id={self.id}, name={self.rule_name}, "
            f"type={self.rule_type}, active={self.is_active})>"
        )


class SeasonalMenu(BaseModel, UUIDMixin, TimestampMixin):
    """
    Seasonal menu configurations.
    
    Manages season-specific menu items and preferences
    for different times of the year.
    """

    __tablename__ = "seasonal_menus"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Season information
    season: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="spring, summer, monsoon, autumn, winter",
    )
    season_start_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    season_end_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Seasonal items
    recommended_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    avoid_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Seasonal preferences
    preferred_cuisines: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    preferred_cooking_methods: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Nutritional adjustments
    calorie_adjustment_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="Percentage increase/decrease in calories",
    )

    # Cost considerations
    budget_adjustment_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    # Menu characteristics
    characteristics: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Seasonal menu characteristics",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="seasonal_menus",
    )

    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "season",
            name="uq_hostel_season",
        ),
        CheckConstraint(
            "season_start_month >= 1 AND season_start_month <= 12",
            name="ck_start_month_range",
        ),
        CheckConstraint(
            "season_end_month >= 1 AND season_end_month <= 12",
            name="ck_end_month_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SeasonalMenu(id={self.id}, hostel_id={self.hostel_id}, "
            f"season={self.season})>"
        )