# --- File: C:\Hostel-Main\app\services\analytics\dashboard_analytics_service.py ---
"""
Dashboard Analytics Service - Unified metrics display and aggregation.

Provides comprehensive dashboard data with:
- KPI aggregation from all modules
- Widget configuration management
- Time-series metric collection
- Alert notification handling
- Quick stats generation
- Role-specific customization
"""

from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.repositories.analytics.dashboard_analytics_repository import (
    DashboardAnalyticsRepository
)
from app.repositories.analytics.analytics_aggregate_repository import (
    AnalyticsAggregateRepository
)


logger = logging.getLogger(__name__)


class DashboardAnalyticsService:
    """Service for dashboard analytics operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = DashboardAnalyticsRepository(db)
        self.aggregate_repo = AnalyticsAggregateRepository(db)
    
    # ==================== Dashboard KPI Management ====================
    
    def create_dashboard_kpi(
        self,
        hostel_id: Optional[UUID],
        kpi_key: str,
        period_start: date,
        period_end: date,
        kpi_data: Dict[str, Any]
    ) -> Any:
        """
        Create or update a dashboard KPI.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            kpi_key: Unique KPI identifier
            period_start: Period start date
            period_end: Period end date
            kpi_data: KPI data including value, target, metadata
        """
        logger.info(f"Creating dashboard KPI: {kpi_key} for hostel {hostel_id}")
        
        kpi = self.repo.create_or_update_kpi(
            hostel_id=hostel_id,
            kpi_key=kpi_key,
            period_start=period_start,
            period_end=period_end,
            kpi_data=kpi_data
        )
        
        return kpi
    
    def get_dashboard_kpis(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        category: Optional[str] = None
    ) -> List[Any]:
        """
        Get all dashboard KPIs for a period.
        
        Optionally filter by category.
        """
        if category:
            kpis = self.repo.get_kpis_by_category(
                hostel_id, category, period_start, period_end
            )
        else:
            kpis = self.repo.get_all_kpis_for_period(
                hostel_id, period_start, period_end
            )
        
        return kpis
    
    # ==================== Time Series Metrics ====================
    
    def add_timeseries_metric(
        self,
        metric_key: str,
        hostel_id: Optional[UUID],
        data_date: date,
        value: Decimal,
        label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Add a time series data point.
        
        Used for tracking metrics over time for charts and trends.
        """
        metric = self.repo.add_timeseries_metric(
            metric_key=metric_key,
            hostel_id=hostel_id,
            data_date=data_date,
            value=value,
            label=label,
            metadata=metadata
        )
        
        return metric
    
    def get_timeseries_data(
        self,
        metric_key: str,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """
        Get time series data for a metric.
        
        Returns data points formatted for charting.
        """
        metrics = self.repo.get_timeseries_metrics(
            metric_key, hostel_id, start_date, end_date
        )
        
        return [
            {
                'date': m.data_date.isoformat(),
                'value': float(m.value),
                'label': m.label,
            }
            for m in metrics
        ]
    
    def get_metric_trend(
        self,
        metric_key: str,
        hostel_id: Optional[UUID],
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate trend for a metric over recent days.
        
        Returns trend direction, percentage change, and confidence.
        """
        trend = self.repo.calculate_metric_trend(
            metric_key, hostel_id, days
        )
        
        return trend
    
    # ==================== Widget Management ====================
    
    def create_widget(
        self,
        user_id: Optional[UUID],
        role: Optional[str],
        hostel_id: Optional[UUID],
        widget_data: Dict[str, Any]
    ) -> Any:
        """
        Create or update a dashboard widget configuration.
        
        Args:
            user_id: User ID for personalized widgets
            role: Role for role-based widgets
            hostel_id: Hostel ID
            widget_data: Widget configuration
        """
        logger.info(f"Creating widget for user {user_id} / role {role}")
        
        widget = self.repo.create_or_update_widget(
            user_id=user_id,
            role=role,
            hostel_id=hostel_id,
            widget_data=widget_data
        )
        
        return widget
    
    def get_user_widgets(
        self,
        user_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> List[Any]:
        """Get all widgets configured for a user."""
        widgets = self.repo.get_user_widgets(user_id, hostel_id)
        return widgets
    
    def get_role_widgets(
        self,
        role: str,
        hostel_id: Optional[UUID] = None
    ) -> List[Any]:
        """Get default widgets for a role."""
        widgets = self.repo.get_role_widgets(role, hostel_id)
        return widgets
    
    def update_widget_position(
        self,
        widget_id: UUID,
        new_position: int
    ) -> Any:
        """Update widget display position/order."""
        widget = self.repo.update_widget_position(widget_id, new_position)
        return widget
    
    def toggle_widget_visibility(
        self,
        widget_id: UUID
    ) -> Any:
        """Toggle widget visibility on/off."""
        widget = self.repo.toggle_widget_visibility(widget_id)
        return widget
    
    # ==================== Alert Notifications ====================
    
    def create_alert(
        self,
        hostel_id: Optional[UUID],
        severity: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> Any:
        """
        Create a new alert notification.
        
        Args:
            hostel_id: Hostel ID
            severity: Alert severity (info, warning, error, critical)
            title: Alert title
            message: Alert message
            action_url: Optional action URL
            action_label: Optional action button label
            expires_at: Optional expiration datetime
        """
        logger.info(f"Creating {severity} alert for hostel {hostel_id}: {title}")
        
        alert_data = {
            'severity': severity,
            'title': title,
            'message': message,
            'action_url': action_url,
            'action_label': action_label,
            'expires_at': expires_at,
        }
        
        alert = self.repo.create_alert(hostel_id, alert_data)
        return alert
    
    def get_active_alerts(
        self,
        hostel_id: Optional[UUID],
        severity: Optional[str] = None
    ) -> List[Any]:
        """
        Get all active (non-dismissed, non-expired) alerts.
        
        Optionally filter by severity.
        """
        alerts = self.repo.get_active_alerts(hostel_id, severity)
        return alerts
    
    def dismiss_alert(
        self,
        alert_id: UUID,
        dismissed_by: UUID
    ) -> Any:
        """Dismiss an alert."""
        alert = self.repo.dismiss_alert(alert_id, dismissed_by)
        return alert
    
    def generate_system_alerts(
        self,
        hostel_id: Optional[UUID]
    ) -> List[Any]:
        """
        Generate system alerts based on current metrics.
        
        Analyzes metrics and creates alerts for issues requiring attention.
        """
        logger.info(f"Generating system alerts for hostel {hostel_id}")
        
        alerts_created = []
        
        # Get quick stats to check for issues
        quick_stats = self.repo.get_quick_stats(hostel_id)
        
        if not quick_stats:
            return alerts_created
        
        # Critical complaint alerts
        if quick_stats.urgent_complaints > 0:
            alert = self.create_alert(
                hostel_id=hostel_id,
                severity='critical',
                title='Urgent Complaints Pending',
                message=f'{quick_stats.urgent_complaints} urgent complaints require immediate attention',
                action_url='/complaints?filter=urgent',
                action_label='View Complaints',
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            alerts_created.append(alert)
        
        # Overdue maintenance alerts
        if quick_stats.overdue_maintenance > 0:
            alert = self.create_alert(
                hostel_id=hostel_id,
                severity='error',
                title='Overdue Maintenance Requests',
                message=f'{quick_stats.overdue_maintenance} maintenance requests are overdue',
                action_url='/maintenance?filter=overdue',
                action_label='View Maintenance',
                expires_at=datetime.utcnow() + timedelta(hours=48)
            )
            alerts_created.append(alert)
        
        # Payment alerts
        if quick_stats.overdue_payments > 5000:
            alert = self.create_alert(
                hostel_id=hostel_id,
                severity='warning',
                title='High Overdue Payments',
                message=f'₹{float(quick_stats.overdue_payments):,.2f} in overdue payments',
                action_url='/payments?filter=overdue',
                action_label='View Payments',
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            alerts_created.append(alert)
        
        # Occupancy alerts
        if quick_stats.occupancy_rate and quick_stats.occupancy_rate < 50:
            alert = self.create_alert(
                hostel_id=hostel_id,
                severity='warning',
                title='Low Occupancy Rate',
                message=f'Current occupancy at {float(quick_stats.occupancy_rate)}% - below target',
                action_url='/occupancy',
                action_label='View Details',
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            alerts_created.append(alert)
        
        return alerts_created
    
    # ==================== Quick Stats ====================
    
    def generate_quick_stats(
        self,
        hostel_id: Optional[UUID],
        snapshot_date: Optional[date] = None
    ) -> Any:
        """
        Generate quick stats snapshot for a date.
        
        Aggregates key metrics for immediate dashboard visibility.
        """
        if snapshot_date is None:
            snapshot_date = date.today()
        
        logger.info(f"Generating quick stats for hostel {hostel_id}, date {snapshot_date}")
        
        # Would query actual data from various modules
        # Placeholder implementation
        stats_data = {
            'total_students': 0,
            'active_students': 0,
            'total_visitors': 0,
            'active_visitors': 0,
            'todays_check_ins': 0,
            'todays_check_outs': 0,
            'open_complaints': 0,
            'urgent_complaints': 0,
            'pending_maintenance': 0,
            'overdue_maintenance': 0,
            'todays_revenue': Decimal('0.00'),
            'monthly_revenue': Decimal('0.00'),
            'outstanding_payments': Decimal('0.00'),
            'overdue_payments': Decimal('0.00'),
            'occupancy_rate': Decimal('0.00'),
        }
        
        stats = self.repo.create_or_update_quick_stats(
            hostel_id=hostel_id,
            snapshot_date=snapshot_date,
            stats_data=stats_data
        )
        
        return stats
    
    def get_quick_stats(
        self,
        hostel_id: Optional[UUID],
        snapshot_date: Optional[date] = None
    ) -> Any:
        """Get quick stats for a specific date."""
        stats = self.repo.get_quick_stats(hostel_id, snapshot_date)
        return stats
    
    def get_quick_stats_history(
        self,
        hostel_id: Optional[UUID],
        days: int = 7
    ) -> List[Any]:
        """Get quick stats history for recent days."""
        history = self.repo.get_quick_stats_history(hostel_id, days)
        return history
    
    # ==================== Role-Specific Dashboard ====================
    
    def create_role_dashboard(
        self,
        user_id: UUID,
        hostel_id: Optional[UUID],
        role: str,
        dashboard_data: Dict[str, Any]
    ) -> Any:
        """
        Create or update role-specific dashboard configuration.
        
        Customizes dashboard based on user role and permissions.
        """
        logger.info(f"Creating role dashboard for user {user_id}, role {role}")
        
        dashboard = self.repo.create_or_update_role_dashboard(
            user_id=user_id,
            hostel_id=hostel_id,
            role=role,
            dashboard_data=dashboard_data
        )
        
        return dashboard
    
    def get_role_dashboard(
        self,
        user_id: UUID,
        hostel_id: Optional[UUID]
    ) -> Any:
        """Get role-specific dashboard for a user."""
        dashboard = self.repo.get_role_dashboard(user_id, hostel_id)
        return dashboard
    
    # ==================== Unified Dashboard Data ====================
    
    def get_unified_dashboard(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        user_id: Optional[UUID] = None,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get unified dashboard data for a user.
        
        Combines metrics, widgets, alerts, and role-specific customizations.
        """
        logger.info(f"Getting unified dashboard for user {user_id}, hostel {hostel_id}")
        
        # Get unified metrics from aggregate repository
        metrics = self.aggregate_repo.get_unified_dashboard_metrics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end
        )
        
        # Get widgets
        if user_id:
            widgets = self.get_user_widgets(user_id, hostel_id)
        elif role:
            widgets = self.get_role_widgets(role, hostel_id)
        else:
            widgets = []
        
        # Get active alerts
        alerts = self.get_active_alerts(hostel_id)
        
        # Get quick stats
        quick_stats = self.get_quick_stats(hostel_id)
        
        # Get role dashboard if available
        role_dashboard = None
        if user_id:
            role_dashboard = self.get_role_dashboard(user_id, hostel_id)
        
        return {
            'metrics': metrics,
            'widgets': [self._format_widget(w) for w in widgets],
            'alerts': [self._format_alert(a) for a in alerts],
            'quick_stats': self._format_quick_stats(quick_stats) if quick_stats else None,
            'role_dashboard': role_dashboard,
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
            }
        }
    
    # ==================== Helper Methods ====================
    
    def _format_widget(self, widget: Any) -> Dict[str, Any]:
        """Format widget for API response."""
        return {
            'id': str(widget.id),
            'widget_id': widget.widget_id,
            'widget_type': widget.widget_type,
            'title': widget.title,
            'position': widget.position,
            'size': widget.size,
            'data_source': widget.data_source,
            'configuration': widget.configuration,
            'is_visible': widget.is_visible,
        }
    
    def _format_alert(self, alert: Any) -> Dict[str, Any]:
        """Format alert for API response."""
        return {
            'id': str(alert.id),
            'severity': alert.severity,
            'title': alert.title,
            'message': alert.message,
            'action_url': alert.action_url,
            'action_label': alert.action_label,
            'created_at': alert.created_at.isoformat(),
            'expires_at': alert.expires_at.isoformat() if alert.expires_at else None,
        }
    
    def _format_quick_stats(self, stats: Any) -> Dict[str, Any]:
        """Format quick stats for API response."""
        return {
            'total_students': stats.total_students,
            'active_students': stats.active_students,
            'todays_check_ins': stats.todays_check_ins,
            'todays_check_outs': stats.todays_check_outs,
            'open_complaints': stats.open_complaints,
            'urgent_complaints': stats.urgent_complaints,
            'pending_maintenance': stats.pending_maintenance,
            'todays_revenue': float(stats.todays_revenue),
            'monthly_revenue': float(stats.monthly_revenue),
            'outstanding_payments': float(stats.outstanding_payments),
            'occupancy_rate': float(stats.occupancy_rate) if stats.occupancy_rate else 0,
        }


