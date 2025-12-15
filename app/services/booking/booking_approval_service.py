# app/services/booking/booking_approval_service.py
from __future__ import annotations

from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.common import UnitOfWork, errors
from app.repositories.transactions import BookingRepository
from app.schemas.booking.booking_approval import (
    BookingApprovalRequest,
    ApprovalResponse,
    RejectionRequest,
    BulkApprovalRequest,
    ApprovalSettings,
)


class BookingApprovalService:
    """
    Stub implementation for booking approval workflows.

    Wire real logic later; for now this just shows the expected interface.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        # NOTE: In your routers you're passing `uow` here; that will still work
        # at runtime because Python doesn't enforce types. Once you implement
        # logic, you'll either:
        #   - pass a real `session_factory` here, OR
        #   - change this signature to accept `UnitOfWork` directly.
        self._session_factory = session_factory

    def _get_booking_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    def approve_booking(
        self,
        booking_id: UUID,
        request: BookingApprovalRequest,
    ) -> ApprovalResponse:
        # TODO: implement real approval logic
        raise NotImplementedError("BookingApprovalService.approve_booking is not implemented yet")

    def reject_booking(
        self,
        booking_id: UUID,
        request: RejectionRequest,
    ) -> ApprovalResponse:
        # TODO: implement real rejection logic
        raise NotImplementedError("BookingApprovalService.reject_booking is not implemented yet")

    def bulk_approve(
        self,
        request: BulkApprovalRequest,
    ) -> List[ApprovalResponse]:
        # TODO: implement real bulk logic
        raise NotImplementedError("BookingApprovalService.bulk_approve is not implemented yet")

    def get_settings(self) -> ApprovalSettings:
        # TODO: load settings from DB/config
        raise NotImplementedError("BookingApprovalService.get_settings is not implemented yet")

    def update_settings(self, settings: ApprovalSettings) -> ApprovalSettings:
        # TODO: persist settings to DB/config
        raise NotImplementedError("BookingApprovalService.update_settings is not implemented yet")