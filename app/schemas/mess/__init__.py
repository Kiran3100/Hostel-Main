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
)
from app.schemas.mess.menu_approval import (
    ApprovalAttempt,
    ApprovalHistory,
    ApprovalWorkflow,
    BulkApproval,
    MenuApprovalRequest,
    MenuApprovalResponse,
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
    ItemRating,
    QualityMetrics,
    RatingsSummary,
    SentimentAnalysis,
)
from app.schemas.mess.menu_planning import (
    DailyMenuPlan,
    MenuPlanRequest,
    MenuSuggestion,
    MenuTemplate,
    MonthlyPlan,
    SpecialDayMenu,
    SpecialMenu,
    WeeklyPlan,
)
from app.schemas.mess.mess_menu_base import (
    MessMenuBase,
    MessMenuCreate,
    MessMenuUpdate,
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

__all__ = [
    # Base schemas
    "MessMenuBase",
    "MessMenuCreate",
    "MessMenuUpdate",
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
    # Planning
    "MenuPlanRequest",
    "WeeklyPlan",
    "DailyMenuPlan",
    "MonthlyPlan",
    "SpecialMenu",
    "SpecialDayMenu",
    "MenuTemplate",
    "MenuSuggestion",
    # Feedback
    "FeedbackRequest",
    "FeedbackResponse",
    "RatingsSummary",
    "ItemRating",
    "QualityMetrics",
    "FeedbackAnalysis",
    "SentimentAnalysis",
    # Approval
    "MenuApprovalRequest",
    "MenuApprovalResponse",
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
]