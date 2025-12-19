"""
Complaint Analytics Repository for service quality tracking.

Provides comprehensive complaint analytics with:
- SLA compliance monitoring
- Resolution time tracking
- Category and priority analysis
- Supervisor performance metrics
- Trend analysis and forecasting
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, distinct
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.models.analytics.complaint_analytics import (
    ComplaintKPI,
    SLAMetrics,
    ComplaintTrendPoint,
    CategoryBreakdown,
    PriorityBreakdown,
    ComplaintDashboard,
)


class ComplaintAnalyticsRepository(BaseRepository):
    """Repository for complaint analytics operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    # ==================== KPI Operations ====================
    
    def create_complaint_kpi(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        kpi_data: Dict[str, Any]
    ) -> ComplaintKPI:
        """
        Create or update complaint KPI record.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            period_start: Period start date
            period_end: Period end date
            kpi_data: KPI metrics data
            
        Returns:
            Created or updated ComplaintKPI instance
        """
        existing = self.db.query(ComplaintKPI).filter(
            and_(
                ComplaintKPI.hostel_id == hostel_id if hostel_id else ComplaintKPI.hostel_id.is_(None),
                ComplaintKPI.period_start == period_start,
                ComplaintKPI.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in kpi_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        kpi = ComplaintKPI(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **kpi_data
        )
        
        self.db.add(kpi)
        self.db.commit()
        self.db.refresh(kpi)
        
        return kpi
    
    def get_complaint_kpi(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[ComplaintKPI]:
        """Get complaint KPI for specific period."""
        query = QueryBuilder(ComplaintKPI, self.db)
        
        if hostel_id:
            query = query.where(ComplaintKPI.hostel_id == hostel_id)
        else:
            query = query.where(ComplaintKPI.hostel_id.is_(None))
        
        query = query.where(
            and_(
                ComplaintKPI.period_start == period_start,
                ComplaintKPI.period_end == period_end
            )
        )
        
        return query.first()
    
    def get_complaint_kpis_by_date_range(
        self,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date
    ) -> List[ComplaintKPI]:
        """Get all complaint KPIs within date range."""
        query = QueryBuilder(ComplaintKPI, self.db)
        
        if hostel_id:
            query = query.where(ComplaintKPI.hostel_id == hostel_id)
        
        query = query.where(
            or_(
                and_(
                    ComplaintKPI.period_start >= start_date,
                    ComplaintKPI.period_start <= end_date
                ),
                and_(
                    ComplaintKPI.period_end >= start_date,
                    ComplaintKPI.period_end <= end_date
                )
            )
        ).order_by(ComplaintKPI.period_start.desc())
        
        return query.all()
    
    # ==================== SLA Metrics ====================
    
    def create_sla_metrics(
        self,
        complaint_kpi_id: UUID,
        sla_data: Dict[str, Any]
    ) -> SLAMetrics:
        """Create or update SLA metrics for a complaint KPI."""
        existing = self.db.query(SLAMetrics).filter(
            SLAMetrics.complaint_kpi_id == complaint_kpi_id
        ).first()
        
        if existing:
            for key, value in sla_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = SLAMetrics(
            complaint_kpi_id=complaint_kpi_id,
            **sla_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def calculate_sla_compliance_rate(
        self,
        total_with_sla: int,
        met_sla: int
    ) -> Decimal:
        """Calculate SLA compliance rate percentage."""
        if total_with_sla == 0:
            return Decimal('0.00')
        
        rate = (met_sla / total_with_sla) * 100
        return Decimal(str(round(rate, 2)))
    
    def get_sla_breach_analysis(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Analyze SLA breaches for the period."""
        kpi = self.get_complaint_kpi(hostel_id, period_start, period_end)
        
        if not kpi or not kpi.sla_metrics:
            return self._empty_sla_analysis()
        
        sla = kpi.sla_metrics
        
        return {
            'total_with_sla': sla.total_with_sla,
            'met_sla': sla.met_sla,
            'breached_sla': sla.breached_sla,
            'compliance_rate': float(sla.sla_compliance_rate),
            'average_buffer_hours': float(sla.average_sla_buffer_hours),
            'at_risk_count': sla.at_risk_count,
            'breach_rate': (
                float(sla.breached_sla / sla.total_with_sla * 100)
                if sla.total_with_sla > 0 else 0
            ),
            'risk_percentage': (
                float(sla.at_risk_count / kpi.open_complaints * 100)
                if kpi.open_complaints > 0 else 0
            ),
        }
    
    def _empty_sla_analysis(self) -> Dict[str, Any]:
        """Return empty SLA analysis."""
        return {
            'total_with_sla': 0,
            'met_sla': 0,
            'breached_sla': 0,
            'compliance_rate': 0,
            'average_buffer_hours': 0,
            'at_risk_count': 0,
            'breach_rate': 0,
            'risk_percentage': 0,
        }
    
    def identify_sla_risk_complaints(
        self,
        hostel_id: Optional[UUID],
        hours_threshold: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Identify complaints at risk of SLA breach.
        
        Args:
            hostel_id: Hostel ID
            hours_threshold: Hours before SLA breach to flag
            
        Returns:
            List of at-risk complaint summaries
        """
        # This would query actual Complaint model (not analytics)
        # Placeholder for structure
        return []
    
    # ==================== Trend Analysis ====================
    
    def add_complaint_trend_points(
        self,
        kpi_id: UUID,
        trend_points: List[Dict[str, Any]]
    ) -> List[ComplaintTrendPoint]:
        """Add multiple complaint trend points."""
        created_points = []
        
        for point_data in trend_points:
            existing = self.db.query(ComplaintTrendPoint).filter(
                and_(
                    ComplaintTrendPoint.kpi_id == kpi_id,
                    ComplaintTrendPoint.trend_date == point_data['trend_date']
                )
            ).first()
            
            if existing:
                for key, value in point_data.items():
                    if key != 'trend_date':
                        setattr(existing, key, value)
                created_points.append(existing)
            else:
                point = ComplaintTrendPoint(
                    kpi_id=kpi_id,
                    **point_data
                )
                self.db.add(point)
                created_points.append(point)
        
        self.db.commit()
        for point in created_points:
            self.db.refresh(point)
        
        return created_points
    
    def get_complaint_trend_points(
        self,
        kpi_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[ComplaintTrendPoint]:
        """Get complaint trend points for a KPI."""
        query = QueryBuilder(ComplaintTrendPoint, self.db)
        query = query.where(ComplaintTrendPoint.kpi_id == kpi_id)
        
        if start_date:
            query = query.where(ComplaintTrendPoint.trend_date >= start_date)
        if end_date:
            query = query.where(ComplaintTrendPoint.trend_date <= end_date)
        
        query = query.order_by(ComplaintTrendPoint.trend_date.asc())
        
        return query.all()
    
    def analyze_complaint_trends(
        self,
        kpi_id: UUID
    ) -> Dict[str, Any]:
        """Analyze trends in complaint metrics."""
        points = self.get_complaint_trend_points(kpi_id)
        
        if len(points) < 2:
            return {
                'direction': 'stable',
                'volume_trend': 'stable',
                'resolution_trend': 'stable',
                'escalation_trend': 'stable',
            }
        
        # Volume trend
        first_half_volume = sum(
            p.total_complaints for p in points[:len(points)//2]
        ) / (len(points)//2)
        
        second_half_volume = sum(
            p.total_complaints for p in points[len(points)//2:]
        ) / (len(points) - len(points)//2)
        
        volume_trend = self._determine_trend_direction(
            first_half_volume, second_half_volume
        )
        
        # Resolution trend
        first_half_resolution = sum(
            p.resolved_complaints for p in points[:len(points)//2]
        ) / (len(points)//2)
        
        second_half_resolution = sum(
            p.resolved_complaints for p in points[len(points)//2:]
        ) / (len(points) - len(points)//2)
        
        resolution_trend = self._determine_trend_direction(
            first_half_resolution, second_half_resolution
        )
        
        # Escalation trend
        first_half_escalation = sum(
            p.escalated for p in points[:len(points)//2]
        ) / (len(points)//2)
        
        second_half_escalation = sum(
            p.escalated for p in points[len(points)//2:]
        ) / (len(points) - len(points)//2)
        
        escalation_trend = self._determine_trend_direction(
            first_half_escalation, second_half_escalation
        )
        
        # Overall direction
        if volume_trend == 'increasing' and resolution_trend != 'increasing':
            overall = 'worsening'
        elif volume_trend == 'decreasing' and resolution_trend == 'increasing':
            overall = 'improving'
        else:
            overall = 'stable'
        
        return {
            'direction': overall,
            'volume_trend': volume_trend,
            'resolution_trend': resolution_trend,
            'escalation_trend': escalation_trend,
            'data_points': len(points),
        }
    
    def _determine_trend_direction(
        self,
        first_value: float,
        second_value: float,
        threshold: float = 0.1
    ) -> str:
        """Determine trend direction based on values."""
        if first_value == 0:
            return 'stable'
        
        change = (second_value - first_value) / first_value
        
        if change > threshold:
            return 'increasing'
        elif change < -threshold:
            return 'decreasing'
        else:
            return 'stable'
    
    # ==================== Category Analysis ====================
    
    def create_category_breakdown(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        category: str,
        breakdown_data: Dict[str, Any]
    ) -> CategoryBreakdown:
        """Create or update category breakdown."""
        existing = self.db.query(CategoryBreakdown).filter(
            and_(
                CategoryBreakdown.hostel_id == hostel_id if hostel_id else CategoryBreakdown.hostel_id.is_(None),
                CategoryBreakdown.period_start == period_start,
                CategoryBreakdown.period_end == period_end,
                CategoryBreakdown.category == category
            )
        ).first()
        
        if existing:
            for key, value in breakdown_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        breakdown = CategoryBreakdown(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            category=category,
            **breakdown_data
        )
        
        self.db.add(breakdown)
        self.db.commit()
        self.db.refresh(breakdown)
        
        return breakdown
    
    def get_category_breakdowns(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[CategoryBreakdown]:
        """Get all category breakdowns for period."""
        query = QueryBuilder(CategoryBreakdown, self.db)
        
        if hostel_id:
            query = query.where(CategoryBreakdown.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                CategoryBreakdown.period_start == period_start,
                CategoryBreakdown.period_end == period_end
            )
        ).order_by(CategoryBreakdown.count.desc())
        
        return query.all()
    
    def get_top_complaint_categories(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top complaint categories by volume."""
        breakdowns = self.get_category_breakdowns(
            hostel_id, period_start, period_end
        )
        
        top_categories = breakdowns[:limit]
        
        return [
            {
                'category': b.category,
                'count': b.count,
                'percentage': float(b.percentage_of_total),
                'resolution_rate': float(b.resolution_rate) if b.resolution_rate else 0,
                'avg_resolution_time': float(b.average_resolution_time_hours),
            }
            for b in top_categories
        ]
    
    def identify_problem_categories(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[Dict[str, Any]]:
        """Identify categories with poor performance."""
        breakdowns = self.get_category_breakdowns(
            hostel_id, period_start, period_end
        )
        
        problem_categories = []
        
        for breakdown in breakdowns:
            issues = []
            
            # High volume
            if float(breakdown.percentage_of_total) > 20:
                issues.append('high_volume')
            
            # Low resolution rate
            if breakdown.resolution_rate and float(breakdown.resolution_rate) < 70:
                issues.append('low_resolution_rate')
            
            # High resolution time
            if float(breakdown.average_resolution_time_hours) > 48:
                issues.append('slow_resolution')
            
            # High open count
            if breakdown.open_count > breakdown.count * 0.3:
                issues.append('high_backlog')
            
            if issues:
                problem_categories.append({
                    'category': breakdown.category,
                    'issues': issues,
                    'count': breakdown.count,
                    'percentage': float(breakdown.percentage_of_total),
                    'open_count': breakdown.open_count,
                    'resolution_rate': float(breakdown.resolution_rate) if breakdown.resolution_rate else 0,
                    'avg_resolution_time': float(breakdown.average_resolution_time_hours),
                })
        
        # Sort by number of issues
        problem_categories.sort(key=lambda x: len(x['issues']), reverse=True)
        
        return problem_categories
    
    # ==================== Priority Analysis ====================
    
    def create_priority_breakdown(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        priority: str,
        breakdown_data: Dict[str, Any]
    ) -> PriorityBreakdown:
        """Create or update priority breakdown."""
        existing = self.db.query(PriorityBreakdown).filter(
            and_(
                PriorityBreakdown.hostel_id == hostel_id if hostel_id else PriorityBreakdown.hostel_id.is_(None),
                PriorityBreakdown.period_start == period_start,
                PriorityBreakdown.period_end == period_end,
                PriorityBreakdown.priority == priority
            )
        ).first()
        
        if existing:
            for key, value in breakdown_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        breakdown = PriorityBreakdown(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            priority=priority,
            **breakdown_data
        )
        
        self.db.add(breakdown)
        self.db.commit()
        self.db.refresh(breakdown)
        
        return breakdown
    
    def get_priority_breakdowns(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[PriorityBreakdown]:
        """Get all priority breakdowns for period."""
        query = QueryBuilder(PriorityBreakdown, self.db)
        
        if hostel_id:
            query = query.where(PriorityBreakdown.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                PriorityBreakdown.period_start == period_start,
                PriorityBreakdown.period_end == period_end
            )
        ).order_by(PriorityBreakdown.priority_score.desc())
        
        return query.all()
    
    def analyze_priority_distribution(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Analyze complaint distribution by priority."""
        breakdowns = self.get_priority_breakdowns(
            hostel_id, period_start, period_end
        )
        
        total = sum(b.count for b in breakdowns)
        
        distribution = {
            b.priority: {
                'count': b.count,
                'percentage': float(b.percentage_of_total),
                'avg_resolution_time': float(b.average_resolution_time_hours),
                'sla_compliance': float(b.sla_compliance_rate),
            }
            for b in breakdowns
        }
        
        # Identify concerns
        concerns = []
        
        for breakdown in breakdowns:
            # High priority with low SLA compliance
            if breakdown.priority.lower() in ['urgent', 'critical', 'high']:
                if float(breakdown.sla_compliance_rate) < 80:
                    concerns.append({
                        'priority': breakdown.priority,
                        'issue': 'low_sla_compliance',
                        'value': float(breakdown.sla_compliance_rate),
                    })
        
        return {
            'total_complaints': total,
            'distribution': distribution,
            'concerns': concerns,
        }
    
    # ==================== Dashboard Creation ====================
    
    def create_complaint_dashboard(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> ComplaintDashboard:
        """Create comprehensive complaint dashboard."""
        # Get related data
        kpi = self.get_complaint_kpi(hostel_id, period_start, period_end)
        
        categories = self.get_category_breakdowns(
            hostel_id, period_start, period_end
        )
        
        priorities = self.get_priority_breakdowns(
            hostel_id, period_start, period_end
        )
        
        # Calculate aggregates
        total_complaints = kpi.total_complaints if kpi else 0
        open_complaints = kpi.open_complaints if kpi else 0
        
        # Count urgent (high priority)
        urgent_complaints = sum(
            p.count for p in priorities
            if p.priority.lower() in ['urgent', 'critical']
        )
        
        # Most common category
        most_common_category = categories[0].category if categories else None
        
        # Slowest category
        slowest_category = max(
            categories,
            key=lambda c: c.average_resolution_time_hours
        ).category if categories else None
        
        # High priority percentage
        high_priority_count = sum(
            p.count for p in priorities
            if p.priority.lower() in ['high', 'urgent', 'critical']
        )
        high_priority_percentage = (
            Decimal(str(high_priority_count / total_complaints * 100))
            if total_complaints > 0 else Decimal('0')
        )
        
        # Build JSON breakdowns
        category_breakdown_json = [
            {
                'category': c.category,
                'count': c.count,
                'percentage': float(c.percentage_of_total),
                'resolution_rate': float(c.resolution_rate) if c.resolution_rate else 0,
            }
            for c in categories
        ]
        
        priority_breakdown_json = [
            {
                'priority': p.priority,
                'count': p.count,
                'percentage': float(p.percentage_of_total),
                'sla_compliance': float(p.sla_compliance_rate),
            }
            for p in priorities
        ]
        
        # Generate insights
        problem_categories = self.identify_problem_categories(
            hostel_id, period_start, period_end
        )
        
        priority_analysis = self.analyze_priority_distribution(
            hostel_id, period_start, period_end
        )
        
        actionable_insights = {
            'problem_categories': problem_categories,
            'priority_concerns': priority_analysis.get('concerns', []),
            'recommendations': self._generate_complaint_recommendations(
                kpi, categories, priorities
            ),
        }
        
        # Create or update dashboard
        existing = self.db.query(ComplaintDashboard).filter(
            and_(
                ComplaintDashboard.hostel_id == hostel_id if hostel_id else ComplaintDashboard.hostel_id.is_(None),
                ComplaintDashboard.period_start == period_start,
                ComplaintDashboard.period_end == period_end
            )
        ).first()
        
        dashboard_data = {
            'kpi_id': kpi.id if kpi else None,
            'total_complaints': total_complaints,
            'open_complaints': open_complaints,
            'urgent_complaints': urgent_complaints,
            'most_common_category': most_common_category,
            'slowest_category': slowest_category,
            'high_priority_percentage': high_priority_percentage,
            'category_breakdown_json': category_breakdown_json,
            'priority_breakdown_json': priority_breakdown_json,
            'actionable_insights': actionable_insights,
            'is_cached': True,
            'cache_expires_at': datetime.utcnow() + timedelta(hours=1),
            'calculated_at': datetime.utcnow(),
        }
        
        if existing:
            for key, value in dashboard_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        dashboard = ComplaintDashboard(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **dashboard_data
        )
        
        self.db.add(dashboard)
        self.db.commit()
        self.db.refresh(dashboard)
        
        return dashboard
    
    def _generate_complaint_recommendations(
        self,
        kpi: Optional[ComplaintKPI],
        categories: List[CategoryBreakdown],
        priorities: List[PriorityBreakdown]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if not kpi:
            return recommendations
        
        # SLA compliance
        if float(kpi.sla_compliance_rate) < 80:
            recommendations.append(
                'Improve SLA compliance - currently below target at '
                f'{float(kpi.sla_compliance_rate):.1f}%'
            )
        
        # Resolution time
        if float(kpi.average_resolution_time_hours) > 48:
            recommendations.append(
                'Reduce average resolution time - currently at '
                f'{float(kpi.average_resolution_time_hours):.1f} hours'
            )
        
        # Escalation rate
        if float(kpi.escalation_rate) > 15:
            recommendations.append(
                'High escalation rate detected - review first-level resolution capabilities'
            )
        
        # Reopen rate
        if float(kpi.reopen_rate) > 10:
            recommendations.append(
                'High reopen rate - improve quality of initial resolutions'
            )
        
        # Category concentration
        if categories:
            top_category = categories[0]
            if float(top_category.percentage_of_total) > 30:
                recommendations.append(
                    f'Address high volume of {top_category.category} complaints '
                    f'({float(top_category.percentage_of_total):.1f}% of total)'
                )
        
        return recommendations
    
    # ==================== Performance Metrics ====================
    
    def calculate_efficiency_score(
        self,
        kpi: ComplaintKPI
    ) -> Decimal:
        """
        Calculate overall complaint handling efficiency score (0-100).
        
        Based on:
        - Resolution rate (30%)
        - SLA compliance (30%)
        - Average resolution time (20%)
        - Escalation rate (10%)
        - Reopen rate (10%)
        """
        # Resolution rate score
        resolution_rate = (
            kpi.resolved_complaints / kpi.total_complaints * 100
        ) if kpi.total_complaints > 0 else 0
        resolution_score = min(resolution_rate, 100)
        
        # SLA compliance score
        sla_score = float(kpi.sla_compliance_rate)
        
        # Resolution time score (inverse - faster is better)
        # Assume 24 hours is excellent, 72+ hours is poor
        time_hours = float(kpi.average_resolution_time_hours)
        if time_hours <= 24:
            time_score = 100
        elif time_hours >= 72:
            time_score = 0
        else:
            time_score = 100 - ((time_hours - 24) / 48 * 100)
        
        # Escalation score (inverse - lower is better)
        escalation_rate = float(kpi.escalation_rate)
        escalation_score = max(0, 100 - (escalation_rate * 5))
        
        # Reopen score (inverse - lower is better)
        reopen_rate = float(kpi.reopen_rate)
        reopen_score = max(0, 100 - (reopen_rate * 5))
        
        # Weighted average
        efficiency = (
            resolution_score * 0.30 +
            sla_score * 0.30 +
            time_score * 0.20 +
            escalation_score * 0.10 +
            reopen_score * 0.10
        )
        
        return Decimal(str(round(efficiency, 2)))
    
    def get_performance_comparison(
        self,
        hostel_ids: List[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[UUID, Dict[str, Any]]:
        """Compare complaint performance across hostels."""
        comparison = {}
        
        for hostel_id in hostel_ids:
            kpi = self.get_complaint_kpi(hostel_id, period_start, period_end)
            
            if kpi:
                efficiency = self.calculate_efficiency_score(kpi)
                
                comparison[hostel_id] = {
                    'total_complaints': kpi.total_complaints,
                    'resolution_rate': float(
                        kpi.resolved_complaints / kpi.total_complaints * 100
                    ) if kpi.total_complaints > 0 else 0,
                    'sla_compliance': float(kpi.sla_compliance_rate),
                    'avg_resolution_time': float(kpi.average_resolution_time_hours),
                    'efficiency_score': float(efficiency),
                }
            else:
                comparison[hostel_id] = {
                    'total_complaints': 0,
                    'resolution_rate': 0,
                    'sla_compliance': 0,
                    'avg_resolution_time': 0,
                    'efficiency_score': 0,
                }
        
        # Add rankings
        sorted_by_efficiency = sorted(
            comparison.items(),
            key=lambda x: x[1]['efficiency_score'],
            reverse=True
        )
        
        for rank, (hostel_id, data) in enumerate(sorted_by_efficiency, start=1):
            comparison[hostel_id]['rank'] = rank
        
        return comparison
    
    # ==================== Predictive Analytics ====================
    
    def forecast_complaint_volume(
        self,
        hostel_id: Optional[UUID],
        forecast_days: int = 30
    ) -> List[Dict[str, Any]]:
        """Forecast complaint volume using historical trends."""
        # Get historical data (last 90 days)
        end_date = date.today()
        start_date = end_date - timedelta(days=90)
        
        kpis = self.get_complaint_kpis_by_date_range(
            hostel_id, start_date, end_date
        )
        
        if not kpis:
            return []
        
        # Get all trend points
        all_points = []
        for kpi in kpis:
            points = self.get_complaint_trend_points(kpi.id)
            all_points.extend(points)
        
        # Sort by date
        all_points.sort(key=lambda x: x.trend_date)
        
        if len(all_points) < 7:
            return []
        
        # Calculate moving average
        window_size = 7
        recent_values = [p.total_complaints for p in all_points[-window_size:]]
        moving_avg = sum(recent_values) / len(recent_values)
        
        # Calculate trend
        recent_avg = sum(recent_values[-3:]) / 3
        older_avg = sum(recent_values[:3]) / 3
        daily_trend = (recent_avg - older_avg) / 3
        
        # Generate forecast
        forecast = []
        current_date = end_date + timedelta(days=1)
        
        for i in range(forecast_days):
            forecasted_value = moving_avg + (daily_trend * i)
            forecasted_value = max(0, forecasted_value)
            
            # Confidence bounds
            lower_bound = forecasted_value * 0.7
            upper_bound = forecasted_value * 1.3
            
            forecast.append({
                'date': current_date + timedelta(days=i),
                'forecasted_complaints': round(forecasted_value),
                'lower_bound': round(lower_bound),
                'upper_bound': round(upper_bound),
                'confidence': 0.75,
            })
        
        return forecast