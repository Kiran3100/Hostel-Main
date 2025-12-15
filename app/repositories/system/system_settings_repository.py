# app/repositories/system/system_settings_repository.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.system import SystemSettings


class SystemSettingsRepository(BaseRepository[SystemSettings]):
    def __init__(self, session: Session):
        super().__init__(session, SystemSettings)

    def get_by_key(self, key: str) -> Optional[SystemSettings]:
        stmt = self._base_select().where(SystemSettings.key == key)
        return self.session.execute(stmt).scalar_one_or_none()