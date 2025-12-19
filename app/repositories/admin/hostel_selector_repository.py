"""
Hostel Selector Repository

Manages hostel selection UI with recent access, favorites,
quick stats, and pre-computed selector cache.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.admin.hostel_selector import (
    RecentHostel,
    FavoriteHostel,
    HostelQuickStats,
    HostelSelectorCache
)
from app.models.admin.admin_user import AdminUser
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
    DuplicateError
)


class HostelSelectorRepository(BaseRepository[RecentHostel]):
    """
    Hostel selector management with:
    - Recent access tracking with frequency scoring
    - Favorites with customization
    - Quick stats caching
    - Pre-computed selector data
    """

    def __init__(self, db: Session):
        super().__init__(RecentHostel, db)

    # ==================== RECENT HOSTELS ====================

    async def track_hostel_access(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        session_duration_minutes: int = 0,
        last_action: Optional[str] = None
    ) -> RecentHostel:
        """Track hostel access for recent list."""
        # Get or create recent entry
        stmt = (
            select(RecentHostel)
            .where(RecentHostel.admin_id == admin_id)
            .where(RecentHostel.hostel_id == hostel_id)
        )

        result = await self.db.execute(stmt)
        recent = result.scalar_one_or_none()

        if recent:
            # Update existing
            recent.last_accessed = datetime.utcnow()
            recent.access_count += 1
            recent.access_count_last_7_days += 1
            recent.access_count_last_30_days += 1
            
            if session_duration_minutes > 0:
                recent.total_session_time_minutes += session_duration_minutes
                recent.avg_session_duration_minutes = Decimal(
                    recent.total_session_time_minutes / recent.access_count
                )
            
            if last_action:
                recent.last_action_performed = last_action

            # Recalculate frequency score
            recent.frequency_score = self._calculate_frequency_score(recent)

        else:
            # Create new entry
            recent = RecentHostel(
                admin_id=admin_id,
                hostel_id=hostel_id,
                last_accessed=datetime.utcnow(),
                first_accessed=datetime.utcnow(),
                access_count=1,
                access_count_last_7_days=1,
                access_count_last_30_days=1,
                total_session_time_minutes=session_duration_minutes,
                avg_session_duration_minutes=Decimal(str(session_duration_minutes)),
                last_action_performed=last_action,
                frequency_score=Decimal('50.00')  # Initial score
            )
            self.db.add(recent)

        await self.db.flush()
        return recent

    def _calculate_frequency_score(self, recent: RecentHostel) -> Decimal:
        """
        Calculate frequency score based on recency and frequency.
        Score range: 0-100
        """
        # Recency component (0-50 points)
        hours_since = (datetime.utcnow() - recent.last_accessed).total_seconds() / 3600
        recency_score = max(0, 50 - hours_since)

        # Frequency component (0-50 points)
        frequency_score = min(recent.access_count_last_7_days * 5, 50)

        total_score = Decimal(str(recency_score + frequency_score))
        return total_score.quantize(Decimal('0.01'))

    async def get_recent_hostels(
        self,
        admin_id: UUID,
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[RecentHostel]:
        """Get recent hostels sorted by frequency score."""
        stmt = (
            select(RecentHostel)
            .where(RecentHostel.admin_id == admin_id)
            .where(RecentHostel.frequency_score >= min_score)
            .options(selectinload(RecentHostel.hostel))
            .order_by(desc(RecentHostel.frequency_score))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def cleanup_old_recent_entries(
        self,
        admin_id: UUID,
        keep_count: int = 20
    ) -> int:
        """Keep only top N recent entries per admin."""
        # Get all entries for admin
        stmt = (
            select(RecentHostel)
            .where(RecentHostel.admin_id == admin_id)
            .order_by(desc(RecentHostel.frequency_score))
        )

        result = await self.db.execute(stmt)
        all_entries = result.scalars().all()

        if len(all_entries) <= keep_count:
            return 0

        # Delete entries beyond keep_count
        to_delete = all_entries[keep_count:]
        for entry in to_delete:
            await self.db.delete(entry)

        await self.db.flush()
        return len(to_delete)

    async def decay_access_counts(self) -> int:
        """
        Decay access counts for time-based accuracy.
        Run daily to reset 7-day and 30-day counters.
        """
        # Reset 7-day counts for entries older than 7 days
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        stmt = (
            select(RecentHostel)
            .where(RecentHostel.last_accessed < seven_days_ago)
        )

        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        for entry in entries:
            entry.access_count_last_7_days = 0
            entry.frequency_score = self._calculate_frequency_score(entry)

        await self.db.flush()
        return len(entries)

    # ==================== FAVORITE HOSTELS ====================

    async def add_favorite(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        custom_label: Optional[str] = None,
        notes: Optional[str] = None,
        color_code: Optional[str] = None,
        display_order: int = 0
    ) -> FavoriteHostel:
        """Add hostel to favorites."""
        # Check for existing favorite
        existing = await self.find_favorite(admin_id, hostel_id)
        if existing and not existing.is_deleted:
            raise DuplicateError(f"Hostel {hostel_id} already in favorites")

        favorite = FavoriteHostel(
            admin_id=admin_id,
            hostel_id=hostel_id,
            custom_label=custom_label,
            notes=notes,
            color_code=color_code,
            display_order=display_order,
            added_to_favorites=datetime.utcnow()
        )

        self.db.add(favorite)
        await self.db.flush()
        return favorite

    async def find_favorite(
        self,
        admin_id: UUID,
        hostel_id: UUID
    ) -> Optional[FavoriteHostel]:
        """Find specific favorite."""
        stmt = (
            select(FavoriteHostel)
            .where(FavoriteHostel.admin_id == admin_id)
            .where(FavoriteHostel.hostel_id == hostel_id)
            .where(FavoriteHostel.is_deleted == False)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_favorites(
        self,
        admin_id: UUID,
        include_stats: bool = True
    ) -> List[FavoriteHostel]:
        """Get all favorites for admin."""
        stmt = (
            select(FavoriteHostel)
            .where(FavoriteHostel.admin_id == admin_id)
            .where(FavoriteHostel.is_deleted == False)
            .options(selectinload(FavoriteHostel.hostel))
            .order_by(FavoriteHostel.display_order, FavoriteHostel.added_to_favorites)
        )

        result = await self.db.execute(stmt)
        favorites = result.unique().scalars().all()

        # Update quick stats if requested
        if include_stats:
            for favorite in favorites:
                await self._update_favorite_stats(favorite)

        return favorites

    async def update_favorite(
        self,
        favorite_id: UUID,
        updates: Dict[str, Any]
    ) -> FavoriteHostel:
        """Update favorite hostel settings."""
        favorite = await self.db.get(FavoriteHostel, favorite_id)
        if not favorite:
            raise EntityNotFoundError(f"Favorite {favorite_id} not found")

        for key, value in updates.items():
            if hasattr(favorite, key):
                setattr(favorite, key, value)

        await self.db.flush()
        return favorite

    async def remove_favorite(
        self,
        admin_id: UUID,
        hostel_id: UUID
    ) -> bool:
        """Remove hostel from favorites (soft delete)."""
        favorite = await self.find_favorite(admin_id, hostel_id)
        if not favorite:
            return False

        favorite.is_deleted = True
        favorite.deleted_at = datetime.utcnow()
        await self.db.flush()
        return True

    async def reorder_favorites(
        self,
        admin_id: UUID,
        ordered_hostel_ids: List[UUID]
    ) -> List[FavoriteHostel]:
        """Reorder favorites based on provided sequence."""
        favorites = await self.get_favorites(admin_id, include_stats=False)
        
        favorite_map = {f.hostel_id: f for f in favorites}

        updated = []
        for idx, hostel_id in enumerate(ordered_hostel_ids):
            if hostel_id in favorite_map:
                favorite = favorite_map[hostel_id]
                favorite.display_order = idx
                updated.append(favorite)

        await self.db.flush()
        return updated

    async def _update_favorite_stats(self, favorite: FavoriteHostel) -> None:
        """Update cached quick stats for favorite."""
        # This would typically query real data
        # Simplified here
        favorite.current_occupancy = Decimal('75.50')
        favorite.pending_items = 5
        favorite.last_accessed = datetime.utcnow()

    # ==================== QUICK STATS ====================

    async def get_hostel_quick_stats(
        self,
        hostel_id: UUID,
        refresh_if_stale: bool = True
    ) -> Optional[HostelQuickStats]:
        """Get quick stats for hostel."""
        stmt = (
            select(HostelQuickStats)
            .where(HostelQuickStats.hostel_id == hostel_id)
        )

        result = await self.db.execute(stmt)
        stats = result.scalar_one_or_none()

        if stats and refresh_if_stale and stats.is_stale:
            await self.refresh_quick_stats(hostel_id)
            # Reload
            result = await self.db.execute(stmt)
            stats = result.scalar_one_or_none()

        return stats

    async def refresh_quick_stats(
        self,
        hostel_id: UUID,
        stats_data: Optional[Dict[str, Any]] = None
    ) -> HostelQuickStats:
        """Refresh quick stats for hostel."""
        stmt = (
            select(HostelQuickStats)
            .where(HostelQuickStats.hostel_id == hostel_id)
        )

        result = await self.db.execute(stmt)
        stats = result.scalar_one_or_none()

        if not stats:
            stats = HostelQuickStats(hostel_id=hostel_id)
            self.db.add(stats)

        if stats_data:
            # Use provided data
            stats.total_students = stats_data.get('total_students', 0)
            stats.active_students = stats_data.get('active_students', 0)
            stats.total_capacity = stats_data.get('total_capacity', 0)
            stats.available_beds = stats_data.get('available_beds', 0)
            stats.occupancy_percentage = Decimal(str(stats_data.get('occupancy_percentage', 0)))
            stats.pending_tasks = stats_data.get('pending_tasks', 0)
            stats.urgent_alerts = stats_data.get('urgent_alerts', 0)
            stats.pending_bookings = stats_data.get('pending_bookings', 0)
            stats.open_complaints = stats_data.get('open_complaints', 0)
            stats.maintenance_requests = stats_data.get('maintenance_requests', 0)
            stats.revenue_this_month = Decimal(str(stats_data.get('revenue_this_month', 0)))
            stats.outstanding_payments = Decimal(str(stats_data.get('outstanding_payments', 0)))
            stats.health_score = Decimal(str(stats_data.get('health_score', 0)))
            stats.status_indicator = stats_data.get('status_indicator', 'normal')
            stats.requires_attention = stats_data.get('requires_attention', False)
        else:
            # Calculate from database (simplified)
            stats.total_students = 0
            stats.active_students = 0
            stats.total_capacity = 0
            stats.available_beds = 0
            stats.occupancy_percentage = Decimal('0.00')
            stats.pending_tasks = 0
            stats.urgent_alerts = 0
            stats.health_score = Decimal('0.00')
            stats.status_indicator = 'normal'

        stats.last_updated = datetime.utcnow()
        await self.db.flush()
        return stats

    async def bulk_refresh_stats(
        self,
        hostel_ids: List[UUID]
    ) -> List[HostelQuickStats]:
        """Refresh stats for multiple hostels."""
        stats_list = []
        for hostel_id in hostel_ids:
            stats = await self.refresh_quick_stats(hostel_id)
            stats_list.append(stats)
        return stats_list

    # ==================== SELECTOR CACHE ====================

    async def get_selector_cache(
        self,
        admin_id: UUID,
        refresh_if_stale: bool = True
    ) -> Optional[HostelSelectorCache]:
        """Get pre-computed selector cache for admin."""
        stmt = (
            select(HostelSelectorCache)
            .where(HostelSelectorCache.admin_id == admin_id)
        )

        result = await self.db.execute(stmt)
        cache = result.scalar_one_or_none()

        if cache and refresh_if_stale and cache.is_stale:
            await self.rebuild_selector_cache(admin_id)
            # Reload
            result = await self.db.execute(stmt)
            cache = result.scalar_one_or_none()

        return cache

    async def rebuild_selector_cache(
        self,
        admin_id: UUID
    ) -> HostelSelectorCache:
        """Rebuild complete selector cache for admin."""
        start_time = datetime.utcnow()

        # Get or create cache
        stmt = (
            select(HostelSelectorCache)
            .where(HostelSelectorCache.admin_id == admin_id)
        )

        result = await self.db.execute(stmt)
        cache = result.scalar_one_or_none()

        if not cache:
            cache = HostelSelectorCache(admin_id=admin_id)
            self.db.add(cache)

        # Get admin's assignments
        from app.repositories.admin.admin_hostel_assignment_repository import (
            AdminHostelAssignmentRepository
        )
        
        assignment_repo = AdminHostelAssignmentRepository(self.db)
        assignments = await assignment_repo.get_admin_assignments(admin_id)

        # Build cache data
        cache.total_hostels = len(assignments)
        cache.active_hostels = len([a for a in assignments if a.is_active])

        # Recent hostel IDs
        recent = await self.get_recent_hostels(admin_id, limit=10)
        cache.recent_hostel_ids = [str(r.hostel_id) for r in recent]

        # Favorite hostel IDs
        favorites = await self.get_favorites(admin_id, include_stats=False)
        cache.favorite_hostel_ids = [str(f.hostel_id) for f in favorites]

        # Hostels requiring attention
        attention_required = []
        for assignment in assignments:
            stats = await self.get_hostel_quick_stats(
                assignment.hostel_id,
                refresh_if_stale=False
            )
            if stats and (stats.urgent_alerts > 0 or stats.requires_attention):
                attention_required.append(str(assignment.hostel_id))

        cache.attention_required_ids = attention_required

        # Aggregate stats
        total_pending = 0
        total_alerts = 0
        occupancy_sum = Decimal('0.00')

        for assignment in assignments:
            stats = await self.get_hostel_quick_stats(
                assignment.hostel_id,
                refresh_if_stale=False
            )
            if stats:
                total_pending += stats.pending_tasks
                total_alerts += stats.urgent_alerts
                occupancy_sum += stats.occupancy_percentage

        cache.total_pending_tasks = total_pending
        cache.total_urgent_alerts = total_alerts
        cache.avg_occupancy_percentage = (
            occupancy_sum / cache.total_hostels
            if cache.total_hostels > 0 else Decimal('0.00')
        )

        # Build complete hostel data
        hostels_data = {}
        for assignment in assignments:
            stats = await self.get_hostel_quick_stats(
                assignment.hostel_id,
                refresh_if_stale=False
            )
            
            hostels_data[str(assignment.hostel_id)] = {
                'name': assignment.hostel.name if assignment.hostel else None,
                'is_primary': assignment.is_primary,
                'occupancy': float(stats.occupancy_percentage) if stats else 0,
                'pending_tasks': stats.pending_tasks if stats else 0,
                'urgent_alerts': stats.urgent_alerts if stats else 0,
                'status': stats.status_indicator if stats else 'unknown'
            }

        cache.hostels_data = hostels_data

        # Update metadata
        cache.last_updated = datetime.utcnow()
        cache.build_duration_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )

        await self.db.flush()
        return cache

    async def invalidate_selector_cache(
        self,
        admin_id: UUID
    ) -> bool:
        """Force invalidate selector cache."""
        cache = await self.get_selector_cache(admin_id, refresh_if_stale=False)
        if not cache:
            return False

        # Set last_updated to past to force refresh
        cache.last_updated = datetime.utcnow() - timedelta(
            seconds=cache.cache_ttl_seconds + 1
        )
        await self.db.flush()
        return True

    # ==================== ANALYTICS ====================

    async def get_selector_analytics(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get analytics about hostel selector usage."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Most accessed hostels
        recent_stmt = (
            select(
                RecentHostel.hostel_id,
                Hostel.name,
                RecentHostel.access_count,
                RecentHostel.frequency_score
            )
            .join(Hostel, RecentHostel.hostel_id == Hostel.id)
            .where(RecentHostel.admin_id == admin_id)
            .where(RecentHostel.last_accessed >= cutoff)
            .order_by(desc(RecentHostel.access_count))
            .limit(5)
        )

        recent_result = await self.db.execute(recent_stmt)
        most_accessed = [
            {
                'hostel_id': row[0],
                'hostel_name': row[1],
                'access_count': row[2],
                'frequency_score': float(row[3])
            }
            for row in recent_result
        ]

        # Favorite count
        fav_count_stmt = (
            select(func.count(FavoriteHostel.id))
            .where(FavoriteHostel.admin_id == admin_id)
            .where(FavoriteHostel.is_deleted == False)
        )
        favorite_count = await self.db.scalar(fav_count_stmt) or 0

        return {
            'period_days': days,
            'most_accessed_hostels': most_accessed,
            'total_favorites': favorite_count,
            'unique_hostels_accessed': len(most_accessed)
        }