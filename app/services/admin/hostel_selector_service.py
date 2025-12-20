"""
Hostel Selector Service

Business logic for hostel selection UI optimization including
recent access tracking, favorites, and pre-computed selector cache.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.admin.hostel_selector import (
    RecentHostel,
    FavoriteHostel,
    HostelQuickStats,
    HostelSelectorCache
)
from app.repositories.admin.hostel_selector_repository import HostelSelectorRepository
from app.repositories.admin.admin_hostel_assignment_repository import (
    AdminHostelAssignmentRepository
)
from app.core.exceptions import (
    ValidationError,
    EntityNotFoundError,
    DuplicateError
)


class HostelSelectorService:
    """
    Selector optimization service with:
    - Recent access tracking with intelligent scoring
    - Favorites management with customization
    - Quick stats caching for performance
    - Pre-computed selector data
    - Smart recommendations
    """

    def __init__(self, db: Session):
        self.db = db
        self.selector_repo = HostelSelectorRepository(db)
        self.assignment_repo = AdminHostelAssignmentRepository(db)

        # Configuration
        self.max_recent_entries = 20
        self.stats_cache_ttl_seconds = 300  # 5 minutes
        self.selector_cache_ttl_seconds = 300

    # ==================== RECENT HOSTELS ====================

    async def track_hostel_access(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        session_duration_minutes: int = 0,
        last_action: Optional[str] = None
    ) -> RecentHostel:
        """Track hostel access for recent list with frequency scoring."""
        # Validate assignment
        assignment = await self.assignment_repo.find_assignment(admin_id, hostel_id)
        if not assignment:
            raise ValidationError(
                f"Admin {admin_id} not assigned to hostel {hostel_id}"
            )

        # Track access
        recent = await self.selector_repo.track_hostel_access(
            admin_id=admin_id,
            hostel_id=hostel_id,
            session_duration_minutes=session_duration_minutes,
            last_action=last_action
        )

        # Cleanup old entries
        await self.selector_repo.cleanup_old_recent_entries(
            admin_id=admin_id,
            keep_count=self.max_recent_entries
        )

        await self.db.commit()
        return recent

    async def get_recent_hostels(
        self,
        admin_id: UUID,
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[RecentHostel]:
        """Get recent hostels sorted by frequency score."""
        return await self.selector_repo.get_recent_hostels(
            admin_id=admin_id,
            limit=limit,
            min_score=min_score
        )

    async def get_recent_with_stats(
        self,
        admin_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent hostels with current stats."""
        recent = await self.get_recent_hostels(admin_id, limit)
        
        result = []
        for entry in recent:
            # Get quick stats
            stats = await self.get_hostel_quick_stats(entry.hostel_id)
            
            result.append({
                'hostel_id': str(entry.hostel_id),
                'hostel_name': entry.hostel.name if entry.hostel else None,
                'last_accessed': entry.last_accessed,
                'access_count': entry.access_count,
                'frequency_score': float(entry.frequency_score),
                'stats': {
                    'occupancy': float(stats.occupancy_percentage) if stats else 0,
                    'pending_tasks': stats.pending_tasks if stats else 0,
                    'urgent_alerts': stats.urgent_alerts if stats else 0,
                    'status': stats.status_indicator if stats else 'unknown'
                }
            })

        return result

    # ==================== FAVORITES ====================

    async def add_favorite(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        custom_label: Optional[str] = None,
        notes: Optional[str] = None,
        color_code: Optional[str] = None,
        quick_actions: Optional[List[str]] = None
    ) -> FavoriteHostel:
        """Add hostel to favorites with customization."""
        # Validate assignment
        assignment = await self.assignment_repo.find_assignment(admin_id, hostel_id)
        if not assignment:
            raise ValidationError(
                f"Admin {admin_id} not assigned to hostel {hostel_id}"
            )

        # Get next display order
        favorites = await self.selector_repo.get_favorites(admin_id, include_stats=False)
        display_order = len(favorites)

        # Add favorite
        favorite = await self.selector_repo.add_favorite(
            admin_id=admin_id,
            hostel_id=hostel_id,
            custom_label=custom_label,
            notes=notes,
            color_code=color_code,
            display_order=display_order
        )

        # Set quick actions if provided
        if quick_actions:
            favorite.quick_actions = quick_actions

        await self.db.commit()

        # Invalidate selector cache
        await self._invalidate_selector_cache(admin_id)

        return favorite

    async def remove_favorite(
        self,
        admin_id: UUID,
        hostel_id: UUID
    ) -> bool:
        """Remove hostel from favorites."""
        result = await self.selector_repo.remove_favorite(admin_id, hostel_id)
        
        if result:
            await self.db.commit()
            await self._invalidate_selector_cache(admin_id)

        return result

    async def get_favorites(
        self,
        admin_id: UUID,
        include_stats: bool = True
    ) -> List[FavoriteHostel]:
        """Get all favorites for admin with optional stats."""
        return await self.selector_repo.get_favorites(
            admin_id=admin_id,
            include_stats=include_stats
        )

    async def get_favorites_with_details(
        self,
        admin_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get favorites with complete details and stats."""
        favorites = await self.get_favorites(admin_id, include_stats=True)
        
        result = []
        for favorite in favorites:
            # Get current stats
            stats = await self.get_hostel_quick_stats(favorite.hostel_id)
            
            result.append({
                'favorite_id': str(favorite.id),
                'hostel_id': str(favorite.hostel_id),
                'hostel_name': favorite.hostel.name if favorite.hostel else None,
                'custom_label': favorite.custom_label,
                'color_code': favorite.color_code,
                'display_order': favorite.display_order,
                'quick_actions': favorite.quick_actions,
                'added_date': favorite.added_to_favorites,
                'days_in_favorites': favorite.days_in_favorites,
                'stats': {
                    'occupancy': float(stats.occupancy_percentage) if stats else 0,
                    'pending_tasks': stats.pending_tasks if stats else 0,
                    'urgent_alerts': stats.urgent_alerts if stats else 0,
                    'status': stats.status_indicator if stats else 'unknown',
                    'requires_attention': stats.requires_attention if stats else False
                }
            })

        return result

    async def update_favorite(
        self,
        favorite_id: UUID,
        updates: Dict[str, Any]
    ) -> FavoriteHostel:
        """Update favorite hostel settings."""
        favorite = await self.selector_repo.update_favorite(
            favorite_id=favorite_id,
            updates=updates
        )

        await self.db.commit()

        # Invalidate cache
        await self._invalidate_selector_cache(favorite.admin_id)

        return favorite

    async def reorder_favorites(
        self,
        admin_id: UUID,
        ordered_hostel_ids: List[UUID]
    ) -> List[FavoriteHostel]:
        """Reorder favorites based on provided sequence."""
        favorites = await self.selector_repo.reorder_favorites(
            admin_id=admin_id,
            ordered_hostel_ids=ordered_hostel_ids
        )

        await self.db.commit()
        await self._invalidate_selector_cache(admin_id)

        return favorites

    # ==================== QUICK STATS ====================

    async def get_hostel_quick_stats(
        self,
        hostel_id: UUID,
        refresh_if_stale: bool = True
    ) -> Optional[HostelQuickStats]:
        """Get quick stats for hostel with auto-refresh."""
        return await self.selector_repo.get_hostel_quick_stats(
            hostel_id=hostel_id,
            refresh_if_stale=refresh_if_stale
        )

    async def refresh_hostel_stats(
        self,
        hostel_id: UUID,
        stats_data: Optional[Dict[str, Any]] = None
    ) -> HostelQuickStats:
        """Refresh quick stats for hostel."""
        if not stats_data:
            # Fetch real-time stats
            stats_data = await self._fetch_real_time_stats(hostel_id)

        stats = await self.selector_repo.refresh_quick_stats(
            hostel_id=hostel_id,
            stats_data=stats_data
        )

        await self.db.commit()
        return stats

    async def _fetch_real_time_stats(self, hostel_id: UUID) -> Dict[str, Any]:
        """Fetch real-time statistics from various sources."""
        # This would aggregate data from:
        # - Student repository
        # - Room repository
        # - Booking repository
        # - Financial repository
        # - Complaint repository
        # etc.
        
        # Simplified placeholder
        return {
            'total_students': 0,
            'active_students': 0,
            'total_capacity': 0,
            'available_beds': 0,
            'occupancy_percentage': 0.0,
            'pending_tasks': 0,
            'urgent_alerts': 0,
            'pending_bookings': 0,
            'open_complaints': 0,
            'maintenance_requests': 0,
            'revenue_this_month': 0.0,
            'outstanding_payments': 0.0,
            'health_score': 75.0,
            'status_indicator': 'normal',
            'requires_attention': False
        }

    async def bulk_refresh_stats(
        self,
        hostel_ids: List[UUID]
    ) -> Dict[str, Any]:
        """Refresh stats for multiple hostels."""
        results = {
            'success': [],
            'failed': []
        }

        for hostel_id in hostel_ids:
            try:
                await self.refresh_hostel_stats(hostel_id)
                results['success'].append(str(hostel_id))
            except Exception as e:
                results['failed'].append({
                    'hostel_id': str(hostel_id),
                    'error': str(e)
                })

        return results

    # ==================== SELECTOR CACHE ====================

    async def get_selector_data(
        self,
        admin_id: UUID,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get complete selector data with caching."""
        # Get cache
        cache = await self.selector_repo.get_selector_cache(
            admin_id=admin_id,
            refresh_if_stale=not force_refresh
        )

        if force_refresh or not cache:
            cache = await self.rebuild_selector_cache(admin_id)

        # Convert to response format
        return {
            'admin_id': str(admin_id),
            'active_hostel_id': str(cache.active_hostel_id) if cache.active_hostel_id else None,
            'total_hostels': cache.total_hostels,
            'active_hostels': cache.active_hostels,
            'recent_hostels': cache.recent_hostel_ids,
            'favorite_hostels': cache.favorite_hostel_ids,
            'attention_required': cache.attention_required_ids,
            'summary': {
                'total_pending_tasks': cache.total_pending_tasks,
                'total_urgent_alerts': cache.total_urgent_alerts,
                'avg_occupancy': float(cache.avg_occupancy_percentage)
            },
            'hostels': cache.hostels_data,
            'cache_age_minutes': cache.cache_age_minutes,
            'is_stale': cache.is_stale
        }

    async def rebuild_selector_cache(
        self,
        admin_id: UUID
    ) -> HostelSelectorCache:
        """Rebuild complete selector cache for admin."""
        cache = await self.selector_repo.rebuild_selector_cache(admin_id)
        await self.db.commit()
        return cache

    async def _invalidate_selector_cache(self, admin_id: UUID) -> None:
        """Invalidate selector cache to force refresh."""
        await self.selector_repo.invalidate_selector_cache(admin_id)
        await self.db.commit()

    # ==================== SMART RECOMMENDATIONS ====================

    async def get_smart_selector_view(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Get intelligent selector view with prioritization."""
        # Get selector data
        selector_data = await self.get_selector_data(admin_id)

        # Get context recommendations
        from app.services.admin.hostel_context_service import HostelContextService
        context_service = HostelContextService(self.db)
        
        recommendations = await context_service.recommend_context_switch(admin_id)

        # Organize data intelligently
        return {
            'priority_hostels': self._prioritize_hostels(
                selector_data,
                recommendations
            ),
            'recent_hostels': selector_data['recent_hostels'][:5],
            'favorite_hostels': selector_data['favorite_hostels'],
            'all_hostels': selector_data['hostels'],
            'summary': selector_data['summary'],
            'alerts': {
                'requires_attention': len(selector_data['attention_required']),
                'urgent_alerts': selector_data['summary']['total_urgent_alerts'],
                'pending_tasks': selector_data['summary']['total_pending_tasks']
            }
        }

    def _prioritize_hostels(
        self,
        selector_data: Dict[str, Any],
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prioritize hostels based on urgency and recommendations."""
        priority_list = []

        # Add hostels requiring attention (highest priority)
        for hostel_id in selector_data['attention_required']:
            hostel_data = selector_data['hostels'].get(hostel_id)
            if hostel_data:
                priority_list.append({
                    'hostel_id': hostel_id,
                    'priority': 'critical',
                    'reason': 'requires_attention',
                    **hostel_data
                })

        # Add recommended hostels
        for rec in recommendations:
            if rec['priority'] == 'high':
                hostel_id = str(rec['hostel_id'])
                hostel_data = selector_data['hostels'].get(hostel_id)
                
                if hostel_data and hostel_id not in selector_data['attention_required']:
                    priority_list.append({
                        'hostel_id': hostel_id,
                        'priority': 'high',
                        'reason': 'recommended',
                        'recommendation_reasons': rec.get('reasons', []),
                        **hostel_data
                    })

        return priority_list[:5]  # Top 5 priority hostels

    # ==================== ANALYTICS ====================

    async def get_selector_analytics(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get hostel selector usage analytics."""
        return await self.selector_repo.get_selector_analytics(
            admin_id=admin_id,
            days=days
        )

    async def analyze_hostel_engagement(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Analyze admin's engagement with hostels."""
        analytics = await self.get_selector_analytics(admin_id, days)
        
        # Get assignments
        assignments = await self.assignment_repo.get_admin_assignments(admin_id)
        
        # Calculate engagement metrics
        total_hostels = len(assignments)
        accessed_hostels = analytics['unique_hostels_accessed']
        
        engagement_rate = (
            (accessed_hostels / total_hostels * 100)
            if total_hostels > 0 else 0
        )

        return {
            'admin_id': str(admin_id),
            'period_days': days,
            'total_assigned_hostels': total_hostels,
            'accessed_hostels': accessed_hostels,
            'engagement_rate': round(engagement_rate, 2),
            'most_accessed': analytics['most_accessed_hostels'],
            'favorites_count': analytics['total_favorites'],
            'engagement_level': self._classify_engagement(engagement_rate),
            'recommendations': self._generate_engagement_recommendations(
                engagement_rate,
                total_hostels,
                accessed_hostels
            )
        }

    def _classify_engagement(self, engagement_rate: float) -> str:
        """Classify engagement level."""
        if engagement_rate >= 90:
            return 'excellent'
        elif engagement_rate >= 70:
            return 'good'
        elif engagement_rate >= 50:
            return 'moderate'
        else:
            return 'low'

    def _generate_engagement_recommendations(
        self,
        engagement_rate: float,
        total_hostels: int,
        accessed_hostels: int
    ) -> List[Dict[str, Any]]:
        """Generate engagement improvement recommendations."""
        recommendations = []

        if engagement_rate < 50:
            recommendations.append({
                'type': 'increase_engagement',
                'message': f'Only {accessed_hostels} of {total_hostels} hostels accessed. '
                          f'Consider reviewing unvisited hostels.',
                'priority': 'high'
            })

        if total_hostels > 5 and accessed_hostels < 3:
            recommendations.append({
                'type': 'workload_review',
                'message': 'Managing many hostels but accessing few. '
                          'Consider workload rebalancing.',
                'priority': 'medium'
            })

        return recommendations

    # ==================== MAINTENANCE ====================

    async def cleanup_recent_entries(self, admin_id: UUID) -> int:
        """Cleanup old recent entries for admin."""
        count = await self.selector_repo.cleanup_old_recent_entries(
            admin_id=admin_id,
            keep_count=self.max_recent_entries
        )

        if count > 0:
            await self.db.commit()

        return count

    async def decay_access_counts(self) -> int:
        """Decay access counts for time-based accuracy."""
        count = await self.selector_repo.decay_access_counts()
        
        if count > 0:
            await self.db.commit()

        return count

    async def refresh_all_stats(
        self,
        max_age_minutes: int = 10
    ) -> Dict[str, Any]:
        """Refresh stats for all hostels that are stale."""
        from sqlalchemy import select
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        
        stmt = (
            select(HostelQuickStats)
            .where(HostelQuickStats.last_updated < cutoff)
        )
        
        result = await self.db.execute(stmt)
        stale_stats = result.scalars().all()

        hostel_ids = [s.hostel_id for s in stale_stats]
        
        return await self.bulk_refresh_stats(hostel_ids)