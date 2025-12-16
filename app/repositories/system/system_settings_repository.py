# app/repositories/system/system_settings_repository.py
from typing import Union

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.system import SystemSettings


class SystemSettingsRepository(BaseRepository[SystemSettings]):
    def __init__(self, session: Session):
        super().__init__(session, SystemSettings)

    def get_by_key(self, key: str) -> Union[SystemSettings, None]:
        stmt = self._base_select().where(SystemSettings.key == key)
        return self.session.execute(stmt).scalar_one_or_none()