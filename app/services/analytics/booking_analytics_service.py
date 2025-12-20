# --- File: C:\Hostel-Main\app\services\analytics\booking_analytics_service.py ---
"""
Booking Analytics Service - Booking performance and conversion tracking.

Provides comprehensive booking analytics with:
- KPI calculation and tracking
- Conversion funnel analysis
- Cancellation pattern detection
- Source performance evaluation
- Demand forecasting
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from uuid import UUID
import logging

from app.repositories.analytics.booking_analytics_repository import (
    BookingAnalyticsRepository
)
from app.models.booking import Booking  # Assuming you have this model
from app.models.analytics.booking_analytics import (
    BookingKPI,
    BookingFunnelAnalytics,
    CancellationAnalytics,
    BookingSourceMetrics,
)


logger = logging.getLogger(__name__)


class BookingAnalyticsService:
    """Service for booking analytics operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = BookingAnalyticsRepository(db)
    
    # ==================== KPI Generation ====================
    
    def generate_booking_kpis(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> BookingKPI:
        """
        Generate comprehensive booking KPIs for period.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            period_start: Period start date
            period_end: Period end date
            
        Returns:
            BookingKPI instance with calculated metrics
        """
        logger.info(
            f"Generating booking KPIs for hostel {hostel_id}, "
            f"period {period_start} to {period_end}"
        )
        
        # Query bookings for the period
        query = self.db.query(Booking).filter(
            and_(
                Booking.created_at >= datetime.combine(period_start, datetime.min.time()),
                Booking.created_at <= datetime.combine(period_end, datetime.max.time())
            )
        )
        
        if hostel_id:
            query = query.filter(Booking.hostel_id == hostel_id)
        
        bookings = query.all()
        
        # Calculate metrics
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.status == 'confirmed'])
        cancelled_bookings = len([b for b in bookings if b.status == 'cancelled'])
        rejected_bookings = len([b for b in bookings if b.status == 'rejected'])
        pending_bookings = len([b for b in bookings if b.status == 'pending'])
        
        # Conversion rate
        booking_conversion_rate = (
            Decimal(str((confirmed_bookings / total_bookings) * 100))
            if total_bookings > 0 else Decimal('0.00')
        )
        
        # Cancellation rate
        cancellation_rate = (
            Decimal(str((cancelled_bookings / total_bookings) * 100))
            if total_bookings > 0 else Decimal('0.00')
        )
        
        # Average lead time
        lead_times = []
        for booking in bookings:
            if booking.check_in_date and booking.created_at:
                lead_time = (booking.check_in_date - booking.created_at.date()).days
                lead_times.append(lead_time)
        
        average_lead_time = (
            Decimal(str(sum(lead_times) / len(lead_times)))
            if lead_times else Decimal('0.00')
        )
        
        # Approval rate
        approved_or_rejected = confirmed_bookings + rejected_bookings
        approval_rate = (
            Decimal(str((confirmed_bookings / approved_or_rejected) * 100))
            if approved_or_rejected > 0 else Decimal('0.00')
        )
        
        # Create KPI
        kpi_data = {
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'rejected_bookings': rejected_bookings,
            'pending_bookings': pending_bookings,
            'booking_conversion_rate': booking_conversion_rate,
            'cancellation_rate': cancellation_rate,
            'average_lead_time_days': average_lead_time,
            'approval_rate': approval_rate,
        }
        
        kpi = self.repo.create_booking_kpi(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            kpi_data=kpi_data
        )
        
        # Generate trend points
        self._generate_booking_trend_points(kpi.id, period_start, period_end, hostel_id)
        
        logger.info(f"Generated booking KPI: {kpi.id}")
        
        return kpi
    
    def _generate_booking_trend_points(
        self,
        kpi_id: UUID,
        period_start: date,
        period_end: date,
        hostel_id: Optional[UUID]
    ) -> None:
        """Generate daily trend points for the period."""
        current_date = period_start
        trend_points = []
        
        while current_date <= period_end:
            # Query bookings for this specific date
            daily_bookings = self.db.query(Booking).filter(
                and_(
                    func.date(Booking.created_at) == current_date,
                    Booking.hostel_id == hostel_id if hostel_id else True
                )
            ).all()
            
            total = len(daily_bookings)
            confirmed = len([b for b in daily_bookings if b.status == 'confirmed'])
            cancelled = len([b for b in daily_bookings if b.status == 'cancelled'])
            rejected = len([b for b in daily_bookings if b.status == 'rejected'])
            pending = len([b for b in daily_bookings if b.status == 'pending'])
            
            # Calculate daily revenue
            revenue = sum(
                float(b.total_amount) for b in daily_bookings
                if b.status == 'confirmed' and b.total_amount
            )
            
            conversion_rate = (
                Decimal(str((confirmed / total) * 100))
                if total > 0 else None
            )
            
            trend_points.append({
                'trend_date': current_date,
                'total_bookings': total,
                'confirmed': confirmed,
                'cancelled': cancelled,
                'rejected': rejected,
                'pending': pending,
                'revenue_for_day': Decimal(str(revenue)),
                'conversion_rate': conversion_rate,
            })
            
            current_date += timedelta(days=1)
        
        if trend_points:
            self.repo.add_trend_points(kpi_id, trend_points)
    
    # ==================== Funnel Analysis ====================
    
    def generate_booking_funnel(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        funnel_data: Dict[str, int]
    ) -> BookingFunnelAnalytics:
        """
        Generate booking conversion funnel analytics.
        
        Args:
            hostel_id: Hostel ID
            period_start: Period start
            period_end: Period end
            funnel_data: Dictionary with funnel stage counts
                {
                    'hostel_page_views': int,
                    'booking_form_starts': int,
                    'booking_submissions': int,
                    'bookings_confirmed': int
                }
        
        Returns:
            BookingFunnelAnalytics instance
        """
        logger.info(f"Generating booking funnel for hostel {hostel_id}")
        
        # Calculate conversion rates
        hostel_views = funnel_data.get('hostel_page_views', 0)
        form_starts = funnel_data.get('booking_form_starts', 0)
        submissions = funnel_data.get('booking_submissions', 0)
        confirmed = funnel_data.get('bookings_confirmed', 0)
        
        view_to_start = (
            Decimal(str((form_starts / hostel_views) * 100))
            if hostel_views > 0 else Decimal('0.00')
        )
        
        start_to_submit = (
            Decimal(str((submissions / form_starts) * 100))
            if form_starts > 0 else Decimal('0.00')
        )
        
        submit_to_confirm = (
            Decimal(str((confirmed / submissions) * 100))
            if submissions > 0 else Decimal('0.00')
        )
        
        view_to_confirm = (
            Decimal(str((confirmed / hostel_views) * 100))
            if hostel_views > 0 else Decimal('0.00')
        )
        
        funnel_data.update({
            'view_to_start_rate': view_to_start,
            'start_to_submit_rate': start_to_submit,
            'submit_to_confirm_rate': submit_to_confirm,
            'view_to_confirm_rate': view_to_confirm,
        })
        
        funnel = self.repo.create_funnel_analytics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            funnel_data=funnel_data
        )
        
        # Identify bottleneck
        bottleneck = self.repo.identify_funnel_bottleneck(funnel)
        logger.info(f"Funnel bottleneck identified: {bottleneck['stage']}")
        
        return funnel
    
    # ==================== Cancellation Analysis ====================
    
    def generate_cancellation_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> CancellationAnalytics:
        """
        Generate cancellation analytics for period.
        
        Analyzes cancellation patterns, timing, and reasons.
        """
        logger.info(f"Generating cancellation analytics for hostel {hostel_id}")
        
        # Query cancelled bookings
        cancelled_bookings = self.db.query(Booking).filter(
            and_(
                Booking.status == 'cancelled',
                Booking.created_at >= datetime.combine(period_start, datetime.min.time()),
                Booking.created_at <= datetime.combine(period_end, datetime.max.time()),
                Booking.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        total_bookings = self.db.query(Booking).filter(
            and_(
                Booking.created_at >= datetime.combine(period_start, datetime.min.time()),
                Booking.created_at <= datetime.combine(period_end, datetime.max.time()),
                Booking.hostel_id == hostel_id if hostel_id else True
            )
        ).count()
        
        total_cancellations = len(cancelled_bookings)
        
        cancellation_rate = (
            Decimal(str((total_cancellations / total_bookings) * 100))
            if total_bookings > 0 else Decimal('0.00')
        )
        
        # Timing analysis
        time_before_checkin = []
        within_24h = 0
        within_week = 0
        
        for booking in cancelled_bookings:
            if booking.check_in_date and booking.cancelled_at:
                days_before = (booking.check_in_date - booking.cancelled_at.date()).days
                time_before_checkin.append(days_before)
                
                if days_before <= 1:
                    within_24h += 1
                if days_before <= 7:
                    within_week += 1
        
        avg_time_before_checkin = (
            Decimal(str(sum(time_before_checkin) / len(time_before_checkin)))
            if time_before_checkin else Decimal('0.00')
        )
        
        early_cancellation_rate = (
            Decimal(str(((total_cancellations - within_week) / total_cancellations) * 100))
            if total_cancellations > 0 else Decimal('0.00')
        )
        
        # Reason breakdown
        cancellations_by_reason = {}
        for booking in cancelled_bookings:
            reason = booking.cancellation_reason or 'Not specified'
            cancellations_by_reason[reason] = cancellations_by_reason.get(reason, 0) + 1
        
        top_reason = (
            max(cancellations_by_reason.items(), key=lambda x: x[1])[0]
            if cancellations_by_reason else None
        )
        
        analytics_data = {
            'total_cancellations': total_cancellations,
            'cancellation_rate': cancellation_rate,
            'average_time_before_checkin_days': avg_time_before_checkin,
            'cancellations_within_24h': within_24h,
            'cancellations_within_week': within_week,
            'early_cancellation_rate': early_cancellation_rate,
            'cancellations_by_reason': cancellations_by_reason,
            'top_cancellation_reason': top_reason,
        }
        
        analytics = self.repo.create_cancellation_analytics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            cancellation_data=analytics_data
        )
        
        return analytics
    
    # ==================== Source Performance ====================
    
    def generate_source_metrics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[BookingSourceMetrics]:
        """
        Generate booking source performance metrics.
        
        Analyzes performance across different acquisition channels.
        """
        logger.info(f"Generating source metrics for hostel {hostel_id}")
        
        # Query bookings grouped by source
        bookings = self.db.query(Booking).filter(
            and_(
                Booking.created_at >= datetime.combine(period_start, datetime.min.time()),
                Booking.created_at <= datetime.combine(period_end, datetime.max.time()),
                Booking.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        # Group by source
        sources = {}
        for booking in bookings:
            source = booking.source or 'direct'
            if source not in sources:
                sources[source] = []
            sources[source].append(booking)
        
        source_metrics_list = []
        
        for source, source_bookings in sources.items():
            total = len(source_bookings)
            confirmed = len([b for b in source_bookings if b.status == 'confirmed'])
            
            conversion_rate = (
                Decimal(str((confirmed / total) * 100))
                if total > 0 else Decimal('0.00')
            )
            
            # Revenue metrics
            total_revenue = sum(
                float(b.total_amount) for b in source_bookings
                if b.status == 'confirmed' and b.total_amount
            )
            
            avg_booking_value = (
                Decimal(str(total_revenue / confirmed))
                if confirmed > 0 else Decimal('0.00')
            )
            
            metrics_data = {
                'total_bookings': total,
                'confirmed_bookings': confirmed,
                'conversion_rate': conversion_rate,
                'total_revenue': Decimal(str(total_revenue)),
                'average_booking_value': avg_booking_value,
                'revenue_per_confirmed_booking': avg_booking_value,
            }
            
            metrics = self.repo.create_source_metrics(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                source=source,
                metrics_data=metrics_data
            )
            
            source_metrics_list.append(metrics)
        
        return source_metrics_list
    
    # ==================== Summary Generation ====================
    
    def generate_booking_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate comprehensive booking analytics summary.
        
        Combines all booking analytics into a single summary.
        """
        logger.info(f"Generating booking summary for hostel {hostel_id}")
        
        # Generate all components
        kpi = self.generate_booking_kpis(hostel_id, period_start, period_end)
        cancellation = self.generate_cancellation_analytics(hostel_id, period_start, period_end)
        sources = self.generate_source_metrics(hostel_id, period_start, period_end)
        
        # Create summary
        summary = self.repo.create_booking_summary(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end
        )
        
        return {
            'summary': summary,
            'kpi': kpi,
            'cancellation': cancellation,
            'sources': sources,
        }
    
    # ==================== Insights and Recommendations ====================
    
    def get_optimization_insights(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate actionable insights for booking optimization.
        
        Returns recommendations based on current performance.
        """
        insights = self.repo.get_conversion_optimization_insights(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end
        )
        
        return insights
    
    # ==================== Forecasting ====================
    
    def forecast_booking_demand(
        self,
        hostel_id: Optional[UUID],
        forecast_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Forecast booking demand for upcoming period.
        
        Uses historical data to predict future bookings.
        """
        logger.info(f"Forecasting booking demand for hostel {hostel_id}")
        
        forecast = self.repo.forecast_booking_demand(
            hostel_id=hostel_id,
            forecast_days=forecast_days,
            historical_days=90
        )
        
        return forecast


