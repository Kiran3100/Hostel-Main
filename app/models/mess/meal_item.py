# app/models/mess/meal_item.py
"""
Meal Item SQLAlchemy Models.

Individual food items with dietary information, allergen tracking,
nutritional data, and recipe management.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, SoftDeleteModel
from app.models.base.mixins import TimestampMixin, UUIDMixin
from app.models.common.enums import MealType

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.mess.nutritional_info import NutritionalInfo

__all__ = [
    "MealItem",
    "Recipe",
    "IngredientMaster",
    "ItemCategory",
    "ItemAllergen",
    "ItemPopularity",
]


class MealItem(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Individual menu item with comprehensive dietary and allergen information.
    
    Represents a single dish/food item with complete classification
    for dietary preferences, allergen warnings, and preparation details.
    """

    __tablename__ = "meal_items"

    hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL means global/shared item",
    )

    # Item identification
    item_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )
    item_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    item_name_local: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    item_description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Category and type
    category: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="main_course, side_dish, bread, rice, dal, curry, dessert, beverage, salad, soup, starter",
    )
    meal_type: Mapped[Optional[str]] = mapped_column(
        Enum(MealType, name="meal_type_enum"),
        nullable=True,
    )
    cuisine_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Indian, Chinese, Continental, etc.",
    )

    # Dietary classification
    is_vegetarian: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    is_vegan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    is_jain: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_gluten_free: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_lactose_free: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Common allergen flags
    contains_dairy: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    contains_nuts: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    contains_soy: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    contains_gluten: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    contains_eggs: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    contains_shellfish: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Spice and taste
    is_spicy: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    spice_level: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="0-5 scale, 0=mild, 5=very spicy",
    )
    taste_profile: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="sweet, salty, sour, bitter, savory",
    )

    # Item properties
    is_popular: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    is_seasonal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    seasonal_months: Mapped[List[str]] = mapped_column(
        ARRAY(String(20)),
        default=list,
        nullable=False,
        comment="Months when item is available",
    )

    # Serving information
    serving_size: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Standard serving size description",
    )
    serving_unit: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="piece, bowl, plate, cup, etc.",
    )
    portion_weight_grams: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Cost information
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Estimated cost per serving",
    )
    cost_category: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="low, medium, high, premium",
    )

    # Preparation details
    preparation_time_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    cooking_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="fried, baked, steamed, grilled, etc.",
    )
    temperature_serving: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="hot, cold, room_temperature",
    )

    # Availability and status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    availability_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Media
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    images: Mapped[List[str]] = mapped_column(
        ARRAY(String(500)),
        default=list,
        nullable=False,
    )

    # Statistics (denormalized)
    times_served: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    average_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    total_ratings: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    popularity_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Calculated popularity score 0-100",
    )

    # Tags for search and categorization
    tags: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Additional metadata
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    special_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        back_populates="meal_items",
    )
    nutritional_info: Mapped[Optional["NutritionalInfo"]] = relationship(
        "NutritionalInfo",
        back_populates="meal_item",
        uselist=False,
        cascade="all, delete-orphan",
    )
    allergens: Mapped[List["ItemAllergen"]] = relationship(
        "ItemAllergen",
        back_populates="meal_item",
        cascade="all, delete-orphan",
    )
    recipes: Mapped[List["Recipe"]] = relationship(
        "Recipe",
        back_populates="meal_item",
        cascade="all, delete-orphan",
    )
    popularity_data: Mapped[Optional["ItemPopularity"]] = relationship(
        "ItemPopularity",
        back_populates="meal_item",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "spice_level IS NULL OR (spice_level >= 0 AND spice_level <= 5)",
            name="ck_spice_level_range",
        ),
        CheckConstraint(
            "NOT (is_vegan = true AND is_vegetarian = false)",
            name="ck_vegan_must_be_vegetarian",
        ),
        CheckConstraint(
            "NOT (is_gluten_free = true AND contains_gluten = true)",
            name="ck_gluten_free_consistency",
        ),
        Index("ix_meal_item_hostel_active", "hostel_id", "is_active"),
        Index("ix_meal_item_category", "category", "is_active"),
        Index("ix_meal_item_dietary", "is_vegetarian", "is_vegan", "is_jain"),
        Index("ix_meal_item_search", "item_name"),  # For text search
    )

    def __repr__(self) -> str:
        return f"<MealItem(id={self.id}, name={self.item_name}, category={self.category})>"

    @property
    def allergen_list(self) -> List[str]:
        """Get list of allergens present in item."""
        allergens = []
        if self.contains_dairy:
            allergens.append("dairy")
        if self.contains_nuts:
            allergens.append("nuts")
        if self.contains_soy:
            allergens.append("soy")
        if self.contains_gluten:
            allergens.append("gluten")
        if self.contains_eggs:
            allergens.append("eggs")
        if self.contains_shellfish:
            allergens.append("shellfish")
        return allergens

    @property
    def dietary_flags(self) -> List[str]:
        """Get list of dietary classifications."""
        flags = []
        if self.is_vegetarian:
            flags.append("vegetarian")
        if self.is_vegan:
            flags.append("vegan")
        if self.is_jain:
            flags.append("jain")
        if self.is_gluten_free:
            flags.append("gluten_free")
        if self.is_lactose_free:
            flags.append("lactose_free")
        return flags


