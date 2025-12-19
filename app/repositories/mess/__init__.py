# --- File: C:\Hostel-Main\app\repositories\mess\__init__.py ---

"""
Mess Repository Package.

Provides data access layer for all mess module operations including
dietary management, menu planning, feedback, and nutritional tracking.
"""

from app.repositories.mess.dietary_option_repository import (
    AllergenProfileRepository,
    DietaryOptionRepository,
    DietaryRestrictionRepository,
    MealCustomizationRepository,
    StudentDietaryPreferenceRepository,
)
from app.repositories.mess.meal_item_repository import (
    IngredientMasterRepository,
    ItemAllergenRepository,
    ItemCategoryRepository,
    ItemPopularityRepository,
    MealItemRepository,
    RecipeRepository,
)
from app.repositories.mess.menu_approval_repository import (
    ApprovalAttemptRepository,
    ApprovalHistoryRepository,
    ApprovalRuleRepository,
    ApprovalWorkflowRepository,
    BulkApprovalRepository,
    MenuApprovalRepository,
    MenuApprovalRequestRepository,
)
from app.repositories.mess.menu_feedback_repository import (
    FeedbackAnalysisRepository,
    FeedbackCommentRepository,
    FeedbackHelpfulnessRepository,
    ItemRatingRepository,
    MenuFeedbackRepository,
    QualityMetricsRepository,
    RatingsSummaryRepository,
    SentimentAnalysisRepository,
)
from app.repositories.mess.menu_planning_repository import (
    DailyMenuPlanRepository,
    MenuPlanningRuleRepository,
    MenuSuggestionRepository,
    MenuTemplateRepository,
    MonthlyMenuPlanRepository,
    SeasonalMenuRepository,
    SpecialOccasionMenuRepository,
    WeeklyMenuPlanRepository,
)
from app.repositories.mess.mess_aggregate_repository import MessAggregateRepository
from app.repositories.mess.mess_menu_repository import (
    MenuAvailabilityRepository,
    MenuCycleRepository,
    MenuPublishingRepository,
    MenuVersionRepository,
    MessMenuRepository,
)
from app.repositories.mess.nutritional_info_repository import (
    DietaryValueRepository,
    NutrientProfileRepository,
    NutritionalInfoRepository,
    NutritionalReportRepository,
)

__all__ = [
    # Dietary Option Repositories
    "DietaryOptionRepository",
    "StudentDietaryPreferenceRepository",
    "AllergenProfileRepository",
    "DietaryRestrictionRepository",
    "MealCustomizationRepository",
    
    # Meal Item Repositories
    "MealItemRepository",
    "RecipeRepository",
    "IngredientMasterRepository",
    "ItemCategoryRepository",
    "ItemAllergenRepository",
    "ItemPopularityRepository",
    
    # Menu Approval Repositories
    "MenuApprovalRepository",
    "MenuApprovalRequestRepository",
    "ApprovalWorkflowRepository",
    "ApprovalHistoryRepository",
    "ApprovalAttemptRepository",
    "ApprovalRuleRepository",
    "BulkApprovalRepository",
    
    # Menu Feedback Repositories
    "MenuFeedbackRepository",
    "ItemRatingRepository",
    "RatingsSummaryRepository",
    "QualityMetricsRepository",
    "SentimentAnalysisRepository",
    "FeedbackAnalysisRepository",
    "FeedbackCommentRepository",
    "FeedbackHelpfulnessRepository",
    
    # Menu Planning Repositories
    "MenuTemplateRepository",
    "WeeklyMenuPlanRepository",
    "MonthlyMenuPlanRepository",
    "DailyMenuPlanRepository",
    "SpecialOccasionMenuRepository",
    "MenuSuggestionRepository",
    "MenuPlanningRuleRepository",
    "SeasonalMenuRepository",
    
    # Mess Menu Repositories
    "MessMenuRepository",
    "MenuCycleRepository",
    "MenuVersionRepository",
    "MenuPublishingRepository",
    "MenuAvailabilityRepository",
    
    # Nutritional Info Repositories
    "NutritionalInfoRepository",
    "NutrientProfileRepository",
    "DietaryValueRepository",
    "NutritionalReportRepository",
    
    # Aggregate Repository
    "MessAggregateRepository",
]


# Repository groupings for easy access
DIETARY_REPOSITORIES = [
    DietaryOptionRepository,
    StudentDietaryPreferenceRepository,
    AllergenProfileRepository,
    DietaryRestrictionRepository,
    MealCustomizationRepository,
]

MEAL_ITEM_REPOSITORIES = [
    MealItemRepository,
    RecipeRepository,
    IngredientMasterRepository,
    ItemCategoryRepository,
    ItemAllergenRepository,
    ItemPopularityRepository,
]

APPROVAL_REPOSITORIES = [
    MenuApprovalRepository,
    MenuApprovalRequestRepository,
    ApprovalWorkflowRepository,
    ApprovalHistoryRepository,
    ApprovalAttemptRepository,
    ApprovalRuleRepository,
    BulkApprovalRepository,
]

FEEDBACK_REPOSITORIES = [
    MenuFeedbackRepository,
    ItemRatingRepository,
    RatingsSummaryRepository,
    QualityMetricsRepository,
    SentimentAnalysisRepository,
    FeedbackAnalysisRepository,
    FeedbackCommentRepository,
    FeedbackHelpfulnessRepository,
]

PLANNING_REPOSITORIES = [
    MenuTemplateRepository,
    WeeklyMenuPlanRepository,
    MonthlyMenuPlanRepository,
    DailyMenuPlanRepository,
    SpecialOccasionMenuRepository,
    MenuSuggestionRepository,
    MenuPlanningRuleRepository,
    SeasonalMenuRepository,
]

MENU_REPOSITORIES = [
    MessMenuRepository,
    MenuCycleRepository,
    MenuVersionRepository,
    MenuPublishingRepository,
    MenuAvailabilityRepository,
]

NUTRITION_REPOSITORIES = [
    NutritionalInfoRepository,
    NutrientProfileRepository,
    DietaryValueRepository,
    NutritionalReportRepository,
]

# All repositories list
ALL_MESS_REPOSITORIES = (
    DIETARY_REPOSITORIES +
    MEAL_ITEM_REPOSITORIES +
    APPROVAL_REPOSITORIES +
    FEEDBACK_REPOSITORIES +
    PLANNING_REPOSITORIES +
    MENU_REPOSITORIES +
    NUTRITION_REPOSITORIES +
    [MessAggregateRepository]
)