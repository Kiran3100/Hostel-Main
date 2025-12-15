# app/services/visitor/visitor_preferences_service.py
from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import VisitorRepository
from app.repositories.core import UserRepository
from app.schemas.visitor.visitor_preferences import (
    VisitorPreferences,
    PreferenceUpdate,
)
from app.services.common import UnitOfWork, errors


class VisitorPreferencesService:
    """
    Visitor preferences management:

    - Map Visitor ORM to VisitorPreferences (with safe defaults).
    - Update preferences via PreferenceUpdate using overlapping fields.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_visitor_repo(self, uow: UnitOfWork) -> VisitorRepository:
        return uow.get_repo(VisitorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # Internal mapping
    def _to_preferences(self, v) -> VisitorPreferences:
        return VisitorPreferences(
            preferred_room_type=v.preferred_room_type,
            preferred_hostel_type=None,
            budget_min=v.budget_min,
            budget_max=v.budget_max,
            preferred_cities=v.preferred_cities or [],
            preferred_areas=[],
            max_distance_from_work_km=None,
            required_amenities=v.preferred_amenities or [],
            preferred_amenities=v.preferred_amenities or [],
            need_parking=False,
            need_gym=False,
            need_laundry=False,
            need_mess=False,
            dietary_preference=None,
            earliest_move_in_date=None,
            preferred_lease_duration_months=None,
            email_notifications=v.email_notifications,
            sms_notifications=v.sms_notifications,
            push_notifications=v.push_notifications,
            notify_on_price_drop=True,
            notify_on_availability=True,
            notify_on_new_listings=True,
        )

    # Public API
    def get_preferences(self, user_id: UUID) -> VisitorPreferences:
        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)

            v = visitor_repo.get_by_user_id(user_id)
            if v is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

        return self._to_preferences(v)

    def update_preferences(
        self,
        user_id: UUID,
        data: PreferenceUpdate,
    ) -> VisitorPreferences:
        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)

            v = visitor_repo.get_by_user_id(user_id)
            if v is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            field_map = {
                "preferred_room_type": "preferred_room_type",
                "preferred_hostel_type": None,
                "budget_min": "budget_min",
                "budget_max": "budget_max",
                "preferred_cities": "preferred_cities",
                "required_amenities": "preferred_amenities",
                "dietary_preference": None,
                "email_notifications": "email_notifications",
                "sms_notifications": "sms_notifications",
                "push_notifications": "push_notifications",
                "notify_on_price_drop": None,
                "notify_on_availability": None,
                "notify_on_new_listings": None,
            }
            for key, value in mapping.items():
                target = field_map.get(key)
                if target and hasattr(v, target):
                    setattr(v, target, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self._to_preferences(v)