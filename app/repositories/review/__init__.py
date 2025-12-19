"""
Review repositories package.

Provides comprehensive repository layer for review management including:
- Core review CRUD and queries
- Moderation workflows and content safety
- Voting and helpfulness scoring
- Response management and templates
- Media handling and processing
- Analytics and insights
- Aggregate queries and reporting

Example Usage:
    from app.repositories.review import (
        ReviewRepository,
        ReviewModerationRepository,
        ReviewVotingRepository,
        ReviewResponseRepository,
        ReviewMediaRepository,
        ReviewAnalyticsRepository,
        ReviewAggregateRepository,
    )
    
    # Initialize repositories with session
    review_repo = ReviewRepository(session)
    moderation_repo = ReviewModerationRepository(session)
    voting_repo = ReviewVotingRepository(session)
    
    # Create review
    review = review_repo.create_review(
        hostel_id=hostel_id,
        reviewer_id=user_id,
        data={
            'overall_rating': Decimal('4.5'),
            'title': 'Great experience!',
            'review_text': 'Had a wonderful stay...',
            'would_recommend': True
        }
    )
    
    # Get hostel reviews with filters
    reviews = review_repo.find_by_hostel(
        hostel_id=hostel_id,
        filters={'min_rating': Decimal('4.0'), 'verified_only': True},
        pagination={'page': 1, 'per_page': 20}
    )
    
    # Cast vote
    vote = voting_repo.cast_vote(
        review_id=review.id,
        voter_id=user_id,
        vote_type=VoteType.HELPFUL
    )
    
    # Create response
    response = response_repo.create_response(
        review_id=review.id,
        hostel_id=hostel_id,
        response_text='Thank you for your feedback!',
        responded_by=admin_id,
        responded_by_name='Hostel Manager'
    )
    
    # Get analytics
    analytics = analytics_repo.calculate_analytics_summary(hostel_id)
    
    # Get dashboard metrics
    metrics = aggregate_repo.get_hostel_dashboard_metrics(
        hostel_id=hostel_id,
        period_days=30
    )
"""

from app.repositories.review.review_repository import ReviewRepository
from app.repositories.review.review_moderation_repository import (
    ReviewModerationRepository
)
from app.repositories.review.review_voting_repository import ReviewVotingRepository
from app.repositories.review.review_response_repository import (
    ReviewResponseRepository
)
from app.repositories.review.review_media_repository import ReviewMediaRepository
from app.repositories.review.review_analytics_repository import (
    ReviewAnalyticsRepository
)
from app.repositories.review.review_aggregate_repository import (
    ReviewAggregateRepository
)

__all__ = [
    # Core repository
    'ReviewRepository',
    
    # Specialized repositories
    'ReviewModerationRepository',
    'ReviewVotingRepository',
    'ReviewResponseRepository',
    'ReviewMediaRepository',
    'ReviewAnalyticsRepository',
    'ReviewAggregateRepository',
]


# Repository usage patterns and best practices
"""
Repository Layer Architecture:

1. ReviewRepository (Core)
   - Primary CRUD operations
   - Basic querying and filtering
   - Status management
   - Lifecycle operations
   
2. ReviewModerationRepository
   - Moderation workflows
   - Flag management
   - Queue operations
   - Auto-moderation integration
   
3. ReviewVotingRepository
   - Vote casting and management
   - Helpfulness scoring (Wilson score)
   - Engagement tracking
   - Ranking calculations
   
4. ReviewResponseRepository
   - Response creation and management
   - Template operations
   - Response analytics
   - Performance tracking
   
5. ReviewMediaRepository
   - Media upload handling
   - Processing workflows
   - Content moderation
   - Media analytics
   
6. ReviewAnalyticsRepository
   - Comprehensive analytics
   - Trend analysis
   - Sentiment tracking
   - Competitive insights
   
7. ReviewAggregateRepository
   - Cross-entity queries
   - Dashboard metrics
   - Complex reporting
   - Data export

Transaction Management:
- Repositories use injected sessions
- Commit/rollback handled at service layer
- Atomic operations within repositories
- Bulk operations optimized for performance

Caching Strategy:
- Analytics results cached with TTL
- Frequently accessed reviews cached
- Cache invalidation on updates
- Read-through caching for queries

Performance Optimization:
- Eager loading for relationships
- Index-optimized queries
- Pagination for large datasets
- Query result caching
- Bulk operations for efficiency

Error Handling:
- Validation errors raised early
- Database errors propagated to service layer
- Constraint violations handled gracefully
- Meaningful error messages

Testing Patterns:
- Unit tests with mocked sessions
- Integration tests with test database
- Factory patterns for test data
- Fixture-based testing

Example Service Integration:
    class ReviewService:
        def __init__(self, session: Session):
            self.review_repo = ReviewRepository(session)
            self.voting_repo = ReviewVotingRepository(session)
            self.analytics_repo = ReviewAnalyticsRepository(session)
            self.session = session
        
        def create_review_with_analytics(self, data):
            try:
                # Create review
                review = self.review_repo.create_review(...)
                
                # Update analytics
                self.analytics_repo.calculate_analytics_summary(
                    review.hostel_id
                )
                
                # Commit transaction
                self.session.commit()
                return review
                
            except Exception as e:
                self.session.rollback()
                raise
"""

# Performance monitoring hooks
"""
Monitoring Integration:

1. Query Performance:
   - Log slow queries (>100ms)
   - Track query execution time
   - Monitor database load
   
2. Cache Efficiency:
   - Cache hit/miss ratios
   - Cache size monitoring
   - Eviction rate tracking
   
3. Business Metrics:
   - Review creation rate
   - Response time tracking
   - Moderation queue depth
   - Analytics refresh frequency

4. Error Tracking:
   - Failed operations logged
   - Constraint violations tracked
   - Validation errors categorized

Example Metrics:
    review_repository_query_duration_seconds
    review_repository_cache_hit_ratio
    review_repository_operations_total
    review_repository_errors_total
"""