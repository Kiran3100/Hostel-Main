# --- File: C:\Hostel-Main\app\repositories\mess\menu_feedback_repository.py ---

"""
Menu Feedback Repository Module.

Manages menu feedback, ratings, sentiment analysis, quality metrics,
and feedback analytics with comprehensive reporting capabilities.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.mess.menu_feedback import (
    FeedbackAnalysis,
    FeedbackComment,
    FeedbackHelpfulness,
    ItemRating,
    MenuFeedback,
    QualityMetrics,
    RatingsSummary,
    SentimentAnalysis,
)
from app.models.student.student import Student
from app.repositories.base.base_repository import BaseRepository


class MenuFeedbackRepository(BaseRepository[MenuFeedback]):
    """
    Repository for managing menu feedback.
    
    Handles student feedback collection, rating management,
    moderation, and engagement tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuFeedback model."""
        super().__init__(MenuFeedback, db_session)

    async def create_feedback(
        self,
        student_id: UUID,
        menu_id: UUID,
        feedback_data: Dict
    ) -> MenuFeedback:
        """
        Create new menu feedback.
        
        Args:
            student_id: Student identifier
            menu_id: Menu identifier
            feedback_data: Feedback details
            
        Returns:
            Created MenuFeedback
        """
        feedback = MenuFeedback(
            student_id=student_id,
            menu_id=menu_id,
            comment_length=len(feedback_data.get('comments', '')),
            **feedback_data
        )
        
        self.db_session.add(feedback)
        await self.db_session.commit()
        await self.db_session.refresh(feedback)
        
        return feedback

    async def find_by_menu(
        self,
        menu_id: UUID,
        verified_only: bool = False,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None
    ) -> List[MenuFeedback]:
        """
        Get feedback for a specific menu.
        
        Args:
            menu_id: Menu identifier
            verified_only: Only verified feedback
            min_rating: Minimum rating filter
            max_rating: Maximum rating filter
            
        Returns:
            List of feedback records
        """
        conditions = [
            MenuFeedback.menu_id == menu_id,
            MenuFeedback.deleted_at.is_(None)
        ]
        
        if verified_only:
            conditions.append(MenuFeedback.is_verified == True)
            
        if min_rating is not None:
            conditions.append(MenuFeedback.rating >= min_rating)
            
        if max_rating is not None:
            conditions.append(MenuFeedback.rating <= max_rating)
            
        query = (
            select(MenuFeedback)
            .where(and_(*conditions))
            .order_by(desc(MenuFeedback.created_at))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_student(
        self,
        student_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[MenuFeedback]:
        """
        Get feedback from a specific student.
        
        Args:
            student_id: Student identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            
        Returns:
            List of student's feedback
        """
        conditions = [
            MenuFeedback.student_id == student_id,
            MenuFeedback.deleted_at.is_(None)
        ]
        
        if start_date:
            conditions.append(MenuFeedback.meal_date >= start_date)
        if end_date:
            conditions.append(MenuFeedback.meal_date <= end_date)
            
        query = (
            select(MenuFeedback)
            .where(and_(*conditions))
            .order_by(desc(MenuFeedback.meal_date))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_meal_type(
        self,
        hostel_id: UUID,
        meal_type: str,
        meal_date: Optional[date] = None
    ) -> List[MenuFeedback]:
        """
        Get feedback for specific meal type.
        
        Args:
            hostel_id: Hostel identifier
            meal_type: Type of meal
            meal_date: Specific date (optional)
            
        Returns:
            List of feedback for meal type
        """
        from app.models.mess.mess_menu import MessMenu
        
        conditions = [
            MenuFeedback.meal_type == meal_type,
            MenuFeedback.deleted_at.is_(None)
        ]
        
        if meal_date:
            conditions.append(MenuFeedback.meal_date == meal_date)
            
        query = (
            select(MenuFeedback)
            .join(MessMenu)
            .where(MessMenu.hostel_id == hostel_id)
            .where(and_(*conditions))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_pending_moderation(
        self,
        hostel_id: Optional[UUID] = None
    ) -> List[MenuFeedback]:
        """
        Get feedback pending moderation.
        
        Args:
            hostel_id: Hostel filter (optional)
            
        Returns:
            List of feedback pending moderation
        """
        from app.models.mess.mess_menu import MessMenu
        
        conditions = [
            MenuFeedback.moderation_status == 'pending',
            MenuFeedback.deleted_at.is_(None)
        ]
        
        query = select(MenuFeedback).where(and_(*conditions))
        
        if hostel_id:
            query = query.join(MessMenu).where(MessMenu.hostel_id == hostel_id)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def moderate_feedback(
        self,
        feedback_id: UUID,
        status: str,
        notes: Optional[str] = None
    ) -> Optional[MenuFeedback]:
        """
        Moderate feedback.
        
        Args:
            feedback_id: Feedback identifier
            status: Moderation status (approved/rejected/flagged)
            notes: Moderation notes (optional)
            
        Returns:
            Updated MenuFeedback
        """
        feedback = await self.get_by_id(feedback_id)
        if not feedback:
            return None
            
        feedback.is_moderated = True
        feedback.moderation_status = status
        feedback.moderation_notes = notes
        
        await self.db_session.commit()
        await self.db_session.refresh(feedback)
        
        return feedback

    async def add_response(
        self,
        feedback_id: UUID,
        responder_id: UUID,
        response_text: str
    ) -> Optional[MenuFeedback]:
        """
        Add management response to feedback.
        
        Args:
            feedback_id: Feedback identifier
            responder_id: User responding
            response_text: Response text
            
        Returns:
            Updated MenuFeedback
        """
        feedback = await self.get_by_id(feedback_id)
        if not feedback:
            return None
            
        feedback.has_response = True
        feedback.response_text = response_text
        feedback.responded_by = responder_id
        feedback.responded_at = datetime.utcnow()
        
        await self.db_session.commit()
        await self.db_session.refresh(feedback)
        
        return feedback

    async def get_featured_feedback(
        self,
        hostel_id: UUID,
        limit: int = 10
    ) -> List[MenuFeedback]:
        """
        Get featured/highlighted feedback.
        
        Args:
            hostel_id: Hostel identifier
            limit: Maximum number of results
            
        Returns:
            List of featured feedback
        """
        from app.models.mess.mess_menu import MessMenu
        
        query = (
            select(MenuFeedback)
            .join(MessMenu)
            .where(MessMenu.hostel_id == hostel_id)
            .where(MenuFeedback.is_featured == True)
            .where(MenuFeedback.is_public == True)
            .where(MenuFeedback.deleted_at.is_(None))
            .order_by(desc(MenuFeedback.helpful_count))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_average_ratings_by_aspect(
        self,
        menu_id: UUID
    ) -> Dict[str, Decimal]:
        """
        Get average ratings for all aspects.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            Dictionary of aspect ratings
        """
        query = (
            select(
                func.avg(MenuFeedback.taste_rating).label('taste'),
                func.avg(MenuFeedback.quantity_rating).label('quantity'),
                func.avg(MenuFeedback.quality_rating).label('quality'),
                func.avg(MenuFeedback.hygiene_rating).label('hygiene'),
                func.avg(MenuFeedback.presentation_rating).label('presentation'),
                func.avg(MenuFeedback.service_rating).label('service'),
                func.avg(MenuFeedback.temperature_rating).label('temperature'),
                func.avg(MenuFeedback.freshness_rating).label('freshness'),
            )
            .where(MenuFeedback.menu_id == menu_id)
            .where(MenuFeedback.deleted_at.is_(None))
        )
        
        result = await self.db_session.execute(query)
        row = result.first()
        
        if not row:
            return {}
            
        return {
            'taste': Decimal(str(row.taste or 0)),
            'quantity': Decimal(str(row.quantity or 0)),
            'quality': Decimal(str(row.quality or 0)),
            'hygiene': Decimal(str(row.hygiene or 0)),
            'presentation': Decimal(str(row.presentation or 0)),
            'service': Decimal(str(row.service or 0)),
            'temperature': Decimal(str(row.temperature or 0)),
            'freshness': Decimal(str(row.freshness or 0)),
        }

    async def get_most_helpful_feedback(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 20
    ) -> List[MenuFeedback]:
        """
        Get most helpful feedback.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            limit: Maximum number of results
            
        Returns:
            List of most helpful feedback
        """
        from app.models.mess.mess_menu import MessMenu
        
        conditions = [
            MenuFeedback.deleted_at.is_(None),
            MenuFeedback.is_public == True
        ]
        
        if start_date:
            conditions.append(MenuFeedback.meal_date >= start_date)
        if end_date:
            conditions.append(MenuFeedback.meal_date <= end_date)
            
        query = (
            select(MenuFeedback)
            .join(MessMenu)
            .where(MessMenu.hostel_id == hostel_id)
            .where(and_(*conditions))
            .order_by(
                desc(MenuFeedback.helpful_count),
                desc(MenuFeedback.comment_length)
            )
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_feedback_with_comments(
        self,
        feedback_id: UUID
    ) -> Optional[MenuFeedback]:
        """
        Get feedback with all comments loaded.
        
        Args:
            feedback_id: Feedback identifier
            
        Returns:
            MenuFeedback with comments
        """
        query = (
            select(MenuFeedback)
            .where(MenuFeedback.id == feedback_id)
            .options(selectinload(MenuFeedback.comments))
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()


class ItemRatingRepository(BaseRepository[ItemRating]):
    """
    Repository for aggregated item ratings.
    
    Manages popularity and satisfaction tracking for
    individual menu items across menus.
    """

    def __init__(self, db_session):
        """Initialize repository with ItemRating model."""
        super().__init__(ItemRating, db_session)

    async def get_by_item_name(
        self,
        hostel_id: UUID,
        item_name: str
    ) -> Optional[ItemRating]:
        """
        Get rating for specific item.
        
        Args:
            hostel_id: Hostel identifier
            item_name: Name of item
            
        Returns:
            ItemRating if found
        """
        query = (
            select(ItemRating)
            .where(ItemRating.hostel_id == hostel_id)
            .where(ItemRating.item_name == item_name)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_top_rated_items(
        self,
        hostel_id: UUID,
        category: Optional[str] = None,
        min_ratings: int = 5,
        limit: int = 10
    ) -> List[ItemRating]:
        """
        Get highest rated items.
        
        Args:
            hostel_id: Hostel identifier
            category: Category filter (optional)
            min_ratings: Minimum ratings required
            limit: Maximum number of results
            
        Returns:
            List of top-rated items
        """
        conditions = [
            ItemRating.hostel_id == hostel_id,
            ItemRating.total_ratings >= min_ratings
        ]
        
        if category:
            conditions.append(ItemRating.item_category == category)
            
        query = (
            select(ItemRating)
            .where(and_(*conditions))
            .order_by(desc(ItemRating.average_rating))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_most_popular_items(
        self,
        hostel_id: UUID,
        limit: int = 10
    ) -> List[ItemRating]:
        """
        Get most popular items by popularity score.
        
        Args:
            hostel_id: Hostel identifier
            limit: Maximum number of results
            
        Returns:
            List of most popular items
        """
        query = (
            select(ItemRating)
            .where(ItemRating.hostel_id == hostel_id)
            .order_by(desc(ItemRating.popularity_score))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_trending_items(
        self,
        hostel_id: UUID,
        trend_direction: str = 'rising',
        limit: int = 10
    ) -> List[ItemRating]:
        """
        Get trending items.
        
        Args:
            hostel_id: Hostel identifier
            trend_direction: Trend direction (rising/declining)
            limit: Maximum number of results
            
        Returns:
            List of trending items
        """
        query = (
            select(ItemRating)
            .where(ItemRating.hostel_id == hostel_id)
            .where(ItemRating.trend_direction == trend_direction)
            .order_by(desc(ItemRating.trend_percentage))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def update_item_rating(
        self,
        hostel_id: UUID,
        item_name: str,
        is_liked: bool
    ) -> ItemRating:
        """
        Update item rating with like/dislike.
        
        Args:
            hostel_id: Hostel identifier
            item_name: Name of item
            is_liked: Whether item was liked
            
        Returns:
            Updated ItemRating
        """
        rating = await self.get_by_item_name(hostel_id, item_name)
        
        if not rating:
            rating = ItemRating(
                hostel_id=hostel_id,
                item_name=item_name,
                liked_count=1 if is_liked else 0,
                disliked_count=0 if is_liked else 1,
                times_served=1,
                last_served=date.today()
            )
            self.db_session.add(rating)
        else:
            if is_liked:
                rating.liked_count += 1
            else:
                rating.disliked_count += 1
                
        # Update popularity score
        total_feedback = rating.liked_count + rating.disliked_count
        if total_feedback > 0:
            like_ratio = (rating.liked_count / total_feedback) * 100
            rating.popularity_score = Decimal(str(like_ratio))
            
        await self.db_session.commit()
        await self.db_session.refresh(rating)
        
        return rating


class RatingsSummaryRepository(BaseRepository[RatingsSummary]):
    """
    Repository for menu ratings summaries.
    
    Provides aggregated rating data for menus with
    statistical analysis and distribution.
    """

    def __init__(self, db_session):
        """Initialize repository with RatingsSummary model."""
        super().__init__(RatingsSummary, db_session)

    async def get_by_menu(
        self,
        menu_id: UUID
    ) -> Optional[RatingsSummary]:
        """
        Get ratings summary for menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            RatingsSummary if found
        """
        query = select(RatingsSummary).where(
            RatingsSummary.menu_id == menu_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def calculate_summary(
        self,
        menu_id: UUID
    ) -> RatingsSummary:
        """
        Calculate and store ratings summary.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            Calculated RatingsSummary
        """
        from app.models.mess.mess_menu import MessMenu
        
        # Get menu details
        menu_query = select(MessMenu).where(MessMenu.id == menu_id)
        menu_result = await self.db_session.execute(menu_query)
        menu = menu_result.scalar_one_or_none()
        
        if not menu:
            raise ValueError("Menu not found")
            
        # Get all feedback for menu
        feedback_query = (
            select(MenuFeedback)
            .where(MenuFeedback.menu_id == menu_id)
            .where(MenuFeedback.deleted_at.is_(None))
        )
        
        feedback_result = await self.db_session.execute(feedback_query)
        feedbacks = list(feedback_result.scalars().all())
        
        # Calculate statistics
        total_feedbacks = len(feedbacks)
        
        if total_feedbacks == 0:
            # Return empty summary
            summary = RatingsSummary(
                menu_id=menu_id,
                hostel_id=menu.hostel_id,
                menu_date=menu.menu_date,
                total_feedbacks=0,
                average_rating=Decimal('0.00'),
                satisfaction_level='no_data'
            )
        else:
            ratings = [f.rating for f in feedbacks]
            average_rating = sum(ratings) / len(ratings)
            
            # Rating distribution
            rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for rating in ratings:
                rating_counts[rating] += 1
                
            # Meal-specific ratings
            meal_ratings = {}
            for meal_type in ['breakfast', 'lunch', 'snacks', 'dinner']:
                meal_feedbacks = [f for f in feedbacks if f.meal_type == meal_type]
                if meal_feedbacks:
                    meal_avg = sum(f.rating for f in meal_feedbacks) / len(meal_feedbacks)
                    meal_ratings[meal_type] = {
                        'average': Decimal(str(meal_avg)),
                        'count': len(meal_feedbacks)
                    }
                    
            # Recommendations
            recommend_count = sum(1 for f in feedbacks if f.would_recommend)
            not_recommend_count = total_feedbacks - recommend_count
            recommend_pct = (recommend_count / total_feedbacks) * 100 if total_feedbacks > 0 else 0
            
            # Satisfaction levels
            very_satisfied = rating_counts[5]
            satisfied = rating_counts[4]
            neutral = rating_counts[3]
            dissatisfied = rating_counts[2]
            very_dissatisfied = rating_counts[1]
            
            satisfaction_pct = ((very_satisfied + satisfied) / total_feedbacks) * 100
            dissatisfaction_pct = ((dissatisfied + very_dissatisfied) / total_feedbacks) * 100
            
            # Determine satisfaction level
            if average_rating >= 4.5:
                satisfaction_level = 'excellent'
            elif average_rating >= 4.0:
                satisfaction_level = 'very_good'
            elif average_rating >= 3.5:
                satisfaction_level = 'good'
            elif average_rating >= 3.0:
                satisfaction_level = 'satisfactory'
            elif average_rating >= 2.0:
                satisfaction_level = 'needs_improvement'
            else:
                satisfaction_level = 'poor'
                
            # Create or update summary
            summary = await self.get_by_menu(menu_id)
            
            if not summary:
                summary = RatingsSummary(
                    menu_id=menu_id,
                    hostel_id=menu.hostel_id,
                    menu_date=menu.menu_date
                )
                self.db_session.add(summary)
                
            summary.total_feedbacks = total_feedbacks
            summary.average_rating = Decimal(str(round(average_rating, 2)))
            summary.rating_5_count = rating_counts[5]
            summary.rating_4_count = rating_counts[4]
            summary.rating_3_count = rating_counts[3]
            summary.rating_2_count = rating_counts[2]
            summary.rating_1_count = rating_counts[1]
            
            # Meal-specific data
            if 'breakfast' in meal_ratings:
                summary.breakfast_rating = meal_ratings['breakfast']['average']
                summary.breakfast_feedback_count = meal_ratings['breakfast']['count']
            if 'lunch' in meal_ratings:
                summary.lunch_rating = meal_ratings['lunch']['average']
                summary.lunch_feedback_count = meal_ratings['lunch']['count']
            if 'snacks' in meal_ratings:
                summary.snacks_rating = meal_ratings['snacks']['average']
                summary.snacks_feedback_count = meal_ratings['snacks']['count']
            if 'dinner' in meal_ratings:
                summary.dinner_rating = meal_ratings['dinner']['average']
                summary.dinner_feedback_count = meal_ratings['dinner']['count']
                
            summary.would_recommend_count = recommend_count
            summary.would_not_recommend_count = not_recommend_count
            summary.would_recommend_percentage = Decimal(str(round(recommend_pct, 2)))
            
            summary.very_satisfied_count = very_satisfied
            summary.satisfied_count = satisfied
            summary.neutral_count = neutral
            summary.dissatisfied_count = dissatisfied
            summary.very_dissatisfied_count = very_dissatisfied
            
            summary.satisfaction_percentage = Decimal(str(round(satisfaction_pct, 2)))
            summary.dissatisfaction_percentage = Decimal(str(round(dissatisfaction_pct, 2)))
            summary.satisfaction_level = satisfaction_level
            
            summary.calculated_at = datetime.utcnow()
            
        await self.db_session.commit()
        await self.db_session.refresh(summary)
        
        return summary

    async def get_hostel_summaries(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[RatingsSummary]:
        """
        Get all summaries for a hostel.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            
        Returns:
            List of ratings summaries
        """
        conditions = [RatingsSummary.hostel_id == hostel_id]
        
        if start_date:
            conditions.append(RatingsSummary.menu_date >= start_date)
        if end_date:
            conditions.append(RatingsSummary.menu_date <= end_date)
            
        query = (
            select(RatingsSummary)
            .where(and_(*conditions))
            .order_by(desc(RatingsSummary.menu_date))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class QualityMetricsRepository(BaseRepository[QualityMetrics]):
    """
    Repository for quality metrics tracking.
    
    Manages quality analysis, trends, and performance
    benchmarking over time periods.
    """

    def __init__(self, db_session):
        """Initialize repository with QualityMetrics model."""
        super().__init__(QualityMetrics, db_session)

    async def calculate_metrics(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
        period_type: str = 'weekly'
    ) -> QualityMetrics:
        """
        Calculate quality metrics for period.
        
        Args:
            hostel_id: Hostel identifier
            period_start: Start of period
            period_end: End of period
            period_type: Type of period (weekly/monthly/quarterly)
            
        Returns:
            Calculated QualityMetrics
        """
        # Get all summaries in period
        summaries = await RatingsSummaryRepository(self.db_session).get_hostel_summaries(
            hostel_id=hostel_id,
            start_date=period_start,
            end_date=period_end
        )
        
        if not summaries:
            # Return empty metrics
            metrics = QualityMetrics(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                overall_average_rating=Decimal('0.00'),
                total_feedbacks=0,
                total_menus_rated=0,
                rating_trend='stable',
                quality_score=Decimal('0.00')
            )
            self.db_session.add(metrics)
        else:
            # Calculate overall metrics
            total_feedbacks = sum(s.total_feedbacks for s in summaries)
            total_menus = len(summaries)
            
            # Weighted average rating
            total_rating_points = sum(
                float(s.average_rating) * s.total_feedbacks
                for s in summaries
            )
            overall_avg = total_rating_points / total_feedbacks if total_feedbacks > 0 else 0
            
            # Find best and worst
            best_summary = max(summaries, key=lambda s: s.average_rating)
            worst_summary = min(summaries, key=lambda s: s.average_rating)
            
            # Calculate satisfaction rate
            total_satisfied = sum(
                s.very_satisfied_count + s.satisfied_count
                for s in summaries
            )
            satisfaction_rate = (total_satisfied / total_feedbacks * 100) if total_feedbacks > 0 else 0
            
            total_dissatisfied = sum(
                s.dissatisfied_count + s.very_dissatisfied_count
                for s in summaries
            )
            dissatisfaction_rate = (total_dissatisfied / total_feedbacks * 100) if total_feedbacks > 0 else 0
            
            # Quality score (0-100)
            quality_score = overall_avg / 5 * 100
            
            metrics = QualityMetrics(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                overall_average_rating=Decimal(str(round(overall_avg, 2))),
                total_feedbacks=total_feedbacks,
                total_menus_rated=total_menus,
                best_menu_date=best_summary.menu_date,
                best_menu_rating=best_summary.average_rating,
                worst_menu_date=worst_summary.menu_date,
                worst_menu_rating=worst_summary.average_rating,
                satisfaction_rate=Decimal(str(round(satisfaction_rate, 2))),
                dissatisfaction_rate=Decimal(str(round(dissatisfaction_rate, 2))),
                quality_score=Decimal(str(round(quality_score, 2))),
                rating_trend='stable',  # Would need historical comparison
                calculated_at=datetime.utcnow()
            )
            self.db_session.add(metrics)
            
        await self.db_session.commit()
        await self.db_session.refresh(metrics)
        
        return metrics

    async def get_latest_metrics(
        self,
        hostel_id: UUID,
        period_type: str = 'weekly'
    ) -> Optional[QualityMetrics]:
        """
        Get latest quality metrics.
        
        Args:
            hostel_id: Hostel identifier
            period_type: Period type filter
            
        Returns:
            Latest QualityMetrics
        """
        query = (
            select(QualityMetrics)
            .where(QualityMetrics.hostel_id == hostel_id)
            .where(QualityMetrics.period_type == period_type)
            .order_by(desc(QualityMetrics.period_end))
            .limit(1)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()


class SentimentAnalysisRepository(BaseRepository[SentimentAnalysis]):
    """
    Repository for sentiment analysis.
    
    Manages sentiment analysis of feedback comments with
    keyword extraction and emotion detection.
    """

    def __init__(self, db_session):
        """Initialize repository with SentimentAnalysis model."""
        super().__init__(SentimentAnalysis, db_session)

    async def get_by_menu(
        self,
        menu_id: UUID
    ) -> Optional[SentimentAnalysis]:
        """
        Get sentiment analysis for menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            SentimentAnalysis if found
        """
        query = select(SentimentAnalysis).where(
            SentimentAnalysis.menu_id == menu_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def analyze_menu_sentiment(
        self,
        menu_id: UUID
    ) -> SentimentAnalysis:
        """
        Analyze sentiment for menu feedback.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            SentimentAnalysis results
        """
        # Get all comments for menu
        feedback_query = (
            select(MenuFeedback)
            .where(MenuFeedback.menu_id == menu_id)
            .where(MenuFeedback.comments.isnot(None))
            .where(MenuFeedback.deleted_at.is_(None))
        )
        
        feedback_result = await self.db_session.execute(feedback_query)
        feedbacks = list(feedback_result.scalars().all())
        
        total_comments = len(feedbacks)
        
        if total_comments == 0:
            # Empty analysis
            analysis = SentimentAnalysis(
                menu_id=menu_id,
                total_comments=0,
                analyzed_comments=0,
                overall_sentiment='neutral',
                sentiment_score=Decimal('0.00')
            )
        else:
            # Simplified sentiment analysis based on ratings
            # In production, would use NLP library
            positive_count = sum(1 for f in feedbacks if f.rating >= 4)
            negative_count = sum(1 for f in feedbacks if f.rating <= 2)
            neutral_count = total_comments - positive_count - negative_count
            
            positive_pct = (positive_count / total_comments) * 100
            negative_pct = (negative_count / total_comments) * 100
            neutral_pct = (neutral_count / total_comments) * 100
            
            # Calculate sentiment score (-100 to +100)
            sentiment_score = positive_pct - negative_pct
            
            # Determine overall sentiment
            if sentiment_score >= 50:
                overall_sentiment = 'very_positive'
            elif sentiment_score >= 20:
                overall_sentiment = 'positive'
            elif sentiment_score >= -20:
                overall_sentiment = 'neutral'
            elif sentiment_score >= -50:
                overall_sentiment = 'negative'
            else:
                overall_sentiment = 'very_negative'
                
            analysis = SentimentAnalysis(
                menu_id=menu_id,
                total_comments=total_comments,
                analyzed_comments=total_comments,
                positive_count=positive_count,
                neutral_count=neutral_count,
                negative_count=negative_count,
                positive_percentage=Decimal(str(round(positive_pct, 2))),
                neutral_percentage=Decimal(str(round(neutral_pct, 2))),
                negative_percentage=Decimal(str(round(negative_pct, 2))),
                overall_sentiment=overall_sentiment,
                sentiment_score=Decimal(str(round(sentiment_score, 2))),
                analysis_method='rating_based',
                analyzed_at=datetime.utcnow()
            )
            
        self.db_session.add(analysis)
        await self.db_session.commit()
        await self.db_session.refresh(analysis)
        
        return analysis


class FeedbackAnalysisRepository(BaseRepository[FeedbackAnalysis]):
    """
    Repository for comprehensive feedback analysis.
    
    Provides actionable insights and recommendations based
    on feedback patterns and trends.
    """

    def __init__(self, db_session):
        """Initialize repository with FeedbackAnalysis model."""
        super().__init__(FeedbackAnalysis, db_session)

    async def generate_analysis(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date
    ) -> FeedbackAnalysis:
        """
        Generate comprehensive feedback analysis.
        
        Args:
            hostel_id: Hostel identifier
            period_start: Start of analysis period
            period_end: End of analysis period
            
        Returns:
            Generated FeedbackAnalysis
        """
        # This would involve complex analysis of feedback patterns
        # Simplified implementation
        
        from app.models.mess.mess_menu import MessMenu
        
        # Get all feedback in period
        feedback_query = (
            select(MenuFeedback)
            .join(MessMenu)
            .where(MessMenu.hostel_id == hostel_id)
            .where(MenuFeedback.meal_date.between(period_start, period_end))
            .where(MenuFeedback.deleted_at.is_(None))
        )
        
        feedback_result = await self.db_session.execute(feedback_query)
        feedbacks = list(feedback_result.scalars().all())
        
        # Analyze sentiment distribution
        positive = sum(1 for f in feedbacks if f.rating >= 4)
        negative = sum(1 for f in feedbacks if f.rating <= 2)
        total = len(feedbacks)
        
        positive_pct = (positive / total * 100) if total > 0 else 0
        negative_pct = (negative / total * 100) if total > 0 else 0
        
        # Extract common items from feedback
        liked_items = {}
        disliked_items = {}
        
        for feedback in feedbacks:
            for item in feedback.liked_items:
                liked_items[item] = liked_items.get(item, 0) + 1
            for item in feedback.disliked_items:
                disliked_items[item] = disliked_items.get(item, 0) + 1
                
        # Sort by frequency
        top_liked = sorted(liked_items.items(), key=lambda x: x[1], reverse=True)[:10]
        top_disliked = sorted(disliked_items.items(), key=lambda x: x[1], reverse=True)[:10]
        
        analysis = FeedbackAnalysis(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            positive_feedback_percentage=Decimal(str(round(positive_pct, 2))),
            negative_feedback_percentage=Decimal(str(round(negative_pct, 2))),
            items_to_keep=[item for item, _ in top_liked],
            items_to_improve=[item for item, _ in top_disliked[:5]],
            generated_at=datetime.utcnow()
        )
        
        self.db_session.add(analysis)
        await self.db_session.commit()
        await self.db_session.refresh(analysis)
        
        return analysis


class FeedbackCommentRepository(BaseRepository[FeedbackComment]):
    """
    Repository for feedback comments/discussions.
    
    Manages threaded comments on feedback with
    public/internal visibility.
    """

    def __init__(self, db_session):
        """Initialize repository with FeedbackComment model."""
        super().__init__(FeedbackComment, db_session)

    async def create_comment(
        self,
        feedback_id: UUID,
        commenter_id: UUID,
        commenter_role: str,
        comment_text: str,
        parent_id: Optional[UUID] = None,
        is_internal: bool = False
    ) -> FeedbackComment:
        """
        Create new comment on feedback.
        
        Args:
            feedback_id: Feedback identifier
            commenter_id: User commenting
            commenter_role: Role of commenter
            comment_text: Comment text
            parent_id: Parent comment for threading (optional)
            is_internal: Internal comment flag
            
        Returns:
            Created FeedbackComment
        """
        comment = FeedbackComment(
            feedback_id=feedback_id,
            commenter_id=commenter_id,
            commenter_role=commenter_role,
            comment_text=comment_text,
            parent_comment_id=parent_id,
            is_internal=is_internal,
            is_public=not is_internal
        )
        
        self.db_session.add(comment)
        await self.db_session.commit()
        await self.db_session.refresh(comment)
        
        return comment

    async def get_feedback_comments(
        self,
        feedback_id: UUID,
        include_internal: bool = False
    ) -> List[FeedbackComment]:
        """
        Get all comments for feedback.
        
        Args:
            feedback_id: Feedback identifier
            include_internal: Include internal comments
            
        Returns:
            List of comments
        """
        conditions = [
            FeedbackComment.feedback_id == feedback_id,
            FeedbackComment.deleted_at.is_(None)
        ]
        
        if not include_internal:
            conditions.append(FeedbackComment.is_public == True)
            
        query = (
            select(FeedbackComment)
            .where(and_(*conditions))
            .order_by(FeedbackComment.created_at)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class FeedbackHelpfulnessRepository(BaseRepository[FeedbackHelpfulness]):
    """
    Repository for feedback helpfulness voting.
    
    Tracks user votes on feedback helpfulness for
    quality ranking.
    """

    def __init__(self, db_session):
        """Initialize repository with FeedbackHelpfulness model."""
        super().__init__(FeedbackHelpfulness, db_session)

    async def vote(
        self,
        feedback_id: UUID,
        voter_id: UUID,
        is_helpful: bool
    ) -> FeedbackHelpfulness:
        """
        Record helpfulness vote.
        
        Args:
            feedback_id: Feedback identifier
            voter_id: User voting
            is_helpful: Whether helpful
            
        Returns:
            FeedbackHelpfulness record
        """
        # Check for existing vote
        existing = await self.get_vote(feedback_id, voter_id)
        
        if existing:
            # Update existing vote
            existing.is_helpful = is_helpful
            vote = existing
        else:
            # Create new vote
            vote = FeedbackHelpfulness(
                feedback_id=feedback_id,
                voter_id=voter_id,
                is_helpful=is_helpful
            )
            self.db_session.add(vote)
            
        # Update feedback counts
        feedback_query = select(MenuFeedback).where(MenuFeedback.id == feedback_id)
        feedback_result = await self.db_session.execute(feedback_query)
        feedback = feedback_result.scalar_one_or_none()
        
        if feedback:
            # Recalculate counts
            helpful_query = (
                select(func.count())
                .select_from(FeedbackHelpfulness)
                .where(FeedbackHelpfulness.feedback_id == feedback_id)
                .where(FeedbackHelpfulness.is_helpful == True)
            )
            helpful_result = await self.db_session.execute(helpful_query)
            helpful_count = helpful_result.scalar() or 0
            
            not_helpful_query = (
                select(func.count())
                .select_from(FeedbackHelpfulness)
                .where(FeedbackHelpfulness.feedback_id == feedback_id)
                .where(FeedbackHelpfulness.is_helpful == False)
            )
            not_helpful_result = await self.db_session.execute(not_helpful_query)
            not_helpful_count = not_helpful_result.scalar() or 0
            
            feedback.helpful_count = helpful_count
            feedback.not_helpful_count = not_helpful_count
            
        await self.db_session.commit()
        await self.db_session.refresh(vote)
        
        return vote

    async def get_vote(
        self,
        feedback_id: UUID,
        voter_id: UUID
    ) -> Optional[FeedbackHelpfulness]:
        """
        Get existing vote.
        
        Args:
            feedback_id: Feedback identifier
            voter_id: Voter identifier
            
        Returns:
            FeedbackHelpfulness if found
        """
        query = (
            select(FeedbackHelpfulness)
            .where(FeedbackHelpfulness.feedback_id == feedback_id)
            .where(FeedbackHelpfulness.voter_id == voter_id)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()