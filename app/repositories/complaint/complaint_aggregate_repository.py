# --- File: complaint_aggregate_repository.py ---
"""
Complaint aggregate repository for complex multi-entity queries.

Provides high-level aggregation queries combining data from multiple
complaint-related entities for comprehensive insights.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.complaint.complaint import Complaint
from app.models.complaint.complaint_assignment import ComplaintAssignment
from app.models.complaint.complaint_comment import ComplaintComment
from app.models.complaint.complaint_escalation import ComplaintEscalation
from app.models.complaint.complaint_feedback import ComplaintFeedback
from app.models.complaint.complaint_resolution import ComplaintResolution
from app.models.hostel.hostel import Hostel
from app.models.student.student import Student
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository


class ComplaintAggregateRepository:
    """
    Aggregate repository for complex complaint queries.
    
    Provides comprehensive queries combining multiple entities
    for advanced analytics and reporting.
    """

    def __init__(self, session: Session):
        """
        Initialize aggregate repository.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    # ==================== Dashboard Queries ====================

    def get_dashboard_summary(
        self,
        hostel_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary.
        
        Args:
            hostel_id: Optional hostel filter
            user_id: Optional user filter for personalization
            
        Returns:
            Dictionary with dashboard metrics
        """
        now = datetime.now(timezone.utc)
        today_start = datetime.combine(now.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # Base query
        query = select(Complaint).where(Complaint.deleted_at.is_(None))
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        if user_id:
            query = query.where(
                or_(
                    Complaint.assigned_to == user_id,
                    Complaint.raised_by == user_id,
                )
            )
        
        result = self.session.execute(query)
        all_complaints = list(result.scalars().all())
        
        # Calculate metrics
        total = len(all_complaints)
        
        from app.models.base.enums import ComplaintStatus
        open_count = len([c for c in all_complaints if c.status == ComplaintStatus.OPEN])
        in_progress = len([c for c in all_complaints if c.status == ComplaintStatus.IN_PROGRESS])
        resolved = len([c for c in all_complaints if c.status == ComplaintStatus.RESOLVED])
        
        overdue = len([
            c for c in all_complaints
            if c.sla_due_at and c.sla_due_at < now and c.status not in [
                ComplaintStatus.RESOLVED,
                ComplaintStatus.CLOSED,
            ]
        ])
        
        escalated = len([c for c in all_complaints if c.escalated])
        
        # Today's complaints
        today_complaints = len([
            c for c in all_complaints
            if c.opened_at >= today_start
        ])
        
        # Pending assignments
        pending_assignment = len([
            c for c in all_complaints
            if c.status == ComplaintStatus.OPEN and c.assigned_to is None
        ])
        
        return {
            "total_complaints": total,
            "open_complaints": open_count,
            "in_progress_complaints": in_progress,
            "resolved_complaints": resolved,
            "overdue_complaints": overdue,
            "escalated_complaints": escalated,
            "today_complaints": today_complaints,
            "pending_assignment": pending_assignment,
        }

    def get_complaint_details_with_relations(
        self,
        complaint_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get complaint with all related entities.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Dictionary with complaint and related data
        """
        # Load complaint with relationships
        query = (
            select(Complaint)
            .where(Complaint.id == complaint_id)
            .options(
                joinedload(Complaint.hostel),
                joinedload(Complaint.raiser),
                joinedload(Complaint.student),
                joinedload(Complaint.room),
                joinedload(Complaint.assignee),
            )
        )
        
        result = self.session.execute(query)
        complaint = result.scalar_one_or_none()
        
        if not complaint:
            return None
        
        # Get assignments
        assignments_query = (
            select(ComplaintAssignment)
            .where(ComplaintAssignment.complaint_id == complaint_id)
            .order_by(desc(ComplaintAssignment.assigned_at))
        )
        assignments_result = self.session.execute(assignments_query)
        assignments = list(assignments_result.scalars().all())
        
        # Get comments
        comments_query = (
            select(ComplaintComment)
            .where(
                and_(
                    ComplaintComment.complaint_id == complaint_id,
                    ComplaintComment.deleted_at.is_(None),
                )
            )
            .order_by(ComplaintComment.created_at.asc())
        )
        comments_result = self.session.execute(comments_query)
        comments = list(comments_result.scalars().all())
        
        # Get escalations
        escalations_query = (
            select(ComplaintEscalation)
            .where(ComplaintEscalation.complaint_id == complaint_id)
            .order_by(desc(ComplaintEscalation.escalated_at))
        )
        escalations_result = self.session.execute(escalations_query)
        escalations = list(escalations_result.scalars().all())
        
        # Get resolutions
        resolutions_query = (
            select(ComplaintResolution)
            .where(ComplaintResolution.complaint_id == complaint_id)
            .order_by(desc(ComplaintResolution.resolved_at))
        )
        resolutions_result = self.session.execute(resolutions_query)
        resolutions = list(resolutions_result.scalars().all())
        
        # Get feedback
        feedback_query = select(ComplaintFeedback).where(
            ComplaintFeedback.complaint_id == complaint_id
        )
        feedback_result = self.session.execute(feedback_query)
        feedback = feedback_result.scalar_one_or_none()
        
        return {
            "complaint": complaint,
            "assignments": assignments,
            "comments": comments,
            "escalations": escalations,
            "resolutions": resolutions,
            "feedback": feedback,
        }

    # ==================== Analytics Queries ====================

    def get_hostel_performance_comparison(
        self,
        hostel_ids: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compare performance across multiple hostels.
        
        Args:
            hostel_ids: List of hostel identifiers
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            List of hostel performance metrics
        """
        comparison = []
        
        for hostel_id in hostel_ids:
            query = select(Complaint).where(
                and_(
                    Complaint.hostel_id == hostel_id,
                    Complaint.deleted_at.is_(None),
                )
            )
            
            if date_from:
                query = query.where(Complaint.opened_at >= date_from)
            
            if date_to:
                query = query.where(Complaint.opened_at <= date_to)
            
            result = self.session.execute(query)
            complaints = list(result.scalars().all())
            
            if complaints:
                total = len(complaints)
                resolved = len([c for c in complaints if c.resolved_at])
                sla_compliant = len([c for c in complaints if not c.sla_breach])
                
                # Average resolution time
                resolution_times = [
                    (c.resolved_at - c.opened_at).total_seconds() / 3600
                    for c in complaints if c.resolved_at
                ]
                avg_time = sum(resolution_times) / len(resolution_times) if resolution_times else None
                
                comparison.append({
                    "hostel_id": hostel_id,
                    "total_complaints": total,
                    "resolved_count": resolved,
                    "resolution_rate": (resolved / total * 100) if total > 0 else 0,
                    "sla_compliance_rate": (sla_compliant / total * 100) if total > 0 else 0,
                    "avg_resolution_time_hours": round(avg_time, 2) if avg_time else None,
                })
        
        return comparison

    def get_category_performance_trends(
        self,
        hostel_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get performance trends by category.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Dictionary mapping categories to trend data
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        query = select(Complaint).where(
            and_(
                Complaint.opened_at >= start_date,
                Complaint.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        complaints = list(result.scalars().all())
        
        # Group by category
        from app.models.base.enums import ComplaintCategory
        trends = {}
        
        for category in ComplaintCategory:
            category_complaints = [
                c for c in complaints
                if c.category == category
            ]
            
            if category_complaints:
                total = len(category_complaints)
                resolved = len([c for c in category_complaints if c.resolved_at])
                
                resolution_times = [
                    (c.resolved_at - c.opened_at).total_seconds() / 3600
                    for c in category_complaints if c.resolved_at
                ]
                
                trends[category.value] = {
                    "total_complaints": total,
                    "resolved_count": resolved,
                    "resolution_rate": (resolved / total * 100) if total > 0 else 0,
                    "avg_resolution_time": (
                        round(sum(resolution_times) / len(resolution_times), 2)
                        if resolution_times else None
                    ),
                }
        
        return trends

    def get_staff_workload_overview(
        self,
        hostel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get workload overview for all staff.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of staff workload metrics
        """
        from app.models.base.enums import ComplaintStatus
        
        # Get active assignments
        query = (
            select(
                ComplaintAssignment.assigned_to,
                func.count(ComplaintAssignment.id).label("active_count"),
            )
            .join(Complaint)
            .where(
                and_(
                    ComplaintAssignment.is_current == True,
                    Complaint.status.in_([
                        ComplaintStatus.ASSIGNED,
                        ComplaintStatus.IN_PROGRESS,
                    ]),
                    Complaint.deleted_at.is_(None),
                )
            )
            .group_by(ComplaintAssignment.assigned_to)
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        workload = []
        for row in result:
            # Get user details
            user_query = select(User).where(User.id == row.assigned_to)
            user_result = self.session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if user:
                workload.append({
                    "user_id": row.assigned_to,
                    "user_name": user.full_name,
                    "active_assignments": row.active_count,
                })
        
        return sorted(workload, key=lambda x: x["active_assignments"], reverse=True)

    # ==================== Reporting Queries ====================

    def generate_executive_report(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive executive report.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Dictionary with executive metrics
        """
        # Get all complaints in period
        query = select(Complaint).where(Complaint.deleted_at.is_(None))
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(Complaint.opened_at >= date_from)
        
        if date_to:
            query = query.where(Complaint.opened_at <= date_to)
        
        result = self.session.execute(query)
        complaints = list(result.scalars().all())
        
        if not complaints:
            return {"message": "No data for specified period"}
        
        total = len(complaints)
        
        # Resolution metrics
        resolved = [c for c in complaints if c.resolved_at]
        resolution_rate = (len(resolved) / total * 100) if total > 0 else 0
        
        resolution_times = [
            (c.resolved_at - c.opened_at).total_seconds() / 3600
            for c in resolved
        ]
        
        avg_resolution_time = (
            sum(resolution_times) / len(resolution_times)
            if resolution_times else None
        )
        
        # SLA metrics
        sla_compliant = len([c for c in complaints if not c.sla_breach])
        sla_compliance_rate = (sla_compliant / total * 100) if total > 0 else 0
        
        # Escalation metrics
        escalated = len([c for c in complaints if c.escalated])
        escalation_rate = (escalated / total * 100) if total > 0 else 0
        
        # Feedback metrics
        feedback_query = (
            select(ComplaintFeedback)
            .join(Complaint)
            .where(Complaint.id.in_([c.id for c in complaints]))
        )
        feedback_result = self.session.execute(feedback_query)
        feedbacks = list(feedback_result.scalars().all())
        
        avg_rating = (
            sum(f.rating for f in feedbacks) / len(feedbacks)
            if feedbacks else None
        )
        
        satisfaction_rate = (
            len([f for f in feedbacks if f.rating >= 4]) / len(feedbacks) * 100
            if feedbacks else None
        )
        
        # Category breakdown
        category_breakdown = {}
        for c in complaints:
            cat = c.category.value
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        
        # Top issues
        top_categories = sorted(
            category_breakdown.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            "summary": {
                "total_complaints": total,
                "resolution_rate": round(resolution_rate, 2),
                "avg_resolution_time_hours": round(avg_resolution_time, 2) if avg_resolution_time else None,
                "sla_compliance_rate": round(sla_compliance_rate, 2),
                "escalation_rate": round(escalation_rate, 2),
                "avg_customer_rating": round(avg_rating, 2) if avg_rating else None,
                "satisfaction_rate": round(satisfaction_rate, 2) if satisfaction_rate else None,
            },
            "top_categories": [
                {"category": cat, "count": count}
                for cat, count in top_categories
            ],
            "category_breakdown": category_breakdown,
        }


