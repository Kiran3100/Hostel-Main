# app/repositories/associations/admin_hostel_repository.py
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.associations import AdminHostel
from app.models.core import Hostel, Admin


class AdminHostelRepository(BaseRepository[AdminHostel]):
    def __init__(self, session: Session):
        super().__init__(session, AdminHostel)

    def get_hostels_for_admin(self, admin_id: UUID, *, only_active: bool = True) -> List[Hostel]:
        stmt = (
            select(Hostel)
            .join(AdminHostel, AdminHostel.hostel_id == Hostel.id)
            .where(AdminHostel.admin_id == admin_id)
        )
        if only_active:
            stmt = stmt.where(
                AdminHostel.is_active.is_(True),
                Hostel.is_active.is_(True),
            )
        return self.session.execute(stmt).scalars().all()

    def get_admins_for_hostel(self, hostel_id: UUID, *, only_active: bool = True) -> List[Admin]:
        stmt = (
            select(Admin)
            .join(AdminHostel, AdminHostel.admin_id == Admin.id)
            .where(AdminHostel.hostel_id == hostel_id)
        )
        if only_active:
            stmt = stmt.where(AdminHostel.is_active.is_(True))
        return self.session.execute(stmt).scalars().all()