# app/models/mess/nutritional_info.py
"""
Nutritional Information SQLAlchemy Models.

Comprehensive nutritional data management for menu items with
macros, micros, vitamins, and dietary value tracking.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.mess.meal_item import MealItem

__all__ = [
    "NutritionalInfo",
    "NutrientProfile",
    "DietaryValue",
    "NutritionalReport",
]


class NutritionalInfo(BaseModel, UUIDMixin, TimestampMixin):
    """
    Detailed nutritional information for menu items.
    
    Provides comprehensive nutritional data including macros,
    micros, vitamins, and minerals per serving.
    """

    __tablename__ = "nutritional_info"

    meal_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("meal_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Serving information
    serving_size: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="1 cup, 150g, 1 piece, etc.",
    )
    serving_size_grams: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    servings_per_container: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Calories
    calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Calories per serving",
    )
    calories_from_fat: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    calories_from_protein: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    calories_from_carbs: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Macronutrients (in grams)
    protein_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    carbohydrates_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    total_fat_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    saturated_fat_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    trans_fat_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    monounsaturated_fat_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    polyunsaturated_fat_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Carbohydrate details
    dietary_fiber_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    soluble_fiber_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    insoluble_fiber_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    total_sugars_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    added_sugars_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    sugar_alcohols_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Minerals (in milligrams unless specified)
    sodium_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    potassium_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    cholesterol_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    calcium_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    iron_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    magnesium_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    phosphorus_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    zinc_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Vitamins (% daily value)
    vitamin_a_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    vitamin_c_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    vitamin_d_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    vitamin_e_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    vitamin_k_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    thiamin_b1_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    riboflavin_b2_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    niacin_b3_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    vitamin_b6_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    folate_b9_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    vitamin_b12_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    # Additional nutrients
    water_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    caffeine_mg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    alcohol_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Ingredient list
    ingredients: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    ingredient_statement: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Preparation impact
    preparation_method: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    cooking_losses_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Nutrient loss during cooking",
    )

    # Data source and verification
    data_source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="USDA, Lab Analysis, Manufacturer, Estimated",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    verified_by: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_analyzed_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Glycemic information
    glycemic_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="GI value 0-100",
    )
    glycemic_load: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    # Health scores
    nutrition_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Overall nutrition score 0-100",
    )
    health_score: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="excellent, good, average, poor",
    )

    # Additional metadata (for extensibility)
    additional_nutrients: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Any additional nutrient data",
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    meal_item: Mapped["MealItem"] = relationship(
        "MealItem",
        back_populates="nutritional_info",
    )
    nutrient_profile: Mapped[Optional["NutrientProfile"]] = relationship(
        "NutrientProfile",
        back_populates="nutritional_info",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "calories_from_fat IS NULL OR calories_from_fat <= calories",
            name="ck_calories_from_fat",
        ),
        CheckConstraint(
            "glycemic_index IS NULL OR (glycemic_index >= 0 AND glycemic_index <= 100)",
            name="ck_glycemic_index_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NutritionalInfo(id={self.id}, meal_item_id={self.meal_item_id}, "
            f"calories={self.calories})>"
        )

    @property
    def macronutrient_ratio(self) -> Optional[dict]:
        """Calculate macronutrient ratio (protein:carbs:fat)."""
        if not all([self.protein_g, self.carbohydrates_g, self.total_fat_g]):
            return None
        
        total = float(self.protein_g + self.carbohydrates_g + self.total_fat_g)
        
        if total == 0:
            return None
        
        return {
            "protein_percent": round((float(self.protein_g) / total) * 100, 1),
            "carbs_percent": round((float(self.carbohydrates_g) / total) * 100, 1),
            "fat_percent": round((float(self.total_fat_g) / total) * 100, 1),
        }

    @property
    def is_high_protein(self) -> bool:
        """Check if item is high in protein (>20g per serving)."""
        return bool(self.protein_g and self.protein_g >= 20)

    @property
    def is_low_carb(self) -> bool:
        """Check if item is low in carbs (<10g per serving)."""
        return bool(self.carbohydrates_g and self.carbohydrates_g < 10)

    @property
    def is_low_fat(self) -> bool:
        """Check if item is low in fat (<3g per serving)."""
        return bool(self.total_fat_g and self.total_fat_g < 3)

    @property
    def is_low_sodium(self) -> bool:
        """Check if item is low in sodium (<140mg per serving)."""
        return bool(self.sodium_mg and self.sodium_mg < 140)

    @property
    def is_high_fiber(self) -> bool:
        """Check if item is high in fiber (>5g per serving)."""
        return bool(self.dietary_fiber_g and self.dietary_fiber_g >= 5)


class NutrientProfile(BaseModel, UUIDMixin, TimestampMixin):
    """
    Comprehensive nutrient profile with daily value percentages.
    
    Calculates and stores complete nutrient profile based on
    recommended daily allowances for different demographics.
    """

    __tablename__ = "nutrient_profiles"

    nutritional_info_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("nutritional_info.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Target demographic for RDA calculation
    target_age_group: Mapped[str] = mapped_column(
        String(30),
        default="adult",
        nullable=False,
        comment="child, teen, adult, senior",
    )
    target_gender: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="male, female, all",
    )
    activity_level: Mapped[str] = mapped_column(
        String(20),
        default="moderate",
        nullable=False,
        comment="sedentary, light, moderate, active, very_active",
    )

    # Daily value percentages (calculated)
    protein_dv_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    carbs_dv_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    fat_dv_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    fiber_dv_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    sodium_dv_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    calcium_dv_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    iron_dv_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    potassium_dv_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    # Nutrient density scores
    protein_density_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Protein per 100 calories",
    )
    fiber_density_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Fiber per 100 calories",
    )
    micronutrient_density_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Overall micronutrient density",
    )

    # Health indicators
    is_nutrient_dense: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_calorie_dense: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_balanced: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Dietary fit scores
    weight_loss_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Suitability for weight loss 0-100",
    )
    muscle_gain_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Suitability for muscle gain 0-100",
    )
    heart_health_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Heart health score 0-100",
    )
    diabetic_friendly_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Diabetic suitability 0-100",
    )

    # Overall nutrition grade
    nutrition_grade: Mapped[Optional[str]] = mapped_column(
        String(5),
        nullable=True,
        comment="A+, A, B+, B, C+, C, D, F",
    )

    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    rda_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="RDA standard version used",
    )

    # Relationships
    nutritional_info: Mapped["NutritionalInfo"] = relationship(
        "NutritionalInfo",
        back_populates="nutrient_profile",
    )

    def __repr__(self) -> str:
        return (
            f"<NutrientProfile(id={self.id}, "
            f"nutritional_info_id={self.nutritional_info_id}, "
            f"grade={self.nutrition_grade})>"
        )


class DietaryValue(BaseModel, UUIDMixin, TimestampMixin):
    """
    Dietary value tracking for specific diets.
    
    Tracks suitability and compliance of menu items for
    various dietary patterns and health goals.
    """

    __tablename__ = "dietary_values"

    meal_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("meal_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Diet type
    diet_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="keto, paleo, mediterranean, dash, low_carb, etc.",
    )

    # Compliance and suitability
    is_compliant: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    compliance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Compliance score 0-100",
    )
    suitability_rating: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="excellent, good, moderate, poor, not_suitable",
    )

    # Specific diet metrics
    net_carbs_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="For keto/low-carb diets",
    )
    protein_to_carb_ratio: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    omega3_to_omega6_ratio: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="For anti-inflammatory diets",
    )

    # Diet-specific scores
    ketogenic_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    paleo_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    mediterranean_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    dash_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Warnings and notes
    warnings: Mapped[Optional[list]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )
    recommendations: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    evaluation_criteria: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "meal_item_id",
            "diet_type",
            name="uq_dietary_value",
        ),
        Index("ix_dietary_value_compliant", "diet_type", "is_compliant"),
    )

    def __repr__(self) -> str:
        return (
            f"<DietaryValue(id={self.id}, meal_item_id={self.meal_item_id}, "
            f"diet_type={self.diet_type}, compliant={self.is_compliant})>"
        )


class NutritionalReport(BaseModel, UUIDMixin, TimestampMixin):
    """
    Aggregated nutritional reports for menus.
    
    Generates and stores comprehensive nutritional analysis
    for complete daily/weekly menus.
    """

    __tablename__ = "nutritional_reports"

    # Report scope
    report_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="daily_menu, weekly_menu, monthly_menu, custom",
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Date range
    start_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    end_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
    )

    # Aggregated nutritional data
    total_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    average_daily_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    total_protein_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    total_carbs_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    total_fat_g: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Macro ratio
    protein_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    carbs_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    fat_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Balance indicators
    is_balanced: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    balance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Nutritional balance score 0-100",
    )

    # Variety metrics
    unique_items_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    food_group_diversity_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Compliance checks
    meets_rda_requirements: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    deficient_nutrients: Mapped[list] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    excessive_nutrients: Mapped[list] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )

    # Health scores
    overall_health_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    nutrition_quality_index: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Detailed breakdown (JSON)
    daily_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Day-by-day nutritional breakdown",
    )
    meal_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Meal-by-meal breakdown",
    )
    nutrient_summary: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete nutrient summary",
    )

    # Recommendations
    recommendations: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    improvement_areas: Mapped[list] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Report metadata
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    generated_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Report status
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_nutritional_report_dates", "hostel_id", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<NutritionalReport(id={self.id}, type={self.report_type}, "
            f"hostel_id={self.hostel_id}, dates={self.start_date} to {self.end_date})>"
        )