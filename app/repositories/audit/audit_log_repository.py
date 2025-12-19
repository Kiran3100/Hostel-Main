"""
Audit log repository for comprehensive system activity tracking.

Provides advanced querying, filtering, and analytics for audit logs
with performance optimization and compliance features.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.audit import AuditLog
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationManager
from app.repositories.base.filtering import FilteringEngine
from app.schemas.common.enums import AuditActionCategory


class AuditLogRepository(BaseRepository):
    """
    Repository for comprehensive audit log management.
    
    Provides advanced querying, analytics, and compliance features
    for system-wide audit trail tracking.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, AuditLog)
    
    # ==================== CRUD Operations ====================
    
    def create_audit_log(
        self,
        user_id: Optional[UUID],
        action_type: str,
        action_category: AuditActionCategory,
        action_description: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        entity_name: Optional[str] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        status: str = "success",
        context_metadata: Optional[Dict] = None,
        **kwargs
    ) -> AuditLog:
        """
        Create a new audit log entry.
        
        Args:
            user_id: User who performed the action
            action_type: Specific action identifier
            action_category: High-level action category
            action_description: Human-readable description
            entity_type: Type of entity affected
            entity_id: ID of affected entity
            entity_name: Display name of entity
            old_values: Previous values (for updates/deletes)
            new_values: New values (for creates/updates)
            status: Action outcome status
            context_metadata: Additional context
            **kwargs: Additional fields
            
        Returns:
            Created AuditLog instance
        """
        audit_log = AuditLog(
            user_id=user_id,
            action_type=action_type,
            action_category=action_category,
            action_description=action_description,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            old_values=old_values or {},
            new_values=new_values or {},
            status=status,
            context_metadata=context_metadata or {},
            **kwargs
        )
        
        # Auto-calculate severity level if not provided
        if 'severity_level' not in kwargs:
            audit_log.severity_level = self._calculate_severity(
                action_category, status, entity_type
            )
        
        # Determine if review is required
        if 'requires_review' not in kwargs:
            audit_log.requires_review = self._requires_review(
                action_category, audit_log.severity_level, status
            )
        
        return self.create(audit_log)
    
    def bulk_create_audit_logs(
        self,
        audit_logs: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> List[AuditLog]:
        """
        Bulk create audit log entries with batch processing.
        
        Args:
            audit_logs: List of audit log data dictionaries
            batch_size: Number of records per batch
            
        Returns:
            List of created AuditLog instances
        """
        created_logs = []
        
        for i in range(0, len(audit_logs), batch_size):
            batch = audit_logs[i:i + batch_size]
            log_objects = [AuditLog(**log_data) for log_data in batch]
            
            self.session.bulk_save_objects(log_objects, return_defaults=True)
            self.session.flush()
            
            created_logs.extend(log_objects)
        
        self.session.commit()
        return created_logs
    
    # ==================== Query Operations ====================
    
    def find_by_user(
        self,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_category: Optional[AuditActionCategory] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[AuditLog], int]:
        """
        Find audit logs by user with optional filtering.
        
        Args:
            user_id: User ID to filter by
            start_date: Start date for filtering
            end_date: End date for filtering
            action_category: Optional action category filter
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            Tuple of (audit logs, total count)
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.user_id == user_id
        )
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        if action_category:
            query = query.filter(AuditLog.action_category == action_category)
        
        total = query.count()
        
        results = query.order_by(desc(AuditLog.created_at))\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        return results, total
    
    def find_by_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        include_related: bool = True,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Find all audit logs for a specific entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            include_related: Include related entity logs
            limit: Maximum number of results
            
        Returns:
            List of audit logs
        """
        query = self.session.query(AuditLog)
        
        if include_related:
            query = query.filter(
                or_(
                    and_(
                        AuditLog.entity_type == entity_type,
                        AuditLog.entity_id == entity_id
                    ),
                    and_(
                        AuditLog.related_entity_type == entity_type,
                        AuditLog.related_entity_id == entity_id
                    )
                )
            )
        else:
            query = query.filter(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id
            )
        
        return query.order_by(desc(AuditLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_categories: Optional[List[AuditActionCategory]] = None,
        severity_levels: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[AuditLog], int]:
        """
        Find audit logs by hostel with advanced filtering.
        
        Args:
            hostel_id: Hostel ID to filter by
            start_date: Start date filter
            end_date: End date filter
            action_categories: List of action categories to include
            severity_levels: List of severity levels to include
            limit: Maximum results
            offset: Results to skip
            
        Returns:
            Tuple of (audit logs, total count)
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.hostel_id == hostel_id
        )
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        if action_categories:
            query = query.filter(AuditLog.action_category.in_(action_categories))
        
        if severity_levels:
            query = query.filter(AuditLog.severity_level.in_(severity_levels))
        
        total = query.count()
        
        results = query.order_by(desc(AuditLog.created_at))\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        return results, total
    
    def find_by_action_type(
        self,
        action_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Find audit logs by action type.
        
        Args:
            action_type: Action type to filter by
            start_date: Start date filter
            end_date: End date filter
            status: Optional status filter
            limit: Maximum results
            
        Returns:
            List of audit logs
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.action_type == action_type
        )
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        if status:
            query = query.filter(AuditLog.status == status)
        
        return query.order_by(desc(AuditLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_failed_actions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Find all failed actions for error analysis.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            user_id: Optional user filter
            limit: Maximum results
            
        Returns:
            List of failed audit logs
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.status == 'failure'
        )
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        return query.order_by(desc(AuditLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_sensitive_actions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Find actions marked as sensitive for security review.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            user_id: Optional user filter
            limit: Maximum results
            
        Returns:
            List of sensitive audit logs
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.is_sensitive == True
        )
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        return query.order_by(desc(AuditLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_requiring_review(
        self,
        severity_level: Optional[str] = None,
        action_category: Optional[AuditActionCategory] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Find audit logs that require manual review.
        
        Args:
            severity_level: Optional severity filter
            action_category: Optional category filter
            limit: Maximum results
            
        Returns:
            List of audit logs requiring review
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.requires_review == True
        )
        
        if severity_level:
            query = query.filter(AuditLog.severity_level == severity_level)
        
        if action_category:
            query = query.filter(AuditLog.action_category == action_category)
        
        return query.order_by(desc(AuditLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_ip_address(
        self,
        ip_address: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Find audit logs by IP address for security analysis.
        
        Args:
            ip_address: IP address to search
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            
        Returns:
            List of audit logs from IP
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.ip_address == ip_address
        )
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        return query.order_by(desc(AuditLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_request_id(
        self,
        request_id: str
    ) -> List[AuditLog]:
        """
        Find all audit logs for a specific request for tracing.
        
        Args:
            request_id: Request/trace ID
            
        Returns:
            List of audit logs for the request
        """
        return self.session.query(AuditLog).filter(
            AuditLog.request_id == request_id
        ).order_by(AuditLog.created_at).all()
    
    def find_by_session_id(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Find all audit logs for a user session.
        
        Args:
            session_id: User session ID
            limit: Maximum results
            
        Returns:
            List of audit logs for the session
        """
        return self.session.query(AuditLog).filter(
            AuditLog.session_id == session_id
        ).order_by(AuditLog.created_at)\
            .limit(limit)\
            .all()
    
    # ==================== Analytics Operations ====================
    
    def get_action_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive action statistics for a period.
        
        Args:
            start_date: Period start date
            end_date: Period end date
            hostel_id: Optional hostel filter
            user_id: Optional user filter
            
        Returns:
            Dictionary with statistics
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        
        if hostel_id:
            query = query.filter(AuditLog.hostel_id == hostel_id)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        total_actions = query.count()
        
        # Actions by status
        status_counts = self.session.query(
            AuditLog.status,
            func.count(AuditLog.id)
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        
        if hostel_id:
            status_counts = status_counts.filter(AuditLog.hostel_id == hostel_id)
        if user_id:
            status_counts = status_counts.filter(AuditLog.user_id == user_id)
        
        status_counts = status_counts.group_by(AuditLog.status).all()
        
        # Actions by category
        category_counts = self.session.query(
            AuditLog.action_category,
            func.count(AuditLog.id)
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        
        if hostel_id:
            category_counts = category_counts.filter(AuditLog.hostel_id == hostel_id)
        if user_id:
            category_counts = category_counts.filter(AuditLog.user_id == user_id)
        
        category_counts = category_counts.group_by(AuditLog.action_category).all()
        
        # Actions by severity
        severity_counts = self.session.query(
            AuditLog.severity_level,
            func.count(AuditLog.id)
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        
        if hostel_id:
            severity_counts = severity_counts.filter(AuditLog.hostel_id == hostel_id)
        if user_id:
            severity_counts = severity_counts.filter(AuditLog.user_id == user_id)
        
        severity_counts = severity_counts.group_by(AuditLog.severity_level).all()
        
        # Top users
        top_users = self.session.query(
            AuditLog.user_id,
            AuditLog.user_email,
            func.count(AuditLog.id).label('action_count')
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        
        if hostel_id:
            top_users = top_users.filter(AuditLog.hostel_id == hostel_id)
        
        top_users = top_users.group_by(
            AuditLog.user_id,
            AuditLog.user_email
        ).order_by(desc('action_count')).limit(10).all()
        
        # Top action types
        top_actions = self.session.query(
            AuditLog.action_type,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        
        if hostel_id:
            top_actions = top_actions.filter(AuditLog.hostel_id == hostel_id)
        if user_id:
            top_actions = top_actions.filter(AuditLog.user_id == user_id)
        
        top_actions = top_actions.group_by(AuditLog.action_type)\
            .order_by(desc('count'))\
            .limit(10)\
            .all()
        
        return {
            'total_actions': total_actions,
            'by_status': dict(status_counts),
            'by_category': {cat.value: count for cat, count in category_counts},
            'by_severity': dict(severity_counts),
            'top_users': [
                {'user_id': str(uid), 'email': email, 'count': count}
                for uid, email, count in top_users
            ],
            'top_actions': [
                {'action_type': action, 'count': count}
                for action, count in top_actions
            ],
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def get_user_activity_timeline(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        group_by: str = 'hour'  # 'hour', 'day', 'week'
    ) -> List[Dict[str, Any]]:
        """
        Get user activity timeline with time-based grouping.
        
        Args:
            user_id: User ID
            start_date: Period start
            end_date: Period end
            group_by: Grouping interval
            
        Returns:
            List of timeline data points
        """
        if group_by == 'hour':
            time_format = func.date_trunc('hour', AuditLog.created_at)
        elif group_by == 'day':
            time_format = func.date_trunc('day', AuditLog.created_at)
        elif group_by == 'week':
            time_format = func.date_trunc('week', AuditLog.created_at)
        else:
            time_format = func.date_trunc('day', AuditLog.created_at)
        
        timeline = self.session.query(
            time_format.label('time_bucket'),
            func.count(AuditLog.id).label('action_count'),
            AuditLog.action_category
        ).filter(
            AuditLog.user_id == user_id,
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        ).group_by(
            'time_bucket',
            AuditLog.action_category
        ).order_by('time_bucket').all()
        
        return [
            {
                'timestamp': bucket.isoformat(),
                'count': count,
                'category': category.value
            }
            for bucket, count, category in timeline
        ]
    
    def get_entity_change_summary(
        self,
        entity_type: str,
        entity_id: UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive change summary for an entity.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            
        Returns:
            Dictionary with change summary
        """
        logs = self.find_by_entity(entity_type, entity_id, include_related=False)
        
        if not logs:
            return {
                'entity_type': entity_type,
                'entity_id': str(entity_id),
                'total_changes': 0,
                'first_change': None,
                'last_change': None,
                'changes_by_user': {},
                'changes_by_type': {}
            }
        
        # Changes by user
        changes_by_user = {}
        for log in logs:
            user_key = log.user_email or str(log.user_id) if log.user_id else 'system'
            changes_by_user[user_key] = changes_by_user.get(user_key, 0) + 1
        
        # Changes by action type
        changes_by_type = {}
        for log in logs:
            changes_by_type[log.action_type] = changes_by_type.get(log.action_type, 0) + 1
        
        return {
            'entity_type': entity_type,
            'entity_id': str(entity_id),
            'entity_name': logs[0].entity_name if logs else None,
            'total_changes': len(logs),
            'first_change': logs[-1].created_at.isoformat() if logs else None,
            'last_change': logs[0].created_at.isoformat() if logs else None,
            'changes_by_user': changes_by_user,
            'changes_by_type': changes_by_type,
            'recent_changes': [
                {
                    'action_type': log.action_type,
                    'user': log.user_email,
                    'timestamp': log.created_at.isoformat(),
                    'status': log.status
                }
                for log in logs[:10]  # Last 10 changes
            ]
        }
    
    def get_security_events(
        self,
        start_date: datetime,
        end_date: datetime,
        severity_threshold: str = 'medium',
        hostel_id: Optional[UUID] = None
    ) -> List[AuditLog]:
        """
        Get security-related events for monitoring.
        
        Args:
            start_date: Period start
            end_date: Period end
            severity_threshold: Minimum severity level
            hostel_id: Optional hostel filter
            
        Returns:
            List of security-related audit logs
        """
        severity_order = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        threshold_value = severity_order.get(severity_threshold, 2)
        
        query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date,
            or_(
                AuditLog.is_sensitive == True,
                AuditLog.status == 'failure',
                AuditLog.requires_review == True
            )
        )
        
        if hostel_id:
            query = query.filter(AuditLog.hostel_id == hostel_id)
        
        results = query.order_by(desc(AuditLog.created_at)).all()
        
        # Filter by severity threshold
        filtered_results = [
            log for log in results
            if severity_order.get(log.severity_level, 0) >= threshold_value
        ]
        
        return filtered_results
    
    def get_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        compliance_tags: Optional[List[str]] = None,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Generate compliance report for audit purposes.
        
        Args:
            start_date: Report period start
            end_date: Report period end
            compliance_tags: Optional compliance framework tags
            hostel_id: Optional hostel filter
            
        Returns:
            Compliance report dictionary
        """
        query = self.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
        
        if hostel_id:
            query = query.filter(AuditLog.hostel_id == hostel_id)
        
        if compliance_tags:
            # Filter by compliance tags in JSONB array
            query = query.filter(
                AuditLog.compliance_tags.contains(compliance_tags)
            )
        
        all_logs = query.all()
        
        # Sensitive data access logs
        sensitive_access = [log for log in all_logs if log.is_sensitive]
        
        # Failed actions
        failed_actions = [log for log in all_logs if log.status == 'failure']
        
        # Critical severity actions
        critical_actions = [log for log in all_logs if log.severity_level == 'critical']
        
        # Actions by category
        category_breakdown = {}
        for log in all_logs:
            cat = log.action_category.value
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        
        return {
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_actions': len(all_logs),
            'sensitive_data_access': {
                'count': len(sensitive_access),
                'percentage': len(sensitive_access) / len(all_logs) * 100 if all_logs else 0
            },
            'failed_actions': {
                'count': len(failed_actions),
                'percentage': len(failed_actions) / len(all_logs) * 100 if all_logs else 0
            },
            'critical_actions': {
                'count': len(critical_actions),
                'percentage': len(critical_actions) / len(all_logs) * 100 if all_logs else 0
            },
            'actions_by_category': category_breakdown,
            'compliance_tags': compliance_tags or [],
            'hostel_id': str(hostel_id) if hostel_id else 'all'
        }
    
    # ==================== Maintenance Operations ====================
    
    def archive_old_logs(
        self,
        cutoff_date: datetime,
        batch_size: int = 1000
    ) -> int:
        """
        Archive audit logs older than cutoff date.
        
        Args:
            cutoff_date: Date before which logs should be archived
            batch_size: Number of records per batch
            
        Returns:
            Number of archived records
        """
        # This would typically move records to an archive table
        # For now, we'll just count what would be archived
        count = self.session.query(AuditLog).filter(
            AuditLog.created_at < cutoff_date
        ).count()
        
        # TODO: Implement actual archival to archive table or file storage
        
        return count
    
    def cleanup_by_retention_policy(
        self,
        default_retention_days: int = 365
    ) -> int:
        """
        Clean up logs based on retention policies.
        
        Args:
            default_retention_days: Default retention in days
            
        Returns:
            Number of deleted records
        """
        cutoff_date = datetime.utcnow() - timedelta(days=default_retention_days)
        
        # Find logs eligible for deletion
        eligible_logs = self.session.query(AuditLog).filter(
            or_(
                and_(
                    AuditLog.retention_days.isnot(None),
                    AuditLog.created_at < func.now() - func.cast(
                        func.concat(AuditLog.retention_days, ' days'),
                        type_=type(timedelta())
                    )
                ),
                and_(
                    AuditLog.retention_days.is_(None),
                    AuditLog.created_at < cutoff_date,
                    AuditLog.is_sensitive == False  # Keep sensitive logs longer
                )
            )
        ).all()
        
        count = len(eligible_logs)
        
        # Soft delete or hard delete based on requirements
        for log in eligible_logs:
            self.session.delete(log)
        
        self.session.commit()
        
        return count
    
    # ==================== Helper Methods ====================
    
    def _calculate_severity(
        self,
        action_category: AuditActionCategory,
        status: str,
        entity_type: Optional[str]
    ) -> str:
        """Calculate severity level based on action characteristics."""
        # Critical severity
        if status == 'failure' and action_category in [
            AuditActionCategory.SECURITY,
            AuditActionCategory.DATA_ACCESS
        ]:
            return 'critical'
        
        # High severity
        if action_category in [
            AuditActionCategory.SECURITY,
            AuditActionCategory.ADMIN_ACTION,
            AuditActionCategory.FINANCIAL
        ]:
            return 'high'
        
        # Medium severity
        if action_category in [
            AuditActionCategory.DATA_CHANGE,
            AuditActionCategory.SYSTEM_CONFIG
        ]:
            return 'medium'
        
        # Low severity
        if action_category in [
            AuditActionCategory.DATA_ACCESS,
            AuditActionCategory.USER_ACTION
        ]:
            return 'low'
        
        # Default to info
        return 'info'
    
    def _requires_review(
        self,
        action_category: AuditActionCategory,
        severity_level: str,
        status: str
    ) -> bool:
        """Determine if action requires manual review."""
        # Always review critical severity
        if severity_level == 'critical':
            return True
        
        # Review failed security actions
        if status == 'failure' and action_category == AuditActionCategory.SECURITY:
            return True
        
        # Review high severity admin actions
        if severity_level == 'high' and action_category == AuditActionCategory.ADMIN_ACTION:
            return True
        
        return False
    
    def get_audit_trail(
        self,
        entity_type: str,
        entity_id: UUID,
        include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get formatted audit trail for an entity.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            include_metadata: Include full metadata
            
        Returns:
            List of formatted audit trail entries
        """
        logs = self.find_by_entity(entity_type, entity_id)
        
        trail = []
        for log in logs:
            entry = {
                'timestamp': log.created_at.isoformat(),
                'action': log.action_type,
                'description': log.action_description,
                'user': log.user_email or str(log.user_id) if log.user_id else 'System',
                'status': log.status,
                'severity': log.severity_level
            }
            
            if include_metadata:
                entry['old_values'] = log.old_values
                entry['new_values'] = log.new_values
                entry['context'] = log.context_metadata
                entry['ip_address'] = str(log.ip_address) if log.ip_address else None
            
            trail.append(entry)
        
        return trail