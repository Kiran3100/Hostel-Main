"""
Supervisor Dashboard Service

Builds comprehensive supervisor dashboard views with performance optimization.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorDashboardRepository
from app.schemas.supervisor import SupervisorDashboard
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SupervisorDashboardService:
    """
    High-level service to build supervisor dashboard data structure.

    Aggregates:
    - Dashboard metrics and KPIs
    - Tasks & recent activities
    - Today's schedule
    - Alerts and notifications
    - Performance indicators
    - Quick stats

    Example:
        >>> service = SupervisorDashboardService(dashboard_repo)
        >>> dashboard = service.get_dashboard(db, supervisor_id, hostel_id)
        >>> print(dashboard.metrics, dashboard.alerts)
    """

    def __init__(
        self,
        dashboard_repo: SupervisorDashboardRepository,
    ) -> None:
        """
        Initialize the supervisor dashboard service.

        Args:
            dashboard_repo: Repository for dashboard operations
        """
        if not dashboard_repo:
            raise ValueError("dashboard_repo cannot be None")
            
        self.dashboard_repo = dashboard_repo

    # -------------------------------------------------------------------------
    # Dashboard Operations
    # -------------------------------------------------------------------------

    def get_dashboard(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        date_filter: Optional[date] = None,
        include_inactive: bool = False,
    ) -> SupervisorDashboard:
        """
        Build and return the supervisor dashboard payload.

        hostel_id is used when supervisors manage multiple hostels.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel context
            date_filter: Optional date for time-based filtering (defaults to today)
            include_inactive: Whether to include inactive items

        Returns:
            SupervisorDashboard: Complete dashboard data

        Raises:
            ValidationException: If validation fails or dashboard cannot be built

        Example:
            >>> dashboard = service.get_dashboard(
            ...     db, supervisor_id, hostel_id,
            ...     date_filter=datetime.now().date()
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            logger.info(
                f"Building dashboard for supervisor: {supervisor_id}, "
                f"hostel: {hostel_id}"
            )
            
            data = self.dashboard_repo.get_dashboard_data(
                db=db,
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                date_filter=date_filter,
                include_inactive=include_inactive,
            )
            
            if not data:
                logger.warning(
                    f"Dashboard data not found for supervisor: {supervisor_id}, "
                    f"hostel: {hostel_id}"
                )
                raise ValidationException(
                    f"Dashboard data not available for supervisor {supervisor_id} "
                    f"in hostel {hostel_id}"
                )
            
            logger.info(f"Successfully built dashboard for supervisor: {supervisor_id}")
            return SupervisorDashboard.model_validate(data)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to build dashboard for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to build dashboard: {str(e)}")

    # -------------------------------------------------------------------------
    # Dashboard Components
    # -------------------------------------------------------------------------

    def get_dashboard_metrics(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get only the metrics section of the dashboard.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel

        Returns:
            Dict[str, Any]: Dashboard metrics

        Raises:
            ValidationException: If validation fails

        Example:
            >>> metrics = service.get_dashboard_metrics(db, supervisor_id, hostel_id)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id or not hostel_id:
            raise ValidationException("Supervisor ID and Hostel ID are required")

        try:
            logger.debug(
                f"Getting dashboard metrics for supervisor: {supervisor_id}"
            )
            
            metrics = self.dashboard_repo.get_metrics(
                db=db,
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
            )
            
            return metrics or {}
            
        except Exception as e:
            logger.error(f"Failed to get dashboard metrics: {str(e)}")
            raise ValidationException(f"Failed to retrieve dashboard metrics: {str(e)}")

    def get_dashboard_alerts(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        severity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get only the alerts section of the dashboard.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel
            severity: Optional filter by severity ("high", "medium", "low")

        Returns:
            Dict[str, Any]: Dashboard alerts

        Raises:
            ValidationException: If validation fails

        Example:
            >>> alerts = service.get_dashboard_alerts(
            ...     db, supervisor_id, hostel_id, severity="high"
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id or not hostel_id:
            raise ValidationException("Supervisor ID and Hostel ID are required")
        
        if severity and severity not in ["high", "medium", "low"]:
            raise ValidationException(
                "Severity must be one of: high, medium, low"
            )

        try:
            logger.debug(
                f"Getting dashboard alerts for supervisor: {supervisor_id}, "
                f"severity: {severity}"
            )
            
            alerts = self.dashboard_repo.get_alerts(
                db=db,
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                severity=severity,
            )
            
            return alerts or {"alerts": [], "count": 0}
            
        except Exception as e:
            logger.error(f"Failed to get dashboard alerts: {str(e)}")
            raise ValidationException(f"Failed to retrieve dashboard alerts: {str(e)}")

    def get_recent_tasks(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Get recent tasks for the supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel
            limit: Maximum number of tasks to return

        Returns:
            Dict[str, Any]: Recent tasks data

        Raises:
            ValidationException: If validation fails

        Example:
            >>> tasks = service.get_recent_tasks(db, supervisor_id, hostel_id, limit=20)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id or not hostel_id:
            raise ValidationException("Supervisor ID and Hostel ID are required")
        
        if limit <= 0 or limit > 100:
            raise ValidationException("Limit must be between 1 and 100")

        try:
            logger.debug(
                f"Getting recent tasks for supervisor: {supervisor_id}, limit: {limit}"
            )
            
            tasks = self.dashboard_repo.get_recent_tasks(
                db=db,
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                limit=limit,
            )
            
            return tasks or {"tasks": [], "count": 0}
            
        except Exception as e:
            logger.error(f"Failed to get recent tasks: {str(e)}")
            raise ValidationException(f"Failed to retrieve recent tasks: {str(e)}")

    # -------------------------------------------------------------------------
    # Dashboard Cache & Refresh
    # -------------------------------------------------------------------------

    def refresh_dashboard_cache(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
    ) -> bool:
        """
        Refresh the dashboard cache for a supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel

        Returns:
            bool: True if cache refreshed successfully

        Example:
            >>> refreshed = service.refresh_dashboard_cache(db, supervisor_id, hostel_id)
        """
        if not db or not supervisor_id or not hostel_id:
            return False
        
        try:
            logger.info(
                f"Refreshing dashboard cache for supervisor: {supervisor_id}"
            )
            
            success = self.dashboard_repo.refresh_cache(
                db=db,
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
            )
            
            if success:
                logger.info(
                    f"Successfully refreshed dashboard cache for: {supervisor_id}"
                )
            return success
            
        except Exception as e:
            logger.error(f"Failed to refresh dashboard cache: {str(e)}")
            return False