"""
Supervisor activity log repository for tracking supervisor actions.

Provides comprehensive supervisor activity tracking with performance
metrics, analytics, and accountability features.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, desc, asc, cast, Integer
from sqlalchemy.orm import Session

from app.models.audit import SupervisorActivityLog
from app.repositories.base.base_repository import BaseRepository
from app.schemas.audit.supervisor_activity_log import SupervisorActionCategory


class SupervisorActivityLogRepository(BaseRepository):
    """
    Repository for supervisor activity tracking and analytics.
    
    Provides comprehensive supervisor action logging, performance
    monitoring, and accountability features.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, SupervisorActivityLog)
    
    # ==================== CRUD Operations ====================
    
    def create_activity_log(
        self,
        supervisor_id: UUID,
        hostel_id: UUID,
        action_type: str,
        action_category: SupervisorActionCategory,
        action_description: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        status: str = "completed",
        metadata: Optional[Dict] = None,
        **kwargs
    ) -> SupervisorActivityLog:
        """
        Create a new supervisor activity log entry.
        
        Args:
            supervisor_id: Supervisor performing action
            hostel_id: Hostel where action occurred
            action_type: Specific action identifier
            action_category: High-level action category
            action_description: Human-readable description
            entity_type: Type of entity affected
            entity_id: ID of affected entity
            status: Action status
            metadata: Additional context
            **kwargs: Additional fields
            
        Returns:
            Created SupervisorActivityLog instance
        """
        activity_log = SupervisorActivityLog(
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            action_type=action_type,
            action_category=action_category,
            action_description=action_description,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            metadata=metadata or {},
            **kwargs
        )
        
        return self.create(activity_log)
    
    def bulk_create_activity_logs(
        self,
        activity_logs: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> List[SupervisorActivityLog]:
        """
        Bulk create supervisor activity logs.
        
        Args:
            activity_logs: List of activity log dictionaries
            batch_size: Batch size for processing
            
        Returns:
            List of created activity logs
        """
        created_logs = []
        
        for i in range(0, len(activity_logs), batch_size):
            batch = activity_logs[i:i + batch_size]
            log_objects = [SupervisorActivityLog(**log_data) for log_data in batch]
            
            self.session.bulk_save_objects(log_objects, return_defaults=True)
            self.session.flush()
            
            created_logs.extend(log_objects)
        
        self.session.commit()
        return created_logs
    
    # ==================== Query Operations ====================
    
    def find_by_supervisor(
        self,
        supervisor_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_category: Optional[SupervisorActionCategory] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[SupervisorActivityLog], int]:
        """
        Find activity logs by supervisor with filtering.
        
        Args:
            supervisor_id: Supervisor ID
            start_date: Start date filter
            end_date: End date filter
            action_category: Optional category filter
            status: Optional status filter
            limit: Maximum results
            offset: Results to skip
            
        Returns:
            Tuple of (activity logs, total count)
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.supervisor_id == supervisor_id
        )
        
        if start_date:
            query = query.filter(SupervisorActivityLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(SupervisorActivityLog.created_at <= end_date)
        
        if action_category:
            query = query.filter(SupervisorActivityLog.action_category == action_category)
        
        if status:
            query = query.filter(SupervisorActivityLog.status == status)
        
        total = query.count()
        
        results = query.order_by(desc(SupervisorActivityLog.created_at))\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        return results, total
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_categories: Optional[List[SupervisorActionCategory]] = None,
        supervisor_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[SupervisorActivityLog], int]:
        """
        Find activity logs by hostel with filtering.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date filter
            end_date: End date filter
            action_categories: Optional categories filter
            supervisor_id: Optional supervisor filter
            limit: Maximum results
            offset: Results to skip
            
        Returns:
            Tuple of (activity logs, total count)
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.hostel_id == hostel_id
        )
        
        if start_date:
            query = query.filter(SupervisorActivityLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(SupervisorActivityLog.created_at <= end_date)
        
        if action_categories:
            query = query.filter(SupervisorActivityLog.action_category.in_(action_categories))
        
        if supervisor_id:
            query = query.filter(SupervisorActivityLog.supervisor_id == supervisor_id)
        
        total = query.count()
        
        results = query.order_by(desc(SupervisorActivityLog.created_at))\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        return results, total
    
    def find_by_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        action_category: Optional[SupervisorActionCategory] = None,
        limit: int = 100
    ) -> List[SupervisorActivityLog]:
        """
        Find activity logs for a specific entity.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            action_category: Optional category filter
            limit: Maximum results
            
        Returns:
            List of activity logs
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.entity_type == entity_type,
            SupervisorActivityLog.entity_id == entity_id
        )
        
        if action_category:
            query = query.filter(SupervisorActivityLog.action_category == action_category)
        
        return query.order_by(desc(SupervisorActivityLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_student(
        self,
        student_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SupervisorActivityLog]:
        """
        Find activities related to a specific student.
        
        Args:
            student_id: Student ID
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            
        Returns:
            List of activity logs
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.related_student_id == student_id
        )
        
        if start_date:
            query = query.filter(SupervisorActivityLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(SupervisorActivityLog.created_at <= end_date)
        
        return query.order_by(desc(SupervisorActivityLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_room(
        self,
        room_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SupervisorActivityLog]:
        """
        Find activities related to a specific room.
        
        Args:
            room_id: Room ID
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            
        Returns:
            List of activity logs
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.related_room_id == room_id
        )
        
        if start_date:
            query = query.filter(SupervisorActivityLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(SupervisorActivityLog.created_at <= end_date)
        
        return query.order_by(desc(SupervisorActivityLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_shift(
        self,
        shift_id: UUID,
        action_category: Optional[SupervisorActionCategory] = None,
        limit: int = 100
    ) -> List[SupervisorActivityLog]:
        """
        Find activities during a specific shift.
        
        Args:
            shift_id: Shift ID
            action_category: Optional category filter
            limit: Maximum results
            
        Returns:
            List of activity logs
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.shift_id == shift_id
        )
        
        if action_category:
            query = query.filter(SupervisorActivityLog.action_category == action_category)
        
        return query.order_by(SupervisorActivityLog.created_at)\
            .limit(limit)\
            .all()
    
    def find_requiring_follow_up(
        self,
        supervisor_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        overdue_only: bool = False,
        limit: int = 100
    ) -> List[SupervisorActivityLog]:
        """
        Find activities requiring follow-up.
        
        Args:
            supervisor_id: Optional supervisor filter
            hostel_id: Optional hostel filter
            overdue_only: Only return overdue follow-ups
            limit: Maximum results
            
        Returns:
            List of activity logs requiring follow-up
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.requires_follow_up == True,
            SupervisorActivityLog.follow_up_completed != True
        )
        
        if supervisor_id:
            query = query.filter(SupervisorActivityLog.supervisor_id == supervisor_id)
        
        if hostel_id:
            query = query.filter(SupervisorActivityLog.hostel_id == hostel_id)
        
        if overdue_only:
            query = query.filter(
                SupervisorActivityLog.follow_up_date < datetime.utcnow()
            )
        
        return query.order_by(SupervisorActivityLog.follow_up_date)\
            .limit(limit)\
            .all()
    
    def find_failed_actions(
        self,
        supervisor_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SupervisorActivityLog]:
        """
        Find failed supervisor actions for analysis.
        
        Args:
            supervisor_id: Optional supervisor filter
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            
        Returns:
            List of failed activity logs
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.status == 'failed'
        )
        
        if supervisor_id:
            query = query.filter(SupervisorActivityLog.supervisor_id == supervisor_id)
        
        if start_date:
            query = query.filter(SupervisorActivityLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(SupervisorActivityLog.created_at <= end_date)
        
        return query.order_by(desc(SupervisorActivityLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_high_priority_actions(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SupervisorActivityLog]:
        """
        Find high priority supervisor actions.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Start date filter
            limit: Maximum results
            
        Returns:
            List of high priority activity logs
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.priority_level.in_(['urgent', 'critical'])
        )
        
        if hostel_id:
            query = query.filter(SupervisorActivityLog.hostel_id == hostel_id)
        
        if start_date:
            query = query.filter(SupervisorActivityLog.created_at >= start_date)
        
        return query.order_by(desc(SupervisorActivityLog.created_at))\
            .limit(limit)\
            .all()
    
    # ==================== Performance Analytics ====================
    
    def get_supervisor_performance_metrics(
        self,
        supervisor_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics for a supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            Performance metrics dictionary
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.supervisor_id == supervisor_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        )
        
        all_activities = query.all()
        total_activities = len(all_activities)
        
        if total_activities == 0:
            return {
                'supervisor_id': str(supervisor_id),
                'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                'total_activities': 0,
                'message': 'No activities found in period'
            }
        
        # Activity breakdown by status
        status_counts = {}
        for activity in all_activities:
            status_counts[activity.status] = status_counts.get(activity.status, 0) + 1
        
        # Category breakdown
        category_counts = {}
        for activity in all_activities:
            cat = activity.action_category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # Calculate average time taken
        timed_activities = [a for a in all_activities if a.time_taken_minutes is not None]
        avg_time_taken = (
            sum(a.time_taken_minutes for a in timed_activities) / len(timed_activities)
            if timed_activities else 0
        )
        
        # Calculate average quality score
        scored_activities = [a for a in all_activities if a.quality_score is not None]
        avg_quality_score = (
            sum(float(a.quality_score) for a in scored_activities) / len(scored_activities)
            if scored_activities else 0
        )
        
        # Calculate average efficiency
        efficient_activities = [a for a in all_activities if a.efficiency_score is not None]
        avg_efficiency = (
            sum(float(a.efficiency_score) for a in efficient_activities) / len(efficient_activities)
            if efficient_activities else 0
        )
        
        # Student feedback
        feedback_activities = [a for a in all_activities if a.student_feedback_score is not None]
        avg_student_feedback = (
            sum(float(a.student_feedback_score) for a in feedback_activities) / len(feedback_activities)
            if feedback_activities else 0
        )
        
        # Follow-up metrics
        follow_up_required = [a for a in all_activities if a.requires_follow_up]
        follow_up_completed = [a for a in follow_up_required if a.follow_up_completed]
        follow_up_completion_rate = (
            len(follow_up_completed) / len(follow_up_required) * 100
            if follow_up_required else 0
        )
        
        # Priority distribution
        priority_counts = {}
        for activity in all_activities:
            if activity.priority_level:
                priority_counts[activity.priority_level] = priority_counts.get(activity.priority_level, 0) + 1
        
        return {
            'supervisor_id': str(supervisor_id),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'activity_summary': {
                'total_activities': total_activities,
                'by_status': status_counts,
                'by_category': category_counts,
                'by_priority': priority_counts,
                'success_rate': (
                    status_counts.get('completed', 0) / total_activities * 100
                    if total_activities else 0
                )
            },
            'performance_metrics': {
                'average_time_taken_minutes': round(avg_time_taken, 2),
                'average_quality_score': round(avg_quality_score, 2),
                'average_efficiency_score': round(avg_efficiency, 2),
                'average_student_feedback': round(avg_student_feedback, 2)
            },
            'follow_up_metrics': {
                'total_requiring_follow_up': len(follow_up_required),
                'completed_follow_ups': len(follow_up_completed),
                'completion_rate': round(follow_up_completion_rate, 2)
            },
            'activities_per_day': round(total_activities / max((end_date - start_date).days, 1), 2)
        }
    
    def get_hostel_activity_summary(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get activity summary for a hostel.
        
        Args:
            hostel_id: Hostel ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            Activity summary dictionary
        """
        query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.hostel_id == hostel_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        )
        
        all_activities = query.all()
        total_activities = len(all_activities)
        
        # Supervisor activity counts
        supervisor_counts = self.session.query(
            SupervisorActivityLog.supervisor_id,
            SupervisorActivityLog.supervisor_name,
            func.count(SupervisorActivityLog.id).label('activity_count')
        ).filter(
            SupervisorActivityLog.hostel_id == hostel_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        ).group_by(
            SupervisorActivityLog.supervisor_id,
            SupervisorActivityLog.supervisor_name
        ).order_by(desc('activity_count')).all()
        
        # Category breakdown
        category_counts = self.session.query(
            SupervisorActivityLog.action_category,
            func.count(SupervisorActivityLog.id).label('count')
        ).filter(
            SupervisorActivityLog.hostel_id == hostel_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        ).group_by(SupervisorActivityLog.action_category).all()
        
        # Top action types
        top_actions = self.session.query(
            SupervisorActivityLog.action_type,
            func.count(SupervisorActivityLog.id).label('count')
        ).filter(
            SupervisorActivityLog.hostel_id == hostel_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        ).group_by(SupervisorActivityLog.action_type)\
            .order_by(desc('count'))\
            .limit(10)\
            .all()
        
        return {
            'hostel_id': str(hostel_id),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_activities': total_activities,
            'supervisor_activity': [
                {
                    'supervisor_id': str(sup_id),
                    'supervisor_name': sup_name,
                    'activity_count': count
                }
                for sup_id, sup_name, count in supervisor_counts
            ],
            'activities_by_category': {
                cat.value: count for cat, count in category_counts
            },
            'top_action_types': [
                {'action_type': action, 'count': count}
                for action, count in top_actions
            ]
        }
    
    def get_activity_timeline(
        self,
        supervisor_id: UUID,
        start_date: datetime,
        end_date: datetime,
        group_by: str = 'day'  # 'hour', 'day', 'week'
    ) -> List[Dict[str, Any]]:
        """
        Get supervisor activity timeline.
        
        Args:
            supervisor_id: Supervisor ID
            start_date: Period start
            end_date: Period end
            group_by: Grouping interval
            
        Returns:
            Timeline data points
        """
        if group_by == 'hour':
            time_format = func.date_trunc('hour', SupervisorActivityLog.created_at)
        elif group_by == 'day':
            time_format = func.date_trunc('day', SupervisorActivityLog.created_at)
        elif group_by == 'week':
            time_format = func.date_trunc('week', SupervisorActivityLog.created_at)
        else:
            time_format = func.date_trunc('day', SupervisorActivityLog.created_at)
        
        timeline = self.session.query(
            time_format.label('time_bucket'),
            func.count(SupervisorActivityLog.id).label('activity_count'),
            SupervisorActivityLog.action_category
        ).filter(
            SupervisorActivityLog.supervisor_id == supervisor_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        ).group_by(
            'time_bucket',
            SupervisorActivityLog.action_category
        ).order_by('time_bucket').all()
        
        return [
            {
                'timestamp': bucket.isoformat(),
                'count': count,
                'category': category.value
            }
            for bucket, count, category in timeline
        ]
    
    def get_efficiency_analysis(
        self,
        supervisor_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Analyze supervisor efficiency metrics.
        
        Args:
            supervisor_id: Supervisor ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            Efficiency analysis
        """
        activities = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.supervisor_id == supervisor_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date,
            SupervisorActivityLog.efficiency_score.isnot(None)
        ).all()
        
        if not activities:
            return {
                'supervisor_id': str(supervisor_id),
                'message': 'No efficiency data available'
            }
        
        efficiency_scores = [float(a.efficiency_score) for a in activities]
        
        # Calculate statistics
        avg_efficiency = sum(efficiency_scores) / len(efficiency_scores)
        min_efficiency = min(efficiency_scores)
        max_efficiency = max(efficiency_scores)
        
        # Efficiency by category
        category_efficiency = {}
        for activity in activities:
            cat = activity.action_category.value
            if cat not in category_efficiency:
                category_efficiency[cat] = []
            category_efficiency[cat].append(float(activity.efficiency_score))
        
        category_avg = {
            cat: sum(scores) / len(scores)
            for cat, scores in category_efficiency.items()
        }
        
        # Trend analysis (simple linear trend)
        if len(activities) > 1:
            sorted_activities = sorted(activities, key=lambda a: a.created_at)
            first_half = sorted_activities[:len(sorted_activities)//2]
            second_half = sorted_activities[len(sorted_activities)//2:]
            
            first_avg = sum(float(a.efficiency_score) for a in first_half) / len(first_half)
            second_avg = sum(float(a.efficiency_score) for a in second_half) / len(second_half)
            
            trend = 'improving' if second_avg > first_avg else 'declining' if second_avg < first_avg else 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'supervisor_id': str(supervisor_id),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'overall_efficiency': {
                'average': round(avg_efficiency, 2),
                'minimum': round(min_efficiency, 2),
                'maximum': round(max_efficiency, 2),
                'total_activities': len(activities)
            },
            'efficiency_by_category': {
                cat: round(avg, 2)
                for cat, avg in category_avg.items()
            },
            'trend': trend
        }
    
    def compare_supervisor_performance(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Compare performance across supervisors in a hostel.
        
        Args:
            hostel_id: Hostel ID
            start_date: Period start
            end_date: Period end
            limit: Number of supervisors to include
            
        Returns:
            Comparative performance data
        """
        # Get supervisor activity counts and metrics
        supervisor_stats = self.session.query(
            SupervisorActivityLog.supervisor_id,
            SupervisorActivityLog.supervisor_name,
            func.count(SupervisorActivityLog.id).label('total_activities'),
            func.avg(SupervisorActivityLog.quality_score).label('avg_quality'),
            func.avg(SupervisorActivityLog.efficiency_score).label('avg_efficiency'),
            func.avg(SupervisorActivityLog.student_feedback_score).label('avg_feedback')
        ).filter(
            SupervisorActivityLog.hostel_id == hostel_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        ).group_by(
            SupervisorActivityLog.supervisor_id,
            SupervisorActivityLog.supervisor_name
        ).order_by(desc('total_activities')).limit(limit).all()
        
        results = []
        for sup_id, sup_name, total, quality, efficiency, feedback in supervisor_stats:
            # Get success rate
            completed = self.session.query(func.count(SupervisorActivityLog.id)).filter(
                SupervisorActivityLog.supervisor_id == sup_id,
                SupervisorActivityLog.hostel_id == hostel_id,
                SupervisorActivityLog.created_at >= start_date,
                SupervisorActivityLog.created_at <= end_date,
                SupervisorActivityLog.status == 'completed'
            ).scalar()
            
            success_rate = (completed / total * 100) if total else 0
            
            results.append({
                'supervisor_id': str(sup_id),
                'supervisor_name': sup_name,
                'total_activities': total,
                'success_rate': round(success_rate, 2),
                'average_quality_score': round(float(quality), 2) if quality else None,
                'average_efficiency_score': round(float(efficiency), 2) if efficiency else None,
                'average_student_feedback': round(float(feedback), 2) if feedback else None
            })
        
        return results
    
    def get_workload_distribution(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Analyze workload distribution across supervisors.
        
        Args:
            hostel_id: Hostel ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            Workload distribution analysis
        """
        workload = self.session.query(
            SupervisorActivityLog.supervisor_id,
            SupervisorActivityLog.supervisor_name,
            func.count(SupervisorActivityLog.id).label('activity_count'),
            func.sum(SupervisorActivityLog.time_taken_minutes).label('total_time')
        ).filter(
            SupervisorActivityLog.hostel_id == hostel_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        ).group_by(
            SupervisorActivityLog.supervisor_id,
            SupervisorActivityLog.supervisor_name
        ).all()
        
        if not workload:
            return {
                'hostel_id': str(hostel_id),
                'message': 'No workload data available'
            }
        
        total_activities = sum(w[2] for w in workload)
        activity_counts = [w[2] for w in workload]
        avg_activities = total_activities / len(workload)
        
        # Calculate workload balance (coefficient of variation)
        variance = sum((count - avg_activities) ** 2 for count in activity_counts) / len(activity_counts)
        std_dev = variance ** 0.5
        cv = (std_dev / avg_activities * 100) if avg_activities else 0
        
        # Identify overloaded and underloaded supervisors
        threshold_high = avg_activities * 1.5
        threshold_low = avg_activities * 0.5
        
        distribution = []
        for sup_id, sup_name, count, total_time in workload:
            status = 'balanced'
            if count > threshold_high:
                status = 'overloaded'
            elif count < threshold_low:
                status = 'underloaded'
            
            distribution.append({
                'supervisor_id': str(sup_id),
                'supervisor_name': sup_name,
                'activity_count': count,
                'total_time_minutes': int(total_time) if total_time else 0,
                'workload_status': status,
                'percentage_of_total': round(count / total_activities * 100, 2)
            })
        
        return {
            'hostel_id': str(hostel_id),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_activities': total_activities,
            'average_activities_per_supervisor': round(avg_activities, 2),
            'workload_balance_coefficient': round(cv, 2),
            'balance_assessment': 'balanced' if cv < 30 else 'unbalanced',
            'supervisor_distribution': sorted(
                distribution,
                key=lambda x: x['activity_count'],
                reverse=True
            )
        }
    
    # ==================== Maintenance Operations ====================
    
    def mark_follow_up_completed(
        self,
        activity_id: UUID
    ) -> SupervisorActivityLog:
        """
        Mark an activity's follow-up as completed.
        
        Args:
            activity_id: Activity log ID
            
        Returns:
            Updated activity log
        """
        activity = self.get_by_id(activity_id)
        if not activity:
            raise ValueError(f"Activity {activity_id} not found")
        
        activity.follow_up_completed = True
        self.session.commit()
        
        return activity
    
    def cleanup_old_logs(
        self,
        cutoff_date: datetime,
        batch_size: int = 1000
    ) -> int:
        """
        Archive or delete old activity logs.
        
        Args:
            cutoff_date: Date before which to cleanup
            batch_size: Batch size for processing
            
        Returns:
            Number of cleaned up records
        """
        count = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.created_at < cutoff_date
        ).count()
        
        # TODO: Implement actual archival or deletion
        
        return count