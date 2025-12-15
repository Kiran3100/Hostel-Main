from datetime import date
from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.referral import ReferralProgramService
from app.schemas.referral.referral_program_base import ProgramCreate, ProgramUpdate
from app.schemas.referral.referral_program_response import ProgramResponse
from . import CurrentUser, get_current_user, get_current_admin

router = APIRouter(tags=["Referrals - Programs"])


def _get_service(session: Session) -> ReferralProgramService:
    uow = UnitOfWork(session)
    return ReferralProgramService(uow)


@router.get("/", response_model=List[ProgramResponse])
def list_programs(
    active_only: bool = Query(
        False,
        description="If true, return only active programs.",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[ProgramResponse]:
    """
    List referral programs (optionally active_only).

    Expected service method:
        list_programs(active_only: bool) -> list[ProgramResponse]
    """
    service = _get_service(session)
    return service.list_programs(active_only=active_only)


@router.get("/active", response_model=List[ProgramResponse])
def list_active_programs(
    as_of: Union[date, None] = Query(
        None,
        description="Filter programs active on this date (defaults to today).",
    ),
    session: Session = Depends(get_session),
) -> List[ProgramResponse]:
    """
    Public endpoint: list active referral programs (by validity window).
    """
    service = _get_service(session)
    # Expected service method:
    #   list_active_programs(as_of: Union[date, None]) -> list[ProgramResponse]
    return service.list_active_programs(as_of=as_of)


@router.get("/{program_id}", response_model=ProgramResponse)
def get_program(
    program_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ProgramResponse:
    """
    Get a single referral program by ID.
    """
    service = _get_service(session)
    # Expected: get_program(program_id: UUID) -> ProgramResponse
    return service.get_program(program_id=program_id)


@router.post(
    "/",
    response_model=ProgramResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_program(
    payload: ProgramCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> ProgramResponse:
    """
    Create a new referral program (admin-only).
    """
    service = _get_service(session)
    # Expected: create_program(data: ProgramCreate) -> ProgramResponse
    return service.create_program(data=payload)


@router.patch("/{program_id}", response_model=ProgramResponse)
def update_program(
    program_id: UUID,
    payload: ProgramUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> ProgramResponse:
    """
    Update an existing referral program (admin-only).
    """
    service = _get_service(session)
    # Expected: update_program(program_id: UUID, data: ProgramUpdate) -> ProgramResponse
    return service.update_program(
        program_id=program_id,
        data=payload,
    )