class Recipe(BaseModel, UUIDMixin, TimestampMixin):
    """
    Recipe management with ingredients and instructions.
    
    Stores complete recipe information including ingredients,
    quantities, and step-by-step preparation instructions.
    """

    __tablename__ = "recipes"

    meal_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("meal_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Recipe information
    recipe_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    recipe_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Ingredients (structured JSON)
    ingredients: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="List of ingredients with quantities",
    )

    # Preparation instructions
    instructions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    preparation_steps: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured step-by-step instructions",
    )

    # Cooking details
    prep_time_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    cook_time_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    total_time_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Serving information
    serves: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of servings",
    )
    yield_quantity: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Difficulty and skill
    difficulty_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="easy, medium, hard, expert",
    )
    skill_requirements: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Chef notes
    chef_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    tips_and_tricks: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Variations
    variations: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Recipe variations and substitutions",
    )

    # Relationships
    meal_item: Mapped["MealItem"] = relationship(
        "MealItem",
        back_populates="recipes",
    )

    __table_args__ = (
        UniqueConstraint(
            "meal_item_id",
            "recipe_version",
            name="uq_recipe_version",
        ),
    )

    def __repr__(self) -> str:
        return f"<Recipe(id={self.id}, name={self.recipe_name}, version={self.recipe_version})>"


