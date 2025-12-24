"""
Supervisor Service

Core supervisor CRUD and retrieval operations.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.supervisor import (
    SupervisorRepository,
    SupervisorAggregateRepository,
)
from app.schemas.supervisor import (
    SupervisorCreate,
    SupervisorUpdate,
    SupervisorResponse,
    SupervisorDetail,
    SupervisorListItem,
    SupervisorProfile,
)
from app.core.exceptions import ValidationException


class SupervisorService:
    """
    High-level service for Supervisor entity operations.

    Responsibilities:
    - Create/update supervisors
    - Get supervisor by id
    - List supervisors (optionally by hostel)
    - Retrieve full profile (SupervisorProfile)
    """

    def __init__(
        self,
        supervisor_repo: SupervisorRepository,
        aggregate_repo: SupervisorAggregateRepository,
    ) -> None:
        self.supervisor_repo = supervisor_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_supervisor(
        self,
        db: Session,
        data: SupervisorCreate,
    ) -> SupervisorResponse:
        """
        Create a new supervisor record and initial assignment/employment info.

        The SupervisorCreate schema encapsulates employment & assignment details.
        """
        obj = self.supervisor_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return SupervisorResponse.model_validate(obj)

    def update_supervisor(
        self,
        db: Session,
        supervisor_id: UUID,
        data: SupervisorUpdate,
    ) -> SupervisorResponse:
        """
        Update supervisor information (employment, status, notes, etc.).
        """
        supervisor = self.supervisor_repo.get_by_id(db, supervisor_id)
        if not supervisor:
            raise ValidationException("Supervisor not found")

        updated = self.supervisor_repo.update(
            db,
            supervisor,
            data.model_dump(exclude_none=True),
        )
        return SupervisorResponse.model_validate(updated)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_supervisor(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> SupervisorDetail:
        """
        Retrieve full detail of a supervisor (including relationships).
        """
        full = self.supervisor_repo.get_full_supervisor(db, supervisor_id)
        if not full:
            raise ValidationException("Supervisor not found")
        return SupervisorDetail.model_validate(full)

    def get_supervisor_profile(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> SupervisorProfile:
        """
        Retrieve full profile data for a supervisor (employment history,
        permissions, performance summary, preferences).
        """
        profile_dict = self.aggregate_repo.get_supervisor_profile(db, supervisor_id)
        if not profile_dict:
            raise ValidationException("Supervisor not found")
        return SupervisorProfile.model_validate(profile_dict)

    def list_supervisors(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SupervisorListItem]:
        """
        List supervisors globally or filtered by hostel.
        """
        if hostel_id:
            objs = self.supervisor_repo.get_by_hostel(db, hostel_id, skip, limit)
        else:
            objs = self.supervisor_repo.get_list(db, skip, limit)

        return [SupervisorListItem.model_validate(o) for o in objs]