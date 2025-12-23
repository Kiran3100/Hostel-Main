"""
Hostel context switching and session-level context service for admins.

Manages active hostel context, switch history, preferences, and snapshots.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.admin import (
    HostelContextRepository,
    AdminHostelAssignmentRepository,
    AdminPermissionsRepository,
)
from app.repositories.hostel import HostelRepository
from app.models.admin import (
    HostelContext,
    ContextSwitch,
    ContextPreference,
    ContextSnapshot,
)
from app.schemas.admin.hostel_context import (
    HostelSwitchRequest,
    ActiveHostelResponse,
)


class HostelContextService(BaseService[HostelContext, HostelContextRepository]):
    """
    Service for admin hostel context management.
    
    Responsibilities:
    - Activate/switch current hostel context
    - Track context switch history and analytics
    - Manage context preferences and snapshots
    - Provide active context view with permissions
    """
    
    def __init__(
        self,
        repository: HostelContextRepository,
        assignment_repository: AdminHostelAssignmentRepository,
        permissions_repository: AdminPermissionsRepository,
        hostel_repository: HostelRepository,
        db_session: Session,
    ):
        """
        Initialize context service.
        
        Args:
            repository: Context repository
            assignment_repository: Assignment repository
            permissions_repository: Permissions repository
            hostel_repository: Hostel repository
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self.assignment_repository = assignment_repository
        self.permissions_repository = permissions_repository
        self.hostel_repository = hostel_repository
    
    # =========================================================================
    # Active Context Management
    # =========================================================================
    
    def get_active_context(
        self,
        admin_id: UUID,
    ) -> ServiceResult[ActiveHostelResponse]:
        """
        Get the currently active hostel context for an admin.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult containing active context or error
        """
        try:
            context = self.repository.get_active_context(admin_id)
            if not context:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No active hostel context found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Get permissions for current context
            permissions = self.permissions_repository.get_admin_permissions(
                admin_id,
                context.hostel_id,
            )
            
            # Get quick stats
            quick_stats = self.repository.get_quick_stats(
                admin_id,
                context.hostel_id,
            )
            
            # Build response
            response = ActiveHostelResponse(
                admin_id=admin_id,
                active_hostel_id=context.hostel_id,
                active_hostel_name=context.hostel_name,
                previous_hostel_id=context.previous_hostel_id,
                previous_hostel_name=context.previous_hostel_name,
                switched_at=context.activated_at,
                permissions=permissions.to_dict() if permissions else {},
                quick_stats=quick_stats or {},
                dashboard_url=context.dashboard_url,
                message="Active hostel context loaded",
                suggested_actions=context.suggested_actions or [],
            )
            
            return ServiceResult.success(response)
            
        except Exception as e:
            return self._handle_exception(e, "get active hostel context", admin_id)
    
    def switch_hostel(
        self,
        admin_id: UUID,
        switch_request: HostelSwitchRequest,
    ) -> ServiceResult[ActiveHostelResponse]:
        """
        Switch active hostel context for an admin.
        
        Process:
        1. Validate hostel exists
        2. Verify admin has assignment
        3. Save current session if requested
        4. Update active context
        5. Record switch history
        6. Refresh dashboard cache if requested
        
        Args:
            admin_id: Admin user ID
            switch_request: Switch request data
            
        Returns:
            ServiceResult containing new active context
        """
        try:
            # Validate hostel exists
            hostel = self.hostel_repository.get_by_id(switch_request.hostel_id)
            if not hostel:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Hostel not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate admin has assignment
            assignment = self.assignment_repository.get_active_assignment(
                admin_id,
                switch_request.hostel_id,
            )
            if not assignment:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.FORBIDDEN,
                        message="Admin has no active assignment for target hostel",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Get previous context
            previous_context = self.repository.get_active_context(admin_id)
            previous_hostel_id = previous_context.hostel_id if previous_context else None
            
            # Save snapshot if requested
            if switch_request.save_current_session and previous_context:
                self._create_snapshot_from_context(previous_context)
            
            # Update active context
            context = self.repository.set_active_context(
                admin_id=admin_id,
                hostel_id=switch_request.hostel_id,
                return_url=switch_request.return_url,
                switch_reason=switch_request.switch_reason,
            )
            self.db.flush()
            
            # Record switch history
            self.repository.create_switch_record(
                admin_id=admin_id,
                from_hostel_id=previous_hostel_id,
                to_hostel_id=switch_request.hostel_id,
                reason=switch_request.switch_reason,
                trigger="manual",
            )
            self.db.flush()
            
            # Refresh dashboard cache if requested
            if switch_request.refresh_dashboard:
                self.repository.refresh_dashboard_cache(admin_id, switch_request.hostel_id)
            
            self.db.commit()
            
            # Build response
            permissions = self.permissions_repository.get_admin_permissions(
                admin_id,
                switch_request.hostel_id,
            )
            stats = self.repository.get_quick_stats(admin_id, switch_request.hostel_id)
            
            response = ActiveHostelResponse(
                admin_id=admin_id,
                active_hostel_id=switch_request.hostel_id,
                active_hostel_name=hostel.name,
                previous_hostel_id=previous_hostel_id,
                previous_hostel_name=previous_context.hostel_name if previous_context else None,
                switched_at=datetime.utcnow(),
                permissions=permissions.to_dict() if permissions else {},
                quick_stats=stats or {},
                dashboard_url=context.dashboard_url if context else None,
                message="Hostel switched successfully",
                suggested_actions=context.suggested_actions if context else [],
            )
            
            self._logger.info(
                "Hostel context switched",
                extra={
                    "admin_id": str(admin_id),
                    "from_hostel_id": str(previous_hostel_id) if previous_hostel_id else None,
                    "to_hostel_id": str(switch_request.hostel_id),
                    "reason": switch_request.switch_reason,
                },
            )
            
            return ServiceResult.success(response)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "switch hostel", admin_id)
    
    def clear_context(
        self,
        admin_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Clear active hostel context for an admin.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult indicating success
        """
        try:
            self.repository.clear_active_context(admin_id)
            self.db.commit()
            
            self._logger.info(
                "Hostel context cleared",
                extra={"admin_id": str(admin_id)},
            )
            
            return ServiceResult.success(True, message="Context cleared successfully")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "clear context", admin_id)
    
    # =========================================================================
    # Preferences Management
    # =========================================================================
    
    def set_preference(
        self,
        admin_id: UUID,
        preferences: Dict[str, Any],
    ) -> ServiceResult[ContextPreference]:
        """
        Save/update context UI preferences.
        
        Args:
            admin_id: Admin user ID
            preferences: Preference data
            
        Returns:
            ServiceResult containing saved preferences
        """
        try:
            preference = self.repository.upsert_preference(admin_id, preferences)
            self.db.commit()
            
            self._logger.info(
                "Context preferences updated",
                extra={"admin_id": str(admin_id)},
            )
            
            return ServiceResult.success(preference, message="Preferences saved")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "set context preference", admin_id)
    
    def get_preference(
        self,
        admin_id: UUID,
    ) -> ServiceResult[Optional[ContextPreference]]:
        """
        Get saved context UI preferences.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult containing preferences or None
        """
        try:
            preference = self.repository.get_preference(admin_id)
            
            return ServiceResult.success(
                preference,
                message="Preferences retrieved" if preference else "No preferences found",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get context preference", admin_id)
    
    # =========================================================================
    # Context History
    # =========================================================================
    
    def get_context_history(
        self,
        admin_id: UUID,
        days: int = 30,
        limit: int = 50,
    ) -> ServiceResult[List[ContextSwitch]]:
        """
        Get context switch history for an admin.
        
        Args:
            admin_id: Admin user ID
            days: Days to look back
            limit: Maximum entries to return
            
        Returns:
            ServiceResult containing switch history
        """
        try:
            switches = self.repository.get_context_switches(
                admin_id,
                days=days,
                limit=limit,
            )
            
            return ServiceResult.success(
                switches,
                message="Context history loaded",
                metadata={
                    "count": len(switches),
                    "days": days,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get context history", admin_id)
    
    def get_switch_statistics(
        self,
        admin_id: UUID,
        days: int = 30,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get context switch statistics.
        
        Args:
            admin_id: Admin user ID
            days: Days to analyze
            
        Returns:
            ServiceResult containing switch statistics
        """
        try:
            stats = self.repository.get_switch_statistics(admin_id, days=days)
            
            return ServiceResult.success(
                stats,
                message="Switch statistics retrieved",
                metadata={"days": days},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get switch statistics", admin_id)
    
    # =========================================================================
    # Snapshots
    # =========================================================================
    
    def create_snapshot(
        self,
        admin_id: UUID,
        snapshot_data: Dict[str, Any],
    ) -> ServiceResult[ContextSnapshot]:
        """
        Manually create a snapshot for current context.
        
        Args:
            admin_id: Admin user ID
            snapshot_data: Snapshot data
            
        Returns:
            ServiceResult containing created snapshot
        """
        try:
            context = self.repository.get_active_context(admin_id)
            if not context:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No active context to snapshot",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            snapshot = self.repository.create_snapshot(
                admin_id=admin_id,
                hostel_id=context.hostel_id,
                snapshot=snapshot_data,
            )
            self.db.commit()
            
            self._logger.info(
                "Context snapshot created",
                extra={
                    "admin_id": str(admin_id),
                    "hostel_id": str(context.hostel_id),
                },
            )
            
            return ServiceResult.success(snapshot, message="Snapshot created")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create snapshot", admin_id)
    
    def get_snapshots(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None,
        limit: int = 10,
    ) -> ServiceResult[List[ContextSnapshot]]:
        """
        Get context snapshots for an admin.
        
        Args:
            admin_id: Admin user ID
            hostel_id: Optional hostel filter
            limit: Maximum snapshots to return
            
        Returns:
            ServiceResult containing snapshots
        """
        try:
            snapshots = self.repository.get_snapshots(
                admin_id,
                hostel_id=hostel_id,
                limit=limit,
            )
            
            return ServiceResult.success(
                snapshots,
                message="Snapshots retrieved",
                metadata={"count": len(snapshots)},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get snapshots", admin_id)
    
    def restore_snapshot(
        self,
        snapshot_id: UUID,
        admin_id: UUID,
    ) -> ServiceResult[ActiveHostelResponse]:
        """
        Restore context from a snapshot.
        
        Args:
            snapshot_id: Snapshot ID
            admin_id: Admin user ID
            
        Returns:
            ServiceResult containing restored context
        """
        try:
            snapshot = self.repository.get_snapshot_by_id(snapshot_id)
            if not snapshot or snapshot.admin_id != admin_id:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Snapshot not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Switch to the hostel in the snapshot
            switch_request = HostelSwitchRequest(
                hostel_id=snapshot.hostel_id,
                switch_reason=f"Restored from snapshot {snapshot_id}",
                save_current_session=False,
                refresh_dashboard=True,
            )
            
            result = self.switch_hostel(admin_id, switch_request)
            
            if result.is_success:
                self._logger.info(
                    "Context restored from snapshot",
                    extra={
                        "admin_id": str(admin_id),
                        "snapshot_id": str(snapshot_id),
                        "hostel_id": str(snapshot.hostel_id),
                    },
                )
            
            return result
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "restore snapshot", snapshot_id)
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _create_snapshot_from_context(self, context: HostelContext) -> None:
        """
        Create a snapshot from current context.
        
        Args:
            context: Current context object
        """
        try:
            self.repository.create_snapshot(
                admin_id=context.admin_id,
                hostel_id=context.hostel_id,
                snapshot={
                    "dashboard_url": context.dashboard_url,
                    "suggested_actions": context.suggested_actions,
                    "switch_reason": context.switch_reason,
                    "activated_at": context.activated_at.isoformat() if context.activated_at else None,
                },
            )
            self.db.flush()
            
        except Exception as e:
            self._logger.error(
                "Failed to create snapshot from context",
                exc_info=True,
                extra={
                    "admin_id": str(context.admin_id),
                    "hostel_id": str(context.hostel_id),
                    "error": str(e),
                },
            )