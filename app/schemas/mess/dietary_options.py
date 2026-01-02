# --- File: app/schemas/mess/dietary_options.py ---
"""
Dietary options and student preferences schemas.

Provides schemas for hostel dietary configurations, student preferences,
and meal customization requests.
"""

from datetime import datetime
from typing import List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema

__all__ = [
    "DietaryOption",
    "DietaryOptionUpdate",
    "StudentDietaryPreference",
    "StudentPreferenceUpdate",
    "MealCustomization",
    "CustomizationCreate",
]


class DietaryOption(BaseSchema):
    """
    Hostel dietary options configuration.
    
    Defines available dietary preferences and customization settings for a hostel.
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
    def validate_menu_availability(self) -> "DietaryOption":
        """Ensure at least one menu type is available."""
        if not any([
            self.vegetarian_menu,
            self.non_vegetarian_menu,
            self.vegan_menu,
            self.jain_menu,
        ]):
            raise ValueError("At least one menu type must be available")
        
        return self


class DietaryOptionUpdate(BaseUpdateSchema):
    """
    Update hostel dietary options configuration.
    
    All fields are optional for partial updates.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    vegetarian_menu: Union[bool, None] = None
    non_vegetarian_menu: Union[bool, None] = None
    vegan_menu: Union[bool, None] = None
    jain_menu: Union[bool, None] = None
    gluten_free_options: Union[bool, None] = None
    lactose_free_options: Union[bool, None] = None
    allow_meal_customization: Union[bool, None] = None
    allow_special_requests: Union[bool, None] = None
    advance_notice_required_days: Union[int, None] = Field(
        None,
        ge=0,
        le=7,
    )
    display_allergen_warnings: Union[bool, None] = None
    mandatory_allergen_declaration: Union[bool, None] = None
    track_student_preferences: Union[bool, None] = None
    auto_suggest_menu: Union[bool, None] = None


class StudentDietaryPreference(BaseSchema):
    """
    Student dietary preferences and restrictions.
    
    Stores individual student's dietary choices and allergen information.
    """

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    
    # Primary dietary preference
    dietary_type: str = Field(
        ...,
        pattern=r"^(vegetarian|non_vegetarian|vegan|jain|eggetarian)$",
        description="Primary dietary preference",
    )
    
    # Dietary restrictions
    is_gluten_free: bool = Field(
        default=False,
        description="Requires gluten-free diet",
    )
    is_lactose_free: bool = Field(
        default=False,
        description="Requires lactose-free diet",
    )
    is_nut_free: bool = Field(
        default=False,
        description="Nut allergy or restriction",
    )
    
    # Allergens
    allergens: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="List of allergens to avoid",
    )
    
    # Food preferences
    preferred_cuisines: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Preferred cuisine types",
    )
    disliked_items: List[str] = Field(
        default_factory=list,
        max_length=30,
        description="Items student doesn't prefer",
    )
    
    # Meal timing preferences
    prefer_early_breakfast: bool = Field(
        default=False,
        description="Prefers early breakfast timing",
    )
    prefer_late_dinner: bool = Field(
        default=False,
        description="Prefers late dinner timing",
    )
    
    # Special notes
    special_requirements: Union[str, None] = Field(
        None,
        max_length=500,
        description="Special dietary requirements or medical conditions",
    )
    
    # Metadata
    last_updated: datetime = Field(
        ...,
        description="Last update timestamp",
    )

    @field_validator("allergens", "preferred_cuisines", "disliked_items", mode="after")
    @classmethod
    def normalize_lists(cls, v: List[str]) -> List[str]:
        """Normalize and deduplicate list items."""
        if not v:
            return v
        
        normalized = []
        seen = set()
        
        for item in v:
            item = item.strip().lower()
            if item and item not in seen:
                seen.add(item)
                normalized.append(item)
        
        return normalized


class StudentPreferenceUpdate(BaseUpdateSchema):
    """
    Update student dietary preferences.
    
    All fields are optional for partial updates.
    """

    dietary_type: Union[str, None] = Field(
        None,
        pattern=r"^(vegetarian|non_vegetarian|vegan|jain|eggetarian)$",
    )
    is_gluten_free: Union[bool, None] = None
    is_lactose_free: Union[bool, None] = None
    is_nut_free: Union[bool, None] = None
    allergens: Union[List[str], None] = Field(None, max_length=20)
    preferred_cuisines: Union[List[str], None] = Field(None, max_length=10)
    disliked_items: Union[List[str], None] = Field(None, max_length=30)
    prefer_early_breakfast: Union[bool, None] = None
    prefer_late_dinner: Union[bool, None] = None
    special_requirements: Union[str, None] = Field(None, max_length=500)

    @field_validator("allergens", "preferred_cuisines", "disliked_items", mode="after")
    @classmethod
    def normalize_lists(cls, v: Union[List[str], None]) -> Union[List[str], None]:
        """Normalize and deduplicate list items."""
        if v is None:
            return None
        
        normalized = []
        seen = set()
        
        for item in v:
            item = item.strip().lower()
            if item and item not in seen:
                seen.add(item)
                normalized.append(item)
        
        return normalized if normalized else None


class MealCustomization(BaseSchema):
    """
    Meal customization request from student.
    
    Represents a request to customize a specific meal.
    """

    id: UUID = Field(
        ...,
        description="Customization request unique identifier",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    meal_type: str = Field(
        ...,
        pattern=r"^(breakfast|lunch|snacks|dinner)$",
        description="Meal type to customize",
    )
    
    # Customization details
    items_to_add: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Items to add to meal",
    )
    items_to_remove: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Items to remove from meal",
    )
    items_to_substitute: dict = Field(
        default_factory=dict,
        description="Item substitutions {original: replacement}",
    )
    
    # Request details
    customization_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for customization",
    )
    is_medical_requirement: bool = Field(
        default=False,
        description="Whether customization is due to medical requirement",
    )
    
    # Status
    status: str = Field(
        ...,
        pattern=r"^(pending|approved|rejected|fulfilled)$",
        description="Customization request status",
    )
    approved_by: Union[UUID, None] = Field(
        None,
        description="Approver user ID",
    )
    rejection_reason: Union[str, None] = Field(
        None,
        max_length=500,
        description="Reason for rejection (if rejected)",
    )
    
    # Timestamps
    requested_at: datetime = Field(
        ...,
        description="Request timestamp",
    )
    reviewed_at: Union[datetime, None] = Field(
        None,
        description="Review timestamp",
    )


class CustomizationCreate(BaseCreateSchema):
    """
    Create meal customization request.
    
    Student submits customization for a specific meal.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    meal_type: str = Field(
        ...,
        pattern=r"^(breakfast|lunch|snacks|dinner)$",
        description="Meal type to customize",
    )
    items_to_add: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Items to add",
    )
    items_to_remove: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Items to remove",
    )
    items_to_substitute: dict = Field(
        default_factory=dict,
        description="Item substitutions",
    )
    customization_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for customization",
    )
    is_medical_requirement: bool = Field(
        default=False,
        description="Medical requirement flag",
    )

    @model_validator(mode="after")
    def validate_customization(self) -> "CustomizationCreate":
        """Ensure at least one customization is specified."""
        if not any([
            self.items_to_add,
            self.items_to_remove,
            self.items_to_substitute,
        ]):
            raise ValueError(
                "At least one customization (add, remove, or substitute) must be specified"
            )
        
        return self