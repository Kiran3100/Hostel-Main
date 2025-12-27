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
    return ComplaintCommentService(db=db)


@router.post(
    "/{complaint_id}",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to complaint",
)
def add_comment(
    complaint_id: str,
    payload: CommentCreate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintCommentService = Depends(get_comment_service),
) -> Any:
    return service.add(
        complaint_id=complaint_id, payload=payload, user_id=current_user.id
    )


@router.put(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Update comment",
)
def update_comment(
    comment_id: str,
    payload: CommentUpdate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintCommentService = Depends(get_comment_service),
) -> Any:
    return service.update(comment_id=comment_id, payload=payload, user_id=current_user.id)


@router.delete(
    "/{comment_id}",
    summary="Delete comment",
)
def delete_comment(
    comment_id: str,
    payload: CommentDelete,
    current_user=Depends(deps.get_current_user),
    service: ComplaintCommentService = Depends(get_comment_service),
) -> Any:
    service.delete(comment_id=comment_id, payload=payload, user_id=current_user.id)
    return {"detail": "Comment deleted"}


@router.get(
    "/{complaint_id}",
    response_model=CommentList,
    summary="List comments for a complaint",
)
def list_comments(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintCommentService = Depends(get_comment_service),
) -> Any:
    return service.list_for_complaint(complaint_id, user_id=current_user.id)