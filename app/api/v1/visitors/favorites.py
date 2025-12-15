# app/api/v1/visitors/favorites.py
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.visitor import FavoritesService
from app.schemas.visitor.visitor_favorites import (
    FavoriteRequest,
    FavoriteUpdate,
    FavoritesList,
    FavoriteHostelItem,
    FavoritesExport,
    FavoriteComparison,
)
from . import CurrentUser, get_current_visitor

router = APIRouter(tags=["Visitor - Favorites"])


def _get_service(session: Session) -> FavoritesService:
    uow = UnitOfWork(session)
    return FavoritesService(uow)


@router.get("/", response_model=FavoritesList)
def list_favorites(
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> FavoritesList:
    """
    List all favorite hostels for the authenticated visitor.
    """
    service = _get_service(session)
    # Expected service method:
    #   list_favorites_for_user(user_id: UUID) -> FavoritesList
    return service.list_favorites_for_user(user_id=current_user.id)


@router.post(
    "/",
    response_model=FavoriteHostelItem,
    status_code=status.HTTP_201_CREATED,
)
def add_favorite(
    payload: FavoriteRequest,
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> FavoriteHostelItem:
    """
    Add a hostel to the visitor's favorites (or update if already exists).
    """
    service = _get_service(session)
    # Expected service method:
    #   add_favorite(user_id: UUID, data: FavoriteRequest) -> FavoriteHostelItem
    return service.add_favorite(user_id=current_user.id, data=payload)


@router.patch(
    "/{hostel_id}",
    response_model=FavoriteHostelItem,
)
def update_favorite(
    hostel_id: UUID,
    payload: FavoriteUpdate,
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> FavoriteHostelItem:
    """
    Update metadata (e.g., notes) for a favorite hostel.
    """
    service = _get_service(session)
    # Expected service method:
    #   update_favorite(user_id: UUID, hostel_id: UUID, data: FavoriteUpdate) -> FavoriteHostelItem
    return service.update_favorite(
        user_id=current_user.id,
        hostel_id=hostel_id,
        data=payload,
    )


@router.delete("/{hostel_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    hostel_id: UUID,
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> Response:
    """
    Remove a hostel from the visitor's favorites.
    """
    service = _get_service(session)
    # Expected service method:
    #   remove_favorite(user_id: UUID, hostel_id: UUID) -> None
    service.remove_favorite(user_id=current_user.id, hostel_id=hostel_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/export", response_model=FavoritesExport)
def export_favorites(
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> FavoritesExport:
    """
    Export the visitor's favorites (for now as a structured JSON model).
    """
    service = _get_service(session)
    # Expected service method:
    #   export_favorites_for_user(user_id: UUID) -> FavoritesExport
    return service.export_favorites_for_user(user_id=current_user.id)


@router.get("/compare", response_model=FavoriteComparison)
def compare_favorites(
    hostel_ids: List[UUID] = Query(..., description="Hostel IDs to compare (2-4 ids recommended)"),
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> FavoriteComparison:
    """
    Compare a subset of favorite hostels.
    """
    service = _get_service(session)
    # Expected service method:
    #   compare_favorites(user_id: UUID, hostel_ids: List[UUID]) -> FavoriteComparison
    return service.compare_favorites(
        user_id=current_user.id,
        hostel_ids=hostel_ids,
    )