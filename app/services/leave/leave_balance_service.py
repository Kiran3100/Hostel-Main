# app/services/leave/leave_balance_service.py
from __future__ import annotations

from datetime import date
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import LeaveApplicationRepository
from app.repositories.core import StudentRepository, HostelRepository
from app.schemas.common.enums import LeaveStatus, LeaveType
from app.schemas.leave import (
    LeaveBalance,
    LeaveBalanceSummary,
)
from app.services.common import UnitOfWork, errors


class LeaveAllocationStore(Protocol):
    """
    Store for configured annual leave allocations per hostel and leave type.

    Example data shape:
        {
            "SICK": 10,
            "CASUAL": 12,
            "EMERGENCY": 5,
        }
    using LeaveType.value as keys.
    """

    def get_allocations(self, hostel_id: UUID) -> Dict[str, int]: ...
    def save_allocations(self, hostel_id: UUID, allocations: Dict[str, int]) -> None: ...


class LeaveBalanceService:
    """
    Compute leave balance summaries for a student:

    - Uses LeaveApplicationRepository to count used days in a given academic year
    - Uses LeaveAllocationStore to get allocated days per leave type
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        allocation_store: LeaveAllocationStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = allocation_store

    def _get_leave_repo(self, uow: UnitOfWork) -> LeaveApplicationRepository:
        return uow.get_repo(LeaveApplicationRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_balance_summary(
        self,
        *,
        student_id: UUID,
        hostel_id: UUID,
        academic_year_start: date,
        academic_year_end: date,
    ) -> LeaveBalanceSummary:
        """
        Compute LeaveBalanceSummary for one student & hostel over an academic year.
        """
        with UnitOfWork(self._session_factory) as uow:
            leave_repo = self._get_leave_repo(uow)
            student_repo = self._get_student_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            student = student_repo.get(student_id)
            if student is None:
                raise errors.NotFoundError(f"Student {student_id} not found")

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            student_name = (
                student.user.full_name if getattr(student, "user", None) else ""
            )
            hostel_name = hostel.name

            # All leaves for the student
            leaves = leave_repo.list_for_student(student_id)

        # Filter leaves in academic year & with APPROVED or PENDING status
        in_range_leaves = []
        for l in leaves:
            if l.from_date > academic_year_end or l.to_date < academic_year_start:
                continue
            if l.status not in (LeaveStatus.APPROVED, LeaveStatus.PENDING):
                continue
            in_range_leaves.append(l)

        # Used days per leave type
        used_map: Dict[LeaveType, int] = {}
        for l in in_range_leaves:
            lt = l.leave_type
            used_map[lt] = used_map.get(lt, 0) + (l.total_days or 0)

        # Allocations from store (by LeaveType.value)
        allocations_raw = self._store.get_allocations(hostel_id) or {}
        balances: List[LeaveBalance] = []

        # Consider all known leave types from allocations + used_map
        all_types: List[LeaveType] = list(LeaveType)  # type: ignore[arg-type]
        for lt in all_types:
            allocated = int(allocations_raw.get(lt.value, 0))
            used = used_map.get(lt, 0)
            remaining = max(0, allocated - used)
            balances.append(
                LeaveBalance(
                    leave_type=lt,
                    allocated_per_year=allocated,
                    used_days=used,
                    remaining_days=remaining,
                )
            )

        return LeaveBalanceSummary(
            student_id=student_id,
            student_name=student_name,
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            academic_year_start=academic_year_start,
            academic_year_end=academic_year_end,
            balances=balances,
        )

    # Optional: admin API to set allocations
    def set_allocations(
        self,
        *,
        hostel_id: UUID,
        allocations: Dict[LeaveType, int],
    ) -> None:
        """
        Persist per-type annual leave allocations for a hostel.
        """
        raw: Dict[str, int] = {lt.value: v for lt, v in allocations.items()}
        self._store.save_allocations(hostel_id, raw)