# app/repositories/supervisor/supervisor_dashboard_repository.py
"""
Supervisor Dashboard Repository - Dashboard data and metrics.

Handles dashboard metrics, alerts, quick actions, schedules,
and performance indicators for supervisor interface.
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload

from app.models.supervisor.supervisor_dashboard import (
    DashboardMetrics,
    DashboardAlert,
    QuickAction,
    TodaySchedule,
    PerformanceIndicator,
)
from app.models.supervisor.supervisor import Supervisor
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import ResourceNotFoundError
from app.core1.logging import logger


class SupervisorDashboardRepository(BaseRepository[DashboardMetrics]):
    """
    Supervisor dashboard repository for real-time metrics.
    
    Manages dashboard data, alerts, quick actions, schedules,
    and performance indicators with caching and optimization.
    """
    
    def __init__(self, db: Session):
        """Initialize dashboard repository."""
        super().__init__(DashboardMetrics, db)
        self.db = db
    
    # ==================== Dashboard Metrics ====================
    
    def get_or_create_metrics(
        self,
        supervisor_id: str,
        hostel_id: str
    ) -> DashboardMetrics:
        """Get or create dashboard metrics for supervisor."""
        metrics = self.db.query(DashboardMetrics).filter(
            DashboardMetrics.supervisor_id == supervisor_id
        ).first()
        
        if not metrics:
            metrics = DashboardMetrics(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                next_refresh_at=datetime.utcnow() + timedelta(minutes=5)
            )
            self.db.add(metrics)
            self.db.commit()
            self.db.refresh(metrics)
        
        return metrics
    
    def update_metrics(
        self,
        supervisor_id: str,
        metrics_data: Dict[str, Any],
        refresh_interval_minutes: int = 5
    ) -> DashboardMetrics:
        """
        Update dashboard metrics with new data.
        
        Args:
            supervisor_id: Supervisor ID
            metrics_data: Metrics data dictionary
            refresh_interval_minutes: Next refresh interval
            
        Returns:
            Updated metrics
        """
        metrics = self.db.query(DashboardMetrics).filter(
            DashboardMetrics.supervisor_id == supervisor_id
        ).first()
        
        if not metrics:
            raise ResourceNotFoundError(
                f"Metrics not found for supervisor {supervisor_id}"
            )
        
        # Update all provided metrics
        for key, value in metrics_data.items():
            if hasattr(metrics, key):
                setattr(metrics, key, value)
        
        metrics.last_calculated = datetime.utcnow()
        metrics.next_refresh_at = (
            datetime.utcnow() + timedelta(minutes=refresh_interval_minutes)
        )
        
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def refresh_metrics(
        self,
        supervisor_id: str,
        hostel_id: str
    ) -> DashboardMetrics:
        """
        Refresh all dashboard metrics for supervisor.
        
        This would integrate with various modules to fetch real-time data.
        For now, providing structure for implementation.
        """
        # Get or create metrics
        metrics = self.get_or_create_metrics(supervisor_id, hostel_id)
        
        # TODO: Integrate with actual modules to fetch data
        # This is a placeholder structure
        
        updated_data = {
            'last_calculated': datetime.utcnow(),
            'next_refresh_at': datetime.utcnow() + timedelta(minutes=5)
        }
        
        return self.update_metrics(supervisor_id, updated_data)
    
    def should_refresh_metrics(
        self,
        supervisor_id: str
    ) -> bool:
        """Check if metrics need refreshing."""
        metrics = self.db.query(DashboardMetrics).filter(
            DashboardMetrics.supervisor_id == supervisor_id
        ).first()
        
        if not metrics:
            return True
        
        return datetime.utcnow() >= metrics.next_refresh_at
    
    # ==================== Dashboard Alerts ====================
    
    def create_alert(
        self,
        supervisor_id: str,
        hostel_id: str,
        alert_type: str,
        title: str,
        message: str,
        action_required: bool = False,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        is_dismissible: bool = True,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        priority: int = 0
    ) -> DashboardAlert:
        """
        Create dashboard alert for supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            hostel_id: Hostel ID
            alert_type: Alert type (urgent, warning, info, success)
            title: Alert title
            message: Alert message
            action_required: Action required flag
            action_url: Action URL
            action_label: Action button label
            expires_at: Alert expiration
            is_dismissible: Can be dismissed
            related_entity_type: Related entity type
            related_entity_id: Related entity ID
            metadata: Additional metadata
            priority: Alert priority
            
        Returns:
            Created alert
        """
        alert = DashboardAlert(
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            alert_type=alert_type,
            title=title,
            message=message,
            action_required=action_required,
            action_url=action_url,
            action_label=action_label,
            expires_at=expires_at,
            is_dismissible=is_dismissible,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            metadata=metadata or {},
            priority=priority
        )
        
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        
        logger.info(f"Created {alert_type} alert for supervisor {supervisor_id}")
        return alert
    
    def get_active_alerts(
        self,
        supervisor_id: str,
        alert_type: Optional[str] = None,
        action_required_only: bool = False,
        limit: int = 50
    ) -> List[DashboardAlert]:
        """
        Get active alerts for supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            alert_type: Filter by alert type
            action_required_only: Only alerts requiring action
            limit: Maximum results
            
        Returns:
            List of active alerts
        """
        query = self.db.query(DashboardAlert).filter(
            and_(
                DashboardAlert.supervisor_id == supervisor_id,
                DashboardAlert.dismissed == False,
                or_(
                    DashboardAlert.expires_at.is_(None),
                    DashboardAlert.expires_at > datetime.utcnow()
                )
            )
        )
        
        if alert_type:
            query = query.filter(DashboardAlert.alert_type == alert_type)
        
        if action_required_only:
            query = query.filter(DashboardAlert.action_required == True)
        
        return query.order_by(
            DashboardAlert.priority.desc(),
            DashboardAlert.created_at.desc()
        ).limit(limit).all()
    
    def dismiss_alert(
        self,
        alert_id: str
    ) -> DashboardAlert:
        """Dismiss dashboard alert."""
        alert = self.db.query(DashboardAlert).filter(
            DashboardAlert.id == alert_id
        ).first()
        
        if not alert:
            raise ResourceNotFoundError(f"Alert {alert_id} not found")
        
        if not alert.is_dismissible:
            raise ValueError("Alert is not dismissible")
        
        alert.dismissed = True
        alert.dismissed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(alert)
        
        return alert
    
    def cleanup_expired_alerts(
        self,
        supervisor_id: Optional[str] = None
    ) -> int:
        """Remove expired alerts."""
        query = self.db.query(DashboardAlert).filter(
            and_(
                DashboardAlert.expires_at.isnot(None),
                DashboardAlert.expires_at <= datetime.utcnow()
            )
        )
        
        if supervisor_id:
            query = query.filter(
                DashboardAlert.supervisor_id == supervisor_id
            )
        
        count = query.delete()
        self.db.commit()
        
        return count
    
    # ==================== Quick Actions ====================
    
    def create_quick_action(
        self,
        supervisor_id: str,
        action_id: str,
        label: str,
        icon: str,
        url: str,
        category: str = "general",
        display_order: int = 0,
        badge_count: Optional[int] = None,
        badge_type: Optional[str] = None,
        requires_permission: Optional[str] = None
    ) -> QuickAction:
        """Create quick action for supervisor dashboard."""
        action = QuickAction(
            supervisor_id=supervisor_id,
            action_id=action_id,
            label=label,
            icon=icon,
            url=url,
            category=category,
            display_order=display_order,
            badge_count=badge_count,
            badge_type=badge_type,
            requires_permission=requires_permission
        )
        
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        
        return action
    
    def get_quick_actions(
        self,
        supervisor_id: str,
        category: Optional[str] = None,
        visible_only: bool = True
    ) -> List[QuickAction]:
        """Get quick actions for supervisor."""
        query = self.db.query(QuickAction).filter(
            QuickAction.supervisor_id == supervisor_id
        )
        
        if category:
            query = query.filter(QuickAction.category == category)
        
        if visible_only:
            query = query.filter(
                and_(
                    QuickAction.is_visible == True,
                    QuickAction.is_enabled == True
                )
            )
        
        return query.order_by(
            QuickAction.category,
            QuickAction.display_order
        ).all()
    
    def update_quick_action_badge(
        self,
        supervisor_id: str,
        action_id: str,
        badge_count: int,
        badge_type: Optional[str] = None
    ) -> Optional[QuickAction]:
        """Update quick action badge count."""
        action = self.db.query(QuickAction).filter(
            and_(
                QuickAction.supervisor_id == supervisor_id,
                QuickAction.action_id == action_id
            )
        ).first()
        
        if action:
            action.badge_count = badge_count
            if badge_type:
                action.badge_type = badge_type
            action.last_updated = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(action)
        
        return action
    
    # ==================== Today's Schedule ====================
    
    def get_or_create_schedule(
        self,
        supervisor_id: str,
        hostel_id: str,
        schedule_date: date = None
    ) -> TodaySchedule:
        """Get or create today's schedule."""
        if schedule_date is None:
            schedule_date = date.today()
        
        schedule = self.db.query(TodaySchedule).filter(
            and_(
                TodaySchedule.supervisor_id == supervisor_id,
                TodaySchedule.schedule_date == schedule_date
            )
        ).first()
        
        if not schedule:
            schedule = TodaySchedule(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                schedule_date=schedule_date
            )
            self.db.add(schedule)
            self.db.commit()
            self.db.refresh(schedule)
        
        return schedule
    
    def update_schedule(
        self,
        supervisor_id: str,
        schedule_date: date,
        schedule_data: Dict[str, Any]
    ) -> TodaySchedule:
        """Update schedule with new data."""
        schedule = self.db.query(TodaySchedule).filter(
            and_(
                TodaySchedule.supervisor_id == supervisor_id,
                TodaySchedule.schedule_date == schedule_date
            )
        ).first()
        
        if not schedule:
            raise ResourceNotFoundError(
                f"Schedule not found for {supervisor_id} on {schedule_date}"
            )
        
        for key, value in schedule_data.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)
        
        self.db.commit()
        self.db.refresh(schedule)
        
        return schedule
    
    def mark_attendance_completed(
        self,
        supervisor_id: str,
        schedule_date: date = None
    ) -> TodaySchedule:
        """Mark attendance as completed for the day."""
        if schedule_date is None:
            schedule_date = date.today()
        
        schedule = self.get_or_create_schedule(supervisor_id, None, schedule_date)
        schedule.attendance_marked = True
        schedule.completed_items += 1
        schedule.pending_items = max(0, schedule.pending_items - 1)
        
        self.db.commit()
        self.db.refresh(schedule)
        
        return schedule
    
    # ==================== Performance Indicators ====================
    
    def create_performance_indicator(
        self,
        supervisor_id: str,
        measurement_date: date,
        period_type: str = "daily",
        **metrics
    ) -> PerformanceIndicator:
        """Create performance indicator record."""
        indicator = PerformanceIndicator(
            supervisor_id=supervisor_id,
            measurement_date=measurement_date,
            period_type=period_type,
            **metrics
        )
        
        self.db.add(indicator)
        self.db.commit()
        self.db.refresh(indicator)
        
        return indicator
    
    def get_latest_performance_indicator(
        self,
        supervisor_id: str,
        period_type: str = "daily"
    ) -> Optional[PerformanceIndicator]:
        """Get latest performance indicator."""
        return self.db.query(PerformanceIndicator).filter(
            and_(
                PerformanceIndicator.supervisor_id == supervisor_id,
                PerformanceIndicator.period_type == period_type
            )
        ).order_by(
            PerformanceIndicator.measurement_date.desc()
        ).first()
    
    def get_performance_trend(
        self,
        supervisor_id: str,
        days: int = 30,
        period_type: str = "daily"
    ) -> List[PerformanceIndicator]:
        """Get performance trend over days."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        return self.db.query(PerformanceIndicator).filter(
            and_(
                PerformanceIndicator.supervisor_id == supervisor_id,
                PerformanceIndicator.period_type == period_type,
                PerformanceIndicator.measurement_date >= start_date,
                PerformanceIndicator.measurement_date <= end_date
            )
        ).order_by(
            PerformanceIndicator.measurement_date
        ).all()