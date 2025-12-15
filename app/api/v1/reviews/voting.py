# app/api/v1/reviews/voting.py
from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.review import ReviewVotingService
from app.schemas.review.review_voting import (
    VoteRequest,
    VoteResponse,
    HelpfulnessScore,
    VoteHistory,
    RemoveVote,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Reviews - Voting"])


def _get_service(session: Session) -> ReviewVotingService:
    uow = UnitOfWork(session)
    return ReviewVotingService(uow)


@router.post("/{review_id}", response_model=VoteResponse)
def cast_or_update_vote(
    review_id: UUID,
    payload: VoteRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> VoteResponse:
    """
    Cast or update a helpfulness vote for a review.
    """
    service = _get_service(session)
    # Expected: cast_vote(user_id: UUID, review_id: UUID, data: VoteRequest) -> VoteResponse
    return service.cast_vote(
        user_id=current_user.id,
        review_id=review_id,
        data=payload,
    )


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_vote(
    review_id: UUID,
    payload: Union[RemoveVote, None] = None,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """
    Remove a helpfulness vote from a review.
    """
    service = _get_service(session)
    # Expected: remove_vote(user_id: UUID, review_id: UUID) -> None
    service.remove_vote(
        user_id=current_user.id,
        review_id=review_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/history", response_model=VoteHistory)
def get_my_vote_history(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> VoteHistory:
    """
    Get the vote history for the authenticated user.
    """
    service = _get_service(session)
    # Expected: get_vote_history(user_id: UUID) -> VoteHistory
    return service.get_vote_history(user_id=current_user.id)


@router.get("/{review_id}/score", response_model=HelpfulnessScore)
def get_review_helpfulness_score(
    review_id: UUID,
    session: Session = Depends(get_session),
) -> HelpfulnessScore:
    """
    Get the helpfulness score for a review.
    """
    service = _get_service(session)
    # Expected: get_helpfulness_score(review_id: UUID) -> HelpfulnessScore
    return service.get_helpfulness_score(review_id=review_id)