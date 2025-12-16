# app/repositories/content/announcement_repository.py
from datetime import datetime
from typing import List, Union
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.content import Announcement
from app.schemas.common.enums import TargetAudience


class AnnouncementRepository(BaseRepository[Announcement]):
    def __init__(self, session: Session):
        super().__init__(session, Announcement)

    def list_published_for_hostel(
        self,
        hostel_id: UUID,
        *,
        now: datetime,
        audience: Union[TargetAudience, None] = None,
    ) -> List[Announcement]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    Announcement.hostel_id == hostel_id,
                    Announcement.is_published.is_(True),
                    (Announcement.expires_at.is_(None) | (Announcement.expires_at > now)),
                )
            )
        )
        if audience is not None:
            stmt = stmt.where(Announcement.target_audience == audience)
        stmt = stmt.order_by(
            Announcement.is_pinned.desc(),
            Announcement.priority.desc(),
            Announcement.created_at.desc(),
        )
        return self.session.execute(stmt).scalars().all()