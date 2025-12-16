# app/repositories/system/platform_config_repository.py
from typing import Union

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.system import PlatformConfig


class PlatformConfigRepository(BaseRepository[PlatformConfig]):
    """
    Typically there is a single row; we expose helpers to fetch or create it.
    """
    def __init__(self, session: Session):
        super().__init__(session, PlatformConfig)

    def get_singleton(self) -> Union[PlatformConfig, None]:
        stmt = self._base_select().limit(1)
        return self.session.execute(stmt).scalar_one_or_none()