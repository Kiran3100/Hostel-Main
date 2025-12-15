# app/repositories/transactions/referral_program_repository.py
from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.transactions import ReferralProgram


class ReferralProgramRepository(BaseRepository[ReferralProgram]):
    def __init__(self, session: Session):
        super().__init__(session, ReferralProgram)

    def list_active(self, as_of: Optional[date] = None) -> List[ReferralProgram]:
        stmt = self._base_select().where(ReferralProgram.is_active.is_(True))
        if as_of is not None:
            stmt = stmt.where(
                (ReferralProgram.valid_from.is_(None) | (ReferralProgram.valid_from <= as_of)),
                (ReferralProgram.valid_to.is_(None) | (ReferralProgram.valid_to >= as_of)),
            )
        return self.session.execute(stmt).scalars().all()