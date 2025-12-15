# app/services/workflows/booking_workflow_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.workflows import BookingWorkflowRepository
from app.services.common import UnitOfWork


class BookingWorkflowService:
    """
    Wrapper over wf_booking table.

    Tracks current_status for a booking (pending, approved, rejected,
    checked_in, checked_out, etc.).
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> BookingWorkflowRepository:
        return uow.get_repo(BookingWorkflowRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def ensure_workflow(self, booking_id: UUID, initial_status: str) -> None:
        """
        Ensure that a workflow row exists for the given booking.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            wf = repo.get_by_booking_id(booking_id)
            if wf is None:
                payload = {
                    "booking_id": booking_id,
                    "current_status": initial_status,
                    "last_updated_at": self._now(),
                }
                repo.create(payload)  # type: ignore[arg-type]
                uow.commit()

    def set_status(self, booking_id: UUID, status: str) -> None:
        """
        Set (or create) workflow status for the booking.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            wf = repo.get_by_booking_id(booking_id)
            if wf is None:
                payload = {
                    "booking_id": booking_id,
                    "current_status": status,
                    "last_updated_at": self._now(),
                }
                repo.create(payload)  # type: ignore[arg-type]
            else:
                wf.current_status = status  # type: ignore[attr-defined]
                wf.last_updated_at = self._now()  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()