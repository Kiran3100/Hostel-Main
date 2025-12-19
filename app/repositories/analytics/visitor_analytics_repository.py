"""
Visitor Analytics Repository for funnel and behavior tracking.

Provides comprehensive visitor analytics with:
- Acquisition funnel tracking
- Traffic source performance
- Search behavior analysis
- Engagement metrics
- Conversion path analysis
- Visitor behavior insights
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, desc
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.models.analytics.visitor_analytics import (
    VisitorFunnel,
    TrafficSourceMetrics,
    SearchBehavior,
    EngagementMetrics,
    VisitorBehaviorAnalytics,
    ConversionPathAnalysis,
    TrafficSourceAnalytics,
)


class VisitorAnalyticsRepository(BaseRepository):
    """Repository for visitor analytics operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    # ==================== Visitor Funnel ====================
    
    def create_visitor_funnel(
        self,
        period_start: date,
        period_end: date,
        funnel_data: Dict[str, Any]
    ) -> VisitorFunnel:
        """Create or update visitor acquisition funnel."""
        # Calculate conversion rates
        total_visits = funnel_data.get('total_visits', 0)
        
        if total_visits > 0:
            visit_to_search = (
                funnel_data.get('searches_performed', 0) / total_visits
            ) * 100
            
            search_to_view = (
                funnel_data.get('hostel_views', 0) / 
                max(funnel_data.get('searches_performed', 1), 1)
            ) * 100
            
            view_to_registration = (
                funnel_data.get('registrations', 0) / 
                max(funnel_data.get('hostel_views', 1), 1)
            ) * 100
            
            registration_to_booking = (
                funnel_data.get('bookings', 0) / 
                max(funnel_data.get('registrations', 1), 1)
            ) * 100
            
            booking_to_confirm = (
                funnel_data.get('confirmed_bookings', 0) / 
                max(funnel_data.get('bookings', 1), 1)
            ) * 100
            
            visit_to_booking = (
                funnel_data.get('confirmed_bookings', 0) / total_visits
            ) * 100
        else:
            visit_to_search = 0
            search_to_view = 0
            view_to_registration = 0
            registration_to_booking = 0
            booking_to_confirm = 0
            visit_to_booking = 0
        
        funnel_data.update({
            'visit_to_search_rate': Decimal(str(round(visit_to_search, 2))),
            'search_to_view_rate': Decimal(str(round(search_to_view, 2))),
            'view_to_registration_rate': Decimal(str(round(view_to_registration, 2))),
            'registration_to_booking_rate': Decimal(str(round(registration_to_booking, 2))),
            'booking_to_confirm_rate': Decimal(str(round(booking_to_confirm, 2))),
            'visit_to_booking_rate': Decimal(str(round(visit_to_booking, 2))),
        })
        
        # Calculate drop-offs
        dropped_after_search = max(
            0,
            funnel_data.get('searches_performed', 0) - 
            funnel_data.get('hostel_views', 0)
        )
        
        dropped_after_view = max(
            0,
            funnel_data.get('hostel_views', 0) - 
            funnel_data.get('registrations', 0)
        )
        
        dropped_after_booking_start = max(
            0,
            funnel_data.get('booking_starts', 0) - 
            funnel_data.get('bookings', 0)
        )
        
        funnel_data.update({
            'dropped_after_search': dropped_after_search,
            'dropped_after_hostel_view': dropped_after_view,
            'dropped_after_booking_start': dropped_after_booking_start,
        })
        
        # Calculate insights
        total_drop_offs = (
            dropped_after_search +
            dropped_after_view +
            dropped_after_booking_start
        )
        funnel_data['total_drop_offs'] = total_drop_offs
        
        # Identify largest drop-off stage
        drop_offs = {
            'search': dropped_after_search,
            'hostel_view': dropped_after_view,
            'booking_start': dropped_after_booking_start,
        }
        
        largest_drop_off_stage = max(drop_offs.items(), key=lambda x: x[1])[0]
        funnel_data['largest_drop_off_stage'] = largest_drop_off_stage
        
        # Calculate efficiency score
        efficiency = (visit_to_booking / 100) * 100  # Already percentage
        funnel_data['funnel_efficiency_score'] = Decimal(str(round(efficiency, 2)))
        
        existing = self.db.query(VisitorFunnel).filter(
            and_(
                VisitorFunnel.period_start == period_start,
                VisitorFunnel.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in funnel_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        funnel = VisitorFunnel(
            period_start=period_start,
            period_end=period_end,
            **funnel_data
        )
        
        self.db.add(funnel)
        self.db.commit()
        self.db.refresh(funnel)
        
        return funnel
    
    def get_visitor_funnel(
        self,
        period_start: date,
        period_end: date
    ) -> Optional[VisitorFunnel]:
        """Get visitor funnel for period."""
        return self.db.query(VisitorFunnel).filter(
            and_(
                VisitorFunnel.period_start == period_start,
                VisitorFunnel.period_end == period_end
            )
        ).first()
    
    # ==================== Traffic Source Metrics ====================
    
    def create_traffic_source_metrics(
        self,
        period_start: date,
        period_end: date,
        source: str,
        metrics_data: Dict[str, Any]
    ) -> TrafficSourceMetrics:
        """Create or update traffic source metrics."""
        # Calculate engagement score
        engagement_score = self._calculate_engagement_score(metrics_data)
        metrics_data['engagement_score'] = engagement_score
        
        # Calculate quality score
        quality_score = self._calculate_source_quality_score(metrics_data)
        metrics_data['quality_score'] = quality_score
        
        existing = self.db.query(TrafficSourceMetrics).filter(
            and_(
                TrafficSourceMetrics.period_start == period_start,
                TrafficSourceMetrics.period_end == period_end,
                TrafficSourceMetrics.source == source
            )
        ).first()
        
        if existing:
            for key, value in metrics_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = TrafficSourceMetrics(
            period_start=period_start,
            period_end=period_end,
            source=source,
            **metrics_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def get_traffic_source_metrics(
        self,
        period_start: date,
        period_end: date
    ) -> List[TrafficSourceMetrics]:
        """Get all traffic source metrics for period."""
        return self.db.query(TrafficSourceMetrics).filter(
            and_(
                TrafficSourceMetrics.period_start == period_start,
                TrafficSourceMetrics.period_end == period_end
            )
        ).order_by(TrafficSourceMetrics.visits.desc()).all()
    
    def _calculate_engagement_score(
        self,
        metrics_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate engagement score (0-100).
        
        Factors:
        - Session duration: 30%
        - Pages per session: 30%
        - Bounce rate (inverse): 40%
        """
        # Normalize session duration (assume 300s is excellent)
        avg_duration = float(metrics_data.get('avg_session_duration_seconds', 0))
        duration_score = min(avg_duration / 300, 1.0) * 30
        
        # Normalize pages per session (assume 5 is excellent)
        avg_pages = float(metrics_data.get('avg_pages_per_session', 0))
        pages_score = min(avg_pages / 5, 1.0) * 30
        
        # Bounce rate (inverse)
        bounce_rate = float(metrics_data.get('bounce_rate', 100))
        bounce_score = max(0, (100 - bounce_rate)) * 0.40
        
        total_score = duration_score + pages_score + bounce_score
        
        return Decimal(str(round(total_score, 2)))
    
    def _calculate_source_quality_score(
        self,
        metrics_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate source quality score (0-100).
        
        Factors:
        - Conversion rate: 40%
        - Engagement score: 30%
        - ROI: 30%
        """
        # Conversion rate (normalize to 0-1, assume 5% is excellent)
        conversion_rate = float(metrics_data.get('visit_to_booking_rate', 0))
        conversion_score = min(conversion_rate / 5, 1.0) * 40
        
        # Engagement
        engagement_score = float(metrics_data.get('engagement_score', 0)) * 0.30
        
        # ROI (normalize, assume 300% is excellent)
        roi = float(metrics_data.get('roi', 0)) if metrics_data.get('roi') else 0
        roi_score = min(max(roi, 0) / 300, 1.0) * 30
        
        total_score = conversion_score + engagement_score + roi_score
        
        return Decimal(str(round(total_score, 2)))
    
    # ==================== Search Behavior ====================
    
    def create_search_behavior(
        self,
        period_start: date,
        period_end: date,
        behavior_data: Dict[str, Any]
    ) -> SearchBehavior:
        """Create or update search behavior analytics."""
        # Calculate effectiveness score
        effectiveness = self._calculate_search_effectiveness(behavior_data)
        behavior_data['search_effectiveness_score'] = effectiveness
        
        existing = self.db.query(SearchBehavior).filter(
            and_(
                SearchBehavior.period_start == period_start,
                SearchBehavior.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in behavior_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        behavior = SearchBehavior(
            period_start=period_start,
            period_end=period_end,
            **behavior_data
        )
        
        self.db.add(behavior)
        self.db.commit()
        self.db.refresh(behavior)
        
        return behavior
    
    def _calculate_search_effectiveness(
        self,
        behavior_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate search effectiveness score (0-100).
        
        Factors:
        - Zero result rate (inverse): 50%
        - Avg results per search: 30%
        - Filter usage: 20%
        """
        # Zero result rate (inverse)
        zero_result_rate = float(behavior_data.get('zero_result_rate', 0))
        zero_result_score = max(0, 100 - zero_result_rate) * 0.50
        
        # Avg results (normalize, assume 10 is ideal)
        avg_results = float(behavior_data.get('avg_results_per_search', 0))
        results_score = min(avg_results / 10, 1.0) * 30
        
        # Filter usage (normalize, assume 2 filters is good)
        avg_filters = float(behavior_data.get('avg_filters_used', 0))
        filter_score = min(avg_filters / 2, 1.0) * 20
        
        total_score = zero_result_score + results_score + filter_score
        
        return Decimal(str(round(total_score, 2)))
    
    # ==================== Engagement Metrics ====================
    
    def create_engagement_metrics(
        self,
        period_start: date,
        period_end: date,
        engagement_data: Dict[str, Any]
    ) -> EngagementMetrics:
        """Create or update engagement metrics."""
        # Determine engagement level
        engagement_level = self._determine_engagement_level(engagement_data)
        engagement_data['engagement_level'] = engagement_level
        
        existing = self.db.query(EngagementMetrics).filter(
            and_(
                EngagementMetrics.period_start == period_start,
                EngagementMetrics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in engagement_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = EngagementMetrics(
            period_start=period_start,
            period_end=period_end,
            **engagement_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def _determine_engagement_level(
        self,
        engagement_data: Dict[str, Any]
    ) -> str:
        """Determine overall engagement level."""
        # Calculate composite engagement score
        avg_hostels_viewed = float(engagement_data.get('avg_hostels_viewed_per_session', 0))
        avg_time_on_page = float(engagement_data.get('avg_time_on_hostel_page_seconds', 0))
        comparison_usage = float(engagement_data.get('comparison_tool_usage_rate', 0))
        
        # Simple scoring
        score = 0
        
        if avg_hostels_viewed >= 3:
            score += 33
        elif avg_hostels_viewed >= 2:
            score += 20
        
        if avg_time_on_page >= 120:
            score += 33
        elif avg_time_on_page >= 60:
            score += 20
        
        if comparison_usage >= 30:
            score += 34
        elif comparison_usage >= 15:
            score += 20
        
        if score >= 70:
            return 'high'
        elif score >= 40:
            return 'moderate'
        else:
            return 'low'
    
    # ==================== Comprehensive Analytics ====================
    
    def create_visitor_behavior_analytics(
        self,
        period_start: date,
        period_end: date,
        search_behavior_id: Optional[UUID],
        engagement_metrics_id: Optional[UUID],
        behavior_data: Dict[str, Any]
    ) -> VisitorBehaviorAnalytics:
        """Create comprehensive visitor behavior analytics."""
        # Calculate visitor quality score
        quality_score = self._calculate_visitor_quality_score(behavior_data)
        behavior_data['visitor_quality_score'] = quality_score
        
        # Generate optimization recommendations
        recommendations = self._generate_visitor_optimization_recommendations(
            behavior_data
        )
        behavior_data['optimization_recommendations'] = recommendations
        
        existing = self.db.query(VisitorBehaviorAnalytics).filter(
            and_(
                VisitorBehaviorAnalytics.period_start == period_start,
                VisitorBehaviorAnalytics.period_end == period_end
            )
        ).first()
        
        analytics_data = {
            'search_behavior_id': search_behavior_id,
            'engagement_metrics_id': engagement_metrics_id,
            **behavior_data,
            'calculated_at': datetime.utcnow(),
        }
        
        if existing:
            for key, value in analytics_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        analytics = VisitorBehaviorAnalytics(
            period_start=period_start,
            period_end=period_end,
            **analytics_data
        )
        
        self.db.add(analytics)
        self.db.commit()
        self.db.refresh(analytics)
        
        return analytics
    
    def _calculate_visitor_quality_score(
        self,
        behavior_data: Dict[str, Any]
    ) -> Decimal:
        """Calculate visitor quality score (0-100)."""
        # Based on engagement and conversion potential
        avg_session_duration = float(behavior_data.get('avg_session_duration_seconds', 0))
        return_visitor_rate = float(behavior_data.get('return_visitor_rate', 0))
        bounce_rate = float(behavior_data.get('bounce_rate', 100))
        
        # Session duration (normalize to 300s)
        duration_score = min(avg_session_duration / 300, 1.0) * 40
        
        # Return visitor rate
        return_score = return_visitor_rate * 0.30
        
        # Bounce rate (inverse)
        bounce_score = max(0, 100 - bounce_rate) * 0.30
        
        total_score = duration_score + return_score + bounce_score
        
        return Decimal(str(round(total_score, 2)))
    
    def _generate_visitor_optimization_recommendations(
        self,
        behavior_data: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable optimization recommendations."""
        recommendations = []
        
        bounce_rate = float(behavior_data.get('bounce_rate', 0))
        if bounce_rate > 60:
            recommendations.append(
                'High bounce rate detected - improve landing page relevance and loading speed'
            )
        
        avg_session = float(behavior_data.get('avg_session_duration_seconds', 0))
        if avg_session < 60:
            recommendations.append(
                'Low session duration - enhance content engagement and value proposition'
            )
        
        return_rate = float(behavior_data.get('return_visitor_rate', 0))
        if return_rate < 20:
            recommendations.append(
                'Low return visitor rate - implement retargeting and email nurture campaigns'
            )
        
        return recommendations
    
    # ==================== Traffic Source Analytics ====================
    
    def create_traffic_source_analytics(
        self,
        period_start: date,
        period_end: date
    ) -> TrafficSourceAnalytics:
        """Create comprehensive traffic source analytics."""
        # Get all source metrics
        sources = self.get_traffic_source_metrics(period_start, period_end)
        
        if not sources:
            return None
        
        # Aggregate data
        total_visits = sum(s.visits for s in sources)
        
        visits_by_source = {s.source: s.visits for s in sources}
        registrations_by_source = {s.source: s.registrations for s in sources}
        bookings_by_source = {s.source: s.bookings for s in sources}
        
        conversion_rates = {
            s.source: float(s.visit_to_booking_rate)
            for s in sources
        }
        
        # Find best performers
        best_converting = max(sources, key=lambda s: s.visit_to_booking_rate)
        highest_volume = max(sources, key=lambda s: s.visits)
        
        # Best ROI (if available)
        sources_with_roi = [s for s in sources if s.roi is not None]
        best_roi = max(sources_with_roi, key=lambda s: s.roi) if sources_with_roi else None
        
        existing = self.db.query(TrafficSourceAnalytics).filter(
            and_(
                TrafficSourceAnalytics.period_start == period_start,
                TrafficSourceAnalytics.period_end == period_end
            )
        ).first()
        
        analytics_data = {
            'total_visits': total_visits,
            'visits_by_source': visits_by_source,
            'registrations_by_source': registrations_by_source,
            'bookings_by_source': bookings_by_source,
            'visit_to_booking_rate_by_source': conversion_rates,
            'best_converting_source': best_converting.source,
            'highest_volume_source': highest_volume.source,
            'best_roi_source': best_roi.source if best_roi else None,
            'calculated_at': datetime.utcnow(),
        }
        
        if existing:
            for key, value in analytics_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        analytics = TrafficSourceAnalytics(
            period_start=period_start,
            period_end=period_end,
            **analytics_data
        )
        
        self.db.add(analytics)
        self.db.commit()
        self.db.refresh(analytics)
        
        return analytics