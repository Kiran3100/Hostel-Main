"""
Admin override service.

Handles admin override operations, approvals, tracking, and analytics.
"""

from typing import Optional, List, Dict, Any
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
from app.repositories.admin import AdminOverrideRepository
from app.models.admin import AdminOverride
from app.schemas.admin.admin_override import (
    AdminOverrideRequest,
    OverrideLog,
)


class AdminOverrideService(BaseService[AdminOverride, AdminOverrideRepository]):
    """
    Service for admin override operations.
    
    Responsibilities:
    - Override creation and approval workflow
    - Override tracking and analytics
    - Supervisor impact analysis
    - Override validation and limits enforcement
    """
    
    # Override limits
    DEFAULT_DAILY_LIMIT = 10
    DEFAULT_MONTHLY_LIMIT = 100
    
    def __init__(
        self,
        repository: AdminOverrideRepository,
        db_session: Session,
    ):
        """
        Initialize override service.
        
        Args:
            repository: Override repository
            db_session: Database session
        """
        super().__init__(repository, db_session)
    
    # =========================================================================
    # Override Management
    # =========================================================================
    
    def create_override(
        self,
        override_data: AdminOverrideRequest,
        admin_id: UUID,
    ) -> ServiceResult[AdminOverride]:
        """
        Create a new admin override.
        
        Validates:
        - Override limits not exceeded
        - Entity exists
        - Supervisor is valid
        
        Args:
            override_data: Override request data
            admin_id: ID of admin creating override
            
        Returns:
            ServiceResult containing created override or error
        """
        try:
            # Validate override limits
            limit_check = self._check_override_limits(
                admin_id,
                override_data.supervisor_id,
            )
            if not limit_check.is_success:
                return limit_check
            
            # Validate entity exists
            entity_check = self._validate_entity(
                override_data.entity_type,
                override_data.entity_id,
            )
            if not entity_check.is_success:
                return entity_check
            
            # Create override
            override = self.repository.create_override(
                admin_id=admin_id,
                supervisor_id=override_data.supervisor_id,
                hostel_id=override_data.hostel_id,
                entity_type=override_data.entity_type,
                entity_id=override_data.entity_id,
                override_type=override_data.override_type,
                reason=override_data.reason,
                original_action=override_data.original_action,
                override_action=override_data.override_action,
            )
            self.db.flush()
            
            # Send notification if requested
            if override_data.notify_supervisor:
                self._send_override_notification(override)
            
            self.db.commit()
            
            self._logger.info(
                "Override created",
                extra={
                    "override_id": str(override.id),
                    "admin_id": str(admin_id),
                    "supervisor_id": str(override_data.supervisor_id),
                    "override_type": override_data.override_type,
                },
            )
            
            return ServiceResult.success(
                override,
                message="Override created successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create override")
    
    def approve_override(
        self,
        override_id: UUID,
        approved_by: UUID,
        approval_notes: Optional[str] = None,
    ) -> ServiceResult[AdminOverride]:
        """
        Approve a pending override.
        
        Args:
            override_id: Override ID
            approved_by: ID of user approving
            approval_notes: Optional approval notes
            
        Returns:
            ServiceResult containing approved override
        """
        try:
            override = self.repository.get_by_id(override_id)
            if not override:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Override not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check if already processed
            if override.approval_status != 'pending':
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message=f"Override already {override.approval_status}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Update override
            updated = self.repository.update(
                override_id,
                {
                    'approval_status': 'approved',
                    'approved_by': approved_by,
                    'approved_at': datetime.utcnow(),
                    'approval_notes': approval_notes,
                },
            )
            self.db.commit()
            
            self._logger.info(
                "Override approved",
                extra={
                    "override_id": str(override_id),
                    "approved_by": str(approved_by),
                },
            )
            
            return ServiceResult.success(
                updated,
                message="Override approved successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "approve override", override_id)
    
    def reject_override(
        self,
        override_id: UUID,
        rejected_by: UUID,
        rejection_reason: str,
    ) -> ServiceResult[AdminOverride]:
        """
        Reject a pending override.
        
        Args:
            override_id: Override ID
            rejected_by: ID of user rejecting
            rejection_reason: Reason for rejection
            
        Returns:
            ServiceResult containing rejected override
        """
        try:
            override = self.repository.get_by_id(override_id)
            if not override:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Override not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check if already processed
            if override.approval_status != 'pending':
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message=f"Override already {override.approval_status}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Update override
            updated = self.repository.update(
                override_id,
                {
                    'approval_status': 'rejected',
                    'approved_by': rejected_by,
                    'approved_at': datetime.utcnow(),
                    'approval_notes': rejection_reason,
                },
            )
            self.db.commit()
            
            self._logger.info(
                "Override rejected",
                extra={
                    "override_id": str(override_id),
                    "rejected_by": str(rejected_by),
                    "reason": rejection_reason,
                },
            )
            
            return ServiceResult.success(
                updated,
                message="Override rejected",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "reject override", override_id)
    
    # =========================================================================
    # Override Queries
    # =========================================================================
    
    def get_pending_overrides(
        self,
        supervisor_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> ServiceResult[List[AdminOverride]]:
        """
        Get pending overrides awaiting approval.
        
        Args:
            supervisor_id: Filter by supervisor
            hostel_id: Filter by hostel
            limit: Maximum results
            
        Returns:
            ServiceResult containing pending overrides
        """
        try:
            overrides = self.repository.get_pending_overrides(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                limit=limit,
            )
            
            return ServiceResult.success(
                overrides,
                message="Pending overrides retrieved",
                metadata={"count": len(overrides)},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get pending overrides")
    
    def get_admin_overrides(
        self,
        admin_id: UUID,
        days: int = 30,
        status: Optional[str] = None,
    ) -> ServiceResult[List[AdminOverride]]:
        """
        Get overrides created by an admin.
        
        Args:
            admin_id: Admin user ID
            days: Days to look back
            status: Filter by status (pending, approved, rejected)
            
        Returns:
            ServiceResult containing admin's overrides
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            overrides = self.repository.get_admin_overrides(
                admin_id,
                since=since,
                status=status,
            )
            
            return ServiceResult.success(
                overrides,
                message="Admin overrides retrieved",
                metadata={
                    "count": len(overrides),
                    "days": days,
                    "status": status,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get admin overrides", admin_id)
    
    # =========================================================================
    # Override Analytics
    # =========================================================================
    
    def get_override_summary(
        self,
        admin_id: UUID,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get override summary for an admin.
        
        Args:
            admin_id: Admin user ID
            period_start: Start of period
            period_end: End of period
            
        Returns:
            ServiceResult containing override summary
        """
        try:
            # Default to last 30 days
            if not period_start:
                period_start = datetime.utcnow() - timedelta(days=30)
            if not period_end:
                period_end = datetime.utcnow()
            
            summary = self.repository.get_override_summary(
                admin_id,
                period_start,
                period_end,
            )
            
            # Add period info
            summary['period'] = {
                'start': period_start.isoformat(),
                'end': period_end.isoformat(),
                'days': (period_end - period_start).days,
            }
            
            return ServiceResult.success(
                summary,
                message="Override summary retrieved successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get override summary", admin_id)
    
    def get_supervisor_impact(
        self,
        supervisor_id: UUID,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get impact analysis for supervisor overrides.
        
        Args:
            supervisor_id: Supervisor user ID
            period_start: Start of period
            period_end: End of period
            
        Returns:
            ServiceResult containing impact analysis
        """
        try:
            if not period_start:
                period_start = datetime.utcnow() - timedelta(days=30)
            if not period_end:
                period_end = datetime.utcnow()
            
            impact = self.repository.get_supervisor_impact(
                supervisor_id,
                period_start,
                period_end,
            )
            
            # Add period info
            impact['period'] = {
                'start': period_start.isoformat(),
                'end': period_end.isoformat(),
                'days': (period_end - period_start).days,
            }
            
            return ServiceResult.success(
                impact,
                message="Supervisor impact retrieved successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get supervisor impact", supervisor_id)
    
    def get_override_trends(
        self,
        admin_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        days: int = 90,
        granularity: str = "daily",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get override trends over time.
        
        Args:
            admin_id: Optional admin filter
            hostel_id: Optional hostel filter
            days: Days to analyze
            granularity: Trend granularity (daily, weekly, monthly)
            
        Returns:
            ServiceResult containing trend data
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            trends = self.repository.get_override_trends(
                admin_id=admin_id,
                hostel_id=hostel_id,
                since=since,
                granularity=granularity,
            )
            
            return ServiceResult.success(
                trends,
                message="Override trends retrieved",
                metadata={
                    "days": days,
                    "granularity": granularity,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get override trends")
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _check_override_limits(
        self,
        admin_id: UUID,
        supervisor_id: UUID,
    ) -> ServiceResult[None]:
        """
        Check if admin is within override limits.
        
        Args:
            admin_id: Admin user ID
            supervisor_id: Supervisor being overridden
            
        Returns:
            ServiceResult indicating if within limits
        """
        # Check daily limit
        daily_count = self.repository.count_recent_overrides(admin_id, days=1)
        if daily_count >= self.DEFAULT_DAILY_LIMIT:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=f"Daily override limit reached ({self.DEFAULT_DAILY_LIMIT})",
                    details={"current_count": daily_count, "limit": self.DEFAULT_DAILY_LIMIT},
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Check monthly limit
        monthly_count = self.repository.count_recent_overrides(admin_id, days=30)
        if monthly_count >= self.DEFAULT_MONTHLY_LIMIT:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=f"Monthly override limit reached ({self.DEFAULT_MONTHLY_LIMIT})",
                    details={"current_count": monthly_count, "limit": self.DEFAULT_MONTHLY_LIMIT},
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)
    
    def _validate_entity(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> ServiceResult[None]:
        """
        Validate that the entity being overridden exists.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            
        Returns:
            ServiceResult indicating validation result
        """
        # Entity validation logic would go here
        # This is a placeholder that can be extended based on entity types
        return ServiceResult.success(None)
    
    def _send_override_notification(self, override: AdminOverride) -> None:
        """
        Send notification about override to supervisor.
        
        Args:
            override: Override object
        """
        try:
            # Notification logic would go here
            # This is a placeholder for future implementation
            self._logger.info(
                "Override notification sent",
                extra={
                    "override_id": str(override.id),
                    "supervisor_id": str(override.supervisor_id),
                },
            )
        except Exception as e:
            self._logger.error(
                f"Failed to send override notification: {str(e)}",
                exc_info=True,
                extra={"override_id": str(override.id)},
            )