# app/services/visitor/visitor_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorRepository,
    HostelBookingRepository,
    HostelReviewRepository,
)
from app.repositories.core import UserRepository
from app.schemas.visitor import (
    VisitorUpdate,
    VisitorResponse,
    VisitorDetail,
)
from app.services.common import UnitOfWork, errors


class VisitorService:
    """
    Core Visitor service (public-side profile):

    - Get visitor detail (by user_id).
    - Lightweight summary for header/profile.
    - Update visitor preferences & notification flags.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_visitor_repo(self, uow: UnitOfWork) -> VisitorRepository:
        return uow.get_repo(VisitorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_booking_repo(self, uow: UnitOfWork) -> HostelBookingRepository:
        return uow.get_repo(HostelBookingRepository)

    def _get_review_repo(self, uow: UnitOfWork) -> HostelReviewRepository:
        return uow.get_repo(HostelReviewRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        v,
        *,
        user,
        total_bookings: int,
        saved_hostels_count: int,
    ) -> VisitorResponse:
        return VisitorResponse(
            id=v.id,
            created_at=v.created_at,
            updated_at=v.updated_at,
            user_id=v.user_id,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", ""),
            preferred_room_type=v.preferred_room_type,
            budget_min=v.budget_min,
            budget_max=v.budget_max,
            preferred_cities=v.preferred_cities or [],
            total_bookings=total_bookings,
            saved_hostels_count=saved_hostels_count,
            email_notifications=v.email_notifications,
            sms_notifications=v.sms_notifications,
            push_notifications=v.push_notifications,
        )

    def _to_detail(
        self,
        v,
        *,
        user,
        total_bookings: int,
        completed_bookings: int,
        cancelled_bookings: int,
        total_inquiries: int,
        total_reviews: int,
        avg_rating_given: Optional[Decimal],
    ) -> VisitorDetail:
        return VisitorDetail(
            id=v.id,
            created_at=v.created_at,
            updated_at=v.updated_at,
            user_id=v.user_id,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", ""),
            profile_image_url=getattr(user, "profile_image_url", None),
            preferred_room_type=v.preferred_room_type,
            budget_min=v.budget_min,
            budget_max=v.budget_max,
            preferred_cities=v.preferred_cities or [],
            preferred_amenities=v.preferred_amenities or [],
            favorite_hostel_ids=v.favorite_hostel_ids or [],
            total_saved_hostels=len(v.favorite_hostel_ids or []),
            total_bookings=total_bookings,
            completed_bookings=completed_bookings,
            cancelled_bookings=cancelled_bookings,
            total_inquiries=total_inquiries,
            total_reviews_written=total_reviews,
            average_rating_given=avg_rating_given,
            email_notifications=v.email_notifications,
            sms_notifications=v.sms_notifications,
            push_notifications=v.push_notifications,
            last_login=user.last_login_at,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_visitor_detail(self, user_id: UUID) -> VisitorDetail:
        """
        Fetch detailed visitor profile by core_user.id.
        """
        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)
            user_repo = self._get_user_repo(uow)
            booking_repo = self._get_booking_repo(uow)
            review_repo = self._get_review_repo(uow)

            user = user_repo.get(user_id)
            if user is None:
                raise errors.NotFoundError(f"User {user_id} not found")

            v = visitor_repo.get_by_user_id(user_id)
            if v is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

            # Bookings
            bookings = booking_repo.list_for_visitor(v.id)
            total_bookings = len(bookings)
            completed_bookings = sum(
                1
                for b in bookings
                if (b.booking_status or "").lower() in {"completed", "checked_out"}
            )
            cancelled_bookings = sum(
                1 for b in bookings if (b.booking_status or "").lower() == "cancelled"
            )

            # Inquiries not directly modeled under visitor; placeholder
            total_inquiries = 0

            # Reviews
            reviews = review_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"visitor_id": v.id},
            )
            total_reviews = len(reviews)
            if total_reviews:
                total_rating = sum(
                    (Decimal(str(r.overall_rating)) for r in reviews), Decimal("0")
                )
                avg_rating_given: Optional[Decimal] = total_rating / Decimal(
                    str(total_reviews)
                )
            else:
                avg_rating_given = None

        return self._to_detail(
            v,
            user=user,
            total_bookings=total_bookings,
            completed_bookings=completed_bookings,
            cancelled_bookings=cancelled_bookings,
            total_inquiries=total_inquiries,
            total_reviews=total_reviews,
            avg_rating_given=avg_rating_given,
        )

    def update_visitor(
        self,
        user_id: UUID,
        data: VisitorUpdate,
    ) -> VisitorDetail:
        """
        Update visitor profile fields (preferences & notification flags).
        """
        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)

            v = visitor_repo.get_by_user_id(user_id)
            if v is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(v, field) and field != "id":
                    setattr(v, field, value)

            uow.session.flush()  # type: ignore[union-attr]

            # Reuse get_visitor_detail for full mapping
            uow.commit()

        return self.get_visitor_detail(user_id)

    def get_summary(self, user_id: UUID) -> VisitorResponse:
        """
        Lightweight summary for a visitor (e.g., for header/profile).
        """
        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)
            user_repo = self._get_user_repo(uow)
            booking_repo = self._get_booking_repo(uow)

            user = user_repo.get(user_id)
            if user is None:
                raise errors.NotFoundError(f"User {user_id} not found")

            v = visitor_repo.get_by_user_id(user_id)
            if v is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

            bookings = booking_repo.list_for_visitor(v.id)
            total_bookings = len(bookings)
            saved_hostels_count = len(v.favorite_hostel_ids or [])

        return self._to_response(
            v,
            user=user,
            total_bookings=total_bookings,
            saved_hostels_count=saved_hostels_count,
        )