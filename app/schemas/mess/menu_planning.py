# --- File: app/schemas/mess/menu_planning.py ---
"""
Menu planning schemas for advance planning and templates.

Provides comprehensive menu planning capabilities including weekly plans,
monthly schedules, special menus, and reusable templates.
"""

from datetime import date as Date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema

__all__ = [
    "MenuPlanRequest",
    "WeeklyPlan",
    "WeeklyPlanCreate",
    "DailyMenuPlan",
    "MonthlyPlan",
    "MonthlyPlanCreate",
    "SpecialMenu",
    "SpecialDayMenu",
    "MenuTemplate",
    "MenuTemplateCreate",
    "MenuTemplateUpdate",
    "MenuSuggestion",
    "SuggestionCriteria",
]


class DailyMenuPlan(BaseSchema):
    """
    Daily menu plan structure.
    
    Defines items for all meals of a single day.
    """

    breakfast: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Breakfast items",
    )
    lunch: List[str] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Lunch items",
    )
    snacks: List[str] = Field(
        default_factory=list,
        max_length=15,
        description="Snacks items",
    )
    dinner: List[str] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Dinner items",
    )
    is_special: bool = Field(
        False,
        description="Special menu indicator",
    )
    special_occasion: Union[str, None] = Field(
        None,
        max_length=255,
        description="Special occasion name",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Planning notes",
    )

    @field_validator("breakfast", "lunch", "snacks", "dinner", mode="after")
    @classmethod
    def validate_menu_items(cls, v: List[str]) -> List[str]:
        """Validate and normalize menu items."""
        normalized = []
        for item in v:
            item = item.strip()
            if item and len(item) >= 2:
                normalized.append(item)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_items = []
        for item in normalized:
            if item.lower() not in seen:
                seen.add(item.lower())
                unique_items.append(item)
        
        return unique_items

    @model_validator(mode="after")
    def validate_special_occasion(self) -> "DailyMenuPlan":
        """Validate special occasion requirements."""
        if self.is_special and not self.special_occasion:
            raise ValueError(
                "special_occasion is required when is_special is True"
            )
        return self


