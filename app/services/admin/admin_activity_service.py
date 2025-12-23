"""
Admin activity service leveraging audit and security repositories.

Tracks admin actions, security events, and provides activity analytics.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.audit import (
    AuditLogRepository,
    AdminOverrideLogRepository,
)
from app.repositories.auth import SecurityEventRepository
from app.models.audit import AuditLog, AdminOverrideLog
from app.models.auth import SecurityEvent


class AdminActivityService(BaseService[AuditLog, AuditLogRepository]):
    """
    Service for admin activity and security event management.
    
    Responsibilities:
    - Record admin activity in audit log
    - Fetch and filter activity streams
    - Generate activity summaries and metrics
    - Track security events for admin accounts
    - Detect and flag suspicious activity
    """
    
    def __init__(
        self,
        audit_repository: AuditLogRepository,
        override_repository: AdminOverrideLogRepository,
        security_repository: SecurityEventRepository,
        db_session: Session,
    ):
        """
        Initialize activity service.
        
        Args:
            audit_repository: Audit log repository
            override_repository: Admin override log repository
            security_repository: Security event repository
            db_session: Database session
        """
        super().__init__(audit_repository, db_session)
        self.audit_repository = audit_repository
        self.override_repository = override_repository
        self.security_repository = security_repository
    
    # =========================================================================
    # Activity Logging
    # =========================================================================
    
    def log_activity(
        self,
        admin_user_id: UUID,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        category: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> ServiceResult[AuditLog]:
        """
        Record an admin activity as audit log entry.
        
        Args:
            admin_user_id: Admin user ID
            action: Action performed
            entity_type: Type of entity affected
            entity_id: ID of entity affected
            category: Activity category
            context: Additional context data
            success: Whether action was successful
            
        Returns:
            ServiceResult containing created audit log entry
        """
        try:
            entry = self.audit_repository.create({
                "actor_user_id": admin_user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "category": category,
                "context": context or {},
                "status": "success" if success else "failed",
                "timestamp": datetime.utcnow(),
            })
            self.db.commit()
            
            self._logger.info(
                f"Activity logged: {action}",
                extra={
                    "admin_id": str(admin_user_id),
                    "action": action,
                    "entity_type": entity_type,
                    "success": success,
                },
            )
            
            return ServiceResult.success(entry, message="Activity logged")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "log activity", admin_user_id)
    
    def log_bulk_activity(
        self,
        admin_user_id: UUID,
        activities: List[Dict[str, Any]],
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Log multiple activities in a single transaction.
        
        Args:
            admin_user_id: Admin user ID
            activities: List of activity dictionaries
            
        Returns:
            ServiceResult with summary of logged activities
        """
        try:
            logged_count = 0
            failed_count = 0
            
            for activity in activities:
                try:
                    activity['actor_user_id'] = admin_user_id
                    activity.setdefault('timestamp', datetime.utcnow())
                    activity.setdefault('context', {})
                    
                    self.audit_repository.create(activity)
                    logged_count += 1
                except Exception as e:
                    failed_count += 1
                    self._logger.warning(
                        f"Failed to log activity: {str(e)}",
                        extra={"activity": activity},
                    )
            
            self.db.commit()
            
            summary = {
                "total": len(activities),
                "logged": logged_count,
                "failed": failed_count,
            }
            
            return ServiceResult.success(
                summary,
                message=f"Bulk activity logged: {logged_count}/{len(activities)} successful",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "log bulk activity", admin_user_id)
    
    # =========================================================================
    # Activity Retrieval
    # =========================================================================
    
    def get_recent_activity(
        self,
        admin_user_id: UUID,
        limit: int = 20,
        days: int = 7,
        category: Optional[str] = None,
    ) -> ServiceResult[List[AuditLog]]:
        """
        Fetch recent activity for an admin.
        
        Args:
            admin_user_id: Admin user ID
            limit: Maximum number of entries to return
            days: Number of days to look back
            category: Optional category filter
            
        Returns:
            ServiceResult containing list of audit log entries
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            items = self.audit_repository.get_user_activity(
                admin_user_id,
                since,
                limit=limit,
                category=category,
            )
            
            return ServiceResult.success(
                items,
                message="Recent activity retrieved",
                metadata={
                    "count": len(items),
                    "days": days,
                    "category": category,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get recent activity", admin_user_id)
    
    def get_activity_by_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
        days: int = 30,
    ) -> ServiceResult[List[AuditLog]]:
        """
        Get all activity related to a specific entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            limit: Maximum entries to return
            days: Days to look back
            
        Returns:
            ServiceResult containing activity for entity
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            items = self.audit_repository.get_entity_activity(
                entity_type,
                entity_id,
                since,
                limit=limit,
            )
            
            return ServiceResult.success(
                items,
                message="Entity activity retrieved",
                metadata={
                    "count": len(items),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get activity by entity")
    
    # =========================================================================
    # Activity Analytics
    # =========================================================================
    
    def get_activity_summary(
        self,
        admin_user_id: UUID,
        days: int = 30,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Generate aggregate activity metrics for an admin.
        
        Args:
            admin_user_id: Admin user ID
            days: Number of days to analyze
            
        Returns:
            ServiceResult containing activity summary
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            # Get activity summary from repository
            summary = self.audit_repository.get_activity_summary(admin_user_id, since)
            
            # Get override summary
            overrides = self.override_repository.get_override_summary(
                admin_user_id,
                since,
                datetime.utcnow(),
            )
            
            # Combine summaries
            summary["overrides"] = overrides or {}
            summary["period_days"] = days
            summary["period_start"] = since.isoformat()
            summary["period_end"] = datetime.utcnow().isoformat()
            
            return ServiceResult.success(
                summary,
                message="Activity summary generated",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get activity summary", admin_user_id)
    
    def get_activity_trends(
        self,
        admin_user_id: UUID,
        days: int = 30,
        granularity: str = "daily",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get activity trends over time.
        
        Args:
            admin_user_id: Admin user ID
            days: Number of days to analyze
            granularity: Trend granularity (daily, weekly, monthly)
            
        Returns:
            ServiceResult containing trend data
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            trends = self.audit_repository.get_activity_trends(
                admin_user_id,
                since,
                granularity=granularity,
            )
            
            return ServiceResult.success(
                trends,
                message="Activity trends retrieved",
                metadata={
                    "days": days,
                    "granularity": granularity,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get activity trends", admin_user_id)
    
    # =========================================================================
    # Security Events
    # =========================================================================
    
    def get_security_events(
        self,
        admin_user_id: UUID,
        days: int = 30,
        event_type: Optional[str] = None,
        resolved_only: bool = False,
    ) -> ServiceResult[List[SecurityEvent]]:
        """
        Retrieve security events for admin account.
        
        Args:
            admin_user_id: Admin user ID
            days: Number of days to look back
            event_type: Optional event type filter
            resolved_only: Only return resolved events
            
        Returns:
            ServiceResult containing list of security events
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            events = self.security_repository.get_events_for_user(
                admin_user_id,
                since,
                event_type=event_type,
                resolved_only=resolved_only,
            )
            
            return ServiceResult.success(
                events,
                message="Security events retrieved",
                metadata={
                    "count": len(events),
                    "days": days,
                    "event_type": event_type,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get security events", admin_user_id)
    
    def flag_suspicious_activity(
        self,
        admin_user_id: UUID,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "medium",
    ) -> ServiceResult[SecurityEvent]:
        """
        Create a security event for suspicious activity.
        
        Args:
            admin_user_id: Admin user ID
            reason: Reason for flagging
            details: Additional details
            severity: Event severity (low, medium, high, critical)
            
        Returns:
            ServiceResult containing created security event
        """
        try:
            event = self.security_repository.create_event({
                "user_id": admin_user_id,
                "event_type": "suspicious_activity",
                "reason": reason,
                "severity": severity,
                "details": details or {},
                "created_at": datetime.utcnow(),
                "resolved": False,
            })
            self.db.commit()
            
            self._logger.warning(
                f"Suspicious activity flagged for admin {admin_user_id}",
                extra={
                    "admin_id": str(admin_user_id),
                    "reason": reason,
                    "severity": severity,
                },
            )
            
            return ServiceResult.success(
                event,
                message="Security event created",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "flag suspicious activity", admin_user_id)
    
    def resolve_security_event(
        self,
        event_id: UUID,
        resolved_by: UUID,
        resolution_notes: Optional[str] = None,
    ) -> ServiceResult[SecurityEvent]:
        """
        Resolve a security event.
        
        Args:
            event_id: Security event ID
            resolved_by: ID of user resolving
            resolution_notes: Resolution notes
            
        Returns:
            ServiceResult containing updated security event
        """
        try:
            event = self.security_repository.resolve_event(
                event_id,
                resolved_by,
                resolution_notes,
            )
            self.db.commit()
            
            self._logger.info(
                f"Security event resolved: {event_id}",
                extra={
                    "event_id": str(event_id),
                    "resolved_by": str(resolved_by),
                },
            )
            
            return ServiceResult.success(
                event,
                message="Security event resolved",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "resolve security event", event_id)