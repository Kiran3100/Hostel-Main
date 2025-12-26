"""
Visitor Service

Core visitor CRUD operations and profile management.
Provides foundational visitor entity operations.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.visitor import (
    VisitorRepository,
    VisitorAggregateRepository,
)
from app.schemas.visitor import (
    VisitorCreate,
    VisitorUpdate,
    VisitorResponse,
    VisitorDetail,
    VisitorStats,
)
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    ServiceException,
    DuplicateException,
)
from app.core.caching import cache_result, invalidate_cache

logger = logging.getLogger(__name__)


class VisitorService:
    """
    Core service for visitor entity management.

    Responsibilities:
    - CRUD operations for visitors
    - Profile management and updates
    - Visitor statistics and analytics
    - Profile completeness tracking
    - Visitor lifecycle management

    This service handles the core visitor entity and delegates
    specialized operations to other services (favorites, preferences, etc.)
    """

    # Cache TTL for visitor profiles
    CACHE_TTL = 600  # 10 minutes

    def __init__(
        self,
        visitor_repo: VisitorRepository,
        aggregate_repo: VisitorAggregateRepository,
    ) -> None:
        """
        Initialize the visitor service.

        Args:
            visitor_repo: Repository for visitor operations
            aggregate_repo: Repository for aggregated visitor data
        """
        self.visitor_repo = visitor_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_visitor(
        self,
        db: Session,
        data: VisitorCreate,
    ) -> VisitorResponse:
        """
        Create a new visitor profile.

        Args:
            db: Database session
            data: Visitor creation data

        Returns:
            VisitorResponse: Created visitor profile

        Raises:
            ValidationException: If data is invalid
            DuplicateException: If visitor already exists (by user_id or email)
            ServiceException: If creation fails
        """
        try:
            # Validate required fields
            self._validate_visitor_create(data)

            # Check for duplicates
            if data.user_id:
                existing = self.visitor_repo.get_by_user_id(db, data.user_id)
                if existing:
                    raise DuplicateException(
                        f"Visitor already exists for user {data.user_id}"
                    )

            if data.email:
                existing = self.visitor_repo.get_by_email(db, data.email)
                if existing:
                    raise DuplicateException(
                        f"Visitor already exists with email {data.email}"
                    )

            # Prepare creation data
            create_data = data.model_dump(exclude_none=True)
            create_data["created_at"] = datetime.utcnow()
            create_data["updated_at"] = datetime.utcnow()

            # Set initial profile completeness
            create_data["profile_completeness"] = self._calculate_profile_completeness(
                create_data
            )

            # Create visitor
            visitor = self.visitor_repo.create(db, data=create_data)

            logger.info(
                f"Created visitor {visitor.id} "
                f"{f'for user {visitor.user_id}' if visitor.user_id else '(anonymous)'}"
            )

            return VisitorResponse.model_validate(visitor)

        except (ValidationException, DuplicateException):
            raise
        except IntegrityError as e:
            logger.error(f"Integrity error creating visitor: {str(e)}")
            raise DuplicateException("Visitor with this data already exists")
        except Exception as e:
            logger.error(f"Failed to create visitor: {str(e)}", exc_info=True)
            raise ServiceException(f"Failed to create visitor: {str(e)}")

    @invalidate_cache(key_prefix="visitor_profile")
    def update_visitor(
        self,
        db: Session,
        visitor_id: UUID,
        data: VisitorUpdate,
    ) -> VisitorResponse:
        """
        Update visitor profile.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            data: Update data

        Returns:
            VisitorResponse: Updated visitor profile

        Raises:
            NotFoundException: If visitor not found
            ValidationException: If update data is invalid
            ServiceException: If update fails
        """
        try:
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            # Validate update data
            self._validate_visitor_update(data)

            # Prepare update data
            update_data = data.model_dump(exclude_none=True)
            update_data["updated_at"] = datetime.utcnow()

            # Recalculate profile completeness if relevant fields updated
            if self._should_recalculate_completeness(update_data):
                merged_data = {**visitor.__dict__, **update_data}
                update_data["profile_completeness"] = self._calculate_profile_completeness(
                    merged_data
                )

            # Update visitor
            updated = self.visitor_repo.update(db, obj=visitor, data=update_data)

            logger.info(f"Updated visitor {visitor_id}")

            return VisitorResponse.model_validate(updated)

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to update visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to update visitor: {str(e)}")

    def delete_visitor(
        self,
        db: Session,
        visitor_id: UUID,
        soft_delete: bool = True,
    ) -> None:
        """
        Delete a visitor profile.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            soft_delete: If True, soft delete; otherwise hard delete

        Raises:
            NotFoundException: If visitor not found
            ServiceException: If deletion fails
        """
        try:
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                logger.warning(f"Attempt to delete non-existent visitor {visitor_id}")
                return

            if soft_delete:
                # Soft delete: mark as deleted
                self.visitor_repo.update(
                    db,
                    obj=visitor,
                    data={
                        "deleted_at": datetime.utcnow(),
                        "is_active": False,
                    }
                )
                logger.info(f"Soft deleted visitor {visitor_id}")
            else:
                # Hard delete
                self.visitor_repo.delete(db, visitor)
                logger.info(f"Hard deleted visitor {visitor_id}")

        except Exception as e:
            logger.error(
                f"Failed to delete visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to delete visitor: {str(e)}")

    # -------------------------------------------------------------------------
    # Retrieval Operations
    # -------------------------------------------------------------------------

    @cache_result(ttl=CACHE_TTL, key_prefix="visitor_profile")
    def get_visitor(
        self,
        db: Session,
        visitor_id: UUID,
        include_deleted: bool = False,
    ) -> VisitorDetail:
        """
        Get detailed visitor profile by ID.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            include_deleted: If True, include soft-deleted visitors

        Returns:
            VisitorDetail: Full visitor profile with relationships

        Raises:
            NotFoundException: If visitor not found
            ServiceException: If retrieval fails
        """
        try:
            visitor = self.visitor_repo.get_full_profile(
                db,
                visitor_id,
                include_deleted=include_deleted
            )

            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            return VisitorDetail.model_validate(visitor)

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve visitor: {str(e)}")

    def get_visitor_by_user_id(
        self,
        db: Session,
        user_id: UUID,
    ) -> Optional[VisitorDetail]:
        """
        Get visitor profile by associated user ID.

        Args:
            db: Database session
            user_id: UUID of the user

        Returns:
            VisitorDetail or None if not found

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            visitor = self.visitor_repo.get_by_user_id(db, user_id)
            if not visitor:
                return None

            full_profile = self.visitor_repo.get_full_profile(db, visitor.id)
            return VisitorDetail.model_validate(full_profile)

        except Exception as e:
            logger.error(
                f"Failed to get visitor by user {user_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve visitor by user: {str(e)}")

    def get_visitor_by_email(
        self,
        db: Session,
        email: str,
    ) -> Optional[VisitorDetail]:
        """
        Get visitor profile by email.

        Args:
            db: Database session
            email: Email address

        Returns:
            VisitorDetail or None if not found

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            visitor = self.visitor_repo.get_by_email(db, email)
            if not visitor:
                return None

            full_profile = self.visitor_repo.get_full_profile(db, visitor.id)
            return VisitorDetail.model_validate(full_profile)

        except Exception as e:
            logger.error(
                f"Failed to get visitor by email {email}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve visitor by email: {str(e)}")

    def list_visitors(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VisitorResponse]:
        """
        List visitors with pagination and filtering.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filter criteria

        Returns:
            List[VisitorResponse]: List of visitors

        Raises:
            ValidationException: If pagination parameters invalid
            ServiceException: If retrieval fails
        """
        try:
            if skip < 0 or limit < 1 or limit > 1000:
                raise ValidationException(
                    "Invalid pagination: skip must be >= 0, limit between 1 and 1000"
                )

            visitors = self.visitor_repo.get_multi(
                db,
                skip=skip,
                limit=limit,
                filters=filters or {}
            )

            return [VisitorResponse.model_validate(v) for v in visitors]

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to list visitors: {str(e)}", exc_info=True)
            raise ServiceException(f"Failed to list visitors: {str(e)}")

    # -------------------------------------------------------------------------
    # Statistics and Analytics
    # -------------------------------------------------------------------------

    @cache_result(ttl=300, key_prefix="visitor_stats")
    def get_visitor_stats(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> VisitorStats:
        """
        Get comprehensive statistics for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            VisitorStats: Visitor statistics and metrics

        Raises:
            NotFoundException: If visitor not found
            ServiceException: If retrieval fails
        """
        try:
            stats_dict = self.aggregate_repo.get_visitor_stats(db, visitor_id)
            if not stats_dict:
                raise NotFoundException(
                    f"Visitor {visitor_id} not found or no stats available"
                )

            return VisitorStats.model_validate(stats_dict)

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get stats for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve visitor stats: {str(e)}")

    def get_engagement_summary(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get engagement summary for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            Dictionary with engagement metrics

        Raises:
            NotFoundException: If visitor not found
        """
        try:
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            engagement_data = self.aggregate_repo.get_engagement_summary(db, visitor_id)

            return {
                "visitor_id": str(visitor_id),
                "engagement_score": engagement_data.get("engagement_score", 0),
                "total_searches": engagement_data.get("total_searches", 0),
                "total_views": engagement_data.get("total_views", 0),
                "total_favorites": engagement_data.get("total_favorites", 0),
                "total_bookings": visitor.total_bookings or 0,
                "total_inquiries": visitor.total_inquiries or 0,
                "last_activity": engagement_data.get("last_activity"),
                "is_active_user": self._is_active_user(engagement_data),
                "user_segment": self._determine_user_segment(engagement_data),
            }

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get engagement summary for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to get engagement summary: {str(e)}")

    # -------------------------------------------------------------------------
    # Profile Management
    # -------------------------------------------------------------------------

    def update_profile_completeness(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> int:
        """
        Recalculate and update profile completeness score.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            int: Profile completeness score (0-100)

        Raises:
            NotFoundException: If visitor not found
        """
        try:
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            completeness = self._calculate_profile_completeness(visitor.__dict__)

            self.visitor_repo.update(
                db,
                obj=visitor,
                data={"profile_completeness": completeness}
            )

            logger.info(
                f"Updated profile completeness for visitor {visitor_id}: {completeness}%"
            )

            return completeness

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update profile completeness for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(
                f"Failed to update profile completeness: {str(e)}"
            )

    def get_profile_completion_suggestions(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get suggestions for completing visitor profile.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            List of suggestions with priorities

        Raises:
            NotFoundException: If visitor not found
        """
        try:
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            suggestions = []

            # Check missing fields
            if not visitor.first_name:
                suggestions.append({
                    "field": "first_name",
                    "message": "Add your first name",
                    "priority": "high",
                    "points": 10,
                })

            if not visitor.last_name:
                suggestions.append({
                    "field": "last_name",
                    "message": "Add your last name",
                    "priority": "high",
                    "points": 10,
                })

            if not visitor.phone:
                suggestions.append({
                    "field": "phone",
                    "message": "Add your phone number for booking confirmations",
                    "priority": "medium",
                    "points": 15,
                })

            if not visitor.date_of_birth:
                suggestions.append({
                    "field": "date_of_birth",
                    "message": "Add your date of birth",
                    "priority": "low",
                    "points": 5,
                })

            if not getattr(visitor, 'address', None):
                suggestions.append({
                    "field": "address",
                    "message": "Add your address",
                    "priority": "low",
                    "points": 10,
                })

            # Check for preferences
            if not hasattr(visitor, 'preferences') or not visitor.preferences:
                suggestions.append({
                    "field": "preferences",
                    "message": "Set your preferences for better recommendations",
                    "priority": "medium",
                    "points": 20,
                })

            return suggestions

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get profile suggestions for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(
                f"Failed to get profile completion suggestions: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_visitor_create(self, data: VisitorCreate) -> None:
        """
        Validate visitor creation data.

        Args:
            data: Visitor creation data

        Raises:
            ValidationException: If validation fails
        """
        # Email validation
        if data.email:
            if not self._is_valid_email(data.email):
                raise ValidationException("Invalid email format")

        # Phone validation
        if data.phone:
            if not self._is_valid_phone(data.phone):
                raise ValidationException("Invalid phone format")

        # Date of birth validation
        if data.date_of_birth:
            if data.date_of_birth > datetime.now().date():
                raise ValidationException("Date of birth cannot be in the future")

            age = (datetime.now().date() - data.date_of_birth).days / 365.25
            if age < 13:
                raise ValidationException("Visitor must be at least 13 years old")

    def _validate_visitor_update(self, data: VisitorUpdate) -> None:
        """
        Validate visitor update data.

        Args:
            data: Visitor update data

        Raises:
            ValidationException: If validation fails
        """
        # Email validation
        if data.email is not None:
            if not self._is_valid_email(data.email):
                raise ValidationException("Invalid email format")

        # Phone validation
        if data.phone is not None:
            if not self._is_valid_phone(data.phone):
                raise ValidationException("Invalid phone format")

        # Date of birth validation
        if data.date_of_birth is not None:
            if data.date_of_birth > datetime.now().date():
                raise ValidationException("Date of birth cannot be in the future")

    def _is_valid_email(self, email: str) -> bool:
        """
        Validate email format.

        Args:
            email: Email address

        Returns:
            bool: True if valid
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _is_valid_phone(self, phone: str) -> bool:
        """
        Validate phone format.

        Args:
            phone: Phone number

        Returns:
            bool: True if valid
        """
        import re
        # Basic phone validation (can be enhanced)
        pattern = r'^\+?[1-9]\d{1,14}$'
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        return re.match(pattern, cleaned) is not None

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _calculate_profile_completeness(self, data: Dict[str, Any]) -> int:
        """
        Calculate profile completeness percentage.

        Args:
            data: Visitor data dictionary

        Returns:
            int: Completeness score (0-100)
        """
        total_fields = 0
        completed_fields = 0

        # Core fields (required)
        core_fields = ['first_name', 'last_name', 'email']
        for field in core_fields:
            total_fields += 2  # Weight core fields more
            if data.get(field):
                completed_fields += 2

        # Optional but important fields
        optional_fields = ['phone', 'date_of_birth', 'gender', 'address', 'city', 'country']
        for field in optional_fields:
            total_fields += 1
            if data.get(field):
                completed_fields += 1

        # Preferences
        total_fields += 2
        if data.get('preferences'):
            completed_fields += 2

        # Profile picture
        total_fields += 1
        if data.get('profile_picture'):
            completed_fields += 1

        if total_fields == 0:
            return 0

        return int((completed_fields / total_fields) * 100)

    def _should_recalculate_completeness(self, update_data: Dict[str, Any]) -> bool:
        """
        Determine if profile completeness should be recalculated.

        Args:
            update_data: Update data dictionary

        Returns:
            bool: True if recalculation needed
        """
        profile_fields = {
            'first_name', 'last_name', 'email', 'phone',
            'date_of_birth', 'gender', 'address', 'city',
            'country', 'profile_picture', 'preferences'
        }

        return bool(set(update_data.keys()) & profile_fields)

    def _is_active_user(self, engagement_data: Dict[str, Any]) -> bool:
        """
        Determine if visitor is an active user.

        Args:
            engagement_data: Engagement data dictionary

        Returns:
            bool: True if active
        """
        last_activity = engagement_data.get("last_activity")
        if not last_activity:
            return False

        days_since_activity = (datetime.utcnow() - last_activity).days
        return days_since_activity <= 30

    def _determine_user_segment(self, engagement_data: Dict[str, Any]) -> str:
        """
        Determine user segment based on engagement.

        Args:
            engagement_data: Engagement data dictionary

        Returns:
            str: User segment identifier
        """
        score = engagement_data.get("engagement_score", 0)
        total_bookings = engagement_data.get("total_bookings", 0)

        if total_bookings > 5:
            return "loyal"
        elif total_bookings > 0:
            return "converted"
        elif score > 50:
            return "engaged"
        elif score > 20:
            return "active"
        else:
            return "new"