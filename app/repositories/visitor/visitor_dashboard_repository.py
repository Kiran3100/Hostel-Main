# --- File: app/repositories/visitor/visitor_dashboard_repository.py ---
"""
Visitor dashboard repository for activity and recommendations.

This module provides repository operations for visitor dashboard components
including recent searches, viewed hostels, recommendations, and alerts.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.visitor.visitor_dashboard import (
    AvailabilityAlert,
    PriceDropAlert,
    RecentSearch,
    RecentlyViewedHostel,
    RecommendedHostel,
    VisitorActivity,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginationResult


class RecentSearchRepository(BaseRepository[RecentSearch]):
    """Repository for RecentSearch entity."""

    def __init__(self, session: Session):
        super().__init__(RecentSearch, session)

    def save_search(
        self,
        visitor_id: UUID,
        search_query: Optional[str] = None,
        filters_applied: Optional[Dict] = None,
        cities: Optional[List[str]] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        room_types: Optional[List[str]] = None,
        amenities: Optional[List[str]] = None,
        results_count: int = 0,
        result_hostel_ids: Optional[List[UUID]] = None,
    ) -> RecentSearch:
        """
        Save a recent search.
        
        Args:
            visitor_id: Visitor ID
            search_query: Search query text
            filters_applied: Applied filters dictionary
            cities: Cities searched
            min_price: Minimum price filter
            max_price: Maximum price filter
            room_types: Room types filtered
            amenities: Amenities filtered
            results_count: Number of results
            result_hostel_ids: List of result hostel IDs
            
        Returns:
            Created RecentSearch instance
        """
        search = RecentSearch(
            visitor_id=visitor_id,
            search_query=search_query,
            filters_applied=filters_applied or {},
            cities=cities or [],
            min_price=min_price,
            max_price=max_price,
            room_types=room_types or [],
            amenities=amenities or [],
            results_count=results_count,
            result_hostel_ids=result_hostel_ids or [],
            searched_at=datetime.utcnow(),
        )
        
        self.session.add(search)
        self.session.flush()
        
        return search

    def get_recent_searches(
        self,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[RecentSearch]:
        """
        Get visitor's recent searches.
        
        Args:
            visitor_id: Visitor ID
            limit: Maximum searches to return
            
        Returns:
            List of recent searches
        """
        query = (
            select(RecentSearch)
            .where(
                and_(
                    RecentSearch.visitor_id == visitor_id,
                    RecentSearch.is_deleted == False,
                )
            )
            .order_by(desc(RecentSearch.searched_at))
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def track_search_re_execution(
        self,
        search_id: UUID,
    ) -> RecentSearch:
        """
        Track when a search is re-executed.
        
        Args:
            search_id: Search ID
            
        Returns:
            Updated RecentSearch instance
        """
        search = self.find_by_id(search_id)
        if not search:
            raise ValueError(f"Search not found: {search_id}")
        
        search.times_re_executed += 1
        search.last_re_executed_at = datetime.utcnow()
        
        self.session.flush()
        return search

    def get_popular_searches(
        self,
        visitor_id: UUID,
        min_re_executions: int = 2,
    ) -> List[RecentSearch]:
        """
        Get searches that have been re-executed multiple times.
        
        Args:
            visitor_id: Visitor ID
            min_re_executions: Minimum re-execution count
            
        Returns:
            List of popular searches
        """
        query = (
            select(RecentSearch)
            .where(
                and_(
                    RecentSearch.visitor_id == visitor_id,
                    RecentSearch.is_deleted == False,
                    RecentSearch.times_re_executed >= min_re_executions,
                )
            )
            .order_by(desc(RecentSearch.times_re_executed))
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def cleanup_old_searches(
        self,
        visitor_id: UUID,
        keep_count: int = 50,
    ) -> int:
        """
        Clean up old searches, keeping only the most recent.
        
        Args:
            visitor_id: Visitor ID
            keep_count: Number of searches to keep
            
        Returns:
            Number of searches deleted
        """
        # Get all searches ordered by date
        query = (
            select(RecentSearch)
            .where(
                and_(
                    RecentSearch.visitor_id == visitor_id,
                    RecentSearch.is_deleted == False,
                )
            )
            .order_by(desc(RecentSearch.searched_at))
        )
        
        result = self.session.execute(query)
        searches = list(result.scalars().all())
        
        # Soft delete searches beyond keep_count
        deleted_count = 0
        for search in searches[keep_count:]:
            search.is_deleted = True
            search.deleted_at = datetime.utcnow()
            deleted_count += 1
        
        self.session.flush()
        return deleted_count


class RecentlyViewedHostelRepository(BaseRepository[RecentlyViewedHostel]):
    """Repository for RecentlyViewedHostel entity."""

    def __init__(self, session: Session):
        super().__init__(RecentlyViewedHostel, session)

    def track_hostel_view(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
        hostel_name: str,
        hostel_slug: str,
        hostel_city: str,
        starting_price: Decimal,
        average_rating: Decimal = Decimal("0.00"),
        cover_image_url: Optional[str] = None,
        time_spent_seconds: int = 0,
        sections_viewed: Optional[List[str]] = None,
    ) -> RecentlyViewedHostel:
        """
        Track a hostel view.
        
        Args:
            visitor_id: Visitor ID
            hostel_id: Hostel ID
            hostel_name: Hostel name
            hostel_slug: Hostel slug
            hostel_city: Hostel city
            starting_price: Starting price
            average_rating: Average rating
            cover_image_url: Cover image URL
            time_spent_seconds: Time spent viewing
            sections_viewed: Sections viewed
            
        Returns:
            RecentlyViewedHostel instance
        """
        # Check if already viewed
        query = select(RecentlyViewedHostel).where(
            and_(
                RecentlyViewedHostel.visitor_id == visitor_id,
                RecentlyViewedHostel.hostel_id == hostel_id,
                RecentlyViewedHostel.is_deleted == False,
            )
        )
        result = self.session.execute(query)
        viewed = result.scalar_one_or_none()
        
        if viewed:
            # Update existing
            viewed.view_count += 1
            viewed.last_viewed_at = datetime.utcnow()
            viewed.time_spent_seconds += time_spent_seconds
            
            # Merge sections viewed
            if sections_viewed:
                current_sections = set(viewed.sections_viewed or [])
                current_sections.update(sections_viewed)
                viewed.sections_viewed = list(current_sections)
            
            self.session.flush()
            return viewed
        
        # Create new
        viewed = RecentlyViewedHostel(
            visitor_id=visitor_id,
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            hostel_slug=hostel_slug,
            hostel_city=hostel_city,
            starting_price=starting_price,
            average_rating=average_rating,
            cover_image_url=cover_image_url,
            view_count=1,
            first_viewed_at=datetime.utcnow(),
            last_viewed_at=datetime.utcnow(),
            time_spent_seconds=time_spent_seconds,
            sections_viewed=sections_viewed or [],
        )
        
        self.session.add(viewed)
        self.session.flush()
        
        return viewed

    def get_recently_viewed(
        self,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[RecentlyViewedHostel]:
        """
        Get recently viewed hostels.
        
        Args:
            visitor_id: Visitor ID
            limit: Maximum hostels to return
            
        Returns:
            List of recently viewed hostels
        """
        query = (
            select(RecentlyViewedHostel)
            .where(
                and_(
                    RecentlyViewedHostel.visitor_id == visitor_id,
                    RecentlyViewedHostel.is_deleted == False,
                )
            )
            .order_by(desc(RecentlyViewedHostel.last_viewed_at))
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_most_viewed(
        self,
        visitor_id: UUID,
        limit: int = 5,
    ) -> List[RecentlyViewedHostel]:
        """
        Get most frequently viewed hostels.
        
        Args:
            visitor_id: Visitor ID
            limit: Maximum hostels to return
            
        Returns:
            List of most viewed hostels
        """
        query = (
            select(RecentlyViewedHostel)
            .where(
                and_(
                    RecentlyViewedHostel.visitor_id == visitor_id,
                    RecentlyViewedHostel.is_deleted == False,
                )
            )
            .order_by(desc(RecentlyViewedHostel.view_count))
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def mark_action_taken(
        self,
        viewed_id: UUID,
        action_type: str,
    ) -> RecentlyViewedHostel:
        """
        Mark that an action was taken on a viewed hostel.
        
        Args:
            viewed_id: RecentlyViewedHostel ID
            action_type: Type of action (favorite, inquiry, booking)
            
        Returns:
            Updated RecentlyViewedHostel instance
        """
        viewed = self.find_by_id(viewed_id)
        if not viewed:
            raise ValueError(f"Recently viewed not found: {viewed_id}")
        
        if action_type == "favorite":
            viewed.added_to_favorites = True
        elif action_type == "inquiry":
            viewed.inquiry_sent = True
        elif action_type == "booking":
            viewed.booking_initiated = True
        
        self.session.flush()
        return viewed


class RecommendedHostelRepository(BaseRepository[RecommendedHostel]):
    """Repository for RecommendedHostel entity."""

    def __init__(self, session: Session):
        super().__init__(RecommendedHostel, session)

    def create_recommendation(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
        hostel_name: str,
        hostel_city: str,
        starting_price: Decimal,
        average_rating: Decimal,
        available_beds: int,
        match_score: Decimal,
        recommendation_rank: int,
        match_reasons: List[str],
        matching_criteria: Dict,
        recommendation_type: str,
        recommendation_algorithm: str,
        cover_image_url: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> RecommendedHostel:
        """
        Create a hostel recommendation.
        
        Args:
            visitor_id: Visitor ID
            hostel_id: Hostel ID
            hostel_name: Hostel name
            hostel_city: Hostel city
            starting_price: Starting price
            average_rating: Average rating
            available_beds: Available beds
            match_score: Match score (0-100)
            recommendation_rank: Rank among recommendations
            match_reasons: Reasons for recommendation
            matching_criteria: Matching criteria details
            recommendation_type: Type of recommendation
            recommendation_algorithm: Algorithm used
            cover_image_url: Cover image URL
            expires_at: Expiration timestamp
            
        Returns:
            Created RecommendedHostel instance
        """
        recommendation = RecommendedHostel(
            visitor_id=visitor_id,
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            hostel_city=hostel_city,
            starting_price=starting_price,
            average_rating=average_rating,
            available_beds=available_beds,
            match_score=match_score,
            recommendation_rank=recommendation_rank,
            match_reasons=match_reasons,
            matching_criteria=matching_criteria,
            recommendation_type=recommendation_type,
            recommendation_algorithm=recommendation_algorithm,
            cover_image_url=cover_image_url,
            generated_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        
        self.session.add(recommendation)
        self.session.flush()
        
        return recommendation

    def get_active_recommendations(
        self,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[RecommendedHostel]:
        """
        Get active recommendations for visitor.
        
        Args:
            visitor_id: Visitor ID
            limit: Maximum recommendations to return
            
        Returns:
            List of active recommendations
        """
        now = datetime.utcnow()
        
        query = (
            select(RecommendedHostel)
            .where(
                and_(
                    RecommendedHostel.visitor_id == visitor_id,
                    or_(
                        RecommendedHostel.expires_at.is_(None),
                        RecommendedHostel.expires_at > now,
                    ),
                )
            )
            .order_by(RecommendedHostel.recommendation_rank)
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def mark_recommendation_viewed(
        self,
        recommendation_id: UUID,
    ) -> RecommendedHostel:
        """
        Mark recommendation as viewed.
        
        Args:
            recommendation_id: Recommendation ID
            
        Returns:
            Updated RecommendedHostel instance
        """
        recommendation = self.find_by_id(recommendation_id)
        if not recommendation:
            raise ValueError(f"Recommendation not found: {recommendation_id}")
        
        recommendation.was_viewed = True
        recommendation.viewed_at = datetime.utcnow()
        
        self.session.flush()
        return recommendation

    def mark_recommendation_clicked(
        self,
        recommendation_id: UUID,
    ) -> RecommendedHostel:
        """
        Mark recommendation as clicked.
        
        Args:
            recommendation_id: Recommendation ID
            
        Returns:
            Updated RecommendedHostel instance
        """
        recommendation = self.find_by_id(recommendation_id)
        if not recommendation:
            raise ValueError(f"Recommendation not found: {recommendation_id}")
        
        recommendation.was_clicked = True
        if not recommendation.was_viewed:
            recommendation.was_viewed = True
            recommendation.viewed_at = datetime.utcnow()
        
        self.session.flush()
        return recommendation

    def mark_recommendation_converted(
        self,
        recommendation_id: UUID,
    ) -> RecommendedHostel:
        """
        Mark recommendation as converted (booking made).
        
        Args:
            recommendation_id: Recommendation ID
            
        Returns:
            Updated RecommendedHostel instance
        """
        recommendation = self.find_by_id(recommendation_id)
        if not recommendation:
            raise ValueError(f"Recommendation not found: {recommendation_id}")
        
        recommendation.was_converted = True
        
        self.session.flush()
        return recommendation

    def get_recommendation_performance(
        self,
        visitor_id: UUID,
        days: int = 30,
    ) -> Dict:
        """
        Get recommendation performance metrics.
        
        Args:
            visitor_id: Visitor ID
            days: Days to analyze
            
        Returns:
            Dictionary containing performance metrics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(RecommendedHostel).where(
            and_(
                RecommendedHostel.visitor_id == visitor_id,
                RecommendedHostel.generated_at >= cutoff_date,
            )
        )
        
        result = self.session.execute(query)
        recommendations = list(result.scalars().all())
        
        if not recommendations:
            return {
                "total_recommendations": 0,
                "view_rate": Decimal("0.00"),
                "click_rate": Decimal("0.00"),
                "conversion_rate": Decimal("0.00"),
            }
        
        total = len(recommendations)
        viewed = sum(1 for r in recommendations if r.was_viewed)
        clicked = sum(1 for r in recommendations if r.was_clicked)
        converted = sum(1 for r in recommendations if r.was_converted)
        
        return {
            "total_recommendations": total,
            "view_rate": (Decimal(viewed) / total * 100).quantize(Decimal("0.01")),
            "click_rate": (Decimal(clicked) / total * 100).quantize(Decimal("0.01")),
            "conversion_rate": (Decimal(converted) / total * 100).quantize(Decimal("0.01")),
        }


