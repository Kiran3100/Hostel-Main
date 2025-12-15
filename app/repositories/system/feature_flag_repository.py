# app/repositories/system/feature_flag_repository.py
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.system import FeatureFlag


class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    def __init__(self, session: Session):
        super().__init__(session, FeatureFlag)

    def get_by_name(self, name: str) -> Optional[FeatureFlag]:
        stmt = self._base_select().where(FeatureFlag.name == name)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_enabled(self) -> List[FeatureFlag]:
        stmt = self._base_select().where(FeatureFlag.is_enabled.is_(True))
        return self.session.execute(stmt).scalars().all()