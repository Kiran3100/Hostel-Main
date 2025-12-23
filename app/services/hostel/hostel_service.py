# --- File: C:\Hostel-Main\app\services\hostel\hostel_service.py ---
"""
Core hostel service: create/update, detail/list/search, and operational updates.

This service handles all primary hostel operations including CRUD operations,
visibility management, status updates, and capacity management.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
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
from app.repositories.hostel import HostelRepository
from app.models.hostel.hostel import Hostel as HostelModel
from app.schemas.hostel.hostel_base import (
    HostelCreate, 
    HostelUpdate, 
    HostelMediaUpdate, 
    HostelSEOUpdate
)
from app.schemas.hostel.hostel_response import (
    HostelResponse, 
    HostelDetail, 
    HostelListItem, 
    HostelStats
)
from app.schemas.hostel.hostel_filter import (
    HostelFilterParams, 
    HostelSortOptions, 
    AdvancedFilters
)
from app.services.hostel.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ERROR_HOSTEL_NOT_FOUND,
    SUCCESS_HOSTEL_CREATED,
    SUCCESS_HOSTEL_UPDATED,
    SUCCESS_MEDIA_UPDATED,
    SUCCESS_SEO_UPDATED,
    SUCCESS_VISIBILITY_UPDATED,
    SUCCESS_STATUS_UPDATED,
    SUCCESS_CAPACITY_UPDATED,
)

logger = logging.getLogger(__name__)


class HostelService(BaseService[HostelModel, HostelRepository]):
    """
    High-level hostel operations service.
    
    Provides comprehensive hostel management including:
    - CRUD operations
    - Media and SEO management
    - Visibility and status control
    - Capacity management
    - Statistics and filtering
    """

    def __init__(self, repository: HostelRepository, db_session: Session):
        """
        Initialize hostel service.
        
        Args:
            repository: Hostel repository instance
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self._cache: Dict[str, Any] = {}

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_hostel(
        self,
        request: HostelCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelDetail]:
        """
        Create a new hostel with validation.
        
        Args:
            request: Hostel creation request with all required fields
            created_by: UUID of the user creating the hostel
            
        Returns:
            ServiceResult containing the created hostel detail or error
        """
        try:
            logger.info(f"Creating hostel: {request.name}")
            
            # Validate request
            validation_error = self._validate_hostel_create(request)
            if validation_error:
                return validation_error
            
            # Create hostel
            hostel = self.repository.create_hostel(request, created_by=created_by)
            self.db.flush()
            
            # Get detailed response
            detail = self.repository.get_detail(hostel.id)
            
            self.db.commit()
            
            logger.info(f"Hostel created successfully: {hostel.id}")
            return ServiceResult.success(detail, message=SUCCESS_HOSTEL_CREATED)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating hostel: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Hostel with this name or identifier already exists",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create hostel")

    def update_hostel(
        self,
        hostel_id: UUID,
        request: HostelUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelDetail]:
        """
        Update existing hostel information.
        
        Args:
            hostel_id: UUID of the hostel to update
            request: Update request with fields to modify
            updated_by: UUID of the user performing the update
            
        Returns:
            ServiceResult containing updated hostel detail or error
        """
        try:
            logger.info(f"Updating hostel: {hostel_id}")
            
            # Check existence
            existing = self.repository.get_by_id(hostel_id)
            if not existing:
                return self._not_found_error(ERROR_HOSTEL_NOT_FOUND, hostel_id)
            
            # Validate update
            validation_error = self._validate_hostel_update(request, existing)
            if validation_error:
                return validation_error
            
            # Perform update
            self.repository.update_hostel(hostel_id, request, updated_by=updated_by)
            self.db.flush()
            
            # Get updated detail
            detail = self.repository.get_detail(hostel_id)
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(hostel_id)
            
            logger.info(f"Hostel updated successfully: {hostel_id}")
            return ServiceResult.success(detail, message=SUCCESS_HOSTEL_UPDATED)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error updating hostel: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Update would violate data constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update hostel", hostel_id)

    def update_media(
        self,
        hostel_id: UUID,
        request: HostelMediaUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelDetail]:
        """
        Update hostel media references.
        
        Args:
            hostel_id: UUID of the hostel
            request: Media update request
            updated_by: UUID of the user performing the update
            
        Returns:
            ServiceResult containing updated hostel detail or error
        """
        try:
            logger.info(f"Updating media for hostel: {hostel_id}")
            
            # Verify hostel exists
            if not self.repository.get_by_id(hostel_id):
                return self._not_found_error(ERROR_HOSTEL_NOT_FOUND, hostel_id)
            
            # Update media
            self.repository.update_media(hostel_id, request, updated_by=updated_by)
            self.db.flush()
            
            # Get updated detail
            detail = self.repository.get_detail(hostel_id)
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(hostel_id)
            
            logger.info(f"Media updated successfully for hostel: {hostel_id}")
            return ServiceResult.success(detail, message=SUCCESS_MEDIA_UPDATED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update hostel media", hostel_id)

    def update_seo(
        self,
        hostel_id: UUID,
        request: HostelSEOUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelDetail]:
        """
        Update hostel SEO metadata.
        
        Args:
            hostel_id: UUID of the hostel
            request: SEO update request
            updated_by: UUID of the user performing the update
            
        Returns:
            ServiceResult containing updated hostel detail or error
        """
        try:
            logger.info(f"Updating SEO for hostel: {hostel_id}")
            
            # Verify hostel exists
            if not self.repository.get_by_id(hostel_id):
                return self._not_found_error(ERROR_HOSTEL_NOT_FOUND, hostel_id)
            
            # Update SEO
            self.repository.update_seo(hostel_id, request, updated_by=updated_by)
            self.db.flush()
            
            # Get updated detail
            detail = self.repository.get_detail(hostel_id)
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(hostel_id)
            
            logger.info(f"SEO updated successfully for hostel: {hostel_id}")
            return ServiceResult.success(detail, message=SUCCESS_SEO_UPDATED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update hostel SEO", hostel_id)

    # =========================================================================
    # Query Operations
    # =========================================================================

    def get_detail(
        self, 
        hostel_id: UUID,
        use_cache: bool = True
    ) -> ServiceResult[HostelDetail]:
        """
        Retrieve detailed hostel information.
        
        Args:
            hostel_id: UUID of the hostel
            use_cache: Whether to use cached data if available
            
        Returns:
            ServiceResult containing hostel detail or error
        """
        try:
            # Check cache
            cache_key = f"hostel_detail_{hostel_id}"
            if use_cache and cache_key in self._cache:
                logger.debug(f"Cache hit for hostel detail: {hostel_id}")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch from repository
            detail = self.repository.get_detail(hostel_id)
            
            if not detail:
                return self._not_found_error(ERROR_HOSTEL_NOT_FOUND, hostel_id)
            
            # Cache the result
            if use_cache:
                self._cache[cache_key] = detail
            
            return ServiceResult.success(detail)
            
        except Exception as e:
            return self._handle_exception(e, "get hostel detail", hostel_id)

    def list_hostels(
        self,
        filters: Optional[HostelFilterParams] = None,
        sort: Optional[HostelSortOptions] = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> ServiceResult[List[HostelListItem]]:
        """
        List hostels with filtering, sorting, and pagination.
        
        Args:
            filters: Filter parameters
            sort: Sorting options
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            ServiceResult containing list of hostels with metadata
        """
        try:
            # Validate pagination
            page = max(1, page)
            page_size = min(max(1, page_size), MAX_PAGE_SIZE)
            
            logger.info(
                f"Listing hostels - page: {page}, size: {page_size}, "
                f"filters: {filters}, sort: {sort}"
            )
            
            # Fetch hostels
            items = self.repository.list_hostels(
                filters=filters,
                sort=sort,
                page=page,
                page_size=page_size
            )
            
            # Prepare metadata
            metadata = {
                "count": len(items),
                "page": page,
                "page_size": page_size,
                "has_more": len(items) == page_size
            }
            
            return ServiceResult.success(items, metadata=metadata)
            
        except Exception as e:
            return self._handle_exception(e, "list hostels")

    def get_stats(
        self,
        hostel_id: UUID,
        use_cache: bool = True
    ) -> ServiceResult[HostelStats]:
        """
        Retrieve hostel statistics.
        
        Args:
            hostel_id: UUID of the hostel
            use_cache: Whether to use cached data if available
            
        Returns:
            ServiceResult containing hostel statistics or error
        """
        try:
            # Check cache
            cache_key = f"hostel_stats_{hostel_id}"
            if use_cache and cache_key in self._cache:
                logger.debug(f"Cache hit for hostel stats: {hostel_id}")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch statistics
            stats = self.repository.get_stats(hostel_id)
            
            # Cache the result
            if use_cache:
                self._cache[cache_key] = stats
            
            return ServiceResult.success(stats)
            
        except Exception as e:
            return self._handle_exception(e, "get hostel stats", hostel_id)

    # =========================================================================
    # Operational Updates
    # =========================================================================

    def set_visibility(
        self,
        hostel_id: UUID,
        is_public: Optional[bool] = None,
        is_featured: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        reason: Optional[str] = None,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelDetail]:
        """
        Update hostel visibility settings.
        
        Args:
            hostel_id: UUID of the hostel
            is_public: Whether hostel is publicly visible
            is_featured: Whether hostel is featured
            is_verified: Whether hostel is verified
            reason: Reason for visibility change
            updated_by: UUID of the user making the change
            
        Returns:
            ServiceResult containing updated hostel detail or error
        """
        try:
            logger.info(
                f"Updating visibility for hostel {hostel_id}: "
                f"public={is_public}, featured={is_featured}, verified={is_verified}"
            )
            
            # Verify hostel exists
            if not self.repository.get_by_id(hostel_id):
                return self._not_found_error(ERROR_HOSTEL_NOT_FOUND, hostel_id)
            
            # Update visibility
            self.repository.set_visibility(
                hostel_id,
                is_public=is_public,
                is_featured=is_featured,
                is_verified=is_verified,
                reason=reason
            )
            self.db.flush()
            
            # Get updated detail
            detail = self.repository.get_detail(hostel_id)
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(hostel_id)
            
            logger.info(f"Visibility updated for hostel: {hostel_id}")
            return ServiceResult.success(detail, message=SUCCESS_VISIBILITY_UPDATED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "set hostel visibility", hostel_id)

    def set_status(
        self,
        hostel_id: UUID,
        status: str,
        is_active: Optional[bool] = None,
        reason: Optional[str] = None,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelDetail]:
        """
        Update hostel operational status.
        
        Args:
            hostel_id: UUID of the hostel
            status: New status value
            is_active: Whether hostel is active
            reason: Reason for status change
            updated_by: UUID of the user making the change
            
        Returns:
            ServiceResult containing updated hostel detail or error
        """
        try:
            logger.info(
                f"Updating status for hostel {hostel_id}: "
                f"status={status}, active={is_active}"
            )
            
            # Verify hostel exists
            if not self.repository.get_by_id(hostel_id):
                return self._not_found_error(ERROR_HOSTEL_NOT_FOUND, hostel_id)
            
            # Update status
            self.repository.set_status(
                hostel_id,
                status=status,
                is_active=is_active,
                reason=reason
            )
            self.db.flush()
            
            # Get updated detail
            detail = self.repository.get_detail(hostel_id)
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(hostel_id)
            
            logger.info(f"Status updated for hostel: {hostel_id}")
            return ServiceResult.success(detail, message=SUCCESS_STATUS_UPDATED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "set hostel status", hostel_id)

    def update_capacity(
        self,
        hostel_id: UUID,
        total_rooms: Optional[int] = None,
        total_beds: Optional[int] = None,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelDetail]:
        """
        Update hostel capacity information.
        
        Args:
            hostel_id: UUID of the hostel
            total_rooms: Total number of rooms
            total_beds: Total number of beds
            updated_by: UUID of the user making the change
            
        Returns:
            ServiceResult containing updated hostel detail or error
        """
        try:
            logger.info(
                f"Updating capacity for hostel {hostel_id}: "
                f"rooms={total_rooms}, beds={total_beds}"
            )
            
            # Verify hostel exists
            if not self.repository.get_by_id(hostel_id):
                return self._not_found_error(ERROR_HOSTEL_NOT_FOUND, hostel_id)
            
            # Validate capacity values
            if total_rooms is not None and total_rooms < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Total rooms cannot be negative",
                        severity=ErrorSeverity.WARNING
                    )
                )
            
            if total_beds is not None and total_beds < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Total beds cannot be negative",
                        severity=ErrorSeverity.WARNING
                    )
                )
            
            # Update capacity
            self.repository.update_capacity(
                hostel_id,
                total_rooms=total_rooms,
                total_beds=total_beds
            )
            self.db.flush()
            
            # Get updated detail
            detail = self.repository.get_detail(hostel_id)
            
            self.db.commit()
            
            # Clear cache
            self._invalidate_cache(hostel_id)
            
            logger.info(f"Capacity updated for hostel: {hostel_id}")
            return ServiceResult.success(detail, message=SUCCESS_CAPACITY_UPDATED)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update hostel capacity", hostel_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_hostel_create(
        self, 
        request: HostelCreate
    ) -> Optional[ServiceResult[HostelDetail]]:
        """
        Validate hostel creation request.
        
        Args:
            request: Hostel creation request
            
        Returns:
            ServiceResult with error if validation fails, None otherwise
        """
        # Add custom validation logic here
        if not request.name or len(request.name.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Hostel name is required and cannot be empty",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        return None

    def _validate_hostel_update(
        self, 
        request: HostelUpdate,
        existing: HostelModel
    ) -> Optional[ServiceResult[HostelDetail]]:
        """
        Validate hostel update request.
        
        Args:
            request: Hostel update request
            existing: Existing hostel model
            
        Returns:
            ServiceResult with error if validation fails, None otherwise
        """
        # Add custom validation logic here
        if request.name is not None and len(request.name.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Hostel name cannot be empty",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        return None

    def _not_found_error(
        self, 
        message: str, 
        entity_id: UUID
    ) -> ServiceResult[HostelDetail]:
        """
        Create a standardized not found error response.
        
        Args:
            message: Error message
            entity_id: ID of the entity not found
            
        Returns:
            ServiceResult with not found error
        """
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.NOT_FOUND,
                message=message,
                severity=ErrorSeverity.ERROR,
                details={"entity_id": str(entity_id)}
            )
        )

    def _invalidate_cache(self, hostel_id: UUID) -> None:
        """
        Clear cached data for a specific hostel.
        
        Args:
            hostel_id: UUID of the hostel
        """
        cache_keys = [
            f"hostel_detail_{hostel_id}",
            f"hostel_stats_{hostel_id}"
        ]
        
        for key in cache_keys:
            self._cache.pop(key, None)
        
        logger.debug(f"Cache invalidated for hostel: {hostel_id}")

    def clear_all_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.info("All hostel service cache cleared")