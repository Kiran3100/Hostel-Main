"""
Visitor Favorite Service

Manages visitor favorites (saved hostels) and comparison functionality.
Provides hostel favoriting, note-taking, and side-by-side comparison features.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

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
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
    ServiceException,
)

logger = logging.getLogger(__name__)


class VisitorFavoriteService:
    """
    High-level orchestration for visitor favorites.

    Features:
    - Add/remove favorites with notes
    - Update favorite metadata
    - List and filter favorites
    - Compare multiple favorites side-by-side
    - Track price history for favorites
    - Organize favorites into collections
    """

    # Maximum favorites per visitor
    MAX_FAVORITES = 100

    # Maximum number of hostels in a comparison
    MAX_COMPARISON_SIZE = 5

    def __init__(
        self,
        favorite_repo: VisitorFavoriteRepository,
        comparison_repo: FavoriteComparisonRepository,
        price_history_repo: FavoritePriceHistoryRepository,
    ) -> None:
        """
        Initialize the favorite service.

        Args:
            favorite_repo: Repository for favorite operations
            comparison_repo: Repository for comparison tracking
            price_history_repo: Repository for price history
        """
        self.favorite_repo = favorite_repo
        self.comparison_repo = comparison_repo
        self.price_history_repo = price_history_repo

    # -------------------------------------------------------------------------
    # Favorite Management
    # -------------------------------------------------------------------------

    def toggle_favorite(
        self,
        db: Session,
        visitor_id: UUID,
        request: FavoriteRequest,
    ) -> FavoriteHostelItem:
        """
        Add or remove a favorite (toggle operation).

        If request.is_favorite is True:
        - Creates a new favorite if doesn't exist
        - Restores a soft-deleted favorite if previously removed
        - Updates notes if provided

        If request.is_favorite is False:
        - Soft-deletes the favorite

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            request: Favorite request with hostel_id and preferences

        Returns:
            FavoriteHostelItem: The favorite item

        Raises:
            ValidationException: If request is invalid or limits exceeded
            ServiceException: If operation fails
        """
        try:
            # Validate hostel_id
            if not request.hostel_id:
                raise ValidationException("Hostel ID is required")

            # Check if favorite already exists
            existing = self.favorite_repo.get_by_visitor_and_hostel(
                db,
                visitor_id=visitor_id,
                hostel_id=request.hostel_id,
            )

            if request.is_favorite:
                # Adding/updating favorite
                if existing:
                    # Restore if soft-deleted
                    favorite = self.favorite_repo.restore_if_deleted(db, existing)

                    # Update notes if provided
                    if request.notes is not None:
                        favorite = self.favorite_repo.update_notes(
                            db,
                            favorite,
                            request.notes,
                        )

                    logger.info(
                        f"Restored/updated favorite {favorite.id} for visitor {visitor_id}"
                    )
                else:
                    # Check favorite limit
                    current_count = self.favorite_repo.count_active_favorites(
                        db, visitor_id
                    )
                    if current_count >= self.MAX_FAVORITES:
                        raise ValidationException(
                            f"Maximum number of favorites ({self.MAX_FAVORITES}) reached"
                        )

                    # Create new favorite
                    favorite_data = {
                        "visitor_id": visitor_id,
                        "hostel_id": request.hostel_id,
                        "notes": request.notes or "",
                        "tags": request.tags or [],
                    }

                    favorite = self.favorite_repo.create(db, data=favorite_data)

                    logger.info(
                        f"Created favorite {favorite.id} for visitor {visitor_id}"
                    )

                    # Track initial price if available
                    self._track_initial_price(db, favorite.id, request.hostel_id)

            else:
                # Removing favorite
                if not existing:
                    raise ValidationException(
                        f"Favorite for hostel {request.hostel_id} does not exist"
                    )

                self.favorite_repo.soft_delete(db, existing)
                favorite = existing

                logger.info(
                    f"Soft-deleted favorite {favorite.id} for visitor {visitor_id}"
                )

            return FavoriteHostelItem.model_validate(favorite)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to toggle favorite for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to toggle favorite: {str(e)}")

    def add_favorite(
        self,
        db: Session,
        visitor_id: UUID,
        hostel_id: UUID,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> FavoriteHostelItem:
        """
        Add a hostel to favorites.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            hostel_id: UUID of the hostel
            notes: Optional notes about the hostel
            tags: Optional tags for organization

        Returns:
            FavoriteHostelItem: The created favorite

        Raises:
            ValidationException: If hostel already favorited or limit exceeded
        """
        request = FavoriteRequest(
            hostel_id=hostel_id,
            is_favorite=True,
            notes=notes,
            tags=tags,
        )
        return self.toggle_favorite(db, visitor_id, request)

    def remove_favorite(
        self,
        db: Session,
        visitor_id: UUID,
        hostel_id: UUID,
    ) -> None:
        """
        Remove a hostel from favorites.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            hostel_id: UUID of the hostel

        Raises:
            ValidationException: If favorite doesn't exist
        """
        request = FavoriteRequest(hostel_id=hostel_id, is_favorite=False)
        self.toggle_favorite(db, visitor_id, request)

    def update_favorite_notes(
        self,
        db: Session,
        favorite_id: UUID,
        notes: str,
        visitor_id: Optional[UUID] = None,
    ) -> FavoriteHostelItem:
        """
        Update notes on a favorite.

        Args:
            db: Database session
            favorite_id: UUID of the favorite
            notes: New notes content
            visitor_id: Optional visitor ID for ownership validation

        Returns:
            FavoriteHostelItem: Updated favorite

        Raises:
            NotFoundException: If favorite not found
            ValidationException: If ownership check fails
        """
        try:
            favorite = self.favorite_repo.get_by_id(db, favorite_id)
            if not favorite:
                raise NotFoundException(f"Favorite {favorite_id} not found")

            # Verify ownership if visitor_id provided
            if visitor_id and favorite.visitor_id != visitor_id:
                raise ValidationException(
                    "Cannot update favorite belonging to another visitor"
                )

            # Validate notes length
            if notes and len(notes) > 1000:
                raise ValidationException("Notes cannot exceed 1000 characters")

            updated = self.favorite_repo.update_notes(db, favorite, notes)

            logger.info(f"Updated notes for favorite {favorite_id}")

            return FavoriteHostelItem.model_validate(updated)

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to update notes for favorite {favorite_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to update favorite notes: {str(e)}")

    def update_favorite_tags(
        self,
        db: Session,
        favorite_id: UUID,
        tags: List[str],
        visitor_id: Optional[UUID] = None,
    ) -> FavoriteHostelItem:
        """
        Update tags for a favorite.

        Args:
            db: Database session
            favorite_id: UUID of the favorite
            tags: List of tags
            visitor_id: Optional visitor ID for ownership validation

        Returns:
            FavoriteHostelItem: Updated favorite

        Raises:
            NotFoundException: If favorite not found
            ValidationException: If ownership check fails or tags invalid
        """
        try:
            favorite = self.favorite_repo.get_by_id(db, favorite_id)
            if not favorite:
                raise NotFoundException(f"Favorite {favorite_id} not found")

            if visitor_id and favorite.visitor_id != visitor_id:
                raise ValidationException(
                    "Cannot update favorite belonging to another visitor"
                )

            # Validate tags
            if len(tags) > 10:
                raise ValidationException("Maximum 10 tags allowed")

            cleaned_tags = [tag.strip().lower() for tag in tags if tag.strip()]

            updated = self.favorite_repo.update(
                db,
                obj=favorite,
                data={"tags": cleaned_tags}
            )

            logger.info(f"Updated tags for favorite {favorite_id}")

            return FavoriteHostelItem.model_validate(updated)

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to update tags for favorite {favorite_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to update favorite tags: {str(e)}")

    # -------------------------------------------------------------------------
    # Listing and Filtering
    # -------------------------------------------------------------------------

    def list_favorites(
        self,
        db: Session,
        visitor_id: UUID,
        tags: Optional[List[str]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> FavoritesList:
        """
        List all favorites for a visitor with optional filtering.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            tags: Optional tag filter
            sort_by: Field to sort by (created_at, updated_at, hostel_name)
            sort_order: Sort order (asc, desc)

        Returns:
            FavoritesList: List of favorites with metadata

        Raises:
            ValidationException: If sort parameters are invalid
            ServiceException: If retrieval fails
        """
        try:
            # Validate sort parameters
            valid_sort_fields = ["created_at", "updated_at", "hostel_name"]
            if sort_by not in valid_sort_fields:
                raise ValidationException(
                    f"Invalid sort_by field. Must be one of: {valid_sort_fields}"
                )

            if sort_order not in ["asc", "desc"]:
                raise ValidationException("sort_order must be 'asc' or 'desc'")

            # Fetch favorites with filters
            favorites = self.favorite_repo.get_favorites_by_visitor(
                db,
                visitor_id,
                tags=tags,
                sort_by=sort_by,
                sort_order=sort_order,
            )

            items = [FavoriteHostelItem.model_validate(f) for f in favorites]

            return FavoritesList(
                visitor_id=visitor_id,
                total_favorites=len(items),
                favorites=items,
                filters={
                    "tags": tags,
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                },
            )

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to list favorites for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to list favorites: {str(e)}")

    def get_favorite(
        self,
        db: Session,
        favorite_id: UUID,
        visitor_id: Optional[UUID] = None,
    ) -> FavoriteHostelItem:
        """
        Get a specific favorite by ID.

        Args:
            db: Database session
            favorite_id: UUID of the favorite
            visitor_id: Optional visitor ID for ownership validation

        Returns:
            FavoriteHostelItem: The favorite

        Raises:
            NotFoundException: If favorite not found
            ValidationException: If ownership check fails
        """
        favorite = self.favorite_repo.get_by_id(db, favorite_id)
        if not favorite:
            raise NotFoundException(f"Favorite {favorite_id} not found")

        if visitor_id and favorite.visitor_id != visitor_id:
            raise ValidationException(
                "Cannot access favorite belonging to another visitor"
            )

        return FavoriteHostelItem.model_validate(favorite)

    # -------------------------------------------------------------------------
    # Comparison
    # -------------------------------------------------------------------------

    def get_comparison(
        self,
        db: Session,
        visitor_id: UUID,
        favorite_ids: List[UUID],
    ) -> FavoriteComparisonSchema:
        """
        Build side-by-side comparison for given favorites.

        This creates a comparison session and returns structured data
        for comparing multiple hostels.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            favorite_ids: List of favorite IDs to compare (2-5 items)

        Returns:
            FavoriteComparisonSchema: Comparison data

        Raises:
            ValidationException: If favorite IDs invalid or ownership fails
            NotFoundException: If favorites not found
            ServiceException: If comparison fails
        """
        try:
            # Validate comparison size
            if not favorite_ids:
                raise ValidationException("At least one favorite required for comparison")

            if len(favorite_ids) > self.MAX_COMPARISON_SIZE:
                raise ValidationException(
                    f"Maximum {self.MAX_COMPARISON_SIZE} hostels can be compared at once"
                )

            # Fetch and validate favorites
            favorites = self.favorite_repo.get_by_ids(db, favorite_ids)

            if len(favorites) != len(favorite_ids):
                missing = set(favorite_ids) - {f.id for f in favorites}
                raise NotFoundException(
                    f"Favorites not found: {', '.join(str(id) for id in missing)}"
                )

            # Verify all favorites belong to the visitor
            for favorite in favorites:
                if favorite.visitor_id != visitor_id:
                    raise ValidationException(
                        f"Favorite {favorite.id} does not belong to visitor {visitor_id}"
                    )

            # Store comparison session for analytics
            comparison = self.comparison_repo.create(
                db,
                data={
                    "visitor_id": visitor_id,
                    "favorite_ids": favorite_ids,
                    "created_at": datetime.utcnow(),
                },
            )

            # Build comparison items with enriched data
            comparison_entries = [
                self._enrich_favorite_for_comparison(db, f)
                for f in favorites
            ]

            logger.info(
                f"Created comparison {comparison.id} for visitor {visitor_id} "
                f"with {len(favorite_ids)} hostels"
            )

            return FavoriteComparisonSchema(
                comparison_id=comparison.id,
                visitor_id=visitor_id,
                favorite_ids=favorite_ids,
                comparison_entries=comparison_entries,
                created_at=comparison.created_at,
            )

        except (ValidationException, NotFoundException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to create comparison for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to create comparison: {str(e)}")

    def get_comparison_history(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get comparison history for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            limit: Maximum number of comparisons to return

        Returns:
            List of past comparisons

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            comparisons = self.comparison_repo.get_by_visitor_id(
                db,
                visitor_id,
                limit=limit
            )

            return [
                {
                    "id": str(comp.id),
                    "favorite_ids": [str(fid) for fid in comp.favorite_ids],
                    "created_at": comp.created_at,
                    "hostel_count": len(comp.favorite_ids),
                }
                for comp in comparisons
            ]

        except Exception as e:
            logger.error(
                f"Failed to get comparison history for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to get comparison history: {str(e)}")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _track_initial_price(
        self,
        db: Session,
        favorite_id: UUID,
        hostel_id: UUID,
    ) -> None:
        """
        Track the initial price when a hostel is favorited.

        Args:
            db: Database session
            favorite_id: UUID of the favorite
            hostel_id: UUID of the hostel
        """
        try:
            # This would fetch current price from hostel repository
            # For now, we'll record with placeholder logic
            self.price_history_repo.record_price_snapshot(
                db,
                favorite_id=favorite_id,
                hostel_id=hostel_id,
            )
        except Exception as e:
            # Don't fail the favorite operation if price tracking fails
            logger.warning(
                f"Failed to track initial price for favorite {favorite_id}: {str(e)}"
            )

    def _enrich_favorite_for_comparison(
        self,
        db: Session,
        favorite: Any,
    ) -> FavoriteHostelItem:
        """
        Enrich a favorite with additional data for comparison.

        Args:
            db: Database session
            favorite: Favorite object

        Returns:
            Enriched FavoriteHostelItem
        """
        # Convert to schema
        item = FavoriteHostelItem.model_validate(favorite)

        # Add price history if available
        try:
            price_history = self.price_history_repo.get_price_trend(
                db,
                favorite.id
            )
            if price_history:
                item.price_trend = price_history
        except:
            pass

        return item