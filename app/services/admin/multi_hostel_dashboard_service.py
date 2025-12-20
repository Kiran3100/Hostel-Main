"""
Multi-Hostel Dashboard Service

Business logic for aggregated dashboard data, cross-hostel analytics,
and portfolio-wide insights for multi-hostel admins.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.admin.multi_hostel_dashboard import (
    MultiHostelDashboard,
    CrossHostelMetric,
    HostelPerformanceRanking,
    DashboardWidget,
    DashboardSnapshot
)
from app.repositories.admin.multi_hostel_dashboard_repository import (
    MultiHostelDashboardRepository
)
from app.repositories.admin.admin_hostel_assignment_repository import (
    AdminHostelAssignmentRepository
)
from app.core.exceptions import (
    ValidationError,
    EntityNotFoundError
)


class MultiHostelDashboardService:
    """
    Multi-hostel dashboard service with:
    - Aggregated portfolio metrics
    - Cross-hostel comparisons
    - Performance rankings
    - Widget management
    - Historical trending
    """

    def __init__(self, db: Session):
        self.db = db
        self.dashboard_repo = MultiHostelDashboardRepository(db)
        self.assignment_repo = AdminHostelAssignmentRepository(db)

        # Configuration
        self.dashboard_refresh_threshold_minutes = 5
        self.snapshot_retention_days = 90

    # ==================== DASHBOARD MANAGEMENT ====================

    async def get_dashboard(
        self,
        admin_id: UUID,
        dashboard_date: Optional[date] = None,
        force_refresh: bool = False
    ) -> MultiHostelDashboard:
        """
        Get dashboard with auto-refresh if stale.
        
        Args:
            admin_id: Admin ID
            dashboard_date: Specific date (default: today)
            force_refresh: Force refresh even if not stale
            
        Returns:
            Dashboard with all metrics
        """
        if not dashboard_date:
            dashboard_date = date.today()

        dashboard = await self.dashboard_repo.get_dashboard(
            admin_id=admin_id,
            dashboard_date=dashboard_date,
            refresh_if_stale=not force_refresh
        )

        if force_refresh or not dashboard:
            dashboard = await self.refresh_dashboard(admin_id, dashboard_date)

        return dashboard

    async def refresh_dashboard(
        self,
        admin_id: UUID,
        dashboard_date: Optional[date] = None,
        force: bool = False
    ) -> MultiHostelDashboard:
        """Refresh dashboard with latest data."""
        dashboard = await self.dashboard_repo.refresh_dashboard(
            admin_id=admin_id,
            dashboard_date=dashboard_date,
            force=force
        )

        await self.db.commit()
        return dashboard

    async def get_dashboard_summary(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Get high-level dashboard summary."""
        dashboard = await self.get_dashboard(admin_id)

        return {
            'admin_id': str(admin_id),
            'portfolio_health': float(dashboard.portfolio_health_score),
            'attention_level': dashboard.attention_level,
            'total_hostels': dashboard.total_hostels,
            'active_hostels': dashboard.active_hostels,
            'key_metrics': {
                'avg_occupancy': float(dashboard.avg_occupancy_percentage),
                'total_students': dashboard.total_students,
                'total_revenue': float(dashboard.total_revenue_this_month),
                'outstanding_payments': float(dashboard.total_outstanding_payments)
            },
            'alerts': {
                'pending_tasks': dashboard.total_pending_tasks,
                'urgent_alerts': dashboard.total_urgent_alerts,
                'open_complaints': dashboard.total_open_complaints,
                'hostels_requiring_attention': dashboard.hostels_requiring_attention
            },
            'performance': {
                'top_performer': {
                    'hostel_id': str(dashboard.top_performer_hostel_id),
                    'score': float(dashboard.top_performer_score)
                } if dashboard.top_performer_hostel_id else None,
                'bottom_performer': {
                    'hostel_id': str(dashboard.bottom_performer_hostel_id),
                    'score': float(dashboard.bottom_performer_score)
                } if dashboard.bottom_performer_hostel_id else None
            }
        }

    # ==================== CROSS-HOSTEL METRICS ====================

    async def get_cross_hostel_metrics(
        self,
        admin_id: UUID,
        category: Optional[str] = None
    ) -> List[CrossHostelMetric]:
        """Get cross-hostel metric comparisons."""
        dashboard = await self.get_dashboard(admin_id)
        
        return await self.dashboard_repo.get_cross_hostel_metrics(
            dashboard_id=dashboard.id,
            category=category
        )

    async def compare_hostels(
        self,
        admin_id: UUID,
        metric_name: str
    ) -> Dict[str, Any]:
        """Get detailed comparison for specific metric."""
        dashboard = await self.get_dashboard(admin_id)
        
        # Get all metrics
        metrics = await self.dashboard_repo.get_cross_hostel_metrics(dashboard.id)
        
        # Find specific metric
        target_metric = next(
            (m for m in metrics if m.metric_name == metric_name),
            None
        )

        if not target_metric:
            raise EntityNotFoundError(f"Metric '{metric_name}' not found")

        return {
            'metric_name': target_metric.metric_name,
            'metric_category': target_metric.metric_category,
            'display_unit': target_metric.display_unit,
            'portfolio_stats': {
                'average': float(target_metric.portfolio_average),
                'median': float(target_metric.portfolio_median) if target_metric.portfolio_median else None,
                'std_dev': float(target_metric.portfolio_std_dev) if target_metric.portfolio_std_dev else None
            },
            'best_performer': {
                'hostel_id': str(target_metric.best_hostel_id),
                'value': float(target_metric.best_value)
            } if target_metric.best_hostel_id else None,
            'worst_performer': {
                'hostel_id': str(target_metric.worst_hostel_id),
                'value': float(target_metric.worst_value)
            } if target_metric.worst_hostel_id else None,
            'hostel_values': target_metric.hostel_values,
            'variance_analysis': {
                'range': float(target_metric.value_range) if target_metric.value_range else None,
                'variation_coefficient': float(target_metric.variation_coefficient) if target_metric.variation_coefficient else None,
                'has_significant_variation': target_metric.has_significant_variation
            }
        }

    # ==================== PERFORMANCE RANKINGS ====================

    async def get_performance_rankings(
        self,
        admin_id: UUID,
        min_rank: Optional[int] = None,
        max_rank: Optional[int] = None
    ) -> List[HostelPerformanceRanking]:
        """Get hostel performance rankings."""
        dashboard = await self.get_dashboard(admin_id)
        
        return await self.dashboard_repo.get_performance_rankings(
            dashboard_id=dashboard.id,
            min_rank=min_rank,
            max_rank=max_rank
        )

    async def get_top_performers(
        self,
        admin_id: UUID,
        count: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top performing hostels."""
        dashboard = await self.get_dashboard(admin_id)
        
        rankings = await self.dashboard_repo.get_top_performers(
            dashboard_id=dashboard.id,
            count=count
        )

        return [
            {
                'hostel_id': str(r.hostel_id),
                'hostel_name': r.hostel.name if r.hostel else None,
                'rank': r.overall_rank,
                'overall_score': float(r.overall_score),
                'performance_category': r.performance_category,
                'scores': {
                    'occupancy': float(r.occupancy_score),
                    'financial': float(r.financial_score),
                    'operational': float(r.operational_score),
                    'satisfaction': float(r.satisfaction_score)
                },
                'strengths': r.top_strengths
            }
            for r in rankings
        ]

    async def get_underperformers(
        self,
        admin_id: UUID,
        threshold_score: float = 60.0
    ) -> List[Dict[str, Any]]:
        """Get underperforming hostels."""
        dashboard = await self.get_dashboard(admin_id)
        
        rankings = await self.dashboard_repo.get_underperformers(
            dashboard_id=dashboard.id,
            threshold_score=threshold_score
        )

        return [
            {
                'hostel_id': str(r.hostel_id),
                'hostel_name': r.hostel.name if r.hostel else None,
                'rank': r.overall_rank,
                'overall_score': float(r.overall_score),
                'performance_category': r.performance_category,
                'areas_for_improvement': r.areas_for_improvement,
                'scores': {
                    'occupancy': float(r.occupancy_score),
                    'financial': float(r.financial_score),
                    'operational': float(r.operational_score),
                    'satisfaction': float(r.satisfaction_score)
                }
            }
            for r in rankings
        ]

    async def get_performance_trends(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get performance trends for specific hostel."""
        # Get historical snapshots
        snapshots = await self.get_snapshots(
            admin_id=admin_id,
            start_date=date.today() - timedelta(days=days),
            snapshot_type='daily'
        )

        trends = []
        for snapshot in snapshots:
            # Extract hostel data from snapshot
            hostel_data = snapshot.dashboard_data.get('hostel_breakdown', {}).get(str(hostel_id))
            
            if hostel_data:
                trends.append({
                    'date': snapshot.snapshot_date,
                    'occupancy': hostel_data.get('occupancy', 0),
                    'revenue': hostel_data.get('revenue', 0),
                    'health_score': hostel_data.get('health_score', 0)
                })

        return trends

    # ==================== WIDGET MANAGEMENT ====================

    async def get_widgets(
        self,
        admin_id: UUID,
        visible_only: bool = True
    ) -> List[DashboardWidget]:
        """Get dashboard widgets for admin."""
        return await self.dashboard_repo.get_admin_widgets(
            admin_id=admin_id,
            visible_only=visible_only
        )

    async def create_widget(
        self,
        admin_id: UUID,
        widget_type: str,
        widget_title: str,
        widget_config: Dict[str, Any],
        position: Optional[tuple] = None
    ) -> DashboardWidget:
        """Create new dashboard widget."""
        widget = await self.dashboard_repo.create_widget(
            admin_id=admin_id,
            widget_type=widget_type,
            widget_title=widget_title,
            widget_config=widget_config,
            position=position
        )

        await self.db.commit()
        return widget

    async def update_widget(
        self,
        widget_id: UUID,
        updates: Dict[str, Any]
    ) -> DashboardWidget:
        """Update widget configuration."""
        widget = await self.dashboard_repo.update_widget(
            widget_id=widget_id,
            updates=updates
        )

        await self.db.commit()
        return widget

    async def delete_widget(self, widget_id: UUID) -> bool:
        """Delete dashboard widget."""
        result = await self.dashboard_repo.delete_widget(widget_id)
        
        if result:
            await self.db.commit()
        
        return result

    async def refresh_widget_data(self, widget_id: UUID) -> DashboardWidget:
        """Refresh cached data for widget."""
        widget = await self.dashboard_repo.refresh_widget_data(widget_id)
        await self.db.commit()
        return widget

    async def get_widget_layouts(self) -> List[Dict[str, Any]]:
        """Get predefined widget layout templates."""
        return [
            {
                'name': 'executive_overview',
                'display_name': 'Executive Overview',
                'description': 'High-level portfolio metrics',
                'widgets': [
                    {'type': 'portfolio_summary', 'size': 'large', 'row': 0, 'col': 0},
                    {'type': 'top_performers', 'size': 'medium', 'row': 0, 'col': 2},
                    {'type': 'alerts_summary', 'size': 'medium', 'row': 1, 'col': 0},
                    {'type': 'financial_summary', 'size': 'medium', 'row': 1, 'col': 2}
                ]
            },
            {
                'name': 'operational_focus',
                'display_name': 'Operational Focus',
                'description': 'Day-to-day operations tracking',
                'widgets': [
                    {'type': 'pending_tasks', 'size': 'medium', 'row': 0, 'col': 0},
                    {'type': 'urgent_alerts', 'size': 'medium', 'row': 0, 'col': 2},
                    {'type': 'occupancy_chart', 'size': 'large', 'row': 1, 'col': 0},
                    {'type': 'recent_activity', 'size': 'medium', 'row': 2, 'col': 0}
                ]
            },
            {
                'name': 'financial_analytics',
                'display_name': 'Financial Analytics',
                'description': 'Revenue and financial metrics',
                'widgets': [
                    {'type': 'revenue_chart', 'size': 'large', 'row': 0, 'col': 0},
                    {'type': 'collection_rates', 'size': 'medium', 'row': 0, 'col': 2},
                    {'type': 'outstanding_payments', 'size': 'medium', 'row': 1, 'col': 0},
                    {'type': 'financial_trends', 'size': 'medium', 'row': 1, 'col': 2}
                ]
            }
        ]

    async def apply_widget_layout(
        self,
        admin_id: UUID,
        layout_name: str,
        clear_existing: bool = True
    ) -> List[DashboardWidget]:
        """Apply predefined widget layout."""
        layouts = await self.get_widget_layouts()
        layout = next((l for l in layouts if l['name'] == layout_name), None)

        if not layout:
            raise ValidationError(f"Layout '{layout_name}' not found")

        # Clear existing widgets if requested
        if clear_existing:
            existing_widgets = await self.get_widgets(admin_id, visible_only=False)
            for widget in existing_widgets:
                await self.delete_widget(widget.id)

        # Create new widgets
        created_widgets = []
        for widget_config in layout['widgets']:
            widget = await self.create_widget(
                admin_id=admin_id,
                widget_type=widget_config['type'],
                widget_title=widget_config['type'].replace('_', ' ').title(),
                widget_config={'data_source': 'default'},
                position=(widget_config['row'], widget_config['col'])
            )
            created_widgets.append(widget)

        return created_widgets

    # ==================== SNAPSHOTS & HISTORY ====================

    async def create_snapshot(
        self,
        admin_id: UUID,
        snapshot_type: str = 'daily'
    ) -> DashboardSnapshot:
        """Create dashboard snapshot for historical tracking."""
        snapshot = await self.dashboard_repo.create_snapshot(
            admin_id=admin_id,
            snapshot_type=snapshot_type,
            retention_days=self.snapshot_retention_days
        )

        await self.db.commit()
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
        return await self.dashboard_repo.get_snapshots(
            admin_id=admin_id,
            snapshot_type=snapshot_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

    async def get_trend_data(
        self,
        admin_id: UUID,
        metric: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get trend data for specific metric."""
        return await self.dashboard_repo.get_trend_data(
            admin_id=admin_id,
            metric=metric,
            days=days
        )

    async def cleanup_old_snapshots(self) -> int:
        """Delete snapshots past retention period."""
        count = await self.dashboard_repo.cleanup_old_snapshots()
        
        if count > 0:
            await self.db.commit()
        
        return count

    # ==================== PORTFOLIO ANALYTICS ====================

    async def get_portfolio_summary(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Get comprehensive portfolio summary."""
        return await self.dashboard_repo.get_portfolio_summary(admin_id)

    async def analyze_portfolio_health(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Analyze overall portfolio health with recommendations."""
        summary = await self.get_portfolio_summary(admin_id)
        dashboard = await self.get_dashboard(admin_id)

        # Generate health analysis
        health_factors = []
        recommendations = []

        # Occupancy analysis
        if dashboard.avg_occupancy_percentage < 70:
            health_factors.append({
                'factor': 'low_occupancy',
                'severity': 'high',
                'current_value': float(dashboard.avg_occupancy_percentage),
                'target_value': 85.0
            })
            recommendations.append({
                'type': 'improve_occupancy',
                'message': f'Average occupancy ({dashboard.avg_occupancy_percentage}%) is below target. '
                          'Review pricing and marketing strategies.',
                'priority': 'high'
            })

        # Financial health
        if dashboard.total_outstanding_payments > dashboard.total_revenue_this_month:
            health_factors.append({
                'factor': 'high_outstanding_payments',
                'severity': 'critical',
                'current_value': float(dashboard.total_outstanding_payments),
                'revenue': float(dashboard.total_revenue_this_month)
            })
            recommendations.append({
                'type': 'improve_collections',
                'message': 'Outstanding payments exceed monthly revenue. Intensify collection efforts.',
                'priority': 'critical'
            })

        # Workload analysis
        if dashboard.total_pending_tasks > 100:
            health_factors.append({
                'factor': 'high_pending_tasks',
                'severity': 'medium',
                'current_value': dashboard.total_pending_tasks
            })
            recommendations.append({
                'type': 'reduce_backlog',
                'message': f'{dashboard.total_pending_tasks} pending tasks. Consider workload redistribution.',
                'priority': 'medium'
            })

        # Alert analysis
        if dashboard.total_urgent_alerts > 10:
            health_factors.append({
                'factor': 'urgent_alerts',
                'severity': 'high',
                'current_value': dashboard.total_urgent_alerts
            })
            recommendations.append({
                'type': 'address_alerts',
                'message': f'{dashboard.total_urgent_alerts} urgent alerts require immediate attention.',
                'priority': 'high'
            })

        return {
            'portfolio_health_score': float(dashboard.portfolio_health_score),
            'health_status': self._classify_health_status(dashboard.portfolio_health_score),
            'attention_level': dashboard.attention_level,
            'health_factors': health_factors,
            'recommendations': sorted(
                recommendations,
                key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}[x['priority']]
            ),
            'summary': summary
        }

    def _classify_health_status(self, health_score: Decimal) -> str:
        """Classify portfolio health status."""
        score = float(health_score)
        
        if score >= 90:
            return 'excellent'
        elif score >= 75:
            return 'good'
        elif score >= 60:
            return 'fair'
        elif score >= 40:
            return 'needs_improvement'
        else:
            return 'critical'

    async def compare_period_performance(
        self,
        admin_id: UUID,
        period_1_start: date,
        period_1_end: date,
        period_2_start: date,
        period_2_end: date
    ) -> Dict[str, Any]:
        """Compare performance between two time periods."""
        # Get snapshots for both periods
        period_1_snapshots = await self.get_snapshots(
            admin_id=admin_id,
            start_date=period_1_start,
            end_date=period_1_end
        )

        period_2_snapshots = await self.get_snapshots(
            admin_id=admin_id,
            start_date=period_2_start,
            end_date=period_2_end
        )

        # Calculate averages for each period
        def calculate_period_avg(snapshots):
            if not snapshots:
                return {}
            
            return {
                'avg_occupancy': sum(s.avg_occupancy for s in snapshots) / len(snapshots),
                'avg_revenue': sum(s.total_revenue for s in snapshots) / len(snapshots),
                'avg_health_score': sum(s.portfolio_health_score for s in snapshots) / len(snapshots)
            }

        period_1_avg = calculate_period_avg(period_1_snapshots)
        period_2_avg = calculate_period_avg(period_2_snapshots)

        # Calculate changes
        changes = {}
        for key in period_1_avg.keys():
            if period_1_avg[key] != 0:
                change_pct = ((period_2_avg[key] - period_1_avg[key]) / period_1_avg[key]) * 100
            else:
                change_pct = 0
            
            changes[key] = {
                'period_1': float(period_1_avg[key]),
                'period_2': float(period_2_avg[key]),
                'change': float(period_2_avg[key] - period_1_avg[key]),
                'change_percentage': round(change_pct, 2),
                'trend': 'up' if change_pct > 0 else 'down' if change_pct < 0 else 'stable'
            }

        return {
            'period_1': {'start': period_1_start, 'end': period_1_end},
            'period_2': {'start': period_2_start, 'end': period_2_end},
            'metrics': changes,
            'overall_trend': self._determine_overall_trend(changes)
        }

    def _determine_overall_trend(self, changes: Dict) -> str:
        """Determine overall performance trend."""
        positive_changes = sum(
            1 for v in changes.values()
            if v['change_percentage'] > 5
        )
        negative_changes = sum(
            1 for v in changes.values()
            if v['change_percentage'] < -5
        )

        if positive_changes > negative_changes:
            return 'improving'
        elif negative_changes > positive_changes:
            return 'declining'
        else:
            return 'stable'

    # ==================== SCHEDULED TASKS ====================

    async def create_daily_snapshot(self, admin_id: UUID) -> DashboardSnapshot:
        """Create daily snapshot (for scheduled task)."""
        return await self.create_snapshot(admin_id, snapshot_type='daily')

    async def refresh_all_dashboards(self) -> Dict[str, Any]:
        """Refresh all active dashboards (for scheduled task)."""
        from sqlalchemy import select
        from app.models.admin.admin_user import AdminUser
        
        # Get all active admins
        stmt = (
            select(AdminUser.id)
            .where(AdminUser.is_active == True)
            .where(AdminUser.is_deleted == False)
        )
        
        result = await self.db.execute(stmt)
        admin_ids = result.scalars().all()

        results = {
            'total': len(admin_ids),
            'success': 0,
            'failed': 0
        }

        for admin_id in admin_ids:
            try:
                await self.refresh_dashboard(admin_id, force=True)
                results['success'] += 1
            except Exception:
                results['failed'] += 1

        return results