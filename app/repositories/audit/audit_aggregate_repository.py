"""
Audit aggregate repository for cross-functional audit analytics.

Provides aggregated insights, trend analysis, and comprehensive
reporting across all audit data sources.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, desc, case
from sqlalchemy.orm import Session

from app.models.audit import (
    AuditLog,
    EntityChangeLog,
    SupervisorActivityLog,
    AdminOverrideLog
)
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import AuditActionCategory


class AuditAggregateRepository(BaseRepository):
    """
    Repository for aggregated audit analytics and reporting.
    
    Provides cross-functional insights combining data from all
    audit sources for comprehensive analysis and reporting.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, AuditLog)  # Use AuditLog as base model
    
    # ==================== Dashboard Metrics ====================
    
    def get_dashboard_metrics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard metrics for audit overview.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Period start (defaults to 30 days ago)
            end_date: Period end (defaults to now)
            
        Returns:
            Dashboard metrics dictionary
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Audit logs summary
        audit_query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        if hostel_id:
            audit_query = audit_query.filter(AuditLog.hostel_id == hostel_id)
        
        total_actions = audit_query.count()
        failed_actions = audit_query.filter(AuditLog.status == 'failure').count()
        sensitive_actions = audit_query.filter(AuditLog.is_sensitive == True).count()
        
        # Entity changes summary
        changes_query = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.created_at <= end_date
        )
        
        total_changes = changes_query.count()
        sensitive_changes = changes_query.filter(
            or_(
                EntityChangeLog.is_sensitive == True,
                EntityChangeLog.is_pii == True
            )
        ).count()
        
        # Supervisor activities summary
        activities_query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        )
        if hostel_id:
            activities_query = activities_query.filter(SupervisorActivityLog.hostel_id == hostel_id)
        
        total_activities = activities_query.count()
        failed_activities = activities_query.filter(
            SupervisorActivityLog.status == 'failed'
        ).count()
        
        # Admin overrides summary
        overrides_query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.created_at >= start_date,
            AdminOverrideLog.created_at <= end_date
        )
        if hostel_id:
            overrides_query = overrides_query.filter(AdminOverrideLog.hostel_id == hostel_id)
        
        total_overrides = overrides_query.count()
        pending_approvals = overrides_query.filter(
            AdminOverrideLog.requires_approval == True,
            AdminOverrideLog.approved_at.is_(None)
        ).count()
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'hostel_id': str(hostel_id) if hostel_id else 'all',
            'audit_logs': {
                'total': total_actions,
                'failed': failed_actions,
                'sensitive': sensitive_actions,
                'failure_rate': round(failed_actions / total_actions * 100, 2) if total_actions else 0
            },
            'entity_changes': {
                'total': total_changes,
                'sensitive': sensitive_changes,
                'sensitive_percentage': round(sensitive_changes / total_changes * 100, 2) if total_changes else 0
            },
            'supervisor_activities': {
                'total': total_activities,
                'failed': failed_activities,
                'success_rate': round((total_activities - failed_activities) / total_activities * 100, 2) if total_activities else 0
            },
            'admin_overrides': {
                'total': total_overrides,
                'pending_approvals': pending_approvals,
                'approval_rate': round((total_overrides - pending_approvals) / total_overrides * 100, 2) if total_overrides else 0
            }
        }
    
    # ==================== Trend Analysis ====================
    
    def get_activity_trends(
        self,
        hostel_id: Optional[UUID] = None,
        days: int = 30,
        group_by: str = 'day'  # 'hour', 'day', 'week'
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get activity trends across all audit sources.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            group_by: Time grouping interval
            
        Returns:
            Trends dictionary with data for each audit source
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()
        
        # Determine time truncation
        if group_by == 'hour':
            time_trunc = func.date_trunc('hour', AuditLog.created_at)
        elif group_by == 'day':
            time_trunc = func.date_trunc('day', AuditLog.created_at)
        elif group_by == 'week':
            time_trunc = func.date_trunc('week', AuditLog.created_at)
        else:
            time_trunc = func.date_trunc('day', AuditLog.created_at)
        
        # Audit logs trend
        audit_trend = self.session.query(
            time_trunc.label('time_bucket'),
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        if hostel_id:
            audit_trend = audit_trend.filter(AuditLog.hostel_id == hostel_id)
        audit_trend = audit_trend.group_by('time_bucket').order_by('time_bucket').all()
        
        # Entity changes trend
        changes_trend = self.session.query(
            func.date_trunc(group_by, EntityChangeLog.created_at).label('time_bucket'),
            func.count(EntityChangeLog.id).label('count')
        ).filter(
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.created_at <= end_date
        ).group_by('time_bucket').order_by('time_bucket').all()
        
        # Supervisor activities trend
        activities_trend_query = self.session.query(
            func.date_trunc(group_by, SupervisorActivityLog.created_at).label('time_bucket'),
            func.count(SupervisorActivityLog.id).label('count')
        ).filter(
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        )
        if hostel_id:
            activities_trend_query = activities_trend_query.filter(
                SupervisorActivityLog.hostel_id == hostel_id
            )
        activities_trend = activities_trend_query.group_by('time_bucket').order_by('time_bucket').all()
        
        # Admin overrides trend
        overrides_trend_query = self.session.query(
            func.date_trunc(group_by, AdminOverrideLog.created_at).label('time_bucket'),
            func.count(AdminOverrideLog.id).label('count')
        ).filter(
            AdminOverrideLog.created_at >= start_date,
            AdminOverrideLog.created_at <= end_date
        )
        if hostel_id:
            overrides_trend_query = overrides_trend_query.filter(
                AdminOverrideLog.hostel_id == hostel_id
            )
        overrides_trend = overrides_trend_query.group_by('time_bucket').order_by('time_bucket').all()
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'grouping': group_by
            },
            'audit_logs': [
                {'timestamp': bucket.isoformat(), 'count': count}
                for bucket, count in audit_trend
            ],
            'entity_changes': [
                {'timestamp': bucket.isoformat(), 'count': count}
                for bucket, count in changes_trend
            ],
            'supervisor_activities': [
                {'timestamp': bucket.isoformat(), 'count': count}
                for bucket, count in activities_trend
            ],
            'admin_overrides': [
                {'timestamp': bucket.isoformat(), 'count': count}
                for bucket, count in overrides_trend
            ]
        }
    
    # ==================== User Activity Analysis ====================
    
    def get_user_comprehensive_activity(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get comprehensive activity analysis for a user across all audit sources.
        
        Args:
            user_id: User ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            Comprehensive activity dictionary
        """
        # Audit logs
        audit_logs = self.session.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        ).all()
        
        # Entity changes
        entity_changes = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.changed_by_user_id == user_id,
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.created_at <= end_date
        ).all()
        
        # Supervisor activities (if user is supervisor)
        supervisor_activities = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.supervisor_id == user_id,
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        ).all()
        
        # Admin overrides (if user is admin)
        admin_overrides = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.admin_id == user_id,
            AdminOverrideLog.created_at >= start_date,
            AdminOverrideLog.created_at <= end_date
        ).all()
        
        # Calculate activity scores
        total_activities = (
            len(audit_logs) +
            len(entity_changes) +
            len(supervisor_activities) +
            len(admin_overrides)
        )
        
        # Action categories breakdown
        category_breakdown = {}
        for log in audit_logs:
            cat = log.action_category.value
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        
        # Most active times (hour of day)
        hour_distribution = {}
        for log in audit_logs:
            hour = log.created_at.hour
            hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
        
        # Sensitive data access
        sensitive_access_count = sum(1 for log in audit_logs if log.is_sensitive)
        
        return {
            'user_id': str(user_id),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_activities': total_activities,
            'breakdown': {
                'audit_actions': len(audit_logs),
                'entity_changes': len(entity_changes),
                'supervisor_activities': len(supervisor_activities),
                'admin_overrides': len(admin_overrides)
            },
            'action_categories': category_breakdown,
            'activity_by_hour': hour_distribution,
            'sensitive_data_access': {
                'count': sensitive_access_count,
                'percentage': round(sensitive_access_count / len(audit_logs) * 100, 2) if audit_logs else 0
            },
            'average_daily_activity': round(total_activities / max((end_date - start_date).days, 1), 2)
        }
    
    # ==================== Security Analysis ====================
    
    def get_security_overview(
        self,
        hostel_id: Optional[UUID] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get comprehensive security overview from all audit sources.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Security overview dictionary
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()
        
        # Failed authentication attempts (from audit logs)
        failed_auth_query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.action_category == AuditActionCategory.SECURITY,
            AuditLog.status == 'failure'
        )
        if hostel_id:
            failed_auth_query = failed_auth_query.filter(AuditLog.hostel_id == hostel_id)
        failed_auth = failed_auth_query.count()
        
        # Sensitive data access
        sensitive_access_query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.is_sensitive == True
        )
        if hostel_id:
            sensitive_access_query = sensitive_access_query.filter(AuditLog.hostel_id == hostel_id)
        sensitive_access = sensitive_access_query.count()
        
        # Sensitive entity changes
        sensitive_changes = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.created_at >= start_date,
            or_(
                EntityChangeLog.is_sensitive == True,
                EntityChangeLog.is_pii == True
            )
        ).count()
        
        # High-impact admin overrides
        high_impact_overrides_query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.created_at >= start_date,
            AdminOverrideLog.impact_score >= 75
        )
        if hostel_id:
            high_impact_overrides_query = high_impact_overrides_query.filter(
                AdminOverrideLog.hostel_id == hostel_id
            )
        high_impact_overrides = high_impact_overrides_query.count()
        
        # Unique IPs with failed actions
        failed_ips = self.session.query(
            func.distinct(AuditLog.ip_address)
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.status == 'failure',
            AuditLog.ip_address.isnot(None)
        )
        if hostel_id:
            failed_ips = failed_ips.filter(AuditLog.hostel_id == hostel_id)
        unique_failed_ips = failed_ips.count()
        
        # Security events requiring review
        requiring_review_query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.requires_review == True
        )
        if hostel_id:
            requiring_review_query = requiring_review_query.filter(AuditLog.hostel_id == hostel_id)
        requiring_review = requiring_review_query.count()
        
        # Critical severity events
        critical_events_query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.severity_level == 'critical'
        )
        if hostel_id:
            critical_events_query = critical_events_query.filter(AuditLog.hostel_id == hostel_id)
        critical_events = critical_events_query.count()
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            },
            'hostel_id': str(hostel_id) if hostel_id else 'all',
            'security_metrics': {
                'failed_authentication_attempts': failed_auth,
                'sensitive_data_access': sensitive_access,
                'sensitive_data_changes': sensitive_changes,
                'high_impact_overrides': high_impact_overrides,
                'unique_ips_with_failures': unique_failed_ips,
                'events_requiring_review': requiring_review,
                'critical_severity_events': critical_events
            },
            'security_score': self._calculate_security_score(
                failed_auth,
                sensitive_access,
                critical_events,
                requiring_review
            )
        }
    
    def detect_suspicious_patterns(
        self,
        hostel_id: Optional[UUID] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Detect suspicious activity patterns across all audit sources.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            List of detected suspicious patterns
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()
        
        suspicious_patterns = []
        
        # Pattern 1: Multiple failed login attempts from same IP
        failed_by_ip = self.session.query(
            AuditLog.ip_address,
            func.count(AuditLog.id).label('failure_count')
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.action_type.like('%login%'),
            AuditLog.status == 'failure',
            AuditLog.ip_address.isnot(None)
        )
        if hostel_id:
            failed_by_ip = failed_by_ip.filter(AuditLog.hostel_id == hostel_id)
        
        failed_by_ip = failed_by_ip.group_by(AuditLog.ip_address)\
            .having(func.count(AuditLog.id) > 5)\
            .all()
        
        for ip, count in failed_by_ip:
            suspicious_patterns.append({
                'pattern_type': 'multiple_failed_logins',
                'severity': 'high',
                'ip_address': str(ip),
                'failure_count': count,
                'description': f'IP {ip} had {count} failed login attempts'
            })
        
        # Pattern 2: Unusual activity volume by user
        user_activity = self.session.query(
            AuditLog.user_id,
            AuditLog.user_email,
            func.count(AuditLog.id).label('action_count')
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.user_id.isnot(None)
        )
        if hostel_id:
            user_activity = user_activity.filter(AuditLog.hostel_id == hostel_id)
        
        user_activity = user_activity.group_by(
            AuditLog.user_id,
            AuditLog.user_email
        ).all()
        
        if user_activity:
            action_counts = [count for _, _, count in user_activity]
            avg_count = sum(action_counts) / len(action_counts)
            threshold = avg_count * 3  # 3x average
            
            for user_id, email, count in user_activity:
                if count > threshold:
                    suspicious_patterns.append({
                        'pattern_type': 'unusual_activity_volume',
                        'severity': 'medium',
                        'user_id': str(user_id),
                        'user_email': email,
                        'action_count': count,
                        'threshold': round(threshold, 2),
                        'description': f'User {email} had {count} actions (threshold: {threshold:.0f})'
                    })
        
        # Pattern 3: Multiple sensitive data access in short time
        sensitive_access = self.session.query(
            AuditLog.user_id,
            AuditLog.user_email,
            func.count(AuditLog.id).label('access_count')
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.is_sensitive == True,
            AuditLog.user_id.isnot(None)
        )
        if hostel_id:
            sensitive_access = sensitive_access.filter(AuditLog.hostel_id == hostel_id)
        
        sensitive_access = sensitive_access.group_by(
            AuditLog.user_id,
            AuditLog.user_email
        ).having(func.count(AuditLog.id) > 10).all()
        
        for user_id, email, count in sensitive_access:
            suspicious_patterns.append({
                'pattern_type': 'excessive_sensitive_access',
                'severity': 'high',
                'user_id': str(user_id),
                'user_email': email,
                'access_count': count,
                'description': f'User {email} accessed sensitive data {count} times'
            })
        
        # Pattern 4: Off-hours activity
        off_hours_activity = self.session.query(
            AuditLog.user_id,
            AuditLog.user_email,
            func.count(AuditLog.id).label('activity_count')
        ).filter(
            AuditLog.created_at >= start_date,
            or_(
                func.extract('hour', AuditLog.created_at) < 6,
                func.extract('hour', AuditLog.created_at) > 22
            ),
            AuditLog.user_id.isnot(None)
        )
        if hostel_id:
            off_hours_activity = off_hours_activity.filter(AuditLog.hostel_id == hostel_id)
        
        off_hours_activity = off_hours_activity.group_by(
            AuditLog.user_id,
            AuditLog.user_email
        ).having(func.count(AuditLog.id) > 20).all()
        
        for user_id, email, count in off_hours_activity:
            suspicious_patterns.append({
                'pattern_type': 'off_hours_activity',
                'severity': 'medium',
                'user_id': str(user_id),
                'user_email': email,
                'activity_count': count,
                'description': f'User {email} had {count} actions during off-hours (10PM-6AM)'
            })
        
        return sorted(suspicious_patterns, key=lambda x: {'high': 3, 'medium': 2, 'low': 1}.get(x['severity'], 0), reverse=True)
    
    # ==================== Compliance Reporting ====================
    
    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None,
        compliance_framework: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report across all audit sources.
        
        Args:
            start_date: Report period start
            end_date: Report period end
            hostel_id: Optional hostel filter
            compliance_framework: Optional framework filter (GDPR, HIPAA, etc.)
            
        Returns:
            Compliance report dictionary
        """
        # Audit logs compliance
        audit_query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        if hostel_id:
            audit_query = audit_query.filter(AuditLog.hostel_id == hostel_id)
        if compliance_framework:
            audit_query = audit_query.filter(
                AuditLog.compliance_tags.contains([compliance_framework])
            )
        
        total_audit_logs = audit_query.count()
        sensitive_audit_logs = audit_query.filter(AuditLog.is_sensitive == True).count()
        
        # Entity changes compliance
        changes_query = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.created_at <= end_date
        )
        
        total_changes = changes_query.count()
        pii_changes = changes_query.filter(EntityChangeLog.is_pii == True).count()
        
        # Data retention compliance
        retention_violations = self.session.query(AuditLog).filter(
            AuditLog.created_at < start_date - timedelta(days=365),  # Example: 1 year retention
            AuditLog.retention_days.isnot(None)
        ).count()
        
        # Access control compliance (failed attempts)
        failed_access = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date,
            AuditLog.status == 'failure'
        )
        if hostel_id:
            failed_access = failed_access.filter(AuditLog.hostel_id == hostel_id)
        failed_access_count = failed_access.count()
        
        # Admin oversight compliance
        overrides_requiring_approval = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.created_at >= start_date,
            AdminOverrideLog.created_at <= end_date,
            AdminOverrideLog.requires_approval == True
        )
        if hostel_id:
            overrides_requiring_approval = overrides_requiring_approval.filter(
                AdminOverrideLog.hostel_id == hostel_id
            )
        
        total_overrides_needing_approval = overrides_requiring_approval.count()
        approved_overrides = overrides_requiring_approval.filter(
            AdminOverrideLog.approved_at.isnot(None)
        ).count()
        
        approval_compliance_rate = (
            approved_overrides / total_overrides_needing_approval * 100
            if total_overrides_needing_approval else 100
        )
        
        return {
            'report_metadata': {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'hostel_id': str(hostel_id) if hostel_id else 'all',
                'compliance_framework': compliance_framework or 'all',
                'generated_at': datetime.utcnow().isoformat()
            },
            'audit_trail_compliance': {
                'total_audit_logs': total_audit_logs,
                'sensitive_data_logs': sensitive_audit_logs,
                'sensitive_percentage': round(sensitive_audit_logs / total_audit_logs * 100, 2) if total_audit_logs else 0,
                'compliance_status': 'compliant' if total_audit_logs > 0 else 'no_activity'
            },
            'data_change_tracking': {
                'total_changes': total_changes,
                'pii_changes': pii_changes,
                'pii_percentage': round(pii_changes / total_changes * 100, 2) if total_changes else 0,
                'compliance_status': 'compliant'
            },
            'data_retention': {
                'retention_violations': retention_violations,
                'compliance_status': 'compliant' if retention_violations == 0 else 'violations_found'
            },
            'access_control': {
                'failed_access_attempts': failed_access_count,
                'compliance_status': 'review_required' if failed_access_count > 100 else 'compliant'
            },
            'administrative_oversight': {
                'overrides_requiring_approval': total_overrides_needing_approval,
                'approved_overrides': approved_overrides,
                'approval_rate': round(approval_compliance_rate, 2),
                'compliance_status': 'compliant' if approval_compliance_rate >= 95 else 'review_required'
            },
            'overall_compliance_score': self._calculate_compliance_score(
                total_audit_logs,
                retention_violations,
                approval_compliance_rate
            )
        }
    
    # ==================== Performance Analytics ====================
    
    def get_system_performance_metrics(
        self,
        hostel_id: Optional[UUID] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get system performance metrics from audit data.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Performance metrics dictionary
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()
        
        # Action success rates
        audit_query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        if hostel_id:
            audit_query = audit_query.filter(AuditLog.hostel_id == hostel_id)
        
        total_actions = audit_query.count()
        successful_actions = audit_query.filter(AuditLog.status == 'success').count()
        
        # Supervisor performance
        supervisor_query = self.session.query(SupervisorActivityLog).filter(
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date
        )
        if hostel_id:
            supervisor_query = supervisor_query.filter(SupervisorActivityLog.hostel_id == hostel_id)
        
        total_supervisor_activities = supervisor_query.count()
        completed_activities = supervisor_query.filter(
            SupervisorActivityLog.status == 'completed'
        ).count()
        
        # Average efficiency scores
        avg_efficiency = self.session.query(
            func.avg(SupervisorActivityLog.efficiency_score)
        ).filter(
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date,
            SupervisorActivityLog.efficiency_score.isnot(None)
        )
        if hostel_id:
            avg_efficiency = avg_efficiency.filter(SupervisorActivityLog.hostel_id == hostel_id)
        avg_efficiency = avg_efficiency.scalar()
        
        # Average quality scores
        avg_quality = self.session.query(
            func.avg(SupervisorActivityLog.quality_score)
        ).filter(
            SupervisorActivityLog.created_at >= start_date,
            SupervisorActivityLog.created_at <= end_date,
            SupervisorActivityLog.quality_score.isnot(None)
        )
        if hostel_id:
            avg_quality = avg_quality.filter(SupervisorActivityLog.hostel_id == hostel_id)
        avg_quality = avg_quality.scalar()
        
        # Override impact
        avg_override_impact = self.session.query(
            func.avg(AdminOverrideLog.impact_score)
        ).filter(
            AdminOverrideLog.created_at >= start_date,
            AdminOverrideLog.created_at <= end_date
        )
        if hostel_id:
            avg_override_impact = avg_override_impact.filter(AdminOverrideLog.hostel_id == hostel_id)
        avg_override_impact = avg_override_impact.scalar()
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            },
            'hostel_id': str(hostel_id) if hostel_id else 'all',
            'action_success_rate': round(successful_actions / total_actions * 100, 2) if total_actions else 0,
            'supervisor_completion_rate': round(completed_activities / total_supervisor_activities * 100, 2) if total_supervisor_activities else 0,
            'average_efficiency_score': round(float(avg_efficiency), 2) if avg_efficiency else 0,
            'average_quality_score': round(float(avg_quality), 2) if avg_quality else 0,
            'average_override_impact': round(float(avg_override_impact), 2) if avg_override_impact else 0,
            'performance_rating': self._calculate_performance_rating(
                successful_actions / total_actions * 100 if total_actions else 0,
                float(avg_efficiency) if avg_efficiency else 0,
                float(avg_quality) if avg_quality else 0
            )
        }
    
    # ==================== Helper Methods ====================
    
    def _calculate_security_score(
        self,
        failed_auth: int,
        sensitive_access: int,
        critical_events: int,
        requiring_review: int
    ) -> int:
        """
        Calculate overall security score (0-100).
        
        Args:
            failed_auth: Number of failed authentication attempts
            sensitive_access: Number of sensitive data access
            critical_events: Number of critical severity events
            requiring_review: Number of events requiring review
            
        Returns:
            Security score (0-100, higher is better)
        """
        # Start with perfect score
        score = 100
        
        # Deduct for security issues
        score -= min(failed_auth * 2, 30)  # Max 30 points for failed auth
        score -= min(critical_events * 5, 25)  # Max 25 points for critical events
        score -= min(requiring_review * 1, 20)  # Max 20 points for reviews needed
        
        # Bonus for low sensitive access (within reason)
        if sensitive_access < 10:
            score += 5
        
        return max(0, min(100, score))
    
    def _calculate_compliance_score(
        self,
        total_logs: int,
        retention_violations: int,
        approval_rate: float
    ) -> int:
        """
        Calculate overall compliance score (0-100).
        
        Args:
            total_logs: Total audit logs
            retention_violations: Number of retention policy violations
            approval_rate: Admin override approval rate
            
        Returns:
            Compliance score (0-100)
        """
        score = 100
        
        # Deduct for violations
        score -= min(retention_violations * 10, 40)
        
        # Deduct based on approval rate
        if approval_rate < 95:
            score -= (95 - approval_rate) * 2
        
        # Bonus for comprehensive logging
        if total_logs > 1000:
            score += 10
        
        return max(0, min(100, int(score)))
    
    def _calculate_performance_rating(
        self,
        success_rate: float,
        efficiency: float,
        quality: float
    ) -> str:
        """
        Calculate overall performance rating.
        
        Args:
            success_rate: Action success rate percentage
            efficiency: Average efficiency score
            quality: Average quality score
            
        Returns:
            Performance rating string
        """
        # Weighted average
        score = (success_rate * 0.4) + (efficiency * 0.3) + (quality * 20 * 0.3)
        
        if score >= 90:
            return 'excellent'
        elif score >= 75:
            return 'good'
        elif score >= 60:
            return 'satisfactory'
        elif score >= 45:
            return 'needs_improvement'
        else:
            return 'poor'