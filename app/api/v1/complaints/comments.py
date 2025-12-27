"""
Complaint Comments API Endpoints
Handles creation, updating, deletion, and retrieval of complaint comments.
"""
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    CommentCreate,
    CommentUpdate,
    CommentDelete,
    CommentList,
    CommentResponse,
)
from app.services.complaint.complaint_comment_service import ComplaintCommentService

router = APIRouter(prefix="/complaints/comments", tags=["complaints:comments"])


def get_comment_service(db: Session = Depends(deps.get_db)) -> ComplaintCommentService:
    """
    Dependency injection for ComplaintCommentService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        ComplaintCommentService: Initialized service instance
    """
    return ComplaintCommentService(db=db)


@router.post(
    "/{complaint_id}",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to complaint",
    description="Add a new comment to a complaint. Comments support mentions, attachments, and threading.",
    responses={
        201: {"description": "Comment created successfully"},
        404: {"description": "Complaint not found"},
        403: {"description": "Not authorized to comment on this complaint"},
    },
)
def add_comment(
    complaint_id: str,
    payload: CommentCreate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintCommentService = Depends(get_comment_service),
) -> Any:
    """
    Add a comment to a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Comment content and metadata (text, attachments, parent_id)
        current_user: Authenticated user adding the comment
        service: Comment service instance
        
    Returns:
        CommentResponse: Created comment with metadata
        
    Raises:
        HTTPException: If complaint not found or user not authorized
    """
    return service.add(
        complaint_id=complaint_id,
        payload=payload,
        user_id=current_user.id
    )


@router.put(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Update comment",
    description="Update an existing comment. Only comment author can update their comments.",
    responses={
        200: {"description": "Comment updated successfully"},
        404: {"description": "Comment not found"},
        403: {"description": "Not authorized to update this comment"},
    },
)
def update_comment(
    comment_id: str,
    payload: CommentUpdate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintCommentService = Depends(get_comment_service),
) -> Any:
    """
    Update an existing comment.
    
    Args:
        comment_id: Unique identifier of the comment
        payload: Updated comment content
        current_user: Authenticated user updating the comment
        service: Comment service instance
        
    Returns:
        CommentResponse: Updated comment with edit timestamp
        
    Raises:
        HTTPException: If comment not found or user not authorized
    """
    return service.update(
        comment_id=comment_id,
        payload=payload,
        user_id=current_user.id
    )


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete comment",
    description="Soft delete a comment. Comment author or supervisor can delete comments.",
    responses={
        200: {"description": "Comment deleted successfully"},
        404: {"description": "Comment not found"},
        403: {"description": "Not authorized to delete this comment"},
    },
)
def delete_comment(
    comment_id: str,
    payload: CommentDelete,
    current_user=Depends(deps.get_current_user),
    service: ComplaintCommentService = Depends(get_comment_service),
) -> Any:
    """
    Delete a comment (soft delete).
    
    Args:
        comment_id: Unique identifier of the comment
        payload: Deletion metadata (reason, permanent flag)
        current_user: Authenticated user deleting the comment
        service: Comment service instance
        
    Returns:
        dict: Success message with deletion details
        
    Raises:
        HTTPException: If comment not found or user not authorized
    """
    service.delete(
        comment_id=comment_id,
        payload=payload,
        user_id=current_user.id
    )
    return {
        "success": True,
        "message": "Comment deleted successfully",
        "comment_id": comment_id
    }


@router.get(
    "/{complaint_id}",
    response_model=CommentList,
    summary="List comments for a complaint",
    description="Retrieve all comments for a complaint with pagination and threading support.",
    responses={
        200: {"description": "Comments retrieved successfully"},
        404: {"description": "Complaint not found"},
        403: {"description": "Not authorized to view comments"},
    },
)
def list_comments(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintCommentService = Depends(get_comment_service),
) -> Any:
    """
    List all comments for a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        current_user: Authenticated user requesting comments
        service: Comment service instance
        
    Returns:
        CommentList: List of comments with threading structure
        
    Raises:
        HTTPException: If complaint not found or user not authorized
    """
    return service.list_for_complaint(complaint_id, user_id=current_user.id)