"""
Complaint resolution service: resolve/update/reopen/close.

Manages the complete resolution lifecycle of complaints including
resolution recording, updates, reopening, and final closure.
"""

from typing import Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.complaint.complaint_resolution_repository import ComplaintResolutionRepository
from app.models.complaint.complaint_resolution import ComplaintResolution as ComplaintResolutionModel
from app.schemas.complaint.complaint_resolution import (
    ResolutionRequest,
    ResolutionResponse,
    ResolutionUpdate,
    ReopenRequest,
    CloseRequest,
)

logger = logging.getLogger(__name__)


class ComplaintResolutionService(BaseService[ComplaintResolutionModel, ComplaintResolutionRepository]):
    """
    Resolve and update complaint resolution flows.
    
    Provides comprehensive resolution management including initial resolution,
    updates, reopening for additional work, and final closure.
    """

    def __init__(self, repository: ComplaintResolutionRepository, db_session: Session):
        """
        Initialize resolution service.
        
        Args:
            repository: Complaint resolution repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Resolution Operations
    # -------------------------------------------------------------------------

    def resolve(
        self,
        request: ResolutionRequest,
        resolved_by: Optional[UUID] = None,
    ) -> ServiceResult[ResolutionResponse]:
        """
        Mark a complaint as resolved with resolution details.
        
        Args:
            request: Resolution request data
            resolved_by: UUID of user resolving the complaint
            
        Returns:
            ServiceResult containing ResolutionResponse or error
        """
        try:
            self._logger.info(
                f"Resolving complaint {request.complaint_id}, resolved_by: {resolved_by}"
            )
            
            # Validate resolution request
            validation_result = self._validate_resolution(request)
            if not validation_result.success:
                return validation_result
            
            # Perform resolution
            response = self.repository.resolve(request, resolved_by=resolved_by)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(f"Complaint {request.complaint_id} resolved successfully")
            
            return ServiceResult.success(
                response,
                message="Complaint resolved successfully",
                metadata={
                    "complaint_id": str(request.complaint_id),
                    "resolved_at": datetime.utcnow().isoformat(),
                    "resolved_by": str(resolved_by) if resolved_by else None,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error resolving complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "resolve complaint", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error resolving complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "resolve complaint", request.complaint_id)

    def update_resolution(
        self,
        request: ResolutionUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[ResolutionResponse]:
        """
        Update resolution details for an already resolved complaint.
        
        Args:
            request: Resolution update data
            updated_by: UUID of user updating the resolution
            
        Returns:
            ServiceResult containing updated ResolutionResponse or error
        """
        try:
            self._logger.info(
                f"Updating resolution for complaint {request.complaint_id}, updated_by: {updated_by}"
            )
            
            # Validate update request
            validation_result = self._validate_resolution_update(request)
            if not validation_result.success:
                return validation_result
            
            # Update resolution
            response = self.repository.update_resolution(request, updated_by=updated_by)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Resolution updated successfully for complaint {request.complaint_id}"
            )
            
            return ServiceResult.success(
                response,
                message="Resolution updated successfully",
                metadata={
                    "complaint_id": str(request.complaint_id),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error updating resolution for complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update resolution", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error updating resolution for complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update resolution", request.complaint_id)

    # -------------------------------------------------------------------------
    # State Transition Operations
    # -------------------------------------------------------------------------

    def reopen(
        self,
        request: ReopenRequest,
        reopened_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Reopen a resolved complaint for additional work.
        
        Args:
            request: Reopen request data
            reopened_by: UUID of user reopening the complaint
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            self._logger.info(
                f"Reopening complaint {request.complaint_id}, reopened_by: {reopened_by}"
            )
            
            # Validate reopen request
            validation_result = self._validate_reopen(request)
            if not validation_result.success:
                return validation_result
            
            # Reopen complaint
            success = self.repository.reopen(request, reopened_by=reopened_by)
            
            # Commit transaction
            self.db.commit()
            
            if success:
                self._logger.info(f"Complaint {request.complaint_id} reopened successfully")
                return ServiceResult.success(
                    True,
                    message="Complaint reopened successfully",
                    metadata={
                        "complaint_id": str(request.complaint_id),
                        "reopened_at": datetime.utcnow().isoformat(),
                        "reason": request.reason if hasattr(request, 'reason') else None,
                    }
                )
            else:
                self._logger.warning(f"Failed to reopen complaint {request.complaint_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to reopen complaint",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error reopening complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "reopen complaint", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error reopening complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "reopen complaint", request.complaint_id)

    def close(
        self,
        request: CloseRequest,
        closed_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Permanently close a resolved complaint.
        
        Args:
            request: Close request data
            closed_by: UUID of user closing the complaint
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            self._logger.info(
                f"Closing complaint {request.complaint_id}, closed_by: {closed_by}"
            )
            
            # Validate close request
            validation_result = self._validate_close(request)
            if not validation_result.success:
                return validation_result
            
            # Close complaint
            success = self.repository.close(request, closed_by=closed_by)
            
            # Commit transaction
            self.db.commit()
            
            if success:
                self._logger.info(f"Complaint {request.complaint_id} closed successfully")
                return ServiceResult.success(
                    True,
                    message="Complaint closed successfully",
                    metadata={
                        "complaint_id": str(request.complaint_id),
                        "closed_at": datetime.utcnow().isoformat(),
                    }
                )
            else:
                self._logger.warning(f"Failed to close complaint {request.complaint_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to close complaint",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error closing complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "close complaint", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error closing complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "close complaint", request.complaint_id)

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_resolution(
        self,
        request: ResolutionRequest
    ) -> ServiceResult[None]:
        """
        Validate resolution request.
        
        Args:
            request: Resolution request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.complaint_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if hasattr(request, 'resolution_notes') and request.resolution_notes:
            if len(request.resolution_notes.strip()) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Resolution notes cannot be empty",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if len(request.resolution_notes) > 5000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Resolution notes exceed maximum length of 5000 characters",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        # Validate resolution type if provided
        if hasattr(request, 'resolution_type') and request.resolution_type:
            valid_types = ["FIXED", "WORKAROUND", "DUPLICATE", "CANNOT_REPRODUCE", "WONT_FIX"]
            if request.resolution_type not in valid_types:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid resolution type. Must be one of: {', '.join(valid_types)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        return ServiceResult.success(None)

    def _validate_resolution_update(
        self,
        request: ResolutionUpdate
    ) -> ServiceResult[None]:
        """
        Validate resolution update request.
        
        Args:
            request: Resolution update request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.complaint_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if hasattr(request, 'resolution_notes') and request.resolution_notes is not None:
            if len(request.resolution_notes) > 5000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Resolution notes exceed maximum length of 5000 characters",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        return ServiceResult.success(None)

    def _validate_reopen(
        self,
        request: ReopenRequest
    ) -> ServiceResult[None]:
        """
        Validate reopen request.
        
        Args:
            request: Reopen request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.complaint_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if hasattr(request, 'reason') and request.reason:
            if len(request.reason.strip()) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Reopen reason cannot be empty",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if len(request.reason) > 1000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Reopen reason exceeds maximum length of 1000 characters",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        else:
            # Reason should be mandatory for reopening
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Reason is required for reopening a complaint",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _validate_close(
        self,
        request: CloseRequest
    ) -> ServiceResult[None]:
        """
        Validate close request.
        
        Args:
            request: Close request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.complaint_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Add additional validation logic
        # For example: check if complaint is resolved before closing
        
        return ServiceResult.success(None)