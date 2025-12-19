# --- File: app/repositories/visitor/visitor_favorite_repository.py ---
"""
Visitor favorites repository for wishlist and saved hostels management.

This module provides repository operations for visitor favorites including
price tracking, comparison, and engagement analytics.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.visitor.visitor_favorite import (
    FavoriteComparison,
    FavoritePriceHistory,
    VisitorFavorite,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginationResult


class VisitorFavoriteRepository(BaseRepository[VisitorFavorite]):
    """
    Repository for VisitorFavorite entity.
    
    Provides comprehensive favorite management with price tracking,
    comparison features, and engagement analytics.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(VisitorFavorite, session)

    # ==================== Core CRUD Operations ====================

    def add_favorite(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
        hostel_name: str,
        hostel_slug: str,
        hostel_city: str,
        hostel_type: str,
        price_when_saved: Decimal,
        current_price: Decimal,
        available_beds: int = 0,
        average_rating: Decimal = Decimal("0.00"),
        total_reviews: int = 0,
        cover_image_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> VisitorFavorite:
        """
        Add a hostel to visitor's favorites.
        
        Args:
            visitor_id: Visitor ID
            hostel_id: Hostel ID
            hostel_name: Hostel name
            hostel_slug: Hostel slug
            hostel_city: Hostel city
            hostel_type: Hostel type
            price_when_saved: Price at time of saving
            current_price: Current hostel price
            available_beds: Number of available beds
            average_rating: Average rating
            total_reviews: Total reviews count
            cover_image_url: Cover image URL
            notes: Personal notes
            
        Returns:
            Created VisitorFavorite instance
        """
        # Check if already exists
        existing = self.find_favorite(visitor_id, hostel_id)
        if existing and not existing.is_deleted:
            raise ValueError("Hostel already in favorites")
        
        if existing and existing.is_deleted:
            # Restore soft-deleted favorite
            existing.is_deleted = False
            existing.deleted_at = None
            existing.added_at = datetime.utcnow()
            existing.price_when_saved = price_when_saved
            existing.current_price = current_price
            existing.notes = notes
            self.session.flush()
            return existing
        
        favorite = VisitorFavorite(
            visitor_id=visitor_id,
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            hostel_slug=hostel_slug,
            hostel_city=hostel_city,
            hostel_type=hostel_type,
            price_when_saved=price_when_saved,
            current_price=current_price,
            available_beds=available_beds,
            average_rating=average_rating,
            total_reviews=total_reviews,
            cover_image_url=cover_image_url,
            notes=notes,
            added_at=datetime.utcnow(),
        )
        
        self.session.add(favorite)
        self.session.flush()
        
        # Create initial price history record
        self._create_price_history_record(
            favorite_id=favorite.id,
            price=current_price,
            price_type="initial",
        )
        
        return favorite

    def remove_favorite(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
    ) -> bool:
        """
        Remove a hostel from visitor's favorites (soft delete).
        
        Args:
            visitor_id: Visitor ID
            hostel_id: Hostel ID
            
        Returns:
            True if removed, False if not found
        """
        favorite = self.find_favorite(visitor_id, hostel_id)
        if not favorite or favorite.is_deleted:
            return False
        
        favorite.is_deleted = True
        favorite.deleted_at = datetime.utcnow()
        
        self.session.flush()
        return True

    def find_favorite(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
    ) -> Optional[VisitorFavorite]:
        """
        Find a specific favorite by visitor and hostel.
        
        Args:
            visitor_id: Visitor ID
            hostel_id: Hostel ID
            
        Returns:
            VisitorFavorite instance if found
        """
        query = select(VisitorFavorite).where(
            and_(
                VisitorFavorite.visitor_id == visitor_id,
                VisitorFavorite.hostel_id == hostel_id,
            )
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def get_visitor_favorites(
        self,
        visitor_id: UUID,
        include_deleted: bool = False,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginationResult[VisitorFavorite]:
        """
        Get all favorites for a visitor.
        
        Args:
            visitor_id: Visitor ID
            include_deleted: Include soft-deleted favorites
            pagination: Pagination parameters
            
        Returns:
            Paginated list of favorites
        """
        query = select(VisitorFavorite).where(
            VisitorFavorite.visitor_id == visitor_id
        )
        
        if not include_deleted:
            query = query.where(VisitorFavorite.is_deleted == False)
        
        query = query.order_by(desc(VisitorFavorite.added_at))
        
        return self._paginate_query(query, pagination)

    def check_is_favorite(
        self,
        visitor_id: UUID,
        hostel_id: UUID,
    ) -> bool:
        """
        Check if hostel is in visitor's favorites.
        
        Args:
            visitor_id: Visitor ID
            hostel_id: Hostel ID
            
        Returns:
            True if favorited, False otherwise
        """
        query = select(func.count(VisitorFavorite.id)).where(
            and_(
                VisitorFavorite.visitor_id == visitor_id,
                VisitorFavorite.hostel_id == hostel_id,
                VisitorFavorite.is_deleted == False,
            )
        )
        
        count = self.session.execute(query).scalar_one()
        return count > 0

    def get_favorites_count(
        self,
        visitor_id: UUID,
    ) -> int:
        """
        Get total count of visitor's favorites.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Count of favorites
        """
        query = select(func.count(VisitorFavorite.id)).where(
            and_(
                VisitorFavorite.visitor_id == visitor_id,
                VisitorFavorite.is_deleted == False,
            )
        )
        
        return self.session.execute(query).scalar_one()

    # ==================== Price Tracking ====================

    def update_favorite_price(
        self,
        favorite_id: UUID,
        new_price: Decimal,
    ) -> VisitorFavorite:
        """
        Update favorite's current price and track changes.
        
        Args:
            favorite_id: Favorite ID
            new_price: New price
            
        Returns:
            Updated VisitorFavorite instance
        """
        favorite = self.find_by_id(favorite_id)
        if not favorite:
            raise ValueError(f"Favorite not found: {favorite_id}")
        
        old_price = favorite.current_price
        
        # Update price
        favorite.current_price = new_price
        favorite.last_price_check_at = datetime.utcnow()
        
        # Calculate price drop
        if new_price < old_price:
            favorite.has_price_drop = True
            favorite.price_drop_amount = old_price - new_price
            favorite.price_drop_percentage = (
                (old_price - new_price) / old_price * 100
            ).quantize(Decimal("0.01"))
        else:
            favorite.has_price_drop = False
            favorite.price_drop_amount = None
            favorite.price_drop_percentage = None
        
        self.session.flush()
        
        # Create price history record
        self._create_price_history_record(
            favorite_id=favorite_id,
            price=new_price,
            price_type="regular",
            price_change_from_previous=new_price - old_price,
        )
        
        return favorite

    def update_favorite_availability(
        self,
        favorite_id: UUID,
        available_beds: int,
    ) -> VisitorFavorite:
        """
        Update favorite's availability.
        
        Args:
            favorite_id: Favorite ID
            available_beds: Number of available beds
            
        Returns:
            Updated VisitorFavorite instance
        """
        favorite = self.find_by_id(favorite_id)
        if not favorite:
            raise ValueError(f"Favorite not found: {favorite_id}")
        
        favorite.available_beds = available_beds
        favorite.has_availability = available_beds > 0
        
        self.session.flush()
        return favorite

    def get_favorites_with_price_drops(
        self,
        visitor_id: UUID,
        min_drop_percentage: Optional[Decimal] = None,
    ) -> List[VisitorFavorite]:
        """
        Get favorites that have price drops.
        
        Args:
            visitor_id: Visitor ID
            min_drop_percentage: Minimum drop percentage filter
            
        Returns:
            List of favorites with price drops
        """
        query = select(VisitorFavorite).where(
            and_(
                VisitorFavorite.visitor_id == visitor_id,
                VisitorFavorite.is_deleted == False,
                VisitorFavorite.has_price_drop == True,
            )
        )
        
        if min_drop_percentage:
            query = query.where(
                VisitorFavorite.price_drop_percentage >= min_drop_percentage
            )
        
        query = query.order_by(desc(VisitorFavorite.price_drop_percentage))
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_favorites_without_availability(
        self,
        visitor_id: UUID,
    ) -> List[VisitorFavorite]:
        """
        Get favorites that don't have availability.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            List of favorites without availability
        """
        query = select(VisitorFavorite).where(
            and_(
                VisitorFavorite.visitor_id == visitor_id,
                VisitorFavorite.is_deleted == False,
                VisitorFavorite.has_availability == False,
            )
        ).order_by(desc(VisitorFavorite.added_at))
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def _create_price_history_record(
        self,
        favorite_id: UUID,
        price: Decimal,
        price_type: str,
        price_change_from_previous: Optional[Decimal] = None,
    ) -> FavoritePriceHistory:
        """
        Create a price history record.
        
        Args:
            favorite_id: Favorite ID
            price: Price value
            price_type: Type of price (initial, regular, discounted)
            price_change_from_previous: Change from previous price
            
        Returns:
            Created FavoritePriceHistory instance
        """
        price_change_percentage = None
        if price_change_from_previous and price > 0:
            price_change_percentage = (
                price_change_from_previous / price * 100
            ).quantize(Decimal("0.01"))
        
        history = FavoritePriceHistory(
            favorite_id=favorite_id,
            price=price,
            price_type=price_type,
            recorded_at=datetime.utcnow(),
            price_change_from_previous=price_change_from_previous,
            price_change_percentage=price_change_percentage,
        )
        
        self.session.add(history)
        self.session.flush()
        
        return history

    # ==================== Notes & Personalization ====================

    def update_favorite_notes(
        self,
        favorite_id: UUID,
        notes: Optional[str],
    ) -> VisitorFavorite:
        """
        Update personal notes for a favorite.
        
        Args:
            favorite_id: Favorite ID
            notes: Personal notes
            
        Returns:
            Updated VisitorFavorite instance
        """
        favorite = self.find_by_id(favorite_id)
        if not favorite:
            raise ValueError(f"Favorite not found: {favorite_id}")
        
        favorite.notes = notes
        
        self.session.flush()
        return favorite

    def track_favorite_view(
        self,
        favorite_id: UUID,
    ) -> VisitorFavorite:
        """
        Track when a favorite is viewed.
        
        Args:
            favorite_id: Favorite ID
            
        Returns:
            Updated VisitorFavorite instance
        """
        favorite = self.find_by_id(favorite_id)
        if not favorite:
            raise ValueError(f"Favorite not found: {favorite_id}")
        
        favorite.times_viewed += 1
        favorite.last_viewed_at = datetime.utcnow()
        
        self.session.flush()
        return favorite

    def update_alert_preferences(
        self,
        favorite_id: UUID,
        alert_on_price_drop: Optional[bool] = None,
        alert_on_availability: Optional[bool] = None,
    ) -> VisitorFavorite:
        """
        Update alert preferences for a favorite.
        
        Args:
            favorite_id: Favorite ID
            alert_on_price_drop: Enable price drop alerts
            alert_on_availability: Enable availability alerts
            
        Returns:
            Updated VisitorFavorite instance
        """
        favorite = self.find_by_id(favorite_id)
        if not favorite:
            raise ValueError(f"Favorite not found: {favorite_id}")
        
        if alert_on_price_drop is not None:
            favorite.alert_on_price_drop = alert_on_price_drop
        if alert_on_availability is not None:
            favorite.alert_on_availability = alert_on_availability
        
        self.session.flush()
        return favorite

    # ==================== Analytics & Insights ====================

    def get_favorite_statistics(
        self,
        visitor_id: UUID,
    ) -> Dict:
        """
        Get statistics about visitor's favorites.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Dictionary containing favorite statistics
        """
        favorites = self.get_visitor_favorites(visitor_id).items
        
        if not favorites:
            return {
                "total_favorites": 0,
                "favorites_with_price_drops": 0,
                "favorites_without_availability": 0,
                "average_price": Decimal("0.00"),
                "total_potential_savings": Decimal("0.00"),
                "most_viewed_favorite": None,
            }
        
        total_favorites = len(favorites)
        favorites_with_drops = sum(1 for f in favorites if f.has_price_drop)
        favorites_no_availability = sum(1 for f in favorites if not f.has_availability)
        
        total_price = sum(f.current_price for f in favorites)
        average_price = (total_price / total_favorites).quantize(Decimal("0.01"))
        
        total_savings = sum(
            f.price_drop_amount for f in favorites if f.price_drop_amount
        )
        
        most_viewed = max(favorites, key=lambda f: f.times_viewed)
        
        return {
            "total_favorites": total_favorites,
            "favorites_with_price_drops": favorites_with_drops,
            "favorites_without_availability": favorites_no_availability,
            "average_price": average_price,
            "total_potential_savings": total_savings,
            "most_viewed_favorite": {
                "hostel_name": most_viewed.hostel_name,
                "times_viewed": most_viewed.times_viewed,
            },
        }

    def get_favorites_by_city(
        self,
        visitor_id: UUID,
    ) -> Dict[str, int]:
        """
        Get distribution of favorites by city.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Dictionary mapping city to count
        """
        query = (
            select(
                VisitorFavorite.hostel_city,
                func.count(VisitorFavorite.id).label("count"),
            )
            .where(
                and_(
                    VisitorFavorite.visitor_id == visitor_id,
                    VisitorFavorite.is_deleted == False,
                )
            )
            .group_by(VisitorFavorite.hostel_city)
        )
        
        result = self.session.execute(query)
        return {row.hostel_city: row.count for row in result}

    def get_highly_viewed_favorites(
        self,
        visitor_id: UUID,
        min_views: int = 3,
    ) -> List[VisitorFavorite]:
        """
        Get favorites that have been viewed multiple times.
        
        Args:
            visitor_id: Visitor ID
            min_views: Minimum number of views
            
        Returns:
            List of highly viewed favorites
        """
        query = select(VisitorFavorite).where(
            and_(
                VisitorFavorite.visitor_id == visitor_id,
                VisitorFavorite.is_deleted == False,
                VisitorFavorite.times_viewed >= min_views,
            )
        ).order_by(desc(VisitorFavorite.times_viewed))
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Bulk Operations ====================

    def bulk_update_prices(
        self,
        price_updates: List[Tuple[UUID, Decimal]],
    ) -> int:
        """
        Bulk update favorite prices.
        
        Args:
            price_updates: List of (favorite_id, new_price) tuples
            
        Returns:
            Number of favorites updated
        """
        count = 0
        
        for favorite_id, new_price in price_updates:
            try:
                self.update_favorite_price(favorite_id, new_price)
                count += 1
            except ValueError:
                continue
        
        return count

    def bulk_update_availability(
        self,
        availability_updates: List[Tuple[UUID, int]],
    ) -> int:
        """
        Bulk update favorite availability.
        
        Args:
            availability_updates: List of (favorite_id, available_beds) tuples
            
        Returns:
            Number of favorites updated
        """
        count = 0
        
        for favorite_id, available_beds in availability_updates:
            try:
                self.update_favorite_availability(favorite_id, available_beds)
                count += 1
            except ValueError:
                continue
        
        return count


class FavoriteComparisonRepository(BaseRepository[FavoriteComparison]):
    """Repository for FavoriteComparison entity."""

    def __init__(self, session: Session):
        super().__init__(FavoriteComparison, session)

    def create_comparison(
        self,
        visitor_id: UUID,
        favorite_ids: List[UUID],
        comparison_criteria: Optional[Dict] = None,
    ) -> FavoriteComparison:
        """
        Create a new favorite comparison session.
        
        Args:
            visitor_id: Visitor ID
            favorite_ids: List of favorite IDs being compared
            comparison_criteria: Criteria used for comparison
            
        Returns:
            Created FavoriteComparison instance
        """
        comparison = FavoriteComparison(
            visitor_id=visitor_id,
            favorite_ids=favorite_ids,
            comparison_criteria=comparison_criteria or {},
        )
        
        self.session.add(comparison)
        self.session.flush()
        
        return comparison

    def complete_comparison(
        self,
        comparison_id: UUID,
        selected_favorite_id: Optional[UUID] = None,
        duration_seconds: Optional[int] = None,
    ) -> FavoriteComparison:
        """
        Mark comparison as complete with selection.
        
        Args:
            comparison_id: Comparison ID
            selected_favorite_id: Selected favorite ID (if any)
            duration_seconds: Time spent on comparison
            
        Returns:
            Updated FavoriteComparison instance
        """
        comparison = self.find_by_id(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison not found: {comparison_id}")
        
        comparison.selected_favorite_id = selected_favorite_id
        comparison.comparison_duration_seconds = duration_seconds
        
        self.session.flush()
        return comparison

    def get_visitor_comparisons(
        self,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[FavoriteComparison]:
        """
        Get visitor's comparison history.
        
        Args:
            visitor_id: Visitor ID
            limit: Maximum comparisons to return
            
        Returns:
            List of comparisons
        """
        query = (
            select(FavoriteComparison)
            .where(FavoriteComparison.visitor_id == visitor_id)
            .order_by(desc(FavoriteComparison.created_at))
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())


class FavoritePriceHistoryRepository(BaseRepository[FavoritePriceHistory]):
    """Repository for FavoritePriceHistory entity."""

    def __init__(self, session: Session):
        super().__init__(FavoritePriceHistory, session)

    def get_price_history(
        self,
        favorite_id: UUID,
        days: int = 30,
    ) -> List[FavoritePriceHistory]:
        """
        Get price history for a favorite.
        
        Args:
            favorite_id: Favorite ID
            days: Number of days to look back
            
        Returns:
            List of price history records
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = (
            select(FavoritePriceHistory)
            .where(
                and_(
                    FavoritePriceHistory.favorite_id == favorite_id,
                    FavoritePriceHistory.recorded_at >= cutoff_date,
                )
            )
            .order_by(FavoritePriceHistory.recorded_at)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_price_trends(
        self,
        favorite_id: UUID,
    ) -> Dict:
        """
        Analyze price trends for a favorite.
        
        Args:
            favorite_id: Favorite ID
            
        Returns:
            Dictionary containing trend analysis
        """
        history = self.get_price_history(favorite_id, days=90)
        
        if not history:
            return {
                "trend": "unknown",
                "average_price": Decimal("0.00"),
                "lowest_price": Decimal("0.00"),
                "highest_price": Decimal("0.00"),
                "price_volatility": Decimal("0.00"),
            }
        
        prices = [h.price for h in history]
        average_price = sum(prices) / len(prices)
        lowest_price = min(prices)
        highest_price = max(prices)
        
        # Calculate volatility (standard deviation)
        variance = sum((p - average_price) ** 2 for p in prices) / len(prices)
        volatility = variance.sqrt().quantize(Decimal("0.01"))
        
        # Determine trend
        if len(history) > 1:
            recent_avg = sum(prices[-7:]) / min(7, len(prices[-7:]))
            older_avg = sum(prices[:7]) / min(7, len(prices[:7]))
            
            if recent_avg < older_avg * Decimal("0.95"):
                trend = "decreasing"
            elif recent_avg > older_avg * Decimal("1.05"):
                trend = "increasing"
            else:
                trend = "stable"
        else:
            trend = "unknown"
        
        return {
            "trend": trend,
            "average_price": average_price.quantize(Decimal("0.01")),
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "price_volatility": volatility,
        }