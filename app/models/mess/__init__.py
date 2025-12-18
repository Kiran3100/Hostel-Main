# app/models/mess/__init__.py
"""
Mess Management Models Package.

Complete mess/cafeteria management system including menus, meal items,
dietary options, nutritional information, approval workflows, feedback,
and strategic planning capabilities.
"""

from app.models.mess.dietary_option import (
    AllergenProfile,
    DietaryOption,
    DietaryRestriction,
    MealCustomization,
    StudentDietaryPreference,
)
from app.models.mess.meal_item import (
    IngredientMaster,
    ItemAllergen,
    ItemCategory,
    ItemPopularity,
    MealItem,
    Recipe,
)
from app.models.mess.menu_approval import (
    ApprovalAttempt,
    ApprovalHistory,
    ApprovalRule,
    ApprovalWorkflow,
    BulkApproval,
    MenuApproval,
    MenuApprovalRequest,
)
from app.models.mess.menu_feedback import (
    FeedbackAnalysis,
    FeedbackComment,
    FeedbackHelpfulness,
    ItemRating,
    MenuFeedback,
    QualityMetrics,
    RatingsSummary,
    SentimentAnalysis,
)
from app.models.mess.menu_planning import (
    DailyMenuPlan,
    MenuPlanningRule,
    MenuSuggestion,
    MenuTemplate,
    MonthlyMenuPlan,
    SeasonalMenu,
    SpecialOccasionMenu,
    WeeklyMenuPlan,
)
from app.models.mess.mess_menu import (
    MenuAvailability,
    MenuCycle,
    MenuPublishing,
    MenuVersion,
    MessMenu,
)
from app.models.mess.nutritional_info import (
    DietaryValue,
    NutrientProfile,
    NutritionalInfo,
    NutritionalReport,
)

__all__ = [
    # Core Menu Models
    "MessMenu",
    "MenuCycle",
    "MenuVersion",
    "MenuPublishing",
    "MenuAvailability",
    
    # Meal Items
    "MealItem",
    "Recipe",
    "IngredientMaster",
    "ItemCategory",
    "ItemAllergen",
    "ItemPopularity",
    
    # Dietary Options
    "DietaryOption",
    "StudentDietaryPreference",
    "AllergenProfile",
    "DietaryRestriction",
    "MealCustomization",
    
    # Nutritional Information
    "NutritionalInfo",
    "NutrientProfile",
    "DietaryValue",
    "NutritionalReport",
    
    # Approval Workflow
    "MenuApproval",
    "MenuApprovalRequest",
    "ApprovalWorkflow",
    "ApprovalHistory",
    "ApprovalAttempt",
    "ApprovalRule",
    "BulkApproval",
    
    # Feedback and Ratings
    "MenuFeedback",
    "ItemRating",
    "RatingsSummary",
    "QualityMetrics",
    "SentimentAnalysis",
    "FeedbackAnalysis",
    "FeedbackComment",
    "FeedbackHelpfulness",
    
    # Planning
    "MenuTemplate",
    "WeeklyMenuPlan",
    "MonthlyMenuPlan",
    "DailyMenuPlan",
    "SpecialOccasionMenu",
    "MenuSuggestion",
    "MenuPlanningRule",
    "SeasonalMenu",
]


# Model organization by functionality
MENU_MODELS = [
    "MessMenu",
    "MenuCycle",
    "MenuVersion",
    "MenuPublishing",
    "MenuAvailability",
]

ITEM_MODELS = [
    "MealItem",
    "Recipe",
    "IngredientMaster",
    "ItemCategory",
    "ItemAllergen",
    "ItemPopularity",
]

DIETARY_MODELS = [
    "DietaryOption",
    "StudentDietaryPreference",
    "AllergenProfile",
    "DietaryRestriction",
    "MealCustomization",
]

NUTRITION_MODELS = [
    "NutritionalInfo",
    "NutrientProfile",
    "DietaryValue",
    "NutritionalReport",
]

APPROVAL_MODELS = [
    "MenuApproval",
    "MenuApprovalRequest",
    "ApprovalWorkflow",
    "ApprovalHistory",
    "ApprovalAttempt",
    "ApprovalRule",
    "BulkApproval",
]

FEEDBACK_MODELS = [
    "MenuFeedback",
    "ItemRating",
    "RatingsSummary",
    "QualityMetrics",
    "SentimentAnalysis",
    "FeedbackAnalysis",
    "FeedbackComment",
    "FeedbackHelpfulness",
]

PLANNING_MODELS = [
    "MenuTemplate",
    "WeeklyMenuPlan",
    "MonthlyMenuPlan",
    "DailyMenuPlan",
    "SpecialOccasionMenu",
    "MenuSuggestion",
    "MenuPlanningRule",
    "SeasonalMenu",
]

# All models list for import verification
ALL_MESS_MODELS = (
    MENU_MODELS +
    ITEM_MODELS +
    DIETARY_MODELS +
    NUTRITION_MODELS +
    APPROVAL_MODELS +
    FEEDBACK_MODELS +
    PLANNING_MODELS
)