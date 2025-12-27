"""
Referral Program Service

Manages referral program definitions and their analytics:
- Create/update/delete programs with validation
- List programs with filtering
- Program stats and analytics with caching
- Program performance comparisons
- Program activation/deactivation
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

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
from app.core1.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)


class ReferralProgramService:
    """
    High-level orchestration for referral programs.

    Delegates data operations to ReferralProgramRepository.
    Implements business logic, validation, and analytics aggregation.
    """

    def __init__(self, program_repo: ReferralProgramRepository) -> None:
        """
        Initialize the referral program service.

        Args:
            program_repo: Repository for program data operations

        Raises:
            ValueError: If repository is None
        """
        if not program_repo:
            raise ValueError("ReferralProgramRepository cannot be None")
        self.program_repo = program_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_program(
        self,
        db: Session,
        request: ProgramCreate,
        created_by: UUID,
    ) -> ProgramResponse:
        """
        Create a new referral program.

        Args:
            db: Database session
            request: Program creation request
            created_by: ID of user creating the program

        Returns:
            ProgramResponse: Created program

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If business rules are violated
        """
        self._validate_program_create(request)
        
        payload = request.model_dump(exclude_none=True)
        payload["created_by"] = created_by
        payload["created_at"] = datetime.utcnow()

        try:
            obj = self.program_repo.create_program(db, payload)
            
            logger.info(
                "Referral program created",
                extra={
                    "program_id": str(obj.id),
                    "program_name": obj.name,
                    "created_by": str(created_by),
                },
            )
            
            return ProgramResponse.model_validate(obj)
            
        except Exception as e:
            logger.error(
                f"Failed to create program: {str(e)}",
                extra={"program_name": request.name},
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to create program: {str(e)}")

    def update_program(
        self,
        db: Session,
        program_id: UUID,
        request: ProgramUpdate,
        updated_by: UUID,
    ) -> ProgramResponse:
        """
        Update an existing referral program.

        Args:
            db: Database session
            program_id: ID of program to update
            request: Program update request
            updated_by: ID of user updating the program

        Returns:
            ProgramResponse: Updated program

        Raises:
            ValidationException: If program not found or validation fails
        """
        program = self.program_repo.get_by_id(db, program_id)
        if not program:
            raise ValidationException(f"Referral program with ID '{program_id}' not found")

        self._validate_program_update(request, program)
        
        data = request.model_dump(exclude_none=True)
        data["updated_by"] = updated_by
        data["updated_at"] = datetime.utcnow()

        try:
            updated = self.program_repo.update_program(db, program, data)
            
            logger.info(
                "Referral program updated",
                extra={
                    "program_id": str(program_id),
                    "updated_by": str(updated_by),
                },
            )
            
            return ProgramResponse.model_validate(updated)
            
        except Exception as e:
            logger.error(
                f"Failed to update program: {str(e)}",
                extra={"program_id": str(program_id)},
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to update program: {str(e)}")

    def delete_program(
        self,
        db: Session,
        program_id: UUID,
        deleted_by: Optional[UUID] = None,
    ) -> None:
        """
        Soft delete a referral program.

        Args:
            db: Database session
            program_id: ID of program to delete
            deleted_by: ID of user deleting the program

        Raises:
            ValidationException: If program not found or has active referrals
        """
        program = self.program_repo.get_by_id(db, program_id)
        if not program:
            logger.warning(
                f"Attempted to delete non-existent program: {program_id}"
            )
            return

        # Check if program has active referrals
        if self.program_repo.has_active_referrals(db, program_id):
            raise BusinessLogicException(
                "Cannot delete program with active referrals. "
                "Please deactivate the program instead."
            )

        try:
            self.program_repo.soft_delete_program(
                db=db,
                program=program,
                deleted_by=deleted_by,
            )
            
            logger.info(
                "Referral program deleted",
                extra={
                    "program_id": str(program_id),
                    "deleted_by": str(deleted_by) if deleted_by else None,
                },
            )
            
        except Exception as e:
            logger.error(
                f"Failed to delete program: {str(e)}",
                extra={"program_id": str(program_id)},
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Retrieval & Listing
    # -------------------------------------------------------------------------

    def get_program(
        self,
        db: Session,
        program_id: UUID,
        include_stats: bool = False,
    ) -> ProgramResponse:
        """
        Get a specific referral program by ID.

        Args:
            db: Database session
            program_id: ID of program to retrieve
            include_stats: If True, include basic statistics

        Returns:
            ProgramResponse: Program details

        Raises:
            ValidationException: If program not found
        """
        if not program_id:
            raise ValidationException("Program ID is required")

        try:
            program = self.program_repo.get_by_id(
                db=db,
                program_id=program_id,
                include_stats=include_stats,
            )
            
            if not program:
                raise ValidationException(
                    f"Referral program with ID '{program_id}' not found"
                )
            
            return ProgramResponse.model_validate(program)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to retrieve program: {str(e)}",
                extra={"program_id": str(program_id)},
                exc_info=True,
            )
            raise

    def list_programs(
        self,
        db: Session,
        active_only: bool = True,
        program_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ProgramList:
        """
        Return all programs (or only active ones) as a ProgramList wrapper.

        Args:
            db: Database session
            active_only: If True, return only active programs
            program_type: Optional filter by program type
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            ProgramList: List of programs with metadata

        Raises:
            ValidationException: If parameters are invalid
        """
        if page < 1:
            raise ValidationException("Page number must be at least 1")
        
        if page_size < 1 or page_size > 100:
            raise ValidationException("Page size must be between 1 and 100")

        try:
            data = self.program_repo.get_program_list(
                db=db,
                active_only=active_only,
                program_type=program_type,
                page=page,
                page_size=page_size,
            )
            
            # Repository should produce a dict with the same structure as ProgramList
            program_list = ProgramList.model_validate(data)
            
            logger.debug(
                f"Retrieved {len(program_list.programs)} programs",
                extra={
                    "active_only": active_only,
                    "program_type": program_type,
                    "page": page,
                },
            )
            
            return program_list
            
        except Exception as e:
            logger.error(
                f"Failed to list programs: {str(e)}",
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Stats & Analytics
    # -------------------------------------------------------------------------

    def get_program_stats(
        self,
        db: Session,
        program_id: UUID,
        period: DateRangeFilter,
    ) -> ProgramStats:
        """
        Get aggregated statistics for a program over a time period.

        Args:
            db: Database session
            program_id: ID of the program
            period: Date range for statistics

        Returns:
            ProgramStats: Aggregated statistics

        Raises:
            ValidationException: If program not found or invalid period
        """
        if not program_id:
            raise ValidationException("Program ID is required")
        
        self._validate_date_range(period)

        try:
            data = self.program_repo.get_program_stats(
                db=db,
                program_id=program_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not data:
                raise ValidationException(
                    f"No stats available for program '{program_id}' in the specified period"
                )
            
            logger.debug(
                "Retrieved program stats",
                extra={
                    "program_id": str(program_id),
                    "period": f"{period.start_date} to {period.end_date}",
                },
            )
            
            return ProgramStats.model_validate(data)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to retrieve program stats: {str(e)}",
                extra={"program_id": str(program_id)},
                exc_info=True,
            )
            raise

    def get_program_analytics(
        self,
        db: Session,
        program_id: UUID,
        period: DateRangeFilter,
        granularity: str = "daily",
    ) -> ProgramAnalytics:
        """
        Get detailed analytics for a program including trends and breakdowns.

        Args:
            db: Database session
            program_id: ID of the program
            period: Date range for analytics
            granularity: Time granularity (daily, weekly, monthly)

        Returns:
            ProgramAnalytics: Detailed analytics

        Raises:
            ValidationException: If program not found or invalid parameters
        """
        if not program_id:
            raise ValidationException("Program ID is required")
        
        self._validate_date_range(period)
        
        if granularity not in ["daily", "weekly", "monthly"]:
            raise ValidationException(
                "Granularity must be one of: daily, weekly, monthly"
            )

        try:
            data = self.program_repo.get_program_analytics(
                db=db,
                program_id=program_id,
                start_date=period.start_date,
                end_date=period.end_date,
                granularity=granularity,
            )
            
            if not data:
                raise ValidationException(
                    f"No analytics available for program '{program_id}' in the specified period"
                )
            
            logger.debug(
                "Retrieved program analytics",
                extra={
                    "program_id": str(program_id),
                    "granularity": granularity,
                },
            )
            
            return ProgramAnalytics.model_validate(data)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to retrieve program analytics: {str(e)}",
                extra={"program_id": str(program_id)},
                exc_info=True,
            )
            raise

    def compare_programs(
        self,
        db: Session,
        program_ids: List[UUID],
        period: DateRangeFilter,
        metrics: Optional[List[str]] = None,
    ) -> ProgramPerformance:
        """
        Compare multiple programs across relevant metrics for a time window.

        Args:
            db: Database session
            program_ids: List of program IDs to compare (2-10 programs)
            period: Date range for comparison
            metrics: Optional list of specific metrics to compare

        Returns:
            ProgramPerformance: Comparative performance data

        Raises:
            ValidationException: If parameters are invalid
        """
        if not program_ids:
            raise ValidationException("Program IDs are required")
        
        if len(program_ids) < 2:
            raise ValidationException(
                "At least two programs required for comparison"
            )
        
        if len(program_ids) > 10:
            raise ValidationException(
                "Cannot compare more than 10 programs at once"
            )
        
        self._validate_date_range(period)

        try:
            data = self.program_repo.get_program_performance_comparison(
                db=db,
                program_ids=program_ids,
                start_date=period.start_date,
                end_date=period.end_date,
                metrics=metrics,
            )
            
            if not data:
                raise ValidationException(
                    "No performance data available for the specified programs"
                )
            
            logger.info(
                "Programs compared",
                extra={
                    "program_count": len(program_ids),
                    "period": f"{period.start_date} to {period.end_date}",
                },
            )
            
            return ProgramPerformance.model_validate(data)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to compare programs: {str(e)}",
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Program Management
    # -------------------------------------------------------------------------

    def activate_program(
        self,
        db: Session,
        program_id: UUID,
        activated_by: UUID,
    ) -> ProgramResponse:
        """
        Activate a referral program.

        Args:
            db: Database session
            program_id: ID of program to activate
            activated_by: ID of user activating the program

        Returns:
            ProgramResponse: Updated program

        Raises:
            ValidationException: If program not found
        """
        program = self.program_repo.get_by_id(db, program_id)
        if not program:
            raise ValidationException(
                f"Referral program with ID '{program_id}' not found"
            )

        try:
            updated = self.program_repo.activate_program(
                db=db,
                program=program,
                activated_by=activated_by,
            )
            
            logger.info(
                "Referral program activated",
                extra={
                    "program_id": str(program_id),
                    "activated_by": str(activated_by),
                },
            )
            
            return ProgramResponse.model_validate(updated)
            
        except Exception as e:
            logger.error(
                f"Failed to activate program: {str(e)}",
                extra={"program_id": str(program_id)},
                exc_info=True,
            )
            raise

    def deactivate_program(
        self,
        db: Session,
        program_id: UUID,
        deactivated_by: UUID,
        reason: Optional[str] = None,
    ) -> ProgramResponse:
        """
        Deactivate a referral program.

        Args:
            db: Database session
            program_id: ID of program to deactivate
            deactivated_by: ID of user deactivating the program
            reason: Optional reason for deactivation

        Returns:
            ProgramResponse: Updated program

        Raises:
            ValidationException: If program not found
        """
        program = self.program_repo.get_by_id(db, program_id)
        if not program:
            raise ValidationException(
                f"Referral program with ID '{program_id}' not found"
            )

        try:
            updated = self.program_repo.deactivate_program(
                db=db,
                program=program,
                deactivated_by=deactivated_by,
                reason=reason,
            )
            
            logger.info(
                "Referral program deactivated",
                extra={
                    "program_id": str(program_id),
                    "deactivated_by": str(deactivated_by),
                    "reason": reason,
                },
            )
            
            return ProgramResponse.model_validate(updated)
            
        except Exception as e:
            logger.error(
                f"Failed to deactivate program: {str(e)}",
                extra={"program_id": str(program_id)},
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_program_create(self, request: ProgramCreate) -> None:
        """
        Validate program creation request.

        Args:
            request: Program creation request

        Raises:
            ValidationException: If validation fails
        """
        if not request.name or not request.name.strip():
            raise ValidationException("Program name is required")
        
        if len(request.name) > 200:
            raise ValidationException("Program name must not exceed 200 characters")
        
        # Validate dates if provided
        if hasattr(request, 'start_date') and hasattr(request, 'end_date'):
            if request.start_date and request.end_date:
                if request.end_date <= request.start_date:
                    raise ValidationException(
                        "End date must be after start date"
                    )
        
        # Validate reward amounts if provided
        if hasattr(request, 'referrer_reward_amount') and request.referrer_reward_amount:
            if float(request.referrer_reward_amount) < 0:
                raise ValidationException(
                    "Referrer reward amount cannot be negative"
                )
        
        if hasattr(request, 'referee_reward_amount') and request.referee_reward_amount:
            if float(request.referee_reward_amount) < 0:
                raise ValidationException(
                    "Referee reward amount cannot be negative"
                )

    def _validate_program_update(
        self,
        request: ProgramUpdate,
        existing_program: any,
    ) -> None:
        """
        Validate program update request.

        Args:
            request: Program update request
            existing_program: Current program object

        Raises:
            ValidationException: If validation fails
        """
        if hasattr(request, 'name') and request.name is not None:
            if not request.name.strip():
                raise ValidationException("Program name cannot be empty")
            
            if len(request.name) > 200:
                raise ValidationException(
                    "Program name must not exceed 200 characters"
                )
        
        # Validate dates if being updated
        start_date = getattr(request, 'start_date', None) or existing_program.start_date
        end_date = getattr(request, 'end_date', None) or existing_program.end_date
        
        if start_date and end_date and end_date <= start_date:
            raise ValidationException("End date must be after start date")

    def _validate_date_range(self, period: DateRangeFilter) -> None:
        """
        Validate date range parameters.

        Args:
            period: Date range filter

        Raises:
            ValidationException: If date range is invalid
        """
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")
        
        if period.end_date < period.start_date:
            raise ValidationException("End date must be after or equal to start date")
        
        # Check if date range is too large (e.g., max 2 years)
        max_days = 730  # 2 years
        date_diff = (period.end_date - period.start_date).days
        
        if date_diff > max_days:
            raise ValidationException(
                f"Date range cannot exceed {max_days} days"
            )