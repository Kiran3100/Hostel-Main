"""
Referral Code Service

Manages the lifecycle of referral codes:
- Generation
- Validation
- Listing codes for a user
- Stats per code
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.referral import ReferralCodeRepository
from app.schemas.referral import (
    ReferralCodeGenerate,
    ReferralCodeResponse,
    CodeValidationRequest,
    CodeValidationResponse,
    ReferralCodeStats,
)
from app.core.exceptions import ValidationException
from app.core.logging import LoggingContext


class ReferralCodeService:
    """
    High-level orchestration for referral codes.

    Delegates persistence and heavy logic to ReferralCodeRepository.
    """

    def __init__(self, code_repo: ReferralCodeRepository) -> None:
        self.code_repo = code_repo

    # -------------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------------

    def generate_code(
        self,
        db: Session,
        request: ReferralCodeGenerate,
    ) -> ReferralCodeResponse:
        """
        Generate and persist a new referral code for a user+program.

        If the repository enforces uniqueness per (user, program), it should
        either return the existing code or create a new one accordingly.
        """
        payload = request.model_dump(exclude_none=True)

        with LoggingContext(
            user_id=str(request.user_id),
            program_id=str(request.program_id),
        ):
            obj = self.code_repo.generate_code(db, payload)

        return ReferralCodeResponse.model_validate(obj)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate_code(
        self,
        db: Session,
        request: CodeValidationRequest,
    ) -> CodeValidationResponse:
        """
        Validate whether a referral code is usable by the current user
        and in the given context (e.g., booking/registration).
        """
        code = request.referral_code.upper().strip()
        ctx = request.model_dump(exclude_none=True)

        with LoggingContext(referral_code=code):
            data = self.code_repo.validate_code(
                db=db,
                referral_code=code,
                context=ctx,
            )

        # Repository returns dict with is_valid, program & referrer info, etc.
        return CodeValidationResponse.model_validate(data)

    # -------------------------------------------------------------------------
    # Listing & stats
    # -------------------------------------------------------------------------

    def list_codes_for_user(
        self,
        db: Session,
        user_id: UUID,
    ) -> List[ReferralCodeResponse]:
        """
        List all referral codes owned by a given user.
        """
        objs = self.code_repo.get_codes_by_user(db, user_id)
        return [ReferralCodeResponse.model_validate(o) for o in objs]

    def get_code_stats(
        self,
        db: Session,
        referral_code: str,
    ) -> ReferralCodeStats:
        """
        Get aggregated stats for a specific referral code.
        """
        code = referral_code.upper().strip()
        obj = self.code_repo.get_stats_for_code(db, code)
        if not obj:
            raise ValidationException("Referral code not found")

        return ReferralCodeStats.model_validate(obj)