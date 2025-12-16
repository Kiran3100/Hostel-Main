# --- File: app/schemas/review/review_analytics.py ---
"""
Review analytics schemas with comprehensive metrics and trend analysis.

Provides detailed analytics, sentiment analysis, and competitive insights
for hostel reviews.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- field_validator already uses v2 syntax
- All Decimal fields now have explicit max_digits/decimal_places constraints
- Rating fields use appropriate precision for 1.0-5.0 range
- Percentage fields use proper constraints for 0-100 range
"""

from datetime import Date, datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field

from app.schemas.common.base import BaseSchema
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "ReviewAnalytics",
    "RatingDistribution",
    "TrendAnalysis",
    "MonthlyRating",
    "SentimentAnalysis",
    "AspectAnalysis",
    "CompetitorComparison",
]


class MonthlyRating(BaseSchema):
    """
    Monthly rating aggregation.
    
    Tracks average rating and review volume by month.
    """
    
    month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
        examples=["2024-01", "2024-02"],
    )
    average_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="Average rating for the month",
        ),
    ]
    review_count: int = Field(
        ...,
        ge=0,
        description="Total reviews received in the month",
    )
    
    @field_validator("average_rating")
    @classmethod
    def round_to_half(cls, v: Decimal) -> Decimal:
        """Round rating to nearest 0.5."""
        return Decimal(str(round(float(v) * 2) / 2))


class RatingDistribution(BaseSchema):
    """
    Rating distribution breakdown with percentages.
    
    Provides detailed analysis of rating spread across 1-5 stars.
    """
    
    # Raw counts
    rating_5_count: int = Field(..., ge=0, description="5-star reviews count")
    rating_4_count: int = Field(..., ge=0, description="4-star reviews count")
    rating_3_count: int = Field(..., ge=0, description="3-star reviews count")
    rating_2_count: int = Field(..., ge=0, description="2-star reviews count")
    rating_1_count: int = Field(..., ge=0, description="1-star reviews count")
    
    # Percentages with proper constraints
    rating_5_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of 5-star reviews",
        ),
    ]
    rating_4_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of 4-star reviews",
        ),
    ]
    rating_3_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of 3-star reviews",
        ),
    ]
    rating_2_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of 2-star reviews",
        ),
    ]
    rating_1_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of 1-star reviews",
        ),
    ]
    
    # Aggregated metrics
    positive_reviews: int = Field(
        ...,
        ge=0,
        description="Count of positive reviews (4-5 stars)",
    )
    neutral_reviews: int = Field(
        ...,
        ge=0,
        description="Count of neutral reviews (3 stars)",
    )
    negative_reviews: int = Field(
        ...,
        ge=0,
        description="Count of negative reviews (1-2 stars)",
    )
    
    positive_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of positive reviews",
        ),
    ]
    neutral_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of neutral reviews",
        ),
    ]
    negative_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of negative reviews",
        ),
    ]
    
    @computed_field  # type: ignore[misc]
    @property
    def total_reviews(self) -> int:
        """Calculate total number of reviews."""
        return (
            self.rating_5_count
            + self.rating_4_count
            + self.rating_3_count
            + self.rating_2_count
            + self.rating_1_count
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def recommendation_score(self) -> Decimal:
        """
        Calculate recommendation score.
        
        Based on ratio of positive reviews to total reviews.
        """
        if self.total_reviews == 0:
            return Decimal("0")
        return Decimal(
            str(round((self.positive_reviews / self.total_reviews) * 100, 2))
        )


class TrendAnalysis(BaseSchema):
    """
    Rating trend analysis over time.
    
    Tracks rating changes and provides directional indicators.
    """
    
    trend_direction: str = Field(
        ...,
        pattern=r"^(improving|declining|stable)$",
        description="Overall trend direction",
    )
    trend_percentage: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("-100"),
                le=Decimal("100"),
                max_digits=5,
                decimal_places=2,
                description="Percentage change in rating",
            ),
        ],
        None,
    ] = None
    
    # Time-based ratings with proper constraints
    last_30_days_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="Average rating in last 30 days",
        ),
    ]
    last_90_days_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="Average rating in last 90 days",
        ),
    ]
    all_time_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="All-time average rating",
        ),
    ]
    
    # Monthly breakdown
    monthly_ratings: List[MonthlyRating] = Field(
        default_factory=list,
        description="Monthly rating history",
    )
    
    @field_validator("trend_direction")
    @classmethod
    def normalize_trend(cls, v: str) -> str:
        """Normalize trend direction to lowercase."""
        return v.lower().strip()
    
    @classmethod
    def calculate_trend(
        cls,
        current_rating: Decimal,
        previous_rating: Decimal,
        threshold: Decimal = Decimal("0.1"),
    ) -> str:
        """
        Calculate trend direction based on rating change.
        
        Args:
            current_rating: Current period average rating
            previous_rating: Previous period average rating
            threshold: Minimum change to consider as trend
            
        Returns:
            Trend direction: improving, declining, or stable
        """
        difference = current_rating - previous_rating
        
        if abs(difference) < threshold:
            return "stable"
        return "improving" if difference > 0 else "declining"


