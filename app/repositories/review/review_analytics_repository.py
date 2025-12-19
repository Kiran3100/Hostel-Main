"""
Review Analytics Repository - Comprehensive analytics and insights.

Implements analytics calculations, trend analysis, sentiment tracking,
and competitive comparisons.
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc, case, extract
from sqlalchemy.orm import Session

from app.models.review import Review
from app.models.review.review_analytics import (
    ReviewAnalyticsSummary,
    RatingDistribution,
    ReviewTrend,
    MonthlyRating,
    SentimentAnalysis,
    AspectRating,
    CompetitorComparison,
)
from app.repositories.base import BaseRepository


class ReviewAnalyticsRepository(BaseRepository[ReviewAnalyticsSummary]):
    """
    Repository for review analytics operations.
    
    Provides comprehensive analytics including ratings distribution,
    trends, sentiment analysis, and competitive insights.
    """
    
    def __init__(self, session: Session):
        """
        Initialize review analytics repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ReviewAnalyticsSummary, session)
    
    # ==================== Analytics Summary Operations ====================
    
    def calculate_analytics_summary(
        self,
        hostel_id: UUID,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None
    ) -> ReviewAnalyticsSummary:
        """
        Calculate comprehensive analytics summary for hostel.
        
        Args:
            hostel_id: Hostel ID
            period_start: Optional period start date
            period_end: Optional period end date
            
        Returns:
            Analytics summary
        """
        # Get or create summary
        summary = self.session.query(ReviewAnalyticsSummary).filter(
            ReviewAnalyticsSummary.hostel_id == hostel_id
        ).first()
        
        if not summary:
            summary = ReviewAnalyticsSummary(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end
            )
            self.session.add(summary)
        
        # Build query for published reviews
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        if period_start:
            query = query.filter(Review.created_at >= datetime.combine(period_start, datetime.min.time()))
        if period_end:
            query = query.filter(Review.created_at <= datetime.combine(period_end, datetime.max.time()))
        
        # Calculate basic metrics
        total_reviews = query.count()
        summary.total_reviews = total_reviews
        
        if total_reviews == 0:
            summary.average_rating = Decimal('0')
            summary.quality_score = Decimal('0')
            summary.health_indicator = 'poor'
            self.session.commit()
            return summary
        
        # Calculate average rating
        avg_rating = query.with_entities(
            func.avg(Review.overall_rating)
        ).scalar()
        summary.average_rating = Decimal(str(avg_rating)).quantize(Decimal('0.01'))
        
        # Verification metrics
        verified_count = query.filter(Review.is_verified_stay == True).count()
        summary.verified_reviews_count = verified_count
        summary.verification_rate = Decimal(
            str(verified_count / total_reviews * 100)
        ).quantize(Decimal('0.01'))
        
        # Engagement metrics
        total_votes = query.with_entities(
            func.sum(Review.helpful_count + Review.not_helpful_count)
        ).scalar() or 0
        summary.total_votes = int(total_votes)
        
        avg_helpful = query.with_entities(
            func.avg(Review.helpful_count)
        ).scalar() or 0
        summary.average_helpful_votes = Decimal(str(avg_helpful)).quantize(Decimal('0.01'))
        
        # Response metrics
        from app.models.review.review_response import ReviewResponse
        responses_count = self.session.query(ReviewResponse).join(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True
        ).count()
        
        summary.response_rate = Decimal(
            str(responses_count / total_reviews * 100)
        ).quantize(Decimal('0.01'))
        
        # Calculate average response time
        avg_response_time = self.session.query(ReviewResponse).join(Review).filter(
            Review.hostel_id == hostel_id,
            ReviewResponse.response_time_hours.isnot(None)
        ).with_entities(
            func.avg(ReviewResponse.response_time_hours)
        ).scalar()
        
        if avg_response_time:
            summary.average_response_time_hours = Decimal(str(avg_response_time)).quantize(Decimal('0.01'))
        
        # Recommendation metric
        would_recommend_count = query.filter(Review.would_recommend == True).count()
        summary.would_recommend_percentage = Decimal(
            str(would_recommend_count / total_reviews * 100)
        ).quantize(Decimal('0.01'))
        
        # Calculate aspect ratings averages
        aspect_avgs = query.with_entities(
            func.avg(Review.cleanliness_rating).label('cleanliness'),
            func.avg(Review.food_quality_rating).label('food_quality'),
            func.avg(Review.staff_behavior_rating).label('staff_behavior'),
            func.avg(Review.security_rating).label('security'),
            func.avg(Review.value_for_money_rating).label('value_for_money'),
            func.avg(Review.amenities_rating).label('amenities'),
            func.avg(Review.location_rating).label('location'),
            func.avg(Review.wifi_quality_rating).label('wifi_quality'),
            func.avg(Review.maintenance_rating).label('maintenance')
        ).first()
        
        summary.avg_cleanliness = Decimal(str(aspect_avgs.cleanliness or 0)).quantize(Decimal('0.01'))
        summary.avg_food_quality = Decimal(str(aspect_avgs.food_quality or 0)).quantize(Decimal('0.01'))
        summary.avg_staff_behavior = Decimal(str(aspect_avgs.staff_behavior or 0)).quantize(Decimal('0.01'))
        summary.avg_security = Decimal(str(aspect_avgs.security or 0)).quantize(Decimal('0.01'))
        summary.avg_value_for_money = Decimal(str(aspect_avgs.value_for_money or 0)).quantize(Decimal('0.01'))
        summary.avg_amenities = Decimal(str(aspect_avgs.amenities or 0)).quantize(Decimal('0.01'))
        summary.avg_location = Decimal(str(aspect_avgs.location or 0)).quantize(Decimal('0.01'))
        summary.avg_wifi_quality = Decimal(str(aspect_avgs.wifi_quality or 0)).quantize(Decimal('0.01'))
        summary.avg_maintenance = Decimal(str(aspect_avgs.maintenance or 0)).quantize(Decimal('0.01'))
        
        # Time-based ratings
        now = datetime.utcnow()
        
        # Last 30 days
        last_30_days = query.filter(
            Review.created_at >= now - timedelta(days=30)
        ).with_entities(func.avg(Review.overall_rating)).scalar()
        summary.last_30_days_rating = Decimal(str(last_30_days or 0)).quantize(Decimal('0.01'))
        
        # Last 90 days
        last_90_days = query.filter(
            Review.created_at >= now - timedelta(days=90)
        ).with_entities(func.avg(Review.overall_rating)).scalar()
        summary.last_90_days_rating = Decimal(str(last_90_days or 0)).quantize(Decimal('0.01'))
        
        # All time
        summary.all_time_rating = summary.average_rating
        
        # Calculate trend
        if summary.last_30_days_rating > summary.last_90_days_rating:
            summary.trend_direction = 'improving'
            summary.trend_percentage = Decimal(
                str((summary.last_30_days_rating - summary.last_90_days_rating) / summary.last_90_days_rating * 100)
            ).quantize(Decimal('0.01')) if summary.last_90_days_rating > 0 else Decimal('0')
        elif summary.last_30_days_rating < summary.last_90_days_rating:
            summary.trend_direction = 'declining'
            summary.trend_percentage = Decimal(
                str((summary.last_90_days_rating - summary.last_30_days_rating) / summary.last_90_days_rating * 100)
            ).quantize(Decimal('0.01')) if summary.last_90_days_rating > 0 else Decimal('0')
        else:
            summary.trend_direction = 'stable'
            summary.trend_percentage = Decimal('0')
        
        # Sentiment metrics (placeholder - would use actual sentiment analysis)
        positive_count = query.filter(Review.overall_rating >= 4).count()
        neutral_count = query.filter(
            Review.overall_rating >= 3,
            Review.overall_rating < 4
        ).count()
        negative_count = query.filter(Review.overall_rating < 3).count()
        
        summary.positive_sentiment_count = positive_count
        summary.neutral_sentiment_count = neutral_count
        summary.negative_sentiment_count = negative_count
        
        # Calculate quality score and health indicator
        summary.calculate_quality_score()
        summary.determine_health_indicator()
        
        # Update timestamps
        summary.last_calculated_at = datetime.utcnow()
        summary.generated_at = datetime.utcnow()
        
        self.session.commit()
        self.session.refresh(summary)
        
        return summary
    
    def get_analytics_summary(
        self,
        hostel_id: UUID
    ) -> Optional[ReviewAnalyticsSummary]:
        """
        Get analytics summary for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Analytics summary if exists
        """
        return self.session.query(ReviewAnalyticsSummary).filter(
            ReviewAnalyticsSummary.hostel_id == hostel_id
        ).first()
    
    # ==================== Rating Distribution Operations ====================
    
    def calculate_rating_distribution(
        self,
        hostel_id: UUID
    ) -> RatingDistribution:
        """
        Calculate rating distribution for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Rating distribution
        """
        # Get or create distribution
        distribution = self.session.query(RatingDistribution).filter(
            RatingDistribution.hostel_id == hostel_id
        ).first()
        
        if not distribution:
            distribution = RatingDistribution(hostel_id=hostel_id)
            self.session.add(distribution)
        
        # Count reviews by rating
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        # Count each rating (rounded to nearest integer for distribution)
        rating_5 = query.filter(Review.overall_rating >= 4.5).count()
        rating_4 = query.filter(
            Review.overall_rating >= 3.5,
            Review.overall_rating < 4.5
        ).count()
        rating_3 = query.filter(
            Review.overall_rating >= 2.5,
            Review.overall_rating < 3.5
        ).count()
        rating_2 = query.filter(
            Review.overall_rating >= 1.5,
            Review.overall_rating < 2.5
        ).count()
        rating_1 = query.filter(Review.overall_rating < 1.5).count()
        
        distribution.rating_5_count = rating_5
        distribution.rating_4_count = rating_4
        distribution.rating_3_count = rating_3
        distribution.rating_2_count = rating_2
        distribution.rating_1_count = rating_1
        
        # Calculate percentages
        distribution.calculate_percentages()
        
        distribution.last_calculated_at = datetime.utcnow()
        
        self.session.commit()
        self.session.refresh(distribution)
        
        return distribution
    
    def get_rating_distribution(
        self,
        hostel_id: UUID
    ) -> Optional[RatingDistribution]:
        """
        Get rating distribution for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Rating distribution if exists
        """
        return self.session.query(RatingDistribution).filter(
            RatingDistribution.hostel_id == hostel_id
        ).first()
    
    # ==================== Trend Analysis Operations ====================
    
    def calculate_review_trend(
        self,
        hostel_id: UUID,
        calculation_date: date
    ) -> ReviewTrend:
        """
        Calculate review trend for specific date.
        
        Args:
            hostel_id: Hostel ID
            calculation_date: Date for calculation
            
        Returns:
            Review trend
        """
        # Get or create trend
        trend = self.session.query(ReviewTrend).filter(
            ReviewTrend.hostel_id == hostel_id,
            ReviewTrend.calculated_for_date == calculation_date
        ).first()
        
        if not trend:
            trend = ReviewTrend(
                hostel_id=hostel_id,
                calculated_for_date=calculation_date
            )
            self.session.add(trend)
        
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        calc_datetime = datetime.combine(calculation_date, datetime.max.time())
        
        # Last 30 days
        last_30_start = calc_datetime - timedelta(days=30)
        last_30_query = query.filter(
            Review.created_at >= last_30_start,
            Review.created_at <= calc_datetime
        )
        trend.last_30_days_count = last_30_query.count()
        avg_30 = last_30_query.with_entities(func.avg(Review.overall_rating)).scalar()
        trend.last_30_days_rating = Decimal(str(avg_30 or 0)).quantize(Decimal('0.01'))
        
        # Last 90 days
        last_90_start = calc_datetime - timedelta(days=90)
        last_90_query = query.filter(
            Review.created_at >= last_90_start,
            Review.created_at <= calc_datetime
        )
        trend.last_90_days_count = last_90_query.count()
        avg_90 = last_90_query.with_entities(func.avg(Review.overall_rating)).scalar()
        trend.last_90_days_rating = Decimal(str(avg_90 or 0)).quantize(Decimal('0.01'))
        
        # All time
        all_time_query = query.filter(Review.created_at <= calc_datetime)
        avg_all = all_time_query.with_entities(func.avg(Review.overall_rating)).scalar()
        trend.all_time_rating = Decimal(str(avg_all or 0)).quantize(Decimal('0.01'))
        
        # Determine trend direction
        if trend.last_30_days_rating > trend.last_90_days_rating:
            trend.trend_direction = 'improving'
            if trend.last_90_days_rating > 0:
                trend.trend_percentage = Decimal(
                    str((trend.last_30_days_rating - trend.last_90_days_rating) / trend.last_90_days_rating * 100)
                ).quantize(Decimal('0.01'))
        elif trend.last_30_days_rating < trend.last_90_days_rating:
            trend.trend_direction = 'declining'
            if trend.last_90_days_rating > 0:
                trend.trend_percentage = Decimal(
                    str((trend.last_90_days_rating - trend.last_30_days_rating) / trend.last_90_days_rating * 100)
                ).quantize(Decimal('0.01'))
        else:
            trend.trend_direction = 'stable'
            trend.trend_percentage = Decimal('0')
        
        self.session.commit()
        self.session.refresh(trend)
        
        return trend
    
    def get_trend_history(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[ReviewTrend]:
        """
        Get trend history for date range.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            List of trends
        """
        return self.session.query(ReviewTrend).filter(
            ReviewTrend.hostel_id == hostel_id,
            ReviewTrend.calculated_for_date >= start_date,
            ReviewTrend.calculated_for_date <= end_date
        ).order_by(asc(ReviewTrend.calculated_for_date)).all()
    
    # ==================== Monthly Rating Operations ====================
    
    def calculate_monthly_rating(
        self,
        hostel_id: UUID,
        month: str
    ) -> MonthlyRating:
        """
        Calculate monthly rating aggregation.
        
        Args:
            hostel_id: Hostel ID
            month: Month in YYYY-MM format
            
        Returns:
            Monthly rating
        """
        # Get or create monthly rating
        monthly = self.session.query(MonthlyRating).filter(
            MonthlyRating.hostel_id == hostel_id,
            MonthlyRating.month == month
        ).first()
        
        if not monthly:
            monthly = MonthlyRating(
                hostel_id=hostel_id,
                month=month
            )
            self.session.add(monthly)
        
        # Parse month
        year, month_num = map(int, month.split('-'))
        
        # Get date range for month
        from calendar import monthrange
        start_date = datetime(year, month_num, 1)
        last_day = monthrange(year, month_num)[1]
        end_date = datetime(year, month_num, last_day, 23, 59, 59)
        
        # Query reviews for month
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.created_at >= start_date,
            Review.created_at <= end_date,
            Review.deleted_at.is_(None)
        )
        
        monthly.review_count = query.count()
        
        if monthly.review_count > 0:
            avg_rating = query.with_entities(func.avg(Review.overall_rating)).scalar()
            monthly.average_rating = Decimal(str(avg_rating)).quantize(Decimal('0.01'))
            
            monthly.verified_count = query.filter(Review.is_verified_stay == True).count()
            
            # Count reviews with responses
            from app.models.review.review_response import ReviewResponse
            with_response = self.session.query(Review).join(ReviewResponse).filter(
                Review.hostel_id == hostel_id,
                Review.created_at >= start_date,
                Review.created_at <= end_date
            ).count()
            monthly.with_response_count = with_response
        else:
            monthly.average_rating = Decimal('0')
            monthly.verified_count = 0
            monthly.with_response_count = 0
        
        self.session.commit()
        self.session.refresh(monthly)
        
        return monthly
    
    def get_monthly_ratings(
        self,
        hostel_id: UUID,
        start_month: str,
        end_month: str
    ) -> List[MonthlyRating]:
        """
        Get monthly ratings for date range.
        
        Args:
            hostel_id: Hostel ID
            start_month: Start month (YYYY-MM)
            end_month: End month (YYYY-MM)
            
        Returns:
            List of monthly ratings
        """
        return self.session.query(MonthlyRating).filter(
            MonthlyRating.hostel_id == hostel_id,
            MonthlyRating.month >= start_month,
            MonthlyRating.month <= end_month
        ).order_by(asc(MonthlyRating.month)).all()
    
    # ==================== Sentiment Analysis Operations ====================
    
    def calculate_sentiment_analysis(
        self,
        hostel_id: UUID
    ) -> SentimentAnalysis:
        """
        Calculate sentiment analysis for hostel reviews.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Sentiment analysis
        """
        # Get or create sentiment analysis
        sentiment = self.session.query(SentimentAnalysis).filter(
            SentimentAnalysis.hostel_id == hostel_id
        ).first()
        
        if not sentiment:
            sentiment = SentimentAnalysis(hostel_id=hostel_id)
            self.session.add(sentiment)
        
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        # Simple sentiment classification based on rating
        # In production, would use actual NLP sentiment analysis
        positive_count = query.filter(Review.overall_rating >= 4).count()
        neutral_count = query.filter(
            Review.overall_rating >= 3,
            Review.overall_rating < 4
        ).count()
        negative_count = query.filter(Review.overall_rating < 3).count()
        
        sentiment.positive_count = positive_count
        sentiment.neutral_count = neutral_count
        sentiment.negative_count = negative_count
        
        total = positive_count + neutral_count + negative_count
        
        if total > 0:
            # Calculate weighted sentiment score (-1 to 1)
            score = (positive_count - negative_count) / total
            sentiment.sentiment_score = Decimal(str(score)).quantize(Decimal('0.001'))
            
            # Determine overall sentiment
            if sentiment.sentiment_score >= Decimal('0.2'):
                sentiment.overall_sentiment = 'positive'
            elif sentiment.sentiment_score <= Decimal('-0.2'):
                sentiment.overall_sentiment = 'negative'
            else:
                sentiment.overall_sentiment = 'neutral'
        else:
            sentiment.sentiment_score = Decimal('0')
            sentiment.overall_sentiment = 'neutral'
        
        # Extract common positive and negative themes
        # This is simplified - would use NLP in production
        positive_reviews = query.filter(Review.overall_rating >= 4).all()
        negative_reviews = query.filter(Review.overall_rating < 3).all()
        
        # Extract from pros/cons if available
        positive_themes = []
        negative_themes = []
        
        for review in positive_reviews:
            if review.pros:
                positive_themes.extend(review.pros[:3])  # Top 3 pros
        
        for review in negative_reviews:
            if review.cons:
                negative_themes.extend(review.cons[:3])  # Top 3 cons
        
        # Get most common (simplified)
        from collections import Counter
        if positive_themes:
            sentiment.positive_themes = [
                theme for theme, _ in Counter(positive_themes).most_common(5)
            ]
        
        if negative_themes:
            sentiment.negative_themes = [
                theme for theme, _ in Counter(negative_themes).most_common(5)
            ]
        
        sentiment.analyzed_reviews_count = total
        sentiment.last_analyzed_at = datetime.utcnow()
        
        self.session.commit()
        self.session.refresh(sentiment)
        
        return sentiment
    
    def get_sentiment_analysis(
        self,
        hostel_id: UUID
    ) -> Optional[SentimentAnalysis]:
        """
        Get sentiment analysis for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Sentiment analysis if exists
        """
        return self.session.query(SentimentAnalysis).filter(
            SentimentAnalysis.hostel_id == hostel_id
        ).first()
    
    # ==================== Aspect Rating Operations ====================
    
    def calculate_aspect_ratings(
        self,
        hostel_id: UUID
    ) -> List[AspectRating]:
        """
        Calculate ratings for all aspects.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of aspect ratings
        """
        aspects = [
            'cleanliness', 'food_quality', 'staff_behavior', 'security',
            'value_for_money', 'amenities', 'location', 'wifi_quality',
            'maintenance'
        ]
        
        aspect_ratings = []
        
        for aspect in aspects:
            aspect_rating = self._calculate_single_aspect_rating(hostel_id, aspect)
            aspect_ratings.append(aspect_rating)
        
        return aspect_ratings
    
    def _calculate_single_aspect_rating(
        self,
        hostel_id: UUID,
        aspect: str
    ) -> AspectRating:
        """Calculate rating for single aspect."""
        # Get or create aspect rating
        aspect_rating = self.session.query(AspectRating).filter(
            AspectRating.hostel_id == hostel_id,
            AspectRating.aspect == aspect
        ).first()
        
        if not aspect_rating:
            aspect_rating = AspectRating(
                hostel_id=hostel_id,
                aspect=aspect
            )
            self.session.add(aspect_rating)
        
        # Map aspect name to Review field
        field_map = {
            'cleanliness': Review.cleanliness_rating,
            'food_quality': Review.food_quality_rating,
            'staff_behavior': Review.staff_behavior_rating,
            'security': Review.security_rating,
            'value_for_money': Review.value_for_money_rating,
            'amenities': Review.amenities_rating,
            'location': Review.location_rating,
            'wifi_quality': Review.wifi_quality_rating,
            'maintenance': Review.maintenance_rating
        }
        
        field = field_map.get(aspect)
        if not field:
            return aspect_rating
        
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            field.isnot(None),
            Review.deleted_at.is_(None)
        )
        
        aspect_rating.total_ratings = query.count()
        
        if aspect_rating.total_ratings > 0:
            avg_rating = query.with_entities(func.avg(field)).scalar()
            aspect_rating.average_rating = Decimal(str(avg_rating)).quantize(Decimal('0.01'))
            
            # Calculate rating distribution
            distribution = {}
            for rating in range(1, 6):
                count = query.filter(field == rating).count()
                distribution[rating] = count
            
            aspect_rating.rating_distribution = distribution
            
            # Calculate trend (compare last 30 days to previous 30 days)
            now = datetime.utcnow()
            last_30 = query.filter(
                Review.created_at >= now - timedelta(days=30)
            ).with_entities(func.avg(field)).scalar()
            
            prev_30 = query.filter(
                Review.created_at >= now - timedelta(days=60),
                Review.created_at < now - timedelta(days=30)
            ).with_entities(func.avg(field)).scalar()
            
            if last_30 and prev_30:
                if last_30 > prev_30:
                    aspect_rating.trend = 'improving'
                elif last_30 < prev_30:
                    aspect_rating.trend = 'declining'
                else:
                    aspect_rating.trend = 'stable'
            else:
                aspect_rating.trend = 'stable'
        
        aspect_rating.last_calculated_at = datetime.utcnow()
        
        self.session.commit()
        self.session.refresh(aspect_rating)
        
        return aspect_rating
    
    def get_aspect_ratings(
        self,
        hostel_id: UUID
    ) -> List[AspectRating]:
        """
        Get all aspect ratings for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of aspect ratings
        """
        return self.session.query(AspectRating).filter(
            AspectRating.hostel_id == hostel_id
        ).order_by(desc(AspectRating.average_rating)).all()
    
    # ==================== Competitor Comparison Operations ====================
    
    def calculate_competitor_comparison(
        self,
        hostel_id: UUID,
        competitor_ids: List[UUID],
        comparison_date: date
    ) -> CompetitorComparison:
        """
        Calculate competitive comparison.
        
        Args:
            hostel_id: Hostel ID
            competitor_ids: List of competitor hostel IDs
            comparison_date: Date for comparison
            
        Returns:
            Competitor comparison
        """
        # Get or create comparison
        comparison = self.session.query(CompetitorComparison).filter(
            CompetitorComparison.hostel_id == hostel_id,
            CompetitorComparison.comparison_date == comparison_date
        ).first()
        
        if not comparison:
            comparison = CompetitorComparison(
                hostel_id=hostel_id,
                comparison_date=comparison_date
            )
            self.session.add(comparison)
        
        # Get this hostel's rating
        hostel_query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        this_rating = hostel_query.with_entities(func.avg(Review.overall_rating)).scalar()
        comparison.this_hostel_rating = Decimal(str(this_rating or 0)).quantize(Decimal('0.01'))
        
        # Get competitor ratings
        competitor_ratings = []
        total_competitor_reviews = 0
        
        for comp_id in competitor_ids:
            comp_query = self.session.query(Review).filter(
                Review.hostel_id == comp_id,
                Review.is_published == True,
                Review.deleted_at.is_(None)
            )
            
            comp_rating = comp_query.with_entities(func.avg(Review.overall_rating)).scalar()
            if comp_rating:
                competitor_ratings.append(float(comp_rating))
                total_competitor_reviews += comp_query.count()
        
        if competitor_ratings:
            avg_competitor_rating = sum(competitor_ratings) / len(competitor_ratings)
            comparison.competitor_average_rating = Decimal(str(avg_competitor_rating)).quantize(Decimal('0.01'))
            comparison.rating_difference = comparison.this_hostel_rating - comparison.competitor_average_rating
            
            # Calculate percentile rank
            better_than = sum(1 for r in competitor_ratings if float(comparison.this_hostel_rating) > r)
            percentile = (better_than / len(competitor_ratings)) * 100
            comparison.percentile_rank = Decimal(str(percentile)).quantize(Decimal('0.01'))
            
            # Determine competitive position
            if comparison.percentile_rank >= 75:
                comparison.competitive_position = 'leader'
            elif comparison.percentile_rank >= 50:
                comparison.competitive_position = 'above_average'
            elif comparison.percentile_rank >= 25:
                comparison.competitive_position = 'average'
            else:
                comparison.competitive_position = 'below_average'
        
        comparison.total_competitors = len(competitor_ids)
        comparison.competitors_analyzed = [str(comp_id) for comp_id in competitor_ids]
        comparison.market_average_rating = comparison.competitor_average_rating
        comparison.market_total_reviews = total_competitor_reviews
        
        comparison.last_calculated_at = datetime.utcnow()
        
        self.session.commit()
        self.session.refresh(comparison)
        
        return comparison
    
    def get_competitor_comparison(
        self,
        hostel_id: UUID,
        comparison_date: Optional[date] = None
    ) -> Optional[CompetitorComparison]:
        """
        Get competitor comparison.
        
        Args:
            hostel_id: Hostel ID
            comparison_date: Optional specific date
            
        Returns:
            Competitor comparison if exists
        """
        query = self.session.query(CompetitorComparison).filter(
            CompetitorComparison.hostel_id == hostel_id
        )
        
        if comparison_date:
            query = query.filter(CompetitorComparison.comparison_date == comparison_date)
        
        return query.order_by(desc(CompetitorComparison.comparison_date)).first()
    
    # ==================== Bulk Analytics Operations ====================
    
    def refresh_all_analytics(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Refresh all analytics for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary with all analytics
        """
        summary = self.calculate_analytics_summary(hostel_id)
        distribution = self.calculate_rating_distribution(hostel_id)
        trend = self.calculate_review_trend(hostel_id, date.today())
        sentiment = self.calculate_sentiment_analysis(hostel_id)
        aspects = self.calculate_aspect_ratings(hostel_id)
        
        return {
            'summary': summary,
            'distribution': distribution,
            'trend': trend,
            'sentiment': sentiment,
            'aspects': aspects
        }