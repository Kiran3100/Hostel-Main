"""
Multi-Hostel Dashboard Repository

Manages aggregated dashboard data, cross-hostel analytics,
performance comparisons, and portfolio-wide insights.
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.admin.multi_hostel_dashboard import (
    MultiHostelDashboard,
    CrossHostelMetric,
    HostelPerformanceRanking,
    DashboardWidget,
    DashboardSnapshot
)
from app.models.admin.admin_user import AdminUser
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import (
    EntityNotFoundError,
    ValidationError
)


class MultiHostelDashboardRepository(BaseRepository[MultiHostelDashboard]):
    """
    Multi-hostel dashboard management with:
    - Aggregated metrics across hostels
    - Cross-hostel comparisons
    - Performance rankings
    - Customizable widgets
    - Historical snapshots
    """

    def __init__(self, db: Session):
        super().__init__(MultiHostelDashboard, db)

    # ==================== DASHBOARD MANAGEMENT ====================

    async def get_dashboard(
        self,
        admin_id: UUID,
        dashboard_date: Optional[date] = None,
        refresh_if_stale: bool = True
    ) -> Optional[MultiHostelDashboard]:
        """Get dashboard for admin and date."""
        if not dashboard_date:
            dashboard_date = date.today()

        stmt = (
            select(MultiHostelDashboard)
            .where(MultiHostelDashboard.admin_id == admin_id)
            .where(MultiHostelDashboard.dashboard_date == dashboard_date)
            .options(
                selectinload(MultiHostelDashboard.cross_hostel_metrics),
                selectinload(MultiHostelDashboard.performance_rankings)
            )
        )

        result = await self.db.execute(stmt)
        dashboard = result.unique().scalar_one_or_none()

        if dashboard and refresh_if_stale and dashboard.is_stale:
            await self.refresh_dashboard(admin_id, dashboard_date)
            # Reload
            result = await self.db.execute(stmt)
            dashboard = result.unique().scalar_one_or_none()

        return dashboard

    async def refresh_dashboard(
        self,
        admin_id: UUID,
        dashboard_date: Optional[date] = None,
        force: bool = False
    ) -> MultiHostelDashboard:
        """
        Refresh dashboard with latest data.
        
        Args:
            admin_id: Admin user ID
            dashboard_date: Dashboard date (default: today)
            force: Force refresh even if not stale
            
        Returns:
            Refreshed dashboard
        """
        start_time = datetime.utcnow()
        
        if not dashboard_date:
            dashboard_date = date.today()

        # Get or create dashboard
        dashboard = await self.get_dashboard(
            admin_id,
            dashboard_date,
            refresh_if_stale=False
        )

        if not dashboard:
            dashboard = MultiHostelDashboard(
                admin_id=admin_id,
                dashboard_date=dashboard_date,
                period_start=dashboard_date.replace(day=1),  # First of month
                period_end=dashboard_date
            )
            self.db.add(dashboard)
            await self.db.flush()

        # Skip refresh if not stale and not forced
        if not force and not dashboard.is_stale:
            return dashboard

        # Get admin's hostels
        from app.repositories.admin.admin_hostel_assignment_repository import (
            AdminHostelAssignmentRepository
        )
        
        assignment_repo = AdminHostelAssignmentRepository(self.db)
        assignments = await assignment_repo.get_admin_assignments(admin_id)

        # Update portfolio statistics
        dashboard.total_hostels = len(assignments)
        dashboard.active_hostels = len([a for a in assignments if a.is_active])

        # Aggregate student statistics
        total_students = 0
        active_students = 0
        total_capacity = 0
        occupancy_list = []

        # Workload statistics
        total_pending = 0
        total_alerts = 0
        total_complaints = 0
        tasks_today = 0

        # Financial statistics
        total_revenue = Decimal('0.00')
        total_outstanding = Decimal('0.00')
        collection_rates = []

        # Performance tracking
        best_performer = None
        best_score = Decimal('0.00')
        worst_performer = None
        worst_score = Decimal('100.00')

        # Aggregate data from each hostel
        from app.repositories.admin.hostel_selector_repository import (
            HostelSelectorRepository
        )
        
        selector_repo = HostelSelectorRepository(self.db)

        for assignment in assignments:
            stats = await selector_repo.get_hostel_quick_stats(
                assignment.hostel_id,
                refresh_if_stale=True
            )

            if stats:
                total_students += stats.total_students
                active_students += stats.active_students
                total_capacity += stats.total_capacity
                occupancy_list.append(stats.occupancy_percentage)

                total_pending += stats.pending_tasks
                total_alerts += stats.urgent_alerts
                total_complaints += stats.open_complaints

                total_revenue += stats.revenue_this_month
                total_outstanding += stats.outstanding_payments
                if stats.collection_rate:
                    collection_rates.append(stats.collection_rate)

                # Track best/worst performers
                if stats.health_score > best_score:
                    best_score = stats.health_score
                    best_performer = assignment.hostel_id

                if stats.health_score < worst_score:
                    worst_score = stats.health_score
                    worst_performer = assignment.hostel_id

        # Update dashboard aggregates
        dashboard.total_students = total_students
        dashboard.active_students = active_students
        dashboard.total_capacity = total_capacity

        # Calculate occupancy metrics
        if occupancy_list:
            dashboard.avg_occupancy_percentage = sum(occupancy_list) / len(occupancy_list)
            dashboard.highest_occupancy_percentage = max(occupancy_list)
            dashboard.lowest_occupancy_percentage = min(occupancy_list)
        else:
            dashboard.avg_occupancy_percentage = Decimal('0.00')
            dashboard.highest_occupancy_percentage = Decimal('0.00')
            dashboard.lowest_occupancy_percentage = Decimal('0.00')

        # Update workload
        dashboard.total_pending_tasks = total_pending
        dashboard.total_urgent_alerts = total_alerts
        dashboard.total_open_complaints = total_complaints
        dashboard.tasks_completed_today = tasks_today

        # Update financials
        dashboard.total_revenue_this_month = total_revenue
        dashboard.total_outstanding_payments = total_outstanding
        if collection_rates:
            dashboard.avg_collection_rate = sum(collection_rates) / len(collection_rates)
        else:
            dashboard.avg_collection_rate = Decimal('0.00')

        # Calculate portfolio health
        dashboard.portfolio_health_score = self._calculate_portfolio_health(
            dashboard
        )

        # Determine attention level
        dashboard.attention_level = self._determine_attention_level(dashboard)
        dashboard.hostels_requiring_attention = len([
            s for s in occupancy_list if s < Decimal('50.00')
        ])

        # Set top/bottom performers
        dashboard.top_performer_hostel_id = best_performer
        dashboard.top_performer_score = best_score
        dashboard.bottom_performer_hostel_id = worst_performer
        dashboard.bottom_performer_score = worst_score

        # Update metadata
        dashboard.last_updated = datetime.utcnow()
        dashboard.build_duration_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )

        await self.db.flush()

        # Refresh cross-hostel metrics
        await self._refresh_cross_hostel_metrics(dashboard.id, assignments)

        # Refresh performance rankings
        await self._refresh_performance_rankings(dashboard.id, assignments)

        return dashboard

    def _calculate_portfolio_health(
        self,
        dashboard: MultiHostelDashboard
    ) -> Decimal:
        """Calculate overall portfolio health score (0-100)."""
        scores = []

        # Occupancy score (0-30 points)
        occupancy_score = min(
            float(dashboard.avg_occupancy_percentage) / 100 * 30,
            30
        )
        scores.append(occupancy_score)

        # Financial health (0-30 points)
        if dashboard.total_revenue_this_month > 0:
            outstanding_ratio = float(
                dashboard.total_outstanding_payments / dashboard.total_revenue_this_month
            )
            financial_score = max(0, 30 - (outstanding_ratio * 30))
        else:
            financial_score = 0
        scores.append(financial_score)

        # Operational efficiency (0-20 points)
        if dashboard.total_hostels > 0:
            tasks_per_hostel = dashboard.total_pending_tasks / dashboard.total_hostels
            operational_score = max(0, 20 - tasks_per_hostel)
        else:
            operational_score = 0
        scores.append(operational_score)

        # Alert management (0-20 points)
        alert_score = max(0, 20 - dashboard.total_urgent_alerts)
        scores.append(alert_score)

        total_score = sum(scores)
        return Decimal(str(total_score)).quantize(Decimal('0.01'))

    def _determine_attention_level(
        self,
        dashboard: MultiHostelDashboard
    ) -> str:
        """Determine overall attention level required."""
        if dashboard.total_urgent_alerts > 10:
            return 'critical'
        elif dashboard.total_urgent_alerts > 5 or dashboard.hostels_requiring_attention > 2:
            return 'high'
        elif dashboard.total_pending_tasks > 50:
            return 'medium'
        else:
            return 'low'

    # ==================== CROSS-HOSTEL METRICS ====================

    async def _refresh_cross_hostel_metrics(
        self,
        dashboard_id: UUID,
        assignments: List
    ) -> List[CrossHostelMetric]:
        """Refresh cross-hostel metric comparisons."""
        # Delete existing metrics
        delete_stmt = select(CrossHostelMetric).where(
            CrossHostelMetric.dashboard_id == dashboard_id
        )
        result = await self.db.execute(delete_stmt)
        existing = result.scalars().all()
        for metric in existing:
            await self.db.delete(metric)

        # Define metrics to compare
        metrics_to_compare = [
            ('occupancy', 'Occupancy Rate', '%'),
            ('revenue', 'Monthly Revenue', 'currency'),
            ('collection_rate', 'Collection Rate', '%'),
            ('student_count', 'Active Students', 'count'),
        ]

        from app.repositories.admin.hostel_selector_repository import (
            HostelSelectorRepository
        )
        
        selector_repo = HostelSelectorRepository(self.db)

        new_metrics = []

        for metric_name, display_name, unit in metrics_to_compare:
            # Collect values from all hostels
            values = {}
            
            for assignment in assignments:
                stats = await selector_repo.get_hostel_quick_stats(
                    assignment.hostel_id,
                    refresh_if_stale=False
                )

                if stats:
                    if metric_name == 'occupancy':
                        value = stats.occupancy_percentage
                    elif metric_name == 'revenue':
                        value = stats.revenue_this_month
                    elif metric_name == 'collection_rate':
                        value = stats.collection_rate
                    elif metric_name == 'student_count':
                        value = Decimal(str(stats.active_students))
                    else:
                        value = Decimal('0.00')

                    values[assignment.hostel_id] = value

            if not values:
                continue

            # Calculate statistics
            values_list = list(values.values())
            portfolio_avg = sum(values_list) / len(values_list)
            
            # Find best and worst
            best_hostel = max(values.items(), key=lambda x: x[1])
            worst_hostel = min(values.items(), key=lambda x: x[1])

            # Calculate variance
            variance = max(values_list) - min(values_list)

            metric = CrossHostelMetric(
                dashboard_id=dashboard_id,
                metric_name=metric_name,
                metric_category='operational' if metric_name in ['occupancy', 'student_count'] else 'financial',
                display_unit=unit,
                portfolio_average=portfolio_avg,
                portfolio_median=sorted(values_list)[len(values_list) // 2],
                best_hostel_id=best_hostel[0],
                best_value=best_hostel[1],
                worst_hostel_id=worst_hostel[0],
                worst_value=worst_hostel[1],
                value_range=variance,
                hostel_values=values
            )

            self.db.add(metric)
            new_metrics.append(metric)

        await self.db.flush()
        return new_metrics

    async def get_cross_hostel_metrics(
        self,
        dashboard_id: UUID,
        category: Optional[str] = None
    ) -> List[CrossHostelMetric]:
        """Get cross-hostel metrics with optional category filter."""
        stmt = (
            select(CrossHostelMetric)
            .where(CrossHostelMetric.dashboard_id == dashboard_id)
            .options(
                selectinload(CrossHostelMetric.best_hostel),
                selectinload(CrossHostelMetric.worst_hostel)
            )
        )

        if category:
            stmt = stmt.where(CrossHostelMetric.metric_category == category)

        stmt = stmt.order_by(CrossHostelMetric.metric_name)

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    # ==================== PERFORMANCE RANKINGS ====================

    async def _refresh_performance_rankings(
        self,
        dashboard_id: UUID,
        assignments: List
    ) -> List[HostelPerformanceRanking]:
        """Refresh performance rankings for all hostels."""
        # Delete existing rankings
        delete_stmt = select(HostelPerformanceRanking).where(
            HostelPerformanceRanking.dashboard_id == dashboard_id
        )
        result = await self.db.execute(delete_stmt)
        existing = result.scalars().all()
        for ranking in existing:
            await self.db.delete(ranking)

        from app.repositories.admin.hostel_selector_repository import (
            HostelSelectorRepository
        )
        
        selector_repo = HostelSelectorRepository(self.db)

        # Calculate scores for each hostel
        hostel_scores = []

        for assignment in assignments:
            stats = await selector_repo.get_hostel_quick_stats(
                assignment.hostel_id,
                refresh_if_stale=False
            )

            if not stats:
                continue

            # Calculate dimensional scores
            occupancy_score = min(float(stats.occupancy_percentage), 100)
            
            financial_score = 0
            if stats.revenue_this_month > 0:
                collection_ratio = float(
                    (stats.revenue_this_month - stats.outstanding_payments) / 
                    stats.revenue_this_month
                )
                financial_score = collection_ratio * 100

            operational_score = max(0, 100 - (stats.pending_tasks * 2))
            
            satisfaction_score = float(stats.student_satisfaction_score or 0)

            # Calculate overall score (weighted average)
            overall_score = (
                occupancy_score * 0.3 +
                financial_score * 0.3 +
                operational_score * 0.2 +
                satisfaction_score * 0.2
            )

            hostel_scores.append({
                'hostel_id': assignment.hostel_id,
                'overall_score': Decimal(str(overall_score)),
                'occupancy_score': Decimal(str(occupancy_score)),
                'financial_score': Decimal(str(financial_score)),
                'operational_score': Decimal(str(operational_score)),
                'satisfaction_score': Decimal(str(satisfaction_score))
            })

        # Sort by overall score
        hostel_scores.sort(key=lambda x: x['overall_score'], reverse=True)

        # Create rankings
        rankings = []
        for rank, score_data in enumerate(hostel_scores, 1):
            # Determine performance category
            score = float(score_data['overall_score'])
            if score >= 90:
                category = 'excellent'
            elif score >= 75:
                category = 'good'
            elif score >= 60:
                category = 'fair'
            else:
                category = 'poor'

            # Identify strengths and weaknesses
            strengths = []
            weaknesses = []

            scores = {
                'occupancy': float(score_data['occupancy_score']),
                'financial': float(score_data['financial_score']),
                'operational': float(score_data['operational_score']),
                'satisfaction': float(score_data['satisfaction_score'])
            }

            for key, value in scores.items():
                if value >= 80:
                    strengths.append(key)
                elif value < 60:
                    weaknesses.append(key)

            ranking = HostelPerformanceRanking(
                dashboard_id=dashboard_id,
                hostel_id=score_data['hostel_id'],
                overall_rank=rank,
                overall_score=score_data['overall_score'],
                occupancy_score=score_data['occupancy_score'],
                financial_score=score_data['financial_score'],
                operational_score=score_data['operational_score'],
                satisfaction_score=score_data['satisfaction_score'],
                occupancy_rank=rank,  # Simplified - would need separate ranking
                financial_rank=rank,
                operational_rank=rank,
                satisfaction_rank=rank,
                performance_category=category,
                top_strengths=strengths[:3] if strengths else None,
                areas_for_improvement=weaknesses[:3] if weaknesses else None
            )

            self.db.add(ranking)
            rankings.append(ranking)

        await self.db.flush()
        return rankings

    async def get_performance_rankings(
        self,
        dashboard_id: UUID,
        min_rank: Optional[int] = None,
        max_rank: Optional[int] = None
    ) -> List[HostelPerformanceRanking]:
        """Get performance rankings with optional rank filter."""
        stmt = (
            select(HostelPerformanceRanking)
            .where(HostelPerformanceRanking.dashboard_id == dashboard_id)
            .options(selectinload(HostelPerformanceRanking.hostel))
            .order_by(HostelPerformanceRanking.overall_rank)
        )

        if min_rank:
            stmt = stmt.where(HostelPerformanceRanking.overall_rank >= min_rank)
        if max_rank:
            stmt = stmt.where(HostelPerformanceRanking.overall_rank <= max_rank)

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def get_top_performers(
        self,
        dashboard_id: UUID,
        count: int = 5
    ) -> List[HostelPerformanceRanking]:
        """Get top N performing hostels."""
        return await self.get_performance_rankings(
            dashboard_id,
            max_rank=count
        )

    async def get_underperformers(
        self,
        dashboard_id: UUID,
        threshold_score: float = 60.0
    ) -> List[HostelPerformanceRanking]:
        """Get hostels performing below threshold."""
        stmt = (
            select(HostelPerformanceRanking)
            .where(HostelPerformanceRanking.dashboard_id == dashboard_id)
            .where(HostelPerformanceRanking.overall_score < threshold_score)
            .options(selectinload(HostelPerformanceRanking.hostel))
            .order_by(HostelPerformanceRanking.overall_score)
        )

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    # ==================== DASHBOARD WIDGETS ====================

    async def get_admin_widgets(
        self,
        admin_id: UUID,
        visible_only: bool = True
    ) -> List[DashboardWidget]:
        """Get dashboard widgets for admin."""
        stmt = (
            select(DashboardWidget)
            .where(DashboardWidget.admin_id == admin_id)
            .order_by(
                DashboardWidget.position_row,
                DashboardWidget.position_col
            )
        )

        if visible_only:
            stmt = stmt.where(DashboardWidget.is_visible == True)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create_widget(
        self,
        admin_id: UUID,
        widget_type: str,
        widget_title: str,
        widget_config: Dict[str, Any],
        position: Optional[Tuple[int, int]] = None
    ) -> DashboardWidget:
        """Create new dashboard widget."""
        if position:
            row, col = position
        else:
            # Find next available position
            row, col = await self._find_next_widget_position(admin_id)

        widget = DashboardWidget(
            admin_id=admin_id,
            widget_type=widget_type,
            widget_title=widget_title,
            widget_config=widget_config,
            position_row=row,
            position_col=col,
            data_source=widget_config.get('data_source', 'default'),
            is_visible=True
        )

        self.db.add(widget)
        await self.db.flush()
        return widget

    async def update_widget(
        self,
        widget_id: UUID,
        updates: Dict[str, Any]
    ) -> DashboardWidget:
        """Update widget configuration."""
        widget = await self.db.get(DashboardWidget, widget_id)
        if not widget:
            raise EntityNotFoundError(f"Widget {widget_id} not found")

        for key, value in updates.items():
            if hasattr(widget, key):
                setattr(widget, key, value)

        await self.db.flush()
        return widget

    async def delete_widget(self, widget_id: UUID) -> bool:
        """Delete dashboard widget."""
        widget = await self.db.get(DashboardWidget, widget_id)
        if not widget:
            return False

        await self.db.delete(widget)
        await self.db.flush()
        return True

    async def refresh_widget_data(
        self,
        widget_id: UUID
    ) -> DashboardWidget:
        """Refresh cached data for widget."""
        widget = await self.db.get(DashboardWidget, widget_id)
        if not widget:
            raise EntityNotFoundError(f"Widget {widget_id} not found")

        # Widget data refresh logic would go here
        # This would depend on widget type and data source
        
        widget.last_refreshed = datetime.utcnow()
        await self.db.flush()
        return widget

    async def _find_next_widget_position(
        self,
        admin_id: UUID
    ) -> Tuple[int, int]:
        """Find next available widget position."""
        stmt = (
            select(
                func.max(DashboardWidget.position_row).label('max_row'),
                func.max(DashboardWidget.position_col).label('max_col')
            )
            .where(DashboardWidget.admin_id == admin_id)
        )

        result = await self.db.execute(stmt)
        row = result.first()

        if row and row.max_row is not None:
            # Place in next column, or new row if at column limit
            if row.max_col < 3:  # Assuming 4 columns max
                return (row.max_row, row.max_col + 1)
            else:
                return (row.max_row + 1, 0)
        else:
            # First widget
            return (0, 0)

    # ==================== DASHBOARD SNAPSHOTS ====================

    async def create_snapshot(
        self,
        admin_id: UUID,
        snapshot_type: str = 'daily',
        retention_days: int = 90
    ) -> DashboardSnapshot:
        """Create dashboard snapshot for historical tracking."""
        # Get current dashboard
        dashboard = await self.get_dashboard(admin_id, refresh_if_stale=True)
        if not dashboard:
            raise ValidationError(f"No dashboard found for admin {admin_id}")

        # Create snapshot
        snapshot = DashboardSnapshot(
            admin_id=admin_id,
            snapshot_timestamp=datetime.utcnow(),
            snapshot_date=date.today(),
            snapshot_type=snapshot_type,
            dashboard_data={
                'total_hostels': dashboard.total_hostels,
                'avg_occupancy': float(dashboard.avg_occupancy_percentage),
                'total_revenue': float(dashboard.total_revenue_this_month),
                'portfolio_health': float(dashboard.portfolio_health_score),
                'pending_tasks': dashboard.total_pending_tasks,
                'urgent_alerts': dashboard.total_urgent_alerts
            },
            total_hostels=dashboard.total_hostels,
            avg_occupancy=dashboard.avg_occupancy_percentage,
            total_revenue=dashboard.total_revenue_this_month,
            portfolio_health_score=dashboard.portfolio_health_score,
            retention_days=retention_days
        )

        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def get_snapshots(
        self,
        admin_id: UUID,
        snapshot_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50
    ) -> List[DashboardSnapshot]:
        """Get dashboard snapshots with filters."""
        stmt = (
            select(DashboardSnapshot)
            .where(DashboardSnapshot.admin_id == admin_id)
            .order_by(desc(DashboardSnapshot.snapshot_date))
            .limit(limit)
        )

        if snapshot_type:
            stmt = stmt.where(DashboardSnapshot.snapshot_type == snapshot_type)

        if start_date:
            stmt = stmt.where(DashboardSnapshot.snapshot_date >= start_date)

        if end_date:
            stmt = stmt.where(DashboardSnapshot.snapshot_date <= end_date)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def cleanup_old_snapshots(self) -> int:
        """Delete snapshots past their retention period."""
        stmt = (
            select(DashboardSnapshot)
            .where(DashboardSnapshot.should_be_deleted == True)
        )

        result = await self.db.execute(stmt)
        old_snapshots = result.scalars().all()

        for snapshot in old_snapshots:
            await self.db.delete(snapshot)

        await self.db.flush()
        return len(old_snapshots)

    async def get_trend_data(
        self,
        admin_id: UUID,
        metric: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get trend data for specific metric from snapshots."""
        start_date = date.today() - timedelta(days=days)

        snapshots = await self.get_snapshots(
            admin_id=admin_id,
            start_date=start_date,
            snapshot_type='daily'
        )

        trend_data = []
        for snapshot in reversed(snapshots):  # Chronological order
            value = None
            
            if metric == 'occupancy':
                value = float(snapshot.avg_occupancy)
            elif metric == 'revenue':
                value = float(snapshot.total_revenue)
            elif metric == 'health':
                value = float(snapshot.portfolio_health_score)
            elif metric == 'hostels':
                value = snapshot.total_hostels

            if value is not None:
                trend_data.append({
                    'date': snapshot.snapshot_date,
                    'value': value
                })

        return trend_data

    # ==================== ANALYTICS ====================

    async def get_portfolio_summary(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Get comprehensive portfolio summary."""
        dashboard = await self.get_dashboard(admin_id, refresh_if_stale=True)
        if not dashboard:
            return {}

        # Get top performers
        top_performers = await self.get_top_performers(dashboard.id, count=3)
        
        # Get underperformers
        underperformers = await self.get_underperformers(
            dashboard.id,
            threshold_score=60.0
        )

        # Get cross-hostel metrics
        metrics = await self.get_cross_hostel_metrics(dashboard.id)

        return {
            'portfolio_health': float(dashboard.portfolio_health_score),
            'attention_level': dashboard.attention_level,
            'total_hostels': dashboard.total_hostels,
            'avg_occupancy': float(dashboard.avg_occupancy_percentage),
            'total_revenue': float(dashboard.total_revenue_this_month),
            'outstanding_payments': float(dashboard.total_outstanding_payments),
            'pending_tasks': dashboard.total_pending_tasks,
            'urgent_alerts': dashboard.total_urgent_alerts,
            'top_performers': [
                {
                    'hostel_id': r.hostel_id,
                    'rank': r.overall_rank,
                    'score': float(r.overall_score),
                    'category': r.performance_category
                }
                for r in top_performers
            ],
            'underperformers': [
                {
                    'hostel_id': r.hostel_id,
                    'rank': r.overall_rank,
                    'score': float(r.overall_score),
                    'areas_for_improvement': r.areas_for_improvement
                }
                for r in underperformers
            ],
            'key_metrics': [
                {
                    'name': m.metric_name,
                    'avg': float(m.portfolio_average),
                    'best': float(m.best_value),
                    'worst': float(m.worst_value)
                }
                for m in metrics[:5]  # Top 5 metrics
            ]
        }