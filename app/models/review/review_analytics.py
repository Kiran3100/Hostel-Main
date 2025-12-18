# --- File: C:\Hostel-Main\app\models\review\review_analytics.py ---
"""
Review analytics models for comprehensive review insights.

Implements analytics, trends, sentiment analysis, and competitive comparison.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, validates

from app.models.base import BaseModel, TimestampMixin

__all__ = [
    "ReviewAnalyticsSummary",
    "RatingDistribution",
    "ReviewTrend",
    "MonthlyRating",
    "SentimentAnalysis",
    "AspectRating",
    "CompetitorComparison",
]


class ReviewAnalyticsSummary(BaseModel, TimestampMixin):
    """
    Comprehensive review analytics summary for hostels.
    
    Aggregates all review metrics and insights.
    """
    
    __tablename__ = "review_analytics_summary"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Analysis period
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    
    # Summary metrics
    total_reviews = Column(Integer, default=0, nullable=False)
    average_rating = Column(
        Numeric(precision=3, scale=2),
        default=0,
        nullable=False,
        index=True,
    )
    
    # Verification metrics
    verified_reviews_count = Column(Integer, default=0, nullable=False)
    verification_rate = Column(
        Numeric(precision=5, scale=2),
        default=0,
        nullable=False,
    )
    
    # Engagement metrics
    total_votes = Column(Integer, default=0, nullable=False)
    average_helpful_votes = Column(
        Numeric(precision=8, scale=2),
        default=0,
        nullable=False,
    )
    
    # Response metrics
    response_rate = Column(
        Numeric(precision=5, scale=2),
        default=0,
        nullable=False,
    )
    average_response_time_hours = Column(
        Numeric(precision=8, scale=2),
        nullable=True,
    )
    
    # Quality metrics
    quality_score = Column(
        Numeric(precision=5, scale=2),
        default=0,
        nullable=False,
        index=True,
    )
    health_indicator = Column(String(20), nullable=True)
    # Indicators: excellent, good, fair, poor
    
    # Recommendation metric
    would_recommend_percentage = Column(
        Numeric(precision=5, scale=2),
        default=0,
        nullable=False,
    )
    
    # Detailed ratings averages
    avg_cleanliness = Column(Numeric(precision=3, scale=2), nullable=True)
    avg_food_quality = Column(Numeric(precision=3, scale=2), nullable=True)
    avg_staff_behavior = Column(Numeric(precision=3, scale=2), nullable=True)
    avg_security = Column(Numeric(precision=3, scale=2), nullable=True)
    avg_value_for_money = Column(Numeric(precision=3, scale=2), nullable=True)
    avg_amenities = Column(Numeric(precision=3, scale=2), nullable=True)
    avg_location = Column(Numeric(precision=3, scale=2), nullable=True)
    avg_wifi_quality = Column(Numeric(precision=3, scale=2), nullable=True)
    avg_maintenance = Column(Numeric(precision=3, scale=2), nullable=True)
    
    # Trend indicators
    trend_direction = Column(String(20), nullable=True)
    # Directions: improving, declining, stable
    
    trend_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
    )
    
    # Time-based ratings
    last_30_days_rating = Column(Numeric(precision=3, scale=2), nullable=True)
    last_90_days_rating = Column(Numeric(precision=3, scale=2), nullable=True)
    all_time_rating = Column(Numeric(precision=3, scale=2), nullable=True)
    
    # Sentiment metrics
    positive_sentiment_count = Column(Integer, default=0, nullable=False)
    neutral_sentiment_count = Column(Integer, default=0, nullable=False)
    negative_sentiment_count = Column(Integer, default=0, nullable=False)
    
    overall_sentiment_score = Column(
        Numeric(precision=4, scale=3),
        nullable=True,
    )
    
    # Top themes
    positive_themes = Column(ARRAY(String), default=list, server_default='{}')
    negative_themes = Column(ARRAY(String), default=list, server_default='{}')
    
    # Calculation metadata
    generated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    last_calculated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    calculation_version = Column(String(20), default='1.0', nullable=False)
    
    # Additional metadata
    metadata = Column(JSONB, nullable=True)
    
    __table_args__ = (
        CheckConstraint(
            "total_reviews >= 0",
            name="check_total_reviews_positive",
        ),
        CheckConstraint(
            "average_rating >= 1 AND average_rating <= 5",
            name="check_average_rating_range",
        ),
        CheckConstraint(
            "verification_rate >= 0 AND verification_rate <= 100",
            name="check_verification_rate_range",
        ),
        CheckConstraint(
            "response_rate >= 0 AND response_rate <= 100",
            name="check_response_rate_range",
        ),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 100",
            name="check_quality_score_range",
        ),
        CheckConstraint(
            "would_recommend_percentage >= 0 AND would_recommend_percentage <= 100",
            name="check_recommend_percentage_range",
        ),
        Index("idx_quality_rating", "quality_score", "average_rating"),
    )
    
    @validates("health_indicator")
    def validate_health_indicator(self, key, value):
        """Validate health indicator."""
        if value is None:
            return value
        valid_indicators = {'excellent', 'good', 'fair', 'poor'}
        if value.lower() not in valid_indicators:
            raise ValueError(f"Invalid health indicator: {value}")
        return value.lower()
    
    @validates("trend_direction")
    def validate_trend_direction(self, key, value):
        """Validate trend direction."""
        if value is None:
            return value
        valid_directions = {'improving', 'declining', 'stable'}
        if value.lower() not in valid_directions:
            raise ValueError(f"Invalid trend direction: {value}")
        return value.lower()
    
    def calculate_quality_score(self):
        """Calculate overall quality score (0-100)."""
        # Base score from rating (max 70 points)
        rating_score = (float(self.average_rating) / 5.0) * 70
        
        # Verification bonus (max 15 points)
        verification_score = (float(self.verification_rate) / 100) * 15
        
        # Engagement bonus (max 15 points)
        engagement_score = min(
            (float(self.average_helpful_votes) / 10) * 15, 15
        )
        
        total = rating_score + verification_score + engagement_score
        self.quality_score = Decimal(str(round(total, 2)))
    
    def determine_health_indicator(self):
        """Determine health indicator based on quality score."""
        score = float(self.quality_score)
        if score >= 80:
            self.health_indicator = 'excellent'
        elif score >= 65:
            self.health_indicator = 'good'
        elif score >= 50:
            self.health_indicator = 'fair'
        else:
            self.health_indicator = 'poor'
    
    def __repr__(self):
        return (
            f"<ReviewAnalyticsSummary(hostel_id={self.hostel_id}, "
            f"rating={self.average_rating}, reviews={self.total_reviews})>"
        )


class RatingDistribution(BaseModel, TimestampMixin):
    """
    Rating distribution breakdown for hostels.
    
    Provides detailed analysis of rating spread.
    """
    
    __tablename__ = "rating_distributions"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Raw counts
    rating_5_count = Column(Integer, default=0, nullable=False)
    rating_4_count = Column(Integer, default=0, nullable=False)
    rating_3_count = Column(Integer, default=0, nullable=False)
    rating_2_count = Column(Integer, default=0, nullable=False)
    rating_1_count = Column(Integer, default=0, nullable=False)
    
    # Percentages
    rating_5_percentage = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    rating_4_percentage = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    rating_3_percentage = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    rating_2_percentage = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    rating_1_percentage = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    
    # Aggregated categories
    positive_reviews = Column(Integer, default=0, nullable=False)  # 4-5 stars
    neutral_reviews = Column(Integer, default=0, nullable=False)   # 3 stars
    negative_reviews = Column(Integer, default=0, nullable=False)  # 1-2 stars
    
    positive_percentage = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    neutral_percentage = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    negative_percentage = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    
    # Recommendation score (based on positive reviews)
    recommendation_score = Column(
        Numeric(precision=5, scale=2),
        default=0,
        nullable=False,
    )
    
    # Calculation metadata
    last_calculated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    __table_args__ = (
        CheckConstraint(
            "rating_5_count >= 0",
            name="check_rating_5_count_positive",
        ),
        CheckConstraint(
            "rating_4_count >= 0",
            name="check_rating_4_count_positive",
        ),
        CheckConstraint(
            "rating_3_count >= 0",
            name="check_rating_3_count_positive",
        ),
        CheckConstraint(
            "rating_2_count >= 0",
            name="check_rating_2_count_positive",
        ),
        CheckConstraint(
            "rating_1_count >= 0",
            name="check_rating_1_count_positive",
        ),
    )
    
    def calculate_percentages(self):
        """Calculate rating percentages."""
        total = (
            self.rating_5_count + self.rating_4_count + 
            self.rating_3_count + self.rating_2_count + 
            self.rating_1_count
        )
        
        if total == 0:
            return
        
        self.rating_5_percentage = Decimal(str(round((self.rating_5_count / total) * 100, 2)))
        self.rating_4_percentage = Decimal(str(round((self.rating_4_count / total) * 100, 2)))
        self.rating_3_percentage = Decimal(str(round((self.rating_3_count / total) * 100, 2)))
        self.rating_2_percentage = Decimal(str(round((self.rating_2_count / total) * 100, 2)))
        self.rating_1_percentage = Decimal(str(round((self.rating_1_count / total) * 100, 2)))
        
        # Calculate aggregated categories
        self.positive_reviews = self.rating_5_count + self.rating_4_count
        self.neutral_reviews = self.rating_3_count
        self.negative_reviews = self.rating_2_count + self.rating_1_count
        
        self.positive_percentage = Decimal(str(round((self.positive_reviews / total) * 100, 2)))
        self.neutral_percentage = Decimal(str(round((self.neutral_reviews / total) * 100, 2)))
        self.negative_percentage = Decimal(str(round((self.negative_reviews / total) * 100, 2)))
        
        # Calculate recommendation score
        self.recommendation_score = self.positive_percentage
    
    def __repr__(self):
        return (
            f"<RatingDistribution(hostel_id={self.hostel_id}, "
            f"positive={self.positive_percentage}%)>"
        )


class ReviewTrend(BaseModel, TimestampMixin):
    """
    Review trend analysis over time.
    
    Tracks rating changes and directional indicators.
    """
    
    __tablename__ = "review_trends"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Trend analysis
    trend_direction = Column(String(20), nullable=False)
    # Directions: improving, declining, stable
    
    trend_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
    )
    
    # Time-based ratings
    last_30_days_rating = Column(
        Numeric(precision=3, scale=2),
        nullable=True,
    )
    last_90_days_rating = Column(
        Numeric(precision=3, scale=2),
        nullable=True,
    )
    all_time_rating = Column(
        Numeric(precision=3, scale=2),
        nullable=True,
    )
    
    # Volume trends
    last_30_days_count = Column(Integer, default=0, nullable=False)
    last_90_days_count = Column(Integer, default=0, nullable=False)
    
    # Calculation period
    calculated_for_date = Column(Date, nullable=False, index=True)
    
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "calculated_for_date",
            name="uq_hostel_trend_date",
        ),
        Index("idx_hostel_date", "hostel_id", "calculated_for_date"),
    )
    
    @validates("trend_direction")
    def validate_trend_direction(self, key, value):
        """Validate trend direction."""
        valid_directions = {'improving', 'declining', 'stable'}
        if value.lower() not in valid_directions:
            raise ValueError(f"Invalid trend direction: {value}")
        return value.lower()
    
    def __repr__(self):
        return (
            f"<ReviewTrend(hostel_id={self.hostel_id}, "
            f"direction={self.trend_direction}, date={self.calculated_for_date})>"
        )


class MonthlyRating(BaseModel, TimestampMixin):
    """
    Monthly rating aggregation.
    
    Tracks average rating and review volume by month.
    """
    
    __tablename__ = "monthly_ratings"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Month in YYYY-MM format
    month = Column(String(7), nullable=False, index=True)
    
    # Metrics
    average_rating = Column(
        Numeric(precision=3, scale=2),
        nullable=False,
    )
    review_count = Column(Integer, default=0, nullable=False)
    
    # Detailed breakdowns
    verified_count = Column(Integer, default=0, nullable=False)
    with_response_count = Column(Integer, default=0, nullable=False)
    
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "month",
            name="uq_hostel_month",
        ),
        CheckConstraint(
            "average_rating >= 1 AND average_rating <= 5",
            name="check_monthly_rating_range",
        ),
        CheckConstraint(
            "review_count >= 0",
            name="check_monthly_count_positive",
        ),
        Index("idx_hostel_month", "hostel_id", "month"),
    )
    
    @validates("month")
    def validate_month_format(self, key, value):
        """Validate month format (YYYY-MM)."""
        import re
        if not re.match(r'^\d{4}-\d{2}$', value):
            raise ValueError("Month must be in YYYY-MM format")
        
        # Validate month range
        year, month = value.split('-')
        if not (1 <= int(month) <= 12):
            raise ValueError("Month must be between 01 and 12")
        
        return value
    
    def __repr__(self):
        return (
            f"<MonthlyRating(hostel_id={self.hostel_id}, "
            f"month={self.month}, rating={self.average_rating})>"
        )


class SentimentAnalysis(BaseModel, TimestampMixin):
    """
    Sentiment analysis of review content.
    
    AI-powered sentiment scoring and theme extraction.
    """
    
    __tablename__ = "sentiment_analysis"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Overall sentiment
    overall_sentiment = Column(String(20), nullable=False)
    # Sentiments: positive, neutral, negative
    
    sentiment_score = Column(
        Numeric(precision=4, scale=3),
        nullable=False,
    )
    
    # Distribution
    positive_count = Column(Integer, default=0, nullable=False)
    neutral_count = Column(Integer, default=0, nullable=False)
    negative_count = Column(Integer, default=0, nullable=False)
    
    # Themes and keywords
    positive_themes = Column(ARRAY(String), default=list, server_default='{}')
    negative_themes = Column(ARRAY(String), default=list, server_default='{}')
    
    most_mentioned_positive = Column(ARRAY(String), default=list, server_default='{}')
    most_mentioned_negative = Column(ARRAY(String), default=list, server_default='{}')
    
    # Analysis metadata
    analyzed_reviews_count = Column(Integer, default=0, nullable=False)
    last_analyzed_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    analysis_version = Column(String(20), default='1.0', nullable=False)
    
    __table_args__ = (
        CheckConstraint(
            "sentiment_score >= -1 AND sentiment_score <= 1",
            name="check_sentiment_score_range",
        ),
        CheckConstraint(
            "positive_count >= 0",
            name="check_positive_count_positive",
        ),
        CheckConstraint(
            "neutral_count >= 0",
            name="check_neutral_count_positive",
        ),
        CheckConstraint(
            "negative_count >= 0",
            name="check_negative_count_positive",
        ),
    )
    
    @validates("overall_sentiment")
    def validate_overall_sentiment(self, key, value):
        """Validate overall sentiment."""
        valid_sentiments = {'positive', 'neutral', 'negative'}
        if value.lower() not in valid_sentiments:
            raise ValueError(f"Invalid sentiment: {value}")
        return value.lower()
    
    def __repr__(self):
        return (
            f"<SentimentAnalysis(hostel_id={self.hostel_id}, "
            f"sentiment={self.overall_sentiment}, score={self.sentiment_score})>"
        )


class AspectRating(BaseModel, TimestampMixin):
    """
    Analysis of specific review aspects.
    
    Granular insights into individual service aspects.
    """
    
    __tablename__ = "aspect_ratings"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Aspect details
    aspect = Column(String(100), nullable=False)
    # Aspects: cleanliness, food_quality, staff_behavior, security, etc.
    
    average_rating = Column(
        Numeric(precision=3, scale=2),
        nullable=False,
    )
    total_ratings = Column(Integer, default=0, nullable=False)
    
    # Rating distribution
    rating_distribution = Column(JSONB, nullable=True)
    # Format: {1: 5, 2: 10, 3: 20, 4: 40, 5: 25}
    
    # Trend
    trend = Column(String(20), nullable=False)
    # Trends: improving, declining, stable
    
    # Mentions
    mention_count = Column(Integer, default=0, nullable=False)
    positive_mentions = Column(Integer, default=0, nullable=False)
    negative_mentions = Column(Integer, default=0, nullable=False)
    
    # Sample comments
    top_positive_comments = Column(ARRAY(String), default=list, server_default='{}')
    top_negative_comments = Column(ARRAY(String), default=list, server_default='{}')
    
    # Calculation metadata
    last_calculated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "aspect",
            name="uq_hostel_aspect",
        ),
        CheckConstraint(
            "average_rating >= 1 AND average_rating <= 5",
            name="check_aspect_rating_range",
        ),
        CheckConstraint(
            "total_ratings >= 0",
            name="check_total_ratings_positive",
        ),
        Index("idx_hostel_aspect_rating", "hostel_id", "aspect", "average_rating"),
    )
    
    @validates("aspect")
    def validate_aspect(self, key, value):
        """Validate aspect name."""
        valid_aspects = {
            'cleanliness', 'food_quality', 'staff_behavior', 'security',
            'value_for_money', 'amenities', 'location', 'wifi_quality',
            'maintenance'
        }
        if value.lower() not in valid_aspects:
            raise ValueError(f"Invalid aspect: {value}")
        return value.lower()
    
    @validates("trend")
    def validate_trend(self, key, value):
        """Validate trend."""
        valid_trends = {'improving', 'declining', 'stable'}
        if value.lower() not in valid_trends:
            raise ValueError(f"Invalid trend: {value}")
        return value.lower()
    
    def calculate_sentiment_ratio(self) -> Decimal:
        """Calculate sentiment ratio for this aspect."""
        total_mentions = self.positive_mentions + self.negative_mentions
        if total_mentions == 0:
            return Decimal("0.5")  # Neutral
        return Decimal(str(round(self.positive_mentions / total_mentions, 3)))
    
    def __repr__(self):
        return (
            f"<AspectRating(hostel_id={self.hostel_id}, "
            f"aspect={self.aspect}, rating={self.average_rating})>"
        )


class CompetitorComparison(BaseModel, TimestampMixin):
    """
    Competitive analysis comparing hostel with nearby competitors.
    
    Benchmarking insights and competitive positioning.
    """
    
    __tablename__ = "competitor_comparisons"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Comparison period
    comparison_date = Column(Date, nullable=False, index=True)
    
    # Ratings comparison
    this_hostel_rating = Column(
        Numeric(precision=3, scale=2),
        nullable=False,
    )
    competitor_average_rating = Column(
        Numeric(precision=3, scale=2),
        nullable=False,
    )
    rating_difference = Column(
        Numeric(precision=3, scale=2),
        nullable=False,
    )
    
    # Competitive positioning
    percentile_rank = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
    )
    # 0-100, where higher is better
    
    competitive_position = Column(String(20), nullable=False)
    # Positions: leader, above_average, average, below_average
    
    # Competitive advantages and weaknesses
    competitive_advantages = Column(ARRAY(String), default=list, server_default='{}')
    improvement_areas = Column(ARRAY(String), default=list, server_default='{}')
    
    # Competitor context
    total_competitors = Column(Integer, default=0, nullable=False)
    competitors_analyzed = Column(ARRAY(String), default=list, server_default='{}')
    
    # Market insights
    market_average_rating = Column(
        Numeric(precision=3, scale=2),
        nullable=True,
    )
    market_total_reviews = Column(Integer, default=0, nullable=False)
    
    # Calculation metadata
    last_calculated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "comparison_date",
            name="uq_hostel_comparison_date",
        ),
        CheckConstraint(
            "percentile_rank >= 0 AND percentile_rank <= 100",
            name="check_percentile_range",
        ),
        CheckConstraint(
            "total_competitors >= 0",
            name="check_competitors_positive",
        ),
        Index("idx_hostel_comparison_date", "hostel_id", "comparison_date"),
    )
    
    @validates("competitive_position")
    def validate_position(self, key, value):
        """Validate competitive position."""
        valid_positions = {'leader', 'above_average', 'average', 'below_average'}
        if value.lower() not in valid_positions:
            raise ValueError(f"Invalid competitive position: {value}")
        return value.lower()
    
    def is_outperforming(self) -> bool:
        """Check if hostel is outperforming competitors."""
        return self.rating_difference > Decimal("0")
    
    def __repr__(self):
        return (
            f"<CompetitorComparison(hostel_id={self.hostel_id}, "
            f"position={self.competitive_position}, rank={self.percentile_rank})>"
        )