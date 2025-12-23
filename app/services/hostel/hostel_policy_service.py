# --- File: C:\Hostel-Main\app\services\hostel\hostel_policy_service.py ---
"""
Hostel policy service (documents, acknowledgments, violations).

Manages hostel policies, compliance tracking, acknowledgment workflows,
and violation reporting system.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.hostel import HostelPolicyRepository
from app.models.hostel.hostel_policy import (
    HostelPolicy as HostelPolicyModel,
    PolicyAcknowledgment as PolicyAcknowledgmentModel,
    PolicyViolation as PolicyViolationModel
)
from app.schemas.hostel.hostel_policy import (
    PolicyCreate,
    PolicyUpdate,
    PolicyAckRequest,
    ViolationCreate,
)
from app.services.hostel.constants import (
    ERROR_POLICY_NOT_FOUND,
    SUCCESS_POLICY_CREATED,
    SUCCESS_POLICY_UPDATED,
    SUCCESS_POLICY_ACKNOWLEDGED,
    SUCCESS_VIOLATION_RECORDED,
)

logger = logging.getLogger(__name__)


class HostelPolicyService(BaseService[HostelPolicyModel, HostelPolicyRepository]):
    """
    Manage policy documents and compliance actions.
    
    Provides functionality for:
    - Policy document management
    - User acknowledgment tracking
    - Violation reporting and tracking
    - Compliance analytics
    - Policy versioning
    """

    # Policy types
    POLICY_TYPES = {
        'terms_of_service',
        'house_rules',
        'privacy_policy',
        'cancellation_policy',
        'safety_guidelines',
        'community_standards',
        'guest_code_of_conduct'
    }

    # Violation severity levels
    VIOLATION_SEVERITIES = {
        'low': 1,
        'medium': 2,
        'high': 3,
        'critical': 4
    }

    def __init__(self, repository: HostelPolicyRepository, db_session: Session):
        """
        Initialize hostel policy service.
        
        Args:
            repository: Hostel policy repository instance
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self._policy_cache: Dict[UUID, HostelPolicyModel] = {}
        self._acknowledgment_cache: Dict[str, bool] = {}

    # =========================================================================
    # Policy CRUD Operations
    # =========================================================================

    def create_policy(
        self,
        request: PolicyCreate,
        created_by: Optional[UUID] = None,
        auto_version: bool = True,
    ) -> ServiceResult[HostelPolicyModel]:
        """
        Create a new policy with automatic versioning.
        
        Args:
            request: Policy creation request
            created_by: UUID of the user creating the policy
            auto_version: Whether to automatically version existing policies
            
        Returns:
            ServiceResult containing created policy or error
        """
        try:
            logger.info(
                f"Creating policy: {request.title} for hostel {request.hostel_id}"
            )
            
            # Validate request
            validation_error = self._validate_policy_create(request)
            if validation_error:
                return validation_error
            
            # Check for existing policy and version if needed
            if auto_version and hasattr(request, 'policy_type'):
                existing = self._get_active_policy_by_type(
                    request.hostel_id,
                    request.policy_type
                )
                if existing:
                    # Archive existing policy
                    self._archive_policy(existing.id)
                    logger.info(f"Archived existing policy: {existing.id}")
            
            # Create new policy
            policy = self.repository.create_policy(request, created_by=created_by)
            self.db.flush()
            
            # Set version number
            if hasattr(policy, 'version'):
                policy.version = self._get_next_version(
                    request.hostel_id,
                    request.policy_type if hasattr(request, 'policy_type') else None
                )
            
            self.db.commit()
            
            logger.info(f"Policy created successfully: {policy.id}")
            return ServiceResult.success(policy, message=SUCCESS_POLICY_CREATED)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating policy: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Policy with this identifier already exists",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create hostel policy")

    def update_policy(
        self,
        policy_id: UUID,
        request: PolicyUpdate,
        updated_by: Optional[UUID] = None,
        create_version: bool = False,
    ) -> ServiceResult[HostelPolicyModel]:
        """
        Update existing policy with optional versioning.
        
        Args:
            policy_id: UUID of the policy to update
            request: Update request with fields to modify
            updated_by: UUID of the user performing the update
            create_version: Whether to create a new version instead of updating
            
        Returns:
            ServiceResult containing updated policy or error
        """
        try:
            logger.info(f"Updating policy: {policy_id}")
            
            # Check existence
            existing = self.repository.get_by_id(policy_id)
            if not existing:
                return self._not_found_error(ERROR_POLICY_NOT_FOUND, policy_id)
            
            # If creating new version, create instead of update
            if create_version:
                # Archive current policy
                self._archive_policy(policy_id)
                
                # Create new version based on update
                new_policy_data = self._merge_update_with_existing(existing, request)
                return self.create_policy(
                    new_policy_data,
                    created_by=updated_by,
                    auto_version=False
                )
            
            # Validate update
            validation_error = self._validate_policy_update(request, existing)
            if validation_error:
                return validation_error
            
            # Perform update
            policy = self.repository.update_policy(
                policy_id,
                request,
                updated_by=updated_by
            )
            self.db.flush()
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_policy_cache(policy_id)
            
            logger.info(f"Policy updated successfully: {policy_id}")
            return ServiceResult.success(policy, message=SUCCESS_POLICY_UPDATED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update hostel policy", policy_id)

    def delete_policy(
        self,
        policy_id: UUID,
        soft_delete: bool = True,
        deleted_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Delete a policy with optional soft delete.
        
        Args:
            policy_id: UUID of the policy to delete
            soft_delete: Whether to perform soft delete (archive)
            deleted_by: UUID of the user performing the deletion
            
        Returns:
            ServiceResult containing success status or error
        """
        try:
            logger.info(f"Deleting policy: {policy_id} (soft={soft_delete})")
            
            # Check existence
            existing = self.repository.get_by_id(policy_id)
            if not existing:
                return self._not_found_error(ERROR_POLICY_NOT_FOUND, policy_id)
            
            # Check if policy has acknowledgments
            ack_count = self._count_acknowledgments(policy_id)
            if ack_count > 0 and not soft_delete:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Cannot hard delete policy with {ack_count} acknowledgments",
                        severity=ErrorSeverity.WARNING,
                        details={"acknowledgment_count": ack_count}
                    )
                )
            
            # Perform deletion
            if soft_delete:
                self._archive_policy(policy_id)
            else:
                self.repository.delete(policy_id)
            
            self.db.flush()
            self.db.commit()
            
            # Clear cache
            self._invalidate_policy_cache(policy_id)
            
            logger.info(f"Policy deleted successfully: {policy_id}")
            return ServiceResult.success(True, message="Policy deleted successfully")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete hostel policy", policy_id)

    def list_policies(
        self,
        hostel_id: UUID,
        active_only: bool = True,
        policy_type: Optional[str] = None,
        include_archived: bool = False,
    ) -> ServiceResult[List[HostelPolicyModel]]:
        """
        List policies for a hostel with filtering.
        
        Args:
            hostel_id: UUID of the hostel
            active_only: Only return active policies
            policy_type: Filter by policy type
            include_archived: Include archived policies
            
        Returns:
            ServiceResult containing list of policies with metadata
        """
        try:
            logger.info(
                f"Listing policies for hostel {hostel_id}: "
                f"active={active_only}, type={policy_type}, "
                f"archived={include_archived}"
            )
            
            # Fetch policies
            items = self.repository.list_policies(
                hostel_id,
                active_only=active_only,
                policy_type=policy_type,
                include_archived=include_archived
            )
            
            # Prepare metadata
            metadata = {
                "count": len(items),
                "hostel_id": str(hostel_id),
                "active_only": active_only,
                "include_archived": include_archived,
            }
            
            if policy_type:
                metadata["policy_type"] = policy_type
            
            # Group by type
            grouped = {}
            for item in items:
                p_type = getattr(item, 'policy_type', 'general')
                if p_type not in grouped:
                    grouped[p_type] = []
                grouped[p_type].append(item)
            
            metadata["grouped_count"] = {k: len(v) for k, v in grouped.items()}
            
            return ServiceResult.success(items, metadata=metadata)
            
        except Exception as e:
            return self._handle_exception(e, "list hostel policies", hostel_id)

    # =========================================================================
    # Acknowledgment Operations
    # =========================================================================

    def acknowledge(
        self,
        request: PolicyAckRequest,
        acknowledged_by: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> ServiceResult[PolicyAcknowledgmentModel]:
        """
        Record user acknowledgment of a policy.
        
        Args:
            request: Policy acknowledgment request
            acknowledged_by: UUID of the user acknowledging (overrides request)
            ip_address: IP address of the acknowledgment
            
        Returns:
            ServiceResult containing acknowledgment record or error
        """
        try:
            user_id = acknowledged_by or request.user_id
            logger.info(
                f"Recording policy acknowledgment: user={user_id}, "
                f"policy={request.policy_id}"
            )
            
            # Validate policy exists and is active
            policy = self.repository.get_by_id(request.policy_id)
            if not policy:
                return self._not_found_error(ERROR_POLICY_NOT_FOUND, request.policy_id)
            
            if hasattr(policy, 'is_active') and not policy.is_active:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Cannot acknowledge inactive policy",
                        severity=ErrorSeverity.WARNING
                    )
                )
            
            # Check for duplicate acknowledgment
            cache_key = f"{user_id}_{request.policy_id}"
            if cache_key in self._acknowledgment_cache:
                if self._acknowledgment_cache[cache_key]:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="Policy already acknowledged by this user",
                            severity=ErrorSeverity.WARNING
                        )
                    )
            
            # Create acknowledgment
            ack = self.repository.acknowledge_policy(request)
            self.db.flush()
            
            # Store additional metadata
            if ip_address and hasattr(ack, 'metadata'):
                ack.metadata = ack.metadata or {}
                ack.metadata['ip_address'] = ip_address
                ack.metadata['acknowledged_at'] = datetime.utcnow().isoformat()
            
            self.db.commit()
            
            # Update cache
            self._acknowledgment_cache[cache_key] = True
            
            logger.info(f"Policy acknowledgment recorded: {ack.id}")
            return ServiceResult.success(ack, message=SUCCESS_POLICY_ACKNOWLEDGED)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error acknowledging policy: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Policy already acknowledged by this user",
                    severity=ErrorSeverity.WARNING,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "acknowledge policy")

    def check_acknowledgment(
        self,
        user_id: UUID,
        policy_id: UUID,
        use_cache: bool = True,
    ) -> ServiceResult[bool]:
        """
        Check if a user has acknowledged a specific policy.
        
        Args:
            user_id: UUID of the user
            policy_id: UUID of the policy
            use_cache: Whether to use cached data
            
        Returns:
            ServiceResult containing acknowledgment status
        """
        try:
            # Check cache first
            cache_key = f"{user_id}_{policy_id}"
            if use_cache and cache_key in self._acknowledgment_cache:
                return ServiceResult.success(self._acknowledgment_cache[cache_key])
            
            # Query database
            acknowledged = self.repository.check_acknowledgment(user_id, policy_id)
            
            # Update cache
            if use_cache:
                self._acknowledgment_cache[cache_key] = acknowledged
            
            return ServiceResult.success(acknowledged)
            
        except Exception as e:
            return self._handle_exception(e, "check policy acknowledgment")

    def get_acknowledgment_status(
        self,
        user_id: UUID,
        hostel_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get comprehensive acknowledgment status for a user across all hostel policies.
        
        Args:
            user_id: UUID of the user
            hostel_id: UUID of the hostel
            
        Returns:
            ServiceResult containing acknowledgment status summary
        """
        try:
            logger.info(
                f"Getting acknowledgment status: user={user_id}, hostel={hostel_id}"
            )
            
            # Get all active policies for hostel
            policies_result = self.list_policies(hostel_id, active_only=True)
            if not policies_result.success:
                return policies_result
            
            policies = policies_result.data
            
            # Check acknowledgment for each policy
            status = {
                "user_id": str(user_id),
                "hostel_id": str(hostel_id),
                "total_policies": len(policies),
                "acknowledged_count": 0,
                "pending_count": 0,
                "policies": []
            }
            
            for policy in policies:
                ack_result = self.check_acknowledgment(user_id, policy.id)
                is_acknowledged = ack_result.data if ack_result.success else False
                
                policy_status = {
                    "policy_id": str(policy.id),
                    "policy_type": getattr(policy, 'policy_type', None),
                    "title": policy.title,
                    "acknowledged": is_acknowledged,
                }
                
                if is_acknowledged:
                    status["acknowledged_count"] += 1
                    # Get acknowledgment details
                    ack = self.repository.get_acknowledgment(user_id, policy.id)
                    if ack:
                        policy_status["acknowledged_at"] = ack.acknowledged_at.isoformat()
                else:
                    status["pending_count"] += 1
                
                status["policies"].append(policy_status)
            
            status["compliance_rate"] = (
                status["acknowledged_count"] / status["total_policies"] * 100
                if status["total_policies"] > 0 else 0
            )
            
            return ServiceResult.success(status)
            
        except Exception as e:
            return self._handle_exception(e, "get acknowledgment status")

    # =========================================================================
    # Violation Operations
    # =========================================================================

    def record_violation(
        self,
        request: ViolationCreate,
        recorded_by: Optional[UUID] = None,
        auto_notify: bool = True,
    ) -> ServiceResult[PolicyViolationModel]:
        """
        Record a policy violation with optional notifications.
        
        Args:
            request: Violation creation request
            recorded_by: UUID of the user recording the violation
            auto_notify: Whether to automatically notify relevant parties
            
        Returns:
            ServiceResult containing violation record or error
        """
        try:
            logger.info(
                f"Recording policy violation: policy={request.policy_id}, "
                f"user={request.violator_id}, severity={request.severity}"
            )
            
            # Validate policy exists
            policy = self.repository.get_by_id(request.policy_id)
            if not policy:
                return self._not_found_error(ERROR_POLICY_NOT_FOUND, request.policy_id)
            
            # Validate severity
            if hasattr(request, 'severity'):
                if request.severity not in self.VIOLATION_SEVERITIES:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Invalid severity level: {request.severity}",
                            severity=ErrorSeverity.ERROR,
                            details={"valid_severities": list(self.VIOLATION_SEVERITIES.keys())}
                        )
                    )
            
            # Create violation record
            violation = self.repository.record_violation(
                request,
                recorded_by=recorded_by
            )
            self.db.flush()
            
            # Check for repeat violations
            violation_count = self._count_user_violations(
                request.violator_id,
                request.policy_id
            )
            
            if hasattr(violation, 'metadata'):
                violation.metadata = violation.metadata or {}
                violation.metadata['violation_count'] = violation_count
                violation.metadata['is_repeat_offender'] = violation_count > 1
            
            self.db.commit()
            
            # Trigger notifications if enabled
            if auto_notify:
                self._notify_violation(violation)
            
            logger.info(f"Policy violation recorded: {violation.id}")
            return ServiceResult.success(violation, message=SUCCESS_VIOLATION_RECORDED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "record policy violation")

    def get_violations(
        self,
        hostel_id: Optional[UUID] = None,
        policy_id: Optional[UUID] = None,
        violator_id: Optional[UUID] = None,
        severity: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        resolved_only: Optional[bool] = None,
    ) -> ServiceResult[List[PolicyViolationModel]]:
        """
        Get policy violations with comprehensive filtering.
        
        Args:
            hostel_id: Filter by hostel
            policy_id: Filter by policy
            violator_id: Filter by violator
            severity: Filter by severity level
            start_date: Filter violations after this date
            end_date: Filter violations before this date
            resolved_only: Filter by resolution status
            
        Returns:
            ServiceResult containing list of violations with metadata
        """
        try:
            logger.info(
                f"Fetching violations: hostel={hostel_id}, policy={policy_id}, "
                f"violator={violator_id}, severity={severity}"
            )
            
            violations = self.repository.get_violations(
                hostel_id=hostel_id,
                policy_id=policy_id,
                violator_id=violator_id,
                severity=severity,
                start_date=start_date,
                end_date=end_date,
                resolved_only=resolved_only
            )
            
            # Calculate statistics
            metadata = {
                "count": len(violations),
                "by_severity": {},
                "resolved_count": 0,
                "pending_count": 0,
            }
            
            for violation in violations:
                # Count by severity
                sev = getattr(violation, 'severity', 'unknown')
                metadata["by_severity"][sev] = metadata["by_severity"].get(sev, 0) + 1
                
                # Count by resolution status
                if getattr(violation, 'is_resolved', False):
                    metadata["resolved_count"] += 1
                else:
                    metadata["pending_count"] += 1
            
            return ServiceResult.success(violations, metadata=metadata)
            
        except Exception as e:
            return self._handle_exception(e, "get policy violations")

    def resolve_violation(
        self,
        violation_id: UUID,
        resolution_notes: Optional[str] = None,
        resolved_by: Optional[UUID] = None,
    ) -> ServiceResult[PolicyViolationModel]:
        """
        Mark a violation as resolved.
        
        Args:
            violation_id: UUID of the violation
            resolution_notes: Notes about the resolution
            resolved_by: UUID of the user resolving the violation
            
        Returns:
            ServiceResult containing updated violation or error
        """
        try:
            logger.info(f"Resolving violation: {violation_id}")
            
            violation = self.repository.get_violation_by_id(violation_id)
            if not violation:
                return self._not_found_error("Violation not found", violation_id)
            
            if getattr(violation, 'is_resolved', False):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Violation is already resolved",
                        severity=ErrorSeverity.WARNING
                    )
                )
            
            # Mark as resolved
            violation.is_resolved = True
            violation.resolved_at = datetime.utcnow()
            violation.resolved_by = resolved_by
            
            if resolution_notes:
                violation.resolution_notes = resolution_notes
            
            self.db.flush()
            self.db.commit()
            
            logger.info(f"Violation resolved: {violation_id}")
            return ServiceResult.success(
                violation,
                message="Violation resolved successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "resolve violation", violation_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_policy_create(
        self,
        request: PolicyCreate
    ) -> Optional[ServiceResult[HostelPolicyModel]]:
        """Validate policy creation request."""
        if not request.title or len(request.title.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Policy title is required",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        if hasattr(request, 'policy_type') and request.policy_type:
            if request.policy_type not in self.POLICY_TYPES:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid policy type: {request.policy_type}",
                        severity=ErrorSeverity.ERROR,
                        details={"valid_types": list(self.POLICY_TYPES)}
                    )
                )
        
        return None

    def _validate_policy_update(
        self,
        request: PolicyUpdate,
        existing: HostelPolicyModel
    ) -> Optional[ServiceResult[HostelPolicyModel]]:
        """Validate policy update request."""
        if request.title is not None and len(request.title.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Policy title cannot be empty",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        return None

    def _get_active_policy_by_type(
        self,
        hostel_id: UUID,
        policy_type: str
    ) -> Optional[HostelPolicyModel]:
        """Get active policy of a specific type."""
        try:
            return self.repository.get_active_policy_by_type(hostel_id, policy_type)
        except Exception as e:
            logger.error(f"Error getting active policy: {str(e)}")
            return None

    def _archive_policy(self, policy_id: UUID) -> None:
        """Archive a policy."""
        try:
            policy = self.repository.get_by_id(policy_id)
            if policy:
                policy.is_active = False
                policy.archived_at = datetime.utcnow()
                self.db.flush()
        except Exception as e:
            logger.error(f"Error archiving policy: {str(e)}")

    def _get_next_version(
        self,
        hostel_id: UUID,
        policy_type: Optional[str]
    ) -> int:
        """Get the next version number for a policy."""
        try:
            return self.repository.get_next_version(hostel_id, policy_type)
        except Exception as e:
            logger.error(f"Error getting next version: {str(e)}")
            return 1

    def _merge_update_with_existing(
        self,
        existing: HostelPolicyModel,
        update: PolicyUpdate
    ) -> PolicyCreate:
        """Merge update data with existing policy for versioning."""
        # This is a placeholder - implement actual merge logic
        merged = PolicyCreate(
            hostel_id=existing.hostel_id,
            title=update.title if update.title else existing.title,
            content=update.content if update.content else existing.content,
        )
        return merged

    def _count_acknowledgments(self, policy_id: UUID) -> int:
        """Count acknowledgments for a policy."""
        try:
            return self.repository.count_acknowledgments(policy_id)
        except Exception as e:
            logger.error(f"Error counting acknowledgments: {str(e)}")
            return 0

    def _count_user_violations(
        self,
        user_id: UUID,
        policy_id: UUID
    ) -> int:
        """Count violations for a user on a specific policy."""
        try:
            violations = self.repository.get_violations(
                policy_id=policy_id,
                violator_id=user_id
            )
            return len(violations)
        except Exception as e:
            logger.error(f"Error counting violations: {str(e)}")
            return 0

    def _notify_violation(self, violation: PolicyViolationModel) -> None:
        """Send notifications for a violation."""
        try:
            # This is a placeholder for notification logic
            # Integrate with your notification service
            logger.info(f"Sending violation notifications for: {violation.id}")
        except Exception as e:
            logger.error(f"Error sending violation notifications: {str(e)}")

    def _not_found_error(
        self,
        message: str,
        entity_id: UUID
    ) -> ServiceResult[HostelPolicyModel]:
        """Create a standardized not found error response."""
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.NOT_FOUND,
                message=message,
                severity=ErrorSeverity.ERROR,
                details={"entity_id": str(entity_id)}
            )
        )

    def _invalidate_policy_cache(self, policy_id: UUID) -> None:
        """Clear cached data for a specific policy."""
        if policy_id in self._policy_cache:
            del self._policy_cache[policy_id]
            logger.debug(f"Policy cache invalidated: {policy_id}")
        
        # Also clear acknowledgment cache for this policy
        keys_to_remove = [
            k for k in self._acknowledgment_cache.keys()
            if k.endswith(f"_{policy_id}")
        ]
        for key in keys_to_remove:
            del self._acknowledgment_cache[key]

    def clear_cache(self) -> None:
        """Clear all cached policy data."""
        self._policy_cache.clear()
        self._acknowledgment_cache.clear()
        logger.info("All policy cache cleared")