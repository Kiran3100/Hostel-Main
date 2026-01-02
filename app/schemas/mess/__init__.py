# --- File: app/schemas/mess/__init__.py ---
"""
Mess management schemas package.

Comprehensive mess/cafeteria menu management schemas including planning,
feedback, approval workflows, and duplication with enhanced validation.
"""

from app.schemas.mess.meal_items import (
    AllergenInfo,
    DietaryOptions,
    ItemCategory,
    ItemMasterList,
    MealItems,
    MenuItem,
    NutritionalInfo,
    MealItemCreate,
    MealItemUpdate,
    MealItemResponse,
    MealItemDetail,
)
from app.schemas.mess.menu_approval import (
    ApprovalAttempt,
    ApprovalHistory,
    ApprovalWorkflow,
    BulkApproval,
    MenuApprovalRequest,
    MenuApprovalResponse,
    MenuRejectionRequest,
)
from app.schemas.mess.menu_duplication import (
    BulkMenuCreate,
    CrossHostelDuplication,
    DuplicateMenuRequest,
    DuplicateResponse,
    MenuCloneConfig,
)
from app.schemas.mess.menu_feedback import (
    FeedbackAnalysis,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackCreate,
    ItemRating,
    QualityMetrics,
    RatingsSummary,
    FeedbackSummary,
    SentimentAnalysis,
)
from app.schemas.mess.menu_planning import (
    DailyMenuPlan,
    MenuPlanRequest,
    MenuSuggestion,
    MenuTemplate,
    MenuTemplateCreate,
    MenuTemplateUpdate,
    MonthlyPlan,
    MonthlyPlanCreate,
    SpecialDayMenu,
    SpecialMenu,
    WeeklyPlan,
    WeeklyPlanCreate,
    SuggestionCriteria,
)
from app.schemas.mess.mess_menu_base import (
    MessMenuBase,
    MessMenuCreate,
    MessMenuUpdate,
    MenuCreate,
    MenuUpdate,
)
from app.schemas.mess.mess_menu_response import (
    DailyMenuSummary,
    MenuDetail,
    MenuListItem,
    MenuResponse,
    MonthlyMenu,
    TodayMenu,
    WeeklyMenu,
)
from app.schemas.mess.dietary_options import (
    DietaryOption,
    DietaryOptionUpdate,
    StudentDietaryPreference,
    StudentPreferenceUpdate,
    MealCustomization,
    CustomizationCreate,
)
from app.schemas.mess.menu_stats import (
    MenuStats,
    ItemPopularity,
    MealTypeStats,
    DietaryDistribution,
)

__all__ = [
    # Base schemas
    "MessMenuBase",
    "MessMenuCreate",
    "MessMenuUpdate",
    "MenuCreate",
    "MenuUpdate",
    # Response schemas
    "MenuResponse",
    "MenuDetail",
    "MenuListItem",
    "WeeklyMenu",
    "DailyMenuSummary",
    "MonthlyMenu",
    "TodayMenu",
    # Meal items
    "MealItems",
    "MenuItem",
    "DietaryOptions",
    "NutritionalInfo",
    "AllergenInfo",
    "ItemMasterList",
    "ItemCategory",
    "MealItemCreate",
    "MealItemUpdate",
    "MealItemResponse",
    "MealItemDetail",
    # Planning
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
    # Feedback
    "FeedbackRequest",
    "FeedbackResponse",
    "FeedbackCreate",
    "RatingsSummary",
    "FeedbackSummary",
    "ItemRating",
    "QualityMetrics",
    "FeedbackAnalysis",
    "SentimentAnalysis",
    # Approval
    "MenuApprovalRequest",
    "MenuApprovalResponse",
    "MenuRejectionRequest",
    "ApprovalWorkflow",
    "BulkApproval",
    "ApprovalHistory",
    "ApprovalAttempt",
    # Duplication
    "DuplicateMenuRequest",
    "BulkMenuCreate",
    "DuplicateResponse",
    "CrossHostelDuplication",
    "MenuCloneConfig",
    # Dietary
    "DietaryOption",
    "DietaryOptionUpdate",
    "StudentDietaryPreference",
    "StudentPreferenceUpdate",
    "MealCustomization",
    "CustomizationCreate",
    # Stats
    "MenuStats",
    "ItemPopularity",
    "MealTypeStats",
    "DietaryDistribution",
]