class PriceDropAlertRepository(BaseRepository[PriceDropAlert]):
    """Repository for PriceDropAlert entity."""

    def __init__(self, session: Session):
        super().__init__(PriceDropAlert, session)

    def create_price_drop_alert(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
        favorite_id: Optional[UUID],
        hostel_name: str,
        hostel_slug: str,
        previous_price: Decimal,
        new_price: Decimal,
    ) -> PriceDropAlert:
        """
        Create a price drop alert.
        
        Args:
            visitor_id: Visitor ID
            hostel_id: Hostel ID
            favorite_id: Favorite ID (if applicable)
            hostel_name: Hostel name
            hostel_slug: Hostel slug
            previous_price: Previous price
            new_price: New reduced price
            
        Returns:
            Created PriceDropAlert instance
        """
        discount_amount = previous_price - new_price
        discount_percentage = (discount_amount / previous_price * 100).quantize(
            Decimal("0.01")
        )
        
        alert = PriceDropAlert(
            visitor_id=visitor_id,
            hostel_id=hostel_id,
            favorite_id=favorite_id,
            hostel_name=hostel_name,
            hostel_slug=hostel_slug,
            previous_price=previous_price,
            new_price=new_price,
            discount_amount=discount_amount,
            discount_percentage=discount_percentage,
        )
        
        self.session.add(alert)
        self.session.flush()
        
        return alert

    def get_unread_alerts(
        self,
        visitor_id: UUID,
    ) -> List[PriceDropAlert]:
        """
        Get unread price drop alerts.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            List of unread alerts
        """
        query = (
            select(PriceDropAlert)
            .where(
                and_(
                    PriceDropAlert.visitor_id == visitor_id,
                    PriceDropAlert.is_read == False,
                )
            )
            .order_by(desc(PriceDropAlert.created_at))
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def mark_alert_read(
        self,
        alert_id: UUID,
    ) -> PriceDropAlert:
        """
        Mark alert as read.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            Updated PriceDropAlert instance
        """
        alert = self.find_by_id(alert_id)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        
        alert.is_read = True
        alert.read_at = datetime.utcnow()
        
        self.session.flush()
        return alert

    def mark_notification_sent(
        self,
        alert_id: UUID,
        channels: List[str],
    ) -> PriceDropAlert:
        """
        Mark that notification was sent.
        
        Args:
            alert_id: Alert ID
            channels: Channels used (email, sms, push)
            
        Returns:
            Updated PriceDropAlert instance
        """
        alert = self.find_by_id(alert_id)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        
        if "email" in channels:
            alert.email_sent = True
        if "sms" in channels:
            alert.sms_sent = True
        if "push" in channels:
            alert.push_sent = True
        
        alert.notification_sent_at = datetime.utcnow()
        
        self.session.flush()
        return alert


class AvailabilityAlertRepository(BaseRepository[AvailabilityAlert]):
    """Repository for AvailabilityAlert entity."""

    def __init__(self, session: Session):
        super().__init__(AvailabilityAlert, session)

    def create_availability_alert(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
        favorite_id: Optional[UUID],
        hostel_name: str,
        hostel_slug: str,
        room_type: str,
        available_beds: int,
        message: str,
    ) -> AvailabilityAlert:
        """
        Create an availability alert.
        
        Args:
            visitor_id: Visitor ID
            hostel_id: Hostel ID
            favorite_id: Favorite ID (if applicable)
            hostel_name: Hostel name
            hostel_slug: Hostel slug
            room_type: Room type now available
            available_beds: Number of beds available
            message: Alert message
            
        Returns:
            Created AvailabilityAlert instance
        """
        alert = AvailabilityAlert(
            visitor_id=visitor_id,
            hostel_id=hostel_id,
            favorite_id=favorite_id,
            hostel_name=hostel_name,
            hostel_slug=hostel_slug,
            room_type=room_type,
            available_beds=available_beds,
            message=message,
        )
        
        self.session.add(alert)
        self.session.flush()
        
        return alert

    def get_unread_alerts(
        self,
        visitor_id: UUID,
    ) -> List[AvailabilityAlert]:
        """
        Get unread availability alerts.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            List of unread alerts
        """
        query = (
            select(AvailabilityAlert)
            .where(
                and_(
                    AvailabilityAlert.visitor_id == visitor_id,
                    AvailabilityAlert.is_read == False,
                )
            )
            .order_by(desc(AvailabilityAlert.created_at))
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def mark_alert_read(
        self,
        alert_id: UUID,
    ) -> AvailabilityAlert:
        """
        Mark alert as read.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            Updated AvailabilityAlert instance
        """
        alert = self.find_by_id(alert_id)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        
        alert.is_read = True
        alert.read_at = datetime.utcnow()
        
        self.session.flush()
        return alert

    def mark_notification_sent(
        self,
        alert_id: UUID,
        channels: List[str],
    ) -> AvailabilityAlert:
        """
        Mark that notification was sent.
        
        Args:
            alert_id: Alert ID
            channels: Channels used (email, sms, push)
            
        Returns:
            Updated AvailabilityAlert instance
        """
        alert = self.find_by_id(alert_id)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        
        if "email" in channels:
            alert.email_sent = True
        if "sms" in channels:
            alert.sms_sent = True
        if "push" in channels:
            alert.push_sent = True
        
        alert.notification_sent_at = datetime.utcnow()
        
        self.session.flush()
        return alert


class VisitorActivityRepository(BaseRepository[VisitorActivity]):
    """Repository for VisitorActivity entity."""

    def __init__(self, session: Session):
        super().__init__(VisitorActivity, session)

    def log_activity(
        self,
        visitor_id: UUID,
        activity_type: str,
        activity_category: str,
        activity_description: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        device_type: Optional[str] = None,
        activity_data: Optional[Dict] = None,
    ) -> VisitorActivity:
        """
        Log a visitor activity.
        
        Args:
            visitor_id: Visitor ID
            activity_type: Type of activity
            activity_category: Activity category
            activity_description: Human-readable description
            entity_type: Related entity type
            entity_id: Related entity ID
            session_id: Session ID
            device_type: Device type
            activity_data: Additional activity data
            
        Returns:
            Created VisitorActivity instance
        """
        activity = VisitorActivity(
            visitor_id=visitor_id,
            activity_type=activity_type,
            activity_category=activity_category,
            activity_description=activity_description,
            entity_type=entity_type,
            entity_id=entity_id,
            session_id=session_id,
            device_type=device_type,
            occurred_at=datetime.utcnow(),
            activity_data=activity_data or {},
        )
        
        self.session.add(activity)
        self.session.flush()
        
        return activity

    def get_recent_activities(
        self,
        visitor_id: UUID,
        limit: int = 20,
        activity_types: Optional[List[str]] = None,
    ) -> List[VisitorActivity]:
        """
        Get recent visitor activities.
        
        Args:
            visitor_id: Visitor ID
            limit: Maximum activities to return
            activity_types: Filter by activity types
            
        Returns:
            List of recent activities
        """
        query = select(VisitorActivity).where(
            VisitorActivity.visitor_id == visitor_id
        )
        
        if activity_types:
            query = query.where(VisitorActivity.activity_type.in_(activity_types))
        
        query = query.order_by(desc(VisitorActivity.occurred_at)).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_activity_summary(
        self,
        visitor_id: UUID,
        days: int = 30,
    ) -> Dict:
        """
        Get activity summary for visitor.
        
        Args:
            visitor_id: Visitor ID
            days: Days to analyze
            
        Returns:
            Dictionary containing activity summary
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(VisitorActivity).where(
            and_(
                VisitorActivity.visitor_id == visitor_id,
                VisitorActivity.occurred_at >= cutoff_date,
            )
        )
        
        result = self.session.execute(query)
        activities = list(result.scalars().all())
        
        # Count by type
        type_counts = {}
        for activity in activities:
            type_counts[activity.activity_type] = type_counts.get(
                activity.activity_type, 0
            ) + 1
        
        # Count by category
        category_counts = {}
        for activity in activities:
            category_counts[activity.activity_category] = category_counts.get(
                activity.activity_category, 0
            ) + 1
        
        return {
            "total_activities": len(activities),
            "activities_by_type": type_counts,
            "activities_by_category": category_counts,
            "most_common_activity": max(type_counts, key=type_counts.get) if type_counts else None,
        }