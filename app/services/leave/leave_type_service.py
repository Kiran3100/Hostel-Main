"""
Leave Type and Policy Configuration Service Module

Manages leave type configurations, policies, and restrictions including:
- Leave type definitions and rules
- Hostel-level policy configuration
- Blackout date management
- Quota templates
- Policy validation

Version: 2.0.0
"""

from typing import Optional, List
from uuid import UUID
from datetime import date
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.leave.leave_type_repository import LeaveTypeRepository
from app.models.leave.leave_type import (
    LeaveTypeConfig as LeaveTypeConfigModel,
    LeavePolicy as LeavePolicyModel,
    LeaveBlackoutDate as LeaveBlackoutDateModel
)
from app.schemas.leave.leave_type import (
    LeaveTypeConfig,
    LeavePolicy,
    LeaveBlackoutDate
)

logger = logging.getLogger(__name__)


class LeaveTypeService(BaseService[LeaveTypeConfigModel, LeaveTypeRepository]):
    """
    Comprehensive service for leave type and policy management.
    
    Handles:
    - Leave type creation and configuration
    - Policy definition and updates
    - Blackout period management
    - Validation rules
    - Template management
    """

    def __init__(self, repository: LeaveTypeRepository, db_session: Session):
        """
        Initialize the leave type service.
        
        Args:
            repository: Leave type repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Leave Type Configuration Methods
    # -------------------------------------------------------------------------

    def create_type(
        self,
        hostel_id: UUID,
        config: LeaveTypeConfig,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[LeaveTypeConfig]:
        """
        Create a new leave type configuration for a hostel.
        
        Args:
            hostel_id: UUID of the hostel
            config: Leave type configuration data
            created_by: UUID of the user creating the type (for audit)
            
        Returns:
            ServiceResult containing created LeaveTypeConfig or error information
        """
        try:
            # Validate configuration
            validation_result = self._validate_type_config(config)
            if not validation_result.success:
                return validation_result
            
            self._logger.info(
                f"Creating leave type '{config.leave_type}' for hostel {hostel_id}"
            )
            
            # Create via repository
            saved = self.repository.create_type_config(
                hostel_id,
                config,
                created_by=created_by
            )
            
            if not saved:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to create leave type",
                        severity=ErrorSeverity.ERROR,
                        details={"hostel_id": str(hostel_id)}
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Leave type '{config.leave_type}' created successfully "
                f"for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                saved,
                message="Leave type created successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while creating leave type: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "create leave type", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while creating leave type: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "create leave type", hostel_id)

    def update_type(
        self,
        hostel_id: UUID,
        leave_type: str,
        config: LeaveTypeConfig,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[LeaveTypeConfig]:
        """
        Update an existing leave type configuration.
        
        Args:
            hostel_id: UUID of the hostel
            leave_type: Name of the leave type to update
            config: Updated configuration data
            updated_by: UUID of the user updating the type (for audit)
            
        Returns:
            ServiceResult containing updated LeaveTypeConfig or error information
        """
        try:
            # Validate configuration
            validation_result = self._validate_type_config(config)
            if not validation_result.success:
                return validation_result
            
            self._logger.info(
                f"Updating leave type '{leave_type}' for hostel {hostel_id}"
            )
            
            # Update via repository
            saved = self.repository.update_type_config(
                hostel_id,
                leave_type,
                config,
                updated_by=updated_by
            )
            
            if not saved:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Leave type '{leave_type}' not found",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "hostel_id": str(hostel_id),
                            "leave_type": leave_type
                        }
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Leave type '{leave_type}' updated successfully "
                f"for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                saved,
                message="Leave type updated successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while updating leave type: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update leave type", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while updating leave type: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update leave type", hostel_id)

    def list_types(
        self,
        hostel_id: UUID,
        active_only: bool = False,
    ) -> ServiceResult[List[LeaveTypeConfig]]:
        """
        List all leave type configurations for a hostel.
        
        Args:
            hostel_id: UUID of the hostel
            active_only: If True, return only active leave types
            
        Returns:
            ServiceResult containing list of LeaveTypeConfig or error information
        """
        try:
            self._logger.debug(
                f"Listing leave types for hostel {hostel_id} "
                f"(active_only={active_only})"
            )
            
            items = self.repository.list_type_configs(hostel_id)
            
            # Filter for active types if requested
            if active_only and items:
                items = [
                    item for item in items
                    if getattr(item, 'is_active', True)
                ]
            
            self._logger.debug(
                f"Retrieved {len(items)} leave types for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "hostel_id": str(hostel_id),
                    "active_only": active_only,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while listing leave types: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list leave types", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while listing leave types: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list leave types", hostel_id)

    def delete_type(
        self,
        hostel_id: UUID,
        leave_type: str,
        deleted_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Delete (or deactivate) a leave type configuration.
        
        Args:
            hostel_id: UUID of the hostel
            leave_type: Name of the leave type to delete
            deleted_by: UUID of the user deleting the type (for audit)
            
        Returns:
            ServiceResult containing success boolean or error information
        """
        try:
            self._logger.info(
                f"Deleting leave type '{leave_type}' for hostel {hostel_id}"
            )
            
            # This would need to be implemented in the repository
            # success = self.repository.delete_type_config(
            #     hostel_id,
            #     leave_type,
            #     deleted_by=deleted_by
            # )
            
            # Placeholder implementation
            success = False
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message=f"Failed to delete leave type '{leave_type}'",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "hostel_id": str(hostel_id),
                            "leave_type": leave_type
                        }
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Leave type '{leave_type}' deleted successfully "
                f"for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                True,
                message="Leave type deleted successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while deleting leave type: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "delete leave type", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while deleting leave type: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "delete leave type", hostel_id)

    # -------------------------------------------------------------------------
    # Leave Policy Methods
    # -------------------------------------------------------------------------

    def set_policy(
        self,
        hostel_id: UUID,
        policy: LeavePolicy,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[LeavePolicy]:
        """
        Set or update the leave policy for a hostel.
        
        Args:
            hostel_id: UUID of the hostel
            policy: Policy configuration data
            updated_by: UUID of the user updating the policy (for audit)
            
        Returns:
            ServiceResult containing saved LeavePolicy or error information
        """
        try:
            # Validate policy
            validation_result = self._validate_policy(policy)
            if not validation_result.success:
                return validation_result
            
            self._logger.info(
                f"Setting leave policy for hostel {hostel_id}"
            )
            
            # Save via repository
            saved = self.repository.set_policy(
                hostel_id,
                policy,
                updated_by=updated_by
            )
            
            if not saved:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to save leave policy",
                        severity=ErrorSeverity.ERROR,
                        details={"hostel_id": str(hostel_id)}
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Leave policy saved successfully for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                saved,
                message="Leave policy saved successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while setting leave policy: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "set leave policy", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while setting leave policy: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "set leave policy", hostel_id)

    def get_policy(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[LeavePolicy]:
        """
        Retrieve the current leave policy for a hostel.
        
        Args:
            hostel_id: UUID of the hostel
            
        Returns:
            ServiceResult containing LeavePolicy or error information
        """
        try:
            self._logger.debug(
                f"Retrieving leave policy for hostel {hostel_id}"
            )
            
            policy = self.repository.get_policy(hostel_id)
            
            if not policy:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Leave policy not found for hostel",
                        severity=ErrorSeverity.WARNING,
                        details={"hostel_id": str(hostel_id)}
                    )
                )
            
            return ServiceResult.success(
                policy,
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving leave policy: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave policy", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving leave policy: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave policy", hostel_id)

    # -------------------------------------------------------------------------
    # Blackout Date Methods
    # -------------------------------------------------------------------------

    def add_blackout(
        self,
        hostel_id: UUID,
        entry: LeaveBlackoutDate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[LeaveBlackoutDate]:
        """
        Add a blackout date period when leaves cannot be taken.
        
        Args:
            hostel_id: UUID of the hostel
            entry: Blackout date configuration
            created_by: UUID of the user creating the blackout (for audit)
            
        Returns:
            ServiceResult containing saved LeaveBlackoutDate or error information
        """
        try:
            # Validate blackout entry
            validation_result = self._validate_blackout(entry)
            if not validation_result.success:
                return validation_result
            
            self._logger.info(
                f"Adding blackout date for hostel {hostel_id} "
                f"from {entry.start_date} to {entry.end_date}"
            )
            
            # Save via repository
            saved = self.repository.add_blackout_date(
                hostel_id,
                entry,
                created_by=created_by
            )
            
            if not saved:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to add blackout date",
                        severity=ErrorSeverity.ERROR,
                        details={"hostel_id": str(hostel_id)}
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Blackout date added successfully for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                saved,
                message="Blackout date added successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while adding blackout date: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "add blackout date", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while adding blackout date: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "add blackout date", hostel_id)

    def remove_blackout(
        self,
        hostel_id: UUID,
        blackout_id: UUID,
        deleted_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Remove a blackout date period.
        
        Args:
            hostel_id: UUID of the hostel
            blackout_id: UUID of the blackout date entry to remove
            deleted_by: UUID of the user removing the blackout (for audit)
            
        Returns:
            ServiceResult containing success boolean or error information
        """
        try:
            self._logger.info(
                f"Removing blackout date {blackout_id} for hostel {hostel_id}"
            )
            
            # Remove via repository
            success = self.repository.remove_blackout_date(hostel_id, blackout_id)
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Blackout date not found",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "hostel_id": str(hostel_id),
                            "blackout_id": str(blackout_id)
                        }
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Blackout date {blackout_id} removed successfully "
                f"for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                True,
                message="Blackout date removed successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while removing blackout date: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "remove blackout date", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while removing blackout date: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "remove blackout date", hostel_id)

    def list_blackouts(
        self,
        hostel_id: UUID,
        active_only: bool = False,
        start_date: Optional[date] = None,
    ) -> ServiceResult[List[LeaveBlackoutDate]]:
        """
        List all blackout dates for a hostel.
        
        Args:
            hostel_id: UUID of the hostel
            active_only: If True, return only currently active blackouts
            start_date: Optional filter for blackouts on or after this date
            
        Returns:
            ServiceResult containing list of LeaveBlackoutDate or error information
        """
        try:
            self._logger.debug(
                f"Listing blackout dates for hostel {hostel_id} "
                f"(active_only={active_only})"
            )
            
            items = self.repository.list_blackout_dates(hostel_id)
            
            if items is None:
                items = []
            
            # Apply filters if requested
            if active_only or start_date:
                today = date.today()
                filtered_items = []
                
                for item in items:
                    # Skip if active_only and blackout has ended
                    if active_only and hasattr(item, 'end_date') and item.end_date < today:
                        continue
                    
                    # Skip if start_date filter and blackout ends before filter date
                    if start_date and hasattr(item, 'end_date') and item.end_date < start_date:
                        continue
                    
                    filtered_items.append(item)
                
                items = filtered_items
            
            self._logger.debug(
                f"Retrieved {len(items)} blackout dates for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "hostel_id": str(hostel_id),
                    "active_only": active_only,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while listing blackout dates: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list blackout dates", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while listing blackout dates: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list blackout dates", hostel_id)

    # -------------------------------------------------------------------------
    # Private Validation Methods
    # -------------------------------------------------------------------------

    def _validate_type_config(
        self,
        config: LeaveTypeConfig
    ) -> ServiceResult[None]:
        """
        Validate leave type configuration.
        
        Args:
            config: The configuration to validate
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Validate leave type name
        if not hasattr(config, 'leave_type') or not config.leave_type or not config.leave_type.strip():
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Leave type name is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Additional validation logic can be added here
        # - Max duration limits
        # - Advance notice requirements
        # - Documentation requirements
        
        return ServiceResult.success(None)

    def _validate_policy(
        self,
        policy: LeavePolicy
    ) -> ServiceResult[None]:
        """
        Validate leave policy configuration.
        
        Args:
            policy: The policy to validate
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Add policy validation logic here
        # - Maximum leave limits
        # - Approval workflow requirements
        # - Restriction rules
        
        return ServiceResult.success(None)

    def _validate_blackout(
        self,
        entry: LeaveBlackoutDate
    ) -> ServiceResult[None]:
        """
        Validate blackout date entry.
        
        Args:
            entry: The blackout entry to validate
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Validate date range
        if hasattr(entry, 'start_date') and hasattr(entry, 'end_date'):
            if entry.end_date < entry.start_date:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Blackout end date cannot be before start date",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "start_date": entry.start_date.isoformat(),
                            "end_date": entry.end_date.isoformat()
                        }
                    )
                )
        
        # Validate reason is provided
        if not hasattr(entry, 'reason') or not entry.reason or not entry.reason.strip():
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Blackout reason is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)