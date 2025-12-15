# app/services/visitor/favorites_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository
from app.repositories.associations import UserHostelRepository
from app.repositories.visitor import VisitorRepository
from app.schemas.visitor.visitor_favorites import (
    FavoriteRequest,
    FavoritesList,
    FavoriteHostelItem,
    FavoriteUpdate,
)
from app.services.common import UnitOfWork, errors


class FavoritesService:
    """
    Visitor favorites/wishlist management.

    Implementation:

    - Uses assoc_user_hostel as backing store with association_type="favorite".
    - FavoriteHostelItem.favorite_id is assoc_user_hostel.id.
    - Extra metadata (notes, price_when_saved, times_viewed, etc.) is stored in
      UserHostel.metadata_json.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
    ) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_visitor_repo(self, uow: UnitOfWork) -> VisitorRepository:
        return uow.get_repo(VisitorRepository)

    def _get_assoc_repo(self, uow: UnitOfWork) -> UserHostelRepository:
        return uow.get_repo(UserHostelRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Set favorite
    # ------------------------------------------------------------------ #
    def set_favorite(
        self,
        user_id: UUID,
        data: FavoriteRequest,
    ) -> None:
        """
        Add or remove a hostel from a user's favorites.

        - If is_favorite=True: upsert assoc_user_hostel.
        - If is_favorite=False: soft-delete assoc_user_hostel rows.
        """
        with UnitOfWork(self._session_factory) as uow:
            assoc_repo = self._get_assoc_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            existing = assoc_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={
                    "user_id": user_id,
                    "hostel_id": data.hostel_id,
                    "association_type": "favorite",
                },
            )

            if data.is_favorite:
                if existing:
                    assoc = existing[0]
                    meta = assoc.metadata_json or {}
                    meta["notes"] = data.notes
                    meta.setdefault("price_when_saved", str(hostel.starting_price_monthly or Decimal("0")))
                    assoc.metadata_json = meta  # type: ignore[attr-defined]
                    uow.session.flush()  # type: ignore[union-attr]
                else:
                    meta = {
                        "notes": data.notes,
                        "price_when_saved": str(hostel.starting_price_monthly or Decimal("0")),
                        "times_viewed": 0,
                        "last_viewed": None,
                    }
                    assoc_repo.create(
                        {
                            "user_id": user_id,
                            "hostel_id": data.hostel_id,
                            "association_type": "favorite",
                            "metadata_json": meta,
                        }
                    )
            else:
                for a in existing:
                    assoc_repo.delete(a)

            uow.commit()

    # ------------------------------------------------------------------ #
    # List favorites
    # ------------------------------------------------------------------ #
    def get_favorites(self, user_id: UUID) -> FavoritesList:
        with UnitOfWork(self._session_factory) as uow:
            assoc_repo = self._get_assoc_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            visitor_repo = self._get_visitor_repo(uow)

            visitor = visitor_repo.get_by_user_id(user_id)
            if visitor is None:
                raise errors.NotFoundError(f"Visitor profile for user {user_id} not found")

            assocs = assoc_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={
                    "user_id": user_id,
                    "association_type": "favorite",
                },
            )

            items: List[FavoriteHostelItem] = []
            now = self._now()

            for a in assocs:
                hostel = hostel_repo.get(a.hostel_id)
                if not hostel:
                    continue

                starting_price = hostel.starting_price_monthly or Decimal("0")
                current_price = starting_price

                meta = a.metadata_json or {}
                notes = meta.get("notes")
                price_when_saved = Decimal(str(meta.get("price_when_saved", starting_price)))
                times_viewed = int(meta.get("times_viewed", 0))
                last_viewed = meta.get("last_viewed")

                has_price_drop = current_price < price_when_saved
                drop_pct: Optional[Decimal] = None
                if has_price_drop and price_when_saved > 0:
                    drop_pct = (
                        (price_when_saved - current_price)
                        / price_when_saved
                        * Decimal("100")
                    )

                available_beds = max(
                    0, (hostel.total_beds or 0) - (hostel.occupied_beds or 0)
                )
                has_availability = available_beds > 0

                items.append(
                    FavoriteHostelItem(
                        favorite_id=a.id,
                        hostel_id=hostel.id,
                        hostel_name=hostel.name,
                        hostel_slug=hostel.slug,
                        hostel_city=hostel.city,
                        hostel_type=hostel.hostel_type.value
                        if hasattr(hostel.hostel_type, "value")
                        else str(hostel.hostel_type),
                        starting_price_monthly=starting_price,
                        price_when_saved=price_when_saved,
                        current_price=current_price,
                        has_price_drop=has_price_drop,
                        price_drop_percentage=drop_pct,
                        available_beds=available_beds,
                        has_availability=has_availability,
                        average_rating=Decimal(str(hostel.average_rating or 0.0)),
                        total_reviews=hostel.total_reviews or 0,
                        cover_image_url=hostel.cover_image_url,
                        notes=notes,
                        added_to_favorites=a.created_date
                        if getattr(a, "created_date", None)
                        else now.date(),
                        times_viewed=times_viewed,
                        last_viewed=last_viewed,
                    )
                )

        return FavoritesList(
            visitor_id=visitor.id,
            total_favorites=len(items),
            favorites=items,
        )

    # ------------------------------------------------------------------ #
    # Update favorite metadata (notes)
    # ------------------------------------------------------------------ #
    def update_favorite(self, user_id: UUID, data: FavoriteUpdate) -> None:
        with UnitOfWork(self._session_factory) as uow:
            assoc_repo = self._get_assoc_repo(uow)

            assoc = assoc_repo.get(data.favorite_id)
            if assoc is None or assoc.user_id != user_id:
                raise errors.NotFoundError("Favorite not found or not owned by user")

            meta = assoc.metadata_json or {}
            meta["notes"] = data.notes
            assoc.metadata_json = meta  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()