# app/services/supervisor/supervisor_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import (
    SupervisorRepository,
    UserRepository,
    HostelRepository,
)
from app.schemas.common.enums import SupervisorStatus, EmploymentType
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.supervisor import (
    SupervisorCreate,
    SupervisorUpdate,
    SupervisorResponse,
    SupervisorDetail,
    SupervisorListItem,
)
from app.services.common import UnitOfWork, errors


class SupervisorService:
    """
    Core supervisor service:

    - Create/update supervisors
    - Get supervisor detail
    - List supervisors for a hostel
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # Mapping
    def _to_response(
        self,
        s,
        *,
        user,
        hostel_name: str,
        assigned_by: UUID,
        assigned_date: datetime,
    ) -> SupervisorResponse:
        return SupervisorResponse(
            id=s.id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            user_id=s.user_id,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", ""),
            assigned_hostel_id=s.hostel_id,
            hostel_name=hostel_name,
            employee_id=s.employee_id,
            join_date=s.join_date,
            employment_type=s.employment_type,
            status=s.status,
            is_active=s.is_active,
            assigned_by=assigned_by,
            assigned_date=assigned_date.date(),
        )

    def _to_detail(
        self,
        s,
        *,
        user,
        hostel_name: str,
        assigned_by: UUID,
        assigned_by_name: str,
        assigned_date: datetime,
    ) -> SupervisorDetail:
        return SupervisorDetail(
            id=s.id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", ""),
            profile_image_url=getattr(user, "profile_image_url", None),
            assigned_hostel_id=s.hostel_id,
            hostel_name=hostel_name,
            assigned_by=assigned_by,
            assigned_by_name=assigned_by_name,
            assigned_date=assigned_date.date(),
            employee_id=s.employee_id,
            join_date=s.join_date,
            employment_type=s.employment_type,
            shift_timing=s.shift_timing,
            status=s.status,
            is_active=s.is_active,
            termination_date=None,
            termination_reason=None,
            permissions=s.permissions or {},
            total_complaints_resolved=0,
            average_resolution_time_hours=Decimal("0"),
            last_performance_review=None,
            performance_rating=None,
            last_login=None,
            total_logins=0,
        )

    def _to_list_item(
        self,
        s,
        *,
        user,
        hostel_name: str,
    ) -> SupervisorListItem:
        return SupervisorListItem(
            id=s.id,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", ""),
            hostel_name=hostel_name,
            employee_id=s.employee_id,
            employment_type=s.employment_type,
            status=s.status,
            is_active=s.is_active,
            join_date=s.join_date,
            performance_rating=None,
        )

    # CRUD
    def create_supervisor(self, data: SupervisorCreate) -> SupervisorDetail:
        with UnitOfWork(self._session_factory) as uow:
            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            user = user_repo.get(data.user_id)
            if user is None:
                raise errors.NotFoundError(f"User {data.user_id} not found")

            hostel = hostel_repo.get(data.assigned_hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.assigned_hostel_id} not found")

            payload = {
                "user_id": data.user_id,
                "hostel_id": data.assigned_hostel_id,
                "employee_id": data.employee_id,
                "join_date": data.join_date,
                "employment_type": data.employment_type,
                "shift_timing": data.shift_timing,
                "status": SupervisorStatus.ACTIVE,
                "is_active": True,
                "permissions": data.permissions or {},
            }
            s = sup_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            assigned_by_user = user_repo.get(data.assigned_by)
            assigned_by_name = assigned_by_user.full_name if assigned_by_user else ""
            assigned_date = datetime.combine(data.join_date, datetime.min.time())

            return self._to_detail(
                s,
                user=user,
                hostel_name=hostel.name,
                assigned_by=data.assigned_by,
                assigned_by_name=assigned_by_name,
                assigned_date=assigned_date,
            )

    def update_supervisor(self, supervisor_id: UUID, data: SupervisorUpdate) -> SupervisorDetail:
        with UnitOfWork(self._session_factory) as uow:
            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            s = sup_repo.get(supervisor_id)
            if s is None:
                raise errors.NotFoundError(f"Supervisor {supervisor_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(s, field) and field != "id":
                    setattr(s, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            user = user_repo.get(s.user_id)
            hostel = hostel_repo.get(s.hostel_id)
            uow.commit()

            assigned_by = UUID(int=0)
            assigned_by_name = ""
            assigned_date = datetime.combine(s.join_date, datetime.min.time())

            return self._to_detail(
                s,
                user=user,
                hostel_name=hostel.name if hostel else "",
                assigned_by=assigned_by,
                assigned_by_name=assigned_by_name,
                assigned_date=assigned_date,
            )

    def get_supervisor(self, supervisor_id: UUID) -> SupervisorDetail:
        with UnitOfWork(self._session_factory) as uow:
            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            s = sup_repo.get(supervisor_id)
            if s is None:
                raise errors.NotFoundError(f"Supervisor {supervisor_id} not found")

            user = user_repo.get(s.user_id)
            hostel = hostel_repo.get(s.hostel_id)
            assigned_by = UUID(int=0)
            assigned_by_name = ""
            assigned_date = datetime.combine(s.join_date, datetime.min.time())

            return self._to_detail(
                s,
                user=user,
                hostel_name=hostel.name if hostel else "",
                assigned_by=assigned_by,
                assigned_by_name=assigned_by_name,
                assigned_date=assigned_date,
            )

    # Listing
    def list_supervisors_for_hostel(
        self,
        hostel_id: UUID,
        params: PaginationParams,
        *,
        status: Optional[SupervisorStatus] = None,
    ) -> PaginatedResponse[SupervisorListItem]:
        with UnitOfWork(self._session_factory) as uow:
            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            supervisors = sup_repo.list_for_hostel(hostel_id, status=status)
            hostel = hostel_repo.get(hostel_id)
            hostel_name = hostel.name if hostel else ""

            items: List[SupervisorListItem] = []
            for s in supervisors:
                user = user_repo.get(s.user_id)
                if not user:
                    continue
                items.append(self._to_list_item(s, user=user, hostel_name=hostel_name))

            total = len(items)
            start = params.offset
            end = start + params.limit
            page_items = items[start:end]

            return PaginatedResponse[SupervisorListItem].create(
                items=page_items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )