# app/services/analytics/visitor_analytics_service.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.analytics import VisitorBehaviorAnalyticsRepository
from app.repositories.visitor import VisitorRepository
from app.schemas.visitor import VisitorStats
from app.services.common import UnitOfWork, errors


class VisitorAnalyticsService:
    """
    Visitor analytics service.
    
    Provides analytics and statistics for visitor behavior,
    search patterns, and conversion metrics.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_visitor_repo(self, uow: UnitOfWork) -> VisitorRepository:
        return uow.get_repo(VisitorRepository)

    def _get_analytics_repo(self, uow: UnitOfWork) -> VisitorBehaviorAnalyticsRepository:
        return uow.get_repo(VisitorBehaviorAnalyticsRepository)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_visitor_stats(self, visitor_id: UUID) -> VisitorStats:
        """
        Get comprehensive statistics for a visitor.
        
        Args:
            visitor_id: Visitor UUID
            
        Returns:
            VisitorStats schema with all analytics data
        """
        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)
            analytics_repo = self._get_analytics_repo(uow)

            # Get visitor
            visitor = visitor_repo.get(visitor_id)
            if visitor is None:
                raise errors.NotFoundError(f"Visitor {visitor_id} not found")

            # Get analytics data
            analytics = analytics_repo.get_by_visitor_id(visitor_id)

            if analytics is None:
                # Return empty stats if no analytics data exists
                return VisitorStats(
                    visitor_id=visitor_id,
                    total_searches=0,
                    unique_hostels_viewed=0,
                    average_search_filters_used=Decimal("0"),
                    total_hostel_views=0,
                    total_comparisons=0,
                    total_inquiries=0,
                    total_bookings=0,
                    booking_conversion_rate=Decimal("0"),
                    most_searched_city=None,
                    most_viewed_room_type=None,
                    average_budget=None,
                )

            # Calculate conversion rate
            conversion_rate = Decimal("0")
            if analytics.hostels_viewed > 0:
                conversion_rate = (
                    Decimal(str(analytics.bookings_made)) 
                    / Decimal(str(analytics.hostels_viewed)) 
                    * Decimal("100")
                ).quantize(Decimal("0.01"))

            # Calculate average search filters
            avg_filters = Decimal("0")
            if analytics.total_searches > 0:
                # This would need to be tracked separately in real implementation
                # For now, returning a placeholder
                avg_filters = Decimal("2.5")

            # Get most searched city
            most_searched_city = None
            if analytics.most_searched_locations:
                most_searched_city = analytics.most_searched_locations[0]

            # Parse preferred price range for average budget
            average_budget = None
            if analytics.preferred_price_range:
                try:
                    # Parse range like "5000-10000"
                    if "-" in analytics.preferred_price_range:
                        min_price, max_price = analytics.preferred_price_range.split("-")
                        average_budget = (
                            Decimal(min_price.strip()) + Decimal(max_price.strip())
                        ) / Decimal("2")
                except (ValueError, AttributeError):
                    pass

            return VisitorStats(
                visitor_id=visitor_id,
                total_searches=analytics.total_searches,
                unique_hostels_viewed=analytics.hostels_viewed,
                average_search_filters_used=avg_filters,
                total_hostel_views=analytics.total_page_views,
                total_comparisons=analytics.comparisons_made,
                total_inquiries=analytics.inquiries_sent,
                total_bookings=analytics.bookings_made,
                booking_conversion_rate=conversion_rate,
                most_searched_city=most_searched_city,
                most_viewed_room_type=None,  # Would need additional tracking
                average_budget=average_budget,
            )

    def get_visitor_stats_by_user_id(self, user_id: UUID) -> VisitorStats:
        """
        Get visitor statistics by user ID.
        
        Args:
            user_id: User UUID
            
        Returns:
            VisitorStats schema
        """
        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)

            # Get visitor by user_id
            visitor = visitor_repo.get_by_user_id(user_id)
            if visitor is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

        return self.get_visitor_stats(visitor.id)