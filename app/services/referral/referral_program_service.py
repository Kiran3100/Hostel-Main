"""
Referral Program Service

Manages referral program definitions and their analytics:
- Create/update/delete programs
- List programs
- Program stats and analytics
- Program performance comparisons
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.referral import ReferralProgramRepository
from app.schemas.common import DateRangeFilter
from app.schemas.referral import (
    ProgramCreate,
    ProgramUpdate,
    ProgramResponse,
    ProgramList,
    ProgramStats,
    ProgramAnalytics,
    ProgramPerformance,
)
from app.core.exceptions import ValidationException


class ReferralProgramService:
    """
    High-level orchestration for referral programs.

    Delegates details to ReferralProgramRepository.
    """

    def __init__(self, program_repo: ReferralProgramRepository) -> None:
        self.program_repo = program_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_program(
        self,
        db: Session,
        request: ProgramCreate,
        created_by: UUID,
    ) -> ProgramResponse:
        payload = request.model_dump(exclude_none=True)
        payload["created_by"] = created_by

        obj = self.program_repo.create_program(db, payload)
        return ProgramResponse.model_validate(obj)

    def update_program(
        self,
        db: Session,
        program_id: UUID,
        request: ProgramUpdate,
        updated_by: UUID,
    ) -> ProgramResponse:
        program = self.program_repo.get_by_id(db, program_id)
        if not program:
            raise ValidationException("Referral program not found")

        data = request.model_dump(exclude_none=True)
        data["updated_by"] = updated_by

        updated = self.program_repo.update_program(db, program, data)
        return ProgramResponse.model_validate(updated)

    def delete_program(
        self,
        db: Session,
        program_id: UUID,
    ) -> None:
        program = self.program_repo.get_by_id(db, program_id)
        if not program:
            return
        self.program_repo.soft_delete_program(db, program)

    # -------------------------------------------------------------------------
    # Retrieval & listing
    # -------------------------------------------------------------------------

    def get_program(
        self,
        db: Session,
        program_id: UUID,
    ) -> ProgramResponse:
        program = self.program_repo.get_by_id(db, program_id)
        if not program:
            raise ValidationException("Referral program not found")
        return ProgramResponse.model_validate(program)

    def list_programs(
        self,
        db: Session,
        active_only: bool = True,
    ) -> ProgramList:
        """
        Return all programs (or only active ones) as a ProgramList wrapper.
        """
        data = self.program_repo.get_program_list(db, active_only=active_only)
        # Repository should produce a dict with the same structure as ProgramList
        return ProgramList.model_validate(data)

    # -------------------------------------------------------------------------
    # Stats & analytics
    # -------------------------------------------------------------------------

    def get_program_stats(
        self,
        db: Session,
        program_id: UUID,
        period: DateRangeFilter,
    ) -> ProgramStats:
        data = self.program_repo.get_program_stats(
            db=db,
            program_id=program_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No stats available for this program/period")
        return ProgramStats.model_validate(data)

    def get_program_analytics(
        self,
        db: Session,
        program_id: UUID,
        period: DateRangeFilter,
    ) -> ProgramAnalytics:
        data = self.program_repo.get_program_analytics(
            db=db,
            program_id=program_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No analytics available for this program/period")
        return ProgramAnalytics.model_validate(data)

    def compare_programs(
        self,
        db: Session,
        program_ids: List[UUID],
        period: DateRangeFilter,
    ) -> ProgramPerformance:
        """
        Compare multiple programs across relevant metrics for a time window.
        """
        if len(program_ids) < 2:
            raise ValidationException("At least two programs required for comparison")

        data = self.program_repo.get_program_performance_comparison(
            db=db,
            program_ids=program_ids,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No performance data for the specified programs")
        return ProgramPerformance.model_validate(data)