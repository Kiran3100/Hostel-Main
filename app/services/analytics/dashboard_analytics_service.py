"""
Dashboard analytics service (generic dashboard KPIs, widgets, alerts, quick stats).

Optimizations:
- Added role-based dashboard customization
- Implemented widget-based architecture
- Enhanced alert system with prioritization
- Added real-time metrics support
- Improved caching strategy
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, timedelta, datetime
from enum import Enum
import logging

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.analytics import DashboardAnalyticsRepository
from app.models.analytics.dashboard_analytics import QuickStats as QuickStatsModel
from app.schemas.analytics.dashboard_analytics import (
    KPIResponse,
    QuickStats,
    TimeseriesPoint,
    AlertNotification,
    DashboardWidget,
    DashboardMetrics,
    RoleSpecificDashboard,
)

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User roles for dashboard customization."""
    ADMIN = "admin"
    MANAGER = "manager"
    SUPERVISOR = "supervisor"
    STAFF = "staff"
    VIEWER = "viewer"


class WidgetType(str, Enum):
    """Dashboard widget types."""
    KPI = "kpi"
    CHART = "chart"
    TABLE = "table"
    ALERT = "alert"
    QUICK_STAT = "quick_stat"
    TREND = "trend"


class DashboardAnalyticsService(BaseService[QuickStatsModel, DashboardAnalyticsRepository]):
    """
    Service for generic dashboard analytics and role-specific dashboards.
    
    Features:
    - Role-based dashboard layouts
    - Customizable widgets
    - Real-time alerts
    - KPI tracking
    - Quick statistics
    """

    # Default time ranges
    DEFAULT_RANGE_DAYS = 30
    
    # Cache TTL
    CACHE_TTL = 180  # 3 minutes for dashboard data
    
    # Alert priorities
    ALERT_PRIORITIES = {
        "critical": 1,
        "high": 2,
        "medium": 3,
        "low": 4,
    }

    def __init__(self, repository: DashboardAnalyticsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._cache = {}
        self._cache_timestamps = {}

    def get_dashboard_metrics(
        self,
        scope_type: str,
        scope_id: Optional[UUID],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force_refresh: bool = False,
    ) -> ServiceResult[DashboardMetrics]:
        """
        Get dashboard metrics for a given scope.
        
        Args:
            scope_type: Type of scope (hostel, platform, user)
            scope_id: Scope identifier
            start_date: Start of date range
            end_date: End of date range
            force_refresh: Bypass cache
            
        Returns:
            ServiceResult containing dashboard metrics
        """
        try:
            # Set default dates
            end_date = end_date or date.today()
            start_date = start_date or (end_date - timedelta(days=self.DEFAULT_RANGE_DAYS))
            
            # Validate scope type
            if scope_type not in ("hostel", "platform", "user", "supervisor"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid scope type: {scope_type}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check cache
            cache_key = f"metrics_{scope_type}_{scope_id}_{start_date}_{end_date}"
            if not force_refresh and self._is_cache_valid(cache_key):
                logger.debug(f"Returning cached metrics for {scope_type}:{scope_id}")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch metrics
            metrics = self.repository.get_dashboard_metrics(
                scope_type, scope_id, start_date, end_date
            )
            
            if not metrics:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No metrics found for {scope_type}:{scope_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance metrics
            metrics = self._enhance_metrics(metrics)
            
            # Cache result
            self._update_cache(cache_key, metrics)
            
            return ServiceResult.success(
                metrics,
                message="Dashboard metrics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {str(e)}")
            return self._handle_exception(e, "get dashboard metrics")

    def get_role_dashboard(
        self,
        role: str,
        user_id: UUID,
        scope_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_widgets: bool = True,
    ) -> ServiceResult[RoleSpecificDashboard]:
        """
        Get role-specific dashboard.
        
        Args:
            role: User role
            user_id: User UUID
            scope_id: Optional scope filter (e.g., hostel_id)
            start_date: Start of date range
            end_date: End of date range
            include_widgets: Include widget definitions
            
        Returns:
            ServiceResult containing role-specific dashboard
        """
        try:
            # Validate role
            try:
                user_role = UserRole(role.lower())
            except ValueError:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid role: {role}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Set default dates
            end_date = end_date or date.today()
            start_date = start_date or (end_date - timedelta(days=self.DEFAULT_RANGE_DAYS))
            
            # Fetch dashboard data
            dashboard = self.repository.get_role_dashboard(
                role, user_id, scope_id, start_date, end_date
            )
            
            if not dashboard:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No dashboard data found for role {role}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Add widgets if requested
            if include_widgets:
                dashboard.widgets = self._get_widgets_for_role(user_role, dashboard)
            
            # Add personalization
            dashboard = self._personalize_dashboard(dashboard, user_id)
            
            return ServiceResult.success(
                dashboard,
                message=f"Dashboard for {role} retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting role dashboard: {str(e)}")
            return self._handle_exception(e, "get role dashboard", user_id)

    def get_active_alerts(
        self,
        scope_type: str,
        scope_id: Optional[UUID],
        severity_filter: Optional[str] = None,
        limit: int = 50,
    ) -> ServiceResult[List[AlertNotification]]:
        """
        Get active alerts for a scope.
        
        Args:
            scope_type: Type of scope
            scope_id: Scope identifier
            severity_filter: Optional severity filter
            limit: Maximum alerts to return
            
        Returns:
            ServiceResult containing active alerts
        """
        try:
            # Validate scope type
            if scope_type not in ("hostel", "platform", "user", "supervisor"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid scope type: {scope_type}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch alerts
            alerts = self.repository.get_active_alerts(scope_type, scope_id)
            
            if not alerts:
                logger.info(f"No active alerts for {scope_type}:{scope_id}")
                alerts = []
            
            # Filter by severity if specified
            if severity_filter:
                alerts = [
                    a for a in alerts
                    if hasattr(a, 'severity') and a.severity.lower() == severity_filter.lower()
                ]
            
            # Sort by priority (critical first)
            alerts.sort(
                key=lambda a: self.ALERT_PRIORITIES.get(
                    getattr(a, 'severity', 'low').lower(), 999
                )
            )
            
            # Limit results
            alerts = alerts[:limit]
            
            return ServiceResult.success(
                alerts,
                metadata={
                    "count": len(alerts),
                    "severity_filter": severity_filter,
                    "limit": limit,
                },
                message=f"Retrieved {len(alerts)} active alerts"
            )
            
        except Exception as e:
            logger.error(f"Error getting active alerts: {str(e)}")
            return self._handle_exception(e, "get dashboard alerts")

    def get_quick_stats(
        self,
        scope_type: str,
        scope_id: Optional[UUID],
    ) -> ServiceResult[QuickStats]:
        """
        Get quick statistics summary.
        
        Args:
            scope_type: Type of scope
            scope_id: Scope identifier
            
        Returns:
            ServiceResult containing quick stats
        """
        try:
            # Validate scope type
            if scope_type not in ("hostel", "platform", "user"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid scope type: {scope_type}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch quick stats
            stats = self.repository.get_quick_stats(scope_type, scope_id)
            
            if not stats:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No quick stats available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(
                stats,
                message="Quick stats retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting quick stats: {str(e)}")
            return self._handle_exception(e, "get quick stats")

    def get_kpi_timeseries(
        self,
        scope_type: str,
        scope_id: Optional[UUID],
        kpi_name: str,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
    ) -> ServiceResult[List[TimeseriesPoint]]:
        """
        Get timeseries data for a specific KPI.
        
        Args:
            scope_type: Type of scope
            scope_id: Scope identifier
            kpi_name: Name of KPI
            start_date: Start date
            end_date: End date
            granularity: Time granularity
            
        Returns:
            ServiceResult containing timeseries data
        """
        try:
            # Validate inputs
            if scope_type not in ("hostel", "platform", "user"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid scope type: {scope_type}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            if granularity not in ("hourly", "daily", "weekly", "monthly"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid granularity: {granularity}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch timeseries data
            timeseries = self.repository.get_kpi_timeseries(
                scope_type, scope_id, kpi_name, start_date, end_date, granularity
            )
            
            if not timeseries:
                logger.warning(f"No timeseries data for KPI {kpi_name}")
                timeseries = []
            
            return ServiceResult.success(
                timeseries,
                metadata={
                    "kpi_name": kpi_name,
                    "points": len(timeseries),
                    "granularity": granularity,
                },
                message=f"Retrieved {len(timeseries)} timeseries points"
            )
            
        except Exception as e:
            logger.error(f"Error getting KPI timeseries: {str(e)}")
            return self._handle_exception(e, "get KPI timeseries")

    def create_custom_widget(
        self,
        user_id: UUID,
        widget_config: Dict[str, Any],
    ) -> ServiceResult[DashboardWidget]:
        """
        Create a custom dashboard widget.
        
        Args:
            user_id: User UUID
            widget_config: Widget configuration
            
        Returns:
            ServiceResult containing created widget
        """
        try:
            # Validate widget configuration
            validation_result = self._validate_widget_config(widget_config)
            if not validation_result.success:
                return validation_result
            
            # Create widget
            widget = self.repository.create_custom_widget(user_id, widget_config)
            
            if not widget:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to create widget",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            self.db.commit()
            
            return ServiceResult.success(
                widget,
                message="Custom widget created successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating custom widget: {str(e)}")
            return self._handle_exception(e, "create custom widget")

    def update_widget_layout(
        self,
        user_id: UUID,
        layout_config: Dict[str, Any],
    ) -> ServiceResult[bool]:
        """
        Update dashboard widget layout for a user.
        
        Args:
            user_id: User UUID
            layout_config: Layout configuration
            
        Returns:
            ServiceResult indicating success
        """
        try:
            # Validate layout configuration
            if not isinstance(layout_config, dict):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Invalid layout configuration",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Update layout
            success = self.repository.update_widget_layout(user_id, layout_config)
            
            if not success:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to update layout",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            self.db.commit()
            
            # Invalidate cache for this user
            self._invalidate_user_cache(user_id)
            
            return ServiceResult.success(
                True,
                message="Widget layout updated successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating widget layout: {str(e)}")
            return self._handle_exception(e, "update widget layout")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache:
            return False
        
        if cache_key not in self._cache_timestamps:
            return False
        
        age = (datetime.utcnow() - self._cache_timestamps[cache_key]).total_seconds()
        return age < self.CACHE_TTL

    def _update_cache(self, cache_key: str, data: Any) -> None:
        """Update cache with new data."""
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = datetime.utcnow()
        
        # Limit cache size
        if len(self._cache) > 200:
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:50]
            for key in oldest_keys:
                del self._cache[key]
                del self._cache_timestamps[key]

    def _invalidate_user_cache(self, user_id: UUID) -> None:
        """Invalidate all cache entries for a user."""
        user_prefix = f"_{user_id}_"
        keys_to_remove = [k for k in self._cache.keys() if user_prefix in k]
        for key in keys_to_remove:
            del self._cache[key]
            if key in self._cache_timestamps:
                del self._cache_timestamps[key]

    def _enhance_metrics(self, metrics: DashboardMetrics) -> DashboardMetrics:
        """Enhance metrics with calculated fields."""
        # Add trend indicators
        if hasattr(metrics, 'kpis'):
            for kpi in metrics.kpis:
                if hasattr(kpi, 'current_value') and hasattr(kpi, 'previous_value'):
                    if kpi.previous_value and kpi.previous_value > 0:
                        change = (
                            (kpi.current_value - kpi.previous_value) /
                            kpi.previous_value * 100
                        )
                        kpi.change_percentage = round(change, 2)
                        kpi.trend = "up" if change > 0 else "down" if change < 0 else "stable"
        
        # Add generated timestamp
        metrics.generated_at = datetime.utcnow()
        
        return metrics

    def _get_widgets_for_role(
        self,
        role: UserRole,
        dashboard: RoleSpecificDashboard,
    ) -> List[DashboardWidget]:
        """Get default widgets for a role."""
        widgets = []
        
        # Admin gets all widgets
        if role == UserRole.ADMIN:
            widgets.extend([
                self._create_widget("platform_overview", WidgetType.KPI),
                self._create_widget("revenue_chart", WidgetType.CHART),
                self._create_widget("booking_trends", WidgetType.TREND),
                self._create_widget("active_alerts", WidgetType.ALERT),
                self._create_widget("user_analytics", WidgetType.TABLE),
            ])
        
        # Manager gets operational widgets
        elif role == UserRole.MANAGER:
            widgets.extend([
                self._create_widget("hostel_overview", WidgetType.KPI),
                self._create_widget("occupancy_chart", WidgetType.CHART),
                self._create_widget("revenue_summary", WidgetType.QUICK_STAT),
                self._create_widget("pending_tasks", WidgetType.TABLE),
            ])
        
        # Supervisor gets team-focused widgets
        elif role == UserRole.SUPERVISOR:
            widgets.extend([
                self._create_widget("team_performance", WidgetType.KPI),
                self._create_widget("task_completion", WidgetType.CHART),
                self._create_widget("complaint_status", WidgetType.TABLE),
            ])
        
        # Staff gets simplified widgets
        elif role == UserRole.STAFF:
            widgets.extend([
                self._create_widget("my_tasks", WidgetType.TABLE),
                self._create_widget("todays_summary", WidgetType.QUICK_STAT),
            ])
        
        # Viewer gets read-only widgets
        elif role == UserRole.VIEWER:
            widgets.extend([
                self._create_widget("summary_stats", WidgetType.QUICK_STAT),
                self._create_widget("trends", WidgetType.CHART),
            ])
        
        return widgets

    def _create_widget(self, widget_id: str, widget_type: WidgetType) -> DashboardWidget:
        """Create a widget definition."""
        return DashboardWidget(
            id=widget_id,
            type=widget_type.value,
            title=widget_id.replace("_", " ").title(),
            config={},
            position=None,
        )

    def _personalize_dashboard(
        self,
        dashboard: RoleSpecificDashboard,
        user_id: UUID,
    ) -> RoleSpecificDashboard:
        """Add personalization to dashboard."""
        # Fetch user preferences
        try:
            preferences = self.repository.get_user_preferences(user_id)
            if preferences:
                dashboard.preferences = preferences
        except Exception as e:
            logger.warning(f"Could not load user preferences: {str(e)}")
        
        # Add last accessed time
        dashboard.last_accessed = datetime.utcnow()
        
        return dashboard

    def _validate_widget_config(self, config: Dict[str, Any]) -> ServiceResult[bool]:
        """Validate widget configuration."""
        required_fields = ["type", "title"]
        
        for field in required_fields:
            if field not in config:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Missing required field: {field}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
        
        # Validate widget type
        try:
            WidgetType(config["type"])
        except ValueError:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid widget type: {config['type']}",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        return ServiceResult.success(True)