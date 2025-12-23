"""
Hostel assignment service for admins.

Handles admin-to-hostel assignments, permissions, transfers,
and assignment lifecycle management.
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
from app.repositories.admin import (
    AdminHostelAssignmentRepository,
    AdminUserRepository,
)
from app.repositories.hostel import HostelRepository
from app.models.admin import (
    AdminHostelAssignment,
    AssignmentPermission,
    AssignmentHistory,
)
from app.schemas.admin.admin_hostel_assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    BulkAssignment,
    RevokeAssignment,
)


class HostelAssignmentService(
    BaseService[AdminHostelAssignment, AdminHostelAssignmentRepository]
):
    """
    Service for managing admin-to-hostel assignments.
    
    Responsibilities:
    - Assignment creation and lifecycle
    - Assignment permissions and overrides
    - Transfer between hostels
    - Assignment analytics and coverage
    - Bulk assignment operations
    """
    
    def __init__(
        self,
        repository: AdminHostelAssignmentRepository,
        admin_repository: AdminUserRepository,
        hostel_repository: HostelRepository,
        db_session: Session,
    ):
        """
        Initialize assignment service.
        
        Args:
            repository: Assignment repository
            admin_repository: Admin user repository
            hostel_repository: Hostel repository
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self.admin_repository = admin_repository
        self.hostel_repository = hostel_repository
    
    # =========================================================================
    # Assignment Management
    # =========================================================================
    
    def create_assignment(
        self,
        assignment_data: AssignmentCreate,
        assigned_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminHostelAssignment]:
        """
        Create a new hostel assignment for an admin.
        
        Validates:
        - Admin exists
        - Hostel exists
        - No duplicate active assignment
        - Multi-hostel capability
        
        Args:
            assignment_data: Assignment creation data
            assigned_by: ID of user creating the assignment
            
        Returns:
            ServiceResult containing created assignment or error
        """
        try:
            # Validate admin
            admin = self.admin_repository.get_by_id(assignment_data.admin_id)
            if not admin:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Admin user not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate hostel
            hostel = self.hostel_repository.get_by_id(assignment_data.hostel_id)
            if not hostel:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Hostel not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check for duplicate assignment
            existing = self.repository.get_active_assignment(
                assignment_data.admin_id,
                assignment_data.hostel_id,
            )
            if existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.ALREADY_EXISTS,
                        message="Active assignment already exists for this admin-hostel pair",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Validate multi-hostel capability
            multi_hostel_check = self._validate_multi_hostel_capability(
                admin,
                assignment_data.admin_id,
            )
            if not multi_hostel_check.is_success:
                return multi_hostel_check
            
            # Create assignment
            assignment = self.repository.create_assignment(
                assignment_data.model_dump(),
                assigned_by=assigned_by,
            )
            self.db.flush()
            
            # Create history entry
            self._create_history_entry(
                assignment.id,
                "created",
                assigned_by,
                details={"hostel_name": hostel.name, "admin_email": admin.user.email},
            )
            
            self.db.commit()
            
            self._logger.info(
                "Assignment created",
                extra={
                    "assignment_id": str(assignment.id),
                    "admin_id": str(assignment_data.admin_id),
                    "hostel_id": str(assignment_data.hostel_id),
                    "assigned_by": str(assigned_by) if assigned_by else None,
                },
            )
            
            return ServiceResult.success(
                assignment,
                message="Assignment created successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create assignment")
    
    def update_assignment(
        self,
        assignment_id: UUID,
        update_data: AssignmentUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminHostelAssignment]:
        """
        Update an existing assignment.
        
        Args:
            assignment_id: Assignment ID
            update_data: Update data
            updated_by: ID of user making update
            
        Returns:
            ServiceResult containing updated assignment
        """
        try:
            assignment = self.repository.get_by_id(assignment_id)
            if not assignment:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Assignment not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Store old state for history
            old_state = {
                "permission_level": assignment.permission_level,
                "is_primary": assignment.is_primary,
            }
            
            # Update assignment
            update_dict = update_data.model_dump(exclude_unset=True)
            updated_assignment = self.repository.update(assignment_id, update_dict)
            self.db.flush()
            
            # Create history entry
            self._create_history_entry(
                assignment_id,
                "updated",
                updated_by,
                details={"old_state": old_state, "changes": update_dict},
            )
            
            self.db.commit()
            
            self._logger.info(
                "Assignment updated",
                extra={
                    "assignment_id": str(assignment_id),
                    "updated_by": str(updated_by) if updated_by else None,
                    "changes": list(update_dict.keys()),
                },
            )
            
            return ServiceResult.success(
                updated_assignment,
                message="Assignment updated successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update assignment", assignment_id)
    
    def revoke_assignment(
        self,
        assignment_id: UUID,
        revoke_data: RevokeAssignment,
        revoked_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Revoke an assignment.
        
        Args:
            assignment_id: Assignment ID
            revoke_data: Revocation data
            revoked_by: ID of user revoking
            
        Returns:
            ServiceResult indicating success or error
        """
        try:
            assignment = self.repository.get_by_id(assignment_id)
            if not assignment:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Assignment not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check if already revoked
            if assignment.revoked_at:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Assignment already revoked",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Revoke assignment
            self.repository.revoke_assignment(
                assignment_id,
                revoke_data.revoke_reason,
                revoked_by,
            )
            self.db.flush()
            
            # Create history entry
            self._create_history_entry(
                assignment_id,
                "revoked",
                revoked_by,
                details={"reason": revoke_data.revoke_reason},
            )
            
            self.db.commit()
            
            self._logger.info(
                "Assignment revoked",
                extra={
                    "assignment_id": str(assignment_id),
                    "revoked_by": str(revoked_by) if revoked_by else None,
                    "reason": revoke_data.revoke_reason,
                },
            )
            
            return ServiceResult.success(True, message="Assignment revoked successfully")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "revoke assignment", assignment_id)
    
    def transfer_assignment(
        self,
        assignment_id: UUID,
        new_admin_id: UUID,
        transfer_reason: str,
        transferred_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminHostelAssignment]:
        """
        Transfer an assignment to a different admin.
        
        Args:
            assignment_id: Assignment ID
            new_admin_id: New admin user ID
            transfer_reason: Reason for transfer
            transferred_by: ID of user performing transfer
            
        Returns:
            ServiceResult containing new assignment
        """
        try:
            # Get original assignment
            original = self.repository.get_by_id(assignment_id)
            if not original:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Assignment not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate new admin
            new_admin = self.admin_repository.get_by_id(new_admin_id)
            if not new_admin:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="New admin not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Revoke original assignment
            self.repository.revoke_assignment(
                assignment_id,
                f"Transferred to admin {new_admin_id}: {transfer_reason}",
                transferred_by,
            )
            self.db.flush()
            
            # Create new assignment
            new_assignment_data = AssignmentCreate(
                admin_id=new_admin_id,
                hostel_id=original.hostel_id,
                permission_level=original.permission_level,
                permissions=original.permissions,
                is_primary=original.is_primary,
                assignment_notes=f"Transferred from admin {original.admin_id}: {transfer_reason}",
            )
            
            new_assignment = self.repository.create_assignment(
                new_assignment_data.model_dump(),
                assigned_by=transferred_by,
            )
            self.db.flush()
            
            # Create history entries
            self._create_history_entry(
                assignment_id,
                "transferred_from",
                transferred_by,
                details={
                    "new_admin_id": str(new_admin_id),
                    "new_assignment_id": str(new_assignment.id),
                    "reason": transfer_reason,
                },
            )
            
            self._create_history_entry(
                new_assignment.id,
                "transferred_to",
                transferred_by,
                details={
                    "old_admin_id": str(original.admin_id),
                    "old_assignment_id": str(assignment_id),
                    "reason": transfer_reason,
                },
            )
            
            self.db.commit()
            
            self._logger.info(
                "Assignment transferred",
                extra={
                    "old_assignment_id": str(assignment_id),
                    "new_assignment_id": str(new_assignment.id),
                    "old_admin_id": str(original.admin_id),
                    "new_admin_id": str(new_admin_id),
                    "transferred_by": str(transferred_by) if transferred_by else None,
                },
            )
            
            return ServiceResult.success(
                new_assignment,
                message="Assignment transferred successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "transfer assignment", assignment_id)
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    def bulk_assign(
        self,
        bulk_data: BulkAssignment,
        assigned_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Create multiple assignments for one admin.
        
        Args:
            bulk_data: Bulk assignment data
            assigned_by: ID of user creating assignments
            
        Returns:
            ServiceResult containing assignment summary
        """
        try:
            # Validate admin
            admin = self.admin_repository.get_by_id(bulk_data.admin_id)
            if not admin:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Admin user not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check multi-hostel capability
            if not admin.can_manage_multiple_hostels and len(bulk_data.hostel_ids) > 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Admin cannot manage multiple hostels",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            summary = {
                "total": len(bulk_data.hostel_ids),
                "success": 0,
                "failed": 0,
                "created_assignments": [],
                "errors": [],
            }
            
            for hostel_id in bulk_data.hostel_ids:
                # Create assignment for each hostel
                assignment_data = AssignmentCreate(
                    admin_id=bulk_data.admin_id,
                    hostel_id=hostel_id,
                    permission_level=bulk_data.permission_level,
                    permissions=bulk_data.permissions,
                    is_primary=(hostel_id == bulk_data.primary_hostel_id),
                    assignment_notes=bulk_data.assignment_notes,
                )
                
                result = self.create_assignment(assignment_data, assigned_by)
                
                if result.is_success:
                    summary["success"] += 1
                    summary["created_assignments"].append(str(result.data.id))
                else:
                    summary["failed"] += 1
                    summary["errors"].append({
                        "hostel_id": str(hostel_id),
                        "error": result.primary_error.message,
                    })
            
            self.db.commit()
            
            message = f"Bulk assignment completed: {summary['success']} succeeded, {summary['failed']} failed"
            
            self._logger.info(
                "Bulk assignment completed",
                extra={
                    "admin_id": str(bulk_data.admin_id),
                    "total": summary["total"],
                    "success": summary["success"],
                    "failed": summary["failed"],
                },
            )
            
            return ServiceResult.success(summary, message=message)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "bulk assign")
    
    def bulk_revoke(
        self,
        admin_id: UUID,
        hostel_ids: List[UUID],
        revoke_reason: str,
        revoked_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Revoke multiple assignments for an admin.
        
        Args:
            admin_id: Admin user ID
            hostel_ids: List of hostel IDs
            revoke_reason: Revocation reason
            revoked_by: ID of user revoking
            
        Returns:
            ServiceResult containing revocation summary
        """
        try:
            summary = {
                "total": len(hostel_ids),
                "success": 0,
                "failed": 0,
                "errors": [],
            }
            
            for hostel_id in hostel_ids:
                assignment = self.repository.get_active_assignment(admin_id, hostel_id)
                
                if not assignment:
                    summary["failed"] += 1
                    summary["errors"].append({
                        "hostel_id": str(hostel_id),
                        "error": "No active assignment found",
                    })
                    continue
                
                revoke_data = RevokeAssignment(revoke_reason=revoke_reason)
                result = self.revoke_assignment(assignment.id, revoke_data, revoked_by)
                
                if result.is_success:
                    summary["success"] += 1
                else:
                    summary["failed"] += 1
                    summary["errors"].append({
                        "hostel_id": str(hostel_id),
                        "error": result.primary_error.message,
                    })
            
            self.db.commit()
            
            return ServiceResult.success(
                summary,
                message=f"Bulk revocation completed: {summary['success']} succeeded, {summary['failed']} failed",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "bulk revoke")
    
    # =========================================================================
    # Assignment Queries
    # =========================================================================
    
    def get_admin_assignments(
        self,
        admin_id: UUID,
        active_only: bool = True,
        include_permissions: bool = False,
    ) -> ServiceResult[List[AdminHostelAssignment]]:
        """
        Get all assignments for an admin.
        
        Args:
            admin_id: Admin user ID
            active_only: Only return active assignments
            include_permissions: Include permission details
            
        Returns:
            ServiceResult containing list of assignments
        """
        try:
            assignments = self.repository.get_admin_assignments(
                admin_id,
                active_only=active_only,
            )
            
            return ServiceResult.success(
                assignments,
                message="Assignments retrieved successfully",
                metadata={
                    "count": len(assignments),
                    "admin_id": str(admin_id),
                    "active_only": active_only,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get admin assignments", admin_id)
    
    def get_hostel_admins(
        self,
        hostel_id: UUID,
        active_only: bool = True,
    ) -> ServiceResult[List[AdminHostelAssignment]]:
        """
        Get all admin assignments for a hostel.
        
        Args:
            hostel_id: Hostel ID
            active_only: Only return active assignments
            
        Returns:
            ServiceResult containing list of assignments
        """
        try:
            assignments = self.repository.get_hostel_assignments(
                hostel_id,
                active_only=active_only,
            )
            
            return ServiceResult.success(
                assignments,
                message="Hostel admins retrieved successfully",
                metadata={
                    "count": len(assignments),
                    "hostel_id": str(hostel_id),
                    "active_only": active_only,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get hostel admins", hostel_id)
    
    def get_primary_assignment(
        self,
        admin_id: UUID,
    ) -> ServiceResult[Optional[AdminHostelAssignment]]:
        """
        Get the primary hostel assignment for an admin.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult containing primary assignment or None
        """
        try:
            assignment = self.repository.get_primary_assignment(admin_id)
            
            return ServiceResult.success(
                assignment,
                message="Primary assignment retrieved" if assignment else "No primary assignment found",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get primary assignment", admin_id)
    
    # =========================================================================
    # Assignment Analytics
    # =========================================================================
    
    def get_assignment_coverage(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get assignment coverage statistics.
        
        Args:
            hostel_id: Optional hostel ID to scope to
            
        Returns:
            ServiceResult containing coverage statistics
        """
        try:
            coverage = self.repository.get_assignment_coverage(hostel_id)
            
            return ServiceResult.success(
                coverage,
                message="Coverage statistics retrieved successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get assignment coverage")
    
    def get_assignment_history(
        self,
        assignment_id: UUID,
        limit: int = 50,
    ) -> ServiceResult[List[AssignmentHistory]]:
        """
        Get history for a specific assignment.
        
        Args:
            assignment_id: Assignment ID
            limit: Maximum entries to return
            
        Returns:
            ServiceResult containing assignment history
        """
        try:
            history = self.repository.get_assignment_history(assignment_id, limit=limit)
            
            return ServiceResult.success(
                history,
                message="Assignment history retrieved successfully",
                metadata={"count": len(history)},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get assignment history", assignment_id)
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _validate_multi_hostel_capability(
        self,
        admin,
        admin_id: UUID,
    ) -> ServiceResult[None]:
        """
        Validate multi-hostel capability.
        
        Args:
            admin: Admin user object
            admin_id: Admin user ID
            
        Returns:
            ServiceResult indicating validation result
        """
        if not admin.can_manage_multiple_hostels:
            # Check if admin already has any assignment
            existing_assignments = self.repository.get_admin_assignments(
                admin_id,
                active_only=True,
            )
            if existing_assignments:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Admin cannot manage multiple hostels",
                        details={
                            "current_assignments": len(existing_assignments),
                            "can_manage_multiple": False,
                        },
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        return ServiceResult.success(None)
    
    def _create_history_entry(
        self,
        assignment_id: UUID,
        action: str,
        performed_by: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create an assignment history entry.
        
        Args:
            assignment_id: Assignment ID
            action: Action performed
            performed_by: User who performed action
            details: Additional details
        """
        try:
            history_data = {
                'assignment_id': assignment_id,
                'action': action,
                'performed_by': performed_by,
                'action_details': details or {},
                'timestamp': datetime.utcnow(),
            }
            
            self.repository.create_history_entry(history_data)
            self.db.flush()
            
        except Exception as e:
            self._logger.error(
                f"Failed to create history entry: {str(e)}",
                exc_info=True,
                extra={
                    "assignment_id": str(assignment_id),
                    "action": action,
                },
            )