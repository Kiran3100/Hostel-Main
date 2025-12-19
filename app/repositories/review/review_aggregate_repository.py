"""
Review Aggregate Repository - Complex aggregations and cross-entity queries.

Implements advanced queries that span multiple review entities and
provide comprehensive insights.
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, joinedload

from app.models.review import Review
from app.models.review.review_response import ReviewResponse
from app.models.review.review_voting import ReviewVote, ReviewHelpfulnessScore
from app.models.review.review_media import ReviewMedia
from app.models.review.review_moderation import ReviewModerationQueue
from app.repositories.base import BaseRepository


class ReviewAggregateRepository(BaseRepository[Review]):
    """
    Repository for complex review aggregations.
    
    Provides advanced queries combining multiple review entities
    for comprehensive reporting and analytics.
    """
    
    def __init__(self, session: Session):
        """
        Initialize review aggregate repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(Review, session)
    
    # ==================== Dashboard Aggregations ====================
    
    def get_hostel_dashboard_metrics(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard metrics for hostel.
        
        Args:
            hostel_id: Hostel ID
            period_days: Number of days for period metrics
            
        Returns:
            Dictionary with dashboard metrics
        """
        start_date = datetime.utcnow() - timedelta(days=period_days)
        
        # Base query
        all_reviews = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        period_reviews = all_reviews.filter(Review.created_at >= start_date)
        
        # Total metrics
        total_reviews = all_reviews.count()
        period_review_count = period_reviews.count()
        
        # Rating metrics
        overall_avg = all_reviews.with_entities(
            func.avg(Review.overall_rating)
        ).scalar()
        
        period_avg = period_reviews.with_entities(
            func.avg(Review.overall_rating)
        ).scalar()
        
        # Response metrics
        total_responses = self.session.query(ReviewResponse).join(Review).filter(
            Review.hostel_id == hostel_id
        ).count()
        
        response_rate = (total_responses / total_reviews * 100) if total_reviews > 0 else 0
        
        avg_response_time = self.session.query(ReviewResponse).join(Review).filter(
            Review.hostel_id == hostel_id
        ).with_entities(
            func.avg(ReviewResponse.response_time_hours)
        ).scalar()
        
        # Engagement metrics
        total_votes = all_reviews.with_entities(
            func.sum(Review.helpful_count + Review.not_helpful_count)
        ).scalar() or 0
        
        avg_helpful_ratio = all_reviews.with_entities(
            func.avg(
                case(
                    (Review.helpful_count + Review.not_helpful_count > 0,
                     Review.helpful_count / (Review.helpful_count + Review.not_helpful_count)),
                    else_=0
                )
            )
        ).scalar() or 0
        
        # Verification metrics
        verified_count = all_reviews.filter(Review.is_verified_stay == True).count()
        verification_rate = (verified_count / total_reviews * 100) if total_reviews > 0 else 0
        
        # Media metrics
        reviews_with_photos = all_reviews.filter(Review.photos != []).count()
        photo_rate = (reviews_with_photos / total_reviews * 100) if total_reviews > 0 else 0
        
        # Sentiment breakdown
        positive_count = all_reviews.filter(Review.overall_rating >= 4).count()
        neutral_count = all_reviews.filter(
            Review.overall_rating >= 3,
            Review.overall_rating < 4
        ).count()
        negative_count = all_reviews.filter(Review.overall_rating < 3).count()
        
        # Pending moderation
        pending_moderation = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.hostel_id == hostel_id,
            ReviewModerationQueue.queue_status == 'pending'
        ).count()
        
        return {
            'period_days': period_days,
            'total_reviews': total_reviews,
            'period_review_count': period_review_count,
            'overall_rating': round(float(overall_avg or 0), 2),
            'period_rating': round(float(period_avg or 0), 2),
            'rating_trend': round(float(period_avg or 0) - float(overall_avg or 0), 2),
            'response_count': total_responses,
            'response_rate': round(response_rate, 2),
            'avg_response_time_hours': round(float(avg_response_time or 0), 2),
            'total_votes': int(total_votes),
            'avg_helpful_ratio': round(float(avg_helpful_ratio), 3),
            'verified_count': verified_count,
            'verification_rate': round(verification_rate, 2),
            'reviews_with_photos': reviews_with_photos,
            'photo_rate': round(photo_rate, 2),
            'sentiment': {
                'positive': positive_count,
                'neutral': neutral_count,
                'negative': negative_count,
                'positive_rate': round((positive_count / total_reviews * 100) if total_reviews > 0 else 0, 2)
            },
            'pending_moderation': pending_moderation
        }
    
    # ==================== Review Performance Queries ====================
    
    def get_top_performing_reviews(
        self,
        hostel_id: UUID,
        limit: int = 10,
        metric: str = 'helpful'
    ) -> List[Dict[str, Any]]:
        """
        Get top performing reviews by various metrics.
        
        Args:
            hostel_id: Hostel ID
            limit: Maximum number of results
            metric: Performance metric (helpful, engagement, views, influence)
            
        Returns:
            List of top reviews with metrics
        """
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        # Order by metric
        if metric == 'helpful':
            query = query.order_by(desc(Review.helpful_count))
        elif metric == 'views':
            query = query.order_by(desc(Review.view_count))
        elif metric == 'engagement':
            query = query.order_by(
                desc(Review.helpful_count + Review.not_helpful_count)
            )
        
        reviews = query.limit(limit).all()
        
        results = []
        for review in reviews:
            # Get helpfulness score
            helpfulness = self.session.query(ReviewHelpfulnessScore).filter(
                ReviewHelpfulnessScore.review_id == review.id
            ).first()
            
            results.append({
                'review_id': review.id,
                'title': review.title,
                'rating': float(review.overall_rating),
                'helpful_count': review.helpful_count,
                'view_count': review.view_count,
                'wilson_score': float(helpfulness.wilson_score) if helpfulness else 0,
                'created_at': review.created_at.isoformat(),
                'has_response': review.hostel_response is not None,
                'is_verified': review.is_verified_stay
            })
        
        return results
    
    def get_review_performance_over_time(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
        interval: str = 'day'
    ) -> List[Dict[str, Any]]:
        """
        Get review performance metrics over time.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            interval: Time interval (day, week, month)
            
        Returns:
            List of performance metrics by time period
        """
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.created_at >= start_date,
            Review.created_at <= end_date,
            Review.deleted_at.is_(None)
        )
        
        # Group by interval
        if interval == 'day':
            time_field = func.date(Review.created_at)
        elif interval == 'week':
            time_field = func.date_trunc('week', Review.created_at)
        else:  # month
            time_field = func.date_trunc('month', Review.created_at)
        
        results = query.with_entities(
            time_field.label('period'),
            func.count(Review.id).label('review_count'),
            func.avg(Review.overall_rating).label('avg_rating'),
            func.sum(Review.helpful_count).label('total_helpful'),
            func.sum(Review.view_count).label('total_views'),
            func.count(case((Review.is_verified_stay == True, 1))).label('verified_count')
        ).group_by(time_field).order_by(time_field).all()
        
        return [
            {
                'period': result.period.isoformat() if hasattr(result.period, 'isoformat') else str(result.period),
                'review_count': result.review_count,
                'avg_rating': round(float(result.avg_rating or 0), 2),
                'total_helpful': int(result.total_helpful or 0),
                'total_views': int(result.total_views or 0),
                'verified_count': result.verified_count
            }
            for result in results
        ]
    
    # ==================== User Behavior Analysis ====================
    
    def get_reviewer_insights(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get insights about reviewers.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary with reviewer insights
        """
        reviews = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        # Review length analysis
        avg_length = reviews.with_entities(
            func.avg(func.length(Review.review_text))
        ).scalar() or 0
        
        # Verified reviewer rate
        verified_reviewers = reviews.filter(Review.is_verified_stay == True).count()
        total_reviewers = reviews.count()
        
        # Photo upload rate
        with_photos = reviews.filter(Review.photos != []).count()
        
        # Recommendation rate
        would_recommend = reviews.filter(Review.would_recommend == True).count()
        
        # Rating distribution among reviewers
        rating_counts = reviews.with_entities(
            func.floor(Review.overall_rating).label('rating'),
            func.count(Review.id).label('count')
        ).group_by(func.floor(Review.overall_rating)).all()
        
        return {
            'total_reviewers': total_reviewers,
            'verified_reviewer_rate': round((verified_reviewers / total_reviewers * 100) if total_reviewers > 0 else 0, 2),
            'photo_upload_rate': round((with_photos / total_reviewers * 100) if total_reviewers > 0 else 0, 2),
            'recommendation_rate': round((would_recommend / total_reviewers * 100) if total_reviewers > 0 else 0, 2),
            'avg_review_length': int(avg_length),
            'rating_distribution': {
                int(r.rating): r.count for r in rating_counts
            }
        }
    
    # ==================== Content Analysis ====================
    
    def get_common_themes(
        self,
        hostel_id: UUID,
        limit: int = 10
    ) -> Dict[str, List[str]]:
        """
        Get common themes from reviews.
        
        Args:
            hostel_id: Hostel ID
            limit: Maximum themes to return
            
        Returns:
            Dictionary with positive and negative themes
        """
        from collections import Counter
        
        reviews = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        ).all()
        
        all_pros = []
        all_cons = []
        
        for review in reviews:
            if review.pros:
                all_pros.extend(review.pros)
            if review.cons:
                all_cons.extend(review.cons)
        
        # Get most common
        top_pros = [theme for theme, _ in Counter(all_pros).most_common(limit)]
        top_cons = [theme for theme, _ in Counter(all_cons).most_common(limit)]
        
        return {
            'positive_themes': top_pros,
            'negative_themes': top_cons
        }
    
    # ==================== Comparative Analysis ====================
    
    def compare_time_periods(
        self,
        hostel_id: UUID,
        period1_start: datetime,
        period1_end: datetime,
        period2_start: datetime,
        period2_end: datetime
    ) -> Dict[str, Any]:
        """
        Compare metrics between two time periods.
        
        Args:
            hostel_id: Hostel ID
            period1_start: First period start
            period1_end: First period end
            period2_start: Second period start
            period2_end: Second period end
            
        Returns:
            Comparison metrics
        """
        def get_period_metrics(start: datetime, end: datetime) -> Dict[str, Any]:
            query = self.session.query(Review).filter(
                Review.hostel_id == hostel_id,
                Review.is_published == True,
                Review.created_at >= start,
                Review.created_at <= end,
                Review.deleted_at.is_(None)
            )
            
            count = query.count()
            avg_rating = query.with_entities(func.avg(Review.overall_rating)).scalar()
            verified = query.filter(Review.is_verified_stay == True).count()
            
            return {
                'count': count,
                'avg_rating': float(avg_rating or 0),
                'verified_count': verified
            }
        
        period1_metrics = get_period_metrics(period1_start, period1_end)
        period2_metrics = get_period_metrics(period2_start, period2_end)
        
        # Calculate changes
        count_change = period2_metrics['count'] - period1_metrics['count']
        rating_change = period2_metrics['avg_rating'] - period1_metrics['avg_rating']
        verified_change = period2_metrics['verified_count'] - period1_metrics['verified_count']
        
        return {
            'period1': {
                'start': period1_start.isoformat(),
                'end': period1_end.isoformat(),
                'metrics': period1_metrics
            },
            'period2': {
                'start': period2_start.isoformat(),
                'end': period2_end.isoformat(),
                'metrics': period2_metrics
            },
            'changes': {
                'count_change': count_change,
                'count_change_percent': round((count_change / period1_metrics['count'] * 100) if period1_metrics['count'] > 0 else 0, 2),
                'rating_change': round(rating_change, 2),
                'verified_change': verified_change
            }
        }
    
    # ==================== Export and Reporting ====================
    
    def get_review_export_data(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_details: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get review data for export.
        
        Args:
            hostel_id: Hostel ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            include_details: Whether to include detailed information
            
        Returns:
            List of review data for export
        """
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        if start_date:
            query = query.filter(Review.created_at >= start_date)
        if end_date:
            query = query.filter(Review.created_at <= end_date)
        
        if include_details:
            query = query.options(
                joinedload(Review.hostel_response),
                joinedload(Review.verification)
            )
        
        reviews = query.order_by(desc(Review.created_at)).all()
        
        export_data = []
        for review in reviews:
            data = {
                'review_id': str(review.id),
                'created_at': review.created_at.isoformat(),
                'overall_rating': float(review.overall_rating),
                'title': review.title,
                'review_text': review.review_text,
                'would_recommend': review.would_recommend,
                'is_verified': review.is_verified_stay,
                'helpful_count': review.helpful_count,
                'view_count': review.view_count
            }
            
            if include_details:
                data.update({
                    'cleanliness_rating': review.cleanliness_rating,
                    'food_quality_rating': review.food_quality_rating,
                    'staff_behavior_rating': review.staff_behavior_rating,
                    'security_rating': review.security_rating,
                    'value_for_money_rating': review.value_for_money_rating,
                    'amenities_rating': review.amenities_rating,
                    'location_rating': review.location_rating,
                    'wifi_quality_rating': review.wifi_quality_rating,
                    'maintenance_rating': review.maintenance_rating,
                    'has_response': review.hostel_response is not None,
                    'response_time_hours': float(review.hostel_response.response_time_hours) if review.hostel_response else None,
                    'pros': review.pros,
                    'cons': review.cons
                })
            
            export_data.append(data)
        
        return export_data