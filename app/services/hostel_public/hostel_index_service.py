# app/services/hostel_public/hostel_index_service.py
from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository
from app.schemas.hostel import PublicHostelCard, PublicHostelList
from app.services.common import UnitOfWork, errors


class HostelIndexService:
    """
    Public-facing hostel index service for landing pages.

    - List featured/top hostels for home page
    - Optionally filter by city/state
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_public_card(self, h) -> PublicHostelCard:
        total_beds = h.total_beds or 0
        occupied_beds = h.occupied_beds or 0
        available_beds = max(0, total_beds - occupied_beds)

        avg_rating = Decimal(str(h.average_rating or 0.0))
        starting_price = h.starting_price_monthly or Decimal("0")
        amenities_top = (h.amenities or [])[:5]

        return PublicHostelCard(
            id=h.id,
            name=h.name,
            slug=h.slug,
            hostel_type=h.hostel_type,
            city=h.city,
            state=h.state,
            starting_price_monthly=starting_price,
            currency=h.currency or "INR",
            average_rating=avg_rating,
            total_reviews=h.total_reviews or 0,
            available_beds=available_beds,
            cover_image_url=h.cover_image_url,
            is_featured=h.is_featured,
            amenities=amenities_top,
            distance_km=None,
        )

    # ------------------------------------------------------------------ #
    # Public index
    # ------------------------------------------------------------------ #
    def list_featured_hostels(
        self,
        *,
        city: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 12,
    ) -> PublicHostelList:
        """
        List featured/top-rated public hostels for home page.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)

            # list_public already enforces is_public + is_active and orders by
            # is_featured desc, average_rating desc
            hostels = repo.list_public(
                city=city,
                state=state,
                search=None,
                limit=limit,
            )

            cards: List[PublicHostelCard] = [self._to_public_card(h) for h in hostels]

            filters_applied: Dict[str, object] = {}
            if city:
                filters_applied["city"] = city
            if state:
                filters_applied["state"] = state
            filters_applied["featured_only"] = True

            return PublicHostelList(
                hostels=cards,
                total_count=len(cards),
                filters_applied=filters_applied,
            )

    def list_newest_hostels(
        self,
        *,
        city: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 12,
    ) -> PublicHostelList:
        """
        List newest public hostels (by created_at) for discovery sections.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)

            filters: Dict[str, object] = {"is_public": True, "is_active": True}
            if city:
                filters["city"] = city
            if state:
                filters["state"] = state

            records = repo.get_multi(
                skip=0,
                limit=limit,
                filters=filters,
                order_by=[repo.model.created_at.desc()],  # type: ignore[attr-defined]
            )

            cards: List[PublicHostelCard] = [self._to_public_card(h) for h in records]

            filters_applied: Dict[str, object] = {}
            if city:
                filters_applied["city"] = city
            if state:
                filters_applied["state"] = state
            filters_applied["sort"] = "newest"

            return PublicHostelList(
                hostels=cards,
                total_count=len(cards),
                filters_applied=filters_applied,
            )