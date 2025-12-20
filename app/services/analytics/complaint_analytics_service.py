# --- File: C:\Hostel-Main\app\services\analytics\complaint_analytics_service.py ---
"""
Complaint Analytics Service - Service quality and SLA tracking.

Provides comprehensive complaint analytics with:
- SLA compliance monitoring
- Resolution time analysis
- Category and priority breakdown
- Performance scoring
- Trend analysis
"""

from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from uuid import UUID
import logging

from app.repositories.analytics.complaint_analytics_repository import (
    ComplaintAnalyticsRepository
)
from app.models.complaints import Complaint  # Assuming you have this model


logger = logging.getLogger(__name__)


class ComplaintAnalyticsService:
    """Service for complaint analytics operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = ComplaintAnalyticsRepository(db)
    
    # ==================== KPI Generation ====================
    
    def generate_complaint_kpis(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate comprehensive complaint KPIs for period.
        
        Returns KPI with SLA metrics and related analytics.
        """
        logger.info(f"Generating complaint KPIs for hostel {hostel_id}")
        
        # Query complaints for period
        complaints = self.db.query(Complaint).filter(
            and_(
                Complaint.created_at >= datetime.combine(period_start, datetime.min.time()),
                Complaint.created_at <= datetime.combine(period_end, datetime.max.time()),
                Complaint.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        # Calculate metrics
        total_complaints = len(complaints)
        open_complaints = len([c for c in complaints if c.status == 'open'])
        in_progress = len([c for c in complaints if c.status == 'in_progress'])
        resolved = len([c for c in complaints if c.status == 'resolved'])
        closed = len([c for c in complaints if c.status == 'closed'])
        
        # Resolution times
        resolution_times = []
        first_response_times = []
        
        for complaint in complaints:
            if complaint.resolved_at and complaint.created_at:
                hours = (complaint.resolved_at - complaint.created_at).total_seconds() / 3600
                resolution_times.append(hours)
            
            if complaint.first_response_at and complaint.created_at:
                hours = (complaint.first_response_at - complaint.created_at).total_seconds() / 3600
                first_response_times.append(hours)
        
        avg_resolution_time = (
            Decimal(str(sum(resolution_times) / len(resolution_times)))
            if resolution_times else Decimal('0.00')
        )
        
        median_resolution_time = (
            Decimal(str(sorted(resolution_times)[len(resolution_times)//2]))
            if resolution_times else None
        )
        
        avg_first_response = (
            Decimal(str(sum(first_response_times) / len(first_response_times)))
            if first_response_times else Decimal('0.00')
        )
        
        # SLA compliance
        sla_met = len([c for c in complaints if c.sla_met == True])
        total_with_sla = len([c for c in complaints if c.sla_deadline is not None])
        
        sla_compliance_rate = (
            Decimal(str((sla_met / total_with_sla) * 100))
            if total_with_sla > 0 else Decimal('0.00')
        )
        
        # Escalation and reopen rates
        escalated = len([c for c in complaints if c.escalated == True])
        reopened = len([c for c in complaints if c.reopened_count > 0])
        
        escalation_rate = (
            Decimal(str((escalated / total_complaints) * 100))
            if total_complaints > 0 else Decimal('0.00')
        )
        
        reopen_rate = (
            Decimal(str((reopened / resolved) * 100))
            if resolved > 0 else Decimal('0.00')
        )
        
        # Average satisfaction
        satisfaction_scores = [
            c.satisfaction_rating for c in complaints
            if c.satisfaction_rating is not None
        ]
        
        avg_satisfaction = (
            Decimal(str(sum(satisfaction_scores) / len(satisfaction_scores)))
            if satisfaction_scores else None
        )
        
        # Create KPI
        kpi_data = {
            'total_complaints': total_complaints,
            'open_complaints': open_complaints,
            'in_progress_complaints': in_progress,
            'resolved_complaints': resolved,
            'closed_complaints': closed,
            'average_resolution_time_hours': avg_resolution_time,
            'median_resolution_time_hours': median_resolution_time,
            'average_first_response_time_hours': avg_first_response,
            'sla_compliance_rate': sla_compliance_rate,
            'escalation_rate': escalation_rate,
            'reopen_rate': reopen_rate,
            'average_satisfaction_score': avg_satisfaction,
        }
        
        # Calculate efficiency score
        kpi = self.repo.create_complaint_kpi(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            kpi_data=kpi_data
        )
        
        # Calculate efficiency score
        efficiency_score = self.repo.calculate_efficiency_score(kpi)
        kpi.efficiency_score = efficiency_score
        self.db.commit()
        
        # Generate SLA metrics
        sla_metrics = self._generate_sla_metrics(kpi.id, complaints)
        
        # Generate trend points
        self._generate_complaint_trend_points(
            kpi.id, period_start, period_end, hostel_id
        )
        
        return {
            'kpi': kpi,
            'sla_metrics': sla_metrics,
            'efficiency_score': float(efficiency_score)
        }
    
    def _generate_sla_metrics(
        self,
        complaint_kpi_id: UUID,
        complaints: List[Any]
    ) -> Any:
        """Generate detailed SLA metrics."""
        total_with_sla = len([c for c in complaints if c.sla_deadline is not None])
        met_sla = len([c for c in complaints if c.sla_met == True])
        breached_sla = len([c for c in complaints if c.sla_met == False])
        
        sla_compliance = (
            Decimal(str((met_sla / total_with_sla) * 100))
            if total_with_sla > 0 else Decimal('0.00')
        )
        
        # Calculate average buffer/breach time
        buffer_times = []
        for complaint in complaints:
            if complaint.sla_deadline and complaint.resolved_at:
                buffer_hours = (
                    complaint.sla_deadline - complaint.resolved_at
                ).total_seconds() / 3600
                buffer_times.append(buffer_hours)
        
        avg_buffer = (
            Decimal(str(sum(buffer_times) / len(buffer_times)))
            if buffer_times else Decimal('0.00')
        )
        
        # At-risk count (open complaints close to SLA)
        at_risk = 0
        now = datetime.utcnow()
        for complaint in complaints:
            if complaint.status in ['open', 'in_progress'] and complaint.sla_deadline:
                hours_remaining = (complaint.sla_deadline - now).total_seconds() / 3600
                if 0 < hours_remaining < 24:  # Within 24 hours
                    at_risk += 1
        
        sla_data = {
            'total_with_sla': total_with_sla,
            'met_sla': met_sla,
            'breached_sla': breached_sla,
            'sla_compliance_rate': sla_compliance,
            'average_sla_buffer_hours': avg_buffer,
            'at_risk_count': at_risk,
        }
        
        sla_metrics = self.repo.create_sla_metrics(
            complaint_kpi_id=complaint_kpi_id,
            sla_data=sla_data
        )
        
        return sla_metrics
    
    def _generate_complaint_trend_points(
        self,
        kpi_id: UUID,
        period_start: date,
        period_end: date,
        hostel_id: Optional[UUID]
    ) -> None:
        """Generate daily trend points."""
        current_date = period_start
        trend_points = []
        
        while current_date <= period_end:
            daily_complaints = self.db.query(Complaint).filter(
                and_(
                    func.date(Complaint.created_at) == current_date,
                    Complaint.hostel_id == hostel_id if hostel_id else True
                )
            ).all()
            
            total = len(daily_complaints)
            open_count = len([c for c in daily_complaints if c.status == 'open'])
            resolved = len([c for c in daily_complaints if c.status == 'resolved'])
            escalated = len([c for c in daily_complaints if c.escalated == True])
            sla_breached = len([c for c in daily_complaints if c.sla_met == False])
            
            resolution_rate = (
                Decimal(str((resolved / total) * 100))
                if total > 0 else None
            )
            
            trend_points.append({
                'trend_date': current_date,
                'total_complaints': total,
                'open_complaints': open_count,
                'resolved_complaints': resolved,
                'escalated': escalated,
                'sla_breached': sla_breached,
                'resolution_rate': resolution_rate,
            })
            
            current_date += timedelta(days=1)
        
        if trend_points:
            self.repo.add_complaint_trend_points(kpi_id, trend_points)
    
    # ==================== Category Analysis ====================
    
    def generate_category_breakdowns(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[Any]:
        """Generate complaint breakdown by category."""
        logger.info(f"Generating category breakdowns for hostel {hostel_id}")
        
        complaints = self.db.query(Complaint).filter(
            and_(
                Complaint.created_at >= datetime.combine(period_start, datetime.min.time()),
                Complaint.created_at <= datetime.combine(period_end, datetime.max.time()),
                Complaint.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        total_complaints = len(complaints)
        
        # Group by category
        categories = {}
        for complaint in complaints:
            category = complaint.category or 'Uncategorized'
            if category not in categories:
                categories[category] = []
            categories[category].append(complaint)
        
        breakdowns = []
        
        for category, cat_complaints in categories.items():
            count = len(cat_complaints)
            percentage = (count / total_complaints * 100) if total_complaints > 0 else 0
            
            resolved = len([c for c in cat_complaints if c.status == 'resolved'])
            open_count = len([c for c in cat_complaints if c.status == 'open'])
            
            resolution_rate = (
                Decimal(str((resolved / count) * 100))
                if count > 0 else Decimal('0.00')
            )
            
            # Average resolution time
            resolution_times = []
            for c in cat_complaints:
                if c.resolved_at and c.created_at:
                    hours = (c.resolved_at - c.created_at).total_seconds() / 3600
                    resolution_times.append(hours)
            
            avg_resolution_time = (
                Decimal(str(sum(resolution_times) / len(resolution_times)))
                if resolution_times else Decimal('0.00')
            )
            
            breakdown_data = {
                'count': count,
                'percentage_of_total': Decimal(str(round(percentage, 2))),
                'average_resolution_time_hours': avg_resolution_time,
                'resolved_count': resolved,
                'open_count': open_count,
                'resolution_rate': resolution_rate,
            }
            
            breakdown = self.repo.create_category_breakdown(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                category=category,
                breakdown_data=breakdown_data
            )
            
            breakdowns.append(breakdown)
        
        return breakdowns
    
    # ==================== Priority Analysis ====================
    
    def generate_priority_breakdowns(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[Any]:
        """Generate complaint breakdown by priority."""
        logger.info(f"Generating priority breakdowns for hostel {hostel_id}")
        
        complaints = self.db.query(Complaint).filter(
            and_(
                Complaint.created_at >= datetime.combine(period_start, datetime.min.time()),
                Complaint.created_at <= datetime.combine(period_end, datetime.max.time()),
                Complaint.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        total_complaints = len(complaints)
        
        # Group by priority
        priorities = {}
        for complaint in complaints:
            priority = complaint.priority or 'Medium'
            if priority not in priorities:
                priorities[priority] = []
            priorities[priority].append(complaint)
        
        # Priority scores for sorting
        priority_scores = {
            'Critical': 5,
            'Urgent': 4,
            'High': 3,
            'Medium': 2,
            'Low': 1
        }
        
        breakdowns = []
        
        for priority, pri_complaints in priorities.items():
            count = len(pri_complaints)
            percentage = (count / total_complaints * 100) if total_complaints > 0 else 0
            
            # Average resolution time
            resolution_times = []
            for c in pri_complaints:
                if c.resolved_at and c.created_at:
                    hours = (c.resolved_at - c.created_at).total_seconds() / 3600
                    resolution_times.append(hours)
            
            avg_resolution_time = (
                Decimal(str(sum(resolution_times) / len(resolution_times)))
                if resolution_times else Decimal('0.00')
            )
            
            # SLA compliance
            with_sla = [c for c in pri_complaints if c.sla_deadline is not None]
            met_sla = len([c for c in with_sla if c.sla_met == True])
            
            sla_compliance = (
                Decimal(str((met_sla / len(with_sla)) * 100))
                if with_sla else Decimal('0.00')
            )
            
            breakdown_data = {
                'count': count,
                'percentage_of_total': Decimal(str(round(percentage, 2))),
                'average_resolution_time_hours': avg_resolution_time,
                'sla_compliance_rate': sla_compliance,
                'priority_score': priority_scores.get(priority, 0),
            }
            
            breakdown = self.repo.create_priority_breakdown(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                priority=priority,
                breakdown_data=breakdown_data
            )
            
            breakdowns.append(breakdown)
        
        return breakdowns
    
    # ==================== Dashboard Generation ====================
    
    def generate_complaint_dashboard(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Any:
        """Generate comprehensive complaint dashboard."""
        logger.info(f"Generating complaint dashboard for hostel {hostel_id}")
        
        # Generate all components
        kpi_result = self.generate_complaint_kpis(hostel_id, period_start, period_end)
        categories = self.generate_category_breakdowns(hostel_id, period_start, period_end)
        priorities = self.generate_priority_breakdowns(hostel_id, period_start, period_end)
        
        # Create dashboard
        dashboard = self.repo.create_complaint_dashboard(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end
        )
        
        return {
            'dashboard': dashboard,
            'kpi': kpi_result['kpi'],
            'sla_metrics': kpi_result['sla_metrics'],
            'categories': categories,
            'priorities': priorities,
        }
    
    # ==================== Trend Analysis ====================
    
    def analyze_complaint_trends(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Analyze complaint trends over period."""
        kpi = self.repo.get_complaint_kpi(hostel_id, period_start, period_end)
        
        if not kpi:
            return {
                'direction': 'unknown',
                'message': 'No data available'
            }
        
        trends = self.repo.analyze_complaint_trends(kpi.id)
        
        return trends
