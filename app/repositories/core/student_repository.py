# app/repositories/core/student_repository.py
from typing import List, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.core import Student
from app.schemas.common.enums import StudentStatus


class StudentRepository(BaseRepository[Student]):
    def __init__(self, session: Session):
        super().__init__(session, Student)

    def list_for_hostel(
        self,
        hostel_id: UUID,
        *,
        status: Union[StudentStatus, None] = None,
    ) -> List[Student]:
        stmt = self._base_select().where(Student.hostel_id == hostel_id)
        if status is not None:
            stmt = stmt.where(Student.student_status == status)
        stmt = stmt.order_by(Student.check_in_date.asc().nulls_last())
        return self.session.execute(stmt).scalars().all()

    def get_by_user_id(self, user_id: UUID) -> Union[Student, None]:
        stmt = self._base_select().where(Student.user_id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()