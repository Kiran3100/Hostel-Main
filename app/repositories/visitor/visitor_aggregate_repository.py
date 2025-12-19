# --- File: app/repositories/visitor/visitor_aggregate_repository.py ---
"""
Visitor aggregate repository for complex queries and analytics.

This module provides advanced repository operations that combine data
from multiple visitor-related entities for comprehensive analytics.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.visitor.visitor import Visitor, VisitorEngagement, VisitorSession
from app.models.visitor.visitor_favorite import VisitorFavorite
from app.models.visitor.saved_search import SavedSearch
from app.models.visitor.visitor_dashboard import (
    RecentlyViewedHostel,
    RecommendedHostel,
    PriceDropAlert,
    AvailabilityAlert,
)
from app.repositories.base.base_repository import BaseRepository


class VisitorAggregateRepository:
    """
    Aggregate repository for complex visitor queries and analytics.
    
    Provides cross-entity queries and comprehensive visitor insights.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    # ==================== Visitor Dashboard Aggregates ====================

    def get_visitor_dashboard_summary(
        self,
        visitor_id: UUID,
    ) -> Dict:
        """
        Get comprehensive dashboard summary for visitor.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Dictionary containing dashboard summary
        """
        # Get visitor basic info
        visitor_query = select(Visitor).where(
            and_(
                Visitor.id == visitor_id,
                Visitor.is_deleted == False,
            )
        )
        visitor = self.session.execute(visitor_query).scalar_one_or_none()
        
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        # Count favorites
        favorites_count = self.session.execute(
            select(func.count(VisitorFavorite.id)).where(
                and_(
                    VisitorFavorite.visitor_id == visitor_id,
                    VisitorFavorite.is_deleted == False,
                )
            )
        ).scalar_one()
        
        # Count saved searches
        saved_searches_count = self.session.execute(
            select(func.count(SavedSearch.id)).where(
                and_(
                    SavedSearch.visitor_id == visitor_id,
                    SavedSearch.is_deleted == False,
                    SavedSearch.is_active == True,
                )
            )
        ).scalar_one()
        
        # Count unread price drop alerts
        price_alerts_count = self.session.execute(
            select(func.count(PriceDropAlert.id)).where(
                and_(
                    PriceDropAlert.visitor_id == visitor_id,
                    PriceDropAlert.is_read == False,
                )
            )
        ).scalar_one()
        
        # Count unread availability alerts
        availability_alerts_count = self.session.execute(
            select(func.count(AvailabilityAlert.id)).where(
                and_(
                    AvailabilityAlert.visitor_id == visitor_id,
                    AvailabilityAlert.is_read == False,
                )
            )
        ).scalar_one()
        
        # Get new matches from saved searches
        new_matches_count = self.session.execute(
            select(func.sum(SavedSearch.new_matches_count)).where(
                and_(
                    SavedSearch.visitor_id == visitor_id,
                    SavedSearch.is_deleted == False,
                    SavedSearch.is_active == True,
                )
            )
        ).scalar_one() or 0
        
        return {
            "visitor": {
                "id": str(visitor.id),
                "full_name": visitor.full_name,
                "email": visitor.email,
                "engagement_score": visitor.engagement_score,
                "last_active_at": visitor.last_active_at,
            },
            "favorites_count": favorites_count,
            "saved_searches_count": saved_searches_count,
            "total_alerts": price_alerts_count + availability_alerts_count,
            "price_drop_alerts": price_alerts_count,
            "availability_alerts": availability_alerts_count,
            "new_matches_count": new_matches_count,
            "activity_stats": {
                "total_searches": visitor.total_searches,
                "total_views": visitor.total_hostel_views,
                "total_inquiries": visitor.total_inquiries,
                "total_bookings": visitor.total_bookings,
            },
        }

    def get_visitor_activity_timeline(
        self,
        visitor_id: UUID,
        days: int = 30,
    ) -> List[Dict]:
        """
        Get visitor activity timeline.
        
        Args:
            visitor_id: Visitor ID
            days: Number of days to include
            
        Returns:
            List of daily activity summaries
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get daily engagement records
        engagement_query = (
            select(VisitorEngagement)
            .where(
                and_(
                    VisitorEngagement.visitor_id == visitor_id,
                    VisitorEngagement.engagement_date >= cutoff_date,
                )
            )
            .order_by(VisitorEngagement.engagement_date)
        )
        
        engagements = self.session.execute(engagement_query).scalars().all()
        
        timeline = []
        for engagement in engagements:
            timeline.append({
                "date": engagement.engagement_date,
                "page_views": engagement.page_views,
                "time_on_site_seconds": engagement.time_on_site_seconds,
                "searches_performed": engagement.searches_performed,
                "hostels_viewed": engagement.hostels_viewed,
                "favorites_added": engagement.favorites_added,
                "inquiries_sent": engagement.inquiries_sent,
                "engagement_score": engagement.engagement_score,
            })
        
        return timeline

    # ==================== Visitor Insights & Analytics ====================

    def get_visitor_preferences_analysis(
        self,
        visitor_id: UUID,
    ) -> Dict:
        """
        Analyze visitor preferences based on behavior.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Dictionary containing preference analysis
        """
        # Get recently viewed hostels
        viewed_query = (
            select(RecentlyViewedHostel)
            .where(
                and_(
                    RecentlyViewedHostel.visitor_id == visitor_id,
                    RecentlyViewedHostel.is_deleted == False,
                )
            )
            .order_by(desc(RecentlyViewedHostel.last_viewed_at))
            .limit(50)
        )
        viewed_hostels = list(self.session.execute(viewed_query).scalars().all())
        
        # Analyze city preferences
        city_views = {}
        for hostel in viewed_hostels:
            city_views[hostel.hostel_city] = city_views.get(hostel.hostel_city, 0) + 1
        
        # Analyze price preferences
        prices = [h.starting_price for h in viewed_hostels]
        avg_price = sum(prices) / len(prices) if prices else Decimal("0.00")
        min_price = min(prices) if prices else Decimal("0.00")
        max_price = max(prices) if prices else Decimal("0.00")
        
        # Get favorites for comparison
        favorites_query = (
            select(VisitorFavorite)
            .where(
                and_(
                    VisitorFavorite.visitor_id == visitor_id,
                    VisitorFavorite.is_deleted == False,
                )
            )
        )
        favorites = list(self.session.execute(favorites_query).scalars().all())
        
        favorite_cities = {}
        for fav in favorites:
            favorite_cities[fav.hostel_city] = favorite_cities.get(fav.hostel_city, 0) + 1
        
        return {
            "viewing_patterns": {
                "total_viewed": len(viewed_hostels),
                "cities_viewed": city_views,
                "price_range": {
                    "average": avg_price.quantize(Decimal("0.01")),
                    "min": min_price,
                    "max": max_price,
                },
            },
            "favorite_patterns": {
                "total_favorites": len(favorites),
                "favorite_cities": favorite_cities,
            },
            "preferred_cities": sorted(
                city_views.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3],
        }

    def get_visitor_engagement_trends(
        self,
        visitor_id: UUID,
        days: int = 90,
    ) -> Dict:
        """
        Analyze visitor engagement trends over time.
        
        Args:
            visitor_id: Visitor ID
            days: Number of days to analyze
            
        Returns:
            Dictionary containing trend analysis
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get engagement history
        engagement_query = (
            select(VisitorEngagement)
            .where(
                and_(
                    VisitorEngagement.visitor_id == visitor_id,
                    VisitorEngagement.engagement_date >= cutoff_date,
                )
            )
            .order_by(VisitorEngagement.engagement_date)
        )
        
        engagements = list(self.session.execute(engagement_query).scalars().all())
        
        if not engagements:
            return {
                "trend": "no_data",
                "average_score": Decimal("0.00"),
                "peak_engagement_date": None,
                "total_sessions": 0,
            }
        
        # Calculate trends
        scores = [e.engagement_score for e in engagements]
        avg_score = sum(scores) / len(scores)
        
        # Find peak engagement
        peak_engagement = max(engagements, key=lambda e: e.engagement_score)
        
        # Determine trend
        if len(engagements) > 7:
            recent_avg = sum(scores[-7:]) / 7
            older_avg = sum(scores[:7]) / 7
            
            if recent_avg > older_avg * Decimal("1.1"):
                trend = "increasing"
            elif recent_avg < older_avg * Decimal("0.9"):
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        # Get session count
        session_count = self.session.execute(
            select(func.count(VisitorSession.id)).where(
                and_(
                    VisitorSession.visitor_id == visitor_id,
                    VisitorSession.started_at >= cutoff_date,
                )
            )
        ).scalar_one()
        
        return {
            "trend": trend,
            "average_score": avg_score.quantize(Decimal("0.01")),
            "peak_engagement_date": peak_engagement.engagement_date,
            "peak_engagement_score": peak_engagement.engagement_score,
            "total_sessions": session_count,
            "days_analyzed": len(engagements),
        }

    def get_conversion_probability(
        self,
        visitor_id: UUID,
    ) -> Dict:
        """
        Calculate visitor's conversion probability based on behavior.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Dictionary containing conversion probability analysis
        """
        visitor_query = select(Visitor).where(Visitor.id == visitor_id)
        visitor = self.session.execute(visitor_query).scalar_one_or_none()
        
        if not visitor:
            raise ValueError(f"Visitor not found: {visitor_id}")
        
        # Calculate probability based on multiple factors
        score = Decimal("0.00")
        
        # Engagement score (0-30 points)
        score += min(visitor.engagement_score * Decimal("0.3"), Decimal("30"))
        
        # Inquiry activity (0-25 points)
        if visitor.total_inquiries > 0:
            score += min(Decimal(visitor.total_inquiries * 5), Decimal("25"))
        
        # Favorites (0-15 points)
        favorites_count = self.session.execute(
            select(func.count(VisitorFavorite.id)).where(
                and_(
                    VisitorFavorite.visitor_id == visitor_id,
                    VisitorFavorite.is_deleted == False,
                )
            )
        ).scalar_one()
        score += min(Decimal(favorites_count * 3), Decimal("15"))
        
        # Saved searches (0-15 points)
        searches_count = self.session.execute(
            select(func.count(SavedSearch.id)).where(
                and_(
                    SavedSearch.visitor_id == visitor_id,
                    SavedSearch.is_deleted == False,
                    SavedSearch.is_active == True,
                )
            )
        ).scalar_one()
        score += min(Decimal(searches_count * 5), Decimal("15"))
        
        # Recency (0-15 points)
        if visitor.last_active_at:
            days_since_active = (datetime.utcnow() - visitor.last_active_at).days
            if days_since_active == 0:
                score += Decimal("15")
            elif days_since_active <= 3:
                score += Decimal("10")
            elif days_since_active <= 7:
                score += Decimal("5")
        
        probability = min(score, Decimal("100.00"))
        
        # Determine category
        if probability >= Decimal("80"):
            category = "very_high"
        elif probability >= Decimal("60"):
            category = "high"
        elif probability >= Decimal("40"):
            category = "medium"
        elif probability >= Decimal("20"):
            category = "low"
        else:
            category = "very_low"
        
        return {
            "probability": probability,
            "category": category,
            "factors": {
                "engagement_score": visitor.engagement_score,
                "total_inquiries": visitor.total_inquiries,
                "favorites_count": favorites_count,
                "saved_searches_count": searches_count,
                "days_since_active": (
                    (datetime.utcnow() - visitor.last_active_at).days
                    if visitor.last_active_at else None
                ),
            },
        }

    # ==================== Bulk Analytics ====================

    def get_platform_visitor_metrics(
        self,
        days: int = 30,
    ) -> Dict:
        """
        Get platform-wide visitor metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary containing platform metrics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total active visitors
        active_visitors = self.session.execute(
            select(func.count(Visitor.id)).where(
                and_(
                    Visitor.is_deleted == False,
                    Visitor.last_active_at >= cutoff_date,
                )
            )
        ).scalar_one()
        
        # Average engagement score
        avg_engagement = self.session.execute(
            select(func.avg(Visitor.engagement_score)).where(
                and_(
                    Visitor.is_deleted == False,
                    Visitor.last_active_at >= cutoff_date,
                )
            )
        ).scalar_one() or Decimal("0.00")
        
        # Total searches
        total_searches = self.session.execute(
            select(func.sum(VisitorEngagement.searches_performed)).where(
                VisitorEngagement.engagement_date >= cutoff_date
            )
        ).scalar_one() or 0
        
        # Total bookings
        total_bookings = self.session.execute(
            select(func.count(Visitor.id)).where(
                and_(
                    Visitor.is_deleted == False,
                    Visitor.last_booking_at >= cutoff_date,
                )
            )
        ).scalar_one()
        
        # Conversion rate
        conversion_rate = Decimal("0.00")
        if active_visitors > 0:
            conversion_rate = (
                Decimal(total_bookings) / Decimal(active_visitors) * 100
            ).quantize(Decimal("0.01"))
        
        return {
            "active_visitors": active_visitors,
            "average_engagement_score": avg_engagement.quantize(Decimal("0.01")),
            "total_searches": total_searches,
            "total_bookings": total_bookings,
            "conversion_rate": conversion_rate,
            "period_days": days,
        }