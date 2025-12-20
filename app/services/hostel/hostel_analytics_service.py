# --- File: C:\Hostel-Main\app\services\hostel\hostel_analytics_service.py ---
"""
Hostel analytics service for performance tracking and insights generation.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hostel.hostel_analytics import HostelAnalytic, OccupancyTrend, RevenueTrend
from app.repositories.hostel.hostel_analytics_repository import (
    HostelAnalyticsRepository,
    OccupancyTrendRepository,
    RevenueTrendRepository
)
from app.core.exceptions import ValidationError, ResourceNotFoundError
from app.services.base.base_service import BaseService


class HostelAnalyticsService(BaseService):
    """
    Hostel analytics service for performance tracking and insights.
    
    Handles analytics generation, trend analysis, performance metrics,
    and business intelligence reporting.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.analytics_repo = HostelAnalyticsRepository(session)
        self.occupancy_repo = OccupancyTrendRepository(session)
        self.revenue_repo = RevenueTrendRepository(session)

    # ===== Analytics Generation =====

    async def generate_monthly_analytics(
        self,
        hostel_id: UUID,
        year: int,
        month: int
    ) -> HostelAnalytic:
        """
        Generate comprehensive monthly analytics for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            year: Year
            month: Month (1-12)
            
        Returns:
            Generated HostelAnalytic instance
            
        Raises:
            ValidationError: If month/year is invalid
        """
        # Validate month and year
        if not (1 <= month <= 12):
            raise ValidationError("Month must be between 1 and 12")
        
        if year < 2000 or year > datetime.utcnow().year + 1:
            raise ValidationError(f"Invalid year: {year}")
        
        # Generate analytics
        analytics = await self.analytics_repo.generate_monthly_analytics(
            hostel_id,
            year,
            month
        )
        
        # Calculate performance score
        await self.analytics_repo.calculate_performance_score(analytics.id)
        
        # Log event
        await self._log_event('analytics_generated', {
            'hostel_id': hostel_id,
            'period': f"{year}-{month:02d}",
            'analytics_id': analytics.id
        })
        
        return analytics

    async def generate_yearly_analytics(
        self,
        hostel_id: UUID,
        year: int
    ) -> HostelAnalytic:
        """
        Generate yearly analytics summary.
        
        Args:
            hostel_id: Hostel UUID
            year: Year
            
        Returns:
            Generated HostelAnalytic instance
        """
        return await self.analytics_repo.generate_yearly_analytics(hostel_id, year)

    async def generate_current_month_analytics(
        self,
        hostel_id: UUID
    ) -> HostelAnalytic:
        """Generate analytics for the current month."""
        now = datetime.utcnow()
        return await self.generate_monthly_analytics(
            hostel_id,
            now.year,
            now.month
        )

    # ===== Performance Metrics =====

    async def get_performance_trends(
        self,
        hostel_id: UUID,
        period_type: str = "monthly",
        months: int = 12
    ) -> List[HostelAnalytic]:
        """
        Get performance trends for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            period_type: Type of period (daily, weekly, monthly, yearly)
            months: Number of months to retrieve
            
        Returns:
            List of analytics records
        """
        return await self.analytics_repo.get_performance_trends(
            hostel_id,
            period_type,
            limit=months
        )

    async def get_performance_summary(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance summary.
        
        Args:
            hostel_id: Hostel UUID
            period_days: Analysis period in days
            
        Returns:
            Performance summary with metrics and trends
        """
        # Get analytics data
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        analytics = await self.analytics_repo.find_by_criteria(
            {
                'hostel_id': hostel_id,
                'period_type': 'monthly'
            },
            custom_filter=lambda q: q.filter(
                HostelAnalytic.period_start >= start_date
            ),
            order_by=[HostelAnalytic.period_start.desc()]
        )
        
        if not analytics:
            return {
                'hostel_id': hostel_id,
                'message': 'No analytics data available',
                'period_days': period_days
            }
        
        # Calculate averages
        avg_occupancy = sum(a.average_occupancy_rate for a in analytics) / len(analytics)
        avg_revenue = sum(a.total_revenue for a in analytics) / len(analytics)
        avg_rating = sum(a.average_rating for a in analytics) / len(analytics)
        
        # Get trends
        occupancy_values = [float(a.average_occupancy_rate) for a in analytics]
        revenue_values = [float(a.total_revenue) for a in analytics]
        
        return {
            'hostel_id': hostel_id,
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': period_days
            },
            'averages': {
                'occupancy_rate': float(avg_occupancy),
                'revenue': float(avg_revenue),
                'rating': float(avg_rating)
            },
            'trends': {
                'occupancy': self._calculate_trend(occupancy_values),
                'revenue': self._calculate_trend(revenue_values)
            },
            'latest_score': float(analytics[0].overall_performance_score) if analytics else 0,
            'total_records': len(analytics)
        }

    async def compare_periods(
        self,
        hostel_id: UUID,
        current_period: Tuple[date, date],
        comparison_period: Tuple[date, date]
    ) -> Dict[str, Any]:
        """
        Compare performance between two periods.
        
        Args:
            hostel_id: Hostel UUID
            current_period: Current period (start, end)
            comparison_period: Comparison period (start, end)
            
        Returns:
            Comparison analysis
        """
        # Get analytics for both periods
        current_analytics = await self._get_period_analytics(
            hostel_id,
            current_period[0],
            current_period[1]
        )
        
        comparison_analytics = await self._get_period_analytics(
            hostel_id,
            comparison_period[0],
            comparison_period[1]
        )
        
        if not current_analytics or not comparison_analytics:
            return {
                'error': 'Insufficient data for comparison',
                'current_records': len(current_analytics),
                'comparison_records': len(comparison_analytics)
            }
        
        # Calculate metrics
        current_metrics = self._aggregate_metrics(current_analytics)
        comparison_metrics = self._aggregate_metrics(comparison_analytics)
        
        # Calculate changes
        changes = {}
        for key in current_metrics:
            if key in comparison_metrics:
                current = current_metrics[key]
                previous = comparison_metrics[key]
                if previous != 0:
                    change_pct = ((current - previous) / previous) * 100
                else:
                    change_pct = 0
                
                changes[key] = {
                    'current': current,
                    'previous': previous,
                    'change': current - previous,
                    'change_percentage': round(change_pct, 2)
                }
        
        return {
            'hostel_id': hostel_id,
            'current_period': {
                'start': current_period[0],
                'end': current_period[1]
            },
            'comparison_period': {
                'start': comparison_period[0],
                'end': comparison_period[1]
            },
            'metrics': changes
        }

    # ===== Occupancy Tracking =====

    async def record_daily_occupancy(
        self,
        hostel_id: UUID,
        data_date: date,
        occupancy_data: Dict[str, Any]
    ) -> OccupancyTrend:
        """
        Record daily occupancy data.
        
        Args:
            hostel_id: Hostel UUID
            data_date: Date of the data
            occupancy_data: Occupancy metrics
            
        Returns:
            Created/updated OccupancyTrend instance
        """
        # Calculate occupancy rate if not provided
        if 'occupancy_rate' not in occupancy_data:
            if occupancy_data.get('total_beds', 0) > 0:
                rate = (occupancy_data['occupied_beds'] / occupancy_data['total_beds']) * 100
                occupancy_data['occupancy_rate'] = Decimal(str(round(rate, 2)))
        
        # Calculate available beds if not provided
        if 'available_beds' not in occupancy_data:
            occupancy_data['available_beds'] = (
                occupancy_data.get('total_beds', 0) - 
                occupancy_data.get('occupied_beds', 0)
            )
        
        return await self.occupancy_repo.record_daily_occupancy(
            hostel_id,
            data_date,
            occupancy_data
        )

    async def get_occupancy_trends(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> List[OccupancyTrend]:
        """
        Get occupancy trends for specified days.
        
        Args:
            hostel_id: Hostel UUID
            days: Number of days to retrieve
            
        Returns:
            List of occupancy trends
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        return await self.occupancy_repo.get_occupancy_trends(
            hostel_id,
            start_date,
            end_date
        )

    async def get_peak_occupancy_days(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> List[OccupancyTrend]:
        """Get days with highest occupancy."""
        return await self.occupancy_repo.get_peak_occupancy_days(
            hostel_id,
            period_days
        )

    # ===== Revenue Tracking =====

    async def record_daily_revenue(
        self,
        hostel_id: UUID,
        data_date: date,
        revenue_data: Dict[str, Any]
    ) -> RevenueTrend:
        """
        Record daily revenue data.
        
        Args:
            hostel_id: Hostel UUID
            data_date: Date of the data
            revenue_data: Revenue metrics
            
        Returns:
            Created/updated RevenueTrend instance
        """
        # Calculate total revenue if not provided
        if 'total_revenue' not in revenue_data:
            revenue_data['total_revenue'] = (
                revenue_data.get('rent_revenue', Decimal('0')) +
                revenue_data.get('mess_revenue', Decimal('0')) +
                revenue_data.get('other_revenue', Decimal('0'))
            )
        
        # Calculate average revenue per student if not provided
        if 'average_revenue_per_student' not in revenue_data:
            student_count = revenue_data.get('student_count', 0)
            if student_count > 0:
                avg = revenue_data['total_revenue'] / student_count
                revenue_data['average_revenue_per_student'] = avg
        
        return await self.revenue_repo.record_daily_revenue(
            hostel_id,
            data_date,
            revenue_data
        )

    async def get_revenue_trends(
        self,
        hostel_id: UUID,
        days: int = 30,
        period_type: str = "daily"
    ) -> List[RevenueTrend]:
        """
        Get revenue trends for specified days.
        
        Args:
            hostel_id: Hostel UUID
            days: Number of days to retrieve
            period_type: Period type (daily, monthly)
            
        Returns:
            List of revenue trends
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        return await self.revenue_repo.get_revenue_trends(
            hostel_id,
            start_date,
            end_date,
            period_type
        )

    async def calculate_revenue_growth(
        self,
        hostel_id: UUID,
        current_period: Tuple[date, date],
        comparison_period: Tuple[date, date]
    ) -> Dict[str, Any]:
        """
        Calculate revenue growth between periods.
        
        Args:
            hostel_id: Hostel UUID
            current_period: Current period (start, end)
            comparison_period: Comparison period (start, end)
            
        Returns:
            Revenue growth analysis
        """
        return await self.revenue_repo.calculate_revenue_growth(
            hostel_id,
            current_period,
            comparison_period
        )

    # ===== Insights and Recommendations =====

    async def generate_insights(
        self,
        hostel_id: UUID,
        period_months: int = 6
    ) -> Dict[str, Any]:
        """
        Generate actionable insights based on analytics.
        
        Args:
            hostel_id: Hostel UUID
            period_months: Analysis period in months
            
        Returns:
            Insights and recommendations
        """
        return await self.analytics_repo.generate_insights(
            hostel_id,
            period_months
        )

    async def get_improvement_suggestions(
        self,
        hostel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get improvement suggestions based on performance.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            List of improvement suggestions
        """
        # Get recent analytics
        analytics = await self.get_performance_trends(hostel_id, limit=3)
        
        if not analytics:
            return []
        
        suggestions = []
        latest = analytics[0]
        
        # Occupancy suggestions
        if latest.average_occupancy_rate < Decimal('60'):
            suggestions.append({
                'category': 'occupancy',
                'priority': 'high',
                'issue': f'Low occupancy rate ({latest.average_occupancy_rate}%)',
                'suggestion': 'Consider promotional campaigns or pricing adjustments',
                'expected_impact': 'Increase occupancy by 10-15%'
            })
        
        # Revenue suggestions
        if latest.collection_rate < Decimal('90'):
            suggestions.append({
                'category': 'revenue',
                'priority': 'high',
                'issue': f'Low collection rate ({latest.collection_rate}%)',
                'suggestion': 'Implement automated payment reminders and stricter policies',
                'expected_impact': 'Improve collection rate by 5-10%'
            })
        
        # Service quality suggestions
        if latest.average_rating < Decimal('3.5'):
            suggestions.append({
                'category': 'service',
                'priority': 'critical',
                'issue': f'Low average rating ({latest.average_rating})',
                'suggestion': 'Address top complaints and improve facilities',
                'expected_impact': 'Increase rating by 0.5-1.0 points'
            })
        
        # Complaint management suggestions
        if latest.complaint_resolution_rate < Decimal('80'):
            suggestions.append({
                'category': 'operations',
                'priority': 'medium',
                'issue': f'Low complaint resolution rate ({latest.complaint_resolution_rate}%)',
                'suggestion': 'Streamline complaint handling process and reduce resolution time',
                'expected_impact': 'Improve satisfaction and retention'
            })
        
        return suggestions

    # ===== Reporting =====

    async def get_executive_summary(
        self,
        hostel_id: UUID,
        period_months: int = 1
    ) -> Dict[str, Any]:
        """
        Generate executive summary report.
        
        Args:
            hostel_id: Hostel UUID
            period_months: Report period in months
            
        Returns:
            Executive summary
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_months * 30)
        
        # Get analytics
        analytics = await self._get_period_analytics(hostel_id, start_date, end_date)
        
        if not analytics:
            return {
                'error': 'No data available for the specified period',
                'hostel_id': hostel_id,
                'period_months': period_months
            }
        
        # Aggregate metrics
        total_revenue = sum(a.total_revenue for a in analytics)
        avg_occupancy = sum(a.average_occupancy_rate for a in analytics) / len(analytics)
        avg_rating = sum(a.average_rating for a in analytics) / len(analytics)
        
        # Get insights
        insights = await self.generate_insights(hostel_id, period_months)
        suggestions = await self.get_improvement_suggestions(hostel_id)
        
        return {
            'hostel_id': hostel_id,
            'period': {
                'start': start_date,
                'end': end_date,
                'months': period_months
            },
            'key_metrics': {
                'total_revenue': float(total_revenue),
                'average_occupancy': float(avg_occupancy),
                'average_rating': float(avg_rating),
                'performance_score': float(analytics[0].overall_performance_score) if analytics else 0
            },
            'insights': insights,
            'suggestions': suggestions[:5],  # Top 5 suggestions
            'generated_at': datetime.utcnow()
        }

    # ===== Helper Methods =====

    async def _get_period_analytics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[HostelAnalytic]:
        """Get analytics for a specific period."""
        return await self.analytics_repo.find_by_criteria(
            {'hostel_id': hostel_id},
            custom_filter=lambda q: q.filter(
                HostelAnalytic.period_start >= start_date,
                HostelAnalytic.period_end <= end_date
            ),
            order_by=[HostelAnalytic.period_start]
        )

    def _aggregate_metrics(self, analytics: List[HostelAnalytic]) -> Dict[str, float]:
        """Aggregate metrics from multiple analytics records."""
        if not analytics:
            return {}
        
        return {
            'occupancy_rate': float(sum(a.average_occupancy_rate for a in analytics) / len(analytics)),
            'revenue': float(sum(a.total_revenue for a in analytics)),
            'rating': float(sum(a.average_rating for a in analytics) / len(analytics)),
            'collection_rate': float(sum(a.collection_rate for a in analytics) / len(analytics)),
            'performance_score': float(sum(a.overall_performance_score for a in analytics) / len(analytics))
        }

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return 'stable'
        
        increases = sum(1 for i in range(1, len(values)) if values[i] > values[i-1])
        decreases = sum(1 for i in range(1, len(values)) if values[i] < values[i-1])
        
        if increases > decreases * 1.5:
            return 'increasing'
        elif decreases > increases * 1.5:
            return 'decreasing'
        else:
            return 'stable'

    async def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log service events for audit and analytics."""
        pass