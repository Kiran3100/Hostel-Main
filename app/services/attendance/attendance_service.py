# app/services/attendance/attendance_service.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import AttendanceRepository
from app.repositories.core import (
    StudentRepository,
    HostelRepository,
    RoomRepository,
    UserRepository,
    SupervisorRepository,
)
from app.schemas.attendance.attendance_base import (
    AttendanceCreate,
    AttendanceUpdate,
)
from app.schemas.attendance.attendance_filters import AttendanceFilterParams
from app.schemas.attendance.attendance_record import (
    AttendanceRecordRequest,
    BulkAttendanceRequest,
)
from app.schemas.attendance.attendance_response import (
    AttendanceResponse,
    AttendanceDetail,
    AttendanceListItem,
    DailyAttendanceSummary,
)
from app.schemas.common.enums import AttendanceStatus, AttendanceMode
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.services.common import UnitOfWork, errors


class AttendanceService:
    """
    Core attendance service:

    - Create/update single attendance records
    - Bulk mark attendance for many students
    - Retrieve attendance detail
    - List attendance with filters
    - Daily hostel summary
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_repo(self, uow: UnitOfWork) -> AttendanceRepository:
        return uow.get_repo(AttendanceRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        a,
        *,
        hostel_name: str,
        student_name: str,
        room_number: Optional[str],
        marked_by_name: str,
    ) -> AttendanceResponse:
        return AttendanceResponse(
            id=a.id,
            created_at=a.created_at,
            updated_at=a.updated_at,
            hostel_id=a.hostel_id,
            hostel_name=hostel_name,
            student_id=a.student_id,
            student_name=student_name,
            room_number=room_number,
            attendance_date=a.attendance_date,
            check_in_time=a.check_in_time,
            check_out_time=a.check_out_time,
            status=a.status,
            is_late=a.is_late,
            late_minutes=a.late_minutes,
            marked_by=a.marked_by_id,
            marked_by_name=marked_by_name,
        )

    def _to_detail(
        self,
        a,
        *,
        hostel_name: str,
        student_name: str,
        student_email: str,
        student_phone: str,
        room_number: Optional[str],
        marked_by_name: str,
        supervisor_name: Optional[str],
    ) -> AttendanceDetail:
        return AttendanceDetail(
            id=a.id,
            created_at=a.created_at,
            updated_at=a.updated_at,
            hostel_id=a.hostel_id,
            hostel_name=hostel_name,
            student_id=a.student_id,
            student_name=student_name,
            student_email=student_email,
            student_phone=student_phone,
            room_number=room_number,
            attendance_date=a.attendance_date,
            check_in_time=a.check_in_time,
            check_out_time=a.check_out_time,
            status=a.status,
            is_late=a.is_late,
            late_minutes=a.late_minutes,
            attendance_mode=a.attendance_mode,
            marked_by=a.marked_by_id,
            marked_by_name=marked_by_name,
            supervisor_id=a.supervisor_id,
            supervisor_name=supervisor_name,
            notes=a.notes,
            location_lat=None,
            location_lng=None,
            device_info=None,
        )

    def _to_list_item(
        self,
        a,
        *,
        student_name: str,
        room_number: Optional[str],
        marked_by_name: str,
    ) -> AttendanceListItem:
        return AttendanceListItem(
            id=a.id,
            student_name=student_name,
            room_number=room_number,
            attendance_date=a.attendance_date,
            status=a.status,
            check_in_time=a.check_in_time,
            is_late=a.is_late,
            marked_by_name=marked_by_name,
        )

    # ------------------------------------------------------------------ #
    # Core read
    # ------------------------------------------------------------------ #
    def get_attendance(self, attendance_id: UUID) -> AttendanceDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            room_repo = self._get_room_repo(uow)
            user_repo = self._get_user_repo(uow)
            supervisor_repo = self._get_supervisor_repo(uow)

            a = repo.get(attendance_id)
            if a is None:
                raise errors.NotFoundError(f"Attendance {attendance_id} not found")

            hostel = hostel_repo.get(a.hostel_id)
            hostel_name = hostel.name if hostel else ""

            student = student_repo.get(a.student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(
                    f"Student {a.student_id} not found for attendance"
                )
            student_user = student.user
            student_name = student_user.full_name
            student_email = student_user.email
            student_phone = getattr(student_user, "phone", "")

            room_number: Optional[str] = None
            if student.room_id:
                room = room_repo.get(student.room_id)
                room_number = room.room_number if room else None

            marked_by_user = user_repo.get(a.marked_by_id)
            marked_by_name = marked_by_user.full_name if marked_by_user else ""

            supervisor_name = None
            if a.supervisor_id:
                sup = supervisor_repo.get(a.supervisor_id)
                if sup and getattr(sup, "user", None):
                    supervisor_name = sup.user.full_name

            return self._to_detail(
                a,
                hostel_name=hostel_name,
                student_name=student_name,
                student_email=student_email,
                student_phone=student_phone,
                room_number=room_number,
                marked_by_name=marked_by_name,
                supervisor_name=supervisor_name,
            )

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_attendance(
        self,
        params: PaginationParams,
        filters: Optional[AttendanceFilterParams] = None,
    ) -> PaginatedResponse[AttendanceListItem]:
        """
        Paginated list of attendance records with filters.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            student_repo = self._get_student_repo(uow)
            room_repo = self._get_room_repo(uow)
            user_repo = self._get_user_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                elif filters.hostel_ids:
                    raw_filters["hostel_id"] = filters.hostel_ids
                if filters.student_id:
                    raw_filters["student_id"] = filters.student_id
                elif filters.student_ids:
                    raw_filters["student_id"] = filters.student_ids
                if filters.status:
                    raw_filters["status"] = filters.status
                elif filters.statuses:
                    raw_filters["status"] = filters.statuses
                if filters.marked_by:
                    raw_filters["marked_by_id"] = filters.marked_by
                if filters.supervisor_id:
                    raw_filters["supervisor_id"] = filters.supervisor_id

            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
                order_by=[repo.model.attendance_date.desc()],  # type: ignore[attr-defined]
            )

            # Advanced filters in Python
            def _match(a) -> bool:
                if not filters:
                    return True

                if filters.date_from and a.attendance_date < filters.date_from:
                    return False
                if filters.date_to and a.attendance_date > filters.date_to:
                    return False
                if filters.late_only and not a.is_late:
                    return False
                if filters.attendance_mode and a.attendance_mode.value != filters.attendance_mode:
                    return False
                return True

            filtered = [a for a in records if _match(a)]

            # Room filter requires looking up students
            if filters and filters.room_id:
                room_id = filters.room_id
                student_room_cache: Dict[UUID, Optional[UUID]] = {}
                tmp: List = []
                for a in filtered:
                    sid = a.student_id
                    if sid not in student_room_cache:
                        st = student_repo.get(sid)
                        student_room_cache[sid] = st.room_id if st else None
                    if student_room_cache[sid] == room_id:
                        tmp.append(a)
                filtered = tmp

            total = len(filtered)
            start = params.offset
            end = start + params.limit
            page_items = filtered[start:end]

            # Map to list items
            student_cache: Dict[UUID, object] = {}
            room_cache: Dict[UUID, Optional[str]] = {}
            user_cache: Dict[UUID, str] = {}

            items: List[AttendanceListItem] = []
            for a in page_items:
                # student
                if a.student_id not in student_cache:
                    st = student_repo.get(a.student_id)
                    student_cache[a.student_id] = st
                st = student_cache[a.student_id]
                if st is not None and getattr(st, "user", None):
                    student_name = st.user.full_name
                else:
                    student_name = ""

                # room
                room_number: Optional[str] = None
                if st is not None and getattr(st, "room_id", None):
                    rid = st.room_id
                    if rid not in room_cache:
                        r = room_repo.get(rid)
                        room_cache[rid] = r.room_number if r else None
                    room_number = room_cache[rid]  # type: ignore[name-defined]

                # marked_by
                if a.marked_by_id not in user_cache:
                    u = user_repo.get(a.marked_by_id)
                    user_cache[a.marked_by_id] = u.full_name if u else ""
                marked_by_name = user_cache[a.marked_by_id]

                items.append(
                    self._to_list_item(
                        a,
                        student_name=student_name,
                        room_number=room_number,
                        marked_by_name=marked_by_name,
                    )
                )

            return PaginatedResponse[AttendanceListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Create / update
    # ------------------------------------------------------------------ #
    def create_attendance(self, data: AttendanceCreate) -> AttendanceDetail:
        """
        Create a new attendance record.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            user_repo = self._get_user_repo(uow)
            room_repo = self._get_room_repo(uow)
            supervisor_repo = self._get_supervisor_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            student = student_repo.get(data.student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(f"Student {data.student_id} not found")
            student_user = student.user

            payload = {
                "hostel_id": data.hostel_id,
                "student_id": data.student_id,
                "attendance_date": data.attendance_date,
                "check_in_time": data.check_in_time,
                "check_out_time": data.check_out_time,
                "status": data.status,
                "is_late": data.is_late,
                "late_minutes": data.late_minutes,
                "attendance_mode": data.attendance_mode,
                "marked_by_id": data.marked_by,
                "supervisor_id": data.supervisor_id,
                "notes": data.notes,
            }
            a = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            # Map to detail
            student_name = student_user.full_name
            student_email = student_user.email
            student_phone = getattr(student_user, "phone", "")
            room_number: Optional[str] = None
            if student.room_id:
                room = room_repo.get(student.room_id)
                room_number = room.room_number if room else None

            marked_by_user = user_repo.get(a.marked_by_id)
            marked_by_name = marked_by_user.full_name if marked_by_user else ""

            supervisor_name = None
            if a.supervisor_id:
                sup = supervisor_repo.get(a.supervisor_id)
                if sup and getattr(sup, "user", None):
                    supervisor_name = sup.user.full_name

            return self._to_detail(
                a,
                hostel_name=hostel.name,
                student_name=student_name,
                student_email=student_email,
                student_phone=student_phone,
                room_number=room_number,
                marked_by_name=marked_by_name,
                supervisor_name=supervisor_name,
            )

    def record_attendance(
        self,
        req: AttendanceRecordRequest,
        *,
        marked_by: UUID,
        supervisor_id: Optional[UUID] = None,
        mode: AttendanceMode = AttendanceMode.MANUAL,
    ) -> AttendanceDetail:
        """
        Convenience wrapper to create attendance from AttendanceRecordRequest.
        """
        data = AttendanceCreate(
            hostel_id=req.hostel_id,
            student_id=req.student_id,
            attendance_date=req.attendance_date,
            check_in_time=req.check_in_time,
            check_out_time=req.check_out_time,
            status=req.status,
            is_late=req.is_late,
            late_minutes=None,
            attendance_mode=mode,
            marked_by=marked_by,
            supervisor_id=supervisor_id,
            notes=req.notes,
            location_lat=None,
            location_lng=None,
            device_info=None,
        )
        return self.create_attendance(data)

    def bulk_record_attendance(self, req: BulkAttendanceRequest) -> int:
        """
        Bulk mark attendance for many students.

        - If a record for (hostel_id, student_id, date) exists, it is updated.
        - Otherwise, a new record is created.
        """
        count = 0
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            for rec in req.student_records:
                status = rec.status or req.default_status
                existing = repo.get_multi(
                    skip=0,
                    limit=1,
                    filters={
                        "hostel_id": req.hostel_id,
                        "student_id": rec.student_id,
                        "attendance_date": req.attendance_date,
                    },
                )
                if existing:
                    a = existing[0]
                    a.status = status  # type: ignore[attr-defined]
                    a.check_in_time = rec.check_in_time  # type: ignore[attr-defined]
                    a.is_late = rec.is_late if rec.is_late is not None else a.is_late  # type: ignore[attr-defined]
                    a.marked_by_id = req.marked_by  # type: ignore[attr-defined]
                    uow.session.flush()  # type: ignore[union-attr]
                else:
                    payload = {
                        "hostel_id": req.hostel_id,
                        "student_id": rec.student_id,
                        "attendance_date": req.attendance_date,
                        "check_in_time": rec.check_in_time,
                        "check_out_time": None,
                        "status": status,
                        "is_late": rec.is_late or False,
                        "late_minutes": None,
                        "attendance_mode": AttendanceMode.MANUAL,
                        "marked_by_id": req.marked_by,
                        "supervisor_id": None,
                        "notes": rec.notes,
                    }
                    repo.create(payload)  # type: ignore[arg-type]
                count += 1

            uow.commit()
        return count

    def update_attendance(
        self,
        attendance_id: UUID,
        data: AttendanceUpdate,
    ) -> AttendanceDetail:
        """
        Update an existing attendance record.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            a = repo.get(attendance_id)
            if a is None:
                raise errors.NotFoundError(f"Attendance {attendance_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(a, field) and field != "id":
                    setattr(a, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
        return self.get_attendance(attendance_id)

    # ------------------------------------------------------------------ #
    # Daily summary
    # ------------------------------------------------------------------ #
    def get_daily_summary(self, hostel_id: UUID, day: date) -> DailyAttendanceSummary:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            user_repo = self._get_user_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            students = student_repo.list_for_hostel(hostel_id, status=None)
            total_students = len(students)

            records = repo.list_for_hostel_date(hostel_id, day)

            total_present = total_absent = total_late = total_on_leave = 0
            for a in records:
                if a.status == AttendanceStatus.PRESENT:
                    total_present += 1
                elif a.status == AttendanceStatus.ABSENT:
                    total_absent += 1
                elif a.status == AttendanceStatus.LATE:
                    total_late += 1
                    total_present += 1  # count as present
                elif a.status == AttendanceStatus.ON_LEAVE:
                    total_on_leave += 1

            attendance_percentage = (
                Decimal(str(total_present))
                / Decimal(str(total_students or 1))
                * 100
                if total_students > 0
                else Decimal("0")
            )

            # Pick one "marked_by" as representative
            marked_by_id: Optional[UUID] = None
            marked_at: Optional[datetime] = None
            if records:
                first = records[0]
                marked_by_id = first.marked_by_id
                marked_at = first.created_at

            marked_by_name = ""
            if marked_by_id:
                u = user_repo.get(marked_by_id)
                marked_by_name = u.full_name if u else ""

            marking_completed = total_students > 0 and len(records) >= total_students

            return DailyAttendanceSummary(
                hostel_id=hostel_id,
                hostel_name=hostel.name,
                date=day,
                total_students=total_students,
                total_present=total_present,
                total_absent=total_absent,
                total_late=total_late,
                total_on_leave=total_on_leave,
                attendance_percentage=attendance_percentage,
                marked_by=marked_by_id or UUID(int=0),
                marked_by_name=marked_by_name,
                marking_completed=marking_completed,
                marked_at=marked_at,
            )