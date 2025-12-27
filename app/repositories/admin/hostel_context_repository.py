"""
Hostel Context Repository

Manages hostel context switching and session tracking for multi-hostel admins.
Provides session management, context history, and performance optimization.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.admin.hostel_context import (
    HostelContext,
    ContextSwitch,
    ContextPreference,
    ContextSnapshot
)
from app.models.admin.admin_user import AdminUser
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import (
    EntityNotFoundError,
    ValidationError,
    ConflictError
)


class HostelContextRepository(BaseRepository[HostelContext]):
    """
    Context switching management with:
    - Active context tracking
    - Session duration monitoring
    - Quick stats caching
    - Context preferences
    - Switch history and analytics
    """

    def __init__(self, db: Session):
        super().__init__(HostelContext, db)

    # ==================== CONTEXT MANAGEMENT ====================

    async def get_active_context(
        self,
        admin_id: UUID,
        include_preferences: bool = False
    ) -> Optional[HostelContext]:
        """Get admin's current active context."""
        stmt = (
            select(HostelContext)
            .where(HostelContext.admin_id == admin_id)
            .where(HostelContext.is_active == True)
            .options(
                selectinload(HostelContext.active_hostel),
                selectinload(HostelContext.previous_hostel)
            )
        )

        if include_preferences:
            stmt = stmt.options(selectinload(HostelContext.preferences))

        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def set_active_context(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        device_info: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ) -> HostelContext:
        """
        Set or switch active context for admin.
        
        Args:
            admin_id: Admin user ID
            hostel_id: Hostel to make active
            device_info: Device information
            ip_address: Client IP address
            
        Returns:
            Active HostelContext
        """
        # Validate admin and hostel
        admin = await self.db.get(AdminUser, admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        hostel = await self.db.get(Hostel, hostel_id)
        if not hostel:
            raise EntityNotFoundError(f"Hostel {hostel_id} not found")

        # Get current active context
        current_context = await self.get_active_context(admin_id)

        # If switching to different hostel, record switch
        if current_context and current_context.active_hostel_id != hostel_id:
            await self._record_context_switch(
                admin_id=admin_id,
                from_hostel_id=current_context.active_hostel_id,
                to_hostel_id=hostel_id,
                context_id=current_context.id,
                device_info=device_info,
                ip_address=ip_address
            )

            # Update current context
            current_context.previous_hostel_id = current_context.active_hostel_id
            current_context.active_hostel_id = hostel_id
            current_context.switch_count += 1
            current_context.last_accessed_at = datetime.utcnow()

            # Reset session duration for new context
            current_context.context_started_at = datetime.utcnow()

            await self.db.flush()
            return current_context

        # If no context exists, create new one
        if not current_context:
            context = HostelContext(
                admin_id=admin_id,
                active_hostel_id=hostel_id,
                context_started_at=datetime.utcnow(),
                last_accessed_at=datetime.utcnow(),
                is_active=True,
                device_type=device_info.get('type') if device_info else None,
                device_info=device_info,
                ip_address=ip_address
            )

            self.db.add(context)
            await self.db.flush()

            # Initialize quick stats
            await self.refresh_context_stats(context.id)

            return context

        # Same hostel, just update activity
        await self.update_activity(current_context.id)
        return current_context

    async def end_context(
        self,
        admin_id: UUID,
        reason: str = 'logout'
    ) -> Optional[HostelContext]:
        """End active context session."""
        context = await self.get_active_context(admin_id)
        if not context:
            return None

        context.is_active = False
        
        # Update final session duration
        duration_delta = datetime.utcnow() - context.last_accessed_at
        context.session_duration_minutes += int(duration_delta.total_seconds() / 60)

        await self.db.flush()
        return context

    async def update_activity(
        self,
        context_id: UUID,
        actions_performed: int = 0,
        decisions_made: int = 0
    ) -> HostelContext:
        """Update context activity metrics."""
        context = await self.find_by_id(context_id)
        if not context:
            raise EntityNotFoundError(f"Context {context_id} not found")

        # Update timestamp and duration
        now = datetime.utcnow()
        duration_delta = now - context.last_accessed_at
        context.session_duration_minutes += int(duration_delta.total_seconds() / 60)
        context.last_accessed_at = now

        # Update activity counters
        context.actions_performed += actions_performed
        context.decisions_made += decisions_made

        # Reset expiration
        if context.expires_at:
            context.expires_at = now + timedelta(hours=8)

        await self.db.flush()
        return context

    # ==================== CONTEXT STATISTICS ====================

    async def refresh_context_stats(
        self,
        context_id: UUID,
        stats_data: Optional[Dict[str, Any]] = None
    ) -> HostelContext:
        """
        Refresh cached statistics for context.
        
        Args:
            context_id: Context ID
            stats_data: Optional pre-calculated stats
            
        Returns:
            Updated context with fresh stats
        """
        context = await self.find_by_id(context_id)
        if not context:
            raise EntityNotFoundError(f"Context {context_id} not found")

        if stats_data:
            # Use provided stats
            context.total_students = stats_data.get('total_students', 0)
            context.active_students = stats_data.get('active_students', 0)
            context.occupancy_percentage = Decimal(str(stats_data.get('occupancy_percentage', 0)))
            context.pending_tasks = stats_data.get('pending_tasks', 0)
            context.urgent_alerts = stats_data.get('urgent_alerts', 0)
            context.unread_notifications = stats_data.get('unread_notifications', 0)
            context.revenue_this_month = Decimal(str(stats_data.get('revenue_this_month', 0)))
            context.outstanding_payments = Decimal(str(stats_data.get('outstanding_payments', 0)))
        else:
            # Calculate stats from database
            # This would typically call other repositories to get real data
            # Simplified here for demonstration
            context.total_students = 0
            context.active_students = 0
            context.occupancy_percentage = Decimal('0.00')
            context.pending_tasks = 0
            context.urgent_alerts = 0
            context.unread_notifications = 0
            context.revenue_this_month = Decimal('0.00')
            context.outstanding_payments = Decimal('0.00')

        context.stats_last_updated = datetime.utcnow()
        await self.db.flush()
        return context

    async def get_context_with_stats(
        self,
        admin_id: UUID,
        refresh_if_stale: bool = True,
        stale_threshold_minutes: int = 5
    ) -> Optional[HostelContext]:
        """Get context with stats, refreshing if stale."""
        context = await self.get_active_context(admin_id)
        if not context:
            return None

        # Check if stats are stale
        if refresh_if_stale and context.stats_last_updated:
            age = datetime.utcnow() - context.stats_last_updated
            if age.total_seconds() / 60 > stale_threshold_minutes:
                await self.refresh_context_stats(context.id)
                # Reload context to get fresh data
                context = await self.find_by_id(context.id)

        return context

    # ==================== CONTEXT SWITCHING ====================

    async def _record_context_switch(
        self,
        admin_id: UUID,
        from_hostel_id: UUID,
        to_hostel_id: UUID,
        context_id: UUID,
        device_info: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        reason: Optional[str] = None,
        triggered_by: str = 'manual'
    ) -> ContextSwitch:
        """Record context switch event."""
        # Get current context to capture session metrics
        context = await self.find_by_id(context_id)
        
        session_duration = None
        if context:
            session_duration = (
                datetime.utcnow() - context.context_started_at
            ).total_seconds() / 60

        switch = ContextSwitch(
            context_id=context_id,
            admin_id=admin_id,
            from_hostel_id=from_hostel_id,
            to_hostel_id=to_hostel_id,
            switched_at=datetime.utcnow(),
            session_duration_minutes=int(session_duration) if session_duration else None,
            switch_reason=reason,
            triggered_by=triggered_by,
            actions_performed=context.actions_performed if context else 0,
            decisions_made=context.decisions_made if context else 0,
            device_type=device_info.get('type') if device_info else None,
            ip_address=ip_address
        )

        self.db.add(switch)
        await self.db.flush()

        # Create snapshot if significant switch
        if context and (context.actions_performed > 0 or context.decisions_made > 0):
            await self._create_context_snapshot(switch.id, context)

        return switch

    async def get_switch_history(
        self,
        admin_id: UUID,
        limit: int = 50,
        include_snapshots: bool = False
    ) -> List[ContextSwitch]:
        """Get context switch history for admin."""
        stmt = (
            select(ContextSwitch)
            .where(ContextSwitch.admin_id == admin_id)
            .options(
                selectinload(ContextSwitch.from_hostel),
                selectinload(ContextSwitch.to_hostel)
            )
            .order_by(desc(ContextSwitch.switched_at))
            .limit(limit)
        )

        if include_snapshots:
            stmt = stmt.options(selectinload(ContextSwitch.snapshot))

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def get_switch_analytics(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get context switching analytics."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Total switches
        total_stmt = (
            select(func.count(ContextSwitch.id))
            .where(ContextSwitch.admin_id == admin_id)
            .where(ContextSwitch.switched_at >= cutoff)
        )
        total_switches = await self.db.scalar(total_stmt) or 0

        # Most switched-to hostels
        popular_stmt = (
            select(
                ContextSwitch.to_hostel_id,
                Hostel.name,
                func.count(ContextSwitch.id).label('switch_count')
            )
            .join(Hostel, ContextSwitch.to_hostel_id == Hostel.id)
            .where(ContextSwitch.admin_id == admin_id)
            .where(ContextSwitch.switched_at >= cutoff)
            .group_by(ContextSwitch.to_hostel_id, Hostel.name)
            .order_by(desc('switch_count'))
            .limit(5)
        )
        popular_result = await self.db.execute(popular_stmt)
        most_visited = [
            {'hostel_id': row[0], 'hostel_name': row[1], 'switch_count': row[2]}
            for row in popular_result
        ]

        # Average session duration
        avg_duration_stmt = (
            select(func.avg(ContextSwitch.session_duration_minutes))
            .where(ContextSwitch.admin_id == admin_id)
            .where(ContextSwitch.switched_at >= cutoff)
            .where(ContextSwitch.session_duration_minutes.isnot(None))
        )
        avg_duration = await self.db.scalar(avg_duration_stmt) or 0

        # Switches by trigger type
        by_trigger_stmt = (
            select(
                ContextSwitch.triggered_by,
                func.count(ContextSwitch.id).label('count')
            )
            .where(ContextSwitch.admin_id == admin_id)
            .where(ContextSwitch.switched_at >= cutoff)
            .group_by(ContextSwitch.triggered_by)
        )
        trigger_result = await self.db.execute(by_trigger_stmt)
        by_trigger = {row[0]: row[1] for row in trigger_result}

        return {
            'period_days': days,
            'total_switches': total_switches,
            'avg_switches_per_day': round(total_switches / days, 2),
            'avg_session_duration_minutes': round(float(avg_duration), 2),
            'most_visited_hostels': most_visited,
            'switches_by_trigger': by_trigger
        }

    # ==================== CONTEXT PREFERENCES ====================

    async def get_context_preferences(
        self,
        context_id: UUID,
        create_if_missing: bool = True
    ) -> Optional[ContextPreference]:
        """Get preferences for context."""
        stmt = (
            select(ContextPreference)
            .where(ContextPreference.context_id == context_id)
        )

        result = await self.db.execute(stmt)
        preferences = result.scalar_one_or_none()

        if not preferences and create_if_missing:
            preferences = ContextPreference(
                context_id=context_id,
                dashboard_layout='default',
                default_view='dashboard',
                records_per_page=25,
                auto_refresh_enabled=True,
                auto_refresh_interval_seconds=300
            )
            self.db.add(preferences)
            await self.db.flush()

        return preferences

    async def update_context_preferences(
        self,
        context_id: UUID,
        preferences_data: Dict[str, Any]
    ) -> ContextPreference:
        """Update context preferences."""
        preferences = await self.get_context_preferences(context_id)
        if not preferences:
            raise EntityNotFoundError(f"Preferences for context {context_id} not found")

        # Update preference fields
        for key, value in preferences_data.items():
            if hasattr(preferences, key):
                setattr(preferences, key, value)

        await self.db.flush()
        return preferences

    async def save_ui_state(
        self,
        context_id: UUID,
        ui_state: Dict[str, Any]
    ) -> HostelContext:
        """Save UI state for session restoration."""
        context = await self.find_by_id(context_id)
        if not context:
            raise EntityNotFoundError(f"Context {context_id} not found")

        context.ui_state = ui_state
        await self.db.flush()
        return context

    # ==================== CONTEXT SNAPSHOTS ====================

    async def _create_context_snapshot(
        self,
        switch_id: UUID,
        context: HostelContext
    ) -> ContextSnapshot:
        """Create snapshot of context state at switch."""
        snapshot = ContextSnapshot(
            switch_id=switch_id,
            snapshot_timestamp=datetime.utcnow(),
            hostel_state={
                'total_students': context.total_students,
                'active_students': context.active_students,
                'occupancy_percentage': float(context.occupancy_percentage),
                'revenue_this_month': float(context.revenue_this_month),
                'outstanding_payments': float(context.outstanding_payments)
            },
            stats_snapshot={
                'pending_tasks': context.pending_tasks,
                'urgent_alerts': context.urgent_alerts,
                'unread_notifications': context.unread_notifications,
                'actions_performed': context.actions_performed,
                'decisions_made': context.decisions_made
            },
            ui_state=context.ui_state,
            snapshot_version='1.0'
        )

        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def get_context_snapshot(
        self,
        switch_id: UUID
    ) -> Optional[ContextSnapshot]:
        """Get snapshot for specific switch."""
        stmt = (
            select(ContextSnapshot)
            .where(ContextSnapshot.switch_id == switch_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ==================== CONTEXT CLEANUP ====================

    async def cleanup_stale_contexts(
        self,
        inactive_hours: int = 24
    ) -> int:
        """Clean up stale inactive contexts."""
        cutoff = datetime.utcnow() - timedelta(hours=inactive_hours)

        stmt = (
            select(HostelContext)
            .where(HostelContext.is_active == True)
            .where(HostelContext.last_accessed_at < cutoff)
        )

        result = await self.db.execute(stmt)
        stale_contexts = result.scalars().all()

        for context in stale_contexts:
            context.is_active = False

        await self.db.flush()
        return len(stale_contexts)

    async def cleanup_old_snapshots(
        self,
        retention_days: int = 90
    ) -> int:
        """Delete old context snapshots."""
        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        stmt = (
            select(ContextSnapshot)
            .where(ContextSnapshot.snapshot_timestamp < cutoff)
        )

        result = await self.db.execute(stmt)
        old_snapshots = result.scalars().all()

        for snapshot in old_snapshots:
            await self.db.delete(snapshot)

        await self.db.flush()
        return len(old_snapshots)

    # ==================== CONTEXT RECOMMENDATIONS ====================

    async def recommend_context_switch(
        self,
        admin_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Recommend hostel context switches based on:
        - Urgent alerts
        - Pending tasks
        - Recent activity
        - Access patterns
        """
        # Get admin's active assignments
        from app.repositories.admin.admin_hostel_assignment_repository import (
            AdminHostelAssignmentRepository
        )
        
        assignment_repo = AdminHostelAssignmentRepository(self.db)
        assignments = await assignment_repo.get_admin_assignments(admin_id)

        recommendations = []

        for assignment in assignments:
            # Calculate recommendation score
            score = 0
            reasons = []

            # Check for urgent items (would need to query actual data)
            # Simplified for demonstration
            urgent_count = 0  # Placeholder
            pending_count = 0  # Placeholder

            if urgent_count > 0:
                score += urgent_count * 10
                reasons.append(f"{urgent_count} urgent alerts")

            if pending_count > 5:
                score += pending_count * 2
                reasons.append(f"{pending_count} pending tasks")

            # Recent access pattern
            recent_switches = await self._get_recent_switches_to_hostel(
                admin_id,
                assignment.hostel_id,
                hours=24
            )
            
            if recent_switches == 0:
                score += 5
                reasons.append("Not accessed today")

            if score > 0:
                recommendations.append({
                    'hostel_id': assignment.hostel_id,
                    'hostel_name': assignment.hostel.name if assignment.hostel else None,
                    'recommendation_score': score,
                    'reasons': reasons,
                    'priority': 'high' if score >= 20 else 'medium' if score >= 10 else 'low'
                })

        # Sort by score
        recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        return recommendations[:5]  # Top 5 recommendations

    async def _get_recent_switches_to_hostel(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        hours: int = 24
    ) -> int:
        """Count recent switches to specific hostel."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        stmt = (
            select(func.count(ContextSwitch.id))
            .where(ContextSwitch.admin_id == admin_id)
            .where(ContextSwitch.to_hostel_id == hostel_id)
            .where(ContextSwitch.switched_at >= cutoff)
        )

        return await self.db.scalar(stmt) or 0