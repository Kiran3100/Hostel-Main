"""
Visitor Tracking Service

Tracks visitor behavior: searches, views, inquiries, bookings, conversions.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

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
from app.core.exceptions import ValidationException


class VisitorTrackingService:
    """
    Records behavior signals to build engagement and personalization:

    - Search events
    - Hostel view events
    - Booking events
    - Generic activity events (CTA clicks, etc.)
    """

    def __init__(
        self,
        visitor_repo: VisitorRepository,
        session_repo: VisitorSessionRepository,
        engagement_repo: VisitorEngagementRepository,
        activity_repo: VisitorActivityRepository,
        recent_search_repo: RecentSearchRepository,
        recently_viewed_repo: RecentlyViewedHostelRepository,
    ) -> None:
        self.visitor_repo = visitor_repo
        self.session_repo = session_repo
        self.engagement_repo = engagement_repo
        self.activity_repo = activity_repo
        self.recent_search_repo = recent_search_repo
        self.recently_viewed_repo = recently_viewed_repo

    # -------------------------------------------------------------------------
    # Search tracking
    # -------------------------------------------------------------------------

    def track_search(
        self,
        db: Session,
        visitor_id: Optional[UUID],
        request: BasicSearchRequest,
        results_count: int,
        execution_time_ms: int,
    ) -> None:
        """
        Track a search event. visitor_id may be None for anonymous visitors.
        """
        self.recent_search_repo.log_search(
            db=db,
            visitor_id=visitor_id,
            query=request.query,
            filters=request.model_dump(exclude_none=True),
            results_count=results_count,
            execution_time_ms=execution_time_ms,
        )

        if visitor_id:
            self.engagement_repo.increment_searches(
                db=db,
                visitor_id=visitor_id,
            )

    # -------------------------------------------------------------------------
    # View tracking
    # -------------------------------------------------------------------------

    def track_hostel_view(
        self,
        db: Session,
        visitor_id: Optional[UUID],
        hostel_id: UUID,
        sections_viewed: Optional[List[str]] = None,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """
        Track that a visitor viewed a hostel.
        """
        self.recently_viewed_repo.track_view(
            db=db,
            visitor_id=visitor_id,
            hostel_id=hostel_id,
            sections_viewed=sections_viewed or [],
            duration_seconds=duration_seconds or 0,
        )

        if visitor_id:
            self.engagement_repo.increment_hostel_views(
                db=db,
                visitor_id=visitor_id,
            )

    # -------------------------------------------------------------------------
    # Booking/inquiry tracking
    # -------------------------------------------------------------------------

    def track_inquiry(
        self,
        db: Session,
        visitor_id: UUID,
        inquiry_id: UUID,
    ) -> None:
        """
        Track that a visitor created an inquiry.
        """
        self.activity_repo.log_activity(
            db=db,
            visitor_id=visitor_id,
            activity_type="inquiry",
            entity_id=inquiry_id,
        )
        self.engagement_repo.increment_inquiries(
            db=db,
            visitor_id=visitor_id,
        )

    def track_booking(
        self,
        db: Session,
        visitor_id: UUID,
        booking_id: UUID,
    ) -> None:
        """
        Track that a visitor completed a booking.
        """
        self.activity_repo.log_activity(
            db=db,
            visitor_id=visitor_id,
            activity_type="booking",
            entity_id=booking_id,
        )
        self.engagement_repo.increment_bookings(
            db=db,
            visitor_id=visitor_id,
        )

    # -------------------------------------------------------------------------
    # Generic activity
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
        """
        self.activity_repo.log_activity(
            db=db,
            visitor_id=visitor_id,
            activity_type=activity_type,
            entity_id=entity_id,
            metadata=metadata or {},
        )

        # Simple engagement bump
        self.engagement_repo.increment_generic_activity(
            db=db,
            visitor_id=visitor_id,
        )