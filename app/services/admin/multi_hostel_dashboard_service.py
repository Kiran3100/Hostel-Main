"""
Multi-hostel admin dashboard service.

Provides portfolio-level analytics and dashboard for admins
managing multiple hostels.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.admin import MultiHostelDashboardRepository
from app.models.admin import (
    MultiHostelDashboard,
    DashboardWidget,
    DashboardSnapshot,
)
from app.schemas.admin.multi_hostel_dashboard import (
    MultiHostelDashboard as MultiHostelDashboardSchema,
    HostelQuickStats,
    AggregatedStats,
    HostelTaskSummary,
    CrossHostelComparison,
)


class MultiHostelDashboardService(
    BaseService[MultiHostelDashboard, MultiHostelDashboardRepository]
):
    """
    Service providing portfolio-level analytics for admins.
    
    Responsibilities:
    - Aggregated statistics across all managed hostels
    - Quick stats per hostel
    - Cross-hostel comparisons and rankings
    - Widget configuration
    - Dashboard snapshots for historical analysis
    """
    
    # Cache configuration
    CACHE_TTL_MINUTES = 15
    DEFAULT_PERIOD_DAYS = 30
    
    def __init__(
        self,
        repository: MultiHostelDashboardRepository,
        db_session: Session,
    ):
        """
        Initialize dashboard service.
        
        Args:
            repository: Dashboard repository
            db_session: Database session
        """
        super().__init__(repository, db_session)
    
    # =========================================================================
    # Dashboard Generation
    # =========================================================================
    
    def generate_dashboard(
        self,
        admin_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_comparison: bool = True,
        force_refresh: bool = False,
    ) -> ServiceResult[MultiHostelDashboardSchema]:
        """
        Generate (or load from cache) the multi-hostel dashboard.
        
        Args:
            admin_id: Admin user ID
            start_date: Period start date
            end_date: Period end date
            include_comparison: Include cross-hostel comparison
            force_refresh: Force cache refresh
            
        Returns:
            ServiceResult containing dashboard data
        """
        try:
            # Set default dates
            end_date = end_date or date.today()
            start_date = start_date or (end_date - timedelta(days=self.DEFAULT_PERIOD_DAYS))
            
            # Check cache if not forcing refresh
            if not force_refresh:
                cached = self._get_cached_dashboard(admin_id, start_date, end_date)
                if cached:
                    return ServiceResult.success(cached, message="Dashboard loaded from cache")
            
            # Generate fresh dashboard
            dashboard = self._generate_fresh_dashboard(
                admin_id,
                start_date,
                end_date,
                include_comparison,
            )
            
            # Cache the result
            self._cache_dashboard(admin_id, dashboard)
            
            return ServiceResult.success(
                dashboard,
                message="Dashboard generated successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "generate multi-hostel dashboard", admin_id)
    
    def refresh_dashboard(
        self,
        admin_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Force refresh of dashboard cache.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult indicating success
        """
        try:
            self.repository.invalidate_dashboard_cache(admin_id)
            self.db.commit()
            
            self._logger.info(
                "Dashboard cache refreshed",
                extra={"admin_id": str(admin_id)},
            )
            
            return ServiceResult.success(True, message="Dashboard refreshed")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "refresh dashboard", admin_id)
    
    # =========================================================================
    # Dashboard Components
    # =========================================================================
    
    def get_aggregated_stats(
        self,
        admin_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[AggregatedStats]:
        """
        Get aggregated statistics across all managed hostels.
        
        Args:
            admin_id: Admin user ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            ServiceResult containing aggregated stats
        """
        try:
            stats = self.repository.get_aggregated_stats(admin_id, start_date, end_date)
            
            return ServiceResult.success(
                stats,
                message="Aggregated stats retrieved",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get aggregated stats", admin_id)
    
    def get_hostel_quick_stats(
        self,
        admin_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[List[HostelQuickStats]]:
        """
        Get quick stats for each managed hostel.
        
        Args:
            admin_id: Admin user ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            ServiceResult containing per-hostel stats
        """
        try:
            stats = self.repository.get_quick_stats_for_admin(
                admin_id,
                start_date,
                end_date,
            )
            
            return ServiceResult.success(
                stats,
                message="Hostel stats retrieved",
                metadata={"hostel_count": len(stats)},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get hostel quick stats", admin_id)
    
    def get_task_summary(
        self,
        admin_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[HostelTaskSummary]:
        """
        Get task summary across all hostels.
        
        Args:
            admin_id: Admin user ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            ServiceResult containing task summary
        """
        try:
            summary = self.repository.get_task_summary(admin_id, start_date, end_date)
            
            return ServiceResult.success(
                summary,
                message="Task summary retrieved",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get task summary", admin_id)
    
    def get_cross_hostel_comparison(
        self,
        admin_id: UUID,
        start_date: date,
        end_date: date,
        metrics: Optional[List[str]] = None,
    ) -> ServiceResult[CrossHostelComparison]:
        """
        Get cross-hostel comparison and rankings.
        
        Args:
            admin_id: Admin user ID
            start_date: Period start
            end_date: Period end
            metrics: Specific metrics to compare
            
        Returns:
            ServiceResult containing comparison data
        """
        try:
            comparison = self.repository.get_cross_hostel_comparison(
                admin_id,
                start_date,
                end_date,
                metrics=metrics,
            )
            
            return ServiceResult.success(
                comparison,
                message="Cross-hostel comparison generated",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get cross hostel comparison", admin_id)
    
    # =========================================================================
    # Widget Management
    # =========================================================================
    
    def get_widgets(
        self,
        admin_id: UUID,
    ) -> ServiceResult[List[DashboardWidget]]:
        """
        Return configured widgets for the admin dashboard.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult containing widget configurations
        """
        try:
            widgets = self.repository.get_dashboard_widgets(admin_id)
            
            return ServiceResult.success(
                widgets,
                message="Widgets retrieved",
                metadata={"count": len(widgets)},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get dashboard widgets", admin_id)
    
    def save_widget_config(
        self,
        admin_id: UUID,
        widgets: List[Dict[str, Any]],
    ) -> ServiceResult[bool]:
        """
        Save widget configuration for the admin.
        
        Args:
            admin_id: Admin user ID
            widgets: Widget configurations
            
        Returns:
            ServiceResult indicating success
        """
        try:
            self.repository.save_dashboard_widgets(admin_id, widgets)
            self.db.commit()
            
            self._logger.info(
                "Dashboard widgets saved",
                extra={
                    "admin_id": str(admin_id),
                    "widget_count": len(widgets),
                },
            )
            
            return ServiceResult.success(True, message="Widgets saved")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "save widget config", admin_id)
    
    def update_widget(
        self,
        widget_id: UUID,
        widget_config: Dict[str, Any],
    ) -> ServiceResult[DashboardWidget]:
        """
        Update a single widget configuration.
        
        Args:
            widget_id: Widget ID
            widget_config: New widget configuration
            
        Returns:
            ServiceResult containing updated widget
        """
        try:
            widget = self.repository.update_widget(widget_id, widget_config)
            self.db.commit()
            
            return ServiceResult.success(widget, message="Widget updated")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update widget", widget_id)
    
    def delete_widget(
        self,
        widget_id: UUID,
        admin_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete a dashboard widget.
        
        Args:
            widget_id: Widget ID
            admin_id: Admin user ID (for validation)
            
        Returns:
            ServiceResult indicating success
        """
        try:
            self.repository.delete_widget(widget_id, admin_id)
            self.db.commit()
            
            self._logger.info(
                "Widget deleted",
                extra={
                    "widget_id": str(widget_id),
                    "admin_id": str(admin_id),
                },
            )
            
            return ServiceResult.success(True, message="Widget deleted")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete widget", widget_id)
    
    # =========================================================================
    # Snapshots
    # =========================================================================
    
    def create_snapshot(
        self,
        admin_id: UUID,
        snapshot_data: Optional[Dict[str, Any]] = None,
        snapshot_name: Optional[str] = None,
    ) -> ServiceResult[DashboardSnapshot]:
        """
        Create a dashboard snapshot for archival/comparison.
        
        Args:
            admin_id: Admin user ID
            snapshot_data: Snapshot data (if None, captures current dashboard)
            snapshot_name: Optional snapshot name
            
        Returns:
            ServiceResult containing created snapshot
        """
        try:
            # If no data provided, capture current dashboard
            if not snapshot_data:
                dashboard = self.generate_dashboard(admin_id, include_comparison=True)
                if not dashboard.is_success:
                    return dashboard
                
                snapshot_data = dashboard.data.model_dump() if hasattr(dashboard.data, 'model_dump') else {}
            
            # Add metadata
            snapshot_data['snapshot_name'] = snapshot_name or f"Snapshot {datetime.utcnow().isoformat()}"
            snapshot_data['created_at'] = datetime.utcnow().isoformat()
            
            snapshot = self.repository.create_dashboard_snapshot(
                admin_id=admin_id,
                snapshot=snapshot_data,
            )
            self.db.commit()
            
            self._logger.info(
                "Dashboard snapshot created",
                extra={
                    "admin_id": str(admin_id),
                    "snapshot_id": str(snapshot.id),
                },
            )
            
            return ServiceResult.success(snapshot, message="Snapshot created")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create dashboard snapshot", admin_id)
    
    def get_snapshots(
        self,
        admin_id: UUID,
        limit: int = 10,
    ) -> ServiceResult[List[DashboardSnapshot]]:
        """
        Get dashboard snapshots for an admin.
        
        Args:
            admin_id: Admin user ID
            limit: Maximum snapshots to return
            
        Returns:
            ServiceResult containing snapshots
        """
        try:
            snapshots = self.repository.get_dashboard_snapshots(admin_id, limit=limit)
            
            return ServiceResult.success(
                snapshots,
                message="Snapshots retrieved",
                metadata={"count": len(snapshots)},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get dashboard snapshots", admin_id)
    
    def compare_snapshots(
        self,
        snapshot_id_1: UUID,
        snapshot_id_2: UUID,
        admin_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare two dashboard snapshots.
        
        Args:
            snapshot_id_1: First snapshot ID
            snapshot_id_2: Second snapshot ID
            admin_id: Admin user ID (for validation)
            
        Returns:
            ServiceResult containing comparison data
        """
        try:
            comparison = self.repository.compare_snapshots(
                snapshot_id_1,
                snapshot_id_2,
                admin_id,
            )
            
            return ServiceResult.success(
                comparison,
                message="Snapshot comparison completed",
            )
            
        except Exception as e:
            return self._handle_exception(e, "compare snapshots")
    
    def delete_snapshot(
        self,
        snapshot_id: UUID,
        admin_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete a dashboard snapshot.
        
        Args:
            snapshot_id: Snapshot ID
            admin_id: Admin user ID (for validation)
            
        Returns:
            ServiceResult indicating success
        """
        try:
            self.repository.delete_snapshot(snapshot_id, admin_id)
            self.db.commit()
            
            self._logger.info(
                "Snapshot deleted",
                extra={
                    "snapshot_id": str(snapshot_id),
                    "admin_id": str(admin_id),
                },
            )
            
            return ServiceResult.success(True, message="Snapshot deleted")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete snapshot", snapshot_id)
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _generate_fresh_dashboard(
        self,
        admin_id: UUID,
        start_date: date,
        end_date: date,
        include_comparison: bool,
    ) -> MultiHostelDashboardSchema:
        """
        Generate fresh dashboard data.
        
        Args:
            admin_id: Admin user ID
            start_date: Period start
            end_date: Period end
            include_comparison: Include comparison data
            
        Returns:
            Dashboard schema
        """
        # Get aggregated stats
        aggregated = self.repository.get_aggregated_stats(admin_id, start_date, end_date)
        
        # Get per-hostel quick stats
        quick_stats = self.repository.get_quick_stats_for_admin(admin_id, start_date, end_date)
        
        # Get task summary
        task_summary = self.repository.get_task_summary(admin_id, start_date, end_date)
        
        # Get cross-hostel comparison if requested
        comparison = None
        if include_comparison:
            comparison = self.repository.get_cross_hostel_comparison(
                admin_id,
                start_date,
                end_date,
            )
        
        # Build schema
        schema = MultiHostelDashboardSchema(
            admin_id=admin_id,
            generated_at=datetime.utcnow(),
            period_start=start_date,
            period_end=end_date,
            aggregated_stats=aggregated,
            hostels=quick_stats,
            task_summary=task_summary,
            cross_hostel_comparison=comparison,
        )
        
        return schema
    
    def _get_cached_dashboard(
        self,
        admin_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Optional[MultiHostelDashboardSchema]:
        """
        Get dashboard from cache if available and fresh.
        
        Args:
            admin_id: Admin user ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            Cached dashboard or None
        """
        try:
            cached = self.repository.get_cached_dashboard(
                admin_id,
                start_date,
                end_date,
            )
            
            if not cached:
                return None
            
            # Check if cache is still fresh
            cache_age = datetime.utcnow() - cached.cached_at
            if cache_age > timedelta(minutes=self.CACHE_TTL_MINUTES):
                return None
            
            return cached.data
            
        except Exception as e:
            self._logger.warning(
                f"Failed to retrieve cached dashboard: {str(e)}",
                exc_info=True,
            )
            return None
    
    def _cache_dashboard(
        self,
        admin_id: UUID,
        dashboard: MultiHostelDashboardSchema,
    ) -> None:
        """
        Cache dashboard data.
        
        Args:
            admin_id: Admin user ID
            dashboard: Dashboard schema to cache
        """
        try:
            self.repository.cache_dashboard(admin_id, dashboard)
            self.db.commit()
            
        except Exception as e:
            self._logger.error(
                f"Failed to cache dashboard: {str(e)}",
                exc_info=True,
                extra={"admin_id": str(admin_id)},
            )