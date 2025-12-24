"""
Hostel selector UI service.

Manages recent hostels, favorites, quick stats, and selector cache
for efficient hostel selection interface.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.admin import HostelSelectorRepository
from app.repositories.hostel import HostelRepository
from app.models.admin import (
    RecentHostel,
    FavoriteHostel,
    HostelQuickStats,
    HostelSelectorCache,
)
from app.schemas.admin.hostel_selector import (
    HostelSelectorResponse,
    HostelSelectorItem,
    FavoriteHostelItem,
    FavoriteHostels,
    UpdateFavoriteRequest,
    RecentHostels,
    RecentHostelItem,
)


class HostelSelectorService(BaseService[HostelSelectorCache, HostelSelectorRepository]):
    """
    Service backing the hostel selector UI.
    
    Responsibilities:
    - Recent and favorite hostel management
    - Quick stats and coverage display
    - Selector cache optimization
    - Access tracking
    """
    
    # Configuration
    MAX_FAVORITES = 100
    MAX_RECENTS = 50
    DEFAULT_TRACKING_PERIOD_DAYS = 30
    
    def __init__(
        self,
        repository: HostelSelectorRepository,
        hostel_repository: HostelRepository,
        db_session: Session,
    ):
        """
        Initialize selector service.
        
        Args:
            repository: Selector repository
            hostel_repository: Hostel repository
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self.hostel_repository = hostel_repository
    
    # =========================================================================
    # Selector Response
    # =========================================================================
    
    def get_selector(
        self,
        admin_id: UUID,
        limit: int = 10,
    ) -> ServiceResult[HostelSelectorResponse]:
        """
        Build the comprehensive selector response.
        
        Combines:
        - Recent hostels
        - Favorite hostels
        - Quick stats for each
        - Attention flags
        
        Args:
            admin_id: Admin user ID
            limit: Maximum items per category
            
        Returns:
            ServiceResult containing selector response
        """
        try:
            # Get recents and favorites
            recents = self.repository.get_recent_hostels(admin_id, limit=limit)
            favorites = self.repository.get_favorites(admin_id, limit=limit)
            
            # Get quick stats
            quick_stats = self.repository.get_selector_quick_stats(admin_id)
            
            # Collect unique hostel IDs
            hostel_ids = set()
            for recent in recents:
                hostel_ids.add(recent.hostel_id)
            for favorite in favorites:
                hostel_ids.add(favorite.hostel_id)
            
            # Build selector items
            items = self._build_selector_items(
                hostel_ids,
                recents,
                favorites,
                quick_stats,
            )
            
            # Categorize hostels
            attention_required = [
                str(item.hostel_id)
                for item in items
                if item.requires_attention
            ]
            
            # Build response
            response = HostelSelectorResponse(
                admin_id=admin_id,
                total_hostels=len(items),
                active_hostels=sum(1 for i in items if not i.requires_attention),
                hostels=items,
                favorites=[str(f.hostel_id) for f in favorites],
                recent=[str(r.hostel_id) for r in recents],
                attention_required=attention_required,
                summary_text=self._generate_summary_text(items, attention_required),
            )
            
            return ServiceResult.success(response)
            
        except Exception as e:
            return self._handle_exception(e, "get hostel selector", admin_id)
    
    def refresh_selector_cache(
        self,
        admin_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Refresh the selector cache for an admin.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult indicating success
        """
        try:
            self.repository.refresh_selector_cache(admin_id)
            self.db.commit()
            
            self._logger.info(
                "Selector cache refreshed",
                extra={"admin_id": str(admin_id)},
            )
            
            return ServiceResult.success(True, message="Cache refreshed successfully")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "refresh selector cache", admin_id)
    
    # =========================================================================
    # Favorites Management
    # =========================================================================
    
    def add_or_update_favorite(
        self,
        admin_id: UUID,
        request: UpdateFavoriteRequest,
    ) -> ServiceResult[FavoriteHostelItem]:
        """
        Add, update, or remove a favorite hostel.
        
        Args:
            admin_id: Admin user ID
            request: Favorite update request
            
        Returns:
            ServiceResult containing favorite item
        """
        try:
            # Handle removal
            if not request.is_favorite:
                return self._remove_favorite(admin_id, request.hostel_id)
            
            # Check limit
            current_count = self.repository.count_favorites(admin_id)
            if current_count >= self.MAX_FAVORITES:
                existing = self.repository.get_favorite(admin_id, request.hostel_id)
                if not existing:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.BUSINESS_RULE_VIOLATION,
                            message=f"Maximum favorites limit reached ({self.MAX_FAVORITES})",
                            severity=ErrorSeverity.WARNING,
                        )
                    )
            
            # Validate hostel exists
            hostel = self.hostel_repository.get_by_id(request.hostel_id)
            if not hostel:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Hostel not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Upsert favorite
            favorite = self.repository.upsert_favorite(
                admin_id=admin_id,
                hostel_id=request.hostel_id,
                custom_label=request.custom_label,
                notes=request.notes,
                display_order=request.display_order,
            )
            self.db.commit()
            
            # Build response item
            response_item = FavoriteHostelItem(
                hostel_id=request.hostel_id,
                hostel_name=hostel.name,
                added_to_favorites=favorite.created_at,
                custom_label=favorite.custom_label,
                notes=favorite.notes,
                display_order=favorite.display_order,
                average_rating=None,  # Could be fetched from hostel stats
                available_beds=None,  # Could be fetched from hostel stats
            )
            
            self._logger.info(
                "Favorite updated",
                extra={
                    "admin_id": str(admin_id),
                    "hostel_id": str(request.hostel_id),
                },
            )
            
            return ServiceResult.success(response_item, message="Favorite updated")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "add/update favorite", admin_id)
    
    def list_favorites(
        self,
        admin_id: UUID,
        limit: int = 20,
    ) -> ServiceResult[FavoriteHostels]:
        """
        Return favorite hostels with quick stats.
        
        Args:
            admin_id: Admin user ID
            limit: Maximum favorites to return
            
        Returns:
            ServiceResult containing favorites list
        """
        try:
            favorites = self.repository.get_favorites(admin_id, limit=limit)
            
            items = []
            for favorite in favorites:
                hostel = self.hostel_repository.get_by_id(favorite.hostel_id)
                if not hostel:
                    continue
                
                items.append(
                    FavoriteHostelItem(
                        hostel_id=favorite.hostel_id,
                        hostel_name=hostel.name,
                        added_to_favorites=favorite.created_at,
                        custom_label=favorite.custom_label,
                        notes=favorite.notes,
                        display_order=favorite.display_order,
                        average_rating=None,  # Could fetch from stats
                        available_beds=None,  # Could fetch from stats
                    )
                )
            
            response = FavoriteHostels(
                admin_id=admin_id,
                hostels=items,
                total_favorites=len(items),
                max_favorites_allowed=self.MAX_FAVORITES,
            )
            
            return ServiceResult.success(response)
            
        except Exception as e:
            return self._handle_exception(e, "list favorites", admin_id)
    
    def reorder_favorites(
        self,
        admin_id: UUID,
        hostel_order: List[UUID],
    ) -> ServiceResult[bool]:
        """
        Reorder favorite hostels.
        
        Args:
            admin_id: Admin user ID
            hostel_order: Ordered list of hostel IDs
            
        Returns:
            ServiceResult indicating success
        """
        try:
            for index, hostel_id in enumerate(hostel_order):
                favorite = self.repository.get_favorite(admin_id, hostel_id)
                if favorite:
                    self.repository.update_favorite(
                        favorite.id,
                        {'display_order': index},
                    )
            
            self.db.commit()
            
            self._logger.info(
                "Favorites reordered",
                extra={
                    "admin_id": str(admin_id),
                    "count": len(hostel_order),
                },
            )
            
            return ServiceResult.success(True, message="Favorites reordered")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "reorder favorites", admin_id)
    
    # =========================================================================
    # Recent Hostels Management
    # =========================================================================
    
    def record_access(
        self,
        admin_id: UUID,
        hostel_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Record that admin accessed a hostel.
        
        Updates access count and timestamp for recent ordering.
        
        Args:
            admin_id: Admin user ID
            hostel_id: Hostel ID
            
        Returns:
            ServiceResult indicating success
        """
        try:
            self.repository.record_recent_access(admin_id, hostel_id)
            self.db.commit()
            
            return ServiceResult.success(True, message="Access recorded")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "record recent access", admin_id)
    
    def list_recents(
        self,
        admin_id: UUID,
        limit: int = 20,
    ) -> ServiceResult[RecentHostels]:
        """
        List recently accessed hostels for an admin.
        
        Args:
            admin_id: Admin user ID
            limit: Maximum recents to return
            
        Returns:
            ServiceResult containing recent hostels
        """
        try:
            recents = self.repository.get_recent_hostels(admin_id, limit=limit)
            
            items = []
            for recent in recents:
                hostel = self.hostel_repository.get_by_id(recent.hostel_id)
                if not hostel:
                    continue
                
                items.append(
                    RecentHostelItem(
                        hostel_id=recent.hostel_id,
                        hostel_name=hostel.name,
                        access_count=recent.access_count,
                        last_accessed=recent.last_accessed,
                        average_session_minutes=recent.average_session_minutes,
                        pending_tasks=None,  # Could fetch from stats
                        occupancy=None,  # Could fetch from stats
                    )
                )
            
            response = RecentHostels(
                admin_id=admin_id,
                hostels=items,
                total_recent_hostels=len(items),
                tracking_period_days=self.DEFAULT_TRACKING_PERIOD_DAYS,
            )
            
            return ServiceResult.success(response)
            
        except Exception as e:
            return self._handle_exception(e, "list recent hostels", admin_id)
    
    def clear_recents(
        self,
        admin_id: UUID,
        older_than_days: Optional[int] = None,
    ) -> ServiceResult[int]:
        """
        Clear recent hostel access history.
        
        Args:
            admin_id: Admin user ID
            older_than_days: Only clear entries older than this
            
        Returns:
            ServiceResult with count of cleared entries
        """
        try:
            count = self.repository.clear_recents(
                admin_id,
                older_than_days=older_than_days,
            )
            self.db.commit()
            
            self._logger.info(
                "Recent hostels cleared",
                extra={
                    "admin_id": str(admin_id),
                    "count": count,
                    "older_than_days": older_than_days,
                },
            )
            
            return ServiceResult.success(
                count,
                message=f"Cleared {count} recent entries",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "clear recents", admin_id)
    
    # =========================================================================
    # Quick Stats
    # =========================================================================
    
    def get_quick_stats_for_hostel(
        self,
        admin_id: UUID,
        hostel_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get quick stats for a specific hostel.
        
        Args:
            admin_id: Admin user ID
            hostel_id: Hostel ID
            
        Returns:
            ServiceResult containing quick stats
        """
        try:
            stats = self.repository.get_hostel_quick_stats(admin_id, hostel_id)
            
            return ServiceResult.success(
                stats or {},
                message="Quick stats retrieved",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get quick stats", hostel_id)
    
    def refresh_quick_stats(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Refresh quick stats cache.
        
        Args:
            admin_id: Admin user ID
            hostel_id: Optional specific hostel ID
            
        Returns:
            ServiceResult indicating success
        """
        try:
            self.repository.refresh_quick_stats(admin_id, hostel_id)
            self.db.commit()
            
            self._logger.info(
                "Quick stats refreshed",
                extra={
                    "admin_id": str(admin_id),
                    "hostel_id": str(hostel_id) if hostel_id else "all",
                },
            )
            
            return ServiceResult.success(True, message="Stats refreshed")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "refresh quick stats", admin_id)
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _build_selector_items(
        self,
        hostel_ids: set,
        recents: List[RecentHostel],
        favorites: List[FavoriteHostel],
        quick_stats: Dict[str, Any],
    ) -> List[HostelSelectorItem]:
        """
        Build selector items from data.
        
        Args:
            hostel_ids: Set of hostel IDs
            recents: List of recent hostels
            favorites: List of favorite hostels
            quick_stats: Quick stats dictionary
            
        Returns:
            List of selector items
        """
        items = []
        
        for hostel_id in hostel_ids:
            hostel = self.hostel_repository.get_by_id(hostel_id)
            if not hostel:
                continue
            
            # Check if in favorites/recents
            is_favorite = any(f.hostel_id == hostel_id for f in favorites)
            is_recent = any(r.hostel_id == hostel_id for r in recents)
            
            # Get stats for this hostel
            stats = quick_stats.get(str(hostel_id), {}) if isinstance(quick_stats, dict) else {}
            
            # Determine if requires attention
            alerts = stats.get('alerts', 0)
            requires_attention = alerts > 0
            
            # Get primary status from favorites
            favorite = next((f for f in favorites if f.hostel_id == hostel_id), None)
            is_primary = favorite.is_primary if favorite and hasattr(favorite, 'is_primary') else False
            
            item = HostelSelectorItem(
                hostel_id=hostel_id,
                hostel_name=hostel.name,
                city=hostel.city if hasattr(hostel, 'city') else None,
                is_primary=is_primary,
                is_favorite=is_favorite,
                is_recent=is_recent,
                occupancy=stats.get('occupancy'),
                pending_tasks=stats.get('pending_tasks'),
                alerts=alerts,
                requires_attention=requires_attention,
            )
            
            items.append(item)
        
        # Sort: primary first, then by attention, then favorites, then recents
        items.sort(
            key=lambda x: (
                not x.is_primary,
                not x.requires_attention,
                not x.is_favorite,
                not x.is_recent,
                x.hostel_name,
            )
        )
        
        return items
    
    def _generate_summary_text(
        self,
        items: List[HostelSelectorItem],
        attention_required: List[str],
    ) -> str:
        """
        Generate summary text for selector response.
        
        Args:
            items: List of selector items
            attention_required: List of hostel IDs requiring attention
            
        Returns:
            Summary text
        """
        total = len(items)
        attention_count = len(attention_required)
        
        if attention_count > 0:
            return f"{attention_count} of {total} hostels require attention"
        elif total > 0:
            return f"All {total} hostels running smoothly"
        else:
            return "No hostels available"
    
    def _remove_favorite(
        self,
        admin_id: UUID,
        hostel_id: UUID,
    ) -> ServiceResult[FavoriteHostelItem]:
        """
        Remove a favorite hostel.
        
        Args:
            admin_id: Admin user ID
            hostel_id: Hostel ID
            
        Returns:
            ServiceResult with removed favorite info
        """
        self.repository.remove_favorite(admin_id, hostel_id)
        self.db.commit()
        
        hostel = self.hostel_repository.get_by_id(hostel_id)
        
        response_item = FavoriteHostelItem(
            hostel_id=hostel_id,
            hostel_name=hostel.name if hostel else "",
            added_to_favorites=None,
            custom_label=None,
            notes=None,
            display_order=None,
            average_rating=None,
            available_beds=None,
        )
        
        self._logger.info(
            "Favorite removed",
            extra={
                "admin_id": str(admin_id),
                "hostel_id": str(hostel_id),
            },
        )
        
        return ServiceResult.success(response_item, message="Favorite removed")