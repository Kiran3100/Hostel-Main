"""
Referral Code Service

Manages the lifecycle of referral codes:
- Generation with collision handling
- Validation with comprehensive checks
- Listing codes for a user with pagination support
- Detailed stats per code with caching support
"""

from __future__ import annotations

import logging
from typing import List, Optional
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
from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.logging import LoggingContext

logger = logging.getLogger(__name__)


class ReferralCodeService:
    """
    High-level orchestration for referral codes.

    Delegates persistence and heavy logic to ReferralCodeRepository.
    Implements service-level validation and business rules.
    """

    def __init__(self, code_repo: ReferralCodeRepository) -> None:
        """
        Initialize the referral code service.

        Args:
            code_repo: Repository for referral code data operations
        """
        if not code_repo:
            raise ValueError("ReferralCodeRepository cannot be None")
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

        If the repository enforces uniqueness per (user, program), it will
        either return the existing code or create a new one accordingly.

        Args:
            db: Database session
            request: Code generation request with user_id, program_id, and optional custom code

        Returns:
            ReferralCodeResponse: Generated or existing referral code

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If business rules are violated
        """
        self._validate_generation_request(request)
        
        payload = request.model_dump(exclude_none=True)

        with LoggingContext(
            user_id=str(request.user_id),
            program_id=str(request.program_id),
            operation="generate_referral_code",
        ):
            try:
                obj = self.code_repo.generate_code(db, payload)
                
                logger.info(
                    "Referral code generated successfully",
                    extra={
                        "code": obj.code,
                        "user_id": str(request.user_id),
                        "program_id": str(request.program_id),
                    },
                )
                
                return ReferralCodeResponse.model_validate(obj)
                
            except Exception as e:
                logger.error(
                    f"Failed to generate referral code: {str(e)}",
                    extra={
                        "user_id": str(request.user_id),
                        "program_id": str(request.program_id),
                    },
                    exc_info=True,
                )
                raise

    def _validate_generation_request(self, request: ReferralCodeGenerate) -> None:
        """
        Validate code generation request.

        Args:
            request: Code generation request

        Raises:
            ValidationException: If validation fails
        """
        if not request.user_id:
            raise ValidationException("User ID is required for code generation")
        
        if not request.program_id:
            raise ValidationException("Program ID is required for code generation")
        
        # Validate custom code if provided
        if hasattr(request, 'custom_code') and request.custom_code:
            custom_code = request.custom_code.strip().upper()
            if len(custom_code) < 4:
                raise ValidationException("Custom code must be at least 4 characters")
            if len(custom_code) > 20:
                raise ValidationException("Custom code must not exceed 20 characters")
            if not custom_code.isalnum():
                raise ValidationException("Custom code must contain only alphanumeric characters")

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

        Performs comprehensive validation including:
        - Code existence and format
        - Code expiration
        - Usage limits
        - User eligibility
        - Program status

        Args:
            db: Database session
            request: Validation request with referral code and context

        Returns:
            CodeValidationResponse: Validation result with detailed information

        Raises:
            ValidationException: If the code format is invalid
        """
        if not request.referral_code:
            raise ValidationException("Referral code is required")
        
        code = request.referral_code.upper().strip()
        
        # Basic format validation
        if len(code) < 4 or len(code) > 20:
            return CodeValidationResponse(
                is_valid=False,
                referral_code=code,
                reason="Invalid code format",
            )
        
        ctx = request.model_dump(exclude_none=True)

        with LoggingContext(
            referral_code=code,
            operation="validate_referral_code",
        ):
            try:
                data = self.code_repo.validate_code(
                    db=db,
                    referral_code=code,
                    context=ctx,
                )
                
                # Repository returns dict with is_valid, program & referrer info, etc.
                response = CodeValidationResponse.model_validate(data)
                
                logger.info(
                    f"Referral code validation: {'valid' if response.is_valid else 'invalid'}",
                    extra={
                        "code": code,
                        "is_valid": response.is_valid,
                        "reason": response.reason if not response.is_valid else None,
                    },
                )
                
                return response
                
            except Exception as e:
                logger.error(
                    f"Error validating referral code: {str(e)}",
                    extra={"code": code},
                    exc_info=True,
                )
                # Return invalid response instead of raising
                return CodeValidationResponse(
                    is_valid=False,
                    referral_code=code,
                    reason="Validation error occurred",
                )

    # -------------------------------------------------------------------------
    # Listing & stats
    # -------------------------------------------------------------------------

    def list_codes_for_user(
        self,
        db: Session,
        user_id: UUID,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> List[ReferralCodeResponse]:
        """
        List all referral codes owned by a given user.

        Args:
            db: Database session
            user_id: User identifier
            active_only: If True, return only active codes
            page: Page number for pagination (1-indexed)
            page_size: Number of items per page

        Returns:
            List[ReferralCodeResponse]: List of referral codes

        Raises:
            ValidationException: If parameters are invalid
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        if page < 1:
            raise ValidationException("Page number must be at least 1")
        
        if page_size < 1 or page_size > 100:
            raise ValidationException("Page size must be between 1 and 100")

        with LoggingContext(
            user_id=str(user_id),
            operation="list_user_codes",
        ):
            try:
                objs = self.code_repo.get_codes_by_user(
                    db=db,
                    user_id=user_id,
                    active_only=active_only,
                    page=page,
                    page_size=page_size,
                )
                
                logger.debug(
                    f"Retrieved {len(objs)} referral codes for user",
                    extra={"user_id": str(user_id), "count": len(objs)},
                )
                
                return [ReferralCodeResponse.model_validate(o) for o in objs]
                
            except Exception as e:
                logger.error(
                    f"Failed to list codes for user: {str(e)}",
                    extra={"user_id": str(user_id)},
                    exc_info=True,
                )
                raise

    def get_code_stats(
        self,
        db: Session,
        referral_code: str,
        include_details: bool = False,
    ) -> ReferralCodeStats:
        """
        Get aggregated stats for a specific referral code.

        Args:
            db: Database session
            referral_code: The referral code to get stats for
            include_details: If True, include detailed breakdown

        Returns:
            ReferralCodeStats: Aggregated statistics for the code

        Raises:
            ValidationException: If the code is not found or invalid
        """
        if not referral_code:
            raise ValidationException("Referral code is required")
        
        code = referral_code.upper().strip()

        with LoggingContext(
            referral_code=code,
            operation="get_code_stats",
        ):
            try:
                obj = self.code_repo.get_stats_for_code(
                    db=db,
                    code=code,
                    include_details=include_details,
                )
                
                if not obj:
                    raise ValidationException(f"Referral code '{code}' not found")

                logger.debug(
                    "Retrieved stats for referral code",
                    extra={"code": code},
                )
                
                return ReferralCodeStats.model_validate(obj)
                
            except ValidationException:
                raise
            except Exception as e:
                logger.error(
                    f"Failed to get stats for code: {str(e)}",
                    extra={"code": code},
                    exc_info=True,
                )
                raise BusinessLogicException(
                    f"Unable to retrieve stats for code '{code}'"
                )

    # -------------------------------------------------------------------------
    # Deactivation & Management
    # -------------------------------------------------------------------------

    def deactivate_code(
        self,
        db: Session,
        referral_code: str,
        reason: Optional[str] = None,
    ) -> ReferralCodeResponse:
        """
        Deactivate a referral code.

        Args:
            db: Database session
            referral_code: Code to deactivate
            reason: Optional reason for deactivation

        Returns:
            ReferralCodeResponse: Updated code information

        Raises:
            ValidationException: If code not found
        """
        if not referral_code:
            raise ValidationException("Referral code is required")
        
        code = referral_code.upper().strip()

        with LoggingContext(
            referral_code=code,
            operation="deactivate_code",
        ):
            try:
                obj = self.code_repo.deactivate_code(
                    db=db,
                    code=code,
                    reason=reason,
                )
                
                if not obj:
                    raise ValidationException(f"Referral code '{code}' not found")
                
                logger.info(
                    "Referral code deactivated",
                    extra={"code": code, "reason": reason},
                )
                
                return ReferralCodeResponse.model_validate(obj)
                
            except ValidationException:
                raise
            except Exception as e:
                logger.error(
                    f"Failed to deactivate code: {str(e)}",
                    extra={"code": code},
                    exc_info=True,
                )
                raise

    def reactivate_code(
        self,
        db: Session,
        referral_code: str,
    ) -> ReferralCodeResponse:
        """
        Reactivate a previously deactivated referral code.

        Args:
            db: Database session
            referral_code: Code to reactivate

        Returns:
            ReferralCodeResponse: Updated code information

        Raises:
            ValidationException: If code not found
        """
        if not referral_code:
            raise ValidationException("Referral code is required")
        
        code = referral_code.upper().strip()

        with LoggingContext(
            referral_code=code,
            operation="reactivate_code",
        ):
            try:
                obj = self.code_repo.reactivate_code(db=db, code=code)
                
                if not obj:
                    raise ValidationException(f"Referral code '{code}' not found")
                
                logger.info("Referral code reactivated", extra={"code": code})
                
                return ReferralCodeResponse.model_validate(obj)
                
            except ValidationException:
                raise
            except Exception as e:
                logger.error(
                    f"Failed to reactivate code: {str(e)}",
                    extra={"code": code},
                    exc_info=True,
                )
                raise