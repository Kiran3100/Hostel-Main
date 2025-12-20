"""
Admin Activity Service

Tracks and analyzes admin activities including actions, decisions,
performance metrics, and behavioral analytics.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, desc

from app.models.admin.admin_user import AdminUser
from app.models.admin.admin_hostel_assignment import AdminHostelAssignment
from app.repositories.admin.admin_user_repository import AdminUserRepository
from app.repositories.admin.admin_hostel_assignment_repository import AdminHostelAssignmentRepository
from app.core.exceptions import EntityNotFoundError, ValidationError


class AdminActivityService:
    """
    Activity tracking and analytics service with:
    - Action logging and tracking
    - Performance metrics calculation
    - Behavioral pattern analysis
    - Productivity analytics
    - Engagement scoring
    """

    def __init__(self, db: Session):
        self.db = db
        self.admin_repo = AdminUserRepository(db)
        self.assignment_repo = AdminHostelAssignmentRepository(db)

    # ==================== ACTIVITY TRACKING ====================

    async def track_activity(
        self,
        admin_id: UUID,
        activity_type: str,
        hostel_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        action_details: Optional[Dict] = None,
        is_decision: bool = False,
        session_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Track admin activity with comprehensive metadata.
        
        Args:
            admin_id: Admin performing activity
            activity_type: Type of activity (view, create, update, etc.)
            hostel_id: Hostel context
            entity_type: Entity being acted upon
            entity_id: Specific entity ID
            action_details: Additional action metadata
            is_decision: Whether this is a decision action
            session_id: Session ID for tracking
            
        Returns:
            Activity tracking confirmation
        """
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        # Update admin last active
        admin.last_active_at = datetime.utcnow()

        # Update assignment metrics if hostel context
        if hostel_id:
            assignment = await self.assignment_repo.find_assignment(admin_id, hostel_id)
            if assignment:
                await self.assignment_repo.update_activity_metrics(
                    assignment_id=assignment.id,
                    actions_performed=1,
                    decisions_made=1 if is_decision else 0
                )

        # Create activity log entry
        # This would typically go to a separate ActivityLog table
        # For now, we'll just return confirmation
        activity_log = {
            'admin_id': str(admin_id),
            'activity_type': activity_type,
            'hostel_id': str(hostel_id) if hostel_id else None,
            'entity_type': entity_type,
            'entity_id': str(entity_id) if entity_id else None,
            'action_details': action_details or {},
            'is_decision': is_decision,
            'session_id': str(session_id) if session_id else None,
            'timestamp': datetime.utcnow()
        }

        await self.db.commit()
        return activity_log

    async def track_bulk_activity(
        self,
        admin_id: UUID,
        activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Track multiple activities in bulk."""
        results = {
            'tracked': 0,
            'failed': 0,
            'activities': []
        }

        for activity_data in activities:
            try:
                log = await self.track_activity(
                    admin_id=admin_id,
                    **activity_data
                )
                results['activities'].append(log)
                results['tracked'] += 1
            except Exception as e:
                results['failed'] += 1

        return results

    # ==================== PERFORMANCE METRICS ====================

    async def get_admin_performance_metrics(
        self,
        admin_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics.
        
        Includes:
        - Activity counts
        - Decision velocity
        - Response times
        - Engagement scores
        - Productivity metrics
        """
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        # Get base performance metrics
        base_metrics = await self.admin_repo.get_admin_performance_metrics(
            admin_id,
            period_days=(end_date - start_date).days
        )

        # Get assignment-level metrics
        assignments = await self.assignment_repo.get_admin_assignments(admin_id)
        
        assignment_metrics = {
            'total_assignments': len(assignments),
            'active_assignments': len([a for a in assignments if a.is_active]),
            'total_actions': sum(a.actions_performed for a in assignments),
            'total_decisions': sum(a.decisions_made for a in assignments),
            'avg_actions_per_hostel': 0,
            'avg_decisions_per_hostel': 0
        }

        if assignment_metrics['active_assignments'] > 0:
            assignment_metrics['avg_actions_per_hostel'] = (
                assignment_metrics['total_actions'] / 
                assignment_metrics['active_assignments']
            )
            assignment_metrics['avg_decisions_per_hostel'] = (
                assignment_metrics['total_decisions'] / 
                assignment_metrics['active_assignments']
            )

        # Calculate engagement score
        engagement_score = await self._calculate_engagement_score(
            admin_id,
            start_date,
            end_date
        )

        # Calculate productivity score
        productivity_score = await self._calculate_productivity_score(
            admin_id,
            assignments
        )

        return {
            'admin_id': str(admin_id),
            'period': {
                'start': start_date,
                'end': end_date,
                'days': (end_date - start_date).days
            },
            'base_metrics': base_metrics,
            'assignment_metrics': assignment_metrics,
            'engagement_score': engagement_score,
            'productivity_score': productivity_score,
            'overall_performance_score': (
                engagement_score * 0.4 + productivity_score * 0.6
            )
        }

    async def _calculate_engagement_score(
        self,
        admin_id: UUID,
        start_date: date,
        end_date: date
    ) -> float:
        """
        Calculate engagement score (0-100).
        
        Based on:
        - Login frequency
        - Session duration
        - Activity consistency
        """
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            return 0.0

        period_days = (end_date - start_date).days
        if period_days == 0:
            return 0.0

        # Login frequency score (0-40 points)
        sessions = await self.admin_repo._get_recent_sessions(
            admin_id,
            hours=period_days * 24
        )
        logins_per_day = len(sessions) / period_days
        login_score = min(logins_per_day * 20, 40)

        # Session duration score (0-30 points)
        if sessions:
            avg_duration = sum(s.duration_seconds for s in sessions) / len(sessions)
            # Ideal session: 30-60 minutes
            if 1800 <= avg_duration <= 3600:
                duration_score = 30
            elif avg_duration < 1800:
                duration_score = (avg_duration / 1800) * 30
            else:
                duration_score = max(30 - ((avg_duration - 3600) / 3600) * 10, 10)
        else:
            duration_score = 0

        # Consistency score (0-30 points)
        # Based on how regularly admin logs in
        active_days = len(set(s.started_at.date() for s in sessions))
        consistency_score = (active_days / period_days) * 30

        return login_score + duration_score + consistency_score

    async def _calculate_productivity_score(
        self,
        admin_id: UUID,
        assignments: List[AdminHostelAssignment]
    ) -> float:
        """
        Calculate productivity score (0-100).
        
        Based on:
        - Actions per session
        - Decision making rate
        - Assignment efficiency
        """
        if not assignments:
            return 0.0

        total_actions = sum(a.actions_performed for a in assignments)
        total_decisions = sum(a.decisions_made for a in assignments)
        total_sessions = sum(a.access_count for a in assignments)

        if total_sessions == 0:
            return 0.0

        # Actions per session score (0-40 points)
        actions_per_session = total_actions / total_sessions
        action_score = min(actions_per_session * 5, 40)

        # Decision making score (0-30 points)
        decisions_per_session = total_decisions / total_sessions
        decision_score = min(decisions_per_session * 10, 30)

        # Assignment efficiency score (0-30 points)
        # Based on time spent vs actions performed
        total_time = sum(a.total_session_time_minutes for a in assignments)
        if total_time > 0:
            actions_per_hour = (total_actions / total_time) * 60
            efficiency_score = min(actions_per_hour * 3, 30)
        else:
            efficiency_score = 0

        return action_score + decision_score + efficiency_score

    # ==================== ACTIVITY ANALYTICS ====================

    async def get_activity_summary(
        self,
        admin_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get activity summary for admin."""
        # This would query an ActivityLog table
        # For now, simplified based on assignment metrics
        
        assignments = await self.assignment_repo.get_admin_assignments(admin_id)
        
        return {
            'admin_id': str(admin_id),
            'period_days': period_days,
            'total_actions': sum(a.actions_performed for a in assignments),
            'total_decisions': sum(a.decisions_made for a in assignments),
            'total_session_time_minutes': sum(
                a.total_session_time_minutes for a in assignments
            ),
            'hostels_accessed': len([a for a in assignments if a.access_count > 0]),
            'most_active_hostel': self._get_most_active_hostel(assignments)
        }

    def _get_most_active_hostel(
        self,
        assignments: List[AdminHostelAssignment]
    ) -> Optional[Dict[str, Any]]:
        """Determine most active hostel."""
        if not assignments:
            return None

        most_active = max(assignments, key=lambda a: a.actions_performed)
        
        return {
            'hostel_id': str(most_active.hostel_id),
            'hostel_name': most_active.hostel.name if most_active.hostel else None,
            'actions_performed': most_active.actions_performed,
            'decisions_made': most_active.decisions_made
        }

    async def get_activity_trends(
        self,
        admin_id: UUID,
        metric: str = 'actions',
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get activity trends over time.
        
        Args:
            admin_id: Admin ID
            metric: Metric to trend (actions, decisions, sessions)
            days: Number of days
        """
        # This would query daily activity aggregates
        # Simplified for now
        
        trends = []
        start_date = date.today() - timedelta(days=days)
        
        for i in range(days):
            trend_date = start_date + timedelta(days=i)
            trends.append({
                'date': trend_date,
                'value': 0,  # Would be actual count from ActivityLog
                'metric': metric
            })

        return trends

    async def compare_admin_performance(
        self,
        admin_id_1: UUID,
        admin_id_2: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Compare performance between two admins."""
        metrics1 = await self.get_admin_performance_metrics(
            admin_id_1,
            start_date=date.today() - timedelta(days=period_days),
            end_date=date.today()
        )
        
        metrics2 = await self.get_admin_performance_metrics(
            admin_id_2,
            start_date=date.today() - timedelta(days=period_days),
            end_date=date.today()
        )

        return {
            'admin_1': {
                'admin_id': str(admin_id_1),
                'engagement_score': metrics1['engagement_score'],
                'productivity_score': metrics1['productivity_score'],
                'total_actions': metrics1['assignment_metrics']['total_actions']
            },
            'admin_2': {
                'admin_id': str(admin_id_2),
                'engagement_score': metrics2['engagement_score'],
                'productivity_score': metrics2['productivity_score'],
                'total_actions': metrics2['assignment_metrics']['total_actions']
            },
            'comparison': {
                'engagement_diff': metrics1['engagement_score'] - metrics2['engagement_score'],
                'productivity_diff': metrics1['productivity_score'] - metrics2['productivity_score'],
                'actions_diff': (
                    metrics1['assignment_metrics']['total_actions'] - 
                    metrics2['assignment_metrics']['total_actions']
                )
            }
        }

    # ==================== BEHAVIORAL ANALYTICS ====================

    async def analyze_work_patterns(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze admin work patterns.
        
        Includes:
        - Peak activity hours
        - Work distribution
        - Break patterns
        - Consistency metrics
        """
        sessions = await self.admin_repo._get_recent_sessions(
            admin_id,
            hours=days * 24
        )

        if not sessions:
            return {
                'admin_id': str(admin_id),
                'has_data': False
            }

        # Analyze peak hours
        hour_distribution = {}
        for session in sessions:
            hour = session.started_at.hour
            hour_distribution[hour] = hour_distribution.get(hour, 0) + 1

        peak_hours = sorted(
            hour_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        # Analyze work consistency
        session_days = set(s.started_at.date() for s in sessions)
        consistency_percentage = (len(session_days) / days) * 100

        # Average session characteristics
        avg_session_duration = sum(
            s.duration_seconds for s in sessions
        ) / len(sessions) / 60  # Convert to minutes

        return {
            'admin_id': str(admin_id),
            'has_data': True,
            'period_days': days,
            'total_sessions': len(sessions),
            'active_days': len(session_days),
            'consistency_percentage': round(consistency_percentage, 2),
            'peak_hours': [
                {'hour': h, 'session_count': c} for h, c in peak_hours
            ],
            'avg_session_duration_minutes': round(avg_session_duration, 2),
            'work_pattern': self._classify_work_pattern(
                hour_distribution,
                consistency_percentage
            )
        }

    def _classify_work_pattern(
        self,
        hour_distribution: Dict[int, int],
        consistency: float
    ) -> str:
        """Classify admin's work pattern."""
        if not hour_distribution:
            return 'insufficient_data'

        # Find primary work hours
        peak_hour = max(hour_distribution.items(), key=lambda x: x[1])[0]

        if consistency >= 80:
            if 9 <= peak_hour <= 17:
                return 'regular_business_hours'
            elif 6 <= peak_hour <= 9 or 17 <= peak_hour <= 20:
                return 'extended_hours'
            else:
                return 'irregular_hours'
        elif consistency >= 50:
            return 'moderate_consistency'
        else:
            return 'irregular_pattern'

    async def detect_anomalies(
        self,
        admin_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalous activity patterns.
        
        Flags unusual behaviors:
        - Sudden activity spikes
        - Prolonged inactivity
        - Unusual access times
        - Abnormal decision velocity
        """
        anomalies = []

        # Get baseline metrics
        assignments = await self.assignment_repo.get_admin_assignments(admin_id)
        sessions = await self.admin_repo._get_recent_sessions(admin_id, hours=days * 24)

        # Check for prolonged inactivity
        if sessions:
            last_session = max(sessions, key=lambda s: s.started_at)
            hours_since_last = (
                datetime.utcnow() - last_session.started_at
            ).total_seconds() / 3600

            if hours_since_last > 72:  # 3 days
                anomalies.append({
                    'type': 'prolonged_inactivity',
                    'severity': 'medium',
                    'hours_since_last_activity': round(hours_since_last, 2),
                    'message': f'No activity in {round(hours_since_last/24, 1)} days'
                })

        # Check for unusual access times
        night_sessions = [
            s for s in sessions 
            if s.started_at.hour < 6 or s.started_at.hour > 22
        ]
        
        if len(night_sessions) > len(sessions) * 0.3:  # >30% night sessions
            anomalies.append({
                'type': 'unusual_hours',
                'severity': 'low',
                'night_session_percentage': round(
                    len(night_sessions) / len(sessions) * 100, 2
                ),
                'message': 'High proportion of late-night activity'
            })

        # Check for decision velocity spikes
        if assignments:
            avg_decisions = sum(a.decisions_made for a in assignments) / len(assignments)
            
            for assignment in assignments:
                if assignment.decisions_made > avg_decisions * 3:
                    anomalies.append({
                        'type': 'decision_spike',
                        'severity': 'medium',
                        'hostel_id': str(assignment.hostel_id),
                        'decisions': assignment.decisions_made,
                        'average': round(avg_decisions, 2),
                        'message': f'Unusually high decision count in hostel'
                    })

        return anomalies

    # ==================== REPORTING ====================

    async def generate_activity_report(
        self,
        admin_id: UUID,
        start_date: date,
        end_date: date,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """Generate comprehensive activity report."""
        performance = await self.get_admin_performance_metrics(
            admin_id,
            start_date,
            end_date
        )

        work_patterns = await self.analyze_work_patterns(
            admin_id,
            days=(end_date - start_date).days
        )

        anomalies = await self.detect_anomalies(
            admin_id,
            days=(end_date - start_date).days
        )

        report = {
            'admin_id': str(admin_id),
            'report_period': {
                'start': start_date,
                'end': end_date,
                'days': (end_date - start_date).days
            },
            'performance_summary': {
                'engagement_score': performance['engagement_score'],
                'productivity_score': performance['productivity_score'],
                'overall_score': performance['overall_performance_score']
            },
            'work_patterns': work_patterns,
            'anomalies_detected': len(anomalies),
            'health_status': self._determine_health_status(
                performance,
                anomalies
            )
        }

        if include_details:
            report['detailed_metrics'] = performance
            report['anomaly_details'] = anomalies

        return report

    def _determine_health_status(
        self,
        performance: Dict[str, Any],
        anomalies: List[Dict[str, Any]]
    ) -> str:
        """Determine overall health status."""
        score = performance['overall_performance_score']
        high_severity_anomalies = len([
            a for a in anomalies 
            if a.get('severity') == 'high'
        ])

        if score >= 80 and high_severity_anomalies == 0:
            return 'excellent'
        elif score >= 60 and high_severity_anomalies <= 1:
            return 'good'
        elif score >= 40:
            return 'fair'
        else:
            return 'needs_attention'

    async def get_team_activity_summary(
        self,
        manager_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get activity summary for manager's team."""
        # Get team members
        from app.services.admin.admin_user_service import AdminUserService
        
        user_service = AdminUserService(self.db)
        team_members = await user_service.get_team_members(
            manager_id,
            include_indirect=False
        )

        team_metrics = []
        
        for member in team_members:
            metrics = await self.get_admin_performance_metrics(
                member.id,
                start_date=date.today() - timedelta(days=period_days),
                end_date=date.today()
            )
            
            team_metrics.append({
                'admin_id': str(member.id),
                'name': member.full_name,
                'engagement_score': metrics['engagement_score'],
                'productivity_score': metrics['productivity_score'],
                'total_actions': metrics['assignment_metrics']['total_actions']
            })

        # Calculate team averages
        if team_metrics:
            avg_engagement = sum(m['engagement_score'] for m in team_metrics) / len(team_metrics)
            avg_productivity = sum(m['productivity_score'] for m in team_metrics) / len(team_metrics)
        else:
            avg_engagement = 0
            avg_productivity = 0

        return {
            'manager_id': str(manager_id),
            'team_size': len(team_members),
            'period_days': period_days,
            'team_averages': {
                'engagement_score': round(avg_engagement, 2),
                'productivity_score': round(avg_productivity, 2)
            },
            'team_members': team_metrics,
            'top_performers': sorted(
                team_metrics,
                key=lambda x: x['productivity_score'],
                reverse=True
            )[:3],
            'needs_attention': [
                m for m in team_metrics
                if m['productivity_score'] < 40 or m['engagement_score'] < 40
            ]
        }