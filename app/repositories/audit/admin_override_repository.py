# app/repositories/audit/admin_override_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.audit import AdminOverride


class AdminOverrideRepository(BaseRepository[AdminOverride]):
    def __init__(self, session: Session):
        super().__init__(session, AdminOverride)

    def list_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> List[AdminOverride]:
        stmt = (
            self._base_select()
            .where(
                (AdminOverride.entity_type == entity_type)
                & (AdminOverride.entity_id == entity_id)
            )
            .order_by(AdminOverride.created_at.desc())
        )
        return self.session.execute(stmt).scalars().all()