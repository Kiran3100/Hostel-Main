# --- File: C:\Hostel-Main\app\models\review\__init__.py ---
"""
Review models package.

Provides comprehensive models for:
- Review management and lifecycle
- Moderation and approval workflows
- Voting and helpfulness scoring
- Hostel responses to reviews
- Media attachments
- Analytics and insights

Example:
    from app.models.review import (
        Review,
        ReviewVote,
        ReviewResponse,
        ReviewModerationLog,
        ReviewAnalyticsSummary,
    )
"""

from app.models.review.review import (
    Review,
    ReviewAspect,
    ReviewVerification,
    ReviewStatusHistory,
)

from app.models.review.review_moderation import (
    ReviewModerationLog,
    ReviewFlag,
    ReviewModerationQueue,
    ReviewAutoModeration,
)

from app.models.review.review_voting import (
    ReviewVote,
    ReviewHelpfulnessScore,
    ReviewEngagement,
)

from app.models.review.review_response import (
    ReviewResponse,
    ResponseTemplate,
    ResponseStatistics,
)

from app.models.review.review_media import (
    ReviewMedia,
    ReviewMediaProcessing,
)

from app.models.review.review_analytics import (
    ReviewAnalyticsSummary,
    RatingDistribution,
    ReviewTrend,
    MonthlyRating,
    SentimentAnalysis,
    AspectRating,
    CompetitorComparison,
)

__all__ = [
    # Core review models
    "Review",
    "ReviewAspect",
    "ReviewVerification",
    "ReviewStatusHistory",
    
    # Moderation models
    "ReviewModerationLog",
    "ReviewFlag",
    "ReviewModerationQueue",
    "ReviewAutoModeration",
    
    # Voting models
    "ReviewVote",
    "ReviewHelpfulnessScore",
    "ReviewEngagement",
    
    # Response models
    "ReviewResponse",
    "ResponseTemplate",
    "ResponseStatistics",
    
    # Media models
    "ReviewMedia",
    "ReviewMediaProcessing",
    
    # Analytics models
    "ReviewAnalyticsSummary",
    "RatingDistribution",
    "ReviewTrend",
    "MonthlyRating",
    "SentimentAnalysis",
    "AspectRating",
    "CompetitorComparison",
]


# Model relationship documentation
"""
Review Module Relationships:

1. Core Review:
   - Review → Hostel (many-to-one)
   - Review → User/Reviewer (many-to-one)
   - Review → Student (many-to-one, optional)
   - Review → Booking (one-to-one, optional)

2. Review Extensions:
   - Review → ReviewAspect (one-to-many)
   - Review → ReviewVerification (one-to-one)
   - Review → ReviewStatusHistory (one-to-many)
   - Review → ReviewMedia (one-to-many)

3. Moderation:
   - Review → ReviewModerationLog (one-to-many)
   - Review → ReviewFlag (one-to-many)
   - Review → ReviewModerationQueue (one-to-one)
   - Review → ReviewAutoModeration (one-to-one)

4. Engagement:
   - Review → ReviewVote (one-to-many)
   - Review → ReviewHelpfulnessScore (one-to-one)
   - Review → ReviewEngagement (one-to-one)

5. Responses:
   - Review → ReviewResponse (one-to-one)
   - ResponseTemplate → ReviewResponse (one-to-many)

6. Analytics:
   - Hostel → ReviewAnalyticsSummary (one-to-one)
   - Hostel → RatingDistribution (one-to-one)
   - Hostel → ReviewTrend (one-to-many)
   - Hostel → MonthlyRating (one-to-many)
   - Hostel → SentimentAnalysis (one-to-one)
   - Hostel → AspectRating (one-to-many)
   - Hostel → CompetitorComparison (one-to-many)

Database Indexes:
- Review: hostel_id, reviewer_id, status, rating, created_at
- ReviewVote: review_id, voter_id, vote_type
- ReviewResponse: review_id, hostel_id, responded_at
- ReviewModerationQueue: queue_status, priority_score, assigned_to
- ReviewAnalyticsSummary: hostel_id, quality_score, average_rating

Performance Considerations:
- Use composite indexes for common query patterns
- Implement caching for analytics summaries
- Use read replicas for heavy analytical queries
- Consider partitioning for large review datasets
- Implement archival strategy for old reviews

Security & Privacy:
- Soft delete for reviews (preserve history)
- Audit trails for all moderation actions
- Personal data handling for GDPR compliance
- Access control for sensitive review data
- IP address and user agent logging for fraud detection
"""