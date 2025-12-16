# app/repositories/workflows/booking_workflow_repository.py
from typing import Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.workflows import BookingWorkflow


class BookingWorkflowRepository(BaseRepository[BookingWorkflow]):
    def __init__(self, session: Session):
        super().__init__(session, BookingWorkflow)

    def get_by_booking_id(self, booking_id: UUID) -> Union[BookingWorkflow, None]:
        stmt = self._base_select().where(BookingWorkflow.booking_id == booking_id)
        return self.session.execute(stmt).scalar_one_or_none()