"""
Visitor Favorite Service

Manages visitor favorites (saved hostels) and comparisons.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorFavoriteRepository,
    FavoriteComparisonRepository,
    FavoritePriceHistoryRepository,
)
from app.schemas.visitor import (
    FavoriteRequest,
    FavoritesList,
    FavoriteHostelItem,
    FavoriteComparison as FavoriteComparisonSchema,
)
from app.core.exceptions import ValidationException


class VisitorFavoriteService:
    """
    High-level orchestration for favorites:

    - Add/remove/update notes on favorites
    - List favorites
    - Compare multiple favorites
    """

    def __init__(
        self,
        favorite_repo: VisitorFavoriteRepository,
        comparison_repo: FavoriteComparisonRepository,
        price_history_repo: FavoritePriceHistoryRepository,
    ) -> None:
        self.favorite_repo = favorite_repo
        self.comparison_repo = comparison_repo
        self.price_history_repo = price_history_repo

    def toggle_favorite(
        self,
        db: Session,
        visitor_id: UUID,
        request: FavoriteRequest,
    ) -> FavoriteHostelItem:
        """
        Add or remove a favorite.

        If request.is_favorite is True, creates or restores a favorite.
        If False, soft-deletes the favorite.
        """
        existing = self.favorite_repo.get_by_visitor_and_hostel(
            db, visitor_id=visitor_id, hostel_id=request.hostel_id
        )

        if request.is_favorite:
            if existing:
                favorite = self.favorite_repo.restore_if_deleted(db, existing)
                if request.notes is not None:
                    favorite = self.favorite_repo.update_notes(
                        db, favorite, request.notes
                    )
            else:
                favorite = self.favorite_repo.create(
                    db,
                    data={
                        "visitor_id": visitor_id,
                        "hostel_id": request.hostel_id,
                        "notes": request.notes,
                    },
                )
        else:
            if existing:
                self.favorite_repo.soft_delete(db, existing)
                favorite = existing
            else:
                raise ValidationException("Favorite does not exist")

        return FavoriteHostelItem.model_validate(favorite)

    def list_favorites(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> FavoritesList:
        """
        List all favorites for a visitor.
        """
        favorites = self.favorite_repo.get_favorites_by_visitor(db, visitor_id)
        items = [FavoriteHostelItem.model_validate(f) for f in favorites]

        return FavoritesList(
            visitor_id=visitor_id,
            total_favorites=len(items),
            favorites=items,
        )

    def update_favorite_notes(
        self,
        db: Session,
        favorite_id: UUID,
        notes: str,
    ) -> FavoriteHostelItem:
        """
        Update notes on a favorite.
        """
        favorite = self.favorite_repo.get_by_id(db, favorite_id)
        if not favorite:
            raise ValidationException("Favorite not found")

        updated = self.favorite_repo.update_notes(db, favorite, notes)
        return FavoriteHostelItem.model_validate(updated)

    def get_comparison(
        self,
        db: Session,
        visitor_id: UUID,
        favorite_ids: List[UUID],
    ) -> FavoriteComparisonSchema:
        """
        Build comparison for given favorites.
        """
        # Validate favorites belong to visitor
        favorites = self.favorite_repo.get_by_ids(db, favorite_ids)
        if len(favorites) != len(favorite_ids):
            raise ValidationException("Some favorites not found")

        for f in favorites:
            if f.visitor_id != visitor_id:
                raise ValidationException("Favorite does not belong to visitor")

        # Store comparison session (optional)
        comparison = self.comparison_repo.create(
            db,
            data={
                "visitor_id": visitor_id,
                "favorite_ids": favorite_ids,
            },
        )

        hostels = [
            FavoriteHostelItem.model_validate(f) for f in favorites
        ]

        return FavoriteComparisonSchema(
            favorite_ids=favorite_ids,
            comparison_entries=hostels,
        )