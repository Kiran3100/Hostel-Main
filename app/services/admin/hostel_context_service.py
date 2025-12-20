"""
Hostel Context Service

Business logic for managing hostel context switching and session
tracking for multi-hostel admins.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.admin.hostel_context import (
    HostelContext,
    ContextSwitch,
    ContextPreference
)
from app.repositories.admin.hostel_context_repository import HostelContextRepository
from app.repositories.admin.admin_hostel_assignment_repository import (
    AdminHostelAssignmentRepository
)
from app.core.exceptions import (
    ValidationError,
    EntityNotFoundError,
    BusinessRuleViolationError
)


class HostelContextService:
    """
    Context management service with:
    - Context switching with validation
    - Session tracking and metrics
    - Quick stats management
    - Context recommendations
    - Preference management
    """

    def __init__(self, db: Session):
        self.db = db
        self.context_repo = HostelContextRepository(db)
        self.assignment_repo = AdminHostelAssignmentRepository(db)

        # Configuration
        self.context_expiry_hours = 8
        self.stats_refresh_interval_minutes = 5

    # ==================== CONTEXT MANAGEMENT ====================

    async def get_active_context(
        self,
        admin_id: UUID,
        refresh_stats: bool = True
    ) -> Optional[HostelContext]:
        """Get admin's current active context."""
        context = await self.context_repo.get_active_context(
            admin_id,
            include_preferences=True
        )

        if context and refresh_stats:
            # Refresh if stale
            if not context.stats_are_fresh:
                await self.refresh_context_stats(context.id)
                # Reload
                context = await self.context_repo.find_by_id(context.id)

        return context

    async def switch_context(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        device_info: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        switch_reason: Optional[str] = None
    ) -> HostelContext:
        """
        Switch admin's active context to different hostel.
        
        Validates assignment and tracks switch.
        """
        # Validate assignment exists
        assignment = await self.assignment_repo.find_assignment(admin_id, hostel_id)
        if not assignment:
            raise ValidationError(
                f"Admin {admin_id} not assigned to hostel {hostel_id}"
            )

        if not assignment.is_active:
            raise ValidationError(
                f"Assignment to hostel {hostel_id} is not active"
            )

        # Set active context (handles switch tracking internally)
        context = await self.context_repo.set_active_context(
            admin_id=admin_id,
            hostel_id=hostel_id,
            device_info=device_info,
            ip_address=ip_address
        )

        # Refresh stats for new context
        await self.refresh_context_stats(context.id)

        await self.db.commit()
        return context

    async def end_context(
        self,
        admin_id: UUID,
        reason: str = 'logout'
    ) -> Optional[HostelContext]:
        """End active context session."""
        context = await self.context_repo.end_context(admin_id, reason)
        
        if context:
            await self.db.commit()
        
        return context

    async def update_context_activity(
        self,
        context_id: UUID,
        actions_performed: int = 0,
        decisions_made: int = 0
    ) -> HostelContext:
        """Update context activity metrics."""
        context = await self.context_repo.update_activity(
            context_id=context_id,
            actions_performed=actions_performed,
            decisions_made=decisions_made
        )

        await self.db.commit()
        return context

    # ==================== STATS MANAGEMENT ====================

    async def refresh_context_stats(
        self,
        context_id: UUID,
        force: bool = False
    ) -> HostelContext:
        """Refresh cached statistics for context."""
        context = await self.context_repo.find_by_id(context_id)
        if not context:
            raise EntityNotFoundError(f"Context {context_id} not found")

        # Check if refresh needed
        if not force and context.stats_are_fresh:
            return context

        # Get real-time stats from hostel
        stats = await self._fetch_hostel_stats(context.active_hostel_id)

        # Update context stats
        context = await self.context_repo.refresh_context_stats(
            context_id=context_id,
            stats_data=stats
        )

        await self.db.commit()
        return context

    async def _fetch_hostel_stats(self, hostel_id: UUID) -> Dict[str, Any]:
        """Fetch real-time statistics for hostel."""
        # This would aggregate data from various sources
        # For now, simplified placeholder
        
        return {
            'total_students': 0,
            'active_students': 0,
            'occupancy_percentage': 0.0,
            'pending_tasks': 0,
            'urgent_alerts': 0,
            'unread_notifications': 0,
            'revenue_this_month': 0.0,
            'outstanding_payments': 0.0
        }

    async def get_context_with_fresh_stats(
        self,
        admin_id: UUID
    ) -> Optional[HostelContext]:
        """Get context ensuring fresh statistics."""
        return await self.context_repo.get_context_with_stats(
            admin_id=admin_id,
            refresh_if_stale=True,
            stale_threshold_minutes=self.stats_refresh_interval_minutes
        )

    # ==================== SWITCH TRACKING ====================

    async def get_switch_history(
        self,
        admin_id: UUID,
        limit: int = 50,
        include_snapshots: bool = False
    ) -> List[ContextSwitch]:
        """Get context switch history for admin."""
        return await self.context_repo.get_switch_history(
            admin_id=admin_id,
            limit=limit,
            include_snapshots=include_snapshots
        )

    async def get_switch_analytics(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get context switching analytics."""
        return await self.context_repo.get_switch_analytics(
            admin_id=admin_id,
            days=days
        )

    async def analyze_switch_patterns(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Analyze context switch patterns for insights."""
        analytics = await self.get_switch_analytics(admin_id, days)
        
        # Enhance with pattern analysis
        patterns = {
            'total_switches': analytics['total_switches'],
            'avg_switches_per_day': analytics['avg_switches_per_day'],
            'most_visited': analytics['most_visited_hostels'],
            'switch_velocity': self._calculate_switch_velocity(analytics),
            'context_stability': self._calculate_context_stability(analytics),
            'recommendations': []
        }

        # Generate recommendations
        if patterns['avg_switches_per_day'] > 10:
            patterns['recommendations'].append({
                'type': 'reduce_switching',
                'message': 'High switch frequency detected. Consider consolidating work.',
                'priority': 'medium'
            })

        if patterns['context_stability'] < 50:
            patterns['recommendations'].append({
                'type': 'improve_stability',
                'message': 'Context switches are very frequent. Focus time may improve productivity.',
                'priority': 'high'
            })

        return patterns

    def _calculate_switch_velocity(self, analytics: Dict[str, Any]) -> str:
        """Calculate switch velocity classification."""
        avg_per_day = analytics['avg_switches_per_day']
        
        if avg_per_day > 15:
            return 'very_high'
        elif avg_per_day > 10:
            return 'high'
        elif avg_per_day > 5:
            return 'moderate'
        else:
            return 'low'

    def _calculate_context_stability(self, analytics: Dict[str, Any]) -> float:
        """Calculate context stability score (0-100)."""
        avg_session = analytics.get('avg_session_duration_minutes', 0)
        
        # Ideal session: 30-60 minutes
        if 30 <= avg_session <= 60:
            return 100.0
        elif avg_session < 30:
            return (avg_session / 30) * 100
        else:
            # Penalize very long sessions
            return max(100 - ((avg_session - 60) / 60) * 10, 50)

    # ==================== PREFERENCES ====================

    async def get_context_preferences(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> Optional[ContextPreference]:
        """Get preferences for admin's context."""
        context = await self.get_active_context(admin_id, refresh_stats=False)
        
        if not context:
            return None

        return await self.context_repo.get_context_preferences(
            context_id=context.id,
            create_if_missing=True
        )

    async def update_preferences(
        self,
        admin_id: UUID,
        preferences: Dict[str, Any]
    ) -> ContextPreference:
        """Update context preferences."""
        context = await self.get_active_context(admin_id, refresh_stats=False)
        
        if not context:
            raise ValidationError("No active context found")

        updated_prefs = await self.context_repo.update_context_preferences(
            context_id=context.id,
            preferences_data=preferences
        )

        await self.db.commit()
        return updated_prefs

    async def save_ui_state(
        self,
        admin_id: UUID,
        ui_state: Dict[str, Any]
    ) -> HostelContext:
        """Save UI state for session restoration."""
        context = await self.get_active_context(admin_id, refresh_stats=False)
        
        if not context:
            raise ValidationError("No active context found")

        updated_context = await self.context_repo.save_ui_state(
            context_id=context.id,
            ui_state=ui_state
        )

        await self.db.commit()
        return updated_context

    # ==================== RECOMMENDATIONS ====================

    async def recommend_context_switch(
        self,
        admin_id: UUID
    ) -> List[Dict[str, Any]]:
        """Recommend hostel context switches based on urgency."""
        return await self.context_repo.recommend_context_switch(admin_id)

    async def get_smart_suggestions(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Get smart context suggestions based on patterns and urgency."""
        # Get recommendations
        recommendations = await self.recommend_context_switch(admin_id)

        # Get switch history
        history = await self.get_switch_history(admin_id, limit=10)

        # Analyze patterns
        if history:
            last_switches = history[:5]
            recent_hostels = {s.to_hostel_id for s in last_switches}
            
            # Filter out recently visited
            fresh_recommendations = [
                r for r in recommendations
                if r['hostel_id'] not in recent_hostels
            ]
        else:
            fresh_recommendations = recommendations

        return {
            'urgent_recommendations': [
                r for r in fresh_recommendations
                if r.get('priority') == 'high'
            ],
            'suggested_recommendations': fresh_recommendations[:5],
            'recently_visited': [
                {
                    'hostel_id': str(s.to_hostel_id),
                    'switched_at': s.switched_at,
                    'session_duration': s.session_duration_minutes
                }
                for s in history[:5]
            ]
        }

    # ==================== CLEANUP ====================

    async def cleanup_stale_contexts(
        self,
        inactive_hours: int = 24
    ) -> int:
        """Clean up stale inactive contexts."""
        count = await self.context_repo.cleanup_stale_contexts(inactive_hours)
        
        if count > 0:
            await self.db.commit()
        
        return count

    async def cleanup_old_snapshots(
        self,
        retention_days: int = 90
    ) -> int:
        """Delete old context snapshots."""
        count = await self.context_repo.cleanup_old_snapshots(retention_days)
        
        if count > 0:
            await self.db.commit()
        
        return count

    # ==================== ANALYTICS ====================

    async def get_context_usage_report(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Generate context usage report for admin."""
        # Get switch analytics
        switch_analytics = await self.get_switch_analytics(admin_id, days)

        # Get pattern analysis
        patterns = await self.analyze_switch_patterns(admin_id, days)

        # Get all contexts in period
        switches = await self.get_switch_history(admin_id, limit=1000)
        recent_switches = [
            s for s in switches
            if s.switched_at >= datetime.utcnow() - timedelta(days=days)
        ]

        # Calculate productivity metrics
        productive_sessions = [
            s for s in recent_switches
            if s.was_productive
        ]

        return {
            'admin_id': str(admin_id),
            'period_days': days,
            'switch_analytics': switch_analytics,
            'patterns': patterns,
            'productivity': {
                'total_sessions': len(recent_switches),
                'productive_sessions': len(productive_sessions),
                'productivity_rate': (
                    len(productive_sessions) / len(recent_switches) * 100
                    if recent_switches else 0
                ),
                'avg_productivity_score': (
                    sum(s.productivity_score for s in recent_switches) / len(recent_switches)
                    if recent_switches else 0
                )
            },
            'recommendations': patterns.get('recommendations', [])
        }