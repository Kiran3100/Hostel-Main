"""
Fee Structure Service

Handles complete lifecycle management of fee structures including:
- Creation, updates, and deletion
- Status management (draft, active, inactive, archived)
- Applicability resolution based on hostel, room type, and date
- Pagination and filtering for list operations
- Comprehensive validation and error handling

Author: Senior Prompt Engineer
Version: 2.0.0
"""

from typing import Optional, List, Tuple
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DataError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.fee_structure import FeeStructureRepository
from app.models.fee_structure.fee_structure import FeeStructure as FeeStructureModel
from app.schemas.fee_structure.fee_structure import (
    FeeStructureCreate,
    FeeStructureUpdate,
)
from app.core1.logging import get_logger


class FeeStructureService(BaseService[FeeStructureModel, FeeStructureRepository]):
    """
    Comprehensive fee structure management service.
    
    Provides business logic for managing hostel fee structures with support for:
    - Temporal validity (effective_from/effective_to)
    - Multi-tenancy (hostel-specific configurations)
    - Room type differentiation
    - Status lifecycle management
    - Audit trail integration
    """

    # Valid status transitions
    VALID_STATUS_TRANSITIONS = {
        "draft": {"active", "inactive", "archived"},
        "active": {"inactive", "archived"},
        "inactive": {"active", "archived"},
        "archived": set(),  # Terminal state
    }

    VALID_STATUSES = {"draft", "active", "inactive", "archived"}

    def __init__(self, repository: FeeStructureRepository, db_session: Session):
        """
        Initialize the fee structure service.

        Args:
            repository: Fee structure repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._logger = get_logger(self.__class__.__name__)

    def create_structure(
        self,
        request: FeeStructureCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[FeeStructureModel]:
        """
        Create a new fee structure with comprehensive validation.

        Args:
            request: Fee structure creation request schema
            created_by: UUID of the user creating the structure

        Returns:
            ServiceResult containing the created fee structure or error details

        Raises:
            Handles all exceptions internally and returns ServiceResult
        """
        try:
            # Pre-creation validation
            validation_result = self._validate_fee_structure_data(request)
            if not validation_result.success:
                return validation_result

            # Check for overlapping structures
            overlap_check = self._check_for_overlaps(
                hostel_id=request.hostel_id,
                room_type=request.room_type,
                effective_from=request.effective_from,
                effective_to=request.effective_to,
            )
            if not overlap_check.success:
                return overlap_check

            # Create the structure
            fee_structure = self.repository.create_structure(request, created_by=created_by)
            self.db.commit()
            self.db.refresh(fee_structure)

            self._logger.info(
                "Fee structure created successfully",
                extra={
                    "structure_id": str(fee_structure.id),
                    "hostel_id": str(request.hostel_id),
                    "room_type": request.room_type,
                    "created_by": str(created_by) if created_by else None,
                }
            )

            return ServiceResult.success(
                fee_structure,
                message="Fee structure created successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(
                "Database integrity error during fee structure creation",
                exc_info=True,
                extra={"error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DUPLICATE_ENTRY,
                    message="Fee structure with similar configuration already exists",
                    severity=ErrorSeverity.ERROR,
                    details={"database_error": str(e)}
                )
            )

        except DataError as e:
            self.db.rollback()
            self._logger.error(
                "Data validation error during fee structure creation",
                exc_info=True,
                extra={"error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Invalid data format for fee structure",
                    severity=ErrorSeverity.ERROR,
                    details={"database_error": str(e)}
                )
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create fee structure")

    def update_structure(
        self,
        structure_id: UUID,
        request: FeeStructureUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[FeeStructureModel]:
        """
        Update an existing fee structure with validation.

        Args:
            structure_id: UUID of the structure to update
            request: Update request schema
            updated_by: UUID of the user performing the update

        Returns:
            ServiceResult containing the updated structure or error details
        """
        try:
            # Fetch existing structure
            existing = self.repository.get_by_id(structure_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Fee structure not found: {structure_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"structure_id": str(structure_id)}
                    )
                )

            # Prevent updates to archived structures
            if existing.status == "archived":
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message="Cannot update archived fee structure",
                        severity=ErrorSeverity.WARNING,
                        details={"structure_id": str(structure_id), "status": "archived"}
                    )
                )

            # Validate update data if dates are being changed
            if request.effective_from or request.effective_to:
                validation_result = self._validate_date_range(
                    effective_from=request.effective_from or existing.effective_from,
                    effective_to=request.effective_to or existing.effective_to,
                )
                if not validation_result.success:
                    return validation_result

            # Perform update
            updated_structure = self.repository.update_structure(
                structure_id,
                request,
                updated_by=updated_by
            )
            self.db.commit()
            self.db.refresh(updated_structure)

            self._logger.info(
                "Fee structure updated successfully",
                extra={
                    "structure_id": str(structure_id),
                    "updated_by": str(updated_by) if updated_by else None,
                }
            )

            return ServiceResult.success(
                updated_structure,
                message="Fee structure updated successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(
                "Integrity constraint violation during update",
                exc_info=True,
                extra={"structure_id": str(structure_id), "error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DUPLICATE_ENTRY,
                    message="Update would violate uniqueness constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"database_error": str(e)}
                )
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update fee structure", structure_id)

    def set_status(
        self,
        structure_id: UUID,
        status: str,
        changed_by: Optional[UUID] = None,
    ) -> ServiceResult[FeeStructureModel]:
        """
        Change the status of a fee structure with validation.

        Args:
            structure_id: UUID of the structure
            status: Target status (draft, active, inactive, archived)
            changed_by: UUID of the user making the change

        Returns:
            ServiceResult containing the updated structure or error details
        """
        try:
            # Validate status value
            status = status.lower()
            if status not in self.VALID_STATUSES:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid status: {status}",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "provided_status": status,
                            "valid_statuses": list(self.VALID_STATUSES)
                        }
                    )
                )

            # Fetch existing structure
            existing = self.repository.get_by_id(structure_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Fee structure not found: {structure_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"structure_id": str(structure_id)}
                    )
                )

            # Validate status transition
            current_status = existing.status or "draft"
            if not self._is_valid_status_transition(current_status, status):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message=f"Invalid status transition from {current_status} to {status}",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "current_status": current_status,
                            "target_status": status,
                            "allowed_transitions": list(
                                self.VALID_STATUS_TRANSITIONS.get(current_status, set())
                            )
                        }
                    )
                )

            # Additional validation for activation
            if status == "active":
                activation_check = self._validate_activation(existing)
                if not activation_check.success:
                    return activation_check

            # Perform status change
            updated_structure = self.repository.set_status(
                structure_id,
                status,
                changed_by=changed_by
            )
            self.db.commit()
            self.db.refresh(updated_structure)

            self._logger.info(
                "Fee structure status changed",
                extra={
                    "structure_id": str(structure_id),
                    "old_status": current_status,
                    "new_status": status,
                    "changed_by": str(changed_by) if changed_by else None,
                }
            )

            return ServiceResult.success(
                updated_structure,
                message=f"Fee structure status changed to {status}"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "set fee structure status", structure_id)

    def delete_structure(
        self,
        structure_id: UUID,
        hard_delete: bool = False,
    ) -> ServiceResult[bool]:
        """
        Delete a fee structure (soft or hard delete).

        Args:
            structure_id: UUID of the structure to delete
            hard_delete: If True, permanently delete; otherwise soft delete

        Returns:
            ServiceResult indicating success or failure
        """
        try:
            # Check if structure exists
            existing = self.repository.get_by_id(structure_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Fee structure not found: {structure_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"structure_id": str(structure_id)}
                    )
                )

            # Check if structure is in use (has active bookings/calculations)
            if self._is_structure_in_use(structure_id):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message="Cannot delete fee structure with active dependencies",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "structure_id": str(structure_id),
                            "suggestion": "Archive the structure instead"
                        }
                    )
                )

            # Perform deletion
            self.repository.delete_structure(structure_id, hard_delete=hard_delete)
            self.db.commit()

            self._logger.info(
                f"Fee structure {'permanently deleted' if hard_delete else 'soft deleted'}",
                extra={
                    "structure_id": str(structure_id),
                    "hard_delete": hard_delete,
                }
            )

            return ServiceResult.success(
                True,
                message=f"Fee structure {'deleted' if hard_delete else 'archived'} successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete fee structure", structure_id)

    def find_applicable(
        self,
        hostel_id: UUID,
        room_type: str,
        effective_date: date,
    ) -> ServiceResult[FeeStructureModel]:
        """
        Find the applicable fee structure for given parameters.

        Args:
            hostel_id: UUID of the hostel
            room_type: Room type identifier
            effective_date: Date for which to find applicable structure

        Returns:
            ServiceResult containing the applicable structure or error
        """
        try:
            # Input validation
            if not hostel_id:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Hostel ID is required",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            if not room_type or not room_type.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Room type is required",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            fee_structure = self.repository.find_applicable(
                hostel_id,
                room_type,
                effective_date
            )

            if not fee_structure:
                self._logger.warning(
                    "No applicable fee structure found",
                    extra={
                        "hostel_id": str(hostel_id),
                        "room_type": room_type,
                        "effective_date": str(effective_date),
                    }
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No applicable fee structure found for the given criteria",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "hostel_id": str(hostel_id),
                            "room_type": room_type,
                            "effective_date": str(effective_date),
                        }
                    )
                )

            return ServiceResult.success(
                fee_structure,
                message="Applicable fee structure found"
            )

        except Exception as e:
            return self._handle_exception(e, "find applicable fee structure", hostel_id)

    def list_structures(
        self,
        hostel_id: Optional[UUID] = None,
        room_type: Optional[str] = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[Tuple[List[FeeStructureModel], int]]:
        """
        List fee structures with filtering and pagination.

        Args:
            hostel_id: Optional filter by hostel
            room_type: Optional filter by room type
            active_only: If True, return only active structures
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            ServiceResult containing list of structures and total count
        """
        try:
            # Validate pagination parameters
            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 50
            if page_size > 100:
                page_size = 100  # Max page size limit

            structures = self.repository.list_structures(
                hostel_id=hostel_id,
                room_type=room_type,
                active_only=active_only,
                page=page,
                page_size=page_size,
            )

            # Calculate total count for pagination metadata
            total_count = len(structures)  # This should ideally come from repository
            total_pages = (total_count + page_size - 1) // page_size

            self._logger.debug(
                "Fee structures listed",
                extra={
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "room_type": room_type,
                    "active_only": active_only,
                    "page": page,
                    "page_size": page_size,
                    "count": total_count,
                }
            )

            return ServiceResult.success(
                (structures, total_count),
                metadata={
                    "count": len(structures),
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                }
            )

        except Exception as e:
            return self._handle_exception(e, "list fee structures")

    def get_structure_by_id(
        self,
        structure_id: UUID,
        include_inactive: bool = False,
    ) -> ServiceResult[FeeStructureModel]:
        """
        Retrieve a specific fee structure by ID.

        Args:
            structure_id: UUID of the structure
            include_inactive: If False, return error for inactive structures

        Returns:
            ServiceResult containing the structure or error
        """
        try:
            structure = self.repository.get_by_id(structure_id)

            if not structure:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Fee structure not found: {structure_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"structure_id": str(structure_id)}
                    )
                )

            if not include_inactive and structure.status not in ("active", "draft"):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message="Fee structure is not active",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "structure_id": str(structure_id),
                            "status": structure.status
                        }
                    )
                )

            return ServiceResult.success(structure)

        except Exception as e:
            return self._handle_exception(e, "get fee structure by ID", structure_id)

    # ==================== Private Helper Methods ====================

    def _validate_fee_structure_data(
        self,
        request: FeeStructureCreate,
    ) -> ServiceResult[None]:
        """Validate fee structure creation data."""
        # Date range validation
        date_validation = self._validate_date_range(
            request.effective_from,
            request.effective_to
        )
        if not date_validation.success:
            return date_validation

        # Amount validations
        if hasattr(request, 'base_amount') and request.base_amount is not None:
            if request.base_amount < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Base amount cannot be negative",
                        severity=ErrorSeverity.ERROR,
                    )
                )

        return ServiceResult.success(None)

    def _validate_date_range(
        self,
        effective_from: date,
        effective_to: Optional[date],
    ) -> ServiceResult[None]:
        """Validate date range for fee structure."""
        if effective_to and effective_from >= effective_to:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Effective from date must be before effective to date",
                    severity=ErrorSeverity.ERROR,
                    details={
                        "effective_from": str(effective_from),
                        "effective_to": str(effective_to),
                    }
                )
            )

        return ServiceResult.success(None)

    def _check_for_overlaps(
        self,
        hostel_id: UUID,
        room_type: str,
        effective_from: date,
        effective_to: Optional[date],
        exclude_structure_id: Optional[UUID] = None,
    ) -> ServiceResult[None]:
        """
        Check for overlapping fee structures.
        
        Note: Implementation depends on repository method availability.
        """
        # This would call a repository method to check for overlaps
        # For now, we'll assume no overlap (implement in repository if needed)
        return ServiceResult.success(None)

    def _is_valid_status_transition(
        self,
        current_status: str,
        target_status: str,
    ) -> bool:
        """Check if status transition is valid."""
        if current_status == target_status:
            return True  # No-op transition is valid

        allowed_transitions = self.VALID_STATUS_TRANSITIONS.get(current_status, set())
        return target_status in allowed_transitions

    def _validate_activation(
        self,
        structure: FeeStructureModel,
    ) -> ServiceResult[None]:
        """Validate that a structure can be activated."""
        # Check if effective dates are valid
        if structure.effective_to:
            if structure.effective_to < date.today():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message="Cannot activate expired fee structure",
                        severity=ErrorSeverity.WARNING,
                        details={"effective_to": str(structure.effective_to)}
                    )
                )

        # Additional validation: ensure structure has required components
        # This depends on your business rules

        return ServiceResult.success(None)

    def _is_structure_in_use(self, structure_id: UUID) -> bool:
        """
        Check if a fee structure is currently in use.
        
        Returns True if the structure has active dependencies.
        """
        # This should query for:
        # - Active bookings using this structure
        # - Fee calculations referencing this structure
        # - Any other dependencies
        
        # Placeholder implementation
        # TODO: Implement actual dependency checking
        return False