class MenuPlanRequest(BaseCreateSchema):
    """
    Request to create comprehensive menu plan.
    
    Initiates menu planning for a Date range with various
    configuration options.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    
    # Planning period
    start_date: Date = Field(
        ...,
        description="Plan start Date",
    )
    end_date: Date = Field(
        ...,
        description="Plan end Date",
    )
    
    # Template usage
    use_template: bool = Field(
        False,
        description="Use existing template",
    )
    template_id: Union[UUID, None] = Field(
        None,
        description="Template ID to use",
    )
    
    # Variety and preferences
    ensure_variety: bool = Field(
        True,
        description="Ensure item variety across days",
    )
    min_days_between_repeat: int = Field(
        3,
        ge=1,
        le=7,
        description="Minimum days before repeating items",
    )
    avoid_consecutive_repeats: bool = Field(
        True,
        description="Avoid same item on consecutive days",
    )
    
    # Dietary requirements
    vegetarian_days_per_week: int = Field(
        7,
        ge=0,
        le=7,
        description="Days with vegetarian-only menu",
    )
    include_vegan_options: bool = Field(
        False,
        description="Include vegan options",
    )
    include_jain_options: bool = Field(
        False,
        description="Include Jain dietary options",
    )
    
    # Budget constraints
    target_cost_per_day: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Target daily cost per person",
    )
    max_cost_per_day: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Maximum daily cost per person",
    )
    
    # Nutritional goals
    target_calories_per_day: Union[int, None] = Field(
        None,
        ge=1000,
        le=5000,
        description="Target daily calories",
    )
    ensure_balanced_nutrition: bool = Field(
        default=True,
        description="Ensure balanced macros",
    )
    
    # Planning preferences
    prefer_seasonal_items: bool = Field(
        default=True,
        description="Prefer seasonal ingredients",
    )
    include_regional_favorites: bool = Field(
        default=True,
        description="Include regional favorites",
    )

    @field_validator("start_date", mode="after")
    @classmethod
    def validate_start_date(cls, v: Date) -> Date:
        """Validate start Date is not too far in past."""
        today = Date.today()
        
        days_past = (today - v).days
        if days_past > 7:
            raise ValueError(
                "Start Date cannot be more than 7 days in the past"
            )
        
        return v

    @field_validator("target_cost_per_day", "max_cost_per_day", mode="after")
    @classmethod
    def round_cost_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round cost values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @model_validator(mode="after")
    def validate_plan_request(self) -> "MenuPlanRequest":
        """Validate menu plan request consistency."""
        # Validate Date range
        if self.end_date < self.start_date:
            raise ValueError("End Date must be after start Date")
        
        # Limit planning period
        days_span = (self.end_date - self.start_date).days + 1
        if days_span > 90:
            raise ValueError("Planning period cannot exceed 90 days")
        
        # Template validation
        if self.use_template and not self.template_id:
            raise ValueError(
                "template_id is required when use_template is True"
            )
        
        # Cost validation
        if self.target_cost_per_day and self.max_cost_per_day:
            if self.max_cost_per_day < self.target_cost_per_day:
                raise ValueError(
                    "max_cost_per_day must be >= target_cost_per_day"
                )
        
        return self


class WeeklyPlan(BaseCreateSchema):
    """
    Complete weekly menu plan.
    
    Defines menus for all seven days of the week.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    week_start_date: Date = Field(
        ...,
        description="Week start Date (Monday)",
    )
    week_number: int = Field(
        ...,
        ge=1,
        le=53,
        description="Week number in year",
    )
    year: int = Field(
        ...,
        ge=2000,
        description="Year",
    )
    
    # Daily menus
    monday: DailyMenuPlan = Field(
        ...,
        description="Monday menu",
    )
    tuesday: DailyMenuPlan = Field(
        ...,
        description="Tuesday menu",
    )
    wednesday: DailyMenuPlan = Field(
        ...,
        description="Wednesday menu",
    )
    thursday: DailyMenuPlan = Field(
        ...,
        description="Thursday menu",
    )
    friday: DailyMenuPlan = Field(
        ...,
        description="Friday menu",
    )
    saturday: DailyMenuPlan = Field(
        ...,
        description="Saturday menu",
    )
    sunday: DailyMenuPlan = Field(
        ...,
        description="Sunday menu",
    )
    
    # Metadata
    created_by: UUID = Field(
        ...,
        description="Creator user ID",
    )
    plan_name: Union[str, None] = Field(
        None,
        max_length=255,
        description="Plan name/title",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Planning notes",
    )
    estimated_total_cost: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Estimated total cost for the week",
    )

    @field_validator("week_start_date", mode="after")
    @classmethod
    def validate_monday(cls, v: Date) -> Date:
        """Ensure week starts on Monday."""
        if v.weekday() != 0:  # 0 = Monday
            raise ValueError("Week must start on Monday")
        return v

    @field_validator("estimated_total_cost", mode="after")
    @classmethod
    def round_cost(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round cost to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v


class WeeklyPlanCreate(BaseCreateSchema):
    """
    Create weekly menu plan.
    
    Plans menu for entire week (Monday-Sunday).
    """

    hostel_id: UUID = Field(..., description="Hostel unique identifier")
    week_start_date: Date = Field(
        ...,
        description="Week start date (Monday)",
    )
    week_number: int = Field(..., ge=1, le=53)
    year: int = Field(..., ge=2000)
    
    monday: DailyMenuPlan = Field(..., description="Monday menu")
    tuesday: DailyMenuPlan = Field(..., description="Tuesday menu")
    wednesday: DailyMenuPlan = Field(..., description="Wednesday menu")
    thursday: DailyMenuPlan = Field(..., description="Thursday menu")
    friday: DailyMenuPlan = Field(..., description="Friday menu")
    saturday: DailyMenuPlan = Field(..., description="Saturday menu")
    sunday: DailyMenuPlan = Field(..., description="Sunday menu")
    
    created_by: UUID = Field(..., description="Creator user ID")
    plan_name: Union[str, None] = Field(None, max_length=255)
    notes: Union[str, None] = Field(None, max_length=1000)

    @field_validator("week_start_date", mode="after")
    @classmethod
    def validate_monday(cls, v: Date) -> Date:
        """Ensure week starts on Monday."""
        if v.weekday() != 0:
            raise ValueError("Week must start on Monday")
        return v


class SpecialDayMenu(BaseSchema):
    """
    Special day menu in monthly plan.
    
    Associates special occasion with specific Date and menu.
    """

    menu_date: Date = Field(
        ...,
        description="Special day Date",
    )
    occasion: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Occasion name",
    )
    occasion_type: str = Field(
        ...,
        pattern=r"^(festival|holiday|celebration|event|birthday|other)$",
        description="Occasion type",
    )
    menu: DailyMenuPlan = Field(
        ...,
        description="Special menu for the day",
    )
    budget: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Special budget allocation",
    )
    expected_guests: Union[int, None] = Field(
        None,
        ge=0,
        description="Expected number of guests",
    )

    @field_validator("budget", mode="after")
    @classmethod
    def round_budget(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round budget to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v


class MonthlyPlan(BaseCreateSchema):
    """
    Comprehensive monthly menu plan.
    
    Organizes weekly plans and special occasions for entire month.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format",
    )
    month_name: str = Field(
        ...,
        description="Month name",
    )
    year: int = Field(
        ...,
        ge=2000,
        description="Year",
    )
    
    # Weekly plans
    weeks: List[WeeklyPlan] = Field(
        ...,
        min_length=4,
        max_length=5,
        description="Weekly menu plans",
    )
    
    # Special days
    special_days: List[SpecialDayMenu] = Field(
        default_factory=list,
        max_length=31,
        description="Special occasion menus",
    )
    
    # Monthly summary
    total_budget: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Total monthly budget",
    )
    created_by: UUID = Field(
        ...,
        description="Creator user ID",
    )
    approved_by: Union[UUID, None] = Field(
        None,
        description="Approver user ID",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=2000,
        description="Monthly planning notes",
    )

    @field_validator("total_budget", mode="after")
    @classmethod
    def round_budget(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round budget to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @model_validator(mode="after")
    def validate_special_days(self) -> "MonthlyPlan":
        """Ensure special days are unique and within month."""
        if self.special_days:
            dates = [day.menu_date for day in self.special_days]
            
            # Check for duplicates
            if len(dates) != len(set(dates)):
                raise ValueError("Duplicate special day dates found")
        
        return self


class MonthlyPlanCreate(BaseCreateSchema):
    """
    Create monthly menu plan.
    
    Comprehensive planning for entire month.
    """

    hostel_id: UUID = Field(..., description="Hostel unique identifier")
    month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format",
    )
    month_name: str = Field(..., description="Month name")
    year: int = Field(..., ge=2000)
    
    weeks: List[WeeklyPlan] = Field(
        ...,
        min_length=4,
        max_length=5,
        description="Weekly plans",
    )
    special_days: List[SpecialDayMenu] = Field(
        default_factory=list,
        max_length=31,
    )
    
    created_by: UUID = Field(..., description="Creator user ID")
    notes: Union[str, None] = Field(None, max_length=2000)

# --- Continuation of menu_planning.py ---

class SpecialMenu(BaseCreateSchema):
    """
    Special occasion menu configuration.
    
    Defines enhanced menu for festivals, celebrations, and events.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    occasion_date: Date = Field(
        ...,
        description="Occasion Date",
    )
    occasion_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Occasion name",
    )
    occasion_type: str = Field(
        ...,
        pattern=r"^(festival|holiday|celebration|cultural_event|sports_event|founder_day|other)$",
        description="Type of occasion",
    )
    
    # Enhanced menu
    breakfast: List[str] = Field(
        ...,
        min_length=1,
        max_length=25,
        description="Special breakfast items",
    )
    lunch: List[str] = Field(
        ...,
        min_length=1,
        max_length=40,
        description="Special lunch items",
    )
    snacks: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Special snacks items",
    )
    dinner: List[str] = Field(
        ...,
        min_length=1,
        max_length=40,
        description="Special dinner items",
    )
    
    # Additional special items
    special_items: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Extra special delicacies",
    )
    desserts: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Special desserts",
    )
    
    # Budget and planning
    budget: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Special occasion budget",
    )
    estimated_cost_per_person: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Estimated cost per person",
    )
    expected_attendees: Union[int, None] = Field(
        None,
        ge=1,
        description="Expected number of attendees",
    )
    
    # Execution details
    decoration_theme: Union[str, None] = Field(
        None,
        max_length=255,
        description="Decoration theme",
    )
    serving_style: Union[str, None] = Field(
        None,
        pattern=r"^(buffet|table_service|plated|family_style)$",
        description="Serving style",
    )
    special_instructions: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Special preparation instructions",
    )
    
    # Notifications
    send_advance_notification: bool = Field(
        default=True,
        description="Send advance notification to students",
    )
    notification_days_before: int = Field(
        default=3,
        ge=0,
        le=30,
        description="Days before to send notification",
    )

    @field_validator("occasion_date", mode="after")
    @classmethod
    def validate_occasion_date(cls, v: Date) -> Date:
        """Validate occasion Date is not too far in future."""
        days_ahead = (v - Date.today()).days
        
        if days_ahead < -7:
            raise ValueError(
                "Cannot create special menu for dates more than 7 days in past"
            )
        
        if days_ahead > 365:
            raise ValueError(
                "Cannot create special menu more than 1 year in advance"
            )
        
        return v

    @field_validator("budget", "estimated_cost_per_person", mode="after")
    @classmethod
    def round_costs(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round cost values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v


class MenuTemplate(BaseCreateSchema):
    """
    Reusable menu template for recurring patterns.
    
    Stores menu patterns that can be applied to multiple dates.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    template_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Template name",
    )
    template_code: Union[str, None] = Field(
        None,
        max_length=50,
        description="Template code/identifier",
    )
    description: Union[str, None] = Field(
        None,
        max_length=500,
        description="Template description",
    )
    
    # Template type and applicability
    template_type: str = Field(
        ...,
        pattern=r"^(weekly|festival|summer|winter|monsoon|exam_period|vacation|regular)$",
        description="Template type/category",
    )
    applicable_season: Union[str, None] = Field(
        None,
        pattern=r"^(spring|summer|monsoon|autumn|winter|all)$",
        description="Applicable season",
    )
    
    # Menu structure (day-wise or meal-wise)
    daily_menus: Dict[str, DailyMenuPlan] = Field(
        ...,
        description="Day name/identifier -> menu plan mapping",
    )
    
    # Template metadata
    created_by: UUID = Field(
        ...,
        description="Creator user ID",
    )
    is_active: bool = Field(
        default=True,
        description="Whether template is active",
    )
    is_default: bool = Field(
        default=False,
        description="Whether this is default template",
    )
    usage_count: int = Field(
        default=0,
        ge=0,
        description="Number of times template has been used",
    )
    average_rating: Union[Decimal, None] = Field(
        None,
        ge=0,
        le=5,
        description="Average rating when template was used",
    )
    
    # Cost information
    estimated_daily_cost: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Estimated daily cost per person",
    )
    
    # Tags for categorization
    tags: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Template tags for search/filter",
    )

    @field_validator("daily_menus", mode="after")
    @classmethod
    def validate_daily_menus(cls, v: Dict[str, DailyMenuPlan]) -> Dict[str, DailyMenuPlan]:
        """Validate daily menus structure."""
        if not v:
            raise ValueError("Template must have at least one daily menu")
        
        # Validate keys are proper day names or identifiers
        valid_days = {
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
            "day1", "day2", "day3", "day4", "day5", "day6", "day7"
        }
        
        for key in v.keys():
            if key.lower() not in valid_days:
                # Allow custom keys but validate they're reasonable
                if len(key) > 20:
                    raise ValueError(f"Daily menu key '{key}' is too long")
        
        return v

    @field_validator("average_rating", "estimated_daily_cost", mode="after")
    @classmethod
    def round_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round decimal values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v


class MenuTemplateCreate(BaseCreateSchema):
    """
    Create reusable menu template.
    
    Template can be applied to multiple dates for efficient planning.
    """

    hostel_id: UUID = Field(..., description="Hostel unique identifier")
    template_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Template name",
    )
    template_code: Union[str, None] = Field(
        None,
        max_length=50,
        description="Template code/identifier",
    )
    description: Union[str, None] = Field(
        None,
        max_length=500,
        description="Template description",
    )
    template_type: str = Field(
        ...,
        pattern=r"^(weekly|festival|summer|winter|monsoon|exam_period|vacation|regular)$",
        description="Template type",
    )
    applicable_season: Union[str, None] = Field(
        None,
        pattern=r"^(spring|summer|monsoon|autumn|winter|all)$",
    )
    daily_menus: Dict[str, DailyMenuPlan] = Field(
        ...,
        description="Day-wise menu plans",
    )
    created_by: UUID = Field(..., description="Creator user ID")
    is_active: bool = Field(default=True)
    tags: List[str] = Field(default_factory=list, max_length=20)


class MenuTemplateUpdate(BaseUpdateSchema):
    """
    Update existing menu template.
    
    All fields optional for partial updates.
    """

    template_name: Union[str, None] = Field(None, min_length=3, max_length=100)
    template_code: Union[str, None] = Field(None, max_length=50)
    description: Union[str, None] = Field(None, max_length=500)
    template_type: Union[str, None] = Field(
        None,
        pattern=r"^(weekly|festival|summer|winter|monsoon|exam_period|vacation|regular)$",
    )
    applicable_season: Union[str, None] = Field(
        None,
        pattern=r"^(spring|summer|monsoon|autumn|winter|all)$",
    )
    daily_menus: Union[Dict[str, DailyMenuPlan], None] = None
    is_active: Union[bool, None] = None
    tags: Union[List[str], None] = Field(None, max_length=20)


class MenuSuggestion(BaseSchema):
    """
    AI/system generated menu suggestions.
    
    Provides intelligent menu recommendations based on various factors.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    suggestion_date: Date = Field(
        ...,
        description="Date for suggested menu",
    )
    
    # Suggested items
    suggested_breakfast: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Breakfast suggestions",
    )
    suggested_lunch: List[str] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Lunch suggestions",
    )
    suggested_snacks: List[str] = Field(
        default_factory=list,
        max_length=15,
        description="Snacks suggestions",
    )
    suggested_dinner: List[str] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Dinner suggestions",
    )
    
    # Suggestion rationale
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Why these items are suggested",
    )
    based_on: List[str] = Field(
        default_factory=list,
        description="Factors considered (past ratings, season, etc.)",
    )
    
    # Scoring
    variety_score: Decimal = Field(
        ...,
        ge=0,
        le=10,
        description="Menu variety score (0-10)",
    )
    nutrition_score: Decimal = Field(
        ...,
        ge=0,
        le=10,
        description="Nutritional balance score (0-10)",
    )
    cost_score: Decimal = Field(
        ...,
        ge=0,
        le=10,
        description="Cost efficiency score (0-10)",
    )
    popularity_score: Decimal = Field(
        ...,
        ge=0,
        le=10,
        description="Based on past ratings (0-10)",
    )
    overall_score: Decimal = Field(
        ...,
        ge=0,
        le=10,
        description="Overall recommendation score (0-10)",
    )
    
    # Additional context
    seasonal_items_count: int = Field(
        default=0,
        ge=0,
        description="Number of seasonal items included",
    )
    estimated_cost_per_person: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Estimated cost per person",
    )
    estimated_calories: Union[int, None] = Field(
        None,
        ge=0,
        description="Estimated daily calories",
    )
    
    # Suggestion metadata
    generated_at: datetime = Field(
        ...,
        description="Suggestion generation timestamp",
    )
    algorithm_version: Union[str, None] = Field(
        None,
        description="Suggestion algorithm version",
    )

    @field_validator(
        "variety_score", "nutrition_score", "cost_score",
        "popularity_score", "overall_score", "estimated_cost_per_person",
        mode="after"
    )
    @classmethod
    def round_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round decimal values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @computed_field
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


