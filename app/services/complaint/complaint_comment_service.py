"""
Complaint comments/notes service.

Manages comment lifecycle including creation, updates, deletion,
and mention notifications for complaint discussions.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.complaint.complaint_comment_repository import ComplaintCommentRepository
from app.models.complaint.complaint_comment import ComplaintComment as ComplaintCommentModel
from app.schemas.complaint.complaint_comments import (
    CommentCreate,
    CommentResponse,
    CommentList,
    CommentUpdate,
    CommentDelete,
    MentionNotification,
)

logger = logging.getLogger(__name__)


class ComplaintCommentService(BaseService[ComplaintCommentModel, ComplaintCommentRepository]):
    """
    Add/update/delete/list comments and handle mention notifications.
    
    Provides comprehensive comment management with support for
    user mentions and rich text content.
    """

    # Regular expression for detecting @mentions in comments
    MENTION_PATTERN = re.compile(r'@(\w+)')

    def __init__(self, repository: ComplaintCommentRepository, db_session: Session):
        """
        Initialize comment service.
        
        Args:
            repository: Complaint comment repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Comment CRUD Operations
    # -------------------------------------------------------------------------

    def add(
        self,
        request: CommentCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[CommentResponse]:
        """
        Add a new comment to a complaint.
        
        Args:
            request: Comment creation data
            created_by: UUID of user creating the comment
            
        Returns:
            ServiceResult containing CommentResponse or error
        """
        try:
            self._logger.info(
                f"Adding comment to complaint {request.complaint_id}, "
                f"created_by: {created_by}"
            )
            
            # Validate comment
            validation_result = self._validate_comment_create(request)
            if not validation_result.success:
                return validation_result
            
            # Extract mentions before saving
            mentions = self._extract_mentions(request.content)
            
            # Add comment
            response = self.repository.add_comment(request, created_by=created_by)
            
            # Commit transaction
            self.db.commit()
            
            # Process mentions (send notifications)
            if mentions:
                self._process_mentions(response.id, mentions, created_by)
            
            self._logger.info(
                f"Comment added successfully to complaint {request.complaint_id}, "
                f"comment_id: {response.id}"
            )
            
            return ServiceResult.success(
                response,
                message="Comment added successfully",
                metadata={
                    "comment_id": str(response.id),
                    "complaint_id": str(request.complaint_id),
                    "mentions_count": len(mentions),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error adding comment to complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "add comment", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error adding comment to complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "add comment", request.complaint_id)

    def update(
        self,
        request: CommentUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[CommentResponse]:
        """
        Update an existing comment.
        
        Args:
            request: Comment update data
            updated_by: UUID of user updating the comment
            
        Returns:
            ServiceResult containing updated CommentResponse or error
        """
        try:
            self._logger.info(
                f"Updating comment {request.comment_id}, updated_by: {updated_by}"
            )
            
            # Validate update
            validation_result = self._validate_comment_update(request, updated_by)
            if not validation_result.success:
                return validation_result
            
            # Extract new mentions if content changed
            mentions = []
            if hasattr(request, 'content') and request.content:
                mentions = self._extract_mentions(request.content)
            
            # Update comment
            response = self.repository.update_comment(request, updated_by=updated_by)
            
            # Commit transaction
            self.db.commit()
            
            # Process new mentions
            if mentions:
                self._process_mentions(response.id, mentions, updated_by)
            
            self._logger.info(f"Comment {request.comment_id} updated successfully")
            
            return ServiceResult.success(
                response,
                message="Comment updated successfully",
                metadata={
                    "comment_id": str(request.comment_id),
                    "mentions_count": len(mentions),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error updating comment {request.comment_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update comment", request.comment_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error updating comment {request.comment_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update comment", request.comment_id)

    def delete(
        self,
        request: CommentDelete,
        deleted_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Delete a comment (soft delete).
        
        Args:
            request: Comment deletion data
            deleted_by: UUID of user deleting the comment
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            self._logger.info(
                f"Deleting comment {request.comment_id}, deleted_by: {deleted_by}"
            )
            
            # Validate deletion
            validation_result = self._validate_comment_delete(request, deleted_by)
            if not validation_result.success:
                return validation_result
            
            # Delete comment
            success = self.repository.delete_comment(request, deleted_by=deleted_by)
            
            # Commit transaction
            self.db.commit()
            
            if success:
                self._logger.info(f"Comment {request.comment_id} deleted successfully")
                return ServiceResult.success(
                    True,
                    message="Comment deleted successfully",
                    metadata={"comment_id": str(request.comment_id)}
                )
            else:
                self._logger.warning(f"Failed to delete comment {request.comment_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to delete comment",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error deleting comment {request.comment_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "delete comment", request.comment_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error deleting comment {request.comment_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "delete comment", request.comment_id)

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def list_for_complaint(
        self,
        complaint_id: UUID,
    ) -> ServiceResult[CommentList]:
        """
        List all comments for a specific complaint.
        
        Args:
            complaint_id: UUID of complaint
            
        Returns:
            ServiceResult containing CommentList or error
        """
        try:
            self._logger.debug(f"Listing comments for complaint {complaint_id}")
            
            listing = self.repository.list_for_complaint(complaint_id)
            
            comment_count = len(listing.comments) if hasattr(listing, 'comments') else 0
            
            self._logger.debug(f"Retrieved {comment_count} comments for complaint {complaint_id}")
            
            return ServiceResult.success(
                listing,
                metadata={
                    "complaint_id": str(complaint_id),
                    "count": comment_count,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error listing comments for complaint {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list complaint comments", complaint_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error listing comments for complaint {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list complaint comments", complaint_id)

    # -------------------------------------------------------------------------
    # Mention Processing
    # -------------------------------------------------------------------------

    def _extract_mentions(self, content: str) -> List[str]:
        """
        Extract @mentions from comment content.
        
        Args:
            content: Comment text content
            
        Returns:
            List of mentioned usernames
        """
        if not content:
            return []
        
        mentions = self.MENTION_PATTERN.findall(content)
        # Remove duplicates while preserving order
        return list(dict.fromkeys(mentions))

    def _process_mentions(
        self,
        comment_id: UUID,
        mentions: List[str],
        mentioned_by: Optional[UUID]
    ) -> None:
        """
        Process mentions and send notifications.
        
        Args:
            comment_id: UUID of comment containing mentions
            mentions: List of mentioned usernames
            mentioned_by: UUID of user who created the mention
        """
        try:
            self._logger.debug(
                f"Processing {len(mentions)} mentions for comment {comment_id}"
            )
            
            # Here you would typically:
            # 1. Resolve usernames to user IDs
            # 2. Create notification records
            # 3. Send real-time notifications (WebSocket, email, etc.)
            
            # Placeholder for actual notification logic
            for username in mentions:
                self._logger.debug(f"Would notify user @{username} about comment {comment_id}")
            
        except Exception as e:
            # Don't fail the entire operation if notifications fail
            self._logger.error(
                f"Error processing mentions for comment {comment_id}: {str(e)}",
                exc_info=True
            )

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_comment_create(
        self,
        request: CommentCreate
    ) -> ServiceResult[None]:
        """
        Validate comment creation request.
        
        Args:
            request: Comment creation data
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.content or len(request.content.strip()) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Comment content cannot be empty",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if len(request.content) > 5000:  # Example limit
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Comment content exceeds maximum length of 5000 characters",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _validate_comment_update(
        self,
        request: CommentUpdate,
        updated_by: Optional[UUID]
    ) -> ServiceResult[None]:
        """
        Validate comment update request.
        
        Args:
            request: Comment update data
            updated_by: UUID of user updating the comment
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Add authorization check: only comment author or admin can update
        # This would require fetching the comment and checking ownership
        
        if hasattr(request, 'content') and request.content is not None:
            if len(request.content.strip()) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Comment content cannot be empty",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if len(request.content) > 5000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Comment content exceeds maximum length of 5000 characters",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        return ServiceResult.success(None)

    def _validate_comment_delete(
        self,
        request: CommentDelete,
        deleted_by: Optional[UUID]
    ) -> ServiceResult[None]:
        """
        Validate comment deletion request.
        
        Args:
            request: Comment deletion data
            deleted_by: UUID of user deleting the comment
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Add authorization check: only comment author or admin can delete
        
        if not request.comment_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Comment ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)