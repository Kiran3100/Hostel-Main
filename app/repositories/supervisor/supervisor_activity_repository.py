# app/repositories/supervisor/supervisor_activity_repository.py
"""
Supervisor Activity Repository - Activity tracking and analytics.

Handles comprehensive activity logging, session management,
productivity analysis, and performance insights.
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, distinct, case
from sqlalchemy.orm import Session, joinedload
from collections import defaultdict

from app.models.supervisor.supervisor_activity import (
    SupervisorActivity,
    SupervisorSession,
    ActivitySummary,
    ActivityMetric,
)
from app.models.supervisor.supervisor import Supervisor
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import ResourceNotFoundError, BusinessLogicError
from app.core1.logging import logger


class SupervisorActivityRepository(BaseRepository[SupervisorActivity]):
    """
    Supervisor activity repository for tracking and analytics.
    
    Manages detailed activity logging, session tracking,
    productivity analysis, and performance optimization.
    """
    
    def __init__(self, db: Session):
        """Initialize activity repository."""
        super().__init__(SupervisorActivity, db)
        self.db = db
    
    # ==================== Activity Logging ====================
    
    def log_activity(
        self,
        supervisor_id: str,
        hostel_id: str,
        action_type: str,
        action_category: str,
        action_description: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_type: Optional[str] = None,
        device_info: Optional[Dict] = None,
        response_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        impact_level: Optional[str] = None,
        affected_users_count: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> SupervisorActivity:
        """
        Log supervisor activity with comprehensive metadata.
        
        Args:
            supervisor_id: Supervisor ID
            hostel_id: Hostel ID
            action_type: Specific action performed
            action_category: Action category
            action_description: Human-readable description
            entity_type: Type of entity affected
            entity_id: ID of affected entity
            entity_name: Name of affected entity
            metadata: Additional action details
            ip_address: IP address
            user_agent: User agent string
            device_type: Device type
            device_info: Device information
            response_time_ms: Response time
            success: Success flag
            error_message: Error message if failed
            error_code: Error code if failed
            impact_level: Impact level
            affected_users_count: Number of users affected
            session_id: Session identifier
            
        Returns:
            Created activity log
        """
        try:
            activity = SupervisorActivity(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                action_type=action_type,
                action_category=action_category,
                action_description=action_description,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                metadata=metadata or {},
                ip_address=ip_address,
                user_agent=user_agent,
                device_type=device_type,
                device_info=device_info,
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message,
                error_code=error_code,
                impact_level=impact_level,
                affected_users_count=affected_users_count,
                session_id=session_id
            )
            
            self.db.add(activity)
            self.db.commit()
            self.db.refresh(activity)
            
            return activity
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error logging activity: {str(e)}")
            raise
    
    def get_activities(
        self,
        supervisor_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        action_type: Optional[str] = None,
        action_category: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SupervisorActivity]:
        """
        Get activities with comprehensive filters.
        
        Args:
            supervisor_id: Filter by supervisor
            hostel_id: Filter by hostel
            action_type: Filter by action type
            action_category: Filter by category
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            success: Filter by success status
            start_date: Start date filter
            end_date: End date filter
            session_id: Filter by session
            limit: Maximum results
            offset: Results offset
            
        Returns:
            List of activities
        """
        query = self.db.query(SupervisorActivity)
        
        if supervisor_id:
            query = query.filter(
                SupervisorActivity.supervisor_id == supervisor_id
            )
        
        if hostel_id:
            query = query.filter(
                SupervisorActivity.hostel_id == hostel_id
            )
        
        if action_type:
            query = query.filter(
                SupervisorActivity.action_type == action_type
            )
        
        if action_category:
            query = query.filter(
                SupervisorActivity.action_category == action_category
            )
        
        if entity_type:
            query = query.filter(
                SupervisorActivity.entity_type == entity_type
            )
        
        if entity_id:
            query = query.filter(
                SupervisorActivity.entity_id == entity_id
            )
        
        if success is not None:
            query = query.filter(
                SupervisorActivity.success == success
            )
        
        if start_date:
            query = query.filter(
                SupervisorActivity.created_at >= start_date
            )
        
        if end_date:
            query = query.filter(
                SupervisorActivity.created_at <= end_date
            )
        
        if session_id:
            query = query.filter(
                SupervisorActivity.session_id == session_id
            )
        
        return query.order_by(
            SupervisorActivity.created_at.desc()
        ).limit(limit).offset(offset).all()
    
    def get_activity_count(
        self,
        supervisor_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_category: Optional[str] = None
    ) -> int:
        """Get count of activities with filters."""
        query = self.db.query(func.count(SupervisorActivity.id))
        
        if supervisor_id:
            query = query.filter(
                SupervisorActivity.supervisor_id == supervisor_id
            )
        
        if hostel_id:
            query = query.filter(
                SupervisorActivity.hostel_id == hostel_id
            )
        
        if start_date:
            query = query.filter(
                SupervisorActivity.created_at >= start_date
            )
        
        if end_date:
            query = query.filter(
                SupervisorActivity.created_at <= end_date
            )
        
        if action_category:
            query = query.filter(
                SupervisorActivity.action_category == action_category
            )
        
        return query.scalar()
    
    def get_failed_activities(
        self,
        supervisor_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[SupervisorActivity]:
        """Get failed activities for error analysis."""
        query = self.db.query(SupervisorActivity).filter(
            SupervisorActivity.success == False
        )
        
        if supervisor_id:
            query = query.filter(
                SupervisorActivity.supervisor_id == supervisor_id
            )
        
        if start_date:
            query = query.filter(
                SupervisorActivity.created_at >= start_date
            )
        
        if end_date:
            query = query.filter(
                SupervisorActivity.created_at <= end_date
            )
        
        return query.order_by(
            SupervisorActivity.created_at.desc()
        ).limit(limit).all()
    
    # ==================== Session Management ====================
    
    def create_session(
        self,
        supervisor_id: str,
        user_id: str,
        session_id: str,
        session_token: str,
        ip_address: str,
        user_agent: str,
        device_type: str = "desktop",
        device_info: Optional[Dict] = None,
        device_fingerprint: Optional[str] = None,
        location: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None
    ) -> SupervisorSession:
        """
        Create new supervisor session.
        
        Args:
            supervisor_id: Supervisor ID
            user_id: User ID
            session_id: Unique session identifier
            session_token: Session token (hashed)
            ip_address: Login IP address
            user_agent: User agent string
            device_type: Device type
            device_info: Device information
            device_fingerprint: Device fingerprint
            location: Geographic location
            country: Country
            city: City
            
        Returns:
            Created session
        """
        try:
            session = SupervisorSession(
                supervisor_id=supervisor_id,
                user_id=user_id,
                session_id=session_id,
                session_token=session_token,
                ip_address=ip_address,
                user_agent=user_agent,
                device_type=device_type,
                device_info=device_info,
                device_fingerprint=device_fingerprint,
                location=location,
                country=country,
                city=city,
                is_active=True
            )
            
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"Created session for supervisor {supervisor_id}")
            return session
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating session: {str(e)}")
            raise
    
    def get_session(
        self,
        session_id: str
    ) -> Optional[SupervisorSession]:
        """Get session by session ID."""
        return self.db.query(SupervisorSession).filter(
            SupervisorSession.session_id == session_id
        ).first()
    
    def get_active_sessions(
        self,
        supervisor_id: str
    ) -> List[SupervisorSession]:
        """Get all active sessions for supervisor."""
        return self.db.query(SupervisorSession).filter(
            and_(
                SupervisorSession.supervisor_id == supervisor_id,
                SupervisorSession.is_active == True
            )
        ).order_by(
            SupervisorSession.login_at.desc()
        ).all()
    
    def update_session_activity(
        self,
        session_id: str
    ) -> Optional[SupervisorSession]:
        """Update session last activity timestamp."""
        session = self.get_session(session_id)
        if session and session.is_active:
            session.last_activity = datetime.utcnow()
            session.actions_count += 1
            self.db.commit()
            self.db.refresh(session)
        
        return session
    
    def end_session(
        self,
        session_id: str,
        logout_reason: str = "manual"
    ) -> Optional[SupervisorSession]:
        """End supervisor session."""
        session = self.get_session(session_id)
        if session and session.is_active:
            session.is_active = False
            session.logout_at = datetime.utcnow()
            session.logout_reason = logout_reason
            
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"Ended session {session_id}")
        
        return session
    
    def end_all_sessions(
        self,
        supervisor_id: str,
        logout_reason: str = "forced"
    ) -> int:
        """End all active sessions for supervisor."""
        sessions = self.get_active_sessions(supervisor_id)
        
        for session in sessions:
            self.end_session(session.session_id, logout_reason)
        
        return len(sessions)
    
    def detect_suspicious_sessions(
        self,
        supervisor_id: str
    ) -> List[SupervisorSession]:
        """Detect potentially suspicious sessions."""
        sessions = self.db.query(SupervisorSession).filter(
            and_(
                SupervisorSession.supervisor_id == supervisor_id,
                SupervisorSession.is_active == True
            )
        ).all()
        
        suspicious = []
        
        if len(sessions) > 3:
            # Too many concurrent sessions
            for session in sessions:
                session.is_suspicious = True
                session.security_notes = "Multiple concurrent sessions detected"
                suspicious.append(session)
        
        # Check for geographically dispersed logins
        locations = set(s.location for s in sessions if s.location)
        if len(locations) > 2:
            for session in sessions:
                session.is_suspicious = True
                session.security_notes = "Geographically dispersed sessions"
                if session not in suspicious:
                    suspicious.append(session)
        
        if suspicious:
            self.db.commit()
        
        return suspicious
    
    # ==================== Activity Summaries ====================
    
    def generate_activity_summary(
        self,
        supervisor_id: str,
        hostel_id: str,
        period_start: datetime,
        period_end: datetime,
        period_type: str = "daily"
    ) -> ActivitySummary:
        """
        Generate activity summary for period.
        
        Args:
            supervisor_id: Supervisor ID
            hostel_id: Hostel ID
            period_start: Period start
            period_end: Period end
            period_type: Period type (hourly, daily, weekly, monthly)
            
        Returns:
            Activity summary
        """
        # Get activities for period
        activities = self.get_activities(
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            start_date=period_start,
            end_date=period_end,
            limit=10000
        )
        
        total_actions = len(activities)
        successful = sum(1 for a in activities if a.success)
        failed = total_actions - successful
        
        # Get unique action types
        unique_types = len(set(a.action_type for a in activities))
        
        # Group by category
        actions_by_category = defaultdict(int)
        actions_by_type = defaultdict(int)
        
        for activity in activities:
            actions_by_category[activity.action_category] += 1
            actions_by_type[activity.action_type] += 1
        
        # Calculate average response time
        response_times = [
            a.response_time_ms for a in activities
            if a.response_time_ms is not None
        ]
        avg_response_time = (
            int(sum(response_times) / len(response_times))
            if response_times else None
        )
        
        # Calculate success rate
        success_rate = (successful / total_actions * 100) if total_actions > 0 else 100.0
        
        # Find peak activity hour
        hour_counts = defaultdict(int)
        for activity in activities:
            hour_counts[activity.created_at.hour] += 1
        
        peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None
        
        # Find most common action
        most_common = max(
            actions_by_type.items(),
            key=lambda x: x[1]
        )[0] if actions_by_type else None
        
        # Get session info
        sessions = self.db.query(SupervisorSession).filter(
            and_(
                SupervisorSession.supervisor_id == supervisor_id,
                SupervisorSession.login_at >= period_start,
                SupervisorSession.login_at <= period_end
            )
        ).all()
        
        sessions_count = len(sessions)
        total_session_time = sum(
            s.session_duration_minutes or 0
            for s in sessions
        )
        
        # Create or update summary
        existing = self.db.query(ActivitySummary).filter(
            and_(
                ActivitySummary.supervisor_id == supervisor_id,
                ActivitySummary.hostel_id == hostel_id,
                ActivitySummary.period_start == period_start,
                ActivitySummary.period_end == period_end,
                ActivitySummary.period_type == period_type
            )
        ).first()
        
        if existing:
            summary = existing
        else:
            summary = ActivitySummary(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type
            )
            self.db.add(summary)
        
        # Update fields
        summary.total_actions = total_actions
        summary.successful_actions = successful
        summary.failed_actions = failed
        summary.unique_action_types = unique_types
        summary.actions_by_category = dict(actions_by_category)
        summary.actions_by_type = dict(actions_by_type)
        summary.average_response_time_ms = avg_response_time
        summary.success_rate = success_rate
        summary.peak_hour = peak_hour
        summary.most_common_action = most_common
        summary.sessions_count = sessions_count
        summary.total_session_time_minutes = total_session_time
        
        self.db.commit()
        self.db.refresh(summary)
        
        return summary
    
    def get_activity_summaries(
        self,
        supervisor_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        period_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 30
    ) -> List[ActivitySummary]:
        """Get activity summaries with filters."""
        query = self.db.query(ActivitySummary)
        
        if supervisor_id:
            query = query.filter(
                ActivitySummary.supervisor_id == supervisor_id
            )
        
        if hostel_id:
            query = query.filter(
                ActivitySummary.hostel_id == hostel_id
            )
        
        if period_type:
            query = query.filter(
                ActivitySummary.period_type == period_type
            )
        
        if start_date:
            query = query.filter(
                ActivitySummary.period_start >= start_date
            )
        
        if end_date:
            query = query.filter(
                ActivitySummary.period_end <= end_date
            )
        
        return query.order_by(
            ActivitySummary.period_start.desc()
        ).limit(limit).all()
    
    # ==================== Activity Metrics ====================
    
    def calculate_activity_metrics(
        self,
        supervisor_id: str,
        metric_date: date,
        period_type: str = "daily"
    ) -> ActivityMetric:
        """
        Calculate comprehensive activity metrics.
        
        Args:
            supervisor_id: Supervisor ID
            metric_date: Metric date
            period_type: Period type (daily, weekly, monthly)
            
        Returns:
            Activity metric
        """
        # Determine date range based on period type
        if period_type == "daily":
            start_date = datetime.combine(metric_date, datetime.min.time())
            end_date = datetime.combine(metric_date, datetime.max.time())
        elif period_type == "weekly":
            start_date = datetime.combine(
                metric_date - timedelta(days=metric_date.weekday()),
                datetime.min.time()
            )
            end_date = start_date + timedelta(days=7)
        elif period_type == "monthly":
            start_date = datetime.combine(
                metric_date.replace(day=1),
                datetime.min.time()
            )
            next_month = metric_date.replace(day=28) + timedelta(days=4)
            end_date = datetime.combine(
                next_month.replace(day=1) - timedelta(days=1),
                datetime.max.time()
            )
        else:
            start_date = datetime.combine(metric_date, datetime.min.time())
            end_date = datetime.combine(metric_date, datetime.max.time())
        
        # Get activities
        activities = self.get_activities(
            supervisor_id=supervisor_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        total_actions = len(activities)
        successful = sum(1 for a in activities if a.success)
        unique_types = len(set(a.action_type for a in activities))
        
        # Calculate active days
        active_days = len(set(
            a.created_at.date() for a in activities
        ))
        
        # Performance metrics
        success_rate = (successful / total_actions * 100) if total_actions > 0 else 100.0
        
        response_times = [
            a.response_time_ms for a in activities
            if a.response_time_ms is not None
        ]
        avg_response_time = (
            int(sum(response_times) / len(response_times))
            if response_times else None
        )
        
        # Efficiency metrics
        actions_per_day = total_actions / active_days if active_days > 0 else 0
        
        sessions = self.db.query(SupervisorSession).filter(
            and_(
                SupervisorSession.supervisor_id == supervisor_id,
                SupervisorSession.login_at >= start_date,
                SupervisorSession.login_at <= end_date
            )
        ).all()
        
        sessions_count = len(sessions)
        actions_per_session = (
            total_actions / sessions_count if sessions_count > 0 else 0
        )
        
        # Category distribution
        actions_by_category = defaultdict(int)
        for activity in activities:
            actions_by_category[activity.action_category] += 1
        
        # Calculate activity score (0-100)
        activity_score = min(
            (total_actions / 50) * 40 +  # Volume score (max 40)
            (success_rate / 100) * 30 +   # Quality score (max 30)
            (min(actions_per_day / 20, 1)) * 30,  # Consistency score (max 30)
            100
        )
        
        # Determine productivity level
        if activity_score >= 80:
            productivity = "excellent"
        elif activity_score >= 60:
            productivity = "good"
        elif activity_score >= 40:
            productivity = "average"
        else:
            productivity = "poor"
        
        # Create or update metric
        existing = self.db.query(ActivityMetric).filter(
            and_(
                ActivityMetric.supervisor_id == supervisor_id,
                ActivityMetric.metric_date == metric_date,
                ActivityMetric.period_type == period_type
            )
        ).first()
        
        if existing:
            metric = existing
        else:
            metric = ActivityMetric(
                supervisor_id=supervisor_id,
                metric_date=metric_date,
                period_type=period_type
            )
            self.db.add(metric)
        
        # Update fields
        metric.total_actions = total_actions
        metric.unique_action_types = unique_types
        metric.active_days = active_days
        metric.overall_success_rate = success_rate
        metric.average_response_time_ms = avg_response_time
        metric.actions_per_day = actions_per_day
        metric.actions_per_session = actions_per_session
        metric.actions_by_category = dict(actions_by_category)
        metric.activity_score = activity_score
        metric.productivity_level = productivity
        
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    def get_activity_metrics(
        self,
        supervisor_id: Optional[str] = None,
        period_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        productivity_level: Optional[str] = None,
        limit: int = 30
    ) -> List[ActivityMetric]:
        """Get activity metrics with filters."""
        query = self.db.query(ActivityMetric)
        
        if supervisor_id:
            query = query.filter(
                ActivityMetric.supervisor_id == supervisor_id
            )
        
        if period_type:
            query = query.filter(
                ActivityMetric.period_type == period_type
            )
        
        if start_date:
            query = query.filter(
                ActivityMetric.metric_date >= start_date
            )
        
        if end_date:
            query = query.filter(
                ActivityMetric.metric_date <= end_date
            )
        
        if productivity_level:
            query = query.filter(
                ActivityMetric.productivity_level == productivity_level
            )
        
        return query.order_by(
            ActivityMetric.metric_date.desc()
        ).limit(limit).all()
    
    # ==================== Analytics ====================
    
    def get_activity_trends(
        self,
        supervisor_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get activity trends over specified days.
        
        Args:
            supervisor_id: Supervisor ID
            days: Number of days to analyze
            
        Returns:
            Trend analysis dictionary
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        activities = self.get_activities(
            supervisor_id=supervisor_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        # Daily activity counts
        daily_counts = defaultdict(int)
        for activity in activities:
            day = activity.created_at.date()
            daily_counts[day] += 1
        
        # Calculate trend
        dates = sorted(daily_counts.keys())
        if len(dates) >= 2:
            first_half = dates[:len(dates)//2]
            second_half = dates[len(dates)//2:]
            
            first_avg = sum(daily_counts[d] for d in first_half) / len(first_half)
            second_avg = sum(daily_counts[d] for d in second_half) / len(second_half)
            
            if second_avg > first_avg * 1.1:
                trend = "increasing"
            elif second_avg < first_avg * 0.9:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            'period_days': days,
            'total_activities': len(activities),
            'daily_average': len(activities) / days if days > 0 else 0,
            'trend': trend,
            'daily_counts': dict(daily_counts)
        }
    
    def get_productivity_comparison(
        self,
        supervisor_ids: List[str],
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """
        Compare productivity across multiple supervisors.
        
        Args:
            supervisor_ids: List of supervisor IDs
            start_date: Start date
            end_date: End date
            
        Returns:
            List of productivity comparisons
        """
        comparisons = []
        
        for supervisor_id in supervisor_ids:
            metrics = self.get_activity_metrics(
                supervisor_id=supervisor_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if metrics:
                avg_score = sum(m.activity_score for m in metrics) / len(metrics)
                avg_actions = sum(m.total_actions for m in metrics) / len(metrics)
                avg_success_rate = sum(
                    m.overall_success_rate for m in metrics
                ) / len(metrics)
                
                comparisons.append({
                    'supervisor_id': supervisor_id,
                    'average_activity_score': round(avg_score, 2),
                    'average_actions': round(avg_actions, 2),
                    'average_success_rate': round(avg_success_rate, 2),
                    'productivity_level': metrics[0].productivity_level
                })
        
        # Sort by activity score
        comparisons.sort(key=lambda x: x['average_activity_score'], reverse=True)
        
        return comparisons