"""
Inquiry Aggregate Repository for complex analytics and reporting.

This repository provides advanced analytics, aggregations, and insights
across inquiries and follow-ups for strategic decision-making.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import and_, or_, func, case, extract
from sqlalchemy.orm import Session

from app.models.inquiry.inquiry import Inquiry
from app.models.inquiry.inquiry_follow_up import InquiryFollowUp, ContactMethod, ContactOutcome
from app.models.hostel.hostel import Hostel
from app.models.user.user import User
from app.schemas.common.enums import InquirySource, InquiryStatus, RoomType
from app.repositories.base.base_repository import BaseRepository


class InquiryAggregateRepository:
    """
    Aggregate repository for complex inquiry analytics and reporting.
    
    Provides cross-entity analytics, trend analysis, and business intelligence
    for inquiry management optimization.
    """
    
    def __init__(self, session: Session):
        """Initialize aggregate repository."""
        self.session = session
    
    # ============================================================================
    # COMPREHENSIVE ANALYTICS
    # ============================================================================
    
    async def get_comprehensive_dashboard(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive inquiry dashboard data.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            Complete dashboard data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Overview metrics
        overview = await self._get_overview_metrics(hostel_id, cutoff_date)
        
        # Conversion funnel
        funnel = await self._get_conversion_funnel(hostel_id, cutoff_date)
        
        # Source performance
        source_performance = await self._get_source_performance(hostel_id, cutoff_date)
        
        # Follow-up metrics
        follow_up_metrics = await self._get_follow_up_metrics(hostel_id, cutoff_date)
        
        # Team performance
        team_performance = await self._get_team_performance(hostel_id, cutoff_date)
        
        # Trends
        trends = await self._get_trend_data(hostel_id, days)
        
        # Quality metrics
        quality_metrics = await self._get_quality_metrics(hostel_id, cutoff_date)
        
        return {
            "period_days": days,
            "overview": overview,
            "conversion_funnel": funnel,
            "source_performance": source_performance,
            "follow_up_metrics": follow_up_metrics,
            "team_performance": team_performance,
            "trends": trends,
            "quality_metrics": quality_metrics,
            "generated_at": datetime.utcnow()
        }
    
    async def get_lead_quality_analysis(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze lead quality and scoring effectiveness.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            Lead quality analysis
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Priority score distribution
        score_distribution = await self._get_priority_score_distribution(hostel_id, cutoff_date)
        
        # Conversion by priority
        conversion_by_priority = await self._get_conversion_by_priority(hostel_id, cutoff_date)
        
        # Completeness analysis
        completeness_analysis = await self._get_completeness_analysis(hostel_id, cutoff_date)
        
        # Source quality
        source_quality = await self._get_source_quality_metrics(hostel_id, cutoff_date)
        
        return {
            "score_distribution": score_distribution,
            "conversion_by_priority": conversion_by_priority,
            "completeness_analysis": completeness_analysis,
            "source_quality": source_quality,
            "period_days": days
        }
    
    async def get_conversion_optimization_insights(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get insights for conversion optimization.
        
        Args:
            hostel_id: Hostel ID
            days: Time period in days
            
        Returns:
            Conversion optimization insights
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Bottleneck analysis
        bottlenecks = await self._identify_conversion_bottlenecks(hostel_id, cutoff_date)
        
        # Time-to-conversion analysis
        time_to_conversion = await self._analyze_time_to_conversion(hostel_id, cutoff_date)
        
        # Drop-off analysis
        drop_offs = await self._analyze_drop_off_points(hostel_id, cutoff_date)
        
        # Best practices
        best_practices = await self._identify_best_practices(hostel_id, cutoff_date)
        
        return {
            "bottlenecks": bottlenecks,
            "time_to_conversion": time_to_conversion,
            "drop_off_analysis": drop_offs,
            "best_practices": best_practices,
            "period_days": days
        }
    
    async def get_forecasting_data(
        self,
        hostel_id: UUID,
        historical_days: int = 90
    ) -> Dict[str, Any]:
        """
        Get data for inquiry and conversion forecasting.
        
        Args:
            hostel_id: Hostel ID
            historical_days: Historical data period
            
        Returns:
            Forecasting data and predictions
        """
        cutoff_date = datetime.utcnow() - timedelta(days=historical_days)
        
        # Historical trends
        historical_data = await self._get_historical_trends(hostel_id, cutoff_date)
        
        # Seasonal patterns
        seasonal_patterns = await self._analyze_seasonal_patterns(hostel_id, cutoff_date)
        
        # Growth metrics
        growth_metrics = await self._calculate_growth_metrics(hostel_id, cutoff_date)
        
        # Predictive indicators
        indicators = await self._get_predictive_indicators(hostel_id, cutoff_date)
        
        return {
            "historical_data": historical_data,
            "seasonal_patterns": seasonal_patterns,
            "growth_metrics": growth_metrics,
            "predictive_indicators": indicators,
            "period_days": historical_days
        }
    
    async def get_comparative_analysis(
        self,
        hostel_ids: List[UUID],
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Compare inquiry performance across multiple hostels.
        
        Args:
            hostel_ids: List of hostel IDs
            days: Time period in days
            
        Returns:
            Comparative analysis data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        comparative_data = []
        
        for hostel_id in hostel_ids:
            hostel_data = await self._get_hostel_comparison_metrics(hostel_id, cutoff_date)
            comparative_data.append(hostel_data)
        
        # Rankings
        rankings = self._calculate_rankings(comparative_data)
        
        # Benchmarks
        benchmarks = self._calculate_benchmarks(comparative_data)
        
        return {
            "hostel_metrics": comparative_data,
            "rankings": rankings,
            "benchmarks": benchmarks,
            "period_days": days
        }
    
    # ============================================================================
    # HELPER METHODS FOR ANALYTICS
    # ============================================================================
    
    async def _get_overview_metrics(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Get overview metrics."""
        query = (
            self.session.query(
                func.count(Inquiry.id).label('total'),
                func.sum(case((Inquiry.status == InquiryStatus.NEW, 1), else_=0)).label('new'),
                func.sum(case((Inquiry.status == InquiryStatus.ASSIGNED, 1), else_=0)).label('assigned'),
                func.sum(case((Inquiry.status == InquiryStatus.CONTACTED, 1), else_=0)).label('contacted'),
                func.sum(case((Inquiry.status == InquiryStatus.INTERESTED, 1), else_=0)).label('interested'),
                func.sum(case((Inquiry.converted_to_booking == True, 1), else_=0)).label('converted'),
                func.sum(case((Inquiry.is_urgent == True, 1), else_=0)).label('urgent'),
                func.avg(Inquiry.priority_score).label('avg_priority'),
                func.avg(Inquiry.response_time_minutes).label('avg_response_time')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
        )
        
        result = self.session.execute(query).first()
        
        conversion_rate = (result.converted / result.total * 100) if result.total > 0 else 0
        
        return {
            "total_inquiries": result.total,
            "new_inquiries": result.new,
            "assigned_inquiries": result.assigned,
            "contacted_inquiries": result.contacted,
            "interested_inquiries": result.interested,
            "converted_inquiries": result.converted,
            "urgent_inquiries": result.urgent,
            "conversion_rate": round(conversion_rate, 2),
            "avg_priority_score": round(result.avg_priority or 0, 2),
            "avg_response_time_minutes": round(result.avg_response_time or 0, 2)
        }
    
    async def _get_conversion_funnel(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Get conversion funnel data."""
        query = (
            self.session.query(
                func.count(Inquiry.id).label('total'),
                func.sum(case((Inquiry.assigned_to.isnot(None), 1), else_=0)).label('assigned'),
                func.sum(case((Inquiry.contacted_at.isnot(None), 1), else_=0)).label('contacted'),
                func.sum(case((Inquiry.status == InquiryStatus.INTERESTED, 1), else_=0)).label('interested'),
                func.sum(case((Inquiry.converted_to_booking == True, 1), else_=0)).label('converted')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
        )
        
        result = self.session.execute(query).first()
        total = result.total or 1
        
        return {
            "total_inquiries": result.total,
            "assigned": {
                "count": result.assigned,
                "rate": round((result.assigned / total) * 100, 2)
            },
            "contacted": {
                "count": result.contacted,
                "rate": round((result.contacted / total) * 100, 2)
            },
            "interested": {
                "count": result.interested,
                "rate": round((result.interested / total) * 100, 2)
            },
            "converted": {
                "count": result.converted,
                "rate": round((result.converted / total) * 100, 2)
            }
        }
    
    async def _get_source_performance(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get source performance metrics."""
        query = (
            self.session.query(
                Inquiry.inquiry_source,
                func.count(Inquiry.id).label('total'),
                func.sum(case((Inquiry.converted_to_booking == True, 1), else_=0)).label('converted'),
                func.avg(Inquiry.priority_score).label('avg_priority'),
                func.avg(Inquiry.response_time_minutes).label('avg_response_time')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
            .group_by(Inquiry.inquiry_source)
        )
        
        results = self.session.execute(query).all()
        
        performance_data = []
        for row in results:
            conversion_rate = (row.converted / row.total * 100) if row.total > 0 else 0
            
            performance_data.append({
                "source": row.inquiry_source.value,
                "total": row.total,
                "converted": row.converted,
                "conversion_rate": round(conversion_rate, 2),
                "avg_priority": round(row.avg_priority or 0, 2),
                "avg_response_time": round(row.avg_response_time or 0, 2)
            })
        
        return sorted(performance_data, key=lambda x: x['conversion_rate'], reverse=True)
    
    async def _get_follow_up_metrics(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Get follow-up metrics."""
        query = (
            self.session.query(
                func.count(InquiryFollowUp.id).label('total'),
                func.sum(case((InquiryFollowUp.is_successful == True, 1), else_=0)).label('successful'),
                func.avg(InquiryFollowUp.response_time_hours).label('avg_response_time')
            )
            .join(Inquiry, InquiryFollowUp.inquiry_id == Inquiry.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(InquiryFollowUp.attempted_at >= cutoff_date)
        )
        
        result = self.session.execute(query).first()
        
        success_rate = (result.successful / result.total * 100) if result.total > 0 else 0
        
        return {
            "total_follow_ups": result.total,
            "successful_follow_ups": result.successful,
            "success_rate": round(success_rate, 2),
            "avg_response_time_hours": round(result.avg_response_time or 0, 2)
        }
    
    async def _get_team_performance(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get team performance metrics."""
        query = (
            self.session.query(
                Inquiry.assigned_to,
                User.full_name,
                func.count(Inquiry.id).label('total'),
                func.sum(case((Inquiry.converted_to_booking == True, 1), else_=0)).label('converted'),
                func.avg(Inquiry.response_time_minutes).label('avg_response_time')
            )
            .join(User, Inquiry.assigned_to == User.id)
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.assigned_at >= cutoff_date)
            .filter(Inquiry.assigned_to.isnot(None))
            .filter(Inquiry.is_deleted == False)
            .group_by(Inquiry.assigned_to, User.full_name)
        )
        
        results = self.session.execute(query).all()
        
        team_data = []
        for row in results:
            conversion_rate = (row.converted / row.total * 100) if row.total > 0 else 0
            
            team_data.append({
                "user_id": str(row.assigned_to),
                "user_name": row.full_name,
                "total_assigned": row.total,
                "converted": row.converted,
                "conversion_rate": round(conversion_rate, 2),
                "avg_response_time": round(row.avg_response_time or 0, 2)
            })
        
        return sorted(team_data, key=lambda x: x['conversion_rate'], reverse=True)
    
    async def _get_trend_data(
        self,
        hostel_id: UUID,
        days: int
    ) -> Dict[str, Any]:
        """Get trend data."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Daily trends
        daily_query = (
            self.session.query(
                func.date(Inquiry.created_at).label('date'),
                func.count(Inquiry.id).label('count'),
                func.sum(case((Inquiry.converted_to_booking == True, 1), else_=0)).label('converted')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
            .group_by(func.date(Inquiry.created_at))
            .order_by(func.date(Inquiry.created_at))
        )
        
        daily_results = self.session.execute(daily_query).all()
        
        daily_trends = [
            {
                "date": row.date.isoformat(),
                "inquiries": row.count,
                "conversions": row.converted
            }
            for row in daily_results
        ]
        
        return {
            "daily_trends": daily_trends
        }
    
    async def _get_quality_metrics(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Get quality metrics."""
        query = (
            self.session.query(
                func.avg(Inquiry.inquiry_quality_score).label('avg_quality'),
                func.sum(case((Inquiry.preferred_check_in_date.isnot(None), 1), else_=0)).label('with_date'),
                func.sum(case((Inquiry.stay_duration_months.isnot(None), 1), else_=0)).label('with_duration'),
                func.sum(case((Inquiry.room_type_preference.isnot(None), 1), else_=0)).label('with_room_type'),
                func.count(Inquiry.id).label('total')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
        )
        
        result = self.session.execute(query).first()
        total = result.total or 1
        
        return {
            "avg_quality_score": round(result.avg_quality or 0, 2),
            "completeness": {
                "with_check_in_date": round((result.with_date / total) * 100, 2),
                "with_duration": round((result.with_duration / total) * 100, 2),
                "with_room_preference": round((result.with_room_type / total) * 100, 2)
            }
        }
    
    async def _get_priority_score_distribution(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, int]:
        """Get priority score distribution."""
        query = (
            self.session.query(
                case(
                    (Inquiry.priority_score >= 80, 'high'),
                    (Inquiry.priority_score >= 50, 'medium'),
                    else_='low'
                ).label('priority_level'),
                func.count(Inquiry.id).label('count')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
            .group_by('priority_level')
        )
        
        results = self.session.execute(query).all()
        
        return {row.priority_level: row.count for row in results}
    
    async def _get_conversion_by_priority(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get conversion rates by priority level."""
        query = (
            self.session.query(
                case(
                    (Inquiry.priority_score >= 80, 'high'),
                    (Inquiry.priority_score >= 50, 'medium'),
                    else_='low'
                ).label('priority_level'),
                func.count(Inquiry.id).label('total'),
                func.sum(case((Inquiry.converted_to_booking == True, 1), else_=0)).label('converted')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
            .group_by('priority_level')
        )
        
        results = self.session.execute(query).all()
        
        conversion_data = []
        for row in results:
            conversion_rate = (row.converted / row.total * 100) if row.total > 0 else 0
            conversion_data.append({
                "priority_level": row.priority_level,
                "total": row.total,
                "converted": row.converted,
                "conversion_rate": round(conversion_rate, 2)
            })
        
        return conversion_data
    
    async def _get_completeness_analysis(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Analyze inquiry completeness impact."""
        query = (
            self.session.query(
                case(
                    (
                        and_(
                            Inquiry.preferred_check_in_date.isnot(None),
                            Inquiry.stay_duration_months.isnot(None),
                            Inquiry.room_type_preference.isnot(None)
                        ),
                        'complete'
                    ),
                    else_='incomplete'
                ).label('completeness'),
                func.count(Inquiry.id).label('total'),
                func.sum(case((Inquiry.converted_to_booking == True, 1), else_=0)).label('converted')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
            .group_by('completeness')
        )
        
        results = self.session.execute(query).all()
        
        analysis = {}
        for row in results:
            conversion_rate = (row.converted / row.total * 100) if row.total > 0 else 0
            analysis[row.completeness] = {
                "total": row.total,
                "converted": row.converted,
                "conversion_rate": round(conversion_rate, 2)
            }
        
        return analysis
    
    async def _get_source_quality_metrics(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get quality metrics by source."""
        query = (
            self.session.query(
                Inquiry.inquiry_source,
                func.avg(Inquiry.inquiry_quality_score).label('avg_quality'),
                func.avg(Inquiry.priority_score).label('avg_priority'),
                func.count(Inquiry.id).label('total')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
            .group_by(Inquiry.inquiry_source)
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "source": row.inquiry_source.value,
                "avg_quality_score": round(row.avg_quality or 0, 2),
                "avg_priority_score": round(row.avg_priority or 0, 2),
                "total_inquiries": row.total
            }
            for row in results
        ]
    
    async def _identify_conversion_bottlenecks(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """Identify conversion bottlenecks."""
        # Status transition analysis
        query = (
            self.session.query(
                Inquiry.status,
                func.count(Inquiry.id).label('stuck_count'),
                func.avg(
                    extract('epoch', func.now() - Inquiry.updated_at) / 86400
                ).label('avg_days_stuck')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.converted_to_booking == False)
            .filter(Inquiry.status.notin_([InquiryStatus.CONVERTED, InquiryStatus.NOT_INTERESTED]))
            .filter(Inquiry.is_deleted == False)
            .group_by(Inquiry.status)
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "status": row.status.value,
                "stuck_count": row.stuck_count,
                "avg_days_stuck": round(row.avg_days_stuck or 0, 2)
            }
            for row in results
        ]
    
    async def _analyze_time_to_conversion(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Analyze time to conversion."""
        query = (
            self.session.query(
                func.avg(
                    extract('epoch', Inquiry.converted_at - Inquiry.created_at) / 86400
                ).label('avg_days'),
                func.min(
                    extract('epoch', Inquiry.converted_at - Inquiry.created_at) / 86400
                ).label('min_days'),
                func.max(
                    extract('epoch', Inquiry.converted_at - Inquiry.created_at) / 86400
                ).label('max_days')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.converted_to_booking == True)
            .filter(Inquiry.converted_at.isnot(None))
        )
        
        result = self.session.execute(query).first()
        
        return {
            "avg_days_to_conversion": round(result.avg_days or 0, 2),
            "fastest_conversion_days": round(result.min_days or 0, 2),
            "slowest_conversion_days": round(result.max_days or 0, 2)
        }
    
    async def _analyze_drop_off_points(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, int]:
        """Analyze where inquiries drop off."""
        query = (
            self.session.query(
                Inquiry.status,
                func.count(Inquiry.id).label('count')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.status == InquiryStatus.NOT_INTERESTED)
            .filter(Inquiry.is_deleted == False)
            .group_by(Inquiry.status)
        )
        
        results = self.session.execute(query).all()
        
        return {row.status.value: row.count for row in results}
    
    async def _identify_best_practices(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Identify best practices from high-converting inquiries."""
        # Analyze characteristics of converted inquiries
        query = (
            self.session.query(
                func.avg(Inquiry.response_time_minutes).label('avg_response_time'),
                func.avg(Inquiry.follow_up_count).label('avg_follow_ups'),
                func.mode().within_group(Inquiry.inquiry_source).label('best_source')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.converted_to_booking == True)
        )
        
        result = self.session.execute(query).first()
        
        return {
            "optimal_response_time_minutes": round(result.avg_response_time or 0, 2),
            "optimal_follow_up_count": round(result.avg_follow_ups or 0, 2),
            "best_performing_source": result.best_source.value if result.best_source else None
        }
    
    async def _get_historical_trends(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical trend data."""
        query = (
            self.session.query(
                extract('year', Inquiry.created_at).label('year'),
                extract('month', Inquiry.created_at).label('month'),
                func.count(Inquiry.id).label('total'),
                func.sum(case((Inquiry.converted_to_booking == True, 1), else_=0)).label('converted')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
            .group_by(
                extract('year', Inquiry.created_at),
                extract('month', Inquiry.created_at)
            )
            .order_by(
                extract('year', Inquiry.created_at),
                extract('month', Inquiry.created_at)
            )
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "year": int(row.year),
                "month": int(row.month),
                "total_inquiries": row.total,
                "conversions": row.converted,
                "conversion_rate": round((row.converted / row.total * 100) if row.total > 0 else 0, 2)
            }
            for row in results
        ]
    
    async def _analyze_seasonal_patterns(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Analyze seasonal patterns."""
        query = (
            self.session.query(
                extract('month', Inquiry.created_at).label('month'),
                func.avg(func.count(Inquiry.id)).over(
                    partition_by=extract('month', Inquiry.created_at)
                ).label('avg_inquiries')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.is_deleted == False)
            .group_by(extract('month', Inquiry.created_at))
        )
        
        results = self.session.execute(query).all()
        
        monthly_averages = {int(row.month): round(row.avg_inquiries, 2) for row in results}
        
        return {
            "monthly_averages": monthly_averages,
            "peak_month": max(monthly_averages, key=monthly_averages.get) if monthly_averages else None,
            "low_month": min(monthly_averages, key=monthly_averages.get) if monthly_averages else None
        }
    
    async def _calculate_growth_metrics(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Calculate growth metrics."""
        # Compare recent period vs previous period
        midpoint = cutoff_date + (datetime.utcnow() - cutoff_date) / 2
        
        recent_query = (
            self.session.query(func.count(Inquiry.id))
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= midpoint)
            .filter(Inquiry.is_deleted == False)
        )
        
        previous_query = (
            self.session.query(func.count(Inquiry.id))
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.created_at >= cutoff_date)
            .filter(Inquiry.created_at < midpoint)
            .filter(Inquiry.is_deleted == False)
        )
        
        recent_count = self.session.execute(recent_query).scalar()
        previous_count = self.session.execute(previous_query).scalar()
        
        growth_rate = 0
        if previous_count > 0:
            growth_rate = ((recent_count - previous_count) / previous_count) * 100
        
        return {
            "recent_period_count": recent_count,
            "previous_period_count": previous_count,
            "growth_rate": round(growth_rate, 2)
        }
    
    async def _get_predictive_indicators(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Get predictive indicators."""
        query = (
            self.session.query(
                func.count(Inquiry.id).label('pipeline_size'),
                func.avg(Inquiry.priority_score).label('avg_priority'),
                func.sum(case((Inquiry.status == InquiryStatus.INTERESTED, 1), else_=0)).label('hot_leads')
            )
            .filter(Inquiry.hostel_id == hostel_id)
            .filter(Inquiry.status.notin_([InquiryStatus.CONVERTED, InquiryStatus.NOT_INTERESTED]))
            .filter(Inquiry.is_deleted == False)
        )
        
        result = self.session.execute(query).first()
        
        return {
            "current_pipeline_size": result.pipeline_size,
            "avg_pipeline_priority": round(result.avg_priority or 0, 2),
            "hot_leads_count": result.hot_leads
        }
    
    async def _get_hostel_comparison_metrics(
        self,
        hostel_id: UUID,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Get metrics for hostel comparison."""
        overview = await self._get_overview_metrics(hostel_id, cutoff_date)
        
        hostel = self.session.query(Hostel).filter(Hostel.id == hostel_id).first()
        
        return {
            "hostel_id": str(hostel_id),
            "hostel_name": hostel.name if hostel else "Unknown",
            **overview
        }
    
    def _calculate_rankings(
        self,
        comparative_data: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Calculate rankings across hostels."""
        # Rank by conversion rate
        by_conversion = sorted(
            comparative_data,
            key=lambda x: x.get('conversion_rate', 0),
            reverse=True
        )
        
        # Rank by total inquiries
        by_volume = sorted(
            comparative_data,
            key=lambda x: x.get('total_inquiries', 0),
            reverse=True
        )
        
        # Rank by response time
        by_response = sorted(
            comparative_data,
            key=lambda x: x.get('avg_response_time_minutes', float('inf'))
        )
        
        return {
            "by_conversion_rate": [
                {"hostel_id": h["hostel_id"], "hostel_name": h["hostel_name"], "value": h.get("conversion_rate", 0)}
                for h in by_conversion
            ],
            "by_inquiry_volume": [
                {"hostel_id": h["hostel_id"], "hostel_name": h["hostel_name"], "value": h.get("total_inquiries", 0)}
                for h in by_volume
            ],
            "by_response_time": [
                {"hostel_id": h["hostel_id"], "hostel_name": h["hostel_name"], "value": h.get("avg_response_time_minutes", 0)}
                for h in by_response
            ]
        }
    
    def _calculate_benchmarks(
        self,
        comparative_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate benchmark metrics."""
        if not comparative_data:
            return {}
        
        conversion_rates = [h.get('conversion_rate', 0) for h in comparative_data]
        response_times = [h.get('avg_response_time_minutes', 0) for h in comparative_data]
        
        return {
            "avg_conversion_rate": round(sum(conversion_rates) / len(conversion_rates), 2),
            "best_conversion_rate": max(conversion_rates),
            "avg_response_time": round(sum(response_times) / len(response_times), 2),
            "best_response_time": min(response_times)
        }