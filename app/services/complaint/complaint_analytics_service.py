"""
Complaint analytics and reporting service.

Handles analytics snapshot generation, trend analysis, performance
metrics, and comprehensive reporting for complaint management.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_analytics_repository import (
    ComplaintAnalyticSnapshotRepository,
    ComplaintCategoryMetricRepository,
    ComplaintStaffPerformanceRepository,
)
from app.repositories.complaint.complaint_aggregate_repository import (
    ComplaintAggregateRepository,
)
from app.core.exceptions import NotFoundError


class ComplaintAnalyticsService:
    """
    Complaint analytics and reporting service.
    
    Provides comprehensive analytics, trend analysis, and reporting
    capabilities for complaint management optimization.
    """

    def __init__(self, session: Session):
        """
        Initialize analytics service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)
        self.snapshot_repo = ComplaintAnalyticSnapshotRepository(session)
        self.category_metric_repo = ComplaintCategoryMetricRepository(session)
        self.staff_performance_repo = ComplaintStaffPerformanceRepository(session)
        self.aggregate_repo = ComplaintAggregateRepository(session)

    # ==================== Snapshot Generation ====================

    def generate_daily_snapshot(
        self,
        target_date: Optional[date] = None,
        hostel_id: Optional[str] = None,
    ):
        """
        Generate daily analytics snapshot.
        
        Args:
            target_date: Date for snapshot (defaults to today)
            hostel_id: Optional hostel filter
            
        Returns:
            Created snapshot
        """
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()
        
        snapshot = self.snapshot_repo.generate_daily_snapshot(
            target_date=target_date,
            hostel_id=hostel_id,
        )
        
        self.session.commit()
        return snapshot

    def generate_weekly_snapshot(
        self,
        week_start: Optional[date] = None,
        hostel_id: Optional[str] = None,
    ):
        """
        Generate weekly analytics snapshot.
        
        Args:
            week_start: Week start date (defaults to current week Monday)
            hostel_id: Optional hostel filter
            
        Returns:
            Created snapshot
        """
        if week_start is None:
            today = datetime.now(timezone.utc).date()
            week_start = today - timedelta(days=today.weekday())
        
        snapshot = self.snapshot_repo.generate_weekly_snapshot(
            week_start=week_start,
            hostel_id=hostel_id,
        )
        
        self.session.commit()
        return snapshot

    def generate_monthly_snapshot(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        hostel_id: Optional[str] = None,
    ):
        """
        Generate monthly analytics snapshot.
        
        Args:
            year: Year (defaults to current)
            month: Month (defaults to current)
            hostel_id: Optional hostel filter
            
        Returns:
            Created snapshot
        """
        now = datetime.now(timezone.utc)
        if year is None:
            year = now.year
        if month is None:
            month = now.month
        
        snapshot = self.snapshot_repo.generate_monthly_snapshot(
            year=year,
            month=month,
            hostel_id=hostel_id,
        )
        
        self.session.commit()
        return snapshot

    def generate_all_snapshots(
        self,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate all snapshot types for current period.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary with all snapshots
        """
        daily = self.generate_daily_snapshot(hostel_id=hostel_id)
        weekly = self.generate_weekly_snapshot(hostel_id=hostel_id)
        monthly = self.generate_monthly_snapshot(hostel_id=hostel_id)
        
        return {
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly,
        }

    # ==================== Snapshot Queries ====================

    def get_latest_snapshot(
        self,
        hostel_id: Optional[str] = None,
        snapshot_type: str = "DAILY",
    ):
        """
        Get most recent snapshot.
        
        Args:
            hostel_id: Optional hostel filter
            snapshot_type: DAILY, WEEKLY, MONTHLY
            
        Returns:
            Latest snapshot or None
        """
        return self.snapshot_repo.find_latest_snapshot(
            hostel_id=hostel_id,
            snapshot_type=snapshot_type,
        )

    def get_snapshots_in_range(
        self,
        date_from: date,
        date_to: date,
        hostel_id: Optional[str] = None,
        snapshot_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ):
        """
        Get snapshots within date range.
        
        Args:
            date_from: Start date
            date_to: End date
            hostel_id: Optional hostel filter
            snapshot_type: Optional type filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of snapshots
        """
        return self.snapshot_repo.find_snapshots_in_range(
            date_from=date_from,
            date_to=date_to,
            hostel_id=hostel_id,
            snapshot_type=snapshot_type,
            skip=skip,
            limit=limit,
        )

    def compare_periods(
        self,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare metrics between two periods.
        
        Args:
            period1_start: First period start
            period1_end: First period end
            period2_start: Second period start
            period2_end: Second period end
            hostel_id: Optional hostel filter
            
        Returns:
            Comparison metrics
        """
        return self.snapshot_repo.compare_periods(
            period1_start=period1_start,
            period1_end=period1_end,
            period2_start=period2_start,
            period2_end=period2_end,
            hostel_id=hostel_id,
        )

    # ==================== Dashboard & Summary ====================

    def get_dashboard_summary(
        self,
        hostel_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary.
        
        Args:
            hostel_id: Optional hostel filter
            user_id: Optional user filter
            
        Returns:
            Dashboard metrics
        """
        return self.aggregate_repo.get_dashboard_summary(
            hostel_id=hostel_id,
            user_id=user_id,
        )

    def get_executive_report(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate executive summary report.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Executive report
        """
        return self.aggregate_repo.generate_executive_report(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )

    # ==================== Performance Analytics ====================

    def get_hostel_performance_comparison(
        self,
        hostel_ids: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compare performance across hostels.
        
        Args:
            hostel_ids: List of hostel IDs
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Performance comparison
        """
        return self.aggregate_repo.get_hostel_performance_comparison(
            hostel_ids=hostel_ids,
            date_from=date_from,
            date_to=date_to,
        )

    def get_category_performance_trends(
        self,
        hostel_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get category performance trends.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Category trends
        """
        return self.aggregate_repo.get_category_performance_trends(
            hostel_id=hostel_id,
            days=days,
        )

    def get_staff_workload_overview(
        self,
        hostel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get staff workload overview.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Staff workload metrics
        """
        return self.aggregate_repo.get_staff_workload_overview(
            hostel_id=hostel_id,
        )

    # ==================== Category Metrics ====================

    def get_category_metrics(
        self,
        hostel_id: str,
        category: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ):
        """
        Get metrics for specific category.
        
        Args:
            hostel_id: Hostel identifier
            category: Complaint category
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Category metrics
        """
        return self.category_metric_repo.find_by_category(
            hostel_id=hostel_id,
            category=category,
            date_from=date_from,
            date_to=date_to,
        )

    # ==================== Staff Performance ====================

    def get_staff_performance(
        self,
        staff_id: str,
        hostel_id: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ):
        """
        Get performance metrics for staff member.
        
        Args:
            staff_id: Staff member ID
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Performance metrics
        """
        return self.staff_performance_repo.find_by_staff(
            staff_id=staff_id,
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_top_performers(
        self,
        hostel_id: str,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ):
        """
        Get top performing staff members.
        
        Args:
            hostel_id: Hostel identifier
            period_start: Period start
            period_end: Period end
            limit: Maximum performers
            
        Returns:
            Top performers list
        """
        return self.staff_performance_repo.get_top_performers(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            limit=limit,
        )

    # ==================== Trends & Insights ====================

    def get_complaint_trends(
        self,
        hostel_id: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get complaint volume trends.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days
            
        Returns:
            Daily trend data
        """
        # Would calculate from snapshots or raw data
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)
        
        snapshots = self.get_snapshots_in_range(
            date_from=start_date,
            date_to=end_date,
            hostel_id=hostel_id,
            snapshot_type="DAILY",
        )
        
        trends = []
        for snapshot in snapshots:
            trends.append({
                "date": snapshot.period_start.isoformat(),
                "total_complaints": snapshot.total_complaints,
                "resolved_complaints": snapshot.resolved_complaints,
                "sla_compliance_rate": float(snapshot.sla_compliance_rate or 0),
                "avg_resolution_time": float(snapshot.avg_resolution_time_hours or 0),
            })
        
        return trends

    def get_resolution_time_trends(
        self,
        hostel_id: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get resolution time trends.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days
            
        Returns:
            Resolution time trend data
        """
        trends = self.get_complaint_trends(hostel_id=hostel_id, days=days)
        
        return [
            {
                "date": t["date"],
                "avg_resolution_time": t["avg_resolution_time"],
            }
            for t in trends
        ]

    def get_sla_compliance_trends(
        self,
        hostel_id: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get SLA compliance trends.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days
            
        Returns:
            SLA compliance trend data
        """
        trends = self.get_complaint_trends(hostel_id=hostel_id, days=days)
        
        return [
            {
                "date": t["date"],
                "sla_compliance_rate": t["sla_compliance_rate"],
            }
            for t in trends
        ]

    # ==================== Advanced Analytics ====================

    def get_predictive_insights(
        self,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get predictive insights (placeholder for ML integration).
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Predictive insights
        """
        # Placeholder for future ML integration
        latest = self.get_latest_snapshot(hostel_id=hostel_id)
        
        if not latest:
            return {"message": "Insufficient data for predictions"}
        
        # Mock predictions
        return {
            "predicted_volume_next_week": latest.total_complaints * 1.1,
            "predicted_sla_compliance": float(latest.sla_compliance_rate or 0) * 0.95,
            "high_risk_categories": ["MAINTENANCE", "FACILITIES"],
            "recommendations": [
                "Increase staff during peak hours",
                "Focus on maintenance category improvements",
            ],
        }

    def get_anomaly_detection(
        self,
        hostel_id: Optional[str] = None,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in complaint patterns.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Detected anomalies
        """
        trends = self.get_complaint_trends(hostel_id=hostel_id, days=days)
        
        if not trends:
            return []
        
        # Simple anomaly detection based on standard deviation
        volumes = [t["total_complaints"] for t in trends]
        avg = sum(volumes) / len(volumes)
        
        # Calculate standard deviation
        variance = sum((x - avg) ** 2 for x in volumes) / len(volumes)
        std_dev = variance ** 0.5
        
        anomalies = []
        for trend in trends:
            if abs(trend["total_complaints"] - avg) > (2 * std_dev):
                anomalies.append({
                    "date": trend["date"],
                    "value": trend["total_complaints"],
                    "expected_range": f"{avg - std_dev:.0f} - {avg + std_dev:.0f}",
                    "severity": "HIGH" if abs(trend["total_complaints"] - avg) > (3 * std_dev) else "MEDIUM",
                })
        
        return anomalies