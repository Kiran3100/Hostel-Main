"""
Visitor Tracking Service

Tracks visitor behavior and interactions for analytics and personalization.
Provides comprehensive activity tracking across the visitor journey.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorRepository,
    VisitorSessionRepository,
    VisitorEngagementRepository,
    VisitorActivityRepository,
    RecentSearchRepository,
    RecentlyViewedHostelRepository,
)
from app.schemas.search import BasicSearchRequest
from app.core1.exceptions import (
    ValidationException,
    ServiceException,
)

logger = logging.getLogger(__name__)


class VisitorTrackingService:
    """
    Records behavioral signals to build engagement profiles and enable personalization.

    Tracking categories:
    1. Search events (queries, filters, results)
    2. Hostel view events (detail pages, sections, duration)
    3. Interaction events (clicks, scrolls, form submissions)
    4. Conversion events (inquiries, bookings, registrations)
    5. Session events (logins, page views, time on site)

    All tracking is privacy-aware and GDPR-compliant.
    """

    # Session timeout in minutes
    SESSION_TIMEOUT_MINUTES = 30

    # Maximum recent items to store
    MAX_RECENT_SEARCHES = 50
    MAX_RECENT_VIEWS = 100

    def __init__(
        self,
        visitor_repo: VisitorRepository,
        session_repo: VisitorSessionRepository,
        engagement_repo: VisitorEngagementRepository,
        activity_repo: VisitorActivityRepository,
        recent_search_repo: RecentSearchRepository,
        recently_viewed_repo: RecentlyViewedHostelRepository,
    ) -> None:
        """
        Initialize the tracking service.

        Args:
            visitor_repo: Repository for visitor operations
            session_repo: Repository for session tracking
            engagement_repo: Repository for engagement metrics
            activity_repo: Repository for activity logging
            recent_search_repo: Repository for recent searches
            recently_viewed_repo: Repository for recently viewed hostels
        """
        self.visitor_repo = visitor_repo
        self.session_repo = session_repo
        self.engagement_repo = engagement_repo
        self.activity_repo = activity_repo
        self.recent_search_repo = recent_search_repo
        self.recently_viewed_repo = recently_viewed_repo

    # -------------------------------------------------------------------------
    # Search Tracking
    # -------------------------------------------------------------------------

    def track_search(
        self,
        db: Session,
        visitor_id: Optional[UUID],
        request: BasicSearchRequest,
        results_count: int,
        execution_time_ms: int,
        session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Track a search event with comprehensive metadata.

        Args:
            db: Database session
            visitor_id: UUID of the visitor (None for anonymous)
            request: Search request details
            results_count: Number of results returned
            execution_time_ms: Search execution time in milliseconds
            session_id: Optional session identifier
            user_agent: Optional user agent string
            ip_address: Optional IP address

        Raises:
            ValidationException: If search data is invalid
            ServiceException: If tracking fails
        """
        try:
            # Validate inputs
            if results_count < 0:
                raise ValidationException("results_count cannot be negative")

            if execution_time_ms < 0:
                raise ValidationException("execution_time_ms cannot be negative")

            # Prepare search filters
            filters = request.model_dump(exclude_none=True)

            # Log the search
            search_data = {
                "visitor_id": visitor_id,
                "query": request.query or "",
                "filters": filters,
                "results_count": results_count,
                "execution_time_ms": execution_time_ms,
                "session_id": session_id,
                "user_agent": user_agent,
                "ip_address": ip_address,
                "searched_at": datetime.utcnow(),
            }

            self.recent_search_repo.log_search(db=db, **search_data)

            # Update engagement metrics for registered visitors
            if visitor_id:
                self.engagement_repo.increment_searches(
                    db=db,
                    visitor_id=visitor_id,
                )

                # Update last activity
                self._update_last_activity(db, visitor_id)

            logger.info(
                f"Tracked search for visitor {visitor_id or 'anonymous'}: "
                f"query='{request.query}', results={results_count}"
            )

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to track search for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            # Don't raise - tracking failures shouldn't break the search
            logger.warning("Search tracking failed, continuing")

    def get_recent_searches(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get recent searches for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            limit: Maximum number of searches to return

        Returns:
            List of recent searches with metadata

        Raises:
            ValidationException: If limit is invalid
        """
        try:
            if limit < 1 or limit > self.MAX_RECENT_SEARCHES:
                raise ValidationException(
                    f"limit must be between 1 and {self.MAX_RECENT_SEARCHES}"
                )

            searches = self.recent_search_repo.get_recent_by_visitor(
                db,
                visitor_id,
                limit=limit
            )

            return [
                {
                    "id": str(search.id),
                    "query": search.query,
                    "filters": search.filters,
                    "results_count": search.results_count,
                    "searched_at": search.searched_at,
                }
                for search in searches
            ]

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get recent searches for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve recent searches: {str(e)}")

    def clear_recent_searches(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> None:
        """
        Clear recent search history for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Raises:
            ServiceException: If clearing fails
        """
        try:
            self.recent_search_repo.clear_for_visitor(db, visitor_id)
            logger.info(f"Cleared recent searches for visitor {visitor_id}")

        except Exception as e:
            logger.error(
                f"Failed to clear searches for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to clear recent searches: {str(e)}")

    # -------------------------------------------------------------------------
    # View Tracking
    # -------------------------------------------------------------------------

    def track_hostel_view(
        self,
        db: Session,
        visitor_id: Optional[UUID],
        hostel_id: UUID,
        sections_viewed: Optional[List[str]] = None,
        duration_seconds: Optional[int] = None,
        referrer: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Track that a visitor viewed a hostel detail page.

        Args:
            db: Database session
            visitor_id: UUID of the visitor (None for anonymous)
            hostel_id: UUID of the hostel viewed
            sections_viewed: List of page sections viewed (e.g., ['photos', 'reviews'])
            duration_seconds: Time spent viewing (seconds)
            referrer: Referrer URL or source
            session_id: Optional session identifier

        Raises:
            ValidationException: If view data is invalid
            ServiceException: If tracking fails
        """
        try:
            # Validate inputs
            if duration_seconds is not None and duration_seconds < 0:
                raise ValidationException("duration_seconds cannot be negative")

            # Track the view
            view_data = {
                "visitor_id": visitor_id,
                "hostel_id": hostel_id,
                "sections_viewed": sections_viewed or [],
                "duration_seconds": duration_seconds or 0,
                "referrer": referrer,
                "session_id": session_id,
                "viewed_at": datetime.utcnow(),
            }

            self.recently_viewed_repo.track_view(db=db, **view_data)

            # Update engagement metrics for registered visitors
            if visitor_id:
                self.engagement_repo.increment_hostel_views(
                    db=db,
                    visitor_id=visitor_id,
                )

                # Update last activity
                self._update_last_activity(db, visitor_id)

            logger.info(
                f"Tracked hostel view for visitor {visitor_id or 'anonymous'}: "
                f"hostel={hostel_id}, duration={duration_seconds}s"
            )

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to track hostel view for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            # Don't raise - tracking failures shouldn't break the view
            logger.warning("Hostel view tracking failed, continuing")

    def get_recently_viewed(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = 10,
        exclude_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recently viewed hostels for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            limit: Maximum number of hostels to return
            exclude_ids: Optional list of hostel IDs to exclude

        Returns:
            List of recently viewed hostels with metadata

        Raises:
            ValidationException: If limit is invalid
        """
        try:
            if limit < 1 or limit > self.MAX_RECENT_VIEWS:
                raise ValidationException(
                    f"limit must be between 1 and {self.MAX_RECENT_VIEWS}"
                )

            views = self.recently_viewed_repo.get_recent_by_visitor(
                db,
                visitor_id,
                limit=limit,
                exclude_ids=exclude_ids or []
            )

            return [
                {
                    "hostel_id": str(view.hostel_id),
                    "viewed_at": view.viewed_at,
                    "duration_seconds": view.duration_seconds,
                    "sections_viewed": view.sections_viewed,
                    "view_count": view.view_count,
                }
                for view in views
            ]

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get recently viewed for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve recently viewed: {str(e)}")

    def clear_recently_viewed(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> None:
        """
        Clear recently viewed history for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Raises:
            ServiceException: If clearing fails
        """
        try:
            self.recently_viewed_repo.clear_for_visitor(db, visitor_id)
            logger.info(f"Cleared recently viewed for visitor {visitor_id}")

        except Exception as e:
            logger.error(
                f"Failed to clear recently viewed for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to clear recently viewed: {str(e)}")

    # -------------------------------------------------------------------------
    # Conversion Tracking
    # -------------------------------------------------------------------------

    def track_inquiry(
        self,
        db: Session,
        visitor_id: UUID,
        inquiry_id: UUID,
        hostel_id: UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track that a visitor created an inquiry.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            inquiry_id: UUID of the inquiry
            hostel_id: UUID of the hostel inquired about
            metadata: Optional additional metadata

        Raises:
            ServiceException: If tracking fails
        """
        try:
            # Log activity
            self.activity_repo.log_activity(
                db=db,
                visitor_id=visitor_id,
                activity_type="inquiry",
                entity_id=inquiry_id,
                metadata={
                    **(metadata or {}),
                    "hostel_id": str(hostel_id),
                },
            )

            # Update engagement
            self.engagement_repo.increment_inquiries(
                db=db,
                visitor_id=visitor_id,
            )

            # Update last activity
            self._update_last_activity(db, visitor_id)

            logger.info(
                f"Tracked inquiry for visitor {visitor_id}: "
                f"inquiry={inquiry_id}, hostel={hostel_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to track inquiry for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            # Don't raise - tracking failures shouldn't break the inquiry
            logger.warning("Inquiry tracking failed, continuing")

    def track_booking(
        self,
        db: Session,
        visitor_id: UUID,
        booking_id: UUID,
        hostel_id: UUID,
        amount: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track that a visitor completed a booking.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            booking_id: UUID of the booking
            hostel_id: UUID of the hostel booked
            amount: Optional booking amount
            metadata: Optional additional metadata

        Raises:
            ServiceException: If tracking fails
        """
        try:
            # Log activity
            activity_metadata = {
                **(metadata or {}),
                "hostel_id": str(hostel_id),
            }
            if amount is not None:
                activity_metadata["amount"] = amount

            self.activity_repo.log_activity(
                db=db,
                visitor_id=visitor_id,
                activity_type="booking",
                entity_id=booking_id,
                metadata=activity_metadata,
            )

            # Update engagement
            self.engagement_repo.increment_bookings(
                db=db,
                visitor_id=visitor_id,
            )

            # Update last activity
            self._update_last_activity(db, visitor_id)

            logger.info(
                f"Tracked booking for visitor {visitor_id}: "
                f"booking={booking_id}, hostel={hostel_id}, amount={amount}"
            )

        except Exception as e:
            logger.error(
                f"Failed to track booking for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            # Don't raise - tracking failures shouldn't break the booking
            logger.warning("Booking tracking failed, continuing")

    # -------------------------------------------------------------------------
    # Generic Activity Tracking
    # -------------------------------------------------------------------------

    def track_activity(
        self,
        db: Session,
        visitor_id: UUID,
        activity_type: str,
        entity_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Generic visitor activity logging.

        Supports tracking custom activities like:
        - CTA clicks
        - Newsletter signups
        - Review submissions
        - Social shares
        - etc.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            activity_type: Type of activity (e.g., 'cta_click', 'newsletter_signup')
            entity_id: Optional related entity ID
            metadata: Optional activity metadata

        Raises:
            ValidationException: If activity_type is invalid
            ServiceException: If tracking fails
        """
        try:
            # Validate activity type
            if not activity_type or not activity_type.strip():
                raise ValidationException("activity_type is required")

            if len(activity_type) > 50:
                raise ValidationException("activity_type too long (max 50 characters)")

            # Log the activity
            self.activity_repo.log_activity(
                db=db,
                visitor_id=visitor_id,
                activity_type=activity_type.strip().lower(),
                entity_id=entity_id,
                metadata=metadata or {},
            )

            # Increment generic engagement
            self.engagement_repo.increment_generic_activity(
                db=db,
                visitor_id=visitor_id,
            )

            # Update last activity
            self._update_last_activity(db, visitor_id)

            logger.info(
                f"Tracked activity for visitor {visitor_id}: "
                f"type={activity_type}, entity={entity_id}"
            )

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to track activity for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            # Don't raise - tracking failures shouldn't break the action
            logger.warning("Activity tracking failed, continuing")

    def get_activity_history(
        self,
        db: Session,
        visitor_id: UUID,
        activity_types: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get activity history for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            activity_types: Optional filter by activity types
            limit: Maximum number of activities to return
            offset: Pagination offset

        Returns:
            List of activities with metadata

        Raises:
            ValidationException: If parameters are invalid
        """
        try:
            if limit < 1 or limit > 500:
                raise ValidationException("limit must be between 1 and 500")

            if offset < 0:
                raise ValidationException("offset must be >= 0")

            activities = self.activity_repo.get_by_visitor_id(
                db,
                visitor_id,
                activity_types=activity_types,
                limit=limit,
                offset=offset,
            )

            return [
                {
                    "id": str(activity.id),
                    "activity_type": activity.activity_type,
                    "entity_id": str(activity.entity_id) if activity.entity_id else None,
                    "metadata": activity.metadata,
                    "created_at": activity.created_at,
                }
                for activity in activities
            ]

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get activity history for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve activity history: {str(e)}")

    # -------------------------------------------------------------------------
    # Session Tracking
    # -------------------------------------------------------------------------

    def start_session(
        self,
        db: Session,
        visitor_id: Optional[UUID],
        session_id: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> None:
        """
        Start a new visitor session.

        Args:
            db: Database session
            visitor_id: UUID of the visitor (None for anonymous)
            session_id: Unique session identifier
            user_agent: User agent string
            ip_address: IP address
            referrer: Referrer URL

        Raises:
            ServiceException: If session creation fails
        """
        try:
            session_data = {
                "visitor_id": visitor_id,
                "session_id": session_id,
                "user_agent": user_agent,
                "ip_address": ip_address,
                "referrer": referrer,
                "started_at": datetime.utcnow(),
                "last_activity_at": datetime.utcnow(),
            }

            self.session_repo.create_session(db=db, **session_data)

            logger.info(
                f"Started session {session_id} for visitor {visitor_id or 'anonymous'}"
            )

        except Exception as e:
            logger.error(
                f"Failed to start session {session_id}: {str(e)}",
                exc_info=True
            )
            # Don't raise - session tracking failures shouldn't break the app
            logger.warning("Session start tracking failed, continuing")

    def end_session(
        self,
        db: Session,
        session_id: str,
    ) -> None:
        """
        End a visitor session.

        Args:
            db: Database session
            session_id: Session identifier

        Raises:
            ServiceException: If session end fails
        """
        try:
            self.session_repo.end_session(
                db=db,
                session_id=session_id,
                ended_at=datetime.utcnow()
            )

            logger.info(f"Ended session {session_id}")

        except Exception as e:
            logger.error(
                f"Failed to end session {session_id}: {str(e)}",
                exc_info=True
            )
            # Don't raise
            logger.warning("Session end tracking failed, continuing")

    def update_session_activity(
        self,
        db: Session,
        session_id: str,
    ) -> None:
        """
        Update last activity time for a session.

        Args:
            db: Database session
            session_id: Session identifier
        """
        try:
            self.session_repo.update_activity(
                db=db,
                session_id=session_id,
                activity_time=datetime.utcnow()
            )

        except Exception as e:
            logger.error(
                f"Failed to update session activity {session_id}: {str(e)}"
            )
            # Don't raise or log warning - this is frequent and low-priority

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _update_last_activity(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> None:
        """
        Update last activity timestamp for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
        """
        try:
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if visitor:
                self.visitor_repo.update(
                    db,
                    obj=visitor,
                    data={"last_activity_at": datetime.utcnow()}
                )
        except Exception as e:
            logger.error(
                f"Failed to update last activity for visitor {visitor_id}: {str(e)}"
            )
            # Don't raise - this is non-critical