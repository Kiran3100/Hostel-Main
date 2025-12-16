# app/repositories/system/notification_config_repository.py
from typing import Union

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.system import NotificationConfig


class NotificationConfigRepository(BaseRepository[NotificationConfig]):
    def __init__(self, session: Session):
        super().__init__(session, NotificationConfig)

    def get_singleton(self) -> Union[NotificationConfig, None]:
        stmt = self._base_select().limit(1)
        return self.session.execute(stmt).scalar_one_or_none()