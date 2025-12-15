# app/repositories/system/notification_config_repository.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.system import NotificationConfig  # assuming this exists in app.models/system/notification.py


class NotificationConfigRepository(BaseRepository[NotificationConfig]):
    def __init__(self, session: Session):
        super().__init__(session, NotificationConfig)

    def get_singleton(self) -> Optional[NotificationConfig]:
        stmt = self._base_select().limit(1)
        return self.session.execute(stmt).scalar_one_or_none()