"""
Visitor Service

Core visitor CRUD and high-level operations not covered by more specific services.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorRepository,
    VisitorAggregateRepository,
)
from app.schemas.visitor import (
    VisitorCreate,
    VisitorUpdate,
    VisitorResponse,
    VisitorDetail,
    VisitorStats,
)
from app.core.exceptions import ValidationException


class VisitorService:
    """
    Core service for visitor entity:

    - Create/update/delete visitor
    - Get visitor by id or user id
    - Fetch detailed profile
    - Fetch stats
    """

    def __init__(
        self,
        visitor_repo: VisitorRepository,
        aggregate_repo: VisitorAggregateRepository,
    ) -> None:
        self.visitor_repo = visitor_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_visitor(
        self,
        db: Session,
        data: VisitorCreate,
    ) -> VisitorResponse:
        visitor = self.visitor_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return VisitorResponse.model_validate(visitor)

    def update_visitor(
        self,
        db: Session,
        visitor_id: UUID,
        data: VisitorUpdate,
    ) -> VisitorResponse:
        visitor = self.visitor_repo.get_by_id(db, visitor_id)
        if not visitor:
            raise ValidationException("Visitor not found")

        updated = self.visitor_repo.update(
            db,
            obj=visitor,
            data=data.model_dump(exclude_none=True),
        )
        return VisitorResponse.model_validate(updated)

    def delete_visitor(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> None:
        visitor = self.visitor_repo.get_by_id(db, visitor_id)
        if not visitor:
            return
        self.visitor_repo.delete(db, visitor)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_visitor(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> VisitorDetail:
        visitor = self.visitor_repo.get_full_profile(db, visitor_id)
        if not visitor:
            raise ValidationException("Visitor not found")
        return VisitorDetail.model_validate(visitor)

    def get_visitor_by_user_id(
        self,
        db: Session,
        user_id: UUID,
    ) -> Optional[VisitorDetail]:
        visitor = self.visitor_repo.get_by_user_id(db, user_id)
        if not visitor:
            return None
        full = self.visitor_repo.get_full_profile(db, visitor.id)
        return VisitorDetail.model_validate(full)

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_visitor_stats(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> VisitorStats:
        stats_dict = self.aggregate_repo.get_visitor_stats(db, visitor_id)
        if not stats_dict:
            raise ValidationException("Visitor not found or no stats data")
        return VisitorStats.model_validate(stats_dict)