class SuggestionCriteria(BaseCreateSchema):
    """
    Criteria for AI menu suggestions.
    
    Defines parameters for generating intelligent menu recommendations.
    """

    hostel_id: UUID = Field(..., description="Hostel unique identifier")
    
    # Date range
    start_date: Date = Field(..., description="Suggestion period start")
    end_date: Date = Field(..., description="Suggestion period end")
    
    # Preferences
    dietary_preferences: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Dietary preferences to consider",
    )
    exclude_items: List[str] = Field(
        default_factory=list,
        max_length=30,
        description="Items to exclude from suggestions",
    )
    preferred_cuisines: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Preferred cuisine types",
    )
    
    # Constraints
    budget_per_person_max: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Maximum budget per person",
    )
    ensure_variety: bool = Field(
        default=True,
        description="Ensure item variety",
    )
    min_days_between_repeat: int = Field(
        default=3,
        ge=1,
        le=7,
        description="Minimum days before repeating items",
    )
    
    # Nutritional goals
    target_calories_per_day: Union[int, None] = Field(
        None,
        ge=1000,
        le=5000,
    )
    ensure_balanced_nutrition: bool = Field(default=True)
    
    # Seasonal preferences
    prefer_seasonal_items: bool = Field(default=True)
    
    # Optimization goals
    optimize_for: str = Field(
        default="balanced",
        pattern=r"^(cost|nutrition|variety|popularity|balanced)$",
        description="Primary optimization goal",
    )

    @field_validator("budget_per_person_max", mode="after")
    @classmethod
    def round_budget(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round budget to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @model_validator(mode="after")
    def validate_date_range(self) -> "SuggestionCriteria":
        """Validate date range."""
        if self.end_date < self.start_date:
            raise ValueError("End date must be after start date")
        
        days_span = (self.end_date - self.start_date).days + 1
        if days_span > 90:
            raise ValueError("Suggestion period cannot exceed 90 days")
        
        return self