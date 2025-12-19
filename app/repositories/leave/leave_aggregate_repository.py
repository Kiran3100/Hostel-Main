"""
Leave Aggregate Repository

Comprehensive aggregation and reporting across all leave entities
with advanced analytics, dashboards, and insights.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case, extract, distinct
from sqlalchemy.orm import Session

from app.models.leave.leave_application import (
    LeaveApplication,
    LeaveStatusHistory,
)
from app.models.leave.leave_approval import LeaveApproval
from app.models.leave.leave_balance import (
    LeaveBalance,
    LeaveUsage,
    LeaveCarryForward,
)
from app.models.common.enums import LeaveStatus, LeaveType
from app.repositories.base.base_repository import BaseRepository


class LeaveAggregateRepository:
    """
    Aggregate repository for comprehensive leave analytics and reporting.
    
    Features:
    - Cross-entity analytics
    - Dashboard data aggregation
    - Trend analysis
    - Predictive insights
    - Performance metrics
    - Compliance reporting
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    # ============================================================================
    # DASHBOARD ANALYTICS
    # ============================================================================

    def get_hostel_dashboard(
        self,
        hostel_id: UUID,
        date_range: Optional[Tuple[date, date]] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive hostel leave dashboard.
        
        Args:
            hostel_id: Hostel ID
            date_range: Optional (from_date, to_date)
            
        Returns:
            Dashboard data
        """
        if date_range:
            from_date, to_date = date_range
        else:
            from_date = date.today() - timedelta(days=30)
            to_date = date.today()
        
        # Active leaves
        active_leaves = self.session.query(func.count(LeaveApplication.id)).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.from_date <= date.today(),
            LeaveApplication.to_date >= date.today(),
            LeaveApplication.deleted_at.is_(None)
        ).scalar() or 0
        
        # Pending approvals
        pending_approvals = self.session.query(func.count(LeaveApplication.id)).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.status == LeaveStatus.PENDING,
            LeaveApplication.deleted_at.is_(None)
        ).scalar() or 0
        
        # Overdue returns
        overdue_returns = self.session.query(func.count(LeaveApplication.id)).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.to_date < date.today(),
            LeaveApplication.return_confirmed == False,
            LeaveApplication.deleted_at.is_(None)
        ).scalar() or 0
        
        # Applications in date range
        applications_in_range = self.session.query(
            LeaveApplication.status,
            func.count(LeaveApplication.id)
        ).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.applied_at >= datetime.combine(from_date, datetime.min.time()),
            LeaveApplication.applied_at <= datetime.combine(to_date, datetime.max.time()),
            LeaveApplication.deleted_at.is_(None)
        ).group_by(LeaveApplication.status).all()
        
        status_breakdown = {status.value: count for status, count in applications_in_range}
        
        # Average processing time
        avg_processing = self.session.query(
            func.avg(
                func.extract('epoch', LeaveApplication.approved_at - LeaveApplication.applied_at)
            )
        ).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.approved_at.isnot(None),
            LeaveApplication.applied_at >= datetime.combine(from_date, datetime.min.time()),
            LeaveApplication.deleted_at.is_(None)
        ).scalar()
        
        # Applications by type
        by_type = self.session.query(
            LeaveApplication.leave_type,
            func.count(LeaveApplication.id)
        ).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.applied_at >= datetime.combine(from_date, datetime.min.time()),
            LeaveApplication.applied_at <= datetime.combine(to_date, datetime.max.time()),
            LeaveApplication.deleted_at.is_(None)
        ).group_by(LeaveApplication.leave_type).all()
        
        return {
            'summary': {
                'active_leaves': active_leaves,
                'pending_approvals': pending_approvals,
                'overdue_returns': overdue_returns,
                'total_applications': sum(status_breakdown.values()),
            },
            'status_breakdown': status_breakdown,
            'leave_type_breakdown': {lt.value: count for lt, count in by_type},
            'performance_metrics': {
                'average_processing_hours': round(avg_processing / 3600, 2) if avg_processing else None,
                'approval_rate': round(
                    (status_breakdown.get('approved', 0) / sum(status_breakdown.values()) * 100)
                    if sum(status_breakdown.values()) > 0 else 0,
                    2
                )
            },
            'date_range': {
                'from': str(from_date),
                'to': str(to_date)
            }
        }

    def get_student_dashboard(
        self,
        student_id: UUID,
        academic_year_start: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive student leave dashboard.
        
        Args:
            student_id: Student ID
            academic_year_start: Academic year (default: current)
            
        Returns:
            Student dashboard data
        """
        if academic_year_start is None:
            academic_year_start = self._get_current_academic_year_start()
        
        academic_year_end = date(
            academic_year_start.year + 1,
            academic_year_start.month,
            academic_year_start.day
        )
        
        # Get all balances
        balances = self.session.query(LeaveBalance).filter(
            LeaveBalance.student_id == student_id,
            LeaveBalance.academic_year_start == academic_year_start,
            LeaveBalance.is_active == True
        ).all()
        
        balance_summary = []
        for balance in balances:
            balance_summary.append({
                'leave_type': balance.leave_type.value,
                'allocated': balance.allocated_days,
                'used': balance.used_days,
                'pending': balance.pending_days,
                'remaining': balance.remaining_days,
                'carry_forward': balance.carry_forward_days,
                'utilization_percentage': balance.usage_percentage,
                'status': balance.utilization_status
            })
        
        # Recent applications
        recent_apps = self.session.query(LeaveApplication).filter(
            LeaveApplication.student_id == student_id,
            LeaveApplication.deleted_at.is_(None)
        ).order_by(LeaveApplication.applied_at.desc()).limit(5).all()
        
        # Active leave
        active_leave = self.session.query(LeaveApplication).filter(
            LeaveApplication.student_id == student_id,
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.from_date <= date.today(),
            LeaveApplication.to_date >= date.today(),
            LeaveApplication.deleted_at.is_(None)
        ).first()
        
        # Upcoming leaves
        upcoming = self.session.query(LeaveApplication).filter(
            LeaveApplication.student_id == student_id,
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.from_date > date.today(),
            LeaveApplication.deleted_at.is_(None)
        ).order_by(LeaveApplication.from_date).limit(3).all()
        
        return {
            'balances': balance_summary,
            'active_leave': {
                'id': str(active_leave.id),
                'leave_type': active_leave.leave_type.value,
                'from_date': str(active_leave.from_date),
                'to_date': str(active_leave.to_date),
                'days_remaining': active_leave.days_remaining
            } if active_leave else None,
            'upcoming_leaves': [
                {
                    'id': str(leave.id),
                    'leave_type': leave.leave_type.value,
                    'from_date': str(leave.from_date),
                    'to_date': str(leave.to_date),
                    'total_days': leave.total_days,
                    'days_until_start': leave.days_until_start
                }
                for leave in upcoming
            ],
            'recent_applications': [
                {
                    'id': str(app.id),
                    'leave_type': app.leave_type.value,
                    'status': app.status.value,
                    'applied_at': app.applied_at.isoformat(),
                    'from_date': str(app.from_date),
                    'to_date': str(app.to_date),
                    'total_days': app.total_days
                }
                for app in recent_apps
            ]
        }

    # ============================================================================
    # TREND ANALYSIS
    # ============================================================================

    def get_leave_trends(
        self,
        hostel_id: Optional[UUID] = None,
        period_days: int = 90,
        group_by: str = 'day'  # day, week, month
    ) -> Dict[str, Any]:
        """
        Get leave application trends.
        
        Args:
            hostel_id: Optional hostel filter
            period_days: Number of days to analyze
            group_by: Grouping period
            
        Returns:
            Trend data
        """
        start_date = datetime.utcnow() - timedelta(days=period_days)
        
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.applied_at >= start_date,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        # Group by period
        if group_by == 'day':
            date_trunc = func.date_trunc('day', LeaveApplication.applied_at)
        elif group_by == 'week':
            date_trunc = func.date_trunc('week', LeaveApplication.applied_at)
        else:  # month
            date_trunc = func.date_trunc('month', LeaveApplication.applied_at)
        
        trends = self.session.query(
            date_trunc.label('period'),
            func.count(LeaveApplication.id).label('total'),
            func.count(case([(LeaveApplication.status == LeaveStatus.APPROVED, 1)])).label('approved'),
            func.count(case([(LeaveApplication.status == LeaveStatus.REJECTED, 1)])).label('rejected'),
            func.count(case([(LeaveApplication.status == LeaveStatus.PENDING, 1)])).label('pending')
        ).filter(
            LeaveApplication.applied_at >= start_date,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            trends = trends.filter(LeaveApplication.hostel_id == hostel_id)
        
        trends = trends.group_by('period').order_by('period').all()
        
        return {
            'period_days': period_days,
            'group_by': group_by,
            'trends': [
                {
                    'period': period.isoformat(),
                    'total': total,
                    'approved': approved,
                    'rejected': rejected,
                    'pending': pending,
                    'approval_rate': round((approved / total * 100) if total > 0 else 0, 2)
                }
                for period, total, approved, rejected, pending in trends
            ]
        }

    def get_seasonal_patterns(
        self,
        hostel_id: Optional[UUID] = None,
        years: int = 2
    ) -> Dict[str, Any]:
        """
        Analyze seasonal leave patterns.
        
        Args:
            hostel_id: Optional hostel filter
            years: Number of years to analyze
            
        Returns:
            Seasonal pattern data
        """
        start_date = datetime.utcnow() - timedelta(days=years * 365)
        
        query = self.session.query(
            extract('month', LeaveApplication.from_date).label('month'),
            func.count(LeaveApplication.id).label('count'),
            func.avg(LeaveApplication.total_days).label('avg_days')
        ).filter(
            LeaveApplication.from_date >= start_date.date(),
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        patterns = query.group_by('month').order_by('month').all()
        
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        
        return {
            'years_analyzed': years,
            'monthly_patterns': [
                {
                    'month': int(month),
                    'month_name': month_names[int(month) - 1],
                    'total_leaves': count,
                    'average_days': round(float(avg_days), 2)
                }
                for month, count, avg_days in patterns
            ]
        }

    # ============================================================================
    # COMPARATIVE ANALYTICS
    # ============================================================================

    def compare_leave_types(
        self,
        hostel_id: Optional[UUID] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Compare performance across leave types.
        
        Args:
            hostel_id: Optional hostel filter
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Comparative data
        """
        query = self.session.query(
            LeaveApplication.leave_type,
            func.count(LeaveApplication.id).label('total'),
            func.count(case([(LeaveApplication.status == LeaveStatus.APPROVED, 1)])).label('approved'),
            func.count(case([(LeaveApplication.status == LeaveStatus.REJECTED, 1)])).label('rejected'),
            func.avg(LeaveApplication.total_days).label('avg_days'),
            func.avg(
                func.extract('epoch', LeaveApplication.approved_at - LeaveApplication.applied_at)
            ).label('avg_processing_time')
        ).filter(
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        if from_date:
            query = query.filter(LeaveApplication.applied_at >= datetime.combine(from_date, datetime.min.time()))
        
        if to_date:
            query = query.filter(LeaveApplication.applied_at <= datetime.combine(to_date, datetime.max.time()))
        
        comparisons = query.group_by(LeaveApplication.leave_type).all()
        
        return {
            'comparisons': [
                {
                    'leave_type': leave_type.value,
                    'total_applications': total,
                    'approved': approved,
                    'rejected': rejected,
                    'approval_rate': round((approved / total * 100) if total > 0 else 0, 2),
                    'average_days': round(float(avg_days), 2) if avg_days else 0,
                    'average_processing_hours': round(float(avg_time / 3600), 2) if avg_time else None
                }
                for leave_type, total, approved, rejected, avg_days, avg_time in comparisons
            ]
        }

    def compare_hostels(
        self,
        hostel_ids: List[UUID],
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Compare leave metrics across hostels.
        
        Args:
            hostel_ids: List of hostel IDs
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Comparative data
        """
        query = self.session.query(
            LeaveApplication.hostel_id,
            func.count(LeaveApplication.id).label('total'),
            func.count(case([(LeaveApplication.status == LeaveStatus.APPROVED, 1)])).label('approved'),
            func.count(case([(LeaveApplication.status == LeaveStatus.PENDING, 1)])).label('pending'),
            func.avg(LeaveApplication.total_days).label('avg_days')
        ).filter(
            LeaveApplication.hostel_id.in_(hostel_ids),
            LeaveApplication.deleted_at.is_(None)
        )
        
        if from_date:
            query = query.filter(LeaveApplication.applied_at >= datetime.combine(from_date, datetime.min.time()))
        
        if to_date:
            query = query.filter(LeaveApplication.applied_at <= datetime.combine(to_date, datetime.max.time()))
        
        comparisons = query.group_by(LeaveApplication.hostel_id).all()
        
        return {
            'comparisons': [
                {
                    'hostel_id': str(hostel_id),
                    'total_applications': total,
                    'approved': approved,
                    'pending': pending,
                    'approval_rate': round((approved / total * 100) if total > 0 else 0, 2),
                    'average_days': round(float(avg_days), 2) if avg_days else 0
                }
                for hostel_id, total, approved, pending, avg_days in comparisons
            ]
        }

    # ============================================================================
    # PERFORMANCE METRICS
    # ============================================================================

    def get_approval_performance(
        self,
        hostel_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive approval performance metrics.
        
        Args:
            hostel_id: Optional hostel filter
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Performance metrics
        """
        # Average decision time
        decision_times = self.session.query(
            func.avg(
                func.extract('epoch', LeaveApproval.decision_at - LeaveApplication.applied_at)
            ).label('avg_time'),
            func.min(
                func.extract('epoch', LeaveApproval.decision_at - LeaveApplication.applied_at)
            ).label('min_time'),
            func.max(
                func.extract('epoch', LeaveApproval.decision_at - LeaveApplication.applied_at)
            ).label('max_time')
        ).join(
            LeaveApplication,
            LeaveApproval.leave_id == LeaveApplication.id
        ).filter(
            LeaveApproval.is_auto_approved == False
        )
        
        if hostel_id:
            decision_times = decision_times.filter(LeaveApplication.hostel_id == hostel_id)
        
        if from_date:
            decision_times = decision_times.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            decision_times = decision_times.filter(LeaveApproval.decision_at <= to_date)
        
        times = decision_times.first()
        
        # Approver performance
        top_approvers = self.session.query(
            LeaveApproval.approver_id,
            func.count(LeaveApproval.id).label('count'),
            func.avg(
                func.extract('epoch', LeaveApproval.decision_at - LeaveApplication.applied_at)
            ).label('avg_time'),
            func.count(case([(LeaveApproval.is_approved == True, 1)])).label('approved')
        ).join(
            LeaveApplication,
            LeaveApproval.leave_id == LeaveApplication.id
        ).filter(
            LeaveApproval.approver_id.isnot(None)
        )
        
        if hostel_id:
            top_approvers = top_approvers.filter(LeaveApplication.hostel_id == hostel_id)
        
        if from_date:
            top_approvers = top_approvers.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            top_approvers = top_approvers.filter(LeaveApproval.decision_at <= to_date)
        
        top_approvers = top_approvers.group_by(
            LeaveApproval.approver_id
        ).order_by(
            func.count(LeaveApproval.id).desc()
        ).limit(10).all()
        
        return {
            'decision_times': {
                'average_hours': round(times.avg_time / 3600, 2) if times.avg_time else None,
                'minimum_hours': round(times.min_time / 3600, 2) if times.min_time else None,
                'maximum_hours': round(times.max_time / 3600, 2) if times.max_time else None
            },
            'top_approvers': [
                {
                    'approver_id': str(approver_id),
                    'total_decisions': count,
                    'average_decision_hours': round(avg_time / 3600, 2) if avg_time else None,
                    'approved_count': approved,
                    'approval_rate': round((approved / count * 100) if count > 0 else 0, 2)
                }
                for approver_id, count, avg_time, approved in top_approvers
            ]
        }

    def get_compliance_metrics(
        self,
        hostel_id: Optional[UUID] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get compliance and policy adherence metrics.
        
        Args:
            hostel_id: Optional hostel filter
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Compliance metrics
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        if from_date:
            query = query.filter(LeaveApplication.applied_at >= datetime.combine(from_date, datetime.min.time()))
        
        if to_date:
            query = query.filter(LeaveApplication.applied_at <= datetime.combine(to_date, datetime.max.time()))
        
        total = query.count()
        
        # Document compliance
        with_documents = query.filter(
            LeaveApplication.supporting_document_url.isnot(None)
        ).count()
        
        # Return confirmation compliance
        should_be_confirmed = query.filter(
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.to_date < date.today()
        ).count()
        
        confirmed = query.filter(
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.to_date < date.today(),
            LeaveApplication.return_confirmed == True
        ).count()
        
        # Backdated applications
        backdated = query.filter(
            LeaveApplication.from_date < func.date(LeaveApplication.applied_at)
        ).count()
        
        return {
            'total_applications': total,
            'document_compliance': {
                'with_documents': with_documents,
                'compliance_rate': round((with_documents / total * 100) if total > 0 else 0, 2)
            },
            'return_confirmation': {
                'should_confirm': should_be_confirmed,
                'confirmed': confirmed,
                'compliance_rate': round((confirmed / should_be_confirmed * 100) if should_be_confirmed > 0 else 0, 2),
                'pending_confirmations': should_be_confirmed - confirmed
            },
            'backdated_applications': {
                'count': backdated,
                'percentage': round((backdated / total * 100) if total > 0 else 0, 2)
            }
        }

    # ============================================================================
    # PREDICTIVE ANALYTICS
    # ============================================================================

    def predict_leave_demand(
        self,
        hostel_id: UUID,
        forecast_days: int = 30
    ) -> Dict[str, Any]:
        """
        Predict leave demand for upcoming period.
        
        Args:
            hostel_id: Hostel ID
            forecast_days: Days to forecast
            
        Returns:
            Demand prediction
        """
        # Analyze historical patterns
        one_year_ago = date.today() - timedelta(days=365)
        
        historical = self.session.query(
            func.count(LeaveApplication.id).label('count')
        ).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.from_date >= one_year_ago,
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.deleted_at.is_(None)
        ).scalar() or 0
        
        # Simple prediction based on historical average
        daily_average = historical / 365
        predicted = int(daily_average * forecast_days)
        
        # Get upcoming scheduled leaves
        scheduled = self.session.query(func.count(LeaveApplication.id)).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.from_date > date.today(),
            LeaveApplication.from_date <= date.today() + timedelta(days=forecast_days),
            LeaveApplication.deleted_at.is_(None)
        ).scalar() or 0
        
        return {
            'forecast_period_days': forecast_days,
            'historical_average_daily': round(daily_average, 2),
            'predicted_applications': predicted,
            'already_scheduled': scheduled,
            'expected_new_applications': max(0, predicted - scheduled),
            'confidence': 'medium'  # Would be calculated based on variance
        }

    def identify_high_risk_students(
        self,
        hostel_id: UUID,
        academic_year_start: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify students at risk of exhausting leave balance.
        
        Args:
            hostel_id: Hostel ID
            academic_year_start: Academic year
            
        Returns:
            List of high-risk students
        """
        if academic_year_start is None:
            academic_year_start = self._get_current_academic_year_start()
        
        # Students with low remaining balance
        low_balance = self.session.query(
            LeaveBalance.student_id,
            LeaveBalance.leave_type,
            LeaveBalance.remaining_days,
            LeaveBalance.used_days,
            LeaveBalance.allocated_days
        ).filter(
            LeaveBalance.academic_year_start == academic_year_start,
            LeaveBalance.remaining_days <= 5,
            LeaveBalance.is_active == True
        ).all()
        
        risk_students = []
        for student_id, leave_type, remaining, used, allocated in low_balance:
            utilization = (used / allocated * 100) if allocated > 0 else 0
            
            risk_students.append({
                'student_id': str(student_id),
                'leave_type': leave_type.value,
                'remaining_days': remaining,
                'used_days': used,
                'allocated_days': allocated,
                'utilization_percentage': round(utilization, 2),
                'risk_level': 'critical' if remaining <= 2 else 'high'
            })
        
        return risk_students

    # ============================================================================
    # EXPORT AND REPORTING
    # ============================================================================

    def generate_comprehensive_report(
        self,
        hostel_id: UUID,
        from_date: date,
        to_date: date
    ) -> Dict[str, Any]:
        """
        Generate comprehensive leave report.
        
        Args:
            hostel_id: Hostel ID
            from_date: Report start date
            to_date: Report end date
            
        Returns:
            Comprehensive report data
        """
        return {
            'report_period': {
                'from': str(from_date),
                'to': str(to_date)
            },
            'hostel_id': str(hostel_id),
            'dashboard': self.get_hostel_dashboard(hostel_id, (from_date, to_date)),
            'trends': self.get_leave_trends(hostel_id, (to_date - from_date).days),
            'leave_type_comparison': self.compare_leave_types(hostel_id, from_date, to_date),
            'approval_performance': self.get_approval_performance(
                hostel_id,
                datetime.combine(from_date, datetime.min.time()),
                datetime.combine(to_date, datetime.max.time())
            ),
            'compliance_metrics': self.get_compliance_metrics(hostel_id, from_date, to_date),
            'generated_at': datetime.utcnow().isoformat()
        }

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_current_academic_year_start(self) -> date:
        """
        Get current academic year start date.
        
        Returns:
            Academic year start date
        """
        today = date.today()
        # Assuming academic year starts in August
        if today.month >= 8:
            return date(today.year, 8, 1)
        else:
            return date(today.year - 1, 8, 1)