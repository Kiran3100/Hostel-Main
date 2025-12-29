# app/repositories/supervisor/supervisor_aggregate_repository.py
"""
Supervisor Aggregate Repository - Cross-cutting queries and analytics.

Provides aggregate queries, reports, and analytics that span
multiple supervisor-related entities for comprehensive insights.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, desc, case
from sqlalchemy.orm import Session, joinedload

from app.models.supervisor.supervisor import Supervisor
from app.models.supervisor.supervisor_assignment import SupervisorAssignment
from app.models.supervisor.supervisor_activity import SupervisorActivity
from app.models.supervisor.supervisor_performance import SupervisorPerformance
from app.models.supervisor.supervisor_permissions import SupervisorPermission
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository
from app.core.logging import logger


class SupervisorAggregateRepository:
    """
    Supervisor aggregate repository for cross-cutting analytics.
    
    Provides comprehensive queries and analytics across all
    supervisor-related entities for reporting and insights.
    """
    
    def __init__(self, db: Session):
        """Initialize aggregate repository."""
        self.db = db
    
    # ==================== Comprehensive Dashboard ====================
    
    def get_supervisor_overview(
        self,
        supervisor_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive overview for supervisor.
        
        Combines data from all supervisor entities for complete view.
        """
        # Get supervisor
        supervisor = self.db.query(Supervisor).filter(
            Supervisor.id == supervisor_id
        ).options(
            joinedload(Supervisor.user),
            joinedload(Supervisor.assigned_hostel),
            joinedload(Supervisor.permissions)
        ).first()
        
        if not supervisor:
            return {}
        
        # Get current assignment
        current_assignment = self.db.query(SupervisorAssignment).filter(
            and_(
                SupervisorAssignment.supervisor_id == supervisor_id,
                SupervisorAssignment.is_active == True,
                SupervisorAssignment.is_primary == True
            )
        ).first()
        
        # Get recent activities
        recent_activities = self.db.query(SupervisorActivity).filter(
            SupervisorActivity.supervisor_id == supervisor_id
        ).order_by(
            SupervisorActivity.created_at.desc()
        ).limit(10).all()
        
        # Get latest performance
        latest_performance = self.db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == supervisor_id
        ).order_by(
            SupervisorPerformance.period_end.desc()
        ).first()
        
        return {
            'supervisor': {
                'id': supervisor.id,
                'employee_id': supervisor.employee_id,
                'name': supervisor.user.full_name,
                'email': supervisor.user.email,
                'status': supervisor.status.value,
                'is_active': supervisor.is_active,
                'join_date': supervisor.join_date,
                'tenure_months': supervisor.tenure_months,
                'employment_type': supervisor.employment_type.value,
                'designation': supervisor.designation
            },
            'hostel': {
                'id': supervisor.assigned_hostel.id,
                'name': supervisor.assigned_hostel.name
            } if supervisor.assigned_hostel else None,
            'assignment': {
                'id': current_assignment.id,
                'assigned_date': current_assignment.assigned_date,
                'is_primary': current_assignment.is_primary,
                'assignment_type': current_assignment.assignment_type
            } if current_assignment else None,
            'performance': {
                'overall_score': float(latest_performance.overall_performance_score),
                'grade': latest_performance.performance_grade,
                'period_type': latest_performance.period_type,
                'period_end': latest_performance.period_end
            } if latest_performance else None,
            'activity_summary': {
                'total_complaints_resolved': supervisor.total_complaints_resolved,
                'total_attendance_records': supervisor.total_attendance_records,
                'total_maintenance_requests': supervisor.total_maintenance_requests,
                'last_login': supervisor.last_login,
                'last_activity': supervisor.last_activity,
                'recent_activities_count': len(recent_activities)
            },
            'permissions': {
                'can_manage_complaints': supervisor.permissions.can_manage_complaints if supervisor.permissions else False,
                'can_record_attendance': supervisor.permissions.can_record_attendance if supervisor.permissions else False,
                'can_manage_maintenance': supervisor.permissions.can_manage_maintenance if supervisor.permissions else False
            }
        }
    
    # ==================== Hostel Analytics ====================
    
    def get_hostel_supervisor_analytics(
        self,
        hostel_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive supervisor analytics for hostel.
        
        Args:
            hostel_id: Hostel ID
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Analytics dictionary
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()
        
        # Get active supervisors
        supervisors = self.db.query(Supervisor).filter(
            and_(
                Supervisor.assigned_hostel_id == hostel_id,
                Supervisor.is_deleted == False
            )
        ).all()
        
        total_supervisors = len(supervisors)
        active_supervisors = len([s for s in supervisors if s.is_active])
        
        # Performance distribution
        performances = self.db.query(SupervisorPerformance).filter(
            and_(
                SupervisorPerformance.hostel_id == hostel_id,
                SupervisorPerformance.period_end >= start_date,
                SupervisorPerformance.period_end <= end_date
            )
        ).all()
        
        if performances:
            avg_performance = sum(
                p.overall_performance_score for p in performances
            ) / len(performances)
        else:
            avg_performance = 0
        
        # Activity statistics
        activities = self.db.query(SupervisorActivity).filter(
            and_(
                SupervisorActivity.hostel_id == hostel_id,
                SupervisorActivity.created_at >= datetime.combine(start_date, datetime.min.time()),
                SupervisorActivity.created_at <= datetime.combine(end_date, datetime.max.time())
            )
        ).all()
        
        total_activities = len(activities)
        successful_activities = len([a for a in activities if a.success])
        
        return {
            'hostel_id': hostel_id,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'supervisor_count': {
                'total': total_supervisors,
                'active': active_supervisors,
                'inactive': total_supervisors - active_supervisors
            },
            'performance': {
                'average_score': round(avg_performance, 2),
                'total_records': len(performances)
            },
            'activity': {
                'total_activities': total_activities,
                'successful_activities': successful_activities,
                'success_rate': round(
                    (successful_activities / total_activities * 100)
                    if total_activities > 0 else 0,
                    2
                )
            }
        }
    
    # ==================== Performance Reports ====================
    
    def generate_performance_report(
        self,
        start_date: date,
        end_date: date,
        hostel_id: Optional[str] = None,
        min_grade: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Args:
            start_date: Report start date
            end_date: Report end date
            hostel_id: Optional hostel filter
            min_grade: Optional minimum grade filter
            
        Returns:
            Performance report dictionary
        """
        query = self.db.query(SupervisorPerformance).filter(
            and_(
                SupervisorPerformance.period_end >= start_date,
                SupervisorPerformance.period_end <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(
                SupervisorPerformance.hostel_id == hostel_id
            )
        
        performances = query.options(
            joinedload(SupervisorPerformance.supervisor)
        ).all()
        
        if not performances:
            return {'error': 'No performance data found'}
        
        # Calculate statistics
        scores = [p.overall_performance_score for p in performances]
        
        # Top performers
        top_performers = sorted(
            performances,
            key=lambda p: p.overall_performance_score,
            reverse=True
        )[:10]
        
        # Grade distribution
        grade_distribution = {}
        for perf in performances:
            grade = perf.performance_grade
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
        
        # Metric averages
        metric_averages = {
            'complaint_resolution_rate': round(
                sum(p.complaint_resolution_rate for p in performances) / len(performances),
                2
            ),
            'sla_compliance_rate': round(
                sum(p.sla_compliance_rate for p in performances) / len(performances),
                2
            ),
            'attendance_accuracy': round(
                sum(p.attendance_accuracy for p in performances) / len(performances),
                2
            )
        }
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary': {
                'total_supervisors': len(performances),
                'average_score': round(sum(scores) / len(scores), 2),
                'highest_score': max(scores),
                'lowest_score': min(scores),
                'median_score': sorted(scores)[len(scores) // 2]
            },
            'grade_distribution': grade_distribution,
            'metric_averages': metric_averages,
            'top_performers': [
                {
                    'supervisor_id': p.supervisor_id,
                    'supervisor_name': p.supervisor.user.full_name,
                    'score': float(p.overall_performance_score),
                    'grade': p.performance_grade
                }
                for p in top_performers
            ]
        }
    
    # ==================== Activity Analytics ====================
    
    def get_activity_analytics(
        self,
        hostel_id: Optional[str] = None,
        supervisor_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive activity analytics.
        
        Args:
            hostel_id: Optional hostel filter
            supervisor_id: Optional supervisor filter
            days: Number of days to analyze
            
        Returns:
            Activity analytics dictionary
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        query = self.db.query(SupervisorActivity).filter(
            and_(
                SupervisorActivity.created_at >= start_date,
                SupervisorActivity.created_at <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(
                SupervisorActivity.hostel_id == hostel_id
            )
        
        if supervisor_id:
            query = query.filter(
                SupervisorActivity.supervisor_id == supervisor_id
            )
        
        activities = query.all()
        
        if not activities:
            return {'total_activities': 0}
        
        # Category breakdown
        category_breakdown = {}
        for activity in activities:
            cat = activity.action_category
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        
        # Success analysis
        successful = len([a for a in activities if a.success])
        failed = len(activities) - successful
        
        # Response time analysis
        response_times = [
            a.response_time_ms for a in activities
            if a.response_time_ms is not None
        ]
        avg_response_time = (
            int(sum(response_times) / len(response_times))
            if response_times else None
        )
        
        # Daily activity counts
        daily_counts = {}
        for activity in activities:
            day = activity.created_at.date()
            daily_counts[str(day)] = daily_counts.get(str(day), 0) + 1
        
        return {
            'period_days': days,
            'total_activities': len(activities),
            'successful_activities': successful,
            'failed_activities': failed,
            'success_rate': round(
                (successful / len(activities) * 100),
                2
            ),
            'average_response_time_ms': avg_response_time,
            'category_breakdown': category_breakdown,
            'daily_activity_counts': daily_counts,
            'daily_average': round(len(activities) / days, 2)
        }
    
    # ==================== Comparative Analytics ====================
    
    def compare_supervisors(
        self,
        supervisor_ids: List[str],
        metric: str = "overall_performance",
        period_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Compare multiple supervisors across metrics.
        
        Args:
            supervisor_ids: List of supervisor IDs to compare
            metric: Metric to compare
            period_days: Period for comparison
            
        Returns:
            List of comparison results
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        comparisons = []
        
        for supervisor_id in supervisor_ids:
            supervisor = self.db.query(Supervisor).filter(
                Supervisor.id == supervisor_id
            ).options(
                joinedload(Supervisor.user)
            ).first()
            
            if not supervisor:
                continue
            
            # Get latest performance
            performance = self.db.query(SupervisorPerformance).filter(
                and_(
                    SupervisorPerformance.supervisor_id == supervisor_id,
                    SupervisorPerformance.period_end >= start_date
                )
            ).order_by(
                SupervisorPerformance.period_end.desc()
            ).first()
            
            # Get activity count
            activity_count = self.db.query(func.count(SupervisorActivity.id)).filter(
                and_(
                    SupervisorActivity.supervisor_id == supervisor_id,
                    SupervisorActivity.created_at >= datetime.combine(start_date, datetime.min.time())
                )
            ).scalar()
            
            comparisons.append({
                'supervisor_id': supervisor_id,
                'supervisor_name': supervisor.user.full_name,
                'employee_id': supervisor.employee_id,
                'overall_score': float(performance.overall_performance_score) if performance else 0,
                'grade': performance.performance_grade if performance else 'N/A',
                'total_activities': activity_count,
                'complaints_resolved': supervisor.total_complaints_resolved,
                'attendance_records': supervisor.total_attendance_records
            })
        
        # Sort by metric
        if metric == "overall_performance":
            comparisons.sort(key=lambda x: x['overall_score'], reverse=True)
        elif metric == "activity":
            comparisons.sort(key=lambda x: x['total_activities'], reverse=True)
        
        return comparisons
    
    # ==================== Trend Analysis ====================
    
    def get_performance_trends(
        self,
        supervisor_id: str,
        months: int = 6
    ) -> Dict[str, Any]:
        """
        Get performance trends over time.
        
        Args:
            supervisor_id: Supervisor ID
            months: Number of months to analyze
            
        Returns:
            Trend analysis dictionary
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        performances = self.db.query(SupervisorPerformance).filter(
            and_(
                SupervisorPerformance.supervisor_id == supervisor_id,
                SupervisorPerformance.period_end >= start_date,
                SupervisorPerformance.period_end <= end_date
            )
        ).order_by(
            SupervisorPerformance.period_end
        ).all()
        
        if not performances:
            return {'error': 'No performance data found'}
        
        # Extract trends
        scores = [float(p.overall_performance_score) for p in performances]
        dates = [str(p.period_end) for p in performances]
        
        # Calculate trend direction
        if len(scores) >= 2:
            first_half_avg = sum(scores[:len(scores)//2]) / len(scores[:len(scores)//2])
            second_half_avg = sum(scores[len(scores)//2:]) / len(scores[len(scores)//2:])
            
            if second_half_avg > first_half_avg * 1.05:
                trend = "improving"
            elif second_half_avg < first_half_avg * 0.95:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            'supervisor_id': supervisor_id,
            'period_months': months,
            'data_points': len(performances),
            'trend': trend,
            'scores': scores,
            'dates': dates,
            'average_score': round(sum(scores) / len(scores), 2),
            'highest_score': max(scores),
            'lowest_score': min(scores),
            'improvement': round(scores[-1] - scores[0], 2) if len(scores) > 1 else 0
        }