# --- File: app/repositories/referral/referral_code_repository.py ---
"""
Referral Code Repository.

Manages referral codes with usage tracking, validation, analytics,
and optimization features.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.referral.referral_code import ReferralCode
from app.models.referral.referral import Referral
from app.models.referral.referral_program import ReferralProgram
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
    BusinessLogicError,
)

__all__ = ["ReferralCodeRepository"]


class ReferralCodeRepository(BaseRepository[ReferralCode]):
    """
    Referral Code Repository.
    
    Provides comprehensive referral code management with usage tracking,
    analytics, and intelligent recommendations.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        super().__init__(ReferralCode, session)

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    async def create_referral_code(
        self,
        user_id: UUID,
        program_id: UUID,
        referral_code: str,
        code_prefix: str = "HOSTEL",
        custom_suffix: Optional[str] = None,
        max_uses: int = 100,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReferralCode:
        """
        Create a new referral code.
        
        Args:
            user_id: Code owner user ID
            program_id: Associated program ID
            referral_code: Unique referral code
            code_prefix: Code prefix
            custom_suffix: Custom suffix
            max_uses: Maximum allowed uses
            expires_at: Expiration timestamp
            metadata: Additional metadata
            
        Returns:
            Created referral code
            
        Raises:
            ValidationError: If code already exists
        """
        # Check if code already exists
        existing = await self.get_by_code(referral_code)
        if existing:
            raise ValidationError(f"Referral code '{referral_code}' already exists")

        # Validate program exists and is active
        program_query = select(ReferralProgram).where(
            ReferralProgram.id == program_id
        )
        program_result = await self.session.execute(program_query)
        program = program_result.scalar_one_or_none()
        
        if not program:
            raise EntityNotFoundError(f"Program {program_id} not found")
        
        if not program.is_active:
            raise BusinessLogicError("Cannot create code for inactive program")

        code = ReferralCode(
            user_id=user_id,
            program_id=program_id,
            referral_code=referral_code,
            code_prefix=code_prefix,
            custom_suffix=custom_suffix,
            max_uses=max_uses,
            expires_at=expires_at,
            is_active=True,
            metadata=metadata,
        )

        self.session.add(code)
        await self.session.flush()
        
        return code

    async def get_code_by_id(
        self,
        code_id: UUID,
        include_relationships: bool = True,
    ) -> Optional[ReferralCode]:
        """
        Get referral code by ID with optional relationships.
        
        Args:
            code_id: Code ID
            include_relationships: Include related entities
            
        Returns:
            ReferralCode if found, None otherwise
        """
        query = select(ReferralCode).where(ReferralCode.id == code_id)

        if include_relationships:
            query = query.options(
                joinedload(ReferralCode.user),
                joinedload(ReferralCode.program),
                selectinload(ReferralCode.referrals),
            )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        referral_code: str,
        include_relationships: bool = False,
    ) -> Optional[ReferralCode]:
        """
        Get referral code by code string.
        
        Args:
            referral_code: Referral code string
            include_relationships: Include related entities
            
        Returns:
            ReferralCode if found, None otherwise
        """
        query = select(ReferralCode).where(
            ReferralCode.referral_code == referral_code
        )

        if include_relationships:
            query = query.options(
                joinedload(ReferralCode.user),
                joinedload(ReferralCode.program),
            )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_code(
        self,
        code_id: UUID,
        update_data: Dict[str, Any],
    ) -> ReferralCode:
        """
        Update referral code details.
        
        Args:
            code_id: Code ID
            update_data: Data to update
            
        Returns:
            Updated referral code
            
        Raises:
            EntityNotFoundError: If code not found
        """
        code = await self.get_code_by_id(code_id)
        if not code:
            raise EntityNotFoundError(f"Referral code {code_id} not found")

        # Prevent updating the code string itself
        if "referral_code" in update_data:
            del update_data["referral_code"]

        for key, value in update_data.items():
            if hasattr(code, key):
                setattr(code, key, value)

        await self.session.flush()
        return code

    # ============================================================================
    # CODE LOOKUP OPERATIONS
    # ============================================================================

    async def find_by_user(
        self,
        user_id: UUID,
        is_active: Optional[bool] = None,
        program_id: Optional[UUID] = None,
    ) -> List[ReferralCode]:
        """
        Find referral codes by user.
        
        Args:
            user_id: User ID
            is_active: Filter by active status
            program_id: Filter by program
            
        Returns:
            List of referral codes
        """
        query = select(ReferralCode).where(ReferralCode.user_id == user_id)

        if is_active is not None:
            query = query.where(ReferralCode.is_active == is_active)

        if program_id:
            query = query.where(ReferralCode.program_id == program_id)

        query = query.order_by(ReferralCode.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_program(
        self,
        program_id: UUID,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[ReferralCode], int]:
        """
        Find referral codes by program.
        
        Args:
            program_id: Program ID
            is_active: Filter by active status
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (codes, total_count)
        """
        query = select(ReferralCode).where(
            ReferralCode.program_id == program_id
        )

        if is_active is not None:
            query = query.where(ReferralCode.is_active == is_active)

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query
        query = (
            query.order_by(ReferralCode.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(joinedload(ReferralCode.user))
        )

        result = await self.session.execute(query)
        codes = result.scalars().all()

        return list(codes), total

    async def find_active_codes(
        self,
        user_id: Optional[UUID] = None,
        program_id: Optional[UUID] = None,
    ) -> List[ReferralCode]:
        """
        Find all active and valid codes.
        
        Args:
            user_id: Filter by user
            program_id: Filter by program
            
        Returns:
            List of active codes
        """
        query = select(ReferralCode).where(
            and_(
                ReferralCode.is_active == True,
                ReferralCode.is_deleted == False,
                or_(
                    ReferralCode.expires_at.is_(None),
                    ReferralCode.expires_at > datetime.utcnow(),
                ),
            )
        )

        if user_id:
            query = query.where(ReferralCode.user_id == user_id)

        if program_id:
            query = query.where(ReferralCode.program_id == program_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_expiring_codes(
        self,
        days_ahead: int = 7,
        limit: int = 100,
    ) -> List[ReferralCode]:
        """
        Find codes expiring within specified days.
        
        Args:
            days_ahead: Days ahead to check
            limit: Maximum results
            
        Returns:
            List of expiring codes
        """
        future_date = datetime.utcnow() + timedelta(days=days_ahead)

        query = (
            select(ReferralCode)
            .where(
                and_(
                    ReferralCode.is_active == True,
                    ReferralCode.expires_at.isnot(None),
                    ReferralCode.expires_at <= future_date,
                    ReferralCode.expires_at > datetime.utcnow(),
                )
            )
            .order_by(ReferralCode.expires_at.asc())
            .limit(limit)
            .options(
                joinedload(ReferralCode.user),
                joinedload(ReferralCode.program),
            )
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_exhausted_codes(
        self, limit: int = 100
    ) -> List[ReferralCode]:
        """
        Find codes that have reached their usage limit.
        
        Args:
            limit: Maximum results
            
        Returns:
            List of exhausted codes
        """
        query = (
            select(ReferralCode)
            .where(
                and_(
                    ReferralCode.is_active == True,
                    ReferralCode.times_used >= ReferralCode.max_uses,
                )
            )
            .order_by(ReferralCode.last_used_at.desc())
            .limit(limit)
            .options(joinedload(ReferralCode.user))
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # VALIDATION OPERATIONS
    # ============================================================================

    async def validate_code(
        self, referral_code: str
    ) -> tuple[bool, Optional[str], Optional[ReferralCode]]:
        """
        Validate if a referral code can be used.
        
        Args:
            referral_code: Code to validate
            
        Returns:
            Tuple of (is_valid, error_message, code_object)
        """
        code = await self.get_by_code(referral_code, include_relationships=True)

        if not code:
            return False, "Referral code not found", None

        if not code.is_active:
            return False, "Referral code is inactive", code

        if code.is_deleted:
            return False, "Referral code has been deleted", code

        if code.is_expired:
            return False, "Referral code has expired", code

        if code.is_exhausted:
            return False, "Referral code has reached maximum uses", code

        # Check if program is active
        if not code.program.is_currently_valid:
            return False, "Referral program is not active", code

        return True, None, code

    async def check_code_availability(
        self, referral_code: str
    ) -> bool:
        """
        Check if a referral code is available for creation.
        
        Args:
            referral_code: Code to check
            
        Returns:
            True if available, False otherwise
        """
        existing = await self.get_by_code(referral_code)
        return existing is None

    # ============================================================================
    # USAGE TRACKING
    # ============================================================================

    async def increment_usage(
        self, code_id: UUID
    ) -> tuple[bool, Optional[str]]:
        """
        Increment code usage count.
        
        Args:
            code_id: Code ID
            
        Returns:
            Tuple of (success, error_message)
        """
        code = await self.get_code_by_id(code_id, include_relationships=False)
        if not code:
            return False, "Code not found"

        if not code.increment_usage():
            return False, "Code has reached maximum uses"

        await self.session.flush()
        return True, None

    async def increment_shares(self, code_id: UUID) -> None:
        """
        Increment share count for a code.
        
        Args:
            code_id: Code ID
        """
        code = await self.get_code_by_id(code_id, include_relationships=False)
        if code:
            code.increment_shares()
            await self.session.flush()

    async def increment_clicks(self, code_id: UUID) -> None:
        """
        Increment click count for a code.
        
        Args:
            code_id: Code ID
        """
        code = await self.get_code_by_id(code_id, include_relationships=False)
        if code:
            code.increment_clicks()
            await self.session.flush()

    async def increment_registrations(self, code_id: UUID) -> None:
        """
        Increment registration count for a code.
        
        Args:
            code_id: Code ID
        """
        code = await self.get_code_by_id(code_id, include_relationships=False)
        if code:
            code.increment_registrations()
            await self.session.flush()

    async def increment_bookings(self, code_id: UUID) -> None:
        """
        Increment booking count for a code.
        
        Args:
            code_id: Code ID
        """
        code = await self.get_code_by_id(code_id, include_relationships=False)
        if code:
            code.increment_bookings()
            await self.session.flush()

    async def track_channel_usage(
        self,
        code_id: UUID,
        channel: str,
    ) -> None:
        """
        Track which channel a code was shared on.
        
        Args:
            code_id: Code ID
            channel: Channel name (e.g., 'whatsapp', 'email')
        """
        code = await self.get_code_by_id(code_id, include_relationships=False)
        if not code:
            return

        if code.source_channels is None:
            code.source_channels = {}

        # Increment channel count
        current_count = code.source_channels.get(channel, 0)
        code.source_channels[channel] = current_count + 1

        await self.session.flush()

    # ============================================================================
    # CODE MANAGEMENT
    # ============================================================================

    async def activate_code(self, code_id: UUID) -> ReferralCode:
        """
        Activate a referral code.
        
        Args:
            code_id: Code ID
            
        Returns:
            Updated code
        """
        code = await self.get_code_by_id(code_id)
        if not code:
            raise EntityNotFoundError(f"Code {code_id} not found")

        code.is_active = True
        await self.session.flush()
        return code

    async def deactivate_code(self, code_id: UUID) -> ReferralCode:
        """
        Deactivate a referral code.
        
        Args:
            code_id: Code ID
            
        Returns:
            Updated code
        """
        code = await self.get_code_by_id(code_id)
        if not code:
            raise EntityNotFoundError(f"Code {code_id} not found")

        code.deactivate()
        await self.session.flush()
        return code

    async def extend_expiry(
        self,
        code_id: UUID,
        additional_days: int,
    ) -> ReferralCode:
        """
        Extend code expiry date.
        
        Args:
            code_id: Code ID
            additional_days: Days to add
            
        Returns:
            Updated code
        """
        code = await self.get_code_by_id(code_id)
        if not code:
            raise EntityNotFoundError(f"Code {code_id} not found")

        if code.expires_at:
            code.expires_at = code.expires_at + timedelta(days=additional_days)
        else:
            code.expires_at = datetime.utcnow() + timedelta(days=additional_days)

        await self.session.flush()
        return code

    async def increase_max_uses(
        self,
        code_id: UUID,
        additional_uses: int,
    ) -> ReferralCode:
        """
        Increase maximum uses for a code.
        
        Args:
            code_id: Code ID
            additional_uses: Additional uses to allow
            
        Returns:
            Updated code
        """
        code = await self.get_code_by_id(code_id)
        if not code:
            raise EntityNotFoundError(f"Code {code_id} not found")

        code.max_uses += additional_uses
        await self.session.flush()
        return code

    async def expire_old_codes(self) -> int:
        """
        Expire codes that have passed their expiry date.
        
        Returns:
            Number of codes expired
        """
        query = select(ReferralCode).where(
            and_(
                ReferralCode.is_active == True,
                ReferralCode.expires_at.isnot(None),
                ReferralCode.expires_at <= datetime.utcnow(),
            )
        )

        result = await self.session.execute(query)
        codes = result.scalars().all()

        count = 0
        for code in codes:
            code.deactivate()
            count += 1

        await self.session.flush()
        return count

    # ============================================================================
    # ANALYTICS & REPORTING
    # ============================================================================

    async def get_code_statistics(
        self,
        code_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a code.
        
        Args:
            code_id: Code ID
            
        Returns:
            Dictionary of statistics
        """
        code = await self.get_code_by_id(code_id, include_relationships=True)
        if not code:
            raise EntityNotFoundError(f"Code {code_id} not found")

        return {
            "code": code.referral_code,
            "is_valid": code.is_valid,
            "is_active": code.is_active,
            "is_expired": code.is_expired,
            "is_exhausted": code.is_exhausted,
            "times_used": code.times_used,
            "max_uses": code.max_uses,
            "remaining_uses": code.remaining_uses,
            "times_shared": code.times_shared,
            "times_clicked": code.times_clicked,
            "total_registrations": code.total_registrations,
            "total_bookings": code.total_bookings,
            "conversion_rate": code.conversion_rate,
            "registration_rate": code.registration_rate,
            "source_channels": code.source_channels or {},
            "created_at": code.created_at.isoformat(),
            "expires_at": code.expires_at.isoformat() if code.expires_at else None,
            "last_used_at": code.last_used_at.isoformat() if code.last_used_at else None,
        }

    async def get_user_code_performance(
        self, user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get performance summary for all user codes.
        
        Args:
            user_id: User ID
            
        Returns:
            Performance summary
        """
        codes = await self.find_by_user(user_id)

        total_codes = len(codes)
        active_codes = sum(1 for c in codes if c.is_active)
        total_clicks = sum(c.times_clicked for c in codes)
        total_registrations = sum(c.total_registrations for c in codes)
        total_bookings = sum(c.total_bookings for c in codes)
        total_shares = sum(c.times_shared for c in codes)

        avg_conversion_rate = (
            sum(c.conversion_rate for c in codes) / total_codes
            if total_codes > 0
            else 0
        )

        best_code = max(codes, key=lambda c: c.total_bookings) if codes else None

        return {
            "total_codes": total_codes,
            "active_codes": active_codes,
            "total_clicks": total_clicks,
            "total_registrations": total_registrations,
            "total_bookings": total_bookings,
            "total_shares": total_shares,
            "average_conversion_rate": round(avg_conversion_rate, 2),
            "best_performing_code": (
                {
                    "code": best_code.referral_code,
                    "bookings": best_code.total_bookings,
                    "conversion_rate": best_code.conversion_rate,
                }
                if best_code
                else None
            ),
        }

    async def get_top_performing_codes(
        self,
        program_id: Optional[UUID] = None,
        limit: int = 10,
        sort_by: str = "total_bookings",
    ) -> List[Dict[str, Any]]:
        """
        Get top performing codes.
        
        Args:
            program_id: Filter by program
            limit: Maximum results
            sort_by: Sort criterion (total_bookings, conversion_rate, clicks)
            
        Returns:
            List of top codes with statistics
        """
        query = select(ReferralCode).where(ReferralCode.is_active == True)

        if program_id:
            query = query.where(ReferralCode.program_id == program_id)

        result = await self.session.execute(query)
        codes = result.scalars().all()

        # Sort codes
        if sort_by == "total_bookings":
            codes = sorted(codes, key=lambda c: c.total_bookings, reverse=True)
        elif sort_by == "conversion_rate":
            codes = sorted(codes, key=lambda c: c.conversion_rate, reverse=True)
        elif sort_by == "clicks":
            codes = sorted(codes, key=lambda c: c.times_clicked, reverse=True)
        else:
            codes = sorted(codes, key=lambda c: c.total_bookings, reverse=True)

        top_codes = codes[:limit]

        return [
            {
                "code_id": str(code.id),
                "code": code.referral_code,
                "user_id": str(code.user_id),
                "total_bookings": code.total_bookings,
                "total_registrations": code.total_registrations,
                "times_clicked": code.times_clicked,
                "conversion_rate": code.conversion_rate,
                "registration_rate": code.registration_rate,
            }
            for code in top_codes
        ]

    async def get_channel_breakdown(
        self,
        program_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get breakdown of code usage by channel.
        
        Args:
            program_id: Filter by program
            
        Returns:
            Channel statistics
        """
        query = select(ReferralCode)

        if program_id:
            query = query.where(ReferralCode.program_id == program_id)

        result = await self.session.execute(query)
        codes = result.scalars().all()

        # Aggregate channel data
        channel_stats = {}
        for code in codes:
            if code.source_channels:
                for channel, count in code.source_channels.items():
                    if channel not in channel_stats:
                        channel_stats[channel] = {
                            "channel": channel,
                            "total_shares": 0,
                            "codes_using": 0,
                        }
                    channel_stats[channel]["total_shares"] += count
                    channel_stats[channel]["codes_using"] += 1

        return sorted(
            channel_stats.values(),
            key=lambda x: x["total_shares"],
            reverse=True,
        )

    # ============================================================================
    # RECOMMENDATIONS
    # ============================================================================

    async def get_recommended_codes_for_user(
        self,
        user_id: UUID,
        limit: int = 3,
    ) -> List[ReferralCode]:
        """
        Get recommended codes for a user based on performance.
        
        Args:
            user_id: User ID
            limit: Maximum recommendations
            
        Returns:
            List of recommended codes
        """
        codes = await self.find_by_user(user_id, is_active=True)

        # Filter valid codes
        valid_codes = [c for c in codes if c.is_valid]

        # Sort by performance (combination of bookings and conversion rate)
        valid_codes.sort(
            key=lambda c: (c.total_bookings * 0.7 + c.conversion_rate * 0.3),
            reverse=True,
        )

        return valid_codes[:limit]

    async def suggest_code_optimization(
        self, code_id: UUID
    ) -> List[str]:
        """
        Suggest optimizations for a code.
        
        Args:
            code_id: Code ID
            
        Returns:
            List of optimization suggestions
        """
        code = await self.get_code_by_id(code_id, include_relationships=True)
        if not code:
            return []

        suggestions = []

        # Check if code is expiring soon
        if code.expires_at:
            days_until_expiry = (code.expires_at - datetime.utcnow()).days
            if days_until_expiry < 7 and code.is_active:
                suggestions.append(
                    f"Code expires in {days_until_expiry} days. Consider extending."
                )

        # Check if approaching max uses
        if code.remaining_uses < 10 and code.remaining_uses > 0:
            suggestions.append(
                f"Only {code.remaining_uses} uses remaining. Consider increasing limit."
            )

        # Check conversion rate
        if code.times_clicked > 20 and code.conversion_rate < 5:
            suggestions.append(
                "Low conversion rate. Review targeting or offer details."
            )

        # Check if not being used
        if code.times_clicked == 0 and code.times_shared > 5:
            suggestions.append(
                "Code shared but not clicked. Review share messaging."
            )

        # Check channel performance
        if code.source_channels:
            total_shares = sum(code.source_channels.values())
            if total_shares > 0:
                # Find underperforming channels
                for channel, shares in code.source_channels.items():
                    if shares / total_shares < 0.1:
                        suggestions.append(
                            f"Low engagement on {channel}. Consider alternative channels."
                        )

        return suggestions

    # ============================================================================
    # SEARCH & FILTER
    # ============================================================================

    async def search_codes(
        self,
        search_term: Optional[str] = None,
        user_id: Optional[UUID] = None,
        program_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        min_bookings: Optional[int] = None,
        min_conversion_rate: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ReferralCode], int]:
        """
        Search referral codes with filters.
        
        Args:
            search_term: Search in code string
            user_id: Filter by user
            program_id: Filter by program
            is_active: Filter by active status
            min_bookings: Minimum booking count
            min_conversion_rate: Minimum conversion rate
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (codes, total_count)
        """
        query = select(ReferralCode)

        conditions = []

        # Search term
        if search_term:
            search_pattern = f"%{search_term}%"
            conditions.append(ReferralCode.referral_code.ilike(search_pattern))

        # User filter
        if user_id:
            conditions.append(ReferralCode.user_id == user_id)

        # Program filter
        if program_id:
            conditions.append(ReferralCode.program_id == program_id)

        # Active status
        if is_active is not None:
            conditions.append(ReferralCode.is_active == is_active)

        # Minimum bookings
        if min_bookings is not None:
            conditions.append(ReferralCode.total_bookings >= min_bookings)

        if conditions:
            query = query.where(and_(*conditions))

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query with post-filtering for conversion rate
        query = query.order_by(ReferralCode.created_at.desc()).options(
            joinedload(ReferralCode.user),
            joinedload(ReferralCode.program),
        )

        result = await self.session.execute(query)
        codes = list(result.scalars().all())

        # Apply conversion rate filter (can't do in SQL easily)
        if min_conversion_rate is not None:
            codes = [c for c in codes if c.conversion_rate >= min_conversion_rate]
            total = len(codes)

        # Apply pagination after filtering
        codes = codes[offset : offset + limit]

        return codes, total