class SentimentAnalysis(BaseSchema):
    """
    Sentiment analysis of review content.
    
    Provides AI-powered sentiment scoring and theme extraction.
    """
    
    overall_sentiment: str = Field(
        ...,
        pattern=r"^(positive|neutral|negative)$",
        description="Overall sentiment classification",
    )
    
    sentiment_score: Annotated[
        Decimal,
        Field(
            ge=Decimal("-1"),
            le=Decimal("1"),
            max_digits=4,
            decimal_places=3,
            description="Sentiment score (-1 to 1, where 1 is most positive)",
        ),
    ]
    
    # Distribution
    positive_count: int = Field(..., ge=0, description="Positive reviews count")
    neutral_count: int = Field(..., ge=0, description="Neutral reviews count")
    negative_count: int = Field(..., ge=0, description="Negative reviews count")
    
    # Themes and keywords
    positive_themes: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Common positive themes extracted from reviews",
        examples=[["clean", "friendly staff", "good food"]],
    )
    negative_themes: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Common complaints extracted from reviews",
        examples=[["noise", "maintenance issues"]],
    )
    
    most_mentioned_positive: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Most frequently mentioned positive keywords",
    )
    most_mentioned_negative: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Most frequently mentioned negative keywords",
    )
    
    @field_validator("overall_sentiment")
    @classmethod
    def normalize_sentiment(cls, v: str) -> str:
        """Normalize sentiment to lowercase."""
        return v.lower().strip()
    
    @computed_field  # type: ignore[misc]
    @property
    def total_analyzed(self) -> int:
        """Total reviews analyzed for sentiment."""
        return self.positive_count + self.neutral_count + self.negative_count
    
    @computed_field  # type: ignore[misc]
    @property
    def positive_percentage(self) -> Decimal:
        """Percentage of positive sentiment reviews."""
        if self.total_analyzed == 0:
            return Decimal("0")
        return Decimal(
            str(round((self.positive_count / self.total_analyzed) * 100, 2))
        )


class AspectAnalysis(BaseSchema):
    """
    Analysis of specific review aspects (cleanliness, food, staff, etc.).
    
    Provides granular insights into individual service aspects.
    """
    
    aspect: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Aspect name (e.g., cleanliness, food, staff)",
        examples=["cleanliness", "food_quality", "staff_behavior"],
    )
    
    average_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="Average rating for this aspect",
        ),
    ]
    total_ratings: int = Field(
        ...,
        ge=0,
        description="Total number of ratings for this aspect",
    )
    
    # Rating distribution for this aspect
    rating_distribution: Dict[int, int] = Field(
        default_factory=dict,
        description="Rating value to count mapping",
        examples=[{1: 5, 2: 10, 3: 20, 4: 40, 5: 25}],
    )
    
    # Trend
    trend: str = Field(
        ...,
        pattern=r"^(improving|declining|stable)$",
        description="Trend direction for this aspect",
    )
    
    # Mentions in review text
    mention_count: int = Field(
        ...,
        ge=0,
        description="Times this aspect was mentioned in reviews",
    )
    positive_mentions: int = Field(
        ...,
        ge=0,
        description="Positive mentions count",
    )
    negative_mentions: int = Field(
        ...,
        ge=0,
        description="Negative mentions count",
    )
    
    # Sample comments
    top_positive_comments: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top positive comments about this aspect",
    )
    top_negative_comments: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top negative comments about this aspect",
    )
    
    @field_validator("rating_distribution")
    @classmethod
    def validate_rating_keys(cls, v: Dict[int, int]) -> Dict[int, int]:
        """Ensure rating distribution keys are valid (1-5)."""
        invalid_keys = [k for k in v.keys() if k < 1 or k > 5]
        if invalid_keys:
            raise ValueError(
                f"Invalid rating keys found: {invalid_keys}. "
                "Rating keys must be between 1 and 5."
            )
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def sentiment_ratio(self) -> Decimal:
        """
        Calculate sentiment ratio for this aspect.
        
        Returns ratio of positive to total mentions.
        """
        total_mentions = self.positive_mentions + self.negative_mentions
        if total_mentions == 0:
            return Decimal("0.5")  # Neutral if no mentions
        return Decimal(
            str(round(self.positive_mentions / total_mentions, 3))
        )


