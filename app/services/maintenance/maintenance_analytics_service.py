"""
Maintenance Analytics Service

Provides comprehensive analytics and performance metrics for maintenance operations.

Features:
- Overall maintenance analytics and KPIs
- Performance metrics tracking
- Productivity analysis
- Category breakdown and trends
- Vendor performance comparison
- Cost analytics integration
- Predictive insights
"""

from __future__ import annotations

from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceAnalyticsRepository
from app.schemas.common import DateRangeFilter
from app.schemas.maintenance import (
    MaintenanceAnalytics,
    PerformanceMetrics,
    ProductivityMetrics,
    CategoryBreakdown,
    VendorPerformance,
)
from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.logging import logger


class MaintenanceAnalyticsService:
    """
    High-level service for maintenance analytics and reporting.

    Aggregates data from various sources to provide comprehensive
    insights into maintenance operations.
    """

    def __init__(self, analytics_repo: MaintenanceAnalyticsRepository) -> None:
        """
        Initialize the analytics service.

        Args:
            analytics_repo: Repository for analytics data access
        """
        if not analytics_repo:
            raise ValueError("MaintenanceAnalyticsRepository is required")
        self.analytics_repo = analytics_repo

    # -------------------------------------------------------------------------
    # Overall Analytics
    # -------------------------------------------------------------------------

    def get_hostel_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> MaintenanceAnalytics:
        """
        Get comprehensive maintenance analytics for a hostel.

        Includes request volumes, resolution times, costs, and trends.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            period: Date range for analytics

        Returns:
            MaintenanceAnalytics with comprehensive metrics

        Raises:
            ValidationException: If no data available or invalid parameters
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Generating analytics for hostel {hostel_id} "
                f"from {period.start_date} to {period.end_date}"
            )

            data = self.analytics_repo.get_analytics_for_hostel(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not data:
                raise ValidationException(
                    f"No maintenance analytics available for the period "
                    f"{period.start_date} to {period.end_date}"
                )

            analytics = MaintenanceAnalytics.model_validate(data)

            # Enrich with calculated insights
            analytics = self._enrich_analytics(analytics)

            logger.info(
                f"Analytics generated: {analytics.total_requests} total requests, "
                f"{analytics.avg_resolution_time_hours:.1f}h avg resolution"
            )

            return analytics

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating hostel analytics: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate maintenance analytics: {str(e)}"
            )

    def get_analytics_comparison(
        self,
        db: Session,
        hostel_id: UUID,
        current_period: DateRangeFilter,
        previous_period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Compare analytics between two periods.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            current_period: Current period date range
            previous_period: Previous period date range

        Returns:
            Dictionary with comparison metrics and trends
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            # Get analytics for both periods
            current = self.get_hostel_analytics(db, hostel_id, current_period)
            previous = self.get_hostel_analytics(db, hostel_id, previous_period)

            # Calculate changes
            comparison = {
                "current_period": {
                    "start": current_period.start_date.isoformat(),
                    "end": current_period.end_date.isoformat(),
                    "metrics": current.model_dump(),
                },
                "previous_period": {
                    "start": previous_period.start_date.isoformat(),
                    "end": previous_period.end_date.isoformat(),
                    "metrics": previous.model_dump(),
                },
                "changes": self._calculate_period_changes(current, previous),
                "trends": self._identify_trends(current, previous),
            }

            return comparison

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error comparing analytics: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to compare analytics: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Performance Metrics
    # -------------------------------------------------------------------------

    def get_performance_metrics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> PerformanceMetrics:
        """
        Get detailed performance metrics for maintenance operations.

        Includes SLA compliance, response times, and quality metrics.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            period: Date range for metrics

        Returns:
            PerformanceMetrics with detailed KPIs

        Raises:
            ValidationException: If no data available
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Generating performance metrics for hostel {hostel_id}"
            )

            data = self.analytics_repo.get_performance_metrics(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not data:
                raise ValidationException(
                    "No performance metrics available for this period"
                )

            metrics = PerformanceMetrics.model_validate(data)

            # Add performance insights
            metrics.insights = self._generate_performance_insights(metrics)

            logger.info(
                f"Performance metrics: {metrics.sla_compliance_rate:.1f}% SLA compliance"
            )

            return metrics

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating performance metrics: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate performance metrics: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Productivity Metrics
    # -------------------------------------------------------------------------

    def get_productivity_metrics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> ProductivityMetrics:
        """
        Get staff and vendor productivity metrics.

        Includes workload distribution, completion rates, and efficiency.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            period: Date range for metrics

        Returns:
            ProductivityMetrics with efficiency data

        Raises:
            ValidationException: If no data available
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Generating productivity metrics for hostel {hostel_id}"
            )

            data = self.analytics_repo.get_productivity_metrics(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not data:
                raise ValidationException(
                    "No productivity metrics available for this period"
                )

            metrics = ProductivityMetrics.model_validate(data)

            # Add productivity insights
            metrics.insights = self._generate_productivity_insights(metrics)

            logger.info(
                f"Productivity metrics: {metrics.avg_tasks_per_staff:.1f} "
                f"avg tasks/staff"
            )

            return metrics

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating productivity metrics: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate productivity metrics: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Category Analytics
    # -------------------------------------------------------------------------

    def get_category_breakdown(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> CategoryBreakdown:
        """
        Get breakdown of maintenance requests by category.

        Includes volumes, costs, and resolution times per category.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            period: Date range for breakdown

        Returns:
            CategoryBreakdown with category-wise metrics

        Raises:
            ValidationException: If no data available
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Generating category breakdown for hostel {hostel_id}"
            )

            data = self.analytics_repo.get_category_breakdown(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not data:
                raise ValidationException(
                    "No category breakdown available for this period"
                )

            breakdown = CategoryBreakdown.model_validate(data)

            # Sort categories by request volume
            if breakdown.categories:
                breakdown.categories.sort(
                    key=lambda x: x.get("total_requests", 0),
                    reverse=True
                )

            # Add category insights
            breakdown.insights = self._generate_category_insights(breakdown)

            logger.info(
                f"Category breakdown: {len(breakdown.categories)} categories analyzed"
            )

            return breakdown

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating category breakdown: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate category breakdown: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Vendor Performance Analytics
    # -------------------------------------------------------------------------

    def get_vendor_performance(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> VendorPerformance:
        """
        Get comparative vendor performance analytics.

        Includes completion rates, quality scores, and cost efficiency.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            period: Date range for analysis

        Returns:
            VendorPerformance with vendor comparison

        Raises:
            ValidationException: If no data available
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Generating vendor performance analytics for hostel {hostel_id}"
            )

            data = self.analytics_repo.get_vendor_performance(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not data:
                raise ValidationException(
                    "No vendor performance data available for this period"
                )

            performance = VendorPerformance.model_validate(data)

            # Rank vendors by overall performance
            if performance.vendors:
                performance.vendors.sort(
                    key=lambda x: x.get("overall_score", 0),
                    reverse=True
                )

            # Add vendor insights
            performance.insights = self._generate_vendor_insights(performance)

            logger.info(
                f"Vendor performance: {len(performance.vendors)} vendors analyzed"
            )

            return performance

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating vendor performance: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate vendor performance analytics: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Dashboard and Summary
    # -------------------------------------------------------------------------

    def get_dashboard_summary(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get summary dashboard data for maintenance overview.

        Provides key metrics for the current period with quick insights.

        Args:
            db: Database session
            hostel_id: UUID of the hostel

        Returns:
            Dictionary with dashboard metrics
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            # Default to last 30 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            period = DateRangeFilter(start_date=start_date, end_date=end_date)

            # Get key metrics
            analytics = self.get_hostel_analytics(db, hostel_id, period)
            performance = self.get_performance_metrics(db, hostel_id, period)

            # Build dashboard summary
            dashboard = {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": 30,
                },
                "overview": {
                    "total_requests": analytics.total_requests,
                    "open_requests": analytics.open_requests,
                    "completed_requests": analytics.completed_requests,
                    "overdue_requests": analytics.overdue_requests,
                },
                "performance": {
                    "avg_resolution_hours": analytics.avg_resolution_time_hours,
                    "sla_compliance_rate": performance.sla_compliance_rate,
                    "first_response_time_hours": performance.avg_first_response_time_hours,
                },
                "costs": {
                    "total_cost": analytics.total_cost,
                    "avg_cost_per_request": analytics.avg_cost_per_request,
                },
                "alerts": self._generate_dashboard_alerts(analytics, performance),
                "quick_insights": self._generate_quick_insights(analytics, performance),
            }

            return dashboard

        except Exception as e:
            logger.error(
                f"Error generating dashboard summary: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate dashboard summary: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _validate_date_range(self, period: DateRangeFilter) -> None:
        """Validate date range parameters."""
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")

        if period.start_date > period.end_date:
            raise ValidationException("start_date must be before or equal to end_date")

        # Check for unreasonably long periods (more than 1 year)
        if (period.end_date - period.start_date).days > 365:
            logger.warning("Analytics period exceeds 1 year - may affect performance")

    def _enrich_analytics(
        self,
        analytics: MaintenanceAnalytics
    ) -> MaintenanceAnalytics:
        """Add calculated fields to analytics."""
        # Calculate completion rate
        if analytics.total_requests > 0:
            analytics.completion_rate = (
                analytics.completed_requests / analytics.total_requests * 100
            )
        else:
            analytics.completion_rate = 0

        # Calculate overdue rate
        if analytics.total_requests > 0:
            analytics.overdue_rate = (
                analytics.overdue_requests / analytics.total_requests * 100
            )
        else:
            analytics.overdue_rate = 0

        return analytics

    def _calculate_period_changes(
        self,
        current: MaintenanceAnalytics,
        previous: MaintenanceAnalytics,
    ) -> Dict[str, Any]:
        """Calculate changes between periods."""
        def calc_change(curr_val: float, prev_val: float) -> Dict[str, Any]:
            if prev_val == 0:
                return {"value": curr_val, "change_pct": None, "direction": "new"}
            
            change_pct = ((curr_val - prev_val) / prev_val) * 100
            direction = "up" if change_pct > 0 else "down" if change_pct < 0 else "stable"
            
            return {
                "current": curr_val,
                "previous": prev_val,
                "change_pct": round(change_pct, 2),
                "direction": direction,
            }

        return {
            "total_requests": calc_change(
                current.total_requests,
                previous.total_requests
            ),
            "avg_resolution_time": calc_change(
                current.avg_resolution_time_hours,
                previous.avg_resolution_time_hours
            ),
            "total_cost": calc_change(
                current.total_cost,
                previous.total_cost
            ),
            "completion_rate": calc_change(
                current.completion_rate or 0,
                previous.completion_rate or 0
            ),
        }

    def _identify_trends(
        self,
        current: MaintenanceAnalytics,
        previous: MaintenanceAnalytics,
    ) -> List[str]:
        """Identify significant trends between periods."""
        trends = []

        # Request volume trend
        if current.total_requests > previous.total_requests * 1.2:
            trends.append("Significant increase in maintenance requests (+20%)")
        elif current.total_requests < previous.total_requests * 0.8:
            trends.append("Significant decrease in maintenance requests (-20%)")

        # Resolution time trend
        if current.avg_resolution_time_hours > previous.avg_resolution_time_hours * 1.3:
            trends.append("Resolution times increasing - investigate capacity")
        elif current.avg_resolution_time_hours < previous.avg_resolution_time_hours * 0.7:
            trends.append("Resolution times improving - efficiency gains")

        # Cost trend
        if current.total_cost > previous.total_cost * 1.25:
            trends.append("Maintenance costs increasing significantly (+25%)")

        return trends

    def _generate_performance_insights(
        self,
        metrics: PerformanceMetrics
    ) -> List[str]:
        """Generate insights from performance metrics."""
        insights = []

        if metrics.sla_compliance_rate >= 95:
            insights.append("Excellent SLA compliance")
        elif metrics.sla_compliance_rate < 80:
            insights.append("SLA compliance below target - review processes")

        if metrics.avg_first_response_time_hours > 4:
            insights.append("First response time high - consider staffing levels")

        if metrics.rework_rate and metrics.rework_rate > 15:
            insights.append("High rework rate - quality concerns")

        return insights

    def _generate_productivity_insights(
        self,
        metrics: ProductivityMetrics
    ) -> List[str]:
        """Generate insights from productivity metrics."""
        insights = []

        if metrics.avg_tasks_per_staff > 20:
            insights.append("Staff workload high - consider additional resources")
        elif metrics.avg_tasks_per_staff < 5:
            insights.append("Staff underutilized - optimize assignments")

        if metrics.staff_utilization_rate and metrics.staff_utilization_rate < 60:
            insights.append("Low staff utilization - review scheduling")

        return insights

    def _generate_category_insights(
        self,
        breakdown: CategoryBreakdown
    ) -> List[str]:
        """Generate insights from category breakdown."""
        insights = []

        if not breakdown.categories:
            return insights

        # Find top category by volume
        top_category = max(
            breakdown.categories,
            key=lambda x: x.get("total_requests", 0)
        )
        insights.append(
            f"Top category: {top_category.get('category')} "
            f"({top_category.get('total_requests')} requests)"
        )

        # Find category with longest resolution time
        slowest_category = max(
            breakdown.categories,
            key=lambda x: x.get("avg_resolution_hours", 0)
        )
        if slowest_category.get("avg_resolution_hours", 0) > 48:
            insights.append(
                f"{slowest_category.get('category')} category has slow resolution "
                f"({slowest_category.get('avg_resolution_hours')}h avg)"
            )

        return insights

    def _generate_vendor_insights(
        self,
        performance: VendorPerformance
    ) -> List[str]:
        """Generate insights from vendor performance."""
        insights = []

        if not performance.vendors:
            return insights

        # Find top performer
        top_vendor = performance.vendors[0] if performance.vendors else None
        if top_vendor:
            insights.append(
                f"Top performer: {top_vendor.get('vendor_name')} "
                f"(score: {top_vendor.get('overall_score', 0):.1f})"
            )

        # Find underperformers
        underperformers = [
            v for v in performance.vendors
            if v.get("overall_score", 0) < 3.0
        ]
        if underperformers:
            insights.append(
                f"{len(underperformers)} vendor(s) below acceptable performance"
            )

        return insights

    def _generate_dashboard_alerts(
        self,
        analytics: MaintenanceAnalytics,
        performance: PerformanceMetrics,
    ) -> List[Dict[str, Any]]:
        """Generate alerts for dashboard."""
        alerts = []

        # Critical alerts
        if analytics.overdue_requests > 10:
            alerts.append({
                "level": "critical",
                "message": f"{analytics.overdue_requests} overdue requests",
                "action": "Review and prioritize overdue items",
            })

        if performance.sla_compliance_rate < 80:
            alerts.append({
                "level": "warning",
                "message": f"SLA compliance at {performance.sla_compliance_rate:.1f}%",
                "action": "Investigate SLA breaches",
            })

        # Info alerts
        if analytics.open_requests > 50:
            alerts.append({
                "level": "info",
                "message": f"{analytics.open_requests} open requests",
                "action": "Monitor workload",
            })

        return alerts

    def _generate_quick_insights(
        self,
        analytics: MaintenanceAnalytics,
        performance: PerformanceMetrics,
    ) -> List[str]:
        """Generate quick insights for dashboard."""
        insights = []

        completion_rate = (
            analytics.completed_requests / analytics.total_requests * 100
            if analytics.total_requests > 0
            else 0
        )

        insights.append(f"{completion_rate:.0f}% completion rate this period")
        insights.append(
            f"Average resolution: {analytics.avg_resolution_time_hours:.1f} hours"
        )
        insights.append(
            f"SLA compliance: {performance.sla_compliance_rate:.1f}%"
        )

        return insights