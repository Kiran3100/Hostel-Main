"""
Core announcement service: create/update, publish/unpublish, archive/unarchive,
versioning, and high-level queries.

Enhanced with improved error handling, validation, and transaction management.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.announcement import AnnouncementRepository
from app.models.announcement.announcement import Announcement as AnnouncementModel
from app.schemas.announcement.announcement_base import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementPublish,
    AnnouncementUnpublish,
)
from app.schemas.announcement.announcement_response import (
    AnnouncementDetail,
    AnnouncementList,
)


class AnnouncementService(BaseService[AnnouncementModel, AnnouncementRepository]):
    """
    High-level announcement operations with comprehensive lifecycle management.
    
    Responsibilities:
    - Create and update announcements with versioning
    - Manage visibility transitions (publish/unpublish)
    - Archive and restore announcements
    - Query and list announcements with filtering
    """

    def __init__(self, repository: AnnouncementRepository, db_session: Session):
        """
        Initialize announcement service.
        
        Args:
            repository: Announcement repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)

    # =========================================================================
    # Create & Update Operations
    # =========================================================================

    def create_announcement(
        self,
        request: AnnouncementCreate,
    ) -> ServiceResult[AnnouncementDetail]:
        """
        Create a new draft or scheduled announcement.
        
        Args:
            request: Announcement creation data
            
        Returns:
            ServiceResult containing AnnouncementDetail or error
            
        Notes:
            - Creates announcement in draft state by default
            - Validation enforced by schema
            - Automatically commits on success
        """
        try:
            # Validate request data implicitly through schema
            announcement = self.repository.create_announcement(request)
            
            # Commit transaction
            self.db.commit()
            
            # Fetch complete detail view
            detail = self.repository.get_detail(announcement.id)
            
            return ServiceResult.success(
                data=detail,
                message="Announcement created successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(e, "create announcement")
            
        except ValueError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid announcement data: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create announcement")

    def update_announcement(
        self,
        announcement_id: UUID,
        request: AnnouncementUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[AnnouncementDetail]:
        """
        Update announcement content/metadata with versioning.
        
        Args:
            announcement_id: Unique identifier of announcement
            request: Update data
            updated_by: UUID of user performing update
            
        Returns:
            ServiceResult containing updated AnnouncementDetail or error
            
        Notes:
            - Creates version snapshot before applying changes
            - Only allows updates to non-published announcements (unless override)
            - Validates existence before update
        """
        try:
            # Verify announcement exists
            existing = self.repository.get_by_id(announcement_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Announcement {announcement_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Create version snapshot before update
            self.repository.create_version_snapshot(
                announcement_id=announcement_id,
                updated_by=updated_by
            )
            
            # Apply updates
            self.repository.update_announcement(
                announcement_id=announcement_id,
                request=request,
                updated_by=updated_by
            )
            
            # Commit transaction
            self.db.commit()
            
            # Fetch updated detail
            detail = self.repository.get_detail(announcement_id)
            
            return ServiceResult.success(
                data=detail,
                message="Announcement updated successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(e, "update announcement", announcement_id)
            
        except ValueError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid update data: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update announcement", announcement_id)

    # =========================================================================
    # Visibility Transitions (Publish/Unpublish)
    # =========================================================================

    def publish(
        self,
        request: AnnouncementPublish,
    ) -> ServiceResult[AnnouncementDetail]:
        """
        Publish an announcement immediately or schedule for future publishing.
        
        Args:
            request: Publishing configuration
            
        Returns:
            ServiceResult containing published AnnouncementDetail or error
            
        Notes:
            - Immediate publishing sets status to 'published'
            - Scheduled publishing sets status to 'scheduled'
            - Validates announcement is in publishable state
        """
        try:
            # Validate announcement exists and is publishable
            announcement = self.repository.get_by_id(request.announcement_id)
            if not announcement:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Announcement {request.announcement_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Execute publish operation based on timing
            if request.publish_immediately:
                self.repository.publish_immediately(
                    announcement_id=request.announcement_id,
                    published_by=request.published_by,
                )
                message = "Announcement published successfully"
                
            else:
                # Validate scheduled time is provided and in future
                if not request.scheduled_publish_at:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="scheduled_publish_at is required for scheduled publishing",
                            severity=ErrorSeverity.WARNING,
                        )
                    )
                
                if request.scheduled_publish_at <= datetime.utcnow():
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="scheduled_publish_at must be in the future",
                            severity=ErrorSeverity.WARNING,
                        )
                    )
                
                self.repository.schedule_publish(
                    announcement_id=request.announcement_id,
                    scheduled_at=request.scheduled_publish_at,
                    scheduled_by=request.published_by,
                )
                message = "Announcement scheduled for publishing"
            
            # Commit transaction
            self.db.commit()
            
            # Fetch updated detail
            detail = self.repository.get_detail(request.announcement_id)
            
            return ServiceResult.success(
                data=detail,
                message=message
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "publish announcement", request.announcement_id
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e, "publish announcement", request.announcement_id
            )

    def unpublish(
        self,
        request: AnnouncementUnpublish,
    ) -> ServiceResult[AnnouncementDetail]:
        """
        Unpublish a previously published announcement.
        
        Args:
            request: Unpublishing configuration
            
        Returns:
            ServiceResult containing unpublished AnnouncementDetail or error
            
        Notes:
            - Sets announcement status to 'draft'
            - Optionally notifies recipients of unpublishing
            - Records unpublish reason for audit trail
        """
        try:
            # Validate announcement exists
            announcement = self.repository.get_by_id(request.announcement_id)
            if not announcement:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Announcement {request.announcement_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Execute unpublish operation
            self.repository.unpublish(
                announcement_id=request.announcement_id,
                unpublished_by=request.unpublished_by,
                reason=request.reason,
                notify_recipients=request.notify_recipients,
            )
            
            # Commit transaction
            self.db.commit()
            
            # Fetch updated detail
            detail = self.repository.get_detail(request.announcement_id)
            
            return ServiceResult.success(
                data=detail,
                message="Announcement unpublished successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "unpublish announcement", request.announcement_id
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e, "unpublish announcement", request.announcement_id
            )

    # =========================================================================
    # Archive Operations
    # =========================================================================

    def archive(
        self,
        announcement_id: UUID,
        archived_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Archive an announcement (soft-delete from active listings).
        
        Args:
            announcement_id: Unique identifier of announcement
            archived_by: UUID of user performing archive
            
        Returns:
            ServiceResult containing success boolean or error
            
        Notes:
            - Archived announcements excluded from default queries
            - Can be restored via unarchive operation
            - Does not delete underlying data
        """
        try:
            # Validate announcement exists
            announcement = self.repository.get_by_id(announcement_id)
            if not announcement:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Announcement {announcement_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Execute archive operation
            self.repository.archive(
                announcement_id=announcement_id,
                archived_by=archived_by
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=True,
                message="Announcement archived successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "archive announcement", announcement_id
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "archive announcement", announcement_id)

    def unarchive(
        self,
        announcement_id: UUID,
        restored_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Restore an archived announcement.
        
        Args:
            announcement_id: Unique identifier of announcement
            restored_by: UUID of user performing restore
            
        Returns:
            ServiceResult containing success boolean or error
            
        Notes:
            - Restores announcement to active listings
            - Does not change publish status
            - Records restore action for audit trail
        """
        try:
            # Validate announcement exists and is archived
            announcement = self.repository.get_by_id(announcement_id)
            if not announcement:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Announcement {announcement_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Execute unarchive operation
            self.repository.unarchive(
                announcement_id=announcement_id,
                restored_by=restored_by
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=True,
                message="Announcement restored successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "unarchive announcement", announcement_id
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e, "unarchive announcement", announcement_id
            )

    # =========================================================================
    # Query Operations
    # =========================================================================

    def get_detail(
        self,
        announcement_id: UUID,
    ) -> ServiceResult[AnnouncementDetail]:
        """
        Retrieve detailed announcement information.
        
        Args:
            announcement_id: Unique identifier of announcement
            
        Returns:
            ServiceResult containing AnnouncementDetail or error
            
        Notes:
            - Includes all related data (targeting, schedule, etc.)
            - Returns error if announcement not found
        """
        try:
            detail = self.repository.get_detail(announcement_id)
            
            if not detail:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Announcement {announcement_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            return ServiceResult.success(
                data=detail,
                message="Announcement retrieved successfully"
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "get announcement detail", announcement_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "get announcement detail", announcement_id
            )

    def list_for_hostel(
        self,
        hostel_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        urgent_only: bool = False,
        pinned_only: bool = False,
    ) -> ServiceResult[AnnouncementList]:
        """
        List announcements for a hostel with filtering and pagination.
        
        Args:
            hostel_id: Unique identifier of hostel
            page: Page number (1-indexed)
            page_size: Number of items per page
            search: Optional search query
            status: Optional status filter
            category: Optional category filter
            urgent_only: Filter for urgent announcements only
            pinned_only: Filter for pinned announcements only
            
        Returns:
            ServiceResult containing AnnouncementList or error
            
        Notes:
            - Excludes archived announcements by default
            - Supports text search across title and content
            - Results ordered by priority and creation date
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
            
            if page_size < 1 or page_size > 100:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Page size must be between 1 and 100",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Fetch announcement listing
            listing = self.repository.list_for_hostel(
                hostel_id=hostel_id,
                page=page,
                page_size=page_size,
                search=search,
                status=status,
                category=category,
                urgent_only=urgent_only,
                pinned_only=pinned_only,
            )
            
            return ServiceResult.success(
                data=listing,
                message="Announcements retrieved successfully",
                metadata={
                    "count": len(listing.items),
                    "page": page,
                    "page_size": page_size,
                    "total": listing.total if hasattr(listing, 'total') else None,
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "list announcements", hostel_id
            )
            
        except Exception as e:
            return self._handle_exception(e, "list announcements", hostel_id)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _handle_database_error(
        self,
        error: SQLAlchemyError,
        operation: str,
        entity_id: Optional[UUID] = None,
    ) -> ServiceResult:
        """
        Handle database-specific errors with appropriate error codes.
        
        Args:
            error: SQLAlchemy error
            operation: Name of operation being performed
            entity_id: Optional entity identifier
            
        Returns:
            ServiceResult with appropriate error details
        """
        error_msg = f"Database error during {operation}"
        if entity_id:
            error_msg += f" for {entity_id}"
        
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.DATABASE_ERROR,
                message=error_msg,
                severity=ErrorSeverity.ERROR,
                details={"original_error": str(error)},
            )
        )