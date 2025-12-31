# app/models/mess/dietary_option.py
"""
Dietary Options SQLAlchemy Models.

Dietary preference management, allergen profiles, and dietary
restriction tracking for hostel mess management.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Numeric,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, SoftDeleteModel
from app.models.base.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.student.student import Student
    from app.models.user.user import User

__all__ = [
    "DietaryOption",
    "StudentDietaryPreference",
    "AllergenProfile",
    "DietaryRestriction",
    "MealCustomization",
]


class DietaryOption(UUIDMixin, TimestampMixin, SoftDeleteModel, BaseModel):
    """
    Hostel-level dietary options configuration.
    
    Defines available dietary preferences and customization
    settings for the mess at hostel level.
    """

    __tablename__ = "dietary_options"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Available dietary options
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
    vegan_menu: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    jain_menu: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    gluten_free_options: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    lactose_free_options: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    halal_options: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    kosher_options: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Customization settings
    allow_meal_customization: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    allow_special_requests: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    advance_notice_required_days: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    max_special_requests_per_month: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Allergen management
    display_allergen_warnings: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    mandatory_allergen_declaration: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    allergen_cross_contamination_warning: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Student preference tracking
    track_student_preferences: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    auto_suggest_menu: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    preference_learning_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Portion control
    allow_portion_selection: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    portion_sizes_available: Mapped[List[str]] = mapped_column(
        ARRAY(String(20)),
        default=["regular"],
        nullable=False,
        comment="small, regular, large, extra_large",
    )

    # Meal timing flexibility
    flexible_meal_timings: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    allow_meal_skipping: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    meal_credit_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Allow credits for skipped meals",
    )

    # Waste management
    track_food_waste: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    portion_optimization_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Special dietary programs
    diet_plan_support: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Support for weight loss, muscle gain, etc.",
    )
    nutritionist_consultation_available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Configuration metadata
    config_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    last_updated_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Additional settings (JSON for extensibility)
    additional_settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="dietary_options",
    )
    updated_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="dietary_option_updates",
    )

    __table_args__ = (
        CheckConstraint(
            "advance_notice_required_days >= 0 AND advance_notice_required_days <= 7",
            name="ck_advance_notice_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<DietaryOption(id={self.id}, hostel_id={self.hostel_id})>"

    @property
    def available_menus(self) -> List[str]:
        """Get list of available menu types."""
        menus = []
        if self.vegetarian_menu:
            menus.append("vegetarian")
        if self.non_vegetarian_menu:
            menus.append("non_vegetarian")
        if self.vegan_menu:
            menus.append("vegan")
        if self.jain_menu:
            menus.append("jain")
        return menus

    @property
    def special_dietary_options(self) -> List[str]:
        """Get list of special dietary options."""
        options = []
        if self.gluten_free_options:
            options.append("gluten_free")
        if self.lactose_free_options:
            options.append("lactose_free")
        if self.halal_options:
            options.append("halal")
        if self.kosher_options:
            options.append("kosher")
        return options


class StudentDietaryPreference(UUIDMixin, TimestampMixin, SoftDeleteModel, BaseModel):
    """
    Individual student dietary preferences.
    
    Stores and tracks student-specific dietary preferences,
    restrictions, and meal customization settings.
    """

    __tablename__ = "student_dietary_preferences"

    student_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Primary dietary preference
    primary_preference: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="vegetarian, non_vegetarian, vegan, jain, pescatarian, etc.",
    )
    
    # Additional dietary flags
    is_vegetarian: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_vegan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_jain: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_halal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_kosher: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Special dietary needs
    is_gluten_free: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_lactose_intolerant: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_diabetic: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_low_sodium: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Taste preferences
    spice_preference: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="mild, medium, spicy, extra_spicy",
    )
    preferred_cuisines: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Food dislikes and allergies
    disliked_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    disliked_ingredients: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Meal timing preferences
    preferred_breakfast_time: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    preferred_lunch_time: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    preferred_dinner_time: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # Portion preferences
    preferred_portion_size: Mapped[str] = mapped_column(
        String(20),
        default="regular",
        nullable=False,
    )

    # Special requirements
    special_requirements: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    medical_dietary_restrictions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Diet plan (if following specific plan)
    on_diet_plan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    diet_plan_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="weight_loss, muscle_gain, maintenance, therapeutic, etc.",
    )
    diet_plan_start_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    diet_plan_end_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    diet_plan_details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Notification preferences
    notify_menu_updates: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_allergen_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_special_menus: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Preference verification
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    verified_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Medical documentation (if required)
    has_medical_certificate: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    medical_certificate_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="dietary_preference",
    )
    allergen_profile: Mapped[Optional["AllergenProfile"]] = relationship(
        "AllergenProfile",
        back_populates="student_preference",
        uselist=False,
        cascade="all, delete-orphan",
    )
    dietary_restrictions: Mapped[List["DietaryRestriction"]] = relationship(
        "DietaryRestriction",
        back_populates="student_preference",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<StudentDietaryPreference(id={self.id}, student_id={self.student_id}, "
            f"preference={self.primary_preference})>"
        )

    @property
    def dietary_tags(self) -> List[str]:
        """Get all applicable dietary tags."""
        tags = [self.primary_preference]
        
        if self.is_gluten_free:
            tags.append("gluten_free")
        if self.is_lactose_intolerant:
            tags.append("lactose_free")
        if self.is_diabetic:
            tags.append("diabetic_friendly")
        if self.is_low_sodium:
            tags.append("low_sodium")
        
        return tags


class AllergenProfile(UUIDMixin, TimestampMixin, BaseModel):
    """
    Student allergen profile and sensitivity tracking.
    
    Comprehensive allergen tracking with severity levels
    and reaction history for student safety.
    """

    __tablename__ = "allergen_profiles"

    student_preference_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("student_dietary_preferences.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Common allergens with severity
    dairy_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="none, mild, moderate, severe, life_threatening",
    )
    nuts_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    peanut_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    soy_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    gluten_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    egg_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    shellfish_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    fish_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    sesame_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    mustard_allergy: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # Other allergens
    other_allergens: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Cross-contamination sensitivity
    cross_contamination_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    requires_separate_preparation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Emergency information
    has_epipen: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # Medical documentation
    allergy_test_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    medical_report_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    doctor_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    doctor_contact: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Reaction history
    past_reactions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="History of allergic reactions",
    )
    last_reaction_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Verification
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    verified_by_medical_staff: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Alert settings
    automatic_alerts_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    alert_threshold: Mapped[str] = mapped_column(
        String(20),
        default="trace",
        nullable=False,
        comment="trace, may_contain, contains",
    )

    # Notes
    additional_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    student_preference: Mapped["StudentDietaryPreference"] = relationship(
        "StudentDietaryPreference",
        back_populates="allergen_profile",
    )

    def __repr__(self) -> str:
        return (
            f"<AllergenProfile(id={self.id}, "
            f"student_pref_id={self.student_preference_id})>"
        )

    @property
    def severe_allergens(self) -> List[str]:
        """Get list of severe and life-threatening allergens."""
        severe = []
        allergen_fields = [
            ("dairy", self.dairy_allergy),
            ("nuts", self.nuts_allergy),
            ("peanut", self.peanut_allergy),
            ("soy", self.soy_allergy),
            ("gluten", self.gluten_allergy),
            ("egg", self.egg_allergy),
            ("shellfish", self.shellfish_allergy),
            ("fish", self.fish_allergy),
            ("sesame", self.sesame_allergy),
            ("mustard", self.mustard_allergy),
        ]
        
        for allergen_name, severity in allergen_fields:
            if severity in ["severe", "life_threatening"]:
                severe.append(allergen_name)
        
        return severe

    @property
    def all_allergens(self) -> List[str]:
        """Get complete list of all allergens."""
        allergens = []
        allergen_fields = [
            ("dairy", self.dairy_allergy),
            ("nuts", self.nuts_allergy),
            ("peanut", self.peanut_allergy),
            ("soy", self.soy_allergy),
            ("gluten", self.gluten_allergy),
            ("egg", self.egg_allergy),
            ("shellfish", self.shellfish_allergy),
            ("fish", self.fish_allergy),
            ("sesame", self.sesame_allergy),
            ("mustard", self.mustard_allergy),
        ]
        
        for allergen_name, severity in allergen_fields:
            if severity and severity != "none":
                allergens.append(allergen_name)
        
        allergens.extend(self.other_allergens)
        return allergens


class DietaryRestriction(UUIDMixin, TimestampMixin, SoftDeleteModel, BaseModel):
    """
    Medical and religious dietary restrictions.
    
    Tracks specific dietary restrictions with reasons,
    documentation, and compliance requirements.
    """

    __tablename__ = "dietary_restrictions"

    student_preference_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("student_dietary_preferences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Restriction details
    restriction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="medical, religious, ethical, personal, cultural",
    )
    restriction_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="mandatory, strict, moderate, preferential",
    )

    # Restricted items
    restricted_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    restricted_ingredients: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    restricted_categories: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Reason and documentation
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    medical_condition: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Medical documentation
    requires_medical_verification: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_medically_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    medical_certificate_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    doctor_prescription: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Duration
    is_permanent: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    start_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Compliance tracking
    compliance_required: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    alert_on_violation: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Alternative suggestions
    alternative_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    student_preference: Mapped["StudentDietaryPreference"] = relationship(
        "StudentDietaryPreference",
        back_populates="dietary_restrictions",
    )

    __table_args__ = (
        Index("ix_restriction_type_severity", "restriction_type", "severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<DietaryRestriction(id={self.id}, name={self.restriction_name}, "
            f"type={self.restriction_type})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if restriction is currently active."""
        if self.is_permanent:
            return True
        
        if self.start_date and self.end_date:
            from datetime import date
            today = date.today()
            return self.start_date <= today <= self.end_date
        
        return True


class MealCustomization(UUIDMixin, TimestampMixin, BaseModel):
    """
    Student meal customization requests.
    
    Tracks individual meal customization requests with
    approval workflow and fulfillment tracking.
    """

    __tablename__ = "meal_customizations"

    student_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Customization details
    meal_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="breakfast, lunch, snacks, dinner",
    )
    customization_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="item_replacement, portion_adjustment, special_preparation, etc.",
    )

    # Request details
    original_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    requested_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    special_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Request metadata
    request_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    meal_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    
    # Reason for customization
    reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="dietary_restriction, allergy, preference, medical, religious",
    )
    reason_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Approval workflow
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
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
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Fulfillment tracking
    is_fulfilled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    fulfilled_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
        comment="pending, approved, rejected, fulfilled, cancelled",
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Cost impact
    additional_cost: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="meal_customizations",
    )

    __table_args__ = (
        Index("ix_customization_student_date", "student_id", "meal_date"),
        Index("ix_customization_status", "status", "meal_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MealCustomization(id={self.id}, student_id={self.student_id}, "
            f"meal_date={self.meal_date}, status={self.status})>"
        )