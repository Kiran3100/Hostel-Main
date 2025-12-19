"""
Booking Analytics Repository for booking performance tracking.

Provides comprehensive booking analytics with:
- Conversion funnel analysis
- Cancellation pattern tracking
- Source performance metrics
- Revenue optimization insights
- Predictive demand forecasting
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, extract
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationManager
from app.models.analytics.booking_analytics import (
    BookingKPI,
    BookingTrendPoint,
    BookingFunnelAnalytics,
    CancellationAnalytics,
    BookingSourceMetrics,
    BookingAnalyticsSummary,
)


class BookingAnalyticsRepository(BaseRepository):
    """Repository for booking analytics operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.pagination = PaginationManager()
    
    # ==================== KPI Operations ====================
    
    def create_booking_kpi(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        kpi_data: Dict[str, Any]
    ) -> BookingKPI:
        """
        Create or update booking KPI record.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            period_start: Period start date
            period_end: Period end date
            kpi_data: KPI metrics data
            
        Returns:
            Created or updated BookingKPI instance
        """
        # Check if exists
        existing = self.get_booking_kpi(hostel_id, period_start, period_end)
        
        if existing:
            # Update existing
            for key, value in kpi_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        # Create new
        kpi = BookingKPI(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **kpi_data
        )
        
        self.db.add(kpi)
        self.db.commit()
        self.db.refresh(kpi)
        
        return kpi
    
    def get_booking_kpi(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[BookingKPI]:
        """Get booking KPI for specific period."""
        query = QueryBuilder(BookingKPI, self.db)
        
        if hostel_id:
            query = query.where(BookingKPI.hostel_id == hostel_id)
        else:
            query = query.where(BookingKPI.hostel_id.is_(None))
        
        query = query.where(
            and_(
                BookingKPI.period_start == period_start,
                BookingKPI.period_end == period_end
            )
        )
        
        return query.first()
    
    def get_booking_kpis_by_date_range(
        self,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date
    ) -> List[BookingKPI]:
        """Get all booking KPIs within date range."""
        query = QueryBuilder(BookingKPI, self.db)
        
        if hostel_id:
            query = query.where(BookingKPI.hostel_id == hostel_id)
        
        query = query.where(
            or_(
                and_(
                    BookingKPI.period_start >= start_date,
                    BookingKPI.period_start <= end_date
                ),
                and_(
                    BookingKPI.period_end >= start_date,
                    BookingKPI.period_end <= end_date
                )
            )
        ).order_by(BookingKPI.period_start.desc())
        
        return query.all()
    
    # ==================== Trend Analysis ====================
    
    def add_trend_points(
        self,
        kpi_id: UUID,
        trend_points: List[Dict[str, Any]]
    ) -> List[BookingTrendPoint]:
        """
        Add multiple trend points for a KPI.
        
        Args:
            kpi_id: Parent KPI ID
            trend_points: List of trend point data
            
        Returns:
            List of created BookingTrendPoint instances
        """
        created_points = []
        
        for point_data in trend_points:
            # Check if point exists
            existing = self.db.query(BookingTrendPoint).filter(
                and_(
                    BookingTrendPoint.kpi_id == kpi_id,
                    BookingTrendPoint.trend_date == point_data['trend_date']
                )
            ).first()
            
            if existing:
                # Update existing
                for key, value in point_data.items():
                    if key != 'trend_date':
                        setattr(existing, key, value)
                created_points.append(existing)
            else:
                # Create new
                point = BookingTrendPoint(
                    kpi_id=kpi_id,
                    **point_data
                )
                self.db.add(point)
                created_points.append(point)
        
        self.db.commit()
        for point in created_points:
            self.db.refresh(point)
        
        return created_points
    
    def get_trend_points(
        self,
        kpi_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[BookingTrendPoint]:
        """Get trend points for a KPI."""
        query = QueryBuilder(BookingTrendPoint, self.db)
        query = query.where(BookingTrendPoint.kpi_id == kpi_id)
        
        if start_date:
            query = query.where(BookingTrendPoint.trend_date >= start_date)
        if end_date:
            query = query.where(BookingTrendPoint.trend_date <= end_date)
        
        query = query.order_by(BookingTrendPoint.trend_date.asc())
        
        return query.all()
    
    def calculate_trend_direction(
        self,
        kpi_id: UUID,
        metric: str = 'total_bookings'
    ) -> Dict[str, Any]:
        """
        Calculate trend direction and percentage for a metric.
        
        Args:
            kpi_id: KPI ID
            metric: Metric name to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        points = self.get_trend_points(kpi_id)
        
        if len(points) < 2:
            return {
                'direction': 'stable',
                'percentage': 0,
                'confidence': 0,
            }
        
        # Get values
        values = [getattr(point, metric) for point in points]
        
        # Calculate linear regression
        n = len(values)
        x = list(range(n))
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(xi * yi for xi, yi in zip(x, values))
        sum_x2 = sum(xi * xi for xi in x)
        
        # Calculate slope
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Calculate percentage change
        if values[0] != 0:
            percentage = ((values[-1] - values[0]) / values[0]) * 100
        else:
            percentage = 0
        
        # Determine direction
        if slope > 0.1:
            direction = 'up'
        elif slope < -0.1:
            direction = 'down'
        else:
            direction = 'stable'
        
        # Calculate R-squared for confidence
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in values)
        
        if ss_tot > 0:
            intercept = (sum_y - slope * sum_x) / n
            y_pred = [slope * xi + intercept for xi in x]
            ss_res = sum((yi - ypi) ** 2 for yi, ypi in zip(values, y_pred))
            r_squared = 1 - (ss_res / ss_tot)
        else:
            r_squared = 0
        
        return {
            'direction': direction,
            'percentage': round(percentage, 2),
            'confidence': round(r_squared, 4),
            'slope': round(slope, 4),
        }
    
    # ==================== Conversion Funnel ====================
    
    def create_funnel_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        funnel_data: Dict[str, Any]
    ) -> BookingFunnelAnalytics:
        """Create or update booking funnel analytics."""
        # Check if exists
        existing = self.db.query(BookingFunnelAnalytics).filter(
            and_(
                BookingFunnelAnalytics.hostel_id == hostel_id if hostel_id else BookingFunnelAnalytics.hostel_id.is_(None),
                BookingFunnelAnalytics.period_start == period_start,
                BookingFunnelAnalytics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in funnel_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        funnel = BookingFunnelAnalytics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **funnel_data
        )
        
        self.db.add(funnel)
        self.db.commit()
        self.db.refresh(funnel)
        
        return funnel
    
    def calculate_conversion_rates(
        self,
        funnel: BookingFunnelAnalytics
    ) -> Dict[str, float]:
        """Calculate all conversion rates for a funnel."""
        rates = {}
        
        # View to start
        if funnel.hostel_page_views > 0:
            rates['view_to_start'] = (
                funnel.booking_form_starts / funnel.hostel_page_views
            ) * 100
        else:
            rates['view_to_start'] = 0
        
        # Start to submit
        if funnel.booking_form_starts > 0:
            rates['start_to_submit'] = (
                funnel.booking_submissions / funnel.booking_form_starts
            ) * 100
        else:
            rates['start_to_submit'] = 0
        
        # Submit to confirm
        if funnel.booking_submissions > 0:
            rates['submit_to_confirm'] = (
                funnel.bookings_confirmed / funnel.booking_submissions
            ) * 100
        else:
            rates['submit_to_confirm'] = 0
        
        # Overall
        if funnel.hostel_page_views > 0:
            rates['overall'] = (
                funnel.bookings_confirmed / funnel.hostel_page_views
            ) * 100
        else:
            rates['overall'] = 0
        
        return rates
    
    def identify_funnel_bottleneck(
        self,
        funnel: BookingFunnelAnalytics
    ) -> Dict[str, Any]:
        """Identify the largest drop-off stage in funnel."""
        stages = {
            'view_to_start': {
                'stage': 'View to Form Start',
                'drop_off': funnel.hostel_page_views - funnel.booking_form_starts,
                'rate': funnel.view_to_start_rate,
            },
            'start_to_submit': {
                'stage': 'Form Start to Submit',
                'drop_off': funnel.booking_form_starts - funnel.booking_submissions,
                'rate': funnel.start_to_submit_rate,
            },
            'submit_to_confirm': {
                'stage': 'Submit to Confirm',
                'drop_off': funnel.booking_submissions - funnel.bookings_confirmed,
                'rate': funnel.submit_to_confirm_rate,
            },
        }
        
        # Find largest drop-off
        bottleneck = max(
            stages.values(),
            key=lambda x: x['drop_off']
        )
        
        return bottleneck
    
    # ==================== Cancellation Analysis ====================
    
    def create_cancellation_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        cancellation_data: Dict[str, Any]
    ) -> CancellationAnalytics:
        """Create or update cancellation analytics."""
        existing = self.db.query(CancellationAnalytics).filter(
            and_(
                CancellationAnalytics.hostel_id == hostel_id if hostel_id else CancellationAnalytics.hostel_id.is_(None),
                CancellationAnalytics.period_start == period_start,
                CancellationAnalytics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in cancellation_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        analytics = CancellationAnalytics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **cancellation_data
        )
        
        self.db.add(analytics)
        self.db.commit()
        self.db.refresh(analytics)
        
        return analytics
    
    def analyze_cancellation_patterns(
        self,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Analyze cancellation patterns over time."""
        analytics_records = self.db.query(CancellationAnalytics).filter(
            and_(
                CancellationAnalytics.hostel_id == hostel_id if hostel_id else CancellationAnalytics.hostel_id.is_(None),
                CancellationAnalytics.period_start >= start_date,
                CancellationAnalytics.period_end <= end_date
            )
        ).all()
        
        if not analytics_records:
            return self._empty_cancellation_pattern()
        
        # Aggregate data
        total_cancellations = sum(a.total_cancellations for a in analytics_records)
        avg_cancellation_rate = sum(
            float(a.cancellation_rate) for a in analytics_records
        ) / len(analytics_records)
        
        # Collect all reasons
        all_reasons = {}
        for record in analytics_records:
            if record.cancellations_by_reason:
                for reason, count in record.cancellations_by_reason.items():
                    all_reasons[reason] = all_reasons.get(reason, 0) + count
        
        # Top reason
        top_reason = max(
            all_reasons.items(),
            key=lambda x: x[1]
        )[0] if all_reasons else None
        
        # Timing analysis
        avg_time_before_checkin = sum(
            float(a.average_time_before_checkin_days) for a in analytics_records
        ) / len(analytics_records)
        
        total_within_24h = sum(a.cancellations_within_24h for a in analytics_records)
        late_cancellation_rate = (
            total_within_24h / total_cancellations * 100
        ) if total_cancellations > 0 else 0
        
        return {
            'total_cancellations': total_cancellations,
            'average_cancellation_rate': round(avg_cancellation_rate, 2),
            'top_cancellation_reason': top_reason,
            'cancellations_by_reason': all_reasons,
            'average_time_before_checkin': round(avg_time_before_checkin, 2),
            'late_cancellation_rate': round(late_cancellation_rate, 2),
            'trend': self._calculate_cancellation_trend(analytics_records),
        }
    
    def _calculate_cancellation_trend(
        self,
        records: List[CancellationAnalytics]
    ) -> str:
        """Calculate cancellation trend direction."""
        if len(records) < 2:
            return 'stable'
        
        # Sort by period start
        sorted_records = sorted(records, key=lambda x: x.period_start)
        
        first_half = sorted_records[:len(sorted_records)//2]
        second_half = sorted_records[len(sorted_records)//2:]
        
        avg_first = sum(r.total_cancellations for r in first_half) / len(first_half)
        avg_second = sum(r.total_cancellations for r in second_half) / len(second_half)
        
        if avg_second > avg_first * 1.1:
            return 'increasing'
        elif avg_second < avg_first * 0.9:
            return 'decreasing'
        else:
            return 'stable'
    
    def _empty_cancellation_pattern(self) -> Dict[str, Any]:
        """Return empty cancellation pattern."""
        return {
            'total_cancellations': 0,
            'average_cancellation_rate': 0,
            'top_cancellation_reason': None,
            'cancellations_by_reason': {},
            'average_time_before_checkin': 0,
            'late_cancellation_rate': 0,
            'trend': 'stable',
        }
    
    # ==================== Source Performance ====================
    
    def create_source_metrics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        source: str,
        metrics_data: Dict[str, Any]
    ) -> BookingSourceMetrics:
        """Create or update booking source metrics."""
        existing = self.db.query(BookingSourceMetrics).filter(
            and_(
                BookingSourceMetrics.hostel_id == hostel_id if hostel_id else BookingSourceMetrics.hostel_id.is_(None),
                BookingSourceMetrics.period_start == period_start,
                BookingSourceMetrics.period_end == period_end,
                BookingSourceMetrics.source == source
            )
        ).first()
        
        if existing:
            for key, value in metrics_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = BookingSourceMetrics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            source=source,
            **metrics_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def get_source_performance_comparison(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[Dict[str, Any]]:
        """Compare performance across all booking sources."""
        metrics = self.db.query(BookingSourceMetrics).filter(
            and_(
                BookingSourceMetrics.hostel_id == hostel_id if hostel_id else BookingSourceMetrics.hostel_id.is_(None),
                BookingSourceMetrics.period_start == period_start,
                BookingSourceMetrics.period_end == period_end
            )
        ).all()
        
        comparison = []
        for metric in metrics:
            comparison.append({
                'source': metric.source,
                'total_bookings': metric.total_bookings,
                'confirmed_bookings': metric.confirmed_bookings,
                'conversion_rate': float(metric.conversion_rate),
                'total_revenue': float(metric.total_revenue),
                'average_booking_value': float(metric.average_booking_value),
                'roi': float(metric.roi) if metric.roi else None,
                'cost_per_booking': float(
                    metric.marketing_cost / metric.confirmed_bookings
                ) if metric.marketing_cost and metric.confirmed_bookings > 0 else None,
            })
        
        # Sort by total revenue
        comparison.sort(key=lambda x: x['total_revenue'], reverse=True)
        
        return comparison
    
    def get_best_performing_source(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        metric: str = 'conversion_rate'
    ) -> Optional[BookingSourceMetrics]:
        """Get the best performing source for a given metric."""
        query = QueryBuilder(BookingSourceMetrics, self.db)
        
        if hostel_id:
            query = query.where(BookingSourceMetrics.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                BookingSourceMetrics.period_start == period_start,
                BookingSourceMetrics.period_end == period_end
            )
        )
        
        # Order by specified metric
        if metric == 'conversion_rate':
            query = query.order_by(BookingSourceMetrics.conversion_rate.desc())
        elif metric == 'total_revenue':
            query = query.order_by(BookingSourceMetrics.total_revenue.desc())
        elif metric == 'roi':
            query = query.order_by(BookingSourceMetrics.roi.desc())
        else:
            query = query.order_by(BookingSourceMetrics.total_bookings.desc())
        
        return query.first()
    
    # ==================== Predictive Analytics ====================
    
    def forecast_booking_demand(
        self,
        hostel_id: Optional[UUID],
        forecast_days: int = 30,
        historical_days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Forecast booking demand using historical data.
        
        Args:
            hostel_id: Hostel ID
            forecast_days: Days to forecast
            historical_days: Historical data days to use
            
        Returns:
            List of forecasted data points
        """
        # Get historical trend points
        end_date = date.today()
        start_date = end_date - timedelta(days=historical_days)
        
        # Get KPIs for the period
        kpis = self.get_booking_kpis_by_date_range(
            hostel_id, start_date, end_date
        )
        
        if not kpis:
            return []
        
        # Get all trend points
        all_points = []
        for kpi in kpis:
            points = self.get_trend_points(kpi.id)
            all_points.extend(points)
        
        # Sort by date
        all_points.sort(key=lambda x: x.trend_date)
        
        if len(all_points) < 7:  # Need minimum data
            return []
        
        # Simple moving average forecast
        window_size = 7
        values = [p.total_bookings for p in all_points[-window_size:]]
        moving_avg = sum(values) / len(values)
        
        # Calculate trend
        recent_avg = sum(values[-3:]) / 3
        older_avg = sum(values[:3]) / 3
        trend = (recent_avg - older_avg) / 3  # Daily trend
        
        # Generate forecast
        forecast = []
        current_date = end_date + timedelta(days=1)
        
        for i in range(forecast_days):
            forecasted_value = moving_avg + (trend * i)
            forecasted_value = max(0, forecasted_value)  # No negative bookings
            
            # Add some uncertainty bounds (±20%)
            lower_bound = forecasted_value * 0.8
            upper_bound = forecasted_value * 1.2
            
            forecast.append({
                'date': current_date + timedelta(days=i),
                'forecasted_bookings': round(forecasted_value),
                'lower_bound': round(lower_bound),
                'upper_bound': round(upper_bound),
                'confidence': 0.80,  # 80% confidence interval
            })
        
        return forecast
    
    # ==================== Summary and Aggregation ====================
    
    def create_booking_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> BookingAnalyticsSummary:
        """
        Create comprehensive booking analytics summary.
        
        Aggregates data from KPIs, funnel, cancellations, and sources.
        """
        # Get related analytics
        kpi = self.get_booking_kpi(hostel_id, period_start, period_end)
        
        funnel = self.db.query(BookingFunnelAnalytics).filter(
            and_(
                BookingFunnelAnalytics.hostel_id == hostel_id if hostel_id else BookingFunnelAnalytics.hostel_id.is_(None),
                BookingFunnelAnalytics.period_start == period_start,
                BookingFunnelAnalytics.period_end == period_end
            )
        ).first()
        
        cancellation = self.db.query(CancellationAnalytics).filter(
            and_(
                CancellationAnalytics.hostel_id == hostel_id if hostel_id else CancellationAnalytics.hostel_id.is_(None),
                CancellationAnalytics.period_start == period_start,
                CancellationAnalytics.period_end == period_end
            )
        ).first()
        
        sources = self.db.query(BookingSourceMetrics).filter(
            and_(
                BookingSourceMetrics.hostel_id == hostel_id if hostel_id else BookingSourceMetrics.hostel_id.is_(None),
                BookingSourceMetrics.period_start == period_start,
                BookingSourceMetrics.period_end == period_end
            )
        ).all()
        
        # Calculate aggregates
        total_revenue = sum(float(s.total_revenue) for s in sources)
        
        bookings_by_source = {
            s.source: s.total_bookings for s in sources
        }
        
        revenue_by_source = {
            s.source: float(s.total_revenue) for s in sources
        }
        
        # Find best performers
        best_conversion = max(
            sources,
            key=lambda s: s.conversion_rate
        ) if sources else None
        
        best_revenue = max(
            sources,
            key=lambda s: s.total_revenue
        ) if sources else None
        
        # Create or update summary
        existing = self.db.query(BookingAnalyticsSummary).filter(
            and_(
                BookingAnalyticsSummary.hostel_id == hostel_id if hostel_id else BookingAnalyticsSummary.hostel_id.is_(None),
                BookingAnalyticsSummary.period_start == period_start,
                BookingAnalyticsSummary.period_end == period_end
            )
        ).first()
        
        summary_data = {
            'kpi_id': kpi.id if kpi else None,
            'funnel_id': funnel.id if funnel else None,
            'cancellation_id': cancellation.id if cancellation else None,
            'total_bookings': kpi.total_bookings if kpi else 0,
            'total_revenue': total_revenue,
            'overall_conversion_rate': float(kpi.booking_conversion_rate) if kpi else 0,
            'bookings_by_source': bookings_by_source,
            'revenue_by_source': revenue_by_source,
            'best_performing_source': best_conversion.source if best_conversion else None,
            'highest_revenue_source': best_revenue.source if best_revenue else None,
            'trend_summary': self._generate_trend_summary(kpi) if kpi else {},
            'is_cached': True,
            'cache_expires_at': datetime.utcnow() + timedelta(hours=1),
            'calculated_at': datetime.utcnow(),
        }
        
        if existing:
            for key, value in summary_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        summary = BookingAnalyticsSummary(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **summary_data
        )
        
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        
        return summary
    
    def _generate_trend_summary(self, kpi: BookingKPI) -> Dict[str, Any]:
        """Generate trend summary for KPI."""
        trend_analysis = self.calculate_trend_direction(kpi.id, 'total_bookings')
        
        return {
            'booking_trend': trend_analysis['direction'],
            'booking_change_percentage': trend_analysis['percentage'],
            'trend_confidence': trend_analysis['confidence'],
        }
    
    # ==================== Performance Optimization ====================
    
    def get_conversion_optimization_insights(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Generate actionable insights for conversion optimization."""
        funnel = self.db.query(BookingFunnelAnalytics).filter(
            and_(
                BookingFunnelAnalytics.hostel_id == hostel_id if hostel_id else BookingFunnelAnalytics.hostel_id.is_(None),
                BookingFunnelAnalytics.period_start == period_start,
                BookingFunnelAnalytics.period_end == period_end
            )
        ).first()
        
        if not funnel:
            return {'insights': [], 'recommendations': []}
        
        insights = []
        recommendations = []
        
        # Analyze view to form start
        if float(funnel.view_to_start_rate) < 10:  # Low threshold
            insights.append({
                'metric': 'view_to_start_rate',
                'value': float(funnel.view_to_start_rate),
                'status': 'needs_improvement',
                'priority': 'high',
            })
            recommendations.append(
                'Improve call-to-action visibility and value proposition on hostel pages'
            )
        
        # Analyze form completion
        if float(funnel.start_to_submit_rate) < 50:
            insights.append({
                'metric': 'start_to_submit_rate',
                'value': float(funnel.start_to_submit_rate),
                'status': 'needs_improvement',
                'priority': 'high',
            })
            recommendations.append(
                'Simplify booking form and reduce friction in form completion'
            )
        
        # Analyze confirmation rate
        if float(funnel.submit_to_confirm_rate) < 70:
            insights.append({
                'metric': 'submit_to_confirm_rate',
                'value': float(funnel.submit_to_confirm_rate),
                'status': 'needs_improvement',
                'priority': 'medium',
            })
            recommendations.append(
                'Streamline confirmation process and improve payment success rates'
            )
        
        # Overall conversion
        if float(funnel.view_to_confirm_rate) < 5:
            insights.append({
                'metric': 'overall_conversion',
                'value': float(funnel.view_to_confirm_rate),
                'status': 'critical',
                'priority': 'critical',
            })
            recommendations.append(
                'Comprehensive funnel optimization required - consider A/B testing'
            )
        
        return {
            'insights': insights,
            'recommendations': recommendations,
            'bottleneck': self.identify_funnel_bottleneck(funnel),
        }