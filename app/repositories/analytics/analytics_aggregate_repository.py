"""
Analytics Aggregate Repository for cross-module data aggregation.

Provides unified access to analytics data across all modules with:
- Cross-module metric aggregation
- Unified reporting capabilities
- Performance optimization for complex queries
- Cache coordination across repositories
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case
from sqlalchemy.orm import Session, joinedload, selectinload
from uuid import UUID

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.caching_repository import CachingRepository
from app.models.analytics import (
    BookingKPI,
    ComplaintKPI,
    OccupancyKPI,
    FinancialReport,
    SupervisorKPI,
    PlatformMetrics,
    DashboardKPI,
    QuickStats,
)


class AnalyticsAggregateRepository(BaseRepository):
    """
    Aggregate repository for cross-module analytics operations.
    
    Coordinates data retrieval and aggregation across all analytics
    modules for unified reporting and insights.
    """
    
    def __init__(self, db: Session):
        """Initialize with database session and caching."""
        super().__init__(db)
        self.cache = CachingRepository(db)
        self._cache_ttl = 300  # 5 minutes default cache
    
    # ==================== Unified Dashboard Data ====================
    
    def get_unified_dashboard_metrics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get unified dashboard metrics across all modules.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            period_start: Period start date
            period_end: Period end date
            use_cache: Whether to use cached results
            
        Returns:
            Dictionary with aggregated metrics from all modules
        """
        cache_key = f"unified_dashboard:{hostel_id}:{period_start}:{period_end}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        # Aggregate from all modules
        metrics = {
            'booking_metrics': self._get_booking_summary(hostel_id, period_start, period_end),
            'financial_metrics': self._get_financial_summary(hostel_id, period_start, period_end),
            'occupancy_metrics': self._get_occupancy_summary(hostel_id, period_start, period_end),
            'complaint_metrics': self._get_complaint_summary(hostel_id, period_start, period_end),
            'supervisor_metrics': self._get_supervisor_summary(hostel_id, period_start, period_end),
            'quick_stats': self._get_quick_stats_summary(hostel_id, period_end),
            'alerts': self._get_critical_alerts(hostel_id),
            'trends': self._calculate_period_trends(hostel_id, period_start, period_end),
        }
        
        # Calculate composite scores
        metrics['health_score'] = self._calculate_overall_health_score(metrics)
        metrics['performance_grade'] = self._calculate_performance_grade(metrics)
        
        # Cache results
        if use_cache:
            self.cache.set(cache_key, metrics, ttl=self._cache_ttl)
        
        return metrics
    
    def _get_booking_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Get booking metrics summary."""
        query = QueryBuilder(BookingKPI, self.db)
        
        if hostel_id:
            query = query.where(BookingKPI.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                BookingKPI.period_start >= period_start,
                BookingKPI.period_end <= period_end
            )
        )
        
        kpi = query.first()
        
        if not kpi:
            return self._empty_booking_summary()
        
        return {
            'total_bookings': kpi.total_bookings,
            'confirmed_bookings': kpi.confirmed_bookings,
            'conversion_rate': float(kpi.booking_conversion_rate),
            'cancellation_rate': float(kpi.cancellation_rate),
            'average_lead_time': float(kpi.average_lead_time_days),
            'approval_rate': float(kpi.approval_rate) if kpi.approval_rate else 0,
        }
    
    def _get_financial_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Get financial metrics summary."""
        query = QueryBuilder(FinancialReport, self.db)
        
        if hostel_id:
            query = query.where(FinancialReport.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                FinancialReport.period_start >= period_start,
                FinancialReport.period_end <= period_end
            )
        )
        
        report = query.first()
        
        if not report:
            return self._empty_financial_summary()
        
        return {
            'total_revenue': float(report.pnl.revenue_breakdown.total_revenue) if report.pnl else 0,
            'net_profit': float(report.pnl.net_profit) if report.pnl else 0,
            'net_profit_margin': float(report.pnl.net_profit_margin) if report.pnl else 0,
            'collection_rate': float(report.collection_rate),
            'overdue_ratio': float(report.overdue_ratio),
            'financial_health_score': float(report.financial_health_score) if report.financial_health_score else 0,
            'performance_grade': report.performance_grade,
        }
    
    def _get_occupancy_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Get occupancy metrics summary."""
        query = QueryBuilder(OccupancyKPI, self.db)
        
        if hostel_id:
            query = query.where(OccupancyKPI.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                OccupancyKPI.period_start >= period_start,
                OccupancyKPI.period_end <= period_end
            )
        )
        
        kpi = query.first()
        
        if not kpi:
            return self._empty_occupancy_summary()
        
        return {
            'current_occupancy': float(kpi.current_occupancy_percentage),
            'average_occupancy': float(kpi.average_occupancy_percentage),
            'total_beds': kpi.total_beds,
            'occupied_beds': kpi.occupied_beds,
            'available_beds': kpi.available_beds,
            'utilization_rate': float(kpi.utilization_rate),
            'occupancy_status': kpi.occupancy_status,
        }
    
    def _get_complaint_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Get complaint metrics summary."""
        query = QueryBuilder(ComplaintKPI, self.db)
        
        if hostel_id:
            query = query.where(ComplaintKPI.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                ComplaintKPI.period_start >= period_start,
                ComplaintKPI.period_end <= period_end
            )
        )
        
        kpi = query.first()
        
        if not kpi:
            return self._empty_complaint_summary()
        
        return {
            'total_complaints': kpi.total_complaints,
            'open_complaints': kpi.open_complaints,
            'resolved_complaints': kpi.resolved_complaints,
            'average_resolution_time': float(kpi.average_resolution_time_hours),
            'sla_compliance_rate': float(kpi.sla_compliance_rate),
            'escalation_rate': float(kpi.escalation_rate),
            'efficiency_score': float(kpi.efficiency_score) if kpi.efficiency_score else 0,
        }
    
    def _get_supervisor_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Get supervisor metrics summary."""
        query = QueryBuilder(SupervisorKPI, self.db)
        
        if hostel_id:
            query = query.where(SupervisorKPI.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                SupervisorKPI.period_start >= period_start,
                SupervisorKPI.period_end <= period_end
            )
        )
        
        # Aggregate across all supervisors
        supervisors = query.all()
        
        if not supervisors:
            return self._empty_supervisor_summary()
        
        return {
            'total_supervisors': len(supervisors),
            'average_performance_score': float(
                sum(s.overall_performance_score for s in supervisors) / len(supervisors)
            ),
            'total_complaints_resolved': sum(s.complaints_resolved for s in supervisors),
            'average_sla_compliance': float(
                sum(s.complaint_sla_compliance_rate for s in supervisors) / len(supervisors)
            ),
            'total_tasks_completed': sum(
                s.complaints_resolved + s.maintenance_requests_completed 
                for s in supervisors
            ),
        }
    
    def _get_quick_stats_summary(
        self,
        hostel_id: Optional[UUID],
        snapshot_date: date
    ) -> Dict[str, Any]:
        """Get quick stats for immediate dashboard visibility."""
        query = QueryBuilder(QuickStats, self.db)
        
        if hostel_id:
            query = query.where(QuickStats.hostel_id == hostel_id)
        
        query = query.where(QuickStats.snapshot_date == snapshot_date)
        
        stats = query.first()
        
        if not stats:
            return self._empty_quick_stats()
        
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
    
    def _get_critical_alerts(self, hostel_id: Optional[UUID]) -> List[Dict[str, Any]]:
        """Get critical alerts requiring immediate attention."""
        alerts = []
        
        # Check for critical metrics from quick stats
        query = QueryBuilder(QuickStats, self.db)
        if hostel_id:
            query = query.where(QuickStats.hostel_id == hostel_id)
        
        query = query.order_by(QuickStats.snapshot_date.desc())
        stats = query.first()
        
        if not stats:
            return alerts
        
        # Critical complaint alerts
        if stats.urgent_complaints > 0:
            alerts.append({
                'severity': 'critical',
                'type': 'complaints',
                'message': f'{stats.urgent_complaints} urgent complaints require attention',
                'value': stats.urgent_complaints,
            })
        
        # Overdue maintenance alerts
        if stats.overdue_maintenance > 0:
            alerts.append({
                'severity': 'error',
                'type': 'maintenance',
                'message': f'{stats.overdue_maintenance} overdue maintenance requests',
                'value': stats.overdue_maintenance,
            })
        
        # Overdue payment alerts
        if stats.overdue_payments > 1000:  # Threshold
            alerts.append({
                'severity': 'warning',
                'type': 'payments',
                'message': f'₹{float(stats.overdue_payments):,.2f} in overdue payments',
                'value': float(stats.overdue_payments),
            })
        
        # Low occupancy alerts
        if stats.occupancy_rate and stats.occupancy_rate < 50:
            alerts.append({
                'severity': 'warning',
                'type': 'occupancy',
                'message': f'Low occupancy rate: {float(stats.occupancy_rate)}%',
                'value': float(stats.occupancy_rate),
            })
        
        return alerts
    
    def _calculate_period_trends(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Calculate trends over the period."""
        # Calculate previous period for comparison
        period_length = (period_end - period_start).days
        prev_period_start = period_start - timedelta(days=period_length)
        prev_period_end = period_start - timedelta(days=1)
        
        current = self.get_unified_dashboard_metrics(
            hostel_id, period_start, period_end, use_cache=False
        )
        previous = self.get_unified_dashboard_metrics(
            hostel_id, prev_period_start, prev_period_end, use_cache=False
        )
        
        return {
            'booking_trend': self._calculate_trend_percentage(
                current['booking_metrics']['total_bookings'],
                previous['booking_metrics']['total_bookings']
            ),
            'revenue_trend': self._calculate_trend_percentage(
                current['financial_metrics']['total_revenue'],
                previous['financial_metrics']['total_revenue']
            ),
            'occupancy_trend': self._calculate_trend_percentage(
                current['occupancy_metrics']['average_occupancy'],
                previous['occupancy_metrics']['average_occupancy']
            ),
            'complaint_resolution_trend': self._calculate_trend_percentage(
                current['complaint_metrics']['resolved_complaints'],
                previous['complaint_metrics']['resolved_complaints']
            ),
        }
    
    def _calculate_trend_percentage(
        self,
        current: float,
        previous: float
    ) -> Dict[str, Any]:
        """Calculate trend percentage and direction."""
        if previous == 0:
            return {
                'percentage': 0,
                'direction': 'stable',
                'is_improvement': True,
            }
        
        percentage = ((current - previous) / previous) * 100
        
        return {
            'percentage': round(percentage, 2),
            'direction': 'up' if percentage > 0 else 'down' if percentage < 0 else 'stable',
            'is_improvement': percentage > 0,  # Context-dependent
        }
    
    def _calculate_overall_health_score(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate overall health score (0-100) based on all metrics.
        
        Weighted average of:
        - Financial health: 30%
        - Occupancy: 25%
        - Complaint resolution: 20%
        - Booking performance: 15%
        - Supervisor performance: 10%
        """
        weights = {
            'financial': 0.30,
            'occupancy': 0.25,
            'complaint': 0.20,
            'booking': 0.15,
            'supervisor': 0.10,
        }
        
        scores = {
            'financial': metrics['financial_metrics']['financial_health_score'],
            'occupancy': metrics['occupancy_metrics']['average_occupancy'],
            'complaint': metrics['complaint_metrics']['efficiency_score'],
            'booking': metrics['booking_metrics']['conversion_rate'],
            'supervisor': metrics['supervisor_metrics']['average_performance_score'],
        }
        
        weighted_score = sum(
            scores[key] * weights[key] 
            for key in weights.keys()
        )
        
        return round(weighted_score, 2)
    
    def _calculate_performance_grade(self, metrics: Dict[str, Any]) -> str:
        """Calculate letter grade based on health score."""
        health_score = metrics.get('health_score', 0)
        
        if health_score >= 90:
            return 'A+'
        elif health_score >= 85:
            return 'A'
        elif health_score >= 80:
            return 'A-'
        elif health_score >= 75:
            return 'B+'
        elif health_score >= 70:
            return 'B'
        elif health_score >= 65:
            return 'B-'
        elif health_score >= 60:
            return 'C+'
        elif health_score >= 55:
            return 'C'
        elif health_score >= 50:
            return 'C-'
        else:
            return 'D'
    
    # ==================== Empty Summary Helpers ====================
    
    def _empty_booking_summary(self) -> Dict[str, Any]:
        """Return empty booking summary."""
        return {
            'total_bookings': 0,
            'confirmed_bookings': 0,
            'conversion_rate': 0,
            'cancellation_rate': 0,
            'average_lead_time': 0,
            'approval_rate': 0,
        }
    
    def _empty_financial_summary(self) -> Dict[str, Any]:
        """Return empty financial summary."""
        return {
            'total_revenue': 0,
            'net_profit': 0,
            'net_profit_margin': 0,
            'collection_rate': 0,
            'overdue_ratio': 0,
            'financial_health_score': 0,
            'performance_grade': 'N/A',
        }
    
    def _empty_occupancy_summary(self) -> Dict[str, Any]:
        """Return empty occupancy summary."""
        return {
            'current_occupancy': 0,
            'average_occupancy': 0,
            'total_beds': 0,
            'occupied_beds': 0,
            'available_beds': 0,
            'utilization_rate': 0,
            'occupancy_status': 'unknown',
        }
    
    def _empty_complaint_summary(self) -> Dict[str, Any]:
        """Return empty complaint summary."""
        return {
            'total_complaints': 0,
            'open_complaints': 0,
            'resolved_complaints': 0,
            'average_resolution_time': 0,
            'sla_compliance_rate': 0,
            'escalation_rate': 0,
            'efficiency_score': 0,
        }
    
    def _empty_supervisor_summary(self) -> Dict[str, Any]:
        """Return empty supervisor summary."""
        return {
            'total_supervisors': 0,
            'average_performance_score': 0,
            'total_complaints_resolved': 0,
            'average_sla_compliance': 0,
            'total_tasks_completed': 0,
        }
    
    def _empty_quick_stats(self) -> Dict[str, Any]:
        """Return empty quick stats."""
        return {
            'total_students': 0,
            'active_students': 0,
            'todays_check_ins': 0,
            'todays_check_outs': 0,
            'open_complaints': 0,
            'urgent_complaints': 0,
            'pending_maintenance': 0,
            'todays_revenue': 0,
            'monthly_revenue': 0,
            'outstanding_payments': 0,
            'occupancy_rate': 0,
        }
    
    # ==================== Platform-Wide Aggregation ====================
    
    def get_platform_wide_metrics(
        self,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Get platform-wide aggregated metrics across all hostels.
        
        Args:
            period_start: Period start date
            period_end: Period end date
            
        Returns:
            Dictionary with platform-wide aggregated metrics
        """
        query = QueryBuilder(PlatformMetrics, self.db)
        query = query.where(
            and_(
                PlatformMetrics.period_start >= period_start,
                PlatformMetrics.period_end <= period_end
            )
        )
        
        metrics = query.first()
        
        if not metrics:
            return self._empty_platform_metrics()
        
        return {
            'total_hostels': metrics.total_hostels,
            'active_hostels': metrics.active_hostels,
            'total_users': metrics.total_users,
            'total_students': metrics.total_students,
            'total_beds': metrics.total_beds_platform,
            'platform_occupancy': float(metrics.platform_occupancy_rate),
            'activation_rate': float(metrics.activation_rate) if metrics.activation_rate else 0,
            'avg_daily_active_users': metrics.avg_daily_active_users,
            'peak_concurrent_sessions': metrics.peak_concurrent_sessions,
        }
    
    def _empty_platform_metrics(self) -> Dict[str, Any]:
        """Return empty platform metrics."""
        return {
            'total_hostels': 0,
            'active_hostels': 0,
            'total_users': 0,
            'total_students': 0,
            'total_beds': 0,
            'platform_occupancy': 0,
            'activation_rate': 0,
            'avg_daily_active_users': 0,
            'peak_concurrent_sessions': 0,
        }
    
    # ==================== Comparative Analysis ====================
    
    def compare_hostels_performance(
        self,
        hostel_ids: List[UUID],
        period_start: date,
        period_end: date,
        metrics: Optional[List[str]] = None
    ) -> Dict[UUID, Dict[str, Any]]:
        """
        Compare performance across multiple hostels.
        
        Args:
            hostel_ids: List of hostel IDs to compare
            period_start: Period start date
            period_end: Period end date
            metrics: Specific metrics to compare (None for all)
            
        Returns:
            Dictionary mapping hostel IDs to their metrics
        """
        comparison = {}
        
        for hostel_id in hostel_ids:
            comparison[hostel_id] = self.get_unified_dashboard_metrics(
                hostel_id, period_start, period_end
            )
        
        # Add rankings
        comparison = self._add_hostel_rankings(comparison, metrics)
        
        return comparison
    
    def _add_hostel_rankings(
        self,
        comparison: Dict[UUID, Dict[str, Any]],
        metrics: Optional[List[str]] = None
    ) -> Dict[UUID, Dict[str, Any]]:
        """Add ranking information to comparison data."""
        # Extract values for ranking
        hostel_scores = {
            hostel_id: data['health_score']
            for hostel_id, data in comparison.items()
        }
        
        # Sort by score
        ranked = sorted(
            hostel_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Add rankings
        for rank, (hostel_id, score) in enumerate(ranked, start=1):
            comparison[hostel_id]['overall_rank'] = rank
            comparison[hostel_id]['total_hostels'] = len(ranked)
        
        return comparison
    
    # ==================== Time Series Analysis ====================
    
    def get_time_series_metrics(
        self,
        hostel_id: Optional[UUID],
        metric_keys: List[str],
        start_date: date,
        end_date: date,
        granularity: str = 'daily'
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get time series data for specified metrics.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            metric_keys: List of metric keys to retrieve
            start_date: Start date
            end_date: End date
            granularity: Time granularity (daily, weekly, monthly)
            
        Returns:
            Dictionary mapping metric keys to time series data
        """
        # Implementation would aggregate from various trend tables
        # For now, return structure
        return {
            metric_key: []
            for metric_key in metric_keys
        }
    
    # ==================== Export and Reporting ====================
    
    def export_analytics_report(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        format: str = 'json'
    ) -> Dict[str, Any]:
        """
        Export comprehensive analytics report.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            period_start: Period start date
            period_end: Period end date
            format: Export format (json, csv, excel)
            
        Returns:
            Formatted report data
        """
        report = {
            'metadata': {
                'hostel_id': str(hostel_id) if hostel_id else 'platform',
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'generated_at': datetime.utcnow().isoformat(),
                'format': format,
            },
            'metrics': self.get_unified_dashboard_metrics(
                hostel_id, period_start, period_end
            ),
        }
        
        return report