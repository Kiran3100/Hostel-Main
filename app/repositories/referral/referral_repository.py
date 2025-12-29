# --- File: app/repositories/referral/referral_repository.py ---
"""
Referral Repository.

Manages referral operations with lifecycle tracking, conversion management,
and analytics integration.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.referral.referral import Referral
from app.models.referral.referral_code import ReferralCode
from app.models.referral.referral_program import ReferralProgram
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import ReferralStatus, RewardStatus
from app.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
    BusinessLogicError,
)

__all__ = ["ReferralRepository"]


class ReferralRepository(BaseRepository[Referral]):
    """
    Referral Repository.
    
    Provides comprehensive referral management with conversion tracking,
    reward processing, and analytics.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        super().__init__(Referral, session)

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    async def create_referral(
        self,
        program_id: UUID,
        referrer_id: UUID,
        referral_code: str,
        referee_email: Optional[str] = None,
        referee_phone: Optional[str] = None,
        referee_name: Optional[str] = None,
        referral_source: Optional[str] = None,
        utm_parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Referral:
        """
        Create a new referral.
        
        Args:
            program_id: Referral program ID
            referrer_id: User ID of referrer
            referral_code: Referral code used
            referee_email: Email of referred person
            referee_phone: Phone of referred person
            referee_name: Name of referred person
            referral_source: Source of referral
            utm_parameters: UTM tracking parameters
            metadata: Additional metadata
            
        Returns:
            Created referral
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate at least one contact method
        if not any([referee_email, referee_phone]):
            raise ValidationError(
                "At least one contact method (email or phone) is required"
            )

        # Get referral code entity
        code_query = select(ReferralCode).where(
            ReferralCode.referral_code == referral_code,
            ReferralCode.is_active == True,
        )
        result = await self.session.execute(code_query)
        code = result.scalar_one_or_none()

        referral = Referral(
            program_id=program_id,
            referrer_id=referrer_id,
            referral_code=referral_code,
            code_id=code.id if code else None,
            referee_email=referee_email,
            referee_phone=referee_phone,
            referee_name=referee_name,
            referral_source=referral_source,
            utm_parameters=utm_parameters,
            metadata=metadata,
            status=ReferralStatus.PENDING,
            first_interaction_date=datetime.utcnow(),
        )

        self.session.add(referral)
        await self.session.flush()
        
        # Increment code usage if code exists
        if code:
            code.increment_usage()
            code.increment_registrations()

        return referral

    async def get_referral_by_id(
        self,
        referral_id: UUID,
        include_relationships: bool = True,
    ) -> Optional[Referral]:
        """
        Get referral by ID with optional relationships.
        
        Args:
            referral_id: Referral ID
            include_relationships: Include related entities
            
        Returns:
            Referral if found, None otherwise
        """
        query = select(Referral).where(Referral.id == referral_id)

        if include_relationships:
            query = query.options(
                joinedload(Referral.program),
                joinedload(Referral.referrer),
                joinedload(Referral.referee),
                joinedload(Referral.code),
                joinedload(Referral.booking),
                selectinload(Referral.rewards),
            )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_referral(
        self,
        referral_id: UUID,
        update_data: Dict[str, Any],
    ) -> Referral:
        """
        Update referral details.
        
        Args:
            referral_id: Referral ID
            update_data: Data to update
            
        Returns:
            Updated referral
            
        Raises:
            EntityNotFoundError: If referral not found
        """
        referral = await self.get_referral_by_id(referral_id)
        if not referral:
            raise EntityNotFoundError(f"Referral {referral_id} not found")

        for key, value in update_data.items():
            if hasattr(referral, key):
                setattr(referral, key, value)

        await self.session.flush()
        return referral

    # ============================================================================
    # REFERRAL LOOKUP OPERATIONS
    # ============================================================================

    async def find_by_referrer(
        self,
        referrer_id: UUID,
        status: Optional[ReferralStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Referral], int]:
        """
        Find referrals by referrer.
        
        Args:
            referrer_id: Referrer user ID
            status: Filter by status
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (referrals, total_count)
        """
        query = select(Referral).where(Referral.referrer_id == referrer_id)

        if status:
            query = query.where(Referral.status == status)

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query
        query = (
            query.order_by(Referral.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(
                joinedload(Referral.referee),
                joinedload(Referral.booking),
            )
        )

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        return list(referrals), total

    async def find_by_referee_email(
        self, referee_email: str
    ) -> Optional[Referral]:
        """
        Find referral by referee email.
        
        Args:
            referee_email: Referee email address
            
        Returns:
            Referral if found, None otherwise
        """
        query = (
            select(Referral)
            .where(Referral.referee_email == referee_email)
            .order_by(Referral.created_at.desc())
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_referee_phone(
        self, referee_phone: str
    ) -> Optional[Referral]:
        """
        Find referral by referee phone.
        
        Args:
            referee_phone: Referee phone number
            
        Returns:
            Referral if found, None otherwise
        """
        query = (
            select(Referral)
            .where(Referral.referee_phone == referee_phone)
            .order_by(Referral.created_at.desc())
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_referee_user(
        self, referee_user_id: UUID
    ) -> List[Referral]:
        """
        Find referrals by referee user ID.
        
        Args:
            referee_user_id: Referee user ID
            
        Returns:
            List of referrals
        """
        query = (
            select(Referral)
            .where(Referral.referee_user_id == referee_user_id)
            .order_by(Referral.created_at.desc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_code(
        self,
        referral_code: str,
        status: Optional[ReferralStatus] = None,
    ) -> List[Referral]:
        """
        Find referrals by referral code.
        
        Args:
            referral_code: Referral code
            status: Filter by status
            
        Returns:
            List of referrals
        """
        query = select(Referral).where(
            Referral.referral_code == referral_code
        )

        if status:
            query = query.where(Referral.status == status)

        query = query.order_by(Referral.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_program(
        self,
        program_id: UUID,
        status: Optional[ReferralStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Referral], int]:
        """
        Find referrals by program.
        
        Args:
            program_id: Program ID
            status: Filter by status
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (referrals, total_count)
        """
        query = select(Referral).where(Referral.program_id == program_id)

        if status:
            query = query.where(Referral.status == status)

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query
        query = (
            query.order_by(Referral.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(
                joinedload(Referral.referrer),
                joinedload(Referral.referee),
            )
        )

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        return list(referrals), total

    # ============================================================================
    # CONVERSION MANAGEMENT
    # ============================================================================

    async def mark_as_converted(
        self,
        referral_id: UUID,
        booking_id: UUID,
        booking_amount: Decimal,
        stay_duration_months: int,
        referrer_reward_amount: Decimal,
        referee_reward_amount: Decimal,
    ) -> Referral:
        """
        Mark referral as converted to booking.
        
        Args:
            referral_id: Referral ID
            booking_id: Associated booking ID
            booking_amount: Booking amount
            stay_duration_months: Stay duration
            referrer_reward_amount: Reward for referrer
            referee_reward_amount: Reward for referee
            
        Returns:
            Updated referral
            
        Raises:
            EntityNotFoundError: If referral not found
            BusinessLogicError: If already converted
        """
        referral = await self.get_referral_by_id(referral_id)
        if not referral:
            raise EntityNotFoundError(f"Referral {referral_id} not found")

        if referral.is_converted:
            raise BusinessLogicError("Referral already converted")

        referral.mark_converted(
            booking_id=booking_id,
            booking_amount=booking_amount,
            stay_duration_months=stay_duration_months,
        )

        referral.referrer_reward_amount = referrer_reward_amount
        referral.referee_reward_amount = referee_reward_amount
        referral.referrer_reward_status = RewardStatus.PENDING
        referral.referee_reward_status = RewardStatus.PENDING

        await self.session.flush()
        return referral

    async def link_referee_user(
        self,
        referral_id: UUID,
        referee_user_id: UUID,
    ) -> Referral:
        """
        Link referee user to referral after registration.
        
        Args:
            referral_id: Referral ID
            referee_user_id: Referee user ID
            
        Returns:
            Updated referral
        """
        referral = await self.get_referral_by_id(referral_id)
        if not referral:
            raise EntityNotFoundError(f"Referral {referral_id} not found")

        referral.referee_user_id = referee_user_id
        referral.referee_registration_date = datetime.utcnow()

        await self.session.flush()
        return referral

    # ============================================================================
    # STATUS MANAGEMENT
    # ============================================================================

    async def update_status(
        self,
        referral_id: UUID,
        new_status: ReferralStatus,
        changed_by: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> Referral:
        """
        Update referral status with history tracking.
        
        Args:
            referral_id: Referral ID
            new_status: New status
            changed_by: User who changed status
            reason: Reason for change
            
        Returns:
            Updated referral
        """
        referral = await self.get_referral_by_id(referral_id)
        if not referral:
            raise EntityNotFoundError(f"Referral {referral_id} not found")

        old_status = referral.status
        referral.status = new_status
        referral.add_status_to_history(
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )

        await self.session.flush()
        return referral

    async def cancel_referral(
        self,
        referral_id: UUID,
        reason: Optional[str] = None,
    ) -> Referral:
        """
        Cancel a referral.
        
        Args:
            referral_id: Referral ID
            reason: Cancellation reason
            
        Returns:
            Cancelled referral
        """
        referral = await self.get_referral_by_id(referral_id)
        if not referral:
            raise EntityNotFoundError(f"Referral {referral_id} not found")

        referral.cancel(reason=reason)
        await self.session.flush()
        return referral

    async def expire_old_referrals(
        self, days_old: int = 90
    ) -> int:
        """
        Expire referrals older than specified days.
        
        Args:
            days_old: Age threshold in days
            
        Returns:
            Number of referrals expired
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        query = select(Referral).where(
            and_(
                Referral.status == ReferralStatus.PENDING,
                Referral.created_at < cutoff_date,
            )
        )

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        count = 0
        for referral in referrals:
            referral.expire()
            count += 1

        await self.session.flush()
        return count

    # ============================================================================
    # REWARD STATUS MANAGEMENT
    # ============================================================================

    async def update_referrer_reward_status(
        self,
        referral_id: UUID,
        reward_status: RewardStatus,
    ) -> Referral:
        """
        Update referrer reward status.
        
        Args:
            referral_id: Referral ID
            reward_status: New reward status
            
        Returns:
            Updated referral
        """
        referral = await self.get_referral_by_id(referral_id)
        if not referral:
            raise EntityNotFoundError(f"Referral {referral_id} not found")

        referral.referrer_reward_status = reward_status
        await self.session.flush()
        return referral

    async def update_referee_reward_status(
        self,
        referral_id: UUID,
        reward_status: RewardStatus,
    ) -> Referral:
        """
        Update referee reward status.
        
        Args:
            referral_id: Referral ID
            reward_status: New reward status
            
        Returns:
            Updated referral
        """
        referral = await self.get_referral_by_id(referral_id)
        if not referral:
            raise EntityNotFoundError(f"Referral {referral_id} not found")

        referral.referee_reward_status = reward_status
        await self.session.flush()
        return referral

    # ============================================================================
    # ANALYTICS & REPORTING
    # ============================================================================

    async def get_referral_statistics(
        self,
        referrer_id: Optional[UUID] = None,
        program_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get referral statistics.
        
        Args:
            referrer_id: Filter by referrer
            program_id: Filter by program
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dictionary of statistics
        """
        query = select(Referral)

        # Apply filters
        conditions = []
        if referrer_id:
            conditions.append(Referral.referrer_id == referrer_id)
        if program_id:
            conditions.append(Referral.program_id == program_id)
        if start_date:
            conditions.append(Referral.created_at >= start_date)
        if end_date:
            conditions.append(Referral.created_at <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        # Calculate statistics
        total_referrals = len(referrals)
        completed = sum(1 for r in referrals if r.status == ReferralStatus.COMPLETED)
        pending = sum(1 for r in referrals if r.status == ReferralStatus.PENDING)
        cancelled = sum(1 for r in referrals if r.status == ReferralStatus.CANCELLED)
        expired = sum(1 for r in referrals if r.status == ReferralStatus.EXPIRED)

        total_booking_amount = sum(
            r.booking_amount or Decimal("0.00") for r in referrals
        )
        total_rewards = sum(r.total_reward_amount for r in referrals)

        conversion_rate = (
            (completed / total_referrals * 100) if total_referrals > 0 else 0
        )

        # Calculate average conversion time
        conversion_times = [
            r.conversion_time_days
            for r in referrals
            if r.conversion_time_days is not None
        ]
        avg_conversion_time = (
            sum(conversion_times) / len(conversion_times)
            if conversion_times
            else None
        )

        return {
            "total_referrals": total_referrals,
            "completed": completed,
            "pending": pending,
            "cancelled": cancelled,
            "expired": expired,
            "conversion_rate": round(conversion_rate, 2),
            "total_booking_amount": float(total_booking_amount),
            "total_rewards": float(total_rewards),
            "average_conversion_time_days": avg_conversion_time,
        }

    async def get_conversion_funnel(
        self,
        program_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get conversion funnel analysis.
        
        Args:
            program_id: Filter by program
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Funnel statistics
        """
        query = select(Referral)

        conditions = []
        if program_id:
            conditions.append(Referral.program_id == program_id)
        if start_date:
            conditions.append(Referral.created_at >= start_date)
        if end_date:
            conditions.append(Referral.created_at <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        total = len(referrals)
        with_registration = sum(
            1 for r in referrals if r.referee_user_id is not None
        )
        with_booking = sum(1 for r in referrals if r.booking_id is not None)
        completed = sum(
            1 for r in referrals if r.status == ReferralStatus.COMPLETED
        )

        return {
            "total_referrals": total,
            "registered": with_registration,
            "booked": with_booking,
            "completed": completed,
            "registration_rate": (
                round(with_registration / total * 100, 2) if total > 0 else 0
            ),
            "booking_rate": (
                round(with_booking / total * 100, 2) if total > 0 else 0
            ),
            "completion_rate": (
                round(completed / total * 100, 2) if total > 0 else 0
            ),
        }

    async def get_top_referrers(
        self,
        program_id: Optional[UUID] = None,
        limit: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get top referrers by conversion count.
        
        Args:
            program_id: Filter by program
            limit: Maximum results
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of top referrers with statistics
        """
        query = (
            select(
                Referral.referrer_id,
                func.count(Referral.id).label("total_referrals"),
                func.sum(
                    func.cast(
                        Referral.status == ReferralStatus.COMPLETED,
                        Decimal,
                    )
                ).label("completed_referrals"),
                func.sum(Referral.booking_amount).label("total_booking_value"),
                func.sum(
                    Referral.referrer_reward_amount + Referral.referee_reward_amount
                ).label("total_rewards"),
            )
            .group_by(Referral.referrer_id)
            .order_by(func.count(Referral.id).desc())
            .limit(limit)
        )

        conditions = []
        if program_id:
            conditions.append(Referral.program_id == program_id)
        if start_date:
            conditions.append(Referral.created_at >= start_date)
        if end_date:
            conditions.append(Referral.created_at <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        rows = result.all()

        top_referrers = []
        for row in rows:
            conversion_rate = (
                (row.completed_referrals / row.total_referrals * 100)
                if row.total_referrals > 0
                else 0
            )

            top_referrers.append({
                "referrer_id": str(row.referrer_id),
                "total_referrals": row.total_referrals,
                "completed_referrals": row.completed_referrals or 0,
                "conversion_rate": round(conversion_rate, 2),
                "total_booking_value": float(row.total_booking_value or 0),
                "total_rewards": float(row.total_rewards or 0),
            })

        return top_referrers

    async def get_referral_sources_breakdown(
        self,
        program_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get breakdown of referrals by source.
        
        Args:
            program_id: Filter by program
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of sources with statistics
        """
        query = (
            select(
                Referral.referral_source,
                func.count(Referral.id).label("count"),
                func.sum(
                    func.cast(
                        Referral.status == ReferralStatus.COMPLETED,
                        Decimal,
                    )
                ).label("conversions"),
            )
            .group_by(Referral.referral_source)
            .order_by(func.count(Referral.id).desc())
        )

        conditions = []
        if program_id:
            conditions.append(Referral.program_id == program_id)
        if start_date:
            conditions.append(Referral.created_at >= start_date)
        if end_date:
            conditions.append(Referral.created_at <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        rows = result.all()

        sources = []
        for row in rows:
            conversion_rate = (
                (row.conversions / row.count * 100) if row.count > 0 else 0
            )

            sources.append({
                "source": row.referral_source or "Unknown",
                "count": row.count,
                "conversions": row.conversions or 0,
                "conversion_rate": round(conversion_rate, 2),
            })

        return sources

    # ============================================================================
    # PENDING ACTIONS
    # ============================================================================

    async def get_pending_rewards(
        self, limit: int = 100
    ) -> List[Referral]:
        """
        Get referrals with pending rewards.
        
        Args:
            limit: Maximum results
            
        Returns:
            List of referrals with pending rewards
        """
        query = (
            select(Referral)
            .where(
                or_(
                    Referral.referrer_reward_status == RewardStatus.PENDING,
                    Referral.referee_reward_status == RewardStatus.PENDING,
                )
            )
            .options(
                joinedload(Referral.referrer),
                joinedload(Referral.referee),
            )
            .order_by(Referral.conversion_date.asc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_pending_conversions(
        self, days_old: int = 7, limit: int = 100
    ) -> List[Referral]:
        """
        Get referrals pending conversion for specified days.
        
        Args:
            days_old: Minimum age in days
            limit: Maximum results
            
        Returns:
            List of pending referrals
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        query = (
            select(Referral)
            .where(
                and_(
                    Referral.status == ReferralStatus.PENDING,
                    Referral.created_at <= cutoff_date,
                )
            )
            .options(
                joinedload(Referral.referrer),
                joinedload(Referral.code),
            )
            .order_by(Referral.created_at.asc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # SEARCH & FILTER
    # ============================================================================

    async def search_referrals(
        self,
        search_term: Optional[str] = None,
        status: Optional[ReferralStatus] = None,
        program_id: Optional[UUID] = None,
        referrer_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_booking_amount: Optional[Decimal] = None,
        max_booking_amount: Optional[Decimal] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Referral], int]:
        """
        Search referrals with multiple filters.
        
        Args:
            search_term: Search in referee name, email, phone
            status: Filter by status
            program_id: Filter by program
            referrer_id: Filter by referrer
            start_date: Start date filter
            end_date: End date filter
            min_booking_amount: Minimum booking amount
            max_booking_amount: Maximum booking amount
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (referrals, total_count)
        """
        query = select(Referral)

        conditions = []

        # Search term
        if search_term:
            search_pattern = f"%{search_term}%"
            conditions.append(
                or_(
                    Referral.referee_name.ilike(search_pattern),
                    Referral.referee_email.ilike(search_pattern),
                    Referral.referee_phone.ilike(search_pattern),
                    Referral.referral_code.ilike(search_pattern),
                )
            )

        # Status filter
        if status:
            conditions.append(Referral.status == status)

        # Program filter
        if program_id:
            conditions.append(Referral.program_id == program_id)

        # Referrer filter
        if referrer_id:
            conditions.append(Referral.referrer_id == referrer_id)

        # Date range
        if start_date:
            conditions.append(Referral.created_at >= start_date)
        if end_date:
            conditions.append(Referral.created_at <= end_date)

        # Booking amount range
        if min_booking_amount:
            conditions.append(Referral.booking_amount >= min_booking_amount)
        if max_booking_amount:
            conditions.append(Referral.booking_amount <= max_booking_amount)

        if conditions:
            query = query.where(and_(*conditions))

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query
        query = (
            query.order_by(Referral.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(
                joinedload(Referral.referrer),
                joinedload(Referral.referee),
                joinedload(Referral.program),
            )
        )

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        return list(referrals), total