class CompetitorComparison(BaseSchema):
    """
    Competitive analysis comparing hostel with nearby competitors.
    
    Provides benchmarking insights and competitive positioning.
    """
    
    hostel_id: UUID = Field(..., description="Subject hostel ID")
    hostel_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Subject hostel name",
    )
    
    # Ratings comparison with proper constraints
    this_hostel_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="This hostel's average rating",
        ),
    ]
    competitor_average_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="Average rating of competitors in area",
        ),
    ]
    
    rating_difference: Annotated[
        Decimal,
        Field(
            ge=Decimal("-4.0"),
            le=Decimal("4.0"),
            max_digits=3,
            decimal_places=2,
            description="Rating difference from competitor average",
        ),
    ]
    percentile_rank: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentile rank among competitors (0-100)",
        ),
    ]
    
    # Competitive advantages and weaknesses
    competitive_advantages: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Aspects rated higher than competitors",
        examples=[["cleanliness", "staff_behavior", "security"]],
    )
    improvement_areas: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Aspects rated lower than competitors",
        examples=[["food_quality", "wifi", "amenities"]],
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def competitive_position(self) -> str:
        """
        Determine competitive position based on percentile rank.
        
        Returns:
            Position category: leader, above_average, average, or below_average
        """
        rank = float(self.percentile_rank)
        if rank >= 75:
            return "leader"
        elif rank >= 60:
            return "above_average"
        elif rank >= 40:
            return "average"
        else:
            return "below_average"
    
    @computed_field  # type: ignore[misc]
    @property
    def is_outperforming(self) -> bool:
        """Check if hostel is outperforming competitors."""
        return self.rating_difference > Decimal("0")


class ReviewAnalytics(BaseSchema):
    """
    Comprehensive review analytics for a hostel.
    
    Aggregates all review metrics, trends, and insights.
    """
    
    hostel_id: UUID = Field(..., description="Hostel identifier")
    hostel_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hostel name",
    )
    
    # Analysis period
    analysis_period: Union[DateRangeFilter, None] = Field(
        default=None,
        description="Period for which analytics are calculated",
    )
    generated_at: datetime = Field(
        ...,
        description="Analytics generation timestamp",
    )
    
    # Summary metrics
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total number of reviews",
    )
    average_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="Overall average rating",
        ),
    ]
    
    # Detailed breakdowns
    rating_distribution: RatingDistribution = Field(
        ...,
        description="Rating distribution across 1-5 stars",
    )
    
    # Aspect ratings with proper Decimal constraints
    detailed_ratings_average: Dict[str, Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
        ),
    ]] = Field(
        default_factory=dict,
        description="Average ratings by aspect (cleanliness, food, etc.)",
        examples=[
            {
                "cleanliness": Decimal("4.5"),
                "food_quality": Decimal("4.2"),
                "staff_behavior": Decimal("4.7"),
            }
        ],
    )
    
    # Trends
    rating_trend: TrendAnalysis = Field(
        ...,
        description="Rating trend analysis over time",
    )
    
    # Sentiment
    sentiment_analysis: Union[SentimentAnalysis, None] = Field(
        default=None,
        description="AI-powered sentiment analysis",
    )
    
    # Verification metrics
    verified_reviews_count: int = Field(
        ...,
        ge=0,
        description="Number of verified reviews",
    )
    verification_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of reviews that are verified",
        ),
    ]
    
    # Engagement metrics
    average_helpful_votes: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            max_digits=8,
            decimal_places=2,
            description="Average helpful votes per review",
        ),
    ]
    response_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of reviews with hostel responses",
        ),
    ]
    
    @field_validator("detailed_ratings_average")
    @classmethod
    def validate_aspect_ratings(cls, v: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """Validate aspect ratings are within valid range."""
        for aspect, rating in v.items():
            if not (Decimal("1.0") <= rating <= Decimal("5.0")):
                raise ValueError(
                    f"Rating for '{aspect}' must be between 1.0 and 5.0, "
                    f"got {rating}"
                )
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def quality_score(self) -> Decimal:
        """
        Calculate overall quality score (0-100).
        
        Composite score based on rating, verification rate, and engagement.
        """
        # Base score from rating (max 70 points)
        rating_score = (float(self.average_rating) / 5.0) * 70
        
        # Verification bonus (max 15 points)
        verification_score = (float(self.verification_rate) / 100) * 15
        
        # Engagement bonus (max 15 points)
        engagement_score = min(
            (float(self.average_helpful_votes) / 10) * 15, 15
        )
        
        total = rating_score + verification_score + engagement_score
        return Decimal(str(round(total, 2)))
    
    @computed_field  # type: ignore[misc]
    @property
    def health_indicator(self) -> str:
        """
        Overall review health indicator.
        
        Returns:
            Health status: excellent, good, fair, or poor
        """
        score = float(self.quality_score)
        if score >= 80:
            return "excellent"
        elif score >= 65:
            return "good"
        elif score >= 50:
            return "fair"
        else:
            return "poor"