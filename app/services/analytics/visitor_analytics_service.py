# --- File: C:\Hostel-Main\app\services\analytics\visitor_analytics_service.py ---
"""
Visitor Analytics Service - Funnel and behavior tracking.

Provides comprehensive visitor analytics with:
- Acquisition funnel tracking
- Traffic source performance
- Search behavior analysis
- Engagement metrics
- Conversion optimization
"""

from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.repositories.analytics.visitor_analytics_repository import (
    VisitorAnalyticsRepository
)


logger = logging.getLogger(__name__)


class VisitorAnalyticsService:
    """Service for visitor analytics operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = VisitorAnalyticsRepository(db)
    
    # ==================== Visitor Funnel ====================
    
    def generate_visitor_funnel(
        self,
        period_start: date,
        period_end: date,
        funnel_data: Dict[str, int]
    ) -> Any:
        """
        Generate visitor acquisition funnel analytics.
        
        Tracks visitor journey from initial visit to booking.
        
        Args:
            period_start: Period start date
            period_end: Period end date
            funnel_data: Dictionary with funnel stage counts
        """
        logger.info(f"Generating visitor funnel for period {period_start} to {period_end}")
        
        funnel = self.repo.create_visitor_funnel(
            period_start=period_start,
            period_end=period_end,
            funnel_data=funnel_data
        )
        
        return funnel
    
    def get_funnel_optimization_insights(
        self,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Get optimization insights for visitor funnel.
        
        Identifies bottlenecks and provides recommendations.
        """
        funnel = self.repo.get_visitor_funnel(period_start, period_end)
        
        if not funnel:
            return {
                'insights': [],
                'recommendations': []
            }
        
        insights = []
        recommendations = []
        
        # Analyze each funnel stage
        if float(funnel.visit_to_search_rate) < 30:
            insights.append({
                'stage': 'visit_to_search',
                'rate': float(funnel.visit_to_search_rate),
                'status': 'needs_improvement',
                'priority': 'high'
            })
            recommendations.append(
                'Improve homepage search prominence and value proposition'
            )
        
        if float(funnel.search_to_view_rate) < 40:
            insights.append({
                'stage': 'search_to_view',
                'rate': float(funnel.search_to_view_rate),
                'status': 'needs_improvement',
                'priority': 'high'
            })
            recommendations.append(
                'Enhance search result relevance and hostel presentation'
            )
        
        if float(funnel.view_to_registration_rate) < 15:
            insights.append({
                'stage': 'view_to_registration',
                'rate': float(funnel.view_to_registration_rate),
                'status': 'needs_improvement',
                'priority': 'medium'
            })
            recommendations.append(
                'Simplify registration process and highlight benefits'
            )
        
        if float(funnel.registration_to_booking_rate) < 50:
            insights.append({
                'stage': 'registration_to_booking',
                'rate': float(funnel.registration_to_booking_rate),
                'status': 'needs_improvement',
                'priority': 'high'
            })
            recommendations.append(
                'Streamline booking flow and reduce friction'
            )
        
        # Overall conversion
        if float(funnel.visit_to_booking_rate) < 2:
            insights.append({
                'stage': 'overall',
                'rate': float(funnel.visit_to_booking_rate),
                'status': 'critical',
                'priority': 'critical'
            })
            recommendations.append(
                'Comprehensive funnel optimization needed - consider A/B testing'
            )
        
        return {
            'insights': insights,
            'recommendations': recommendations,
            'funnel_efficiency_score': float(funnel.funnel_efficiency_score),
            'largest_drop_off': funnel.largest_drop_off_stage,
        }
    
    # ==================== Traffic Source Analysis ====================
    
    def generate_traffic_source_metrics(
        self,
        period_start: date,
        period_end: date,
        source: str,
        metrics_data: Dict[str, Any]
    ) -> Any:
        """
        Generate traffic source performance metrics.
        
        Tracks individual acquisition channel performance.
        """
        logger.info(f"Generating traffic source metrics for {source}")
        
        metrics = self.repo.create_traffic_source_metrics(
            period_start=period_start,
            period_end=period_end,
            source=source,
            metrics_data=metrics_data
        )
        
        return metrics
    
    def get_traffic_source_comparison(
        self,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Compare performance across all traffic sources.
        
        Returns ranked sources with key metrics.
        """
        sources = self.repo.get_traffic_source_metrics(period_start, period_end)
        
        if not sources:
            return {
                'sources': [],
                'best_converting': None,
                'highest_volume': None,
                'best_roi': None,
            }
        
        # Sort by different metrics
        by_conversion = sorted(
            sources,
            key=lambda s: s.visit_to_booking_rate,
            reverse=True
        )
        
        by_volume = sorted(
            sources,
            key=lambda s: s.visits,
            reverse=True
        )
        
        by_roi = sorted(
            [s for s in sources if s.roi is not None],
            key=lambda s: s.roi,
            reverse=True
        )
        
        return {
            'sources': [
                {
                    'source': s.source,
                    'visits': s.visits,
                    'bookings': s.confirmed_bookings,
                    'conversion_rate': float(s.visit_to_booking_rate),
                    'revenue': float(s.total_revenue),
                    'roi': float(s.roi) if s.roi else None,
                    'engagement_score': float(s.engagement_score) if s.engagement_score else None,
                }
                for s in sources
            ],
            'best_converting': by_conversion[0].source if by_conversion else None,
            'highest_volume': by_volume[0].source if by_volume else None,
            'best_roi': by_roi[0].source if by_roi else None,
        }
    
    # ==================== Search Behavior ====================
    
    def generate_search_behavior(
        self,
        period_start: date,
        period_end: date,
        behavior_data: Dict[str, Any]
    ) -> Any:
        """
        Generate search behavior analytics.
        
        Analyzes how visitors search and what they're looking for.
        """
        logger.info(f"Generating search behavior analytics")
        
        behavior = self.repo.create_search_behavior(
            period_start=period_start,
            period_end=period_end,
            behavior_data=behavior_data
        )
        
        return behavior
    
    # ==================== Engagement Metrics ====================
    
    def generate_engagement_metrics(
        self,
        period_start: date,
        period_end: date,
        engagement_data: Dict[str, Any]
    ) -> Any:
        """
        Generate visitor engagement metrics.
        
        Measures interaction depth and quality.
        """
        logger.info(f"Generating engagement metrics")
        
        metrics = self.repo.create_engagement_metrics(
            period_start=period_start,
            period_end=period_end,
            engagement_data=engagement_data
        )
        
        return metrics
    
    # ==================== Comprehensive Analytics ====================
    
    def generate_visitor_behavior_analytics(
        self,
        period_start: date,
        period_end: date,
        behavior_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive visitor behavior analytics.
        
        Combines search, engagement, and exit behavior.
        """
        logger.info(f"Generating visitor behavior analytics")
        
        # Generate search behavior if data provided
        search_behavior = None
        if 'search_data' in behavior_data:
            search_behavior = self.generate_search_behavior(
                period_start, period_end, behavior_data['search_data']
            )
        
        # Generate engagement metrics if data provided
        engagement_metrics = None
        if 'engagement_data' in behavior_data:
            engagement_metrics = self.generate_engagement_metrics(
                period_start, period_end, behavior_data['engagement_data']
            )
        
        # Create comprehensive analytics
        analytics = self.repo.create_visitor_behavior_analytics(
            period_start=period_start,
            period_end=period_end,
            search_behavior_id=search_behavior.id if search_behavior else None,
            engagement_metrics_id=engagement_metrics.id if engagement_metrics else None,
            behavior_data=behavior_data
        )
        
        return {
            'analytics': analytics,
            'search_behavior': search_behavior,
            'engagement_metrics': engagement_metrics,
        }
    
    # ==================== Traffic Source Analytics ====================
    
    def generate_traffic_source_analytics(
        self,
        period_start: date,
        period_end: date
    ) -> Any:
        """
        Generate comprehensive traffic source analytics.
        
        Aggregates and compares all acquisition channels.
        """
        logger.info(f"Generating traffic source analytics")
        
        analytics = self.repo.create_traffic_source_analytics(
            period_start=period_start,
            period_end=period_end
        )
        
        return analytics


