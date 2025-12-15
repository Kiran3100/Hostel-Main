# --- File: app/schemas/mess/meal_items.py ---
"""
Meal items, dietary preferences, and nutritional information schemas.

Provides comprehensive schemas for menu item definitions, dietary classifications,
allergen tracking, and nutritional data management.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import Field, field_validator, model_validator
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import DietaryPreference, MealType

__all__ = [
    "MealItems",
    "MenuItem",
    "DietaryOptions",
    "NutritionalInfo",
    "ItemMasterList",
    "ItemCategory",
    "AllergenInfo",
]


class MenuItem(BaseSchema):
    """
    Individual menu item with dietary and allergen information.
    
    Represents a single dish/food item with complete classification
    for dietary preferences and allergen warnings.
    """

    item_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Unique item identifier/code",
    )
    item_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Menu item name",
    )
    item_name_local: Optional[str] = Field(
        None,
        max_length=100,
        description="Item name in local language",
    )
    item_description: Optional[str] = Field(
        None,
        max_length=255,
        description="Brief item description",
    )

    # Category and type
    category: str = Field(
        ...,
        pattern=r"^(main_course|side_dish|bread|rice|dal|curry|dessert|beverage|salad|soup|starter)$",
        description="Item category",
    )
    meal_type: Optional[MealType] = Field(
        None,
        description="Typical meal type for this item",
    )

    # Dietary classification
    is_vegetarian: bool = Field(
        True,
        description="Suitable for vegetarians",
    )
    is_vegan: bool = Field(
        False,
        description="Suitable for vegans (no animal products)",
    )
    is_jain: bool = Field(
        False,
        description="Suitable for Jain diet (no root vegetables, etc.)",
    )
    is_gluten_free: bool = Field(
        False,
        description="Gluten-free item",
    )
    is_lactose_free: bool = Field(
        False,
        description="Lactose-free item",
    )

    # Common allergen flags
    contains_dairy: bool = Field(
        False,
        description="Contains dairy products",
    )
    contains_nuts: bool = Field(
        False,
        description="Contains tree nuts or peanuts",
    )
    contains_soy: bool = Field(
        False,
        description="Contains soy",
    )
    contains_gluten: bool = Field(
        False,
        description="Contains gluten (wheat, barley, rye)",
    )
    contains_eggs: bool = Field(
        False,
        description="Contains eggs",
    )
    contains_shellfish: bool = Field(
        False,
        description="Contains shellfish",
    )

    # Additional properties
    is_spicy: bool = Field(
        False,
        description="Spicy food item",
    )
    spice_level: Optional[int] = Field(
        None,
        ge=0,
        le=5,
        description="Spice level (0-5, 0=mild, 5=very spicy)",
    )
    is_popular: bool = Field(
        False,
        description="Popular/frequently requested item",
    )
    is_seasonal: bool = Field(
        False,
        description="Seasonal availability",
    )
    serving_size: Optional[str] = Field(
        None,
        max_length=50,
        description="Standard serving size description",
    )

    @field_validator("item_name", "item_name_local", "item_description", mode="before")
    @classmethod
    def normalize_text(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_dietary_consistency(self) -> "MenuItem":
        """
        Validate dietary classification consistency.
        
        Ensures logical consistency between dietary flags and allergen flags.
        """
        # Vegan items must be vegetarian
        if self.is_vegan and not self.is_vegetarian:
            raise ValueError("Vegan items must also be vegetarian")
        
        # Vegan items cannot contain dairy or eggs
        if self.is_vegan:
            if self.contains_dairy:
                raise ValueError("Vegan items cannot contain dairy")
            if self.contains_eggs:
                raise ValueError("Vegan items cannot contain eggs")
        
        # Jain items must be vegetarian
        if self.is_jain and not self.is_vegetarian:
            raise ValueError("Jain items must be vegetarian")
        
        # Gluten-free items shouldn't contain gluten
        if self.is_gluten_free and self.contains_gluten:
            raise ValueError(
                "Item marked as gluten-free cannot contain gluten"
            )
        
        # Lactose-free items shouldn't contain dairy
        if self.is_lactose_free and self.contains_dairy:
            raise ValueError(
                "Lactose-free items should not contain dairy"
            )
        
        return self

    @model_validator(mode="after")
    def validate_spice_level(self) -> "MenuItem":
        """Validate spice level consistency."""
        if self.is_spicy and self.spice_level is None:
            # Default to medium spice if marked as spicy
            self.spice_level = 3
        
        if not self.is_spicy and self.spice_level and self.spice_level > 0:
            # If spice level is set, item should be marked as spicy
            self.is_spicy = True
        
        return self


class MealItems(BaseSchema):
    """
    Collection of menu items for a specific meal type.
    
    Groups items by meal with complete item information.
    """

    meal_type: MealType = Field(
        ...,
        description="Type of meal",
    )
    meal_name: Optional[str] = Field(
        None,
        description="Custom meal name (e.g., 'Continental Breakfast')",
    )
    items: List[MenuItem] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of menu items for this meal",
    )
    serving_start_time: Optional[datetime.time] = Field(
        None,
        description="Meal serving start time",
    )
    serving_end_time: Optional[datetime.time] = Field(
        None,
        description="Meal serving end time",
    )

    @field_validator("items", mode="after")
    @classmethod
    def validate_unique_items(cls, v: List[MenuItem]) -> List[MenuItem]:
        """Ensure no duplicate item names in the meal."""
        item_names = [item.item_name.lower() for item in v]
        
        if len(item_names) != len(set(item_names)):
            raise ValueError("Duplicate items found in meal")
        
        return v


class DietaryOptions(BaseSchema):
    """
    Dietary options configuration for hostel mess.
    
    Defines available dietary preferences and customization settings.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )

    # Available dietary options
    vegetarian_menu: bool = Field(
        True,
        description="Vegetarian menu available",
    )
    non_vegetarian_menu: bool = Field(
        False,
        description="Non-vegetarian menu available",
    )
    vegan_menu: bool = Field(
        False,
        description="Vegan menu available",
    )
    jain_menu: bool = Field(
        False,
        description="Jain dietary menu available",
    )
    gluten_free_options: bool = Field(
        False,
        description="Gluten-free options available",
    )
    lactose_free_options: bool = Field(
        False,
        description="Lactose-free options available",
    )

    # Customization settings
    allow_meal_customization: bool = Field(
        False,
        description="Allow students to customize meals",
    )
    allow_special_requests: bool = Field(
        False,
        description="Accept special dietary requests",
    )
    advance_notice_required_days: int = Field(
        default=1,
        ge=0,
        le=7,
        description="Days advance notice required for special requests",
    )

    # Allergen management
    display_allergen_warnings: bool = Field(
        True,
        description="Display allergen information on menus",
    )
    mandatory_allergen_declaration: bool = Field(
        True,
        description="Require allergen declaration for all items",
    )

    # Dietary preference tracking
    track_student_preferences: bool = Field(
        default=True,
        description="Track and remember student dietary preferences",
    )
    auto_suggest_menu: bool = Field(
        default=False,
        description="Auto-suggest menu based on preferences",
    )

    @model_validator(mode="after")
    def validate_menu_availability(self) -> "DietaryOptions":
        """Ensure at least one menu type is available."""
        if not any([
            self.vegetarian_menu,
            self.non_vegetarian_menu,
            self.vegan_menu,
            self.jain_menu,
        ]):
            raise ValueError("At least one menu type must be available")
        
        return self


