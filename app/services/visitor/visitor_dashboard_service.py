"""
Visitor Dashboard Service

Builds comprehensive visitor dashboard views by aggregating data from multiple sources.
Provides a unified interface for visitor-facing dashboards.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.visitor import VisitorAggregateRepository
from app.schemas.visitor import VisitorDashboard
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    ServiceException,
)
from app.core1.caching import cache_result

logger = logging.getLogger(__name__)


class VisitorDashboardService:
    """
    Aggregate service for visitor dashboards.

    Responsibilities:
    - Aggregate data from multiple repositories (read model)
    - Build comprehensive dashboard views
    - Provide cached dashboard data for performance
    - Support dashboard customization based on visitor preferences

    Dashboard components:
    - Saved/favorite hostels
    - Booking history and upcoming bookings
    - Recent searches and viewed hostels
    - Personalized recommendations
    - Price alerts and availability notifications
    - Engagement metrics and rewards
    """

    # Cache TTL for dashboard data (in seconds)
    CACHE_TTL = 300  # 5 minutes

    def __init__(
        self,
        aggregate_repo: VisitorAggregateRepository,
    ) -> None:
        """
        Initialize the dashboard service.

        Args:
            aggregate_repo: Repository for aggregated visitor data
        """
        self.aggregate_repo = aggregate_repo

    @cache_result(ttl=CACHE_TTL)
    def get_dashboard(
        self,
        db: Session,
        visitor_id: UUID,
        include_recommendations: bool = True,
        include_history: bool = True,
        days_back: int = 30,
    ) -> VisitorDashboard:
        """
        Build the comprehensive dashboard for a specific visitor.

        This method aggregates data from multiple sources:
        - Saved hostels and favorites
        - Booking history (past and upcoming)
        - Recent searches and views
        - Personalized recommendations
        - Active alerts and notifications

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            include_recommendations: Whether to include hostel recommendations
            include_history: Whether to include historical activity
            days_back: Number of days of history to include

        Returns:
            VisitorDashboard: Complete dashboard data

        Raises:
            NotFoundException: If visitor not found
            ServiceException: If dashboard building fails
        """
        try:
            # Fetch aggregated dashboard data
            data = self.aggregate_repo.get_dashboard_data(
                db,
                visitor_id,
                include_recommendations=include_recommendations,
                include_history=include_history,
                days_back=days_back,
            )

            if not data:
                raise NotFoundException(
                    f"Visitor {visitor_id} not found or no dashboard data available"
                )

            # Enrich data with computed metrics
            enriched_data = self._enrich_dashboard_data(data)

            # Validate and construct dashboard schema
            dashboard = VisitorDashboard.model_validate(enriched_data)

            logger.info(f"Built dashboard for visitor {visitor_id}")
            return dashboard

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to build dashboard for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to build dashboard: {str(e)}")

    def get_dashboard_summary(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get a lightweight summary of the dashboard.

        Useful for quick overview without full data load.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            Dictionary with summary metrics

        Raises:
            NotFoundException: If visitor not found
        """
        try:
            summary = self.aggregate_repo.get_dashboard_summary(db, visitor_id)
            if not summary:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            return {
                "visitor_id": str(visitor_id),
                "total_favorites": summary.get("total_favorites", 0),
                "total_bookings": summary.get("total_bookings", 0),
                "upcoming_bookings": summary.get("upcoming_bookings", 0),
                "active_alerts": summary.get("active_alerts", 0),
                "unread_notifications": summary.get("unread_notifications", 0),
                "engagement_score": summary.get("engagement_score", 0),
                "last_activity": summary.get("last_activity"),
            }

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get dashboard summary for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to get dashboard summary: {str(e)}")

    def get_activity_timeline(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get recent activity timeline for the visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            limit: Maximum number of activities to return
            offset: Pagination offset

        Returns:
            List of activity events in chronological order

        Raises:
            NotFoundException: If visitor not found
        """
        try:
            activities = self.aggregate_repo.get_activity_timeline(
                db,
                visitor_id,
                limit=limit,
                offset=offset,
            )

            if activities is None:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            return [
                {
                    "id": str(activity.get("id")),
                    "type": activity.get("type"),
                    "description": activity.get("description"),
                    "timestamp": activity.get("timestamp"),
                    "metadata": activity.get("metadata", {}),
                }
                for activity in activities
            ]

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get activity timeline for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to get activity timeline: {str(e)}")

    def get_quick_actions(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get personalized quick actions for the visitor.

        Quick actions are contextual based on visitor state and activity.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            List of recommended quick actions
        """
        try:
            # Get visitor state
            summary = self.aggregate_repo.get_dashboard_summary(db, visitor_id)
            if not summary:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            quick_actions = []

            # Action: Complete profile if incomplete
            if not summary.get("profile_complete", False):
                quick_actions.append({
                    "type": "complete_profile",
                    "title": "Complete Your Profile",
                    "description": "Get better recommendations",
                    "priority": "high",
                })

            # Action: View favorites if any exist
            if summary.get("total_favorites", 0) > 0:
                quick_actions.append({
                    "type": "view_favorites",
                    "title": "View Saved Hostels",
                    "description": f"{summary['total_favorites']} hostels saved",
                    "priority": "medium",
                })

            # Action: Upcoming booking check-in
            if summary.get("upcoming_bookings", 0) > 0:
                quick_actions.append({
                    "type": "upcoming_booking",
                    "title": "Upcoming Check-in",
                    "description": "View booking details",
                    "priority": "high",
                })

            # Action: Search for hostels if no recent activity
            last_activity = summary.get("last_activity")
            if last_activity:
                days_since_activity = (datetime.utcnow() - last_activity).days
                if days_since_activity > 7:
                    quick_actions.append({
                        "type": "search_hostels",
                        "title": "Explore Hostels",
                        "description": "Discover new places",
                        "priority": "medium",
                    })

            return quick_actions

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get quick actions for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to get quick actions: {str(e)}")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _enrich_dashboard_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich raw dashboard data with computed metrics and formatting.

        Args:
            data: Raw dashboard data from repository

        Returns:
            Enriched dashboard data
        """
        enriched = data.copy()

        # Add computed engagement level
        engagement_score = data.get("engagement_score", 0)
        enriched["engagement_level"] = self._compute_engagement_level(engagement_score)

        # Add trend indicators
        enriched["trends"] = self._compute_trends(data)

        # Format dates consistently
        enriched["last_updated"] = datetime.utcnow()

        # Add personalization flags
        enriched["personalization"] = {
            "has_preferences": bool(data.get("preferences")),
            "has_favorites": data.get("total_favorites", 0) > 0,
            "has_searches": data.get("total_searches", 0) > 0,
        }

        return enriched

    def _compute_engagement_level(self, score: int) -> str:
        """
        Compute engagement level from score.

        Args:
            score: Engagement score

        Returns:
            Engagement level string
        """
        if score >= 80:
            return "very_high"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        elif score >= 20:
            return "low"
        else:
            return "very_low"

    def _compute_trends(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Compute trend indicators for dashboard metrics.

        Args:
            data: Dashboard data

        Returns:
            Dictionary of trend indicators
        """
        trends = {}

        # Booking trend
        current_bookings = data.get("total_bookings", 0)
        previous_bookings = data.get("previous_period_bookings", 0)
        trends["bookings"] = self._get_trend_direction(current_bookings, previous_bookings)

        # Search trend
        current_searches = data.get("total_searches", 0)
        previous_searches = data.get("previous_period_searches", 0)
        trends["searches"] = self._get_trend_direction(current_searches, previous_searches)

        # Engagement trend
        current_engagement = data.get("engagement_score", 0)
        previous_engagement = data.get("previous_engagement_score", 0)
        trends["engagement"] = self._get_trend_direction(current_engagement, previous_engagement)

        return trends

    def _get_trend_direction(self, current: int, previous: int) -> str:
        """
        Determine trend direction.

        Args:
            current: Current value
            previous: Previous value

        Returns:
            Trend direction: 'up', 'down', or 'stable'
        """
        if previous == 0:
            return "stable"

        change_percent = ((current - previous) / previous) * 100

        if change_percent > 5:
            return "up"
        elif change_percent < -5:
            return "down"
        else:
            return "stable"