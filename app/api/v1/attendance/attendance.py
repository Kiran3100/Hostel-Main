from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.attendance import (
    AttendanceRecordRequest,
    BulkAttendanceRequest,
    QuickAttendanceMarkAll,
    AttendanceUpdate,
    AttendanceFilterParams,
    AttendanceResponse,
    AttendanceDetail,
    AttendanceListItem,
    DailyAttendanceSummary,
    AttendanceCorrection,
)
from app.services.attendance.attendance_service import AttendanceService
from app.services.attendance.attendance_correction_service import AttendanceCorrectionService

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_attendance_service(db: Session = Depends(deps.get_db)) -> AttendanceService:
    return AttendanceService(db=db)


def get_correction_service(
    db: Session = Depends(deps.get_db),
) -> AttendanceCorrectionService:
    return AttendanceCorrectionService(db=db)


# ---------------------------------------------------------------------------
# Mark attendance (supervisor/admin)
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=AttendanceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Mark attendance for a single student",
)
def mark_attendance(
    payload: AttendanceRecordRequest,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Create a new attendance record for a single student.

    Uses AttendanceService.mark_attendance().
    """
    return service.mark_attendance(payload=payload, actor_id=_supervisor.id)


@router.post(
    "/bulk",
    response_model=List[AttendanceDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk mark attendance for multiple students",
)
def bulk_mark_attendance(
    payload: BulkAttendanceRequest,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Efficiently mark attendance for many students at once.

    Uses AttendanceService.bulk_mark_attendance().
    """
    return service.bulk_mark_attendance(payload=payload, actor_id=_supervisor.id)


@router.post(
    "/quick-mark-all",
    response_model=List[AttendanceDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Quick mark all present with exceptions",
)
def quick_mark_all(
    payload: QuickAttendanceMarkAll,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Mark all students as present with an exception list for absent/late.

    Uses AttendanceService.quick_mark_all().
    """
    return service.quick_mark_all(payload=payload, actor_id=_supervisor.id)


# ---------------------------------------------------------------------------
# Update / list / summaries
# ---------------------------------------------------------------------------


@router.patch(
    "/{attendance_id}",
    response_model=AttendanceDetail,
    summary="Update attendance record status or fields",
)
def update_attendance_record(
    attendance_id: str,
    payload: AttendanceUpdate,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Update existing attendance record (e.g., correct status, times).
    """
    return service.update_record_status(
        attendance_id=attendance_id,
        payload=payload,
        actor_id=_supervisor.id,
    )


@router.get(
    "",
    response_model=List[AttendanceListItem],
    summary="List attendance records with filters",
)
def list_attendance(
    filters: AttendanceFilterParams = Depends(AttendanceFilterParams),
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    List attendance records using rich filtering and pagination.

    Returns lightweight items optimized for list views.
    """
    return service.list_attendance(
        filters=filters,
        pagination=pagination,
        actor_id=_admin.id,
    )


@router.get(
    "/daily-summary",
    response_model=DailyAttendanceSummary,
    summary="Get hostel-level daily attendance summary",
)
def get_daily_attendance_summary(
    hostel_id: Optional[str] = Query(None),
    date_value: Optional[str] = Query(
        None, alias="date", description="Date in YYYY-MM-DD; defaults to today"
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Get overall daily attendance summary for a hostel, including percentages and counts.
    """
    return service.get_daily_summary(
        hostel_id=hostel_id,
        date_str=date_value,
        actor_id=_admin.id,
    )


@router.get(
    "/students/{student_id}",
    response_model=List[AttendanceResponse],
    summary="Get attendance history for student",
)
def get_student_attendance(
    student_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Get full attendance history for a given student (admin/supervisor view).
    """
    return service.get_student_attendance(student_id=student_id, actor_id=_admin.id)


# ---------------------------------------------------------------------------
# Attendance corrections (with workflow)
# ---------------------------------------------------------------------------


@router.post(
    "/corrections",
    response_model=AttendanceCorrection,
    status_code=status.HTTP_201_CREATED,
    summary="Submit attendance correction request",
)
def submit_correction(
    payload: AttendanceCorrection,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceCorrectionService = Depends(get_correction_service),
) -> Any:
    """
    Submit a correction request for an existing attendance record.

    Uses AttendanceCorrectionService.submit_correction().
    """
    return service.submit_correction(payload=payload, actor_id=_supervisor.id)


@router.get(
    "/{attendance_id}/corrections",
    response_model=List[AttendanceCorrection],
    summary="Get correction history for an attendance record",
)
def get_correction_history(
    attendance_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceCorrectionService = Depends(get_correction_service),
) -> Any:
    return service.get_correction_history(attendance_id=attendance_id, actor_id=_admin.id)


@router.post(
    "/corrections/{correction_id}/approve",
    response_model=AttendanceCorrection,
    summary="Approve attendance correction",
)
def approve_correction(
    correction_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceCorrectionService = Depends(get_correction_service),
) -> Any:
    return service.approve_correction(correction_id=correction_id, actor_id=_admin.id)


@router.post(
    "/corrections/{correction_id}/reject",
    response_model=AttendanceCorrection,
    summary="Reject attendance correction",
)
def reject_correction(
    correction_id: str,
    reason: Optional[str] = Query(None, description="Rejection reason"),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceCorrectionService = Depends(get_correction_service),
) -> Any:
    return service.reject_correction(
        correction_id=correction_id,
        reason=reason,
        actor_id=_admin.id,
    )