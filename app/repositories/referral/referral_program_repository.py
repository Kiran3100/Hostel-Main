# --- File: app/repositories/referral/referral_program_repository.py ---
"""
Referral Program Repository.

Manages referral programs with eligibility checking, performance tracking,
and program lifecycle management.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.referral.referral_program import ReferralProgram
from app.models.referral.referral import Referral
from app.models.referral.referral_code import ReferralCode
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
    BusinessLogicError,
)

__all__ = ["ReferralProgramRepository"]


class ReferralProgramRepository(BaseRepository[ReferralProgram]):
    """
    Referral Program Repository.
    
    Provides comprehensive program management with eligibility checking,
    performance analytics, and lifecycle management.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        super().__init__(ReferralProgram, session)

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    async def create_program(
        self,
        program_name: str,
        program_code: str,
        program_type: str,
        reward_type: str,
        referrer_reward_amount: Optional[Decimal] = None,
        referee_reward_amount: Optional[Decimal] = None,
        currency: str = "INR",
        description: Optional[str] = None,
        min_booking_amount: Optional[Decimal] = None,
        min_stay_months: Optional[int] = None,
        min_referrer_stay_months: Optional[int] = None,
        max_referrals_per_user: Optional[int] = None,
        allowed_user_roles: Optional[List[str]] = None,
        valid_from: Optional[date] = None,
        valid_to: Optional[date] = None,
        terms_and_conditions: Optional[str] = None,
        auto_approve_rewards: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[UUID] = None,
    ) -> ReferralProgram:
        """
        Create a new referral program.
        
        Args:
            program_name: Unique program name
            program_code: Unique program code
            program_type: Type of program
            reward_type: Type of reward
            referrer_reward_amount: Reward for referrer
            referee_reward_amount: Reward for referee
            currency: Currency code
            description: Program description
            min_booking_amount: Minimum booking amount
            min_stay_months: Minimum stay duration
            min_referrer_stay_months: Minimum referrer tenure
            max_referrals_per_user: Maximum referrals per user
            allowed_user_roles: Eligible user roles
            valid_from: Start date
            valid_to: End date
            terms_and_conditions: T&C text
            auto_approve_rewards: Auto-approve flag
            metadata: Additional metadata
            created_by: Creator user ID
            
        Returns:
            Created program
            
        Raises:
            ValidationError: If validation fails
        """
        # Check uniqueness
        existing_name = await self.get_by_name(program_name)
        if existing_name:
            raise ValidationError(f"Program name '{program_name}' already exists")

        existing_code = await self.get_by_code(program_code)
        if existing_code:
            raise ValidationError(f"Program code '{program_code}' already exists")

        # Validate dates
        if valid_from and valid_to and valid_to <= valid_from:
            raise ValidationError("End date must be after start date")

        program = ReferralProgram(
            program_name=program_name,
            program_code=program_code,
            program_type=program_type,
            reward_type=reward_type,
            referrer_reward_amount=referrer_reward_amount,
            referee_reward_amount=referee_reward_amount,
            currency=currency,
            description=description,
            min_booking_amount=min_booking_amount,
            min_stay_months=min_stay_months,
            min_referrer_stay_months=min_referrer_stay_months,
            max_referrals_per_user=max_referrals_per_user,
            allowed_user_roles=allowed_user_roles or ["student", "alumni"],
            valid_from=valid_from,
            valid_to=valid_to,
            terms_and_conditions=terms_and_conditions,
            auto_approve_rewards=auto_approve_rewards,
            is_active=True,
            metadata=metadata,
            created_by=created_by,
        )

        self.session.add(program)
        await self.session.flush()
        
        return program

    async def get_program_by_id(
        self,
        program_id: UUID,
        include_relationships: bool = True,
    ) -> Optional[ReferralProgram]:
        """
        Get program by ID with optional relationships.
        
        Args:
            program_id: Program ID
            include_relationships: Include related entities
            
        Returns:
            Program if found, None otherwise
        """
        query = select(ReferralProgram).where(
            ReferralProgram.id == program_id
        )

        if include_relationships:
            query = query.options(
                selectinload(ReferralProgram.referrals),
                selectinload(ReferralProgram.referral_codes),
            )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, program_name: str) -> Optional[ReferralProgram]:
        """
        Get program by name.
        
        Args:
            program_name: Program name
            
        Returns:
            Program if found, None otherwise
        """
        query = select(ReferralProgram).where(
            ReferralProgram.program_name == program_name
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_code(self, program_code: str) -> Optional[ReferralProgram]:
        """
        Get program by code.
        
        Args:
            program_code: Program code
            
        Returns:
            Program if found, None otherwise
        """
        query = select(ReferralProgram).where(
            ReferralProgram.program_code == program_code
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_program(
        self,
        program_id: UUID,
        update_data: Dict[str, Any],
        updated_by: Optional[UUID] = None,
    ) -> ReferralProgram:
        """
        Update program details.
        
        Args:
            program_id: Program ID
            update_data: Data to update
            updated_by: User performing update
            
        Returns:
            Updated program
            
        Raises:
            EntityNotFoundError: If program not found
        """
        program = await self.get_program_by_id(program_id)
        if not program:
            raise EntityNotFoundError(f"Program {program_id} not found")

        # Prevent updating unique identifiers
        for key in ["program_name", "program_code"]:
            if key in update_data:
                del update_data[key]

        for key, value in update_data.items():
            if hasattr(program, key):
                setattr(program, key, value)

        if updated_by:
            program.updated_by = updated_by

        await self.session.flush()
        return program

    # ============================================================================
    # PROGRAM LOOKUP OPERATIONS
    # ============================================================================

    async def find_active_programs(
        self,
        program_type: Optional[str] = None,
    ) -> List[ReferralProgram]:
        """
        Find all active programs.
        
        Args:
            program_type: Filter by program type
            
        Returns:
            List of active programs
        """
        today = date.today()

        query = select(ReferralProgram).where(
            and_(
                ReferralProgram.is_active == True,
                ReferralProgram.is_deleted == False,
                or_(
                    ReferralProgram.valid_from.is_(None),
                    ReferralProgram.valid_from <= today,
                ),
                or_(
                    ReferralProgram.valid_to.is_(None),
                    ReferralProgram.valid_to >= today,
                ),
            )
        )

        if program_type:
            query = query.where(ReferralProgram.program_type == program_type)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_type(
        self,
        program_type: str,
        is_active: Optional[bool] = None,
    ) -> List[ReferralProgram]:
        """
        Find programs by type.
        
        Args:
            program_type: Program type
            is_active: Filter by active status
            
        Returns:
            List of programs
        """
        query = select(ReferralProgram).where(
            ReferralProgram.program_type == program_type
        )

        if is_active is not None:
            query = query.where(ReferralProgram.is_active == is_active)

        query = query.order_by(ReferralProgram.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_expiring_programs(
        self, days_ahead: int = 30
    ) -> List[ReferralProgram]:
        """
        Find programs expiring within specified days.
        
        Args:
            days_ahead: Days ahead to check
            
        Returns:
            List of expiring programs
        """
        future_date = date.today() + timedelta(days=days_ahead)

        query = (
            select(ReferralProgram)
            .where(
                and_(
                    ReferralProgram.is_active == True,
                    ReferralProgram.valid_to.isnot(None),
                    ReferralProgram.valid_to <= future_date,
                    ReferralProgram.valid_to >= date.today(),
                )
            )
            .order_by(ReferralProgram.valid_to.asc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_upcoming_programs(
        self, days_ahead: int = 30
    ) -> List[ReferralProgram]:
        """
        Find programs starting within specified days.
        
        Args:
            days_ahead: Days ahead to check
            
        Returns:
            List of upcoming programs
        """
        future_date = date.today() + timedelta(days=days_ahead)

        query = (
            select(ReferralProgram)
            .where(
                and_(
                    ReferralProgram.is_active == True,
                    ReferralProgram.valid_from.isnot(None),
                    ReferralProgram.valid_from > date.today(),
                    ReferralProgram.valid_from <= future_date,
                )
            )
            .order_by(ReferralProgram.valid_from.asc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # ELIGIBILITY CHECKING
    # ============================================================================

    async def check_user_eligibility(
        self,
        program_id: UUID,
        user_role: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user role is eligible for program.
        
        Args:
            program_id: Program ID
            user_role: User's role
            
        Returns:
            Tuple of (is_eligible, reason)
        """
        program = await self.get_program_by_id(program_id)
        if not program:
            return False, "Program not found"

        if not program.is_active:
            return False, "Program is not active"

        if not program.is_currently_valid:
            if program.is_expired:
                return False, "Program has expired"
            elif program.is_upcoming:
                return False, "Program has not started yet"

        if user_role not in program.allowed_user_roles:
            return False, f"User role '{user_role}' is not eligible for this program"

        return True, None

    async def check_referral_limit(
        self,
        program_id: UUID,
        user_id: UUID,
    ) -> tuple[bool, Optional[str], int]:
        """
        Check if user has reached referral limit.
        
        Args:
            program_id: Program ID
            user_id: User ID
            
        Returns:
            Tuple of (can_refer, reason, current_count)
        """
        program = await self.get_program_by_id(program_id)
        if not program:
            return False, "Program not found", 0

        if program.max_referrals_per_user is None:
            return True, None, 0

        # Count user's referrals in this program
        count_query = select(func.count()).select_from(Referral).where(
            and_(
                Referral.program_id == program_id,
                Referral.referrer_id == user_id,
            )
        )
        result = await self.session.execute(count_query)
        current_count = result.scalar_one()

        if current_count >= program.max_referrals_per_user:
            return (
                False,
                f"Maximum referral limit ({program.max_referrals_per_user}) reached",
                current_count,
            )

        return True, None, current_count

    async def validate_booking_eligibility(
        self,
        program_id: UUID,
        booking_amount: Decimal,
        stay_duration_months: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if booking meets program criteria.
        
        Args:
            program_id: Program ID
            booking_amount: Booking amount
            stay_duration_months: Stay duration
            
        Returns:
            Tuple of (is_eligible, reason)
        """
        program = await self.get_program_by_id(program_id)
        if not program:
            return False, "Program not found"

        # Check minimum booking amount
        if program.min_booking_amount and booking_amount < program.min_booking_amount:
            return (
                False,
                f"Booking amount must be at least {program.min_booking_amount}",
            )

        # Check minimum stay duration
        if program.min_stay_months and stay_duration_months < program.min_stay_months:
            return (
                False,
                f"Stay duration must be at least {program.min_stay_months} months",
            )

        return True, None

    # ============================================================================
    # PROGRAM MANAGEMENT
    # ============================================================================

    async def activate_program(
        self,
        program_id: UUID,
        activated_by: Optional[UUID] = None,
    ) -> ReferralProgram:
        """
        Activate a program.
        
        Args:
            program_id: Program ID
            activated_by: User activating program
            
        Returns:
            Updated program
        """
        program = await self.get_program_by_id(program_id)
        if not program:
            raise EntityNotFoundError(f"Program {program_id} not found")

        program.is_active = True
        if activated_by:
            program.updated_by = activated_by

        await self.session.flush()
        return program

    async def deactivate_program(
        self,
        program_id: UUID,
        deactivated_by: Optional[UUID] = None,
    ) -> ReferralProgram:
        """
        Deactivate a program.
        
        Args:
            program_id: Program ID
            deactivated_by: User deactivating program
            
        Returns:
            Updated program
        """
        program = await self.get_program_by_id(program_id)
        if not program:
            raise EntityNotFoundError(f"Program {program_id} not found")

        program.is_active = False
        if deactivated_by:
            program.updated_by = deactivated_by

        await self.session.flush()
        return program

    async def extend_program(
        self,
        program_id: UUID,
        new_end_date: date,
        extended_by: Optional[UUID] = None,
    ) -> ReferralProgram:
        """
        Extend program end date.
        
        Args:
            program_id: Program ID
            new_end_date: New end date
            extended_by: User extending program
            
        Returns:
            Updated program
        """
        program = await self.get_program_by_id(program_id)
        if not program:
            raise EntityNotFoundError(f"Program {program_id} not found")

        if program.valid_to and new_end_date <= program.valid_to:
            raise ValidationError("New end date must be after current end date")

        program.valid_to = new_end_date
        if extended_by:
            program.updated_by = extended_by

        await self.session.flush()
        return program

    # ============================================================================
    # STATISTICS MANAGEMENT
    # ============================================================================

    async def increment_referral_count(self, program_id: UUID) -> None:
        """
        Increment total referral count for program.
        
        Args:
            program_id: Program ID
        """
        program = await self.get_program_by_id(
            program_id, include_relationships=False
        )
        if program:
            program.increment_referral_count()
            program.increment_pending_referrals()
            await self.session.flush()

    async def increment_successful_referrals(self, program_id: UUID) -> None:
        """
        Increment successful referral count.
        
        Args:
            program_id: Program ID
        """
        program = await self.get_program_by_id(
            program_id, include_relationships=False
        )
        if program:
            program.increment_successful_referrals()
            await self.session.flush()

    async def add_reward_amount(
        self,
        program_id: UUID,
        amount: Decimal,
    ) -> None:
        """
        Add to total rewards distributed.
        
        Args:
            program_id: Program ID
            amount: Reward amount to add
        """
        program = await self.get_program_by_id(
            program_id, include_relationships=False
        )
        if program:
            program.add_reward_amount(amount)
            await self.session.flush()

    async def recalculate_statistics(self, program_id: UUID) -> ReferralProgram:
        """
        Recalculate program statistics from actual data.
        
        Args:
            program_id: Program ID
            
        Returns:
            Updated program with recalculated stats
        """
        from app.schemas.common.enums import ReferralStatus

        program = await self.get_program_by_id(program_id)
        if not program:
            raise EntityNotFoundError(f"Program {program_id} not found")

        # Count total referrals
        total_query = select(func.count()).select_from(Referral).where(
            Referral.program_id == program_id
        )
        total_result = await self.session.execute(total_query)
        program.total_referrals = total_result.scalar_one()

        # Count successful referrals
        success_query = (
            select(func.count())
            .select_from(Referral)
            .where(
                and_(
                    Referral.program_id == program_id,
                    Referral.status == ReferralStatus.COMPLETED,
                )
            )
        )
        success_result = await self.session.execute(success_query)
        program.successful_referrals = success_result.scalar_one()

        # Count pending referrals
        pending_query = (
            select(func.count())
            .select_from(Referral)
            .where(
                and_(
                    Referral.program_id == program_id,
                    Referral.status == ReferralStatus.PENDING,
                )
            )
        )
        pending_result = await self.session.execute(pending_query)
        program.pending_referrals = pending_result.scalar_one()

        # Calculate total rewards
        rewards_query = (
            select(
                func.sum(
                    Referral.referrer_reward_amount + Referral.referee_reward_amount
                )
            )
            .select_from(Referral)
            .where(Referral.program_id == program_id)
        )
        rewards_result = await self.session.execute(rewards_query)
        total_rewards = rewards_result.scalar_one()
        program.total_rewards_distributed = total_rewards or Decimal("0.00")

        await self.session.flush()
        return program

    # ============================================================================
    # ANALYTICS & REPORTING
    # ============================================================================

    async def get_program_statistics(
        self, program_id: UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive program statistics.
        
        Args:
            program_id: Program ID
            
        Returns:
            Dictionary of statistics
        """
        program = await self.get_program_by_id(program_id, include_relationships=True)
        if not program:
            raise EntityNotFoundError(f"Program {program_id} not found")

        return {
            "program_id": str(program.id),
            "program_name": program.program_name,
            "program_code": program.program_code,
            "program_type": program.program_type,
            "is_active": program.is_active,
            "is_currently_valid": program.is_currently_valid,
            "is_expired": program.is_expired,
            "is_upcoming": program.is_upcoming,
            "total_referrals": program.total_referrals,
            "successful_referrals": program.successful_referrals,
            "pending_referrals": program.pending_referrals,
            "conversion_rate": float(program.conversion_rate),
            "total_rewards_distributed": float(program.total_rewards_distributed),
            "referrer_reward_amount": (
                float(program.referrer_reward_amount)
                if program.referrer_reward_amount
                else None
            ),
            "referee_reward_amount": (
                float(program.referee_reward_amount)
                if program.referee_reward_amount
                else None
            ),
            "valid_from": program.valid_from.isoformat() if program.valid_from else None,
            "valid_to": program.valid_to.isoformat() if program.valid_to else None,
        }

    async def get_program_performance_comparison(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Compare performance across all programs.
        
        Returns:
            List of programs with comparative metrics
        """
        query = select(ReferralProgram).order_by(
            ReferralProgram.successful_referrals.desc()
        )

        result = await self.session.execute(query)
        programs = result.scalars().all()

        comparison = []
        for program in programs:
            comparison.append({
                "program_id": str(program.id),
                "program_name": program.program_name,
                "program_code": program.program_code,
                "is_active": program.is_active,
                "total_referrals": program.total_referrals,
                "successful_referrals": program.successful_referrals,
                "conversion_rate": float(program.conversion_rate),
                "total_rewards": float(program.total_rewards_distributed),
                "avg_reward_per_conversion": (
                    float(
                        program.total_rewards_distributed
                        / program.successful_referrals
                    )
                    if program.successful_referrals > 0
                    else 0
                ),
            })

        return comparison

    async def get_program_timeline_data(
        self,
        program_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        interval: str = "day",
    ) -> List[Dict[str, Any]]:
        """
        Get timeline data for program performance.
        
        Args:
            program_id: Program ID
            start_date: Start date for analysis
            end_date: End date for analysis
            interval: Grouping interval (day, week, month)
            
        Returns:
            Timeline data points
        """
        from app.schemas.common.enums import ReferralStatus

        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Get referrals in date range
        query = (
            select(Referral)
            .where(
                and_(
                    Referral.program_id == program_id,
                    Referral.created_at >= start_date,
                    Referral.created_at <= end_date,
                )
            )
            .order_by(Referral.created_at)
        )

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        # Group by interval
        timeline = {}
        for referral in referrals:
            if interval == "day":
                key = referral.created_at.date().isoformat()
            elif interval == "week":
                key = referral.created_at.strftime("%Y-W%W")
            else:  # month
                key = referral.created_at.strftime("%Y-%m")

            if key not in timeline:
                timeline[key] = {
                    "date": key,
                    "total_referrals": 0,
                    "completed": 0,
                    "pending": 0,
                    "cancelled": 0,
                }

            timeline[key]["total_referrals"] += 1

            if referral.status == ReferralStatus.COMPLETED:
                timeline[key]["completed"] += 1
            elif referral.status == ReferralStatus.PENDING:
                timeline[key]["pending"] += 1
            elif referral.status == ReferralStatus.CANCELLED:
                timeline[key]["cancelled"] += 1

        return sorted(timeline.values(), key=lambda x: x["date"])

    # ============================================================================
    # SEARCH & FILTER
    # ============================================================================

    async def search_programs(
        self,
        search_term: Optional[str] = None,
        program_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_currently_valid: Optional[bool] = None,
        min_conversion_rate: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ReferralProgram], int]:
        """
        Search programs with filters.
        
        Args:
            search_term: Search in name, code, description
            program_type: Filter by type
            is_active: Filter by active status
            is_currently_valid: Filter by current validity
            min_conversion_rate: Minimum conversion rate
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (programs, total_count)
        """
        query = select(ReferralProgram)

        conditions = []

        # Search term
        if search_term:
            search_pattern = f"%{search_term}%"
            conditions.append(
                or_(
                    ReferralProgram.program_name.ilike(search_pattern),
                    ReferralProgram.program_code.ilike(search_pattern),
                    ReferralProgram.description.ilike(search_pattern),
                )
            )

        # Type filter
        if program_type:
            conditions.append(ReferralProgram.program_type == program_type)

        # Active status
        if is_active is not None:
            conditions.append(ReferralProgram.is_active == is_active)

        # Currently valid
        if is_currently_valid:
            today = date.today()
            conditions.append(
                and_(
                    or_(
                        ReferralProgram.valid_from.is_(None),
                        ReferralProgram.valid_from <= today,
                    ),
                    or_(
                        ReferralProgram.valid_to.is_(None),
                        ReferralProgram.valid_to >= today,
                    ),
                )
            )

        if conditions:
            query = query.where(and_(*conditions))

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query
        query = query.order_by(ReferralProgram.created_at.desc())

        result = await self.session.execute(query)
        programs = list(result.scalars().all())

        # Apply conversion rate filter (post-query)
        if min_conversion_rate is not None:
            programs = [
                p for p in programs if float(p.conversion_rate) >= min_conversion_rate
            ]
            total = len(programs)

        # Apply pagination
        programs = programs[offset : offset + limit]

        return programs, total


