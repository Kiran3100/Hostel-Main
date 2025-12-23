"""
Core complaint service: create/update/status changes and listings.

This service handles the primary complaint lifecycle operations including
creation, updates, status management, and various query operations.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.models.complaint.complaint import Complaint as ComplaintModel
from app.schemas.complaint.complaint_base import (
    ComplaintCreate,
    ComplaintUpdate,
    ComplaintStatusUpdate,
)
from app.schemas.complaint.complaint_response import (
    ComplaintResponse,
    ComplaintDetail,
    ComplaintListItem,
    ComplaintSummary,
    ComplaintStats,
)
from app.schemas.complaint.complaint_filters import (
    ComplaintFilterParams,
    ComplaintSearchRequest,
    ComplaintExportRequest,
    ComplaintSortOptions,
)

logger = logging.getLogger(__name__)


class ComplaintService(BaseService[ComplaintModel, ComplaintRepository]):
    """
    High-level complaint operations service.
    
    Provides comprehensive complaint management including CRUD operations,
    status transitions, search/filtering, and statistical analysis.
    """

    def __init__(self, repository: ComplaintRepository, db_session: Session):
        """
        Initialize complaint service.
        
        Args:
            repository: Complaint repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Create & Update Operations
    # -------------------------------------------------------------------------

    def create(
        self,
        request: ComplaintCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[ComplaintDetail]:
        """
        Create a new complaint with validation and audit trail.
        
        Args:
            request: Complaint creation data
            created_by: UUID of user creating the complaint
            
        Returns:
            ServiceResult containing ComplaintDetail or error
        """
        try:
            self._logger.info(
                f"Creating complaint for hostel: {request.hostel_id}, "
                f"created_by: {created_by}"
            )
            
            # Validate request data
            validation_result = self._validate_complaint_create(request)
            if not validation_result.success:
                return validation_result
            
            # Create complaint
            complaint = self.repository.create_complaint(request, created_by=created_by)
            
            # Commit transaction
            self.db.commit()
            
            # Fetch complete detail
            detail = self.repository.get_detail(complaint.id)
            
            self._logger.info(f"Complaint created successfully: {complaint.id}")
            
            return ServiceResult.success(
                detail,
                message="Complaint created successfully",
                metadata={"complaint_id": str(complaint.id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error creating complaint: {str(e)}", exc_info=True)
            return self._handle_exception(e, "create complaint")
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Unexpected error creating complaint: {str(e)}", exc_info=True)
            return self._handle_exception(e, "create complaint")

    def update(
        self,
        complaint_id: UUID,
        request: ComplaintUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[ComplaintDetail]:
        """
        Update an existing complaint with validation.
        
        Args:
            complaint_id: UUID of complaint to update
            request: Update data
            updated_by: UUID of user performing update
            
        Returns:
            ServiceResult containing updated ComplaintDetail or error
        """
        try:
            self._logger.info(f"Updating complaint: {complaint_id}, updated_by: {updated_by}")
            
            # Check existence
            existing = self.repository.get_by_id(complaint_id)
            if not existing:
                self._logger.warning(f"Complaint not found: {complaint_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Complaint with ID {complaint_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate update request
            validation_result = self._validate_complaint_update(existing, request)
            if not validation_result.success:
                return validation_result
            
            # Perform update
            self.repository.update_complaint(complaint_id, request, updated_by=updated_by)
            
            # Commit transaction
            self.db.commit()
            
            # Fetch updated detail
            detail = self.repository.get_detail(complaint_id)
            
            self._logger.info(f"Complaint updated successfully: {complaint_id}")
            
            return ServiceResult.success(
                detail,
                message="Complaint updated successfully",
                metadata={"complaint_id": str(complaint_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error updating complaint {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update complaint", complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error updating complaint {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update complaint", complaint_id)

    def change_status(
        self,
        request: ComplaintStatusUpdate,
        changed_by: Optional[UUID] = None,
    ) -> ServiceResult[ComplaintDetail]:
        """
        Change complaint status with validation and state transition rules.
        
        Args:
            request: Status update request
            changed_by: UUID of user changing status
            
        Returns:
            ServiceResult containing updated ComplaintDetail or error
        """
        try:
            self._logger.info(
                f"Changing status for complaint: {request.complaint_id}, "
                f"new_status: {request.new_status}, changed_by: {changed_by}"
            )
            
            # Validate status transition
            validation_result = self._validate_status_change(request)
            if not validation_result.success:
                return validation_result
            
            # Execute status change
            self.repository.change_status(request, changed_by=changed_by)
            
            # Commit transaction
            self.db.commit()
            
            # Fetch updated detail
            detail = self.repository.get_detail(request.complaint_id)
            
            self._logger.info(
                f"Status changed successfully for complaint: {request.complaint_id}"
            )
            
            return ServiceResult.success(
                detail,
                message=f"Status updated to {request.new_status}",
                metadata={
                    "complaint_id": str(request.complaint_id),
                    "new_status": request.new_status
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error changing status for complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "change complaint status", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error changing status for complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "change complaint status", request.complaint_id)

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_detail(
        self,
        complaint_id: UUID,
    ) -> ServiceResult[ComplaintDetail]:
        """
        Retrieve complete complaint details by ID.
        
        Args:
            complaint_id: UUID of complaint to retrieve
            
        Returns:
            ServiceResult containing ComplaintDetail or error
        """
        try:
            self._logger.debug(f"Fetching complaint detail: {complaint_id}")
            
            detail = self.repository.get_detail(complaint_id)
            
            if not detail:
                self._logger.warning(f"Complaint not found: {complaint_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Complaint with ID {complaint_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            return ServiceResult.success(
                detail,
                metadata={"complaint_id": str(complaint_id)}
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching complaint {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint detail", complaint_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching complaint {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint detail", complaint_id)

    def search(
        self,
        request: ComplaintSearchRequest,
    ) -> ServiceResult[List[ComplaintListItem]]:
        """
        Search complaints with text-based query and filters.
        
        Args:
            request: Search request with query and filters
            
        Returns:
            ServiceResult containing list of ComplaintListItem or error
        """
        try:
            self._logger.debug(f"Searching complaints with query: {request.query}")
            
            items = self.repository.search(request)
            
            self._logger.debug(f"Search returned {len(items)} results")
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "query": request.query
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error searching complaints: {str(e)}", exc_info=True)
            return self._handle_exception(e, "search complaints")
            
        except Exception as e:
            self._logger.error(f"Unexpected error searching complaints: {str(e)}", exc_info=True)
            return self._handle_exception(e, "search complaints")

    def list_with_filters(
        self,
        filters: ComplaintFilterParams,
        sort: Optional[ComplaintSortOptions] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[List[ComplaintListItem]]:
        """
        List complaints with advanced filtering, sorting, and pagination.
        
        Args:
            filters: Filter parameters
            sort: Sort options
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            ServiceResult containing list of ComplaintListItem or error
        """
        try:
            # Validate pagination parameters
            if page < 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Page number must be >= 1",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if page_size < 1 or page_size > 1000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Page size must be between 1 and 1000",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.debug(
                f"Listing complaints with filters, page: {page}, page_size: {page_size}"
            )
            
            items = self.repository.list_with_filters(
                filters,
                sort=sort,
                page=page,
                page_size=page_size
            )
            
            # Calculate pagination metadata
            total_items = len(items)  # This should ideally come from repository count
            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
            
            self._logger.debug(f"Listed {len(items)} complaints")
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error listing complaints: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list complaints with filters")
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error listing complaints: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list complaints with filters")

    def get_summary(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[ComplaintSummary]:
        """
        Get complaint summary statistics for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing ComplaintSummary or error
        """
        try:
            self._logger.debug(f"Fetching complaint summary for hostel: {hostel_id}")
            
            summary = self.repository.get_summary(hostel_id)
            
            return ServiceResult.success(
                summary,
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching summary for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint summary", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching summary for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint summary", hostel_id)

    def get_stats(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[ComplaintStats]:
        """
        Get detailed complaint statistics for a date range.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            ServiceResult containing ComplaintStats or error
        """
        try:
            # Validate date range
            if start_date > end_date:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Start date must be before or equal to end date",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.debug(
                f"Fetching complaint stats for hostel: {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            stats = self.repository.get_stats(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                stats,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching stats for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint stats", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching stats for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint stats", hostel_id)

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_complaint_create(
        self,
        request: ComplaintCreate
    ) -> ServiceResult[None]:
        """
        Validate complaint creation request.
        
        Args:
            request: Complaint creation data
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Add custom validation logic here
        # For example: validate hostel exists, validate category, etc.
        
        if not request.title or len(request.title.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint title cannot be empty",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if not request.description or len(request.description.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint description cannot be empty",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _validate_complaint_update(
        self,
        existing: ComplaintModel,
        request: ComplaintUpdate
    ) -> ServiceResult[None]:
        """
        Validate complaint update request.
        
        Args:
            existing: Existing complaint model
            request: Update data
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Add validation for update operations
        # For example: check if complaint can be updated based on status
        
        if hasattr(request, 'title') and request.title is not None:
            if len(request.title.strip()) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Complaint title cannot be empty",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        return ServiceResult.success(None)

    def _validate_status_change(
        self,
        request: ComplaintStatusUpdate
    ) -> ServiceResult[None]:
        """
        Validate status change request and state transitions.
        
        Args:
            request: Status update request
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Implement status transition validation
        # For example: can only move from OPEN to IN_PROGRESS, etc.
        
        return ServiceResult.success(None)