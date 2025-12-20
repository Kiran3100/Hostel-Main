# --- File: C:\Hostel-Main\app\services\analytics\supervisor_analytics_service.py ---
"""
Supervisor Analytics Service - Performance tracking and team management.

Provides comprehensive supervisor analytics with:
- Individual performance KPIs
- Workload distribution analysis
- Performance rating tracking
- Team analytics aggregation
- Comparative benchmarking
"""

from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from uuid import UUID
import logging

from app.repositories.analytics.supervisor_analytics_repository import (
    SupervisorAnalyticsRepository
)
from app.models.supervisors import Supervisor  # Assuming you have this model
from app.models.complaints import Complaint
from app.models.maintenance import MaintenanceRequest


logger = logging.getLogger(__name__)


class SupervisorAnalyticsService:
    """Service for supervisor analytics operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = SupervisorAnalyticsRepository(db)
    
    # ==================== Supervisor KPI Generation ====================
    
    def generate_supervisor_kpis(
        self,
        supervisor_id: UUID,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate comprehensive KPIs for a supervisor.
        
        Tracks workload, performance, and quality metrics.
        """
        logger.info(f"Generating supervisor KPIs for {supervisor_id}")
        
        # Get supervisor details
        supervisor = self.db.query(Supervisor).filter(
            Supervisor.id == supervisor_id
        ).first()
        
        if not supervisor:
            raise ValueError(f"Supervisor {supervisor_id} not found")
        
        # Query complaints assigned to supervisor
        complaints = self.db.query(Complaint).filter(
            and_(
                Complaint.assigned_to == supervisor_id,
                Complaint.created_at >= datetime.combine(period_start, datetime.min.time()),
                Complaint.created_at <= datetime.combine(period_end, datetime.max.time())
            )
        ).all()
        
        complaints_assigned = len(complaints)
        complaints_resolved = len([c for c in complaints if c.status == 'resolved'])
        complaints_pending = len([c for c in complaints if c.status in ['open', 'in_progress']])
        
        # Query maintenance requests
        maintenance_requests = self.db.query(MaintenanceRequest).filter(
            and_(
                MaintenanceRequest.created_by == supervisor_id,
                MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
                MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time())
            )
        ).all()
        
        maintenance_created = len(maintenance_requests)
        maintenance_completed = len([m for m in maintenance_requests if m.status == 'completed'])
        maintenance_pending = len([m for m in maintenance_requests if m.status in ['pending', 'in_progress']])
        
        # Calculate resolution times
        resolution_times = []
        for complaint in complaints:
            if complaint.resolved_at and complaint.created_at:
                hours = (complaint.resolved_at - complaint.created_at).total_seconds() / 3600
                resolution_times.append(hours)
        
        avg_complaint_resolution = (
            Decimal(str(sum(resolution_times) / len(resolution_times)))
            if resolution_times else Decimal('0.00')
        )
        
        # First response times
        first_response_times = []
        for complaint in complaints:
            if complaint.first_response_at and complaint.created_at:
                hours = (complaint.first_response_at - complaint.created_at).total_seconds() / 3600
                first_response_times.append(hours)
        
        avg_first_response = (
            Decimal(str(sum(first_response_times) / len(first_response_times)))
            if first_response_times else Decimal('0.00')
        )
        
        # Maintenance completion times
        maintenance_times = []
        for maintenance in maintenance_requests:
            if maintenance.completed_at and maintenance.created_at:
                hours = (maintenance.completed_at - maintenance.created_at).total_seconds() / 3600
                maintenance_times.append(hours)
        
        avg_maintenance_time = (
            Decimal(str(sum(maintenance_times) / len(maintenance_times)))
            if maintenance_times else Decimal('0.00')
        )
        
        # SLA compliance
        complaints_with_sla = [c for c in complaints if c.sla_deadline is not None]
        met_sla = len([c for c in complaints_with_sla if c.sla_met == True])
        
        complaint_sla_compliance = (
            Decimal(str((met_sla / len(complaints_with_sla)) * 100))
            if complaints_with_sla else Decimal('0.00')
        )
        
        # Maintenance SLA (simplified)
        maintenance_sla_compliance = Decimal('85.00')  # Placeholder
        
        # Quality metrics
        reopened_complaints = len([c for c in complaints if c.reopened_count > 0])
        escalated_complaints = len([c for c in complaints if c.escalated == True])
        
        # Student feedback
        feedback_scores = [
            c.satisfaction_rating for c in complaints
            if c.satisfaction_rating is not None
        ]
        
        student_feedback_score = (
            Decimal(str(sum(feedback_scores) / len(feedback_scores)))
            if feedback_scores else None
        )
        
        feedback_count = len(feedback_scores)
        
        # Calculate overall performance score
        overall_performance_score = self._calculate_supervisor_performance_score({
            'complaint_sla_compliance': float(complaint_sla_compliance),
            'avg_resolution_time': float(avg_complaint_resolution),
            'reopen_rate': (reopened_complaints / complaints_resolved * 100) if complaints_resolved > 0 else 0,
            'student_feedback': float(student_feedback_score) if student_feedback_score else 70,
        })
        
        # Attendance tracking (would query attendance records)
        attendance_records_marked = 0  # Placeholder
        
        kpi_data = {
            'supervisor_name': supervisor.name,
            'complaints_assigned': complaints_assigned,
            'complaints_resolved': complaints_resolved,
            'complaints_pending': complaints_pending,
            'maintenance_requests_created': maintenance_created,
            'maintenance_requests_completed': maintenance_completed,
            'maintenance_pending': maintenance_pending,
            'attendance_records_marked': attendance_records_marked,
            'avg_complaint_resolution_time_hours': avg_complaint_resolution,
            'avg_first_response_time_hours': avg_first_response,
            'avg_maintenance_completion_time_hours': avg_maintenance_time,
            'complaint_sla_compliance_rate': complaint_sla_compliance,
            'maintenance_sla_compliance_rate': maintenance_sla_compliance,
            'reopened_complaints': reopened_complaints,
            'escalated_complaints': escalated_complaints,
            'student_feedback_score': student_feedback_score,
            'feedback_count': feedback_count,
            'overall_performance_score': Decimal(str(overall_performance_score)),
        }
        
        kpi = self.repo.create_supervisor_kpi(
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            kpi_data=kpi_data
        )
        
        # Generate workload metrics
        workload = self._generate_workload_metrics(kpi.id, complaints, maintenance_requests)
        
        # Generate performance rating
        rating = self._generate_performance_rating(kpi.id, kpi_data)
        
        return {
            'kpi': kpi,
            'workload': workload,
            'rating': rating,
        }
    
    def _calculate_supervisor_performance_score(
        self,
        metrics: Dict[str, float]
    ) -> float:
        """
        Calculate overall supervisor performance score (0-100).
        
        Weighted factors:
        - SLA compliance: 30%
        - Resolution time: 25%
        - Quality (reopen rate): 25%
        - Student feedback: 20%
        """
        sla_score = metrics['complaint_sla_compliance'] * 0.30
        
        # Resolution time score (inverse - faster is better)
        # Assume 24 hours is excellent, 72+ hours is poor
        avg_time = metrics['avg_resolution_time']
        if avg_time <= 24:
            time_score = 100 * 0.25
        elif avg_time >= 72:
            time_score = 0
        else:
            time_score = ((72 - avg_time) / 48 * 100) * 0.25
        
        # Quality score (inverse of reopen rate)
        quality_score = max(0, (100 - metrics['reopen_rate'])) * 0.25
        
        # Feedback score
        feedback_score = (metrics['student_feedback'] / 5 * 100) * 0.20
        
        total_score = sla_score + time_score + quality_score + feedback_score
        
        return round(total_score, 2)
    
    def _generate_workload_metrics(
        self,
        supervisor_kpi_id: UUID,
        complaints: List[Any],
        maintenance_requests: List[Any]
    ) -> Any:
        """Generate workload distribution metrics."""
        active_complaints = len([c for c in complaints if c.status in ['open', 'in_progress']])
        active_maintenance = len([m for m in maintenance_requests if m.status in ['pending', 'in_progress']])
        
        pending_tasks = active_complaints + active_maintenance
        
        # Calculate capacity (simplified)
        max_capacity = 50  # Configurable per supervisor
        
        current_utilization = (
            Decimal(str((pending_tasks / max_capacity) * 100))
            if max_capacity > 0 else Decimal('0.00')
        )
        
        # Count urgent tasks
        urgent_tasks = len([
            c for c in complaints
            if c.status in ['open', 'in_progress'] and c.priority in ['urgent', 'critical']
        ])
        
        # Count overdue tasks
        overdue_tasks = len([
            c for c in complaints
            if c.status in ['open', 'in_progress'] and c.sla_deadline and c.sla_deadline < datetime.utcnow()
        ])
        
        workload_data = {
            'active_complaints': active_complaints,
            'active_maintenance': active_maintenance,
            'pending_tasks': pending_tasks,
            'max_capacity': max_capacity,
            'current_utilization': current_utilization,
            'urgent_tasks': urgent_tasks,
            'overdue_tasks': overdue_tasks,
        }
        
        workload = self.repo.create_supervisor_workload(
            supervisor_kpi_id=supervisor_kpi_id,
            workload_data=workload_data
        )
        
        return workload
    
    def _generate_performance_rating(
        self,
        supervisor_kpi_id: UUID,
        kpi_data: Dict[str, Any]
    ) -> Any:
        """Generate multi-dimensional performance rating."""
        # Calculate individual dimension scores
        
        # Efficiency score (based on resolution time)
        avg_resolution = float(kpi_data['avg_complaint_resolution_time_hours'])
        if avg_resolution <= 24:
            efficiency_score = Decimal('95.00')
        elif avg_resolution <= 48:
            efficiency_score = Decimal('80.00')
        else:
            efficiency_score = Decimal('60.00')
        
        # Quality score (based on reopen rate)
        reopened = kpi_data['reopened_complaints']
        resolved = kpi_data['complaints_resolved']
        
        reopen_rate = (reopened / resolved * 100) if resolved > 0 else 0
        quality_score = Decimal(str(max(0, 100 - (reopen_rate * 5))))
        
        # Responsiveness score (based on first response time)
        avg_first_response = float(kpi_data['avg_first_response_time_hours'])
        if avg_first_response <= 2:
            responsiveness_score = Decimal('95.00')
        elif avg_first_response <= 4:
            responsiveness_score = Decimal('80.00')
        else:
            responsiveness_score = Decimal('60.00')
        
        # Student satisfaction score
        student_satisfaction_score = (
            kpi_data['student_feedback_score'] / 5 * 100
            if kpi_data['student_feedback_score'] else Decimal('70.00')
        )
        
        # Reliability score (based on SLA compliance)
        reliability_score = kpi_data['complaint_sla_compliance_rate']
        
        rating_data = {
            'efficiency_score': efficiency_score,
            'quality_score': quality_score,
            'responsiveness_score': responsiveness_score,
            'student_satisfaction_score': student_satisfaction_score,
            'reliability_score': reliability_score,
        }
        
        rating = self.repo.create_performance_rating(
            supervisor_kpi_id=supervisor_kpi_id,
            rating_data=rating_data
        )
        
        return rating
    
    # ==================== Team Analytics ====================
    
    def generate_team_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Any:
        """
        Generate team-level supervisor analytics.
        
        Aggregates metrics across all supervisors in a hostel.
        """
        logger.info(f"Generating team analytics for hostel {hostel_id}")
        
        analytics = self.repo.create_team_analytics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end
        )
        
        return analytics
    
    # ==================== Comparative Analysis ====================
    
    def generate_supervisor_comparison(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Any:
        """
        Generate comparative analysis of supervisors.
        
        Ranks supervisors by various performance metrics.
        """
        logger.info(f"Generating supervisor comparison for hostel {hostel_id}")
        
        comparison = self.repo.create_supervisor_comparison(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            scope_type='hostel'
        )
        
        return comparison
    
    # ==================== Performance Dashboard ====================
    
    def generate_supervisor_dashboard(
        self,
        supervisor_id: UUID,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate comprehensive supervisor dashboard.
        
        Combines KPIs, workload, ratings, and trends.
        """
        logger.info(f"Generating supervisor dashboard for {supervisor_id}")
        
        # Generate KPIs
        kpi_result = self.generate_supervisor_kpis(
            supervisor_id, hostel_id, period_start, period_end
        )
        
        # Get comparison data
        comparison = self.generate_supervisor_comparison(
            hostel_id, period_start, period_end
        )
        
        # Find supervisor's rank
        ranked_by_performance = comparison.ranked_by_performance or []
        supervisor_rank = None
        if str(supervisor_id) in ranked_by_performance:
            supervisor_rank = ranked_by_performance.index(str(supervisor_id)) + 1
        
        return {
            'kpi': kpi_result['kpi'],
            'workload': kpi_result['workload'],
            'rating': kpi_result['rating'],
            'comparison': {
                'rank': supervisor_rank,
                'total_supervisors': comparison.total_supervisors if hasattr(comparison, 'total_supervisors') else len(ranked_by_performance),
                'avg_performance_score': float(comparison.avg_performance_score),
            },
        }


