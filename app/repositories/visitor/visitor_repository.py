# --- File: app/repositories/visitor/visitor_repository.py ---
"""
Visitor repository for comprehensive visitor management.

This module provides repository operations for visitor management including
lifecycle management, behavior tracking, conversion optimization, and personalization.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.visitor.visitor import (
    Visitor,
    VisitorEngagement,
    VisitorJourney,
    VisitorSegment,
    VisitorSession,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginationResult
from app.repositories.base.specifications import Specification


class VisitorRepository(BaseRepository[Visitor]):
    """
    Repository for Visitor entity with advanced querying and analytics.
    
    Provides comprehensive visitor management including behavior tracking,
    conversion optimization, and personalized experiences.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(Visitor, session)

    # ==================== Core CRUD Operations ====================

    def create_visitor(
        self,
        user_id: UUID,
        email: str,
        full_name: str,
        phone: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Visitor:
        """
        Create a new visitor profile.
        
        Args:
            user_id: Associated user ID
            email: Visitor email address
            full_name: Full name
            phone: Optional phone number
            metadata: Additional metadata
            
        Returns:
            Created Visitor instance
        """
        visitor = Visitor(
            user_id=user_id,
            email=email,
            full_name=full_name,
            phone=phone,
            engagement_score=Decimal("0.00"),
            search_metadata=metadata or {},
            preferences_metadata={},
        )
        
        self.session.add(visitor)
        self.session.flush()
        
        return visitor

    def find_by_user_id(self, user_id: UUID) -> Optional[Visitor]:
        """
        Find visitor by associated user ID.
        
        Args:
            user_id: User ID to search for
            
        Returns:
            Visitor instance if found, None otherwise
        """
        query = (
            select(Visitor)
            .where(Visitor.user_id == user_id)
            .where(Visitor.is_deleted == False)
            .options(selectinload(Visitor.preferences))
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_by_email(self, email: str) -> Optional[Visitor]:
        """
        Find visitor by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            Visitor instance if found, None otherwise
        """
        query = (
            select(Visitor)
            .where(func.lower(Visitor.email) == email.lower())
            .where(Visitor.is_deleted == False)
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_by_phone(self, phone: str) -> Optional[Visitor]:
        """
        Find visitor by phone number.
        
        Args:
            phone: Phone number to search for
            
        Returns:
            Visitor instance if found, None otherwise
        """
        query = (
            select(Visitor)
            .where(Visitor.phone == phone)
            .where(Visitor.is_deleted == False)
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def get_with_full_profile(self, visitor_id: UUID) -> Optional[Visitor]:
        """
        Get visitor with all related data eagerly loaded.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Visitor with full profile data
        """
        query = (
            select(Visitor)
            .where(Visitor.id == visitor_id)
            .where(Visitor.is_deleted == False)
            .options(
                selectinload(Visitor.preferences),
                selectinload(Visitor.user),
            )
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    # ==================== Visitor Intelligence & Tracking ====================

    def track_visitor_activity(
        self,
        visitor_id: UUID,
        activity_type: str,
        increment_count: int = 1,
    ) -> Visitor:
        """
        Track visitor activity and update metrics.
        
        Args:
            visitor_id: Visitor ID
            activity_type: Type of activity (search, view, inquiry, booking)
            increment_count: Count to increment
            
        Returns:
            Updated Visitor instance
        """
        visitor = self.find_by_id(visitor_id)
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        # Update activity counters
        if activity_type == "search":
            visitor.total_searches += increment_count
            visitor.last_search_at = datetime.utcnow()
        elif activity_type == "view":
            visitor.total_hostel_views += increment_count
        elif activity_type == "inquiry":
            visitor.total_inquiries += increment_count
        elif activity_type == "booking":
            visitor.total_bookings += increment_count
            visitor.last_booking_at = datetime.utcnow()
        
        # Update last active timestamp
        visitor.last_active_at = datetime.utcnow()
        
        # Recalculate engagement score
        visitor.engagement_score = self._calculate_engagement_score(visitor)
        
        self.session.flush()
        return visitor

    def update_engagement_score(self, visitor_id: UUID) -> Decimal:
        """
        Recalculate and update visitor engagement score.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Updated engagement score
        """
        visitor = self.find_by_id(visitor_id)
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        engagement_score = self._calculate_engagement_score(visitor)
        visitor.engagement_score = engagement_score
        
        self.session.flush()
        return engagement_score

    def _calculate_engagement_score(self, visitor: Visitor) -> Decimal:
        """
        Calculate engagement score based on visitor activity.
        
        Scoring formula:
        - Searches: 1 point each (max 20)
        - Hostel views: 2 points each (max 30)
        - Inquiries: 10 points each (max 25)
        - Bookings: 25 points each (max 25)
        - Recency bonus: Up to 10 points based on last activity
        
        Args:
            visitor: Visitor instance
            
        Returns:
            Engagement score (0-100)
        """
        score = Decimal("0.00")
        
        # Search activity (max 20 points)
        score += min(Decimal(visitor.total_searches), Decimal("20"))
        
        # View activity (max 30 points)
        score += min(Decimal(visitor.total_hostel_views * 2), Decimal("30"))
        
        # Inquiry activity (max 25 points)
        score += min(Decimal(visitor.total_inquiries * 10), Decimal("25"))
        
        # Booking activity (max 25 points)
        score += min(Decimal(visitor.total_bookings * 25), Decimal("25"))
        
        # Recency bonus (max 10 points)
        if visitor.last_active_at:
            days_since_active = (datetime.utcnow() - visitor.last_active_at).days
            if days_since_active == 0:
                score += Decimal("10")
            elif days_since_active <= 7:
                score += Decimal("7")
            elif days_since_active <= 30:
                score += Decimal("3")
        
        return min(score, Decimal("100.00"))

    def update_conversion_likelihood(
        self,
        visitor_id: UUID,
        likelihood: Decimal,
    ) -> Visitor:
        """
        Update visitor's conversion likelihood score.
        
        Args:
            visitor_id: Visitor ID
            likelihood: Predicted conversion likelihood (0-100)
            
        Returns:
            Updated Visitor instance
        """
        visitor = self.find_by_id(visitor_id)
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        visitor.conversion_likelihood = likelihood
        self.session.flush()
        
        return visitor

    def assign_visitor_segment(
        self,
        visitor_id: UUID,
        segment: str,
    ) -> Visitor:
        """
        Assign visitor to a segment.
        
        Args:
            visitor_id: Visitor ID
            segment: Segment identifier
            
        Returns:
            Updated Visitor instance
        """
        visitor = self.find_by_id(visitor_id)
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        visitor.visitor_segment = segment
        self.session.flush()
        
        return visitor

    # ==================== Visitor Search & Filtering ====================

    def find_active_visitors(
        self,
        days: int = 30,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginationResult[Visitor]:
        """
        Find visitors active within specified days.
        
        Args:
            days: Number of days to look back
            pagination: Pagination parameters
            
        Returns:
            Paginated list of active visitors
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = (
            select(Visitor)
            .where(Visitor.is_deleted == False)
            .where(Visitor.last_active_at >= cutoff_date)
            .order_by(desc(Visitor.last_active_at))
        )
        
        return self._paginate_query(query, pagination)

    def find_high_intent_visitors(
        self,
        min_engagement_score: Decimal = Decimal("70.00"),
        pagination: Optional[PaginationParams] = None,
    ) -> PaginationResult[Visitor]:
        """
        Find visitors with high purchase intent.
        
        Args:
            min_engagement_score: Minimum engagement score
            pagination: Pagination parameters
            
        Returns:
            Paginated list of high-intent visitors
        """
        query = (
            select(Visitor)
            .where(Visitor.is_deleted == False)
            .where(Visitor.engagement_score >= min_engagement_score)
            .where(Visitor.total_inquiries > 0)
            .order_by(desc(Visitor.engagement_score))
        )
        
        return self._paginate_query(query, pagination)

    def find_by_segment(
        self,
        segment: str,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginationResult[Visitor]:
        """
        Find visitors in a specific segment.
        
        Args:
            segment: Segment identifier
            pagination: Pagination parameters
            
        Returns:
            Paginated list of visitors in segment
        """
        query = (
            select(Visitor)
            .where(Visitor.is_deleted == False)
            .where(Visitor.visitor_segment == segment)
            .order_by(desc(Visitor.created_at))
        )
        
        return self._paginate_query(query, pagination)

    def find_visitors_with_criteria(
        self,
        preferred_cities: Optional[List[str]] = None,
        budget_range: Optional[Tuple[Decimal, Decimal]] = None,
        has_bookings: Optional[bool] = None,
        min_engagement_score: Optional[Decimal] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginationResult[Visitor]:
        """
        Find visitors matching multiple criteria.
        
        Args:
            preferred_cities: List of preferred cities
            budget_range: Tuple of (min_budget, max_budget)
            has_bookings: Filter by booking status
            min_engagement_score: Minimum engagement score
            pagination: Pagination parameters
            
        Returns:
            Paginated list of matching visitors
        """
        query = select(Visitor).where(Visitor.is_deleted == False)
        
        # City filter
        if preferred_cities:
            query = query.where(
                Visitor.preferred_cities.overlap(preferred_cities)
            )
        
        # Budget filter
        if budget_range:
            min_budget, max_budget = budget_range
            if min_budget:
                query = query.where(
                    or_(
                        Visitor.budget_max >= min_budget,
                        Visitor.budget_max.is_(None),
                    )
                )
            if max_budget:
                query = query.where(
                    or_(
                        Visitor.budget_min <= max_budget,
                        Visitor.budget_min.is_(None),
                    )
                )
        
        # Booking filter
        if has_bookings is not None:
            if has_bookings:
                query = query.where(Visitor.total_bookings > 0)
            else:
                query = query.where(Visitor.total_bookings == 0)
        
        # Engagement score filter
        if min_engagement_score:
            query = query.where(Visitor.engagement_score >= min_engagement_score)
        
        query = query.order_by(desc(Visitor.engagement_score))
        
        return self._paginate_query(query, pagination)

    # ==================== Visitor Analytics ====================

    def get_visitor_statistics(self) -> Dict:
        """
        Get comprehensive visitor statistics.
        
        Returns:
            Dictionary containing visitor statistics
        """
        # Total visitors
        total_query = select(func.count(Visitor.id)).where(
            Visitor.is_deleted == False
        )
        total_visitors = self.session.execute(total_query).scalar_one()
        
        # Active visitors (last 30 days)
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        active_query = select(func.count(Visitor.id)).where(
            and_(
                Visitor.is_deleted == False,
                Visitor.last_active_at >= cutoff_date,
            )
        )
        active_visitors = self.session.execute(active_query).scalar_one()
        
        # Visitors with bookings
        with_bookings_query = select(func.count(Visitor.id)).where(
            and_(
                Visitor.is_deleted == False,
                Visitor.total_bookings > 0,
            )
        )
        visitors_with_bookings = self.session.execute(with_bookings_query).scalar_one()
        
        # Average engagement score
        avg_score_query = select(func.avg(Visitor.engagement_score)).where(
            Visitor.is_deleted == False
        )
        avg_engagement_score = self.session.execute(avg_score_query).scalar_one() or Decimal("0.00")
        
        # Conversion rate
        conversion_rate = Decimal("0.00")
        if total_visitors > 0:
            conversion_rate = (
                Decimal(visitors_with_bookings) / Decimal(total_visitors) * 100
            ).quantize(Decimal("0.01"))
        
        return {
            "total_visitors": total_visitors,
            "active_visitors": active_visitors,
            "visitors_with_bookings": visitors_with_bookings,
            "conversion_rate": conversion_rate,
            "average_engagement_score": avg_engagement_score,
        }

    def get_engagement_distribution(self) -> List[Dict]:
        """
        Get distribution of visitors by engagement score ranges.
        
        Returns:
            List of engagement score range distributions
        """
        ranges = [
            ("0-20", Decimal("0"), Decimal("20")),
            ("21-40", Decimal("21"), Decimal("40")),
            ("41-60", Decimal("41"), Decimal("60")),
            ("61-80", Decimal("61"), Decimal("80")),
            ("81-100", Decimal("81"), Decimal("100")),
        ]
        
        distribution = []
        
        for label, min_score, max_score in ranges:
            query = select(func.count(Visitor.id)).where(
                and_(
                    Visitor.is_deleted == False,
                    Visitor.engagement_score >= min_score,
                    Visitor.engagement_score <= max_score,
                )
            )
            count = self.session.execute(query).scalar_one()
            
            distribution.append({
                "range": label,
                "count": count,
                "min_score": min_score,
                "max_score": max_score,
            })
        
        return distribution

    def get_conversion_funnel(self) -> Dict:
        """
        Get visitor conversion funnel metrics.
        
        Returns:
            Dictionary containing funnel metrics
        """
        # Total visitors
        total_query = select(func.count(Visitor.id)).where(
            Visitor.is_deleted == False
        )
        total = self.session.execute(total_query).scalar_one()
        
        # Visitors who searched
        searched_query = select(func.count(Visitor.id)).where(
            and_(
                Visitor.is_deleted == False,
                Visitor.total_searches > 0,
            )
        )
        searched = self.session.execute(searched_query).scalar_one()
        
        # Visitors who viewed hostels
        viewed_query = select(func.count(Visitor.id)).where(
            and_(
                Visitor.is_deleted == False,
                Visitor.total_hostel_views > 0,
            )
        )
        viewed = self.session.execute(viewed_query).scalar_one()
        
        # Visitors who sent inquiries
        inquired_query = select(func.count(Visitor.id)).where(
            and_(
                Visitor.is_deleted == False,
                Visitor.total_inquiries > 0,
            )
        )
        inquired = self.session.execute(inquired_query).scalar_one()
        
        # Visitors who booked
        booked_query = select(func.count(Visitor.id)).where(
            and_(
                Visitor.is_deleted == False,
                Visitor.total_bookings > 0,
            )
        )
        booked = self.session.execute(booked_query).scalar_one()
        
        def calculate_rate(numerator: int, denominator: int) -> Decimal:
            if denominator == 0:
                return Decimal("0.00")
            return (Decimal(numerator) / Decimal(denominator) * 100).quantize(
                Decimal("0.01")
            )
        
        return {
            "total_visitors": total,
            "searched": searched,
            "search_rate": calculate_rate(searched, total),
            "viewed": viewed,
            "view_rate": calculate_rate(viewed, searched),
            "inquired": inquired,
            "inquiry_rate": calculate_rate(inquired, viewed),
            "booked": booked,
            "booking_rate": calculate_rate(booked, inquired),
            "overall_conversion_rate": calculate_rate(booked, total),
        }

    def get_top_visitors_by_activity(
        self,
        limit: int = 10,
        activity_type: Optional[str] = None,
    ) -> List[Visitor]:
        """
        Get top visitors by activity level.
        
        Args:
            limit: Number of top visitors to return
            activity_type: Specific activity type to rank by
            
        Returns:
            List of top visitors
        """
        query = select(Visitor).where(Visitor.is_deleted == False)
        
        if activity_type == "searches":
            query = query.order_by(desc(Visitor.total_searches))
        elif activity_type == "views":
            query = query.order_by(desc(Visitor.total_hostel_views))
        elif activity_type == "inquiries":
            query = query.order_by(desc(Visitor.total_inquiries))
        elif activity_type == "bookings":
            query = query.order_by(desc(Visitor.total_bookings))
        else:
            query = query.order_by(desc(Visitor.engagement_score))
        
        query = query.limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Visitor Preferences Management ====================

    def update_budget_preferences(
        self,
        visitor_id: UUID,
        budget_min: Optional[Decimal] = None,
        budget_max: Optional[Decimal] = None,
    ) -> Visitor:
        """
        Update visitor budget preferences.
        
        Args:
            visitor_id: Visitor ID
            budget_min: Minimum budget
            budget_max: Maximum budget
            
        Returns:
            Updated Visitor instance
        """
        visitor = self.find_by_id(visitor_id)
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        if budget_min is not None:
            visitor.budget_min = budget_min
        if budget_max is not None:
            visitor.budget_max = budget_max
        
        self.session.flush()
        return visitor

    def update_location_preferences(
        self,
        visitor_id: UUID,
        preferred_cities: Optional[List[str]] = None,
        preferred_areas: Optional[List[str]] = None,
    ) -> Visitor:
        """
        Update visitor location preferences.
        
        Args:
            visitor_id: Visitor ID
            preferred_cities: List of preferred cities
            preferred_areas: List of preferred areas
            
        Returns:
            Updated Visitor instance
        """
        visitor = self.find_by_id(visitor_id)
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        if preferred_cities is not None:
            visitor.preferred_cities = preferred_cities
        if preferred_areas is not None:
            visitor.preferred_areas = preferred_areas
        
        self.session.flush()
        return visitor

    def update_amenity_preferences(
        self,
        visitor_id: UUID,
        required_amenities: Optional[List[str]] = None,
        preferred_amenities: Optional[List[str]] = None,
    ) -> Visitor:
        """
        Update visitor amenity preferences.
        
        Args:
            visitor_id: Visitor ID
            required_amenities: Required amenities list
            preferred_amenities: Preferred amenities list
            
        Returns:
            Updated Visitor instance
        """
        visitor = self.find_by_id(visitor_id)
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        if required_amenities is not None:
            visitor.required_amenities = required_amenities
        if preferred_amenities is not None:
            visitor.preferred_amenities = preferred_amenities
        
        self.session.flush()
        return visitor

    def update_notification_preferences(
        self,
        visitor_id: UUID,
        email_notifications: Optional[bool] = None,
        sms_notifications: Optional[bool] = None,
        push_notifications: Optional[bool] = None,
        notify_on_price_drop: Optional[bool] = None,
        notify_on_availability: Optional[bool] = None,
        notify_on_new_listings: Optional[bool] = None,
    ) -> Visitor:
        """
        Update visitor notification preferences.
        
        Args:
            visitor_id: Visitor ID
            email_notifications: Enable/disable email notifications
            sms_notifications: Enable/disable SMS notifications
            push_notifications: Enable/disable push notifications
            notify_on_price_drop: Enable/disable price drop notifications
            notify_on_availability: Enable/disable availability notifications
            notify_on_new_listings: Enable/disable new listing notifications
            
        Returns:
            Updated Visitor instance
        """
        visitor = self.find_by_id(visitor_id)
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        if email_notifications is not None:
            visitor.email_notifications = email_notifications
        if sms_notifications is not None:
            visitor.sms_notifications = sms_notifications
        if push_notifications is not None:
            visitor.push_notifications = push_notifications
        if notify_on_price_drop is not None:
            visitor.notify_on_price_drop = notify_on_price_drop
        if notify_on_availability is not None:
            visitor.notify_on_availability = notify_on_availability
        if notify_on_new_listings is not None:
            visitor.notify_on_new_listings = notify_on_new_listings
        
        self.session.flush()
        return visitor

    # ==================== Visitor Sessions ====================

    def create_visitor_session(
        self,
        visitor_id: UUID,
        session_id: str,
        device_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
    ) -> VisitorSession:
        """
        Create a new visitor session.
        
        Args:
            visitor_id: Visitor ID
            session_id: Unique session identifier
            device_type: Device type (desktop/mobile/tablet)
            ip_address: IP address
            user_agent: User agent string
            utm_source: UTM source parameter
            utm_medium: UTM medium parameter
            utm_campaign: UTM campaign parameter
            
        Returns:
            Created VisitorSession instance
        """
        session = VisitorSession(
            visitor_id=visitor_id,
            session_id=session_id,
            device_type=device_type,
            started_at=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
        )
        
        self.session.add(session)
        self.session.flush()
        
        return session

    def get_visitor_sessions(
        self,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[VisitorSession]:
        """
        Get recent visitor sessions.
        
        Args:
            visitor_id: Visitor ID
            limit: Maximum number of sessions to return
            
        Returns:
            List of recent sessions
        """
        query = (
            select(VisitorSession)
            .where(VisitorSession.visitor_id == visitor_id)
            .order_by(desc(VisitorSession.started_at))
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Bulk Operations ====================

    def bulk_update_engagement_scores(
        self,
        visitor_ids: Optional[List[UUID]] = None,
    ) -> int:
        """
        Bulk update engagement scores for visitors.
        
        Args:
            visitor_ids: Optional list of specific visitor IDs to update
            
        Returns:
            Number of visitors updated
        """
        query = select(Visitor).where(Visitor.is_deleted == False)
        
        if visitor_ids:
            query = query.where(Visitor.id.in_(visitor_ids))
        
        result = self.session.execute(query)
        visitors = result.scalars().all()
        
        count = 0
        for visitor in visitors:
            visitor.engagement_score = self._calculate_engagement_score(visitor)
            count += 1
        
        self.session.flush()
        return count

    def bulk_assign_segments(
        self,
        segment_rules: Dict[str, Dict],
    ) -> int:
        """
        Bulk assign visitors to segments based on rules.
        
        Args:
            segment_rules: Dictionary of segment names to rule criteria
            
        Returns:
            Number of visitors assigned
        """
        count = 0
        
        for segment_name, rules in segment_rules.items():
            query = select(Visitor).where(Visitor.is_deleted == False)
            
            # Apply rules
            if "min_engagement_score" in rules:
                query = query.where(
                    Visitor.engagement_score >= rules["min_engagement_score"]
                )
            if "min_bookings" in rules:
                query = query.where(
                    Visitor.total_bookings >= rules["min_bookings"]
                )
            if "min_inquiries" in rules:
                query = query.where(
                    Visitor.total_inquiries >= rules["min_inquiries"]
                )
            
            result = self.session.execute(query)
            visitors = result.scalars().all()
            
            for visitor in visitors:
                visitor.visitor_segment = segment_name
                count += 1
        
        self.session.flush()
        return count


class VisitorSessionRepository(BaseRepository[VisitorSession]):
    """Repository for VisitorSession entity."""

    def __init__(self, session: Session):
        super().__init__(VisitorSession, session)

    def update_session_activity(
        self,
        session_id: str,
        page_views: int = 0,
        searches_performed: int = 0,
        hostels_viewed: int = 0,
        inquiries_sent: int = 0,
    ) -> VisitorSession:
        """
        Update session activity metrics.
        
        Args:
            session_id: Session identifier
            page_views: Number of page views to add
            searches_performed: Number of searches to add
            hostels_viewed: Number of hostels viewed to add
            inquiries_sent: Number of inquiries sent to add
            
        Returns:
            Updated VisitorSession instance
        """
        query = select(VisitorSession).where(
            VisitorSession.session_id == session_id
        )
        result = self.session.execute(query)
        visitor_session = result.scalar_one_or_none()
        
        if not visitor_session:
            raise ValueError(f"Session not found: {session_id}")
        
        visitor_session.page_views += page_views
        visitor_session.searches_performed += searches_performed
        visitor_session.hostels_viewed += hostels_viewed
        visitor_session.inquiries_sent += inquiries_sent
        
        # Update duration
        if visitor_session.started_at:
            duration = (datetime.utcnow() - visitor_session.started_at).seconds
            visitor_session.duration_seconds = duration
        
        self.session.flush()
        return visitor_session

    def end_session(
        self,
        session_id: str,
        booking_made: bool = False,
        booking_id: Optional[UUID] = None,
    ) -> VisitorSession:
        """
        End a visitor session.
        
        Args:
            session_id: Session identifier
            booking_made: Whether a booking was made
            booking_id: Booking ID if booking was made
            
        Returns:
            Updated VisitorSession instance
        """
        query = select(VisitorSession).where(
            VisitorSession.session_id == session_id
        )
        result = self.session.execute(query)
        visitor_session = result.scalar_one_or_none()
        
        if not visitor_session:
            raise ValueError(f"Session not found: {session_id}")
        
        visitor_session.ended_at = datetime.utcnow()
        visitor_session.booking_made = booking_made
        visitor_session.booking_id = booking_id
        
        # Calculate final duration
        if visitor_session.started_at:
            duration = (visitor_session.ended_at - visitor_session.started_at).seconds
            visitor_session.duration_seconds = duration
        
        self.session.flush()
        return visitor_session


class VisitorEngagementRepository(BaseRepository[VisitorEngagement]):
    """Repository for VisitorEngagement entity."""

    def __init__(self, session: Session):
        super().__init__(VisitorEngagement, session)

    def create_or_update_daily_engagement(
        self,
        visitor_id: UUID,
        engagement_date: datetime,
        page_views: int = 0,
        time_on_site_seconds: int = 0,
        searches_performed: int = 0,
        hostels_viewed: int = 0,
        favorites_added: int = 0,
        inquiries_sent: int = 0,
    ) -> VisitorEngagement:
        """
        Create or update daily engagement record.
        
        Args:
            visitor_id: Visitor ID
            engagement_date: Date of engagement
            page_views: Number of page views
            time_on_site_seconds: Time spent on site
            searches_performed: Number of searches
            hostels_viewed: Number of hostels viewed
            favorites_added: Number of favorites added
            inquiries_sent: Number of inquiries sent
            
        Returns:
            VisitorEngagement instance
        """
        # Try to find existing record
        query = select(VisitorEngagement).where(
            and_(
                VisitorEngagement.visitor_id == visitor_id,
                func.date(VisitorEngagement.engagement_date) == engagement_date.date(),
            )
        )
        result = self.session.execute(query)
        engagement = result.scalar_one_or_none()
        
        if engagement:
            # Update existing
            engagement.page_views += page_views
            engagement.time_on_site_seconds += time_on_site_seconds
            engagement.searches_performed += searches_performed
            engagement.hostels_viewed += hostels_viewed
            engagement.favorites_added += favorites_added
            engagement.inquiries_sent += inquiries_sent
        else:
            # Create new
            engagement = VisitorEngagement(
                visitor_id=visitor_id,
                engagement_date=engagement_date,
                page_views=page_views,
                time_on_site_seconds=time_on_site_seconds,
                searches_performed=searches_performed,
                hostels_viewed=hostels_viewed,
                favorites_added=favorites_added,
                inquiries_sent=inquiries_sent,
            )
            self.session.add(engagement)
        
        # Calculate engagement score
        engagement.engagement_score = self._calculate_daily_score(engagement)
        
        self.session.flush()
        return engagement

    def _calculate_daily_score(self, engagement: VisitorEngagement) -> Decimal:
        """
        Calculate daily engagement score.
        
        Args:
            engagement: VisitorEngagement instance
            
        Returns:
            Engagement score (0-100)
        """
        score = Decimal("0.00")
        
        # Page views (max 20 points)
        score += min(Decimal(engagement.page_views * 2), Decimal("20"))
        
        # Time on site (max 20 points, 1 point per minute)
        minutes = engagement.time_on_site_seconds // 60
        score += min(Decimal(minutes), Decimal("20"))
        
        # Searches (max 20 points)
        score += min(Decimal(engagement.searches_performed * 5), Decimal("20"))
        
        # Hostels viewed (max 20 points)
        score += min(Decimal(engagement.hostels_viewed * 3), Decimal("20"))
        
        # Favorites added (max 10 points)
        score += min(Decimal(engagement.favorites_added * 5), Decimal("10"))
        
        # Inquiries sent (max 10 points)
        score += min(Decimal(engagement.inquiries_sent * 10), Decimal("10"))
        
        return min(score, Decimal("100.00"))