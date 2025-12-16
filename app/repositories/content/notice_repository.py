# app/repositories/content/notice_repository.py
from datetime import datetime
from typing import List, Union
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.content import Notice
from app.schemas.common.enums import TargetAudience


class NoticeRepository(BaseRepository[Notice]):
    def __init__(self, session: Session):
        super().__init__(session, Notice)

    def list_active_notices(
        self,
        *,
        hostel_id: Union[UUID, None] = None,
        audience: Union[TargetAudience, None] = None,
        now: datetime,
    ) -> List[Notice]:
        stmt = self._base_select().where(
            (Notice.published_at.is_not(None))
            & ((Notice.expires_at.is_(None)) | (Notice.expires_at > now))
        )
        if hostel_id is not None:
            stmt = stmt.where(Notice.hostel_id == hostel_id)
        if audience is not None:
            stmt = stmt.where(Notice.target_audience == audience)
        stmt = stmt.order_by(Notice.published_at.desc())
        return self.session.execute(stmt).scalars().all()