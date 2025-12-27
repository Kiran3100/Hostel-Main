from typing import Any, List

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.services.hostel.hostel_policy_service import HostelPolicyService

router = APIRouter(prefix="/hostels/policies", tags=["hostels:policies"])


def get_policy_service(db: Session = Depends(deps.get_db)) -> HostelPolicyService:
    return HostelPolicyService(db=db)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create policy",
)
def create_policy(
    payload: Any,  # Replace with PolicyCreate schema
    _admin=Depends(deps.get_admin_user),
    service: HostelPolicyService = Depends(get_policy_service),
) -> Any:
    return service.create_policy(payload)


@router.get(
    "",
    response_model=List[Any],  # Replace with PolicyResponse schema
    summary="List policies for hostel",
)
def list_policies(
    hostel_id: str = Query(...),
    service: HostelPolicyService = Depends(get_policy_service),
) -> Any:
    return service.list_policies(hostel_id)


@router.post(
    "/{policy_id}/acknowledge",
    summary="Acknowledge policy (student)",
)
def acknowledge_policy(
    policy_id: str,
    current_user=Depends(deps.get_student_user),
    service: HostelPolicyService = Depends(get_policy_service),
) -> Any:
    return service.acknowledge(policy_id, user_id=current_user.id)