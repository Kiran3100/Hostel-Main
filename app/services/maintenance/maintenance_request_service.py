"""
Maintenance Request Service

Handles lifecycle of maintenance requests:
- Resident/supervisor/emergency submission
- Retrieval and listing with filters/sorting
- High-level summaries
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceRequestRepository
from app.schemas.maintenance import (
    MaintenanceRequest as MaintenanceRequestSchema,
    RequestSubmission,
    EmergencyRequest,
    MaintenanceResponse,
    MaintenanceDetail,
    RequestListItem,
    MaintenanceSummary,
    MaintenanceFilterParams,
    MaintenanceSortOptions,
)
from app.core.exceptions import ValidationException
from app.core.logging import LoggingContext


class MaintenanceRequestService:
    """
    High-level orchestration for maintenance requests.

    Delegates persistence & heavy querying to MaintenanceRequestRepository.
    """

    def __init__(self, request_repo: MaintenanceRequestRepository) -> None:
        self.request_repo = request_repo

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------

    def create_resident_request(
        self,
        db: Session,
        request: MaintenanceRequestSchema,
    ) -> MaintenanceResponse:
        """
        Create a maintenance request submitted by a resident/student.
        """
        payload = request.model_dump(exclude_none=True)
        with LoggingContext(source="resident", hostel_id=str(payload.get("hostel_id"))):
            obj = self.request_repo.create_request(db, payload)
        return MaintenanceResponse.model_validate(obj)

    def create_supervisor_submission(
        self,
        db: Session,
        request: RequestSubmission,
    ) -> MaintenanceResponse:
        """
        Create a maintenance request submitted by a supervisor/staff,
        typically with additional cost/priority details.
        """
        payload = request.model_dump(exclude_none=True)
        with LoggingContext(source="supervisor", hostel_id=str(payload.get("hostel_id"))):
            obj = self.request_repo.create_request(db, payload)
        return MaintenanceResponse.model_validate(obj)

    def create_emergency_request(
        self,
        db: Session,
        request: EmergencyRequest,
    ) -> MaintenanceResponse:
        """
        Create a high-priority emergency maintenance request.
        """
        payload = request.model_dump(exclude_none=True)
        payload["is_emergency"] = True
        with LoggingContext(source="emergency", hostel_id=str(payload.get("hostel_id"))):
            obj = self.request_repo.create_request(db, payload)
        return MaintenanceResponse.model_validate(obj)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_request(
        self,
        db: Session,
        request_id: UUID,
    ) -> MaintenanceDetail:
        obj = self.request_repo.get_full_request(db, request_id)
        if not obj:
            raise ValidationException("Maintenance request not found")
        return MaintenanceDetail.model_validate(obj)

    # -------------------------------------------------------------------------
    # Listing & summary
    # -------------------------------------------------------------------------

    def list_requests_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        filters: Optional[MaintenanceFilterParams] = None,
        sort: Optional[MaintenanceSortOptions] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[RequestListItem], int, MaintenanceSummary]:
        """
        List maintenance requests for a hostel, with optional filtering/sorting.

        Returns:
            (items, total_count, summary)
        """
        filters_dict = filters.model_dump(exclude_none=True) if filters else {}
        sort_dict = sort.model_dump(exclude_none=True) if sort else {}

        result = self.request_repo.search_requests(
            db=db,
            hostel_id=hostel_id,
            filters=filters_dict,
            sort=sort_dict,
            page=page,
            page_size=page_size,
        )

        items = [RequestListItem.model_validate(o) for o in result["items"]]
        total = result["total"]
        summary = MaintenanceSummary.model_validate(result["summary"])
        return items, total, summary