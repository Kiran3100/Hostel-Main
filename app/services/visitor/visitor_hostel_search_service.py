# app/services/visitor/visitor_hostel_search_service.py
from __future__ import annotations

from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import VisitorHostelRepository, VisitorRepository
from app.schemas.visitor.visitor_preferences import SearchPreferences
from app.services.common import UnitOfWork, errors


class VisitorHostelSearchService:
    """
    Public hostel search facade using visitor_hostel (denormalized search index).

    - search_hostels: direct parameterized search over VisitorHostelRepository.
    - search_from_preferences: build a query based on a visitor's preferences.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_hostel_repo(self, uow: UnitOfWork) -> VisitorHostelRepository:
        return uow.get_repo(VisitorHostelRepository)

    def _get_visitor_repo(self, uow: UnitOfWork) -> VisitorRepository:
        return uow.get_repo(VisitorRepository)

    # ------------------------------------------------------------------ #
    # Direct search
    # ------------------------------------------------------------------ #
    def search_hostels(
        self,
        *,
        city: Optional[str] = None,
        area: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        gender_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ):
        """
        Directly delegate to VisitorHostelRepository.search.

        Returns:
            List[VisitorHostel] ORM instances.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)
            results = repo.search(
                city=city,
                area=area,
                min_price=min_price,
                max_price=max_price,
                gender_type=gender_type,
                search=search,
                limit=limit,
            )
        return results

    # ------------------------------------------------------------------ #
    # Search from preferences
    # ------------------------------------------------------------------ #
    def search_from_visitor_preferences(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
    ):
        """
        Build a search query from a visitor's stored preferences:

        - city: first preferred city if any
        - min_price/max_price: budget_min/budget_max
        - other fields left to free-text 'search' or gender_type as provided by caller.
        """
        with UnitOfWork(self._session_factory) as uow:
            visitor_repo = self._get_visitor_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            v = visitor_repo.get_by_user_id(user_id)
            if v is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

            city = v.preferred_cities[0] if v.preferred_cities else None
            min_price = float(v.budget_min) if v.budget_min is not None else None
            max_price = float(v.budget_max) if v.budget_max is not None else None

            results = hostel_repo.search(
                city=city,
                area=None,
                min_price=min_price,
                max_price=max_price,
                gender_type=None,
                search=None,
                limit=limit,
            )

        return results