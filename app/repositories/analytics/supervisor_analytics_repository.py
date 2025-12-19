"""
Supervisor Analytics Repository for performance tracking.

Provides comprehensive supervisor analytics with:
- Individual supervisor KPIs
- Workload distribution analysis
- Performance rating tracking
- Team analytics aggregation
- Comparative benchmarking
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, desc
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.models.analytics.supervisor_analytics import (
    SupervisorWorkload,
    SupervisorPerformanceRating,
    SupervisorKPI,
    SupervisorTrendPoint,
    SupervisorComparison,
    TeamAnalytics,
)


class SupervisorAnalyticsRepository(BaseRepository):
    """Repository for supervisor analytics operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    # ==================== Supervisor KPI ====================
    
    def create_supervisor_kpi(
        self,
        supervisor_id: UUID,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        kpi_data: Dict[str, Any]
    ) -> SupervisorKPI:
        """Create or update supervisor KPI."""
        # Calculate derived metrics
        complaint_resolution_rate = self._calculate_resolution_rate(
            kpi_data.get('complaints_resolved', 0),
            kpi_data.get('complaints_assigned', 0)
        )
        kpi_data['complaint_resolution_rate'] = complaint_resolution_rate
        
        maintenance_completion_rate = self._calculate_resolution_rate(
            kpi_data.get('maintenance_requests_completed', 0),
            kpi_data.get('maintenance_requests_created', 0)
        )
        kpi_data['maintenance_completion_rate'] = maintenance_completion_rate
        
        reopen_rate = self._calculate_reopen_rate(
            kpi_data.get('reopened_complaints', 0),
            kpi_data.get('complaints_resolved', 0)
        )
        kpi_data['reopen_rate'] = reopen_rate
        
        # Determine performance status
        performance_status = self._determine_performance_status(
            kpi_data.get('overall_performance_score', 0)
        )
        kpi_data['performance_status'] = performance_status
        
        existing = self.db.query(SupervisorKPI).filter(
            and_(
                SupervisorKPI.supervisor_id == supervisor_id,
                SupervisorKPI.hostel_id == hostel_id if hostel_id else SupervisorKPI.hostel_id.is_(None),
                SupervisorKPI.period_start == period_start,
                SupervisorKPI.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in kpi_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        kpi = SupervisorKPI(
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **kpi_data
        )
        
        self.db.add(kpi)
        self.db.commit()
        self.db.refresh(kpi)
        
        return kpi
    
    def get_supervisor_kpi(
        self,
        supervisor_id: UUID,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[SupervisorKPI]:
        """Get supervisor KPI for period."""
        return self.db.query(SupervisorKPI).filter(
            and_(
                SupervisorKPI.supervisor_id == supervisor_id,
                SupervisorKPI.hostel_id == hostel_id if hostel_id else SupervisorKPI.hostel_id.is_(None),
                SupervisorKPI.period_start == period_start,
                SupervisorKPI.period_end == period_end
            )
        ).first()
    
    def get_all_supervisor_kpis(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[SupervisorKPI]:
        """Get all supervisor KPIs for a period."""
        query = QueryBuilder(SupervisorKPI, self.db)
        
        if hostel_id:
            query = query.where(SupervisorKPI.hostel_id == hostel_id)
        
        query = query.where(
            and_(
                SupervisorKPI.period_start == period_start,
                SupervisorKPI.period_end == period_end
            )
        )
        
        return query.all()
    
    def _calculate_resolution_rate(
        self,
        resolved: int,
        total: int
    ) -> Decimal:
        """Calculate resolution/completion rate."""
        if total == 0:
            return Decimal('0.00')
        
        rate = (resolved / total) * 100
        return Decimal(str(round(rate, 2)))
    
    def _calculate_reopen_rate(
        self,
        reopened: int,
        resolved: int
    ) -> Decimal:
        """Calculate complaint reopen rate."""
        if resolved == 0:
            return Decimal('0.00')
        
        rate = (reopened / resolved) * 100
        return Decimal(str(round(rate, 2)))
    
    def _determine_performance_status(
        self,
        performance_score: Decimal
    ) -> str:
        """Determine performance status category."""
        score = float(performance_score)
        
        if score >= 90:
            return 'excellent'
        elif score >= 80:
            return 'good'
        elif score >= 70:
            return 'satisfactory'
        elif score >= 60:
            return 'needs_improvement'
        else:
            return 'unsatisfactory'
    
    # ==================== Workload Management ====================
    
    def create_supervisor_workload(
        self,
        supervisor_kpi_id: UUID,
        workload_data: Dict[str, Any]
    ) -> SupervisorWorkload:
        """Create or update supervisor workload."""
        # Calculate available capacity
        max_capacity = workload_data.get('max_capacity', 0)
        pending_tasks = workload_data.get('pending_tasks', 0)
        
        available_capacity = max(0, max_capacity - pending_tasks)
        workload_data['available_capacity'] = available_capacity
        
        # Determine workload status
        current_utilization = float(workload_data.get('current_utilization', 0))
        
        if current_utilization >= 95:
            workload_status = 'overloaded'
        elif current_utilization >= 80:
            workload_status = 'high'
        elif current_utilization >= 50:
            workload_status = 'moderate'
        else:
            workload_status = 'low'
        
        workload_data['workload_status'] = workload_status
        
        existing = self.db.query(SupervisorWorkload).filter(
            SupervisorWorkload.supervisor_kpi_id == supervisor_kpi_id
        ).first()
        
        if existing:
            for key, value in workload_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        workload = SupervisorWorkload(
            supervisor_kpi_id=supervisor_kpi_id,
            **workload_data
        )
        
        self.db.add(workload)
        self.db.commit()
        self.db.refresh(workload)
        
        return workload
    
    # ==================== Performance Rating ====================
    
    def create_performance_rating(
        self,
        supervisor_kpi_id: UUID,
        rating_data: Dict[str, Any]
    ) -> SupervisorPerformanceRating:
        """Create or update performance rating."""
        # Calculate overall rating (weighted average)
        overall_rating = self._calculate_overall_rating(rating_data)
        rating_data['overall_rating'] = overall_rating
        
        # Assign performance grade
        performance_grade = self._assign_performance_grade(overall_rating)
        rating_data['performance_grade'] = performance_grade
        
        # Identify strengths and improvement areas
        strengths, improvements = self._analyze_performance_dimensions(rating_data)
        rating_data['strengths'] = strengths
        rating_data['improvement_areas'] = improvements
        
        existing = self.db.query(SupervisorPerformanceRating).filter(
            SupervisorPerformanceRating.supervisor_kpi_id == supervisor_kpi_id
        ).first()
        
        if existing:
            for key, value in rating_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        rating = SupervisorPerformanceRating(
            supervisor_kpi_id=supervisor_kpi_id,
            **rating_data
        )
        
        self.db.add(rating)
        self.db.commit()
        self.db.refresh(rating)
        
        return rating
    
    def _calculate_overall_rating(
        self,
        rating_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate overall performance rating (0-100).
        
        Weighted average:
        - Efficiency: 25%
        - Quality: 25%
        - Responsiveness: 20%
        - Student satisfaction: 20%
        - Reliability: 10%
        """
        weights = {
            'efficiency_score': 0.25,
            'quality_score': 0.25,
            'responsiveness_score': 0.20,
            'student_satisfaction_score': 0.20,
            'reliability_score': 0.10,
        }
        
        weighted_sum = sum(
            float(rating_data.get(key, 0)) * weight
            for key, weight in weights.items()
        )
        
        return Decimal(str(round(weighted_sum, 2)))
    
    def _assign_performance_grade(
        self,
        overall_rating: Decimal
    ) -> str:
        """Assign letter grade based on overall rating."""
        rating = float(overall_rating)
        
        if rating >= 95:
            return 'A+'
        elif rating >= 90:
            return 'A'
        elif rating >= 85:
            return 'A-'
        elif rating >= 80:
            return 'B+'
        elif rating >= 75:
            return 'B'
        elif rating >= 70:
            return 'B-'
        elif rating >= 65:
            return 'C+'
        elif rating >= 60:
            return 'C'
        else:
            return 'D'
    
    def _analyze_performance_dimensions(
        self,
        rating_data: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """Identify performance strengths and areas for improvement."""
        dimensions = {
            'Efficiency': float(rating_data.get('efficiency_score', 0)),
            'Quality': float(rating_data.get('quality_score', 0)),
            'Responsiveness': float(rating_data.get('responsiveness_score', 0)),
            'Student Satisfaction': float(rating_data.get('student_satisfaction_score', 0)),
            'Reliability': float(rating_data.get('reliability_score', 0)),
        }
        
        # Strengths: scores >= 80
        strengths = [
            dim for dim, score in dimensions.items()
            if score >= 80
        ]
        
        # Improvement areas: scores < 70
        improvements = [
            dim for dim, score in dimensions.items()
            if score < 70
        ]
        
        return strengths, improvements
    
    # ==================== Trend Tracking ====================
    
    def add_supervisor_trend_points(
        self,
        supervisor_kpi_id: UUID,
        trend_points: List[Dict[str, Any]]
    ) -> List[SupervisorTrendPoint]:
        """Add supervisor performance trend points."""
        created_points = []
        
        for point_data in trend_points:
            # Calculate total tasks
            total_tasks = (
                point_data.get('complaints_resolved', 0) +
                point_data.get('maintenance_completed', 0)
            )
            point_data['total_tasks_completed'] = total_tasks
            
            existing = self.db.query(SupervisorTrendPoint).filter(
                and_(
                    SupervisorTrendPoint.supervisor_kpi_id == supervisor_kpi_id,
                    SupervisorTrendPoint.period_start == point_data['period_start'],
                    SupervisorTrendPoint.period_end == point_data['period_end']
                )
            ).first()
            
            if existing:
                for key, value in point_data.items():
                    setattr(existing, key, value)
                created_points.append(existing)
            else:
                point = SupervisorTrendPoint(
                    supervisor_kpi_id=supervisor_kpi_id,
                    **point_data
                )
                self.db.add(point)
                created_points.append(point)
        
        self.db.commit()
        for point in created_points:
            self.db.refresh(point)
        
        return created_points
    
    def get_supervisor_trend_points(
        self,
        supervisor_kpi_id: UUID
    ) -> List[SupervisorTrendPoint]:
        """Get all trend points for a supervisor KPI."""
        return self.db.query(SupervisorTrendPoint).filter(
            SupervisorTrendPoint.supervisor_kpi_id == supervisor_kpi_id
        ).order_by(SupervisorTrendPoint.period_start.asc()).all()
    
    # ==================== Comparative Analysis ====================
    
    def create_supervisor_comparison(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        scope_type: str = 'hostel'
    ) -> SupervisorComparison:
        """Create supervisor performance comparison."""
        # Get all supervisor KPIs for the period
        kpis = self.get_all_supervisor_kpis(hostel_id, period_start, period_end)
        
        if not kpis:
            return None
        
        # Sort by various metrics
        ranked_by_performance = sorted(
            kpis,
            key=lambda k: k.overall_performance_score,
            reverse=True
        )
        
        ranked_by_resolution_speed = sorted(
            kpis,
            key=lambda k: k.avg_complaint_resolution_time_hours
        )
        
        ranked_by_feedback = sorted(
            kpis,
            key=lambda k: k.student_feedback_score or 0,
            reverse=True
        )
        
        ranked_by_sla = sorted(
            kpis,
            key=lambda k: k.complaint_sla_compliance_rate,
            reverse=True
        )
        
        # Create rankings (just IDs)
        rankings = {
            'ranked_by_performance': [str(k.supervisor_id) for k in ranked_by_performance],
            'ranked_by_resolution_speed': [str(k.supervisor_id) for k in ranked_by_resolution_speed],
            'ranked_by_feedback_score': [str(k.supervisor_id) for k in ranked_by_feedback],
            'ranked_by_sla_compliance': [str(k.supervisor_id) for k in ranked_by_sla],
        }
        
        # Calculate statistics
        avg_performance = sum(
            float(k.overall_performance_score) for k in kpis
        ) / len(kpis)
        
        avg_resolution_time = sum(
            float(k.avg_complaint_resolution_time_hours) for k in kpis
        ) / len(kpis)
        
        avg_sla = sum(
            float(k.complaint_sla_compliance_rate) for k in kpis
        ) / len(kpis)
        
        # Top performer
        top_performer = ranked_by_performance[0].supervisor_id
        
        # Performance variance
        performance_scores = [float(k.overall_performance_score) for k in kpis]
        if len(performance_scores) > 1:
            mean = sum(performance_scores) / len(performance_scores)
            variance = sum((x - mean) ** 2 for x in performance_scores) / len(performance_scores)
        else:
            variance = 0.0
        
        existing = self.db.query(SupervisorComparison).filter(
            and_(
                SupervisorComparison.hostel_id == hostel_id if hostel_id else SupervisorComparison.hostel_id.is_(None),
                SupervisorComparison.period_start == period_start,
                SupervisorComparison.period_end == period_end,
                SupervisorComparison.scope_type == scope_type
            )
        ).first()
        
        comparison_data = {
            **rankings,
            'avg_performance_score': Decimal(str(round(avg_performance, 2))),
            'avg_resolution_time_hours': Decimal(str(round(avg_resolution_time, 2))),
            'avg_sla_compliance': Decimal(str(round(avg_sla, 2))),
            'top_performer': top_performer,
            'performance_variance': Decimal(str(round(variance, 4))),
            'calculated_at': datetime.utcnow(),
        }
        
        if existing:
            for key, value in comparison_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        comparison = SupervisorComparison(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            scope_type=scope_type,
            **comparison_data
        )
        
        self.db.add(comparison)
        self.db.commit()
        self.db.refresh(comparison)
        
        return comparison
    
    # ==================== Team Analytics ====================
    
    def create_team_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> TeamAnalytics:
        """Create team-level supervisor analytics."""
        # Get all supervisor KPIs
        kpis = self.get_all_supervisor_kpis(hostel_id, period_start, period_end)
        
        if not kpis:
            return None
        
        # Calculate aggregates
        total_supervisors = len(kpis)
        active_supervisors = len([k for k in kpis if k.complaints_assigned > 0])
        
        total_tasks_assigned = sum(
            k.complaints_assigned + k.maintenance_requests_created
            for k in kpis
        )
        
        total_tasks_completed = sum(
            k.complaints_resolved + k.maintenance_requests_completed
            for k in kpis
        )
        
        team_completion_rate = (
            Decimal(str((total_tasks_completed / total_tasks_assigned) * 100))
            if total_tasks_assigned > 0 else Decimal('0.00')
        )
        
        avg_performance = sum(
            float(k.overall_performance_score) for k in kpis
        ) / len(kpis)
        
        avg_sla = sum(
            float(k.complaint_sla_compliance_rate) for k in kpis
        ) / len(kpis)
        
        # Calculate workload balance
        workload_balance = self._calculate_workload_balance(kpis)
        
        # Identify top performers
        top_performers = sorted(
            kpis,
            key=lambda k: k.overall_performance_score,
            reverse=True
        )[:5]
        
        top_performer_ids = [str(k.supervisor_id) for k in top_performers]
        
        # Determine team efficiency
        if avg_performance >= 85:
            team_efficiency = 'high'
        elif avg_performance >= 70:
            team_efficiency = 'moderate'
        else:
            team_efficiency = 'low'
        
        existing = self.db.query(TeamAnalytics).filter(
            and_(
                TeamAnalytics.hostel_id == hostel_id if hostel_id else TeamAnalytics.hostel_id.is_(None),
                TeamAnalytics.period_start == period_start,
                TeamAnalytics.period_end == period_end
            )
        ).first()
        
        team_data = {
            'total_supervisors': total_supervisors,
            'active_supervisors': active_supervisors,
            'total_tasks_assigned': total_tasks_assigned,
            'total_tasks_completed': total_tasks_completed,
            'team_completion_rate': team_completion_rate,
            'avg_team_performance_score': Decimal(str(round(avg_performance, 2))),
            'avg_team_sla_compliance': Decimal(str(round(avg_sla, 2))),
            'workload_balance_score': workload_balance,
            'top_performers': top_performer_ids,
            'team_efficiency': team_efficiency,
            'calculated_at': datetime.utcnow(),
        }
        
        if existing:
            for key, value in team_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        analytics = TeamAnalytics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **team_data
        )
        
        self.db.add(analytics)
        self.db.commit()
        self.db.refresh(analytics)
        
        return analytics
    
    def _calculate_workload_balance(
        self,
        kpis: List[SupervisorKPI]
    ) -> Decimal:
        """
        Calculate workload balance score (0-100).
        
        100 = perfectly balanced workload
        Lower score = more imbalance
        """
        if not kpis:
            return Decimal('0.00')
        
        # Get task counts
        task_counts = [
            k.complaints_assigned + k.maintenance_requests_created
            for k in kpis
        ]
        
        if not task_counts or sum(task_counts) == 0:
            return Decimal('100.00')  # No tasks = balanced
        
        # Calculate coefficient of variation
        mean = sum(task_counts) / len(task_counts)
        
        if mean == 0:
            return Decimal('100.00')
        
        variance = sum((x - mean) ** 2 for x in task_counts) / len(task_counts)
        std_dev = variance ** 0.5
        cv = std_dev / mean
        
        # Convert to balance score (lower CV = higher balance)
        # CV of 0 = perfect balance (100), CV of 1 or more = poor balance (0)
        balance_score = max(0, min(100, (1 - cv) * 100))
        
        return Decimal(str(round(balance_score, 2)))