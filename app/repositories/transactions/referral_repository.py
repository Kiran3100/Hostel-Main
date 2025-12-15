# app/repositories/transactions/referral_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.transactions import Referral
from app.schemas.common.enums import ReferralStatus


class ReferralRepository(BaseRepository[Referral]):
    def __init__(self, session: Session):
        super().__init__(session, Referral)

    def list_for_referrer(self, referrer_id: UUID) -> List[Referral]:
        stmt = (
            self._base_select()
            .where(Referral.referrer_id == referrer_id)
            .order_by(Referral.created_at.desc())
        )
        return self.session.execute(stmt).scalars().all()

    def list_completed(self, referrer_id: UUID) -> List[Referral]:
        stmt = self._base_select().where(
            Referral.referrer_id == referrer_id,
            Referral.status == ReferralStatus.COMPLETED,
        )
        return self.session.execute(stmt).scalars().all()