# --- File: complaint_analytics_repository.py ---
"""
Complaint analytics repository with comprehensive metrics and insights.

Handles analytics snapshots, category metrics, and staff performance
tracking for data-driven complaint management optimization.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.complaint.complaint_analytics import (
    ComplaintAnalyticSnapshot,
    ComplaintCategoryMetric,
    ComplaintStaffPerformance,
)
from app.models.complaint.complaint import Complaint
from app.repositories.base.base_repository import BaseRepository


class ComplaintAnalyticSnapshotRepository(BaseRepository[ComplaintAnalyticSnapshot]):
    """
    Complaint analytics snapshot repository for pre-computed metrics.
    
    Provides snapshot management and historical analytics tracking
    for performance monitoring and reporting.
    """

    def __init__(self, session: Session):
        """
        Initialize analytics snapshot repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ComplaintAnalyticSnapshot, session)

    # ==================== CRUD Operations ====================

    def create_snapshot(
        self,
        hostel_id: Optional[str],
        period_start: date,
        period_end: date,
        snapshot_type: str,
        metrics: Dict[str, Any],
    ) -> ComplaintAnalyticSnapshot:
        """
        Create a new analytics snapshot.
        
        Args:
            hostel_id: Hostel identifier (None for system-wide)
            period_start: Period start date
            period_end: Period end date
            snapshot_type: DAILY, WEEKLY, MONTHLY, QUARTERLY, YEARLY
            metrics: Dictionary of calculated metrics
            
        Returns:
            Created snapshot instance
        """
        snapshot = ComplaintAnalyticSnapshot(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            snapshot_type=snapshot_type,
            total_complaints=metrics.get("total_complaints", 0),
            open_complaints=metrics.get("open_complaints", 0),
            in_progress_complaints=metrics.get("in_progress_complaints", 0),
            resolved_complaints=metrics.get("resolved_complaints", 0),
            closed_complaints=metrics.get("closed_complaints", 0),
            avg_resolution_time_hours=metrics.get("avg_resolution_time_hours"),
            median_resolution_time_hours=metrics.get("median_resolution_time_hours"),
            min_resolution_time_hours=metrics.get("min_resolution_time_hours"),
            max_resolution_time_hours=metrics.get("max_resolution_time_hours"),
            sla_compliant_count=metrics.get("sla_compliant_count", 0),
            sla_breached_count=metrics.get("sla_breached_count", 0),
            sla_compliance_rate=metrics.get("sla_compliance_rate"),
            escalated_count=metrics.get("escalated_count", 0),
            reopened_count=metrics.get("reopened_count", 0),
            avg_rating=metrics.get("avg_rating"),
            total_feedback_count=metrics.get("total_feedback_count", 0),
            category_breakdown=metrics.get("category_breakdown", {}),
            priority_breakdown=metrics.get("priority_breakdown", {}),
            status_breakdown=metrics.get("status_breakdown", {}),
            generated_at=datetime.now(timezone.utc),
            metadata=metrics.get("metadata", {}),
        )
        
        return self.create(snapshot)

    # ==================== Query Operations ====================

    def find_by_period(
        self,
        period_start: date,
        period_end: date,
        hostel_id: Optional[str] = None,
        snapshot_type: Optional[str] = None,
    ) -> Optional[ComplaintAnalyticSnapshot]:
        """
        Find snapshot for a specific period.
        
        Args:
            period_start: Period start date
            period_end: Period end date
            hostel_id: Optional hostel filter
            snapshot_type: Optional snapshot type filter
            
        Returns:
            Snapshot or None
        """
        query = select(ComplaintAnalyticSnapshot).where(
            and_(
                ComplaintAnalyticSnapshot.period_start == period_start,
                ComplaintAnalyticSnapshot.period_end == period_end,
            )
        )
        
        if hostel_id is not None:
            query = query.where(ComplaintAnalyticSnapshot.hostel_id == hostel_id)
        else:
            query = query.where(ComplaintAnalyticSnapshot.hostel_id.is_(None))
        
        if snapshot_type:
            query = query.where(ComplaintAnalyticSnapshot.snapshot_type == snapshot_type)
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_latest_snapshot(
        self,
        hostel_id: Optional[str] = None,
        snapshot_type: str = "DAILY",
    ) -> Optional[ComplaintAnalyticSnapshot]:
        """
        Find most recent snapshot.
        
        Args:
            hostel_id: Optional hostel filter
            snapshot_type: Snapshot type
            
        Returns:
            Latest snapshot or None
        """
        query = select(ComplaintAnalyticSnapshot).where(
            ComplaintAnalyticSnapshot.snapshot_type == snapshot_type
        )
        
        if hostel_id is not None:
            query = query.where(ComplaintAnalyticSnapshot.hostel_id == hostel_id)
        else:
            query = query.where(ComplaintAnalyticSnapshot.hostel_id.is_(None))
        
        query = query.order_by(desc(ComplaintAnalyticSnapshot.period_end))
        query = query.limit(1)
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_snapshots_in_range(
        self,
        date_from: date,
        date_to: date,
        hostel_id: Optional[str] = None,
        snapshot_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintAnalyticSnapshot]:
        """
        Find snapshots within date range.
        
        Args:
            date_from: Start date
            date_to: End date
            hostel_id: Optional hostel filter
            snapshot_type: Optional snapshot type filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of snapshots
        """
        query = select(ComplaintAnalyticSnapshot).where(
            and_(
                ComplaintAnalyticSnapshot.period_start >= date_from,
                ComplaintAnalyticSnapshot.period_end <= date_to,
            )
        )
        
        if hostel_id is not None:
            query = query.where(ComplaintAnalyticSnapshot.hostel_id == hostel_id)
        
        if snapshot_type:
            query = query.where(ComplaintAnalyticSnapshot.snapshot_type == snapshot_type)
        
        query = query.order_by(ComplaintAnalyticSnapshot.period_start.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics Operations ====================

    def generate_daily_snapshot(
        self,
        target_date: date,
        hostel_id: Optional[str] = None,
    ) -> ComplaintAnalyticSnapshot:
        """
        Generate daily analytics snapshot.
        
        Args:
            target_date: Date for snapshot
            hostel_id: Optional hostel filter
            
        Returns:
            Created snapshot
        """
        metrics = self._calculate_period_metrics(
            period_start=target_date,
            period_end=target_date,
            hostel_id=hostel_id,
        )
        
        return self.create_snapshot(
            hostel_id=hostel_id,
            period_start=target_date,
            period_end=target_date,
            snapshot_type="DAILY",
            metrics=metrics,
        )

    def generate_weekly_snapshot(
        self,
        week_start: date,
        hostel_id: Optional[str] = None,
    ) -> ComplaintAnalyticSnapshot:
        """
        Generate weekly analytics snapshot.
        
        Args:
            week_start: Week start date (Monday)
            hostel_id: Optional hostel filter
            
        Returns:
            Created snapshot
        """
        week_end = week_start + timedelta(days=6)
        
        metrics = self._calculate_period_metrics(
            period_start=week_start,
            period_end=week_end,
            hostel_id=hostel_id,
        )
        
        return self.create_snapshot(
            hostel_id=hostel_id,
            period_start=week_start,
            period_end=week_end,
            snapshot_type="WEEKLY",
            metrics=metrics,
        )

    def generate_monthly_snapshot(
        self,
        year: int,
        month: int,
        hostel_id: Optional[str] = None,
    ) -> ComplaintAnalyticSnapshot:
        """
        Generate monthly analytics snapshot.
        
        Args:
            year: Year
            month: Month (1-12)
            hostel_id: Optional hostel filter
            
        Returns:
            Created snapshot
        """
        from calendar import monthrange
        
        month_start = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        month_end = date(year, month, last_day)
        
        metrics = self._calculate_period_metrics(
            period_start=month_start,
            period_end=month_end,
            hostel_id=hostel_id,
        )
        
        return self.create_snapshot(
            hostel_id=hostel_id,
            period_start=month_start,
            period_end=month_end,
            snapshot_type="MONTHLY",
            metrics=metrics,
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
            Dictionary with comparison metrics
        """
        snapshot1 = self.find_by_period(period1_start, period1_end, hostel_id)
        snapshot2 = self.find_by_period(period2_start, period2_end, hostel_id)
        
        if not snapshot1 or not snapshot2:
            return {}
        
        def calc_change(val1, val2):
            if val2 == 0:
                return None
            return ((val1 - val2) / val2 * 100)
        
        return {
            "period1": {
                "start": period1_start.isoformat(),
                "end": period1_end.isoformat(),
                "total_complaints": snapshot1.total_complaints,
                "sla_compliance_rate": float(snapshot1.sla_compliance_rate or 0),
                "avg_resolution_time": float(snapshot1.avg_resolution_time_hours or 0),
            },
            "period2": {
                "start": period2_start.isoformat(),
                "end": period2_end.isoformat(),
                "total_complaints": snapshot2.total_complaints,
                "sla_compliance_rate": float(snapshot2.sla_compliance_rate or 0),
                "avg_resolution_time": float(snapshot2.avg_resolution_time_hours or 0),
            },
            "changes": {
                "total_complaints_change": calc_change(
                    snapshot1.total_complaints,
                    snapshot2.total_complaints,
                ),
                "sla_compliance_change": calc_change(
                    float(snapshot1.sla_compliance_rate or 0),
                    float(snapshot2.sla_compliance_rate or 0),
                ),
                "resolution_time_change": calc_change(
                    float(snapshot1.avg_resolution_time_hours or 0),
                    float(snapshot2.avg_resolution_time_hours or 0),
                ),
            },
        }

    # ==================== Helper Methods ====================

    def _calculate_period_metrics(
        self,
        period_start: date,
        period_end: date,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate metrics for a specific period.
        
        Args:
            period_start: Period start date
            period_end: Period end date
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary of calculated metrics
        """
        # Convert dates to datetime for queries
        start_dt = datetime.combine(period_start, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(period_end, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        # Base query
        query = select(Complaint).where(
            and_(
                Complaint.opened_at >= start_dt,
                Complaint.opened_at <= end_dt,
            )
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        complaints = list(result.scalars().all())
        
        if not complaints:
            return {
                "total_complaints": 0,
                "open_complaints": 0,
                "in_progress_complaints": 0,
                "resolved_complaints": 0,
                "closed_complaints": 0,
            }
        
        # Calculate metrics
        total = len(complaints)
        
        # Status counts
        from app.models.base.enums import ComplaintStatus
        status_counts = {
            "open": len([c for c in complaints if c.status == ComplaintStatus.OPEN]),
            "in_progress": len([c for c in complaints if c.status == ComplaintStatus.IN_PROGRESS]),
            "resolved": len([c for c in complaints if c.status == ComplaintStatus.RESOLVED]),
            "closed": len([c for c in complaints if c.status == ComplaintStatus.CLOSED]),
        }
        
        # Resolution time metrics
        resolved_complaints = [
            c for c in complaints
            if c.resolved_at is not None
        ]
        
        resolution_times = []
        for c in resolved_complaints:
            hours = (c.resolved_at - c.opened_at).total_seconds() / 3600
            resolution_times.append(hours)
        
        avg_resolution_time = (
            sum(resolution_times) / len(resolution_times)
            if resolution_times else None
        )
        
        median_resolution_time = None
        if resolution_times:
            sorted_times = sorted(resolution_times)
            n = len(sorted_times)
            if n % 2 == 0:
                median_resolution_time = (sorted_times[n//2-1] + sorted_times[n//2]) / 2
            else:
                median_resolution_time = sorted_times[n//2]
        
        min_resolution_time = min(resolution_times) if resolution_times else None
        max_resolution_time = max(resolution_times) if resolution_times else None
        
        # SLA metrics
        sla_compliant = len([c for c in complaints if not c.sla_breach])
        sla_breached = len([c for c in complaints if c.sla_breach])
        sla_compliance_rate = (sla_compliant / total * 100) if total > 0 else 0
        
        # Other metrics
        escalated = len([c for c in complaints if c.escalated])
        reopened = len([c for c in complaints if c.reopened_count > 0])
        
        # Category breakdown
        category_breakdown = {}
        for c in complaints:
            cat = c.category.value
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        
        # Priority breakdown
        priority_breakdown = {}
        for c in complaints:
            pri = c.priority.value
            priority_breakdown[pri] = priority_breakdown.get(pri, 0) + 1
        
        # Status breakdown
        status_breakdown = {}
        for c in complaints:
            stat = c.status.value
            status_breakdown[stat] = status_breakdown.get(stat, 0) + 1
        
        return {
            "total_complaints": total,
            "open_complaints": status_counts["open"],
            "in_progress_complaints": status_counts["in_progress"],
            "resolved_complaints": status_counts["resolved"],
            "closed_complaints": status_counts["closed"],
            "avg_resolution_time_hours": Decimal(str(avg_resolution_time)) if avg_resolution_time else None,
            "median_resolution_time_hours": Decimal(str(median_resolution_time)) if median_resolution_time else None,
            "min_resolution_time_hours": Decimal(str(min_resolution_time)) if min_resolution_time else None,
            "max_resolution_time_hours": Decimal(str(max_resolution_time)) if max_resolution_time else None,
            "sla_compliant_count": sla_compliant,
            "sla_breached_count": sla_breached,
            "sla_compliance_rate": Decimal(str(sla_compliance_rate)),
            "escalated_count": escalated,
            "reopened_count": reopened,
            "category_breakdown": category_breakdown,
            "priority_breakdown": priority_breakdown,
            "status_breakdown": status_breakdown,
        }


class ComplaintCategoryMetricRepository(BaseRepository[ComplaintCategoryMetric]):
    """
    Category-wise complaint metrics repository.
    
    Provides category performance tracking and analysis.
    """

    def __init__(self, session: Session):
        """
        Initialize category metric repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ComplaintCategoryMetric, session)

    def create_category_metric(
        self,
        hostel_id: str,
        category: str,
        period_start: date,
        period_end: date,
        metrics: Dict[str, Any],
    ) -> ComplaintCategoryMetric:
        """
        Create category metric record.
        
        Args:
            hostel_id: Hostel identifier
            category: Complaint category
            period_start: Period start date
            period_end: Period end date
            metrics: Calculated metrics
            
        Returns:
            Created metric instance
        """
        metric = ComplaintCategoryMetric(
            hostel_id=hostel_id,
            category=category,
            period_start=period_start,
            period_end=period_end,
            total_complaints=metrics.get("total_complaints", 0),
            open_complaints=metrics.get("open_complaints", 0),
            resolved_complaints=metrics.get("resolved_complaints", 0),
            avg_resolution_time_hours=metrics.get("avg_resolution_time_hours"),
            resolution_rate=metrics.get("resolution_rate"),
            avg_rating=metrics.get("avg_rating"),
            most_common_sub_category=metrics.get("most_common_sub_category"),
            metadata=metrics.get("metadata", {}),
        )
        
        return self.create(metric)

    def find_by_category(
        self,
        hostel_id: str,
        category: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[ComplaintCategoryMetric]:
        """
        Find metrics for a specific category.
        
        Args:
            hostel_id: Hostel identifier
            category: Complaint category
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            List of category metrics
        """
        query = select(ComplaintCategoryMetric).where(
            and_(
                ComplaintCategoryMetric.hostel_id == hostel_id,
                ComplaintCategoryMetric.category == category,
            )
        )
        
        if date_from:
            query = query.where(ComplaintCategoryMetric.period_start >= date_from)
        
        if date_to:
            query = query.where(ComplaintCategoryMetric.period_end <= date_to)
        
        query = query.order_by(ComplaintCategoryMetric.period_start.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())


class ComplaintStaffPerformanceRepository(BaseRepository[ComplaintStaffPerformance]):
    """
    Staff performance metrics repository.
    
    Provides staff performance tracking and analytics.
    """

    def __init__(self, session: Session):
        """
        Initialize staff performance repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ComplaintStaffPerformance, session)

    def create_performance_metric(
        self,
        staff_id: str,
        hostel_id: str,
        period_start: date,
        period_end: date,
        metrics: Dict[str, Any],
    ) -> ComplaintStaffPerformance:
        """
        Create staff performance metric.
        
        Args:
            staff_id: Staff member ID
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date
            metrics: Calculated metrics
            
        Returns:
            Created performance metric
        """
        performance = ComplaintStaffPerformance(
            staff_id=staff_id,
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            complaints_assigned=metrics.get("complaints_assigned", 0),
            complaints_resolved=metrics.get("complaints_resolved", 0),
            complaints_pending=metrics.get("complaints_pending", 0),
            avg_resolution_time_hours=metrics.get("avg_resolution_time_hours"),
            resolution_rate=metrics.get("resolution_rate"),
            avg_rating=metrics.get("avg_rating"),
            total_feedback_count=metrics.get("total_feedback_count", 0),
            escalation_count=metrics.get("escalation_count", 0),
            reopened_count=metrics.get("reopened_count", 0),
            workload_score=metrics.get("workload_score", 0),
            performance_score=metrics.get("performance_score"),
            metadata=metrics.get("metadata", {}),
        )
        
        return self.create(performance)

    def find_by_staff(
        self,
        staff_id: str,
        hostel_id: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[ComplaintStaffPerformance]:
        """
        Find performance metrics for a staff member.
        
        Args:
            staff_id: Staff member ID
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            List of performance metrics
        """
        query = select(ComplaintStaffPerformance).where(
            ComplaintStaffPerformance.staff_id == staff_id
        )
        
        if hostel_id:
            query = query.where(ComplaintStaffPerformance.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(ComplaintStaffPerformance.period_start >= date_from)
        
        if date_to:
            query = query.where(ComplaintStaffPerformance.period_end <= date_to)
        
        query = query.order_by(ComplaintStaffPerformance.period_start.asc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_top_performers(
        self,
        hostel_id: str,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ) -> List[ComplaintStaffPerformance]:
        """
        Get top performing staff members.
        
        Args:
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date
            limit: Maximum records to return
            
        Returns:
            List of top performers
        """
        query = (
            select(ComplaintStaffPerformance)
            .where(
                and_(
                    ComplaintStaffPerformance.hostel_id == hostel_id,
                    ComplaintStaffPerformance.period_start == period_start,
                    ComplaintStaffPerformance.period_end == period_end,
                )
            )
            .order_by(desc(ComplaintStaffPerformance.performance_score))
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())


