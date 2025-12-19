"""
Dashboard Analytics Repository for unified metrics display.

Provides comprehensive dashboard data management with:
- Generic KPI tracking and storage
- Widget configuration and management
- Time-series metric collection
- Alert notification handling
- Quick stats aggregation
- Role-specific dashboard customization
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, desc
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.models.analytics.dashboard_analytics import (
    DashboardKPI,
    TimeseriesMetric,
    DashboardWidget,
    AlertNotification,
    QuickStats,
    RoleSpecificDashboard,
)


class DashboardAnalyticsRepository(BaseRepository):
    """Repository for dashboard analytics operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    # ==================== Dashboard KPI Operations ====================
    
    def create_or_update_kpi(
        self,
        hostel_id: Optional[UUID],
        kpi_key: str,
        period_start: date,
        period_end: date,
        kpi_data: Dict[str, Any]
    ) -> DashboardKPI:
        """
        Create or update a dashboard KPI.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            kpi_key: Unique KPI identifier
            period_start: Period start date
            period_end: Period end date
            kpi_data: KPI data including value, target, etc.
            
        Returns:
            Created or updated DashboardKPI instance
        """
        existing = self.db.query(DashboardKPI).filter(
            and_(
                DashboardKPI.hostel_id == hostel_id if hostel_id else DashboardKPI.hostel_id.is_(None),
                DashboardKPI.kpi_key == kpi_key,
                DashboardKPI.period_start == period_start,
                DashboardKPI.period_end == period_end
            )
        ).first()
        
        # Calculate performance status
        performance_status = self._calculate_kpi_performance_status(kpi_data)
        kpi_data['performance_status'] = performance_status
        
        # Determine if on target
        is_on_target = self._is_kpi_on_target(kpi_data)
        kpi_data['is_on_target'] = is_on_target
        
        if existing:
            for key, value in kpi_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        kpi = DashboardKPI(
            hostel_id=hostel_id,
            kpi_key=kpi_key,
            period_start=period_start,
            period_end=period_end,
            **kpi_data
        )
        
        self.db.add(kpi)
        self.db.commit()
        self.db.refresh(kpi)
        
        return kpi
    
    def get_kpi(
        self,
        hostel_id: Optional[UUID],
        kpi_key: str,
        period_start: date,
        period_end: date
    ) -> Optional[DashboardKPI]:
        """Get a specific KPI."""
        return self.db.query(DashboardKPI).filter(
            and_(
                DashboardKPI.hostel_id == hostel_id if hostel_id else DashboardKPI.hostel_id.is_(None),
                DashboardKPI.kpi_key == kpi_key,
                DashboardKPI.period_start == period_start,
                DashboardKPI.period_end == period_end
            )
        ).first()
    
    def get_kpis_by_category(
        self,
        hostel_id: Optional[UUID],
        category: str,
        period_start: date,
        period_end: date
    ) -> List[DashboardKPI]:
        """Get all KPIs in a category."""
        query = QueryBuilder(DashboardKPI, self.db)
        
        if hostel_id:
            query = query.where(DashboardKPI.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                DashboardKPI.kpi_category == category,
                DashboardKPI.period_start == period_start,
                DashboardKPI.period_end == period_end
            )
        )
        
        return query.all()
    
    def get_all_kpis_for_period(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[DashboardKPI]:
        """Get all KPIs for a period."""
        query = QueryBuilder(DashboardKPI, self.db)
        
        if hostel_id:
            query = query.where(DashboardKPI.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                DashboardKPI.period_start == period_start,
                DashboardKPI.period_end == period_end
            )
        )
        
        return query.all()
    
    def _calculate_kpi_performance_status(
        self,
        kpi_data: Dict[str, Any]
    ) -> str:
        """Calculate performance status based on value and target."""
        value = kpi_data.get('metric_value')
        target = kpi_data.get('target_value')
        good_when = kpi_data.get('good_when')
        
        if value is None or target is None:
            return 'unknown'
        
        value = float(value)
        target = float(target)
        
        # Calculate percentage of target
        if target == 0:
            return 'unknown'
        
        percentage = (value / target) * 100
        
        if good_when == 'higher_is_better':
            if percentage >= 100:
                return 'excellent'
            elif percentage >= 90:
                return 'good'
            elif percentage >= 70:
                return 'warning'
            else:
                return 'critical'
        
        elif good_when == 'lower_is_better':
            if percentage <= 100:
                return 'excellent'
            elif percentage <= 110:
                return 'good'
            elif percentage <= 130:
                return 'warning'
            else:
                return 'critical'
        
        else:  # closer_to_target
            diff_percentage = abs(100 - percentage)
            if diff_percentage <= 5:
                return 'excellent'
            elif diff_percentage <= 10:
                return 'good'
            elif diff_percentage <= 20:
                return 'warning'
            else:
                return 'critical'
    
    def _is_kpi_on_target(
        self,
        kpi_data: Dict[str, Any]
    ) -> bool:
        """Determine if KPI is on target."""
        status = kpi_data.get('performance_status', 'unknown')
        return status in ['excellent', 'good']
    
    # ==================== Time Series Metrics ====================
    
    def add_timeseries_metric(
        self,
        metric_key: str,
        hostel_id: Optional[UUID],
        data_date: date,
        value: Decimal,
        label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TimeseriesMetric:
        """Add a time series data point."""
        existing = self.db.query(TimeseriesMetric).filter(
            and_(
                TimeseriesMetric.metric_key == metric_key,
                TimeseriesMetric.hostel_id == hostel_id if hostel_id else TimeseriesMetric.hostel_id.is_(None),
                TimeseriesMetric.data_date == data_date
            )
        ).first()
        
        if existing:
            existing.value = value
            if label:
                existing.label = label
            if metadata:
                existing.metadata = metadata
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metric = TimeseriesMetric(
            metric_key=metric_key,
            hostel_id=hostel_id,
            data_date=data_date,
            value=value,
            label=label,
            metadata=metadata
        )
        
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    def get_timeseries_metrics(
        self,
        metric_key: str,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date
    ) -> List[TimeseriesMetric]:
        """Get time series metrics for a date range."""
        query = QueryBuilder(TimeseriesMetric, self.db)
        
        query = query.where(TimeseriesMetric.metric_key == metric_key)
        
        if hostel_id:
            query = query.where(TimeseriesMetric.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                TimeseriesMetric.data_date >= start_date,
                TimeseriesMetric.data_date <= end_date
            )
        ).order_by(TimeseriesMetric.data_date.asc())
        
        return query.all()
    
    def get_latest_metric_value(
        self,
        metric_key: str,
        hostel_id: Optional[UUID]
    ) -> Optional[TimeseriesMetric]:
        """Get the latest value for a metric."""
        query = QueryBuilder(TimeseriesMetric, self.db)
        
        query = query.where(TimeseriesMetric.metric_key == metric_key)
        
        if hostel_id:
            query = query.where(TimeseriesMetric.hostel_id == hostel_id)
        
        query = query.order_by(TimeseriesMetric.data_date.desc())
        
        return query.first()
    
    def calculate_metric_trend(
        self,
        metric_key: str,
        hostel_id: Optional[UUID],
        days: int = 30
    ) -> Dict[str, Any]:
        """Calculate trend for a metric over recent days."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        metrics = self.get_timeseries_metrics(
            metric_key, hostel_id, start_date, end_date
        )
        
        if len(metrics) < 2:
            return {
                'direction': 'stable',
                'percentage_change': 0,
                'data_points': len(metrics),
            }
        
        values = [float(m.value) for m in metrics]
        
        # Compare first half to second half
        mid_point = len(values) // 2
        first_half_avg = sum(values[:mid_point]) / mid_point
        second_half_avg = sum(values[mid_point:]) / (len(values) - mid_point)
        
        if first_half_avg == 0:
            percentage_change = 0
        else:
            percentage_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        if percentage_change > 5:
            direction = 'up'
        elif percentage_change < -5:
            direction = 'down'
        else:
            direction = 'stable'
        
        return {
            'direction': direction,
            'percentage_change': round(percentage_change, 2),
            'data_points': len(metrics),
            'latest_value': float(metrics[-1].value),
        }
    
    # ==================== Dashboard Widgets ====================
    
    def create_or_update_widget(
        self,
        user_id: Optional[UUID],
        role: Optional[str],
        hostel_id: Optional[UUID],
        widget_data: Dict[str, Any]
    ) -> DashboardWidget:
        """Create or update a dashboard widget configuration."""
        widget_id = widget_data.get('widget_id')
        
        existing = self.db.query(DashboardWidget).filter(
            and_(
                DashboardWidget.user_id == user_id if user_id else DashboardWidget.user_id.is_(None),
                DashboardWidget.role == role if role else DashboardWidget.role.is_(None),
                DashboardWidget.hostel_id == hostel_id if hostel_id else DashboardWidget.hostel_id.is_(None),
                DashboardWidget.widget_id == widget_id
            )
        ).first()
        
        if existing:
            for key, value in widget_data.items():
                if key != 'widget_id':
                    setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        widget = DashboardWidget(
            user_id=user_id,
            role=role,
            hostel_id=hostel_id,
            **widget_data
        )
        
        self.db.add(widget)
        self.db.commit()
        self.db.refresh(widget)
        
        return widget
    
    def get_user_widgets(
        self,
        user_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> List[DashboardWidget]:
        """Get all widgets for a user."""
        query = QueryBuilder(DashboardWidget, self.db)
        
        query = query.where(DashboardWidget.user_id == user_id)
        
        if hostel_id:
            query = query.where(DashboardWidget.hostel_id == hostel_id)
        
        query = query.where(DashboardWidget.is_visible == True)
        query = query.order_by(DashboardWidget.position.asc())
        
        return query.all()
    
    def get_role_widgets(
        self,
        role: str,
        hostel_id: Optional[UUID] = None
    ) -> List[DashboardWidget]:
        """Get default widgets for a role."""
        query = QueryBuilder(DashboardWidget, self.db)
        
        query = query.where(DashboardWidget.role == role)
        query = query.where(DashboardWidget.user_id.is_(None))
        
        if hostel_id:
            query = query.where(DashboardWidget.hostel_id == hostel_id)
        
        query = query.where(DashboardWidget.is_visible == True)
        query = query.order_by(DashboardWidget.position.asc())
        
        return query.all()
    
    def update_widget_position(
        self,
        widget_id: UUID,
        new_position: int
    ) -> Optional[DashboardWidget]:
        """Update widget position/order."""
        widget = self.db.query(DashboardWidget).filter(
            DashboardWidget.id == widget_id
        ).first()
        
        if not widget:
            return None
        
        widget.position = new_position
        
        self.db.commit()
        self.db.refresh(widget)
        
        return widget
    
    def toggle_widget_visibility(
        self,
        widget_id: UUID
    ) -> Optional[DashboardWidget]:
        """Toggle widget visibility."""
        widget = self.db.query(DashboardWidget).filter(
            DashboardWidget.id == widget_id
        ).first()
        
        if not widget:
            return None
        
        widget.is_visible = not widget.is_visible
        
        self.db.commit()
        self.db.refresh(widget)
        
        return widget
    
    def delete_widget(
        self,
        widget_id: UUID
    ) -> bool:
        """Delete a widget."""
        widget = self.db.query(DashboardWidget).filter(
            DashboardWidget.id == widget_id
        ).first()
        
        if not widget:
            return False
        
        self.db.delete(widget)
        self.db.commit()
        
        return True
    
    # ==================== Alert Notifications ====================
    
    def create_alert(
        self,
        hostel_id: Optional[UUID],
        alert_data: Dict[str, Any]
    ) -> AlertNotification:
        """Create a new alert notification."""
        alert = AlertNotification(
            hostel_id=hostel_id,
            **alert_data
        )
        
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        
        return alert
    
    def get_active_alerts(
        self,
        hostel_id: Optional[UUID],
        severity: Optional[str] = None
    ) -> List[AlertNotification]:
        """Get active (non-dismissed, non-expired) alerts."""
        query = QueryBuilder(AlertNotification, self.db)
        
        if hostel_id:
            query = query.where(AlertNotification.hostel_id == hostel_id)
        
        query = query.where(AlertNotification.is_dismissed == False)
        
        # Not expired
        query = query.where(
            or_(
                AlertNotification.expires_at.is_(None),
                AlertNotification.expires_at > datetime.utcnow()
            )
        )
        
        if severity:
            query = query.where(AlertNotification.severity == severity)
        
        query = query.order_by(
            case(
                (AlertNotification.severity == 'critical', 1),
                (AlertNotification.severity == 'error', 2),
                (AlertNotification.severity == 'warning', 3),
                else_=4
            ),
            AlertNotification.created_at.desc()
        )
        
        return query.all()
    
    def dismiss_alert(
        self,
        alert_id: UUID,
        dismissed_by: UUID
    ) -> Optional[AlertNotification]:
        """Dismiss an alert."""
        alert = self.db.query(AlertNotification).filter(
            AlertNotification.id == alert_id
        ).first()
        
        if not alert:
            return None
        
        alert.is_dismissed = True
        alert.dismissed_at = datetime.utcnow()
        alert.dismissed_by = dismissed_by
        
        self.db.commit()
        self.db.refresh(alert)
        
        return alert
    
    def cleanup_expired_alerts(
        self,
        before_date: Optional[datetime] = None
    ) -> int:
        """Delete expired and old dismissed alerts."""
        if not before_date:
            before_date = datetime.utcnow()
        
        count = self.db.query(AlertNotification).filter(
            or_(
                AlertNotification.expires_at < before_date,
                and_(
                    AlertNotification.is_dismissed == True,
                    AlertNotification.dismissed_at < (before_date - timedelta(days=30))
                )
            )
        ).delete()
        
        self.db.commit()
        
        return count
    
    # ==================== Quick Stats ====================
    
    def create_or_update_quick_stats(
        self,
        hostel_id: Optional[UUID],
        snapshot_date: date,
        stats_data: Dict[str, Any]
    ) -> QuickStats:
        """Create or update quick stats snapshot."""
        existing = self.db.query(QuickStats).filter(
            and_(
                QuickStats.hostel_id == hostel_id if hostel_id else QuickStats.hostel_id.is_(None),
                QuickStats.snapshot_date == snapshot_date
            )
        ).first()
        
        if existing:
            for key, value in stats_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        stats = QuickStats(
            hostel_id=hostel_id,
            snapshot_date=snapshot_date,
            **stats_data
        )
        
        self.db.add(stats)
        self.db.commit()
        self.db.refresh(stats)
        
        return stats
    
    def get_quick_stats(
        self,
        hostel_id: Optional[UUID],
        snapshot_date: Optional[date] = None
    ) -> Optional[QuickStats]:
        """Get quick stats for a specific date."""
        if not snapshot_date:
            snapshot_date = date.today()
        
        return self.db.query(QuickStats).filter(
            and_(
                QuickStats.hostel_id == hostel_id if hostel_id else QuickStats.hostel_id.is_(None),
                QuickStats.snapshot_date == snapshot_date
            )
        ).first()
    
    def get_quick_stats_history(
        self,
        hostel_id: Optional[UUID],
        days: int = 7
    ) -> List[QuickStats]:
        """Get quick stats history for recent days."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        query = QueryBuilder(QuickStats, self.db)
        
        if hostel_id:
            query = query.where(QuickStats.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                QuickStats.snapshot_date >= start_date,
                QuickStats.snapshot_date <= end_date
            )
        ).order_by(QuickStats.snapshot_date.asc())
        
        return query.all()
    
    # ==================== Role-Specific Dashboard ====================
    
    def create_or_update_role_dashboard(
        self,
        user_id: UUID,
        hostel_id: Optional[UUID],
        role: str,
        dashboard_data: Dict[str, Any]
    ) -> RoleSpecificDashboard:
        """Create or update role-specific dashboard configuration."""
        existing = self.db.query(RoleSpecificDashboard).filter(
            and_(
                RoleSpecificDashboard.user_id == user_id,
                RoleSpecificDashboard.hostel_id == hostel_id if hostel_id else RoleSpecificDashboard.hostel_id.is_(None)
            )
        ).first()
        
        if existing:
            for key, value in dashboard_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        dashboard = RoleSpecificDashboard(
            user_id=user_id,
            hostel_id=hostel_id,
            role=role,
            **dashboard_data
        )
        
        self.db.add(dashboard)
        self.db.commit()
        self.db.refresh(dashboard)
        
        return dashboard
    
    def get_role_dashboard(
        self,
        user_id: UUID,
        hostel_id: Optional[UUID]
    ) -> Optional[RoleSpecificDashboard]:
        """Get role-specific dashboard for a user."""
        return self.db.query(RoleSpecificDashboard).filter(
            and_(
                RoleSpecificDashboard.user_id == user_id,
                RoleSpecificDashboard.hostel_id == hostel_id if hostel_id else RoleSpecificDashboard.hostel_id.is_(None)
            )
        ).first()