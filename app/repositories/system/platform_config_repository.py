# app/repositories/system/platform_config_repository.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.system import PlatformConfig


class PlatformConfigRepository(BaseRepository[PlatformConfig]):
    """
    Typically there is a single row; we expose helpers to fetch or create it.
    """
    def __init__(self, session: Session):
        super().__init__(session, PlatformConfig)

    def get_singleton(self) -> Optional[PlatformConfig]:
        stmt = self._base_select().limit(1)
        return self.session.execute(stmt).scalar_one_or_none()