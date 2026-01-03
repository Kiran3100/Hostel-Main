"""
Review schemas package.

Provides comprehensive schemas for:
- Review creation, update, and submission
- Review responses and details
- Moderation and approval workflows
- Voting and engagement
- Hostel responses to reviews
- Filtering, searching, and export
- Analytics and insights

Example:
    from app.schemas.review import (
        ReviewCreate,
        ReviewResponse,
        ReviewSubmissionRequest,
        ModerationRequest,
        VoteRequest,
    )
"""

# Base schemas
from app.schemas.review.review_base import (
    ReviewBase,
    ReviewCreate,
    ReviewUpdate,
    DetailedRatings,
)

# Response schemas
from app.schemas.review.review_response import (
    ReviewResponse,
    ReviewDetail,
    ReviewListItem,
    ReviewSummary,
    HostelResponseDetail,
    PaginatedReviewResponse,
)

# Submission schemas
from app.schemas.review.review_submission import (
    ReviewSubmissionRequest,
    DetailedRatingsInput,
    VerifiedReview,
    ReviewGuidelines,
    ReviewEligibility,
    ReviewDraft,
)

# Moderation schemas
from app.schemas.review.review_moderation import (
    ModerationRequest,
    ModerationResponse,
    ModerationQueue,
    PendingReview,
    ApprovalWorkflow,
    BulkModeration,
    ModerationStats,
    FlagReview,
)

# Voting schemas
from app.schemas.review.review_voting import (
    VoteRequest,
    VoteResponse,
    HelpfulnessScore,
    VoteHistory,
    VoteHistoryItem,
    RemoveVote,
    VotingStats,
)

# Hostel response schemas
from app.schemas.review.review_response_schema import (
    HostelResponseCreate,
    HostelResponseUpdate,
    OwnerResponse,
    ResponseGuidelines,
    ResponseStats,
    ResponseTemplate,
    ResponseTemplateCreate,
)

# Filter schemas
from app.schemas.review.review_filters import (
    ReviewFilterParams,
    ReviewSearchRequest,
    ReviewSortOptions,
    ReviewExportRequest,
)

# Analytics schemas
from app.schemas.review.review_analytics import (
    ReviewAnalytics,
    RatingDistribution,
    TrendAnalysis,
    MonthlyRating,
    SentimentAnalysis,
    AspectAnalysis,
    CompetitorComparison,
)

__all__ = [
    # Base
    "ReviewBase",
    "ReviewCreate",
    "ReviewUpdate",
    "DetailedRatings",
    
    # Response
    "ReviewResponse",
    "ReviewDetail",
    "ReviewListItem",
    "ReviewSummary",
    "HostelResponseDetail",
    "PaginatedReviewResponse",
    
    # Submission
    "ReviewSubmissionRequest",
    "DetailedRatingsInput",
    "VerifiedReview",
    "ReviewGuidelines",
    "ReviewEligibility",
    "ReviewDraft",
    
    # Moderation
    "ModerationRequest",
    "ModerationResponse",
    "ModerationQueue",
    "PendingReview",
    "ApprovalWorkflow",
    "BulkModeration",
    "ModerationStats",
    "FlagReview",
    
    # Voting
    "VoteRequest",
    "VoteResponse",
    "HelpfulnessScore",
    "VoteHistory",
    "VoteHistoryItem",
    "RemoveVote",
    "VotingStats",
    
    # Hostel Response
    "HostelResponseCreate",
    "HostelResponseUpdate",
    "OwnerResponse",
    "ResponseGuidelines",
    "ResponseStats",
    "ResponseTemplate",
    "ResponseTemplateCreate",
    
    # Filters
    "ReviewFilterParams",
    "ReviewSearchRequest",
    "ReviewSortOptions",
    "ReviewExportRequest",
    
    # Analytics
    "ReviewAnalytics",
    "RatingDistribution",
    "TrendAnalysis",
    "MonthlyRating",
    "SentimentAnalysis",
    "AspectAnalysis",
    "CompetitorComparison",
]