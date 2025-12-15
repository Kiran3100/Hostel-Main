# api/v1/complaints/comments.py

from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status, Response

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.complaint.complaint_comments import (
    CommentCreate,
    CommentResponse,
    CommentList,
    CommentUpdate,
    CommentDelete,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.complaint import ComplaintService

router = APIRouter(prefix="/comments")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.get(
    "/{complaint_id}",
    response_model=CommentList,
    summary="List comments for a complaint",
)
async def list_comments(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> CommentList:
    """
    List all comments associated with a complaint.
    """
    service = ComplaintService(uow)
    try:
        return service.list_comments(complaint_id=complaint_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{complaint_id}",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a complaint",
)
async def add_comment(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: CommentCreate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> CommentResponse:
    """
    Add a new comment to a complaint.
    """
    service = ComplaintService(uow)
    try:
        return service.add_comment(
            complaint_id=complaint_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{complaint_id}/{comment_id}",
    response_model=CommentResponse,
    summary="Update a complaint comment",
)
async def update_comment(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    comment_id: UUID = Path(..., description="Comment ID"),
    payload: CommentUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> CommentResponse:
    """
    Update an existing comment on a complaint.
    """
    service = ComplaintService(uow)
    try:
        return service.update_comment(
            complaint_id=complaint_id,
            comment_id=comment_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.delete(
    "/{complaint_id}/{comment_id}",
    summary="Delete a complaint comment",
)
async def delete_comment(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    comment_id: UUID = Path(..., description="Comment ID"),
    reason: Union[str, None] = Query(
        None, 
        description="Deletion reason (optional)",
        max_length=200
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> Response:
    """
    Delete a comment from a complaint (or mark it as deleted, depending on implementation).
    """
    service = ComplaintService(uow)
    try:
        # Create CommentDelete object from query parameter
        delete_data = CommentDelete(
            comment_id=str(comment_id), 
            reason=reason
        )
        service.delete_comment(
            complaint_id=complaint_id,
            comment_id=comment_id,
            data=delete_data,
        )
        return Response(status_code=204)
    except ServiceError as exc:
        raise _map_service_error(exc)