class IngredientMaster(BaseModel, UUIDMixin, TimestampMixin):
    """
    Master ingredient database for standardization.
    
    Central repository of all ingredients used across recipes
    with nutritional information and supplier details.
    """

    __tablename__ = "ingredient_master"

    # Ingredient identification
    ingredient_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )
    ingredient_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    ingredient_name_local: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Category
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="vegetable, grain, spice, dairy, protein, etc.",
    )
    subcategory: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Measurement
    standard_unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="kg, liter, piece, bunch, etc.",
    )
    unit_weight_grams: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Weight in grams for 1 standard unit",
    )

    # Dietary properties
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
    is_organic: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Allergen information
    allergens: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Seasonality
    is_seasonal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    available_months: Mapped[List[str]] = mapped_column(
        ARRAY(String(20)),
        default=list,
        nullable=False,
    )

    # Cost information
    average_cost_per_unit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    cost_currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False,
    )

    # Storage
    storage_requirements: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="refrigerated, frozen, dry, cool_place",
    )
    shelf_life_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Nutritional info (basic)
    calories_per_100g: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    protein_per_100g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    carbs_per_100g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    fat_per_100g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        Index("ix_ingredient_category", "category", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<IngredientMaster(id={self.id}, name={self.ingredient_name})>"


class ItemCategory(BaseModel, UUIDMixin, TimestampMixin):
    """
    Category of menu items for organization.
    
    Hierarchical categorization system for better menu
    organization and filtering.
    """

    __tablename__ = "item_categories"

    # Category information
    category_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )
    category_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    category_description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Hierarchy
    parent_category_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("item_categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    level: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Display
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    icon: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    color: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Relationships
    parent_category: Mapped[Optional["ItemCategory"]] = relationship(
        "ItemCategory",
        remote_side="ItemCategory.id",
        back_populates="subcategories",
    )
    subcategories: Mapped[List["ItemCategory"]] = relationship(
        "ItemCategory",
        back_populates="parent_category",
    )

    def __repr__(self) -> str:
        return f"<ItemCategory(id={self.id}, name={self.category_name})>"


class ItemAllergen(BaseModel, UUIDMixin, TimestampMixin):
    """
    Detailed allergen information for menu items.
    
    Provides comprehensive allergen tracking with severity
    levels and cross-contamination warnings.
    """

    __tablename__ = "item_allergens"

    meal_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("meal_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Allergen details
    allergen_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    allergen_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="dairy, nuts, soy, gluten, eggs, shellfish, fish, sesame, mustard, celery, other",
    )

    # Severity and presence
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="trace, contains, may_contain",
    )
    is_cross_contamination_risk: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Details
    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Which ingredient contains the allergen",
    )

    # Warning
    warning_message: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    meal_item: Mapped["MealItem"] = relationship(
        "MealItem",
        back_populates="allergens",
    )

    __table_args__ = (
        UniqueConstraint(
            "meal_item_id",
            "allergen_type",
            name="uq_item_allergen",
        ),
        Index("ix_allergen_type", "allergen_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<ItemAllergen(id={self.id}, item_id={self.meal_item_id}, "
            f"allergen={self.allergen_type}, severity={self.severity})>"
        )


class ItemPopularity(BaseModel, UUIDMixin, TimestampMixin):
    """
    Item popularity tracking and analytics.
    
    Tracks popularity metrics for menu items to inform
    menu planning and optimization decisions.
    """

    __tablename__ = "item_popularity"

    meal_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("meal_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Serving statistics
    total_times_served: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_served_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Rating statistics
    average_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    total_ratings: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    rating_5_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_4_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_3_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_2_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_1_count: Mapped[int] = mapped_column(Integer, default=0)

    # Feedback statistics
    total_likes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_dislikes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Popularity metrics
    popularity_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=0.0,
        nullable=False,
        comment="Calculated score 0-100",
    )
    demand_index: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Demand prediction index",
    )

    # Trend analysis
    trend_direction: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="rising, stable, declining",
    )
    trend_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    # Monthly statistics
    monthly_stats: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Month-wise statistics",
    )

    # Relationships
    meal_item: Mapped["MealItem"] = relationship(
        "MealItem",
        back_populates="popularity_data",
    )

    def __repr__(self) -> str:
        return (
            f"<ItemPopularity(id={self.id}, item_id={self.meal_item_id}, "
            f"score={self.popularity_score})>"
        )

    def calculate_popularity_score(self) -> None:
        """Calculate overall popularity score."""
        # Weighted scoring algorithm
        rating_score = float(self.average_rating or 0) * 20  # Max 100
        
        if self.total_ratings + self.total_likes + self.total_dislikes > 0:
            feedback_score = (
                (self.total_likes / (self.total_likes + self.total_dislikes + 1))
                * 100
            )
        else:
            feedback_score = 0
        
        frequency_score = min(self.total_times_served * 2, 100)  # Cap at 100
        
        # Weighted average
        self.popularity_score = Decimal(
            str(round((rating_score * 0.5 + feedback_score * 0.3 + frequency_score * 0.2), 2))
        )