class AllergenInfo(BaseSchema):
    """
    Detailed allergen information for menu item.
    
    Provides comprehensive allergen tracking with severity levels.
    """

    item_name: str = Field(
        ...,
        description="Menu item name",
    )
    allergen_name: str = Field(
        ...,
        description="Allergen name",
    )
    allergen_type: str = Field(
        ...,
        pattern=r"^(dairy|nuts|soy|gluten|eggs|shellfish|fish|sesame|mustard|celery|other)$",
        description="Allergen category",
    )
    severity: str = Field(
        ...,
        pattern=r"^(trace|contains|may_contain)$",
        description="Allergen presence level",
    )
    details: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional allergen details",
    )


# Pydantic v2: For Decimal fields with max_digits and decimal_places, use Annotated
# This resolves the "Unknown constraint decimal_places" error
DecimalWithPrecision = Annotated[
    Decimal,
    Field(ge=0, le=1000)
]


class NutritionalInfo(BaseSchema):
    """
    Nutritional information for menu item.
    
    Provides macros, micros, and calorie information per serving.
    """

    item_name: str = Field(
        ...,
        description="Menu item name",
    )
    item_id: Optional[str] = Field(
        None,
        description="Item identifier",
    )

    # Serving information
    serving_size: str = Field(
        ...,
        max_length=50,
        description="Serving size description (e.g., '1 cup', '150g')",
    )
    servings_per_container: Optional[int] = Field(
        None,
        ge=1,
        description="Number of servings in container",
    )

    # Calories
    calories: Optional[int] = Field(
        None,
        ge=0,
        le=10000,
        description="Calories per serving",
    )
    calories_from_fat: Optional[int] = Field(
        None,
        ge=0,
        description="Calories from fat",
    )

    # Macronutrients (grams)
    # Pydantic v2: Using Decimal with validation in field_validator instead of max_digits/decimal_places
    protein_g: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1000,
        description="Protein in grams",
    )
    carbohydrates_g: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1000,
        description="Carbohydrates in grams",
    )
    fat_g: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1000,
        description="Total fat in grams",
    )
    saturated_fat_g: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Saturated fat in grams",
    )
    trans_fat_g: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Trans fat in grams",
    )
    fiber_g: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Dietary fiber in grams",
    )

    # Micronutrients
    sodium_mg: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Sodium in milligrams",
    )
    sugar_g: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Total sugars in grams",
    )
    cholesterol_mg: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Cholesterol in milligrams",
    )
    potassium_mg: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Potassium in milligrams",
    )

    # Vitamins and minerals (% daily value)
    vitamin_a_percent: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1000,
        description="Vitamin A % daily value",
    )
    vitamin_c_percent: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1000,
        description="Vitamin C % daily value",
    )
    calcium_percent: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1000,
        description="Calcium % daily value",
    )
    iron_percent: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1000,
        description="Iron % daily value",
    )

    # Additional info
    ingredients: Optional[str] = Field(
        None,
        max_length=1000,
        description="List of ingredients",
    )
    preparation_method: Optional[str] = Field(
        None,
        max_length=500,
        description="Preparation method",
    )

    @field_validator("serving_size", mode="before")
    @classmethod
    def normalize_serving_size(cls, v: str) -> str:
        """Normalize serving size description."""
        return v.strip()

    # Pydantic v2: Apply decimal precision using a validator
    @field_validator(
        "protein_g", "carbohydrates_g", "fat_g", "saturated_fat_g",
        "trans_fat_g", "fiber_g", "sugar_g", "sodium_mg", "cholesterol_mg",
        "potassium_mg", "vitamin_a_percent", "vitamin_c_percent",
        "calcium_percent", "iron_percent",
        mode="after"
    )
    @classmethod
    def round_to_two_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round decimal values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @model_validator(mode="after")
    def validate_nutritional_data(self) -> "NutritionalInfo":
        """Validate nutritional data consistency."""
        # Calories from fat shouldn't exceed total calories
        if self.calories and self.calories_from_fat:
            if self.calories_from_fat > self.calories:
                raise ValueError(
                    "Calories from fat cannot exceed total calories"
                )
        
        # Saturated and trans fat shouldn't exceed total fat
        if self.fat_g:
            total_specific_fats = Decimal("0.00")
            
            if self.saturated_fat_g:
                total_specific_fats += self.saturated_fat_g
            if self.trans_fat_g:
                total_specific_fats += self.trans_fat_g
            
            if total_specific_fats > self.fat_g:
                raise ValueError(
                    "Saturated + trans fat cannot exceed total fat"
                )
        
        return self


class ItemCategory(BaseSchema):
    """
    Category of menu items for organization.
    
    Groups related items for easier menu planning.
    """

    category_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Category identifier",
    )
    category_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Category name",
    )
    category_description: Optional[str] = Field(
        None,
        max_length=255,
        description="Category description",
    )
    items: List[str] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Item names in this category",
    )
    display_order: int = Field(
        default=0,
        ge=0,
        description="Display order for category",
    )
    is_active: bool = Field(
        default=True,
        description="Whether category is active",
    )


class ItemMasterList(BaseSchema):
    """
    Master list of all available menu items.
    
    Central repository of items organized by categories for
    a hostel's menu planning.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    list_name: Optional[str] = Field(
        None,
        description="Master list name/version",
    )
    categories: List[ItemCategory] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Item categories",
    )
    total_items: int = Field(
        default=0,
        ge=0,
        description="Total number of items across all categories",
    )
    last_updated: Optional[datetime] = Field(
        None,
        description="Last update timestamp",
    )

    @model_validator(mode="after")
    def calculate_total_items(self) -> "ItemMasterList":
        """Calculate total items across all categories."""
        total = sum(len(category.items) for category in self.categories)
        self.total_items = total
        return self