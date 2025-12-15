# app/services/visitor/visitor_dashboard_service.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorRepository,
    HostelBookingRepository,
)
from app.repositories.core import HostelRepository, UserRepository
from app.schemas.visitor.visitor_dashboard import (
    VisitorDashboard,
    SavedHostels,
    SavedHostelItem,
    BookingHistory,
    BookingHistoryItem,
    RecentSearch,
    RecentlyViewedHostel,
    RecommendedHostel,
    PriceDropAlert,
    AvailabilityAlert,
)
from app.services.common import UnitOfWork, errors


class VisitorDashboardService:
    """
    Visitor dashboard aggregation:

    - Saved hostels summary (from Visitor.favorite_hostel_ids + core_hostel).
    - Booking history from visitor_hostel_booking.
    - Simple behavior stats via VisitorBehaviorAnalytics.
    - Placeholders for searches, recommendations, and alerts.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_visitor_repo(self, uow: UnitOfWork) -> VisitorRepository:
        return uow.get_repo(VisitorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_booking_repo(self, uow: UnitOfWork) -> HostelBookingRepository:
        return uow.get_repo(HostelBookingRepository)

    # REMOVED: _get_behavior_repo method since the repository doesn't exist yet

    def _today(self) -> date:
        return date.today()

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_dashboard(self, user_id: UUID) -> VisitorDashboard:
        now = self._now()

        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            booking_repo = self._get_booking_repo(uow)
            # REMOVED: behavior_repo assignment

            user = user_repo.get(user_id)
            if user is None:
                raise errors.NotFoundError(f"User {user_id} not found")

            v = visitor_repo.get_by_user_id(user_id)
            if v is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

            # Saved hostels
            saved_ids = v.favorite_hostel_ids or []
            hostels = []
            for hid in saved_ids:
                h = hostel_repo.get(hid)
                if h:
                    hostels.append(h)

            saved_items: List[SavedHostelItem] = []
            for h in hostels:
                starting_price = h.starting_price_monthly or Decimal("0")
                avg_rating = Decimal(str(h.average_rating or 0.0))
                available_beds = max(0, (h.total_beds or 0) - (h.occupied_beds or 0))
                saved_items.append(
                    SavedHostelItem(
                        hostel_id=h.id,
                        hostel_name=h.name,
                        hostel_city=h.city,
                        starting_price=starting_price,
                        average_rating=avg_rating,
                        available_beds=available_beds,
                        cover_image_url=h.cover_image_url,
                        saved_at=now,
                        notes=None,
                        price_when_saved=starting_price,
                        current_price=starting_price,
                        price_changed=False,
                        price_change_percentage=None,
                    )
                )

            saved_hostels = SavedHostels(
                total_saved=len(saved_items),
                hostels=saved_items,
            )

            # Booking history
            bookings = booking_repo.list_for_visitor(v.id)
            bh_items: List[BookingHistoryItem] = []
            active = completed = cancelled = 0
            for b in sorted(bookings, key=lambda x: x.created_at, reverse=True):
                status_str = b.booking_status or ""
                status_lower = status_str.lower()
                if status_lower in {"pending", "confirmed", "checked_in"}:
                    active += 1
                elif status_lower in {"completed", "checked_out"}:
                    completed += 1
                elif status_lower == "cancelled":
                    cancelled += 1

                # naive duration parsing: expecting strings like "3 months"
                duration_months = 0
                if b.duration:
                    parts = b.duration.split()
                    if parts and parts[0].isdigit():
                        duration_months = int(parts[0])

                bh_items.append(
                    BookingHistoryItem(
                        booking_id=b.id,
                        booking_reference=str(b.id),
                        hostel_id=b.hostel_id,
                        hostel_name="",  # could be filled via HostelRepository if desired
                        room_type=b.room_type,
                        booking_date=b.created_at,
                        check_in_date=b.check_in_date,
                        duration_months=duration_months,
                        status=status_str,
                        total_amount=b.total_amount,
                        can_cancel=status_lower in {"pending", "confirmed"},
                        can_modify=status_lower in {"pending", "confirmed"},
                        can_review=status_lower in {"completed", "checked_out"},
                    )
                )

            booking_history = BookingHistory(
                total_bookings=len(bookings),
                active_bookings=active,
                completed_bookings=completed,
                cancelled_bookings=cancelled,
                bookings=bh_items,
            )

            # Behavior analytics - Placeholder values until repository is implemented
            total_searches = 0  # TODO: Implement behavior tracking
            total_hostel_views = 0  # TODO: Implement behavior tracking
            total_bookings = len(bookings)

        # Placeholders for sections not yet tracked
        recent_searches: List[RecentSearch] = []
        recently_viewed: List[RecentlyViewedHostel] = []
        recommended: List[RecommendedHostel] = []
        price_alerts: List[PriceDropAlert] = []
        availability_alerts: List[AvailabilityAlert] = []

        return VisitorDashboard(
            visitor_id=v.id,
            visitor_name=user.full_name,
            saved_hostels=saved_hostels,
            booking_history=booking_history,
            recent_searches=recent_searches,
            recently_viewed=recently_viewed,
            recommended_hostels=recommended,
            price_drop_alerts=price_alerts,
            availability_alerts=availability_alerts,
            total_searches=total_searches,
            total_hostel_views=total_hostel_views,
            total_bookings=total_bookings,
        )