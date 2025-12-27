"""
User Service

Core user creation/update and generic operations.
Enhanced with comprehensive validation, search capabilities, and statistics.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.repositories.user import (
    UserRepository,
    UserAggregateRepository,
    UserSecurityRepository,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserDetail,
    UserListItem,
    UserStats,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.utils.string_utils import StringHelper
from app.utils.password_utils import PasswordHelper

logger = logging.getLogger(__name__)


class UserService:
    """
    Core service for the User entity.

    Responsibilities:
    - Create/update/activate/deactivate users
    - Get user by id, email, or phone
    - List and search users
    - Get user statistics
    - Validate user data
    """

    def __init__(
        self,
        user_repo: UserRepository,
        aggregate_repo: UserAggregateRepository,
        security_repo: UserSecurityRepository,
    ) -> None:
        self.user_repo = user_repo
        self.aggregate_repo = aggregate_repo
        self.security_repo = security_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_user(
        self,
        db: Session,
        data: UserCreate,
    ) -> UserResponse:
        """
        Create a new user.

        Args:
            db: Database session
            data: User creation data

        Returns:
            UserResponse schema

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If user already exists
        """
        # Validate user data
        self._validate_user_create(data)

        try:
            # Check for existing user with same email
            if data.email:
                existing = self.user_repo.get_by_email(db, data.email)
                if existing:
                    raise BusinessLogicException(
                        f"User with email {data.email} already exists"
                    )

            # Check for existing user with same phone
            if data.phone:
                normalized_phone = StringHelper.normalize_phone(data.phone)
                existing = self.user_repo.get_by_phone(db, normalized_phone)
                if existing:
                    raise BusinessLogicException(
                        f"User with phone {normalized_phone} already exists"
                    )

            # Prepare user data
            user_data = data.model_dump(exclude_none=True)
            
            # Normalize email
            if "email" in user_data and user_data["email"]:
                user_data["email"] = user_data["email"].strip().lower()
            
            # Normalize phone
            if "phone" in user_data and user_data["phone"]:
                user_data["phone"] = StringHelper.normalize_phone(user_data["phone"])
            
            # Normalize name
            if "full_name" in user_data:
                user_data["full_name"] = self._normalize_name(user_data["full_name"])

            # Create user with password (repository handles hashing)
            user = self.user_repo.create_user_with_password(db, data=user_data)

            logger.info(
                f"Created user {user.id} with email {user.email} and role {user.role}"
            )

            return UserResponse.model_validate(user)

        except (ValidationException, BusinessLogicException):
            raise
        except IntegrityError as e:
            logger.error(f"Integrity error creating user: {str(e)}")
            db.rollback()
            raise BusinessLogicException(
                "User with this email or phone already exists"
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error creating user: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Failed to create user")

    def update_user(
        self,
        db: Session,
        user_id: UUID,
        data: UserUpdate,
    ) -> UserResponse:
        """
        Update core user fields.

        Args:
            db: Database session
            user_id: User identifier
            data: User update data

        Returns:
            Updated UserResponse schema

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If validation fails
        """
        # Validate update data
        self._validate_user_update(data)

        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            update_dict = data.model_dump(exclude_none=True)

            # Normalize email if provided
            if "email" in update_dict and update_dict["email"]:
                update_dict["email"] = update_dict["email"].strip().lower()
                
                # Check uniqueness
                if update_dict["email"] != user.email:
                    existing = self.user_repo.get_by_email(db, update_dict["email"])
                    if existing and existing.id != user_id:
                        raise ValidationException("Email already in use by another user")

            # Normalize phone if provided
            if "phone" in update_dict and update_dict["phone"]:
                update_dict["phone"] = StringHelper.normalize_phone(update_dict["phone"])
                
                # Check uniqueness
                if update_dict["phone"] != user.phone:
                    existing = self.user_repo.get_by_phone(db, update_dict["phone"])
                    if existing and existing.id != user_id:
                        raise ValidationException(
                            "Phone number already in use by another user"
                        )

            # Normalize name if provided
            if "full_name" in update_dict:
                update_dict["full_name"] = self._normalize_name(update_dict["full_name"])

            updated = self.user_repo.update(db, user, update_dict)

            logger.info(f"Updated user {user_id}")

            return UserResponse.model_validate(updated)

        except (NotFoundException, ValidationException):
            raise
        except IntegrityError as e:
            logger.error(f"Integrity error updating user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Email or phone already in use")
        except SQLAlchemyError as e:
            logger.error(f"Database error updating user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Failed to update user")

    def deactivate_user(
        self,
        db: Session,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        """
        Deactivate a user account.

        Args:
            db: Database session
            user_id: User identifier
            reason: Optional deactivation reason

        Raises:
            NotFoundException: If user doesn't exist
            BusinessLogicException: If user is already inactive
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            if not user.is_active:
                raise BusinessLogicException("User is already deactivated")

            self.user_repo.deactivate_user(db, user, reason)

            logger.info(
                f"Deactivated user {user_id}" + (f" - Reason: {reason}" if reason else "")
            )

        except (NotFoundException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deactivating user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Failed to deactivate user")

    def activate_user(
        self,
        db: Session,
        user_id: UUID,
    ) -> None:
        """
        Reactivate a user account.

        Args:
            db: Database session
            user_id: User identifier

        Raises:
            NotFoundException: If user doesn't exist
            BusinessLogicException: If user is already active
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            if user.is_active:
                raise BusinessLogicException("User is already active")

            self.user_repo.activate_user(db, user)

            logger.info(f"Activated user {user_id}")

        except (NotFoundException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error activating user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Failed to activate user")

    def delete_user(
        self,
        db: Session,
        user_id: UUID,
        soft_delete: bool = True,
    ) -> None:
        """
        Delete a user account (soft or hard delete).

        Args:
            db: Database session
            user_id: User identifier
            soft_delete: If True, marks as deleted; if False, permanently removes

        Raises:
            NotFoundException: If user doesn't exist
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            if soft_delete:
                # Mark as deleted (deactivate)
                self.user_repo.deactivate_user(db, user, reason="Account deleted")
                logger.info(f"Soft deleted user {user_id}")
            else:
                # Hard delete
                self.user_repo.delete(db, user)
                logger.info(f"Hard deleted user {user_id}")

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Failed to delete user")

    # -------------------------------------------------------------------------
    # Retrieval Operations
    # -------------------------------------------------------------------------

    def get_user(
        self,
        db: Session,
        user_id: UUID,
        include_inactive: bool = False,
    ) -> UserDetail:
        """
        Get user by ID with full details.

        Args:
            db: Database session
            user_id: User identifier
            include_inactive: If True, returns inactive users too

        Returns:
            UserDetail schema

        Raises:
            NotFoundException: If user doesn't exist
        """
        try:
            user = self.user_repo.get_full_user(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            if not include_inactive and not user.is_active:
                raise NotFoundException(f"User {user_id} is inactive")

            return UserDetail.model_validate(user)

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error getting user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to retrieve user")

    def get_user_by_email(
        self,
        db: Session,
        email: str,
        include_inactive: bool = False,
    ) -> Optional[UserDetail]:
        """
        Get user by email.

        Args:
            db: Database session
            email: User email
            include_inactive: If True, returns inactive users too

        Returns:
            UserDetail schema or None
        """
        try:
            normalized_email = email.strip().lower()
            user = self.user_repo.get_by_email(db, normalized_email)
            
            if not user:
                return None

            if not include_inactive and not user.is_active:
                return None

            full = self.user_repo.get_full_user(db, user.id)
            return UserDetail.model_validate(full) if full else None

        except SQLAlchemyError as e:
            logger.error(f"Database error getting user by email {email}: {str(e)}")
            raise BusinessLogicException("Failed to retrieve user")

    def get_user_by_phone(
        self,
        db: Session,
        phone: str,
        include_inactive: bool = False,
    ) -> Optional[UserDetail]:
        """
        Get user by phone number.

        Args:
            db: Database session
            phone: User phone number
            include_inactive: If True, returns inactive users too

        Returns:
            UserDetail schema or None
        """
        try:
            normalized_phone = StringHelper.normalize_phone(phone)
            user = self.user_repo.get_by_phone(db, normalized_phone)
            
            if not user:
                return None

            if not include_inactive and not user.is_active:
                return None

            full = self.user_repo.get_full_user(db, user.id)
            return UserDetail.model_validate(full) if full else None

        except SQLAlchemyError as e:
            logger.error(f"Database error getting user by phone {phone}: {str(e)}")
            raise BusinessLogicException("Failed to retrieve user")

    def list_users(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 50,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[UserListItem]:
        """
        List users with optional filtering.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            role: Optional role filter
            is_active: Optional active status filter
            search: Optional search term (name, email, phone)

        Returns:
            List of UserListItem schemas
        """
        try:
            # Validate pagination
            if skip < 0:
                skip = 0
            if limit < 1:
                limit = 50
            if limit > 100:
                limit = 100

            # Get users from repository
            users = self.user_repo.get_list(db, skip=skip, limit=limit)

            # Apply filters
            if role:
                users = [u for u in users if u.role == role]

            if is_active is not None:
                users = [u for u in users if u.is_active == is_active]

            if search:
                search_lower = search.lower()
                users = [
                    u for u in users
                    if (u.full_name and search_lower in u.full_name.lower())
                    or (u.email and search_lower in u.email.lower())
                    or (u.phone and search_lower in u.phone)
                ]

            return [UserListItem.model_validate(u) for u in users]

        except SQLAlchemyError as e:
            logger.error(f"Database error listing users: {str(e)}")
            raise BusinessLogicException("Failed to retrieve users")

    def count_users(
        self,
        db: Session,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> int:
        """
        Count users with optional filtering.

        Args:
            db: Database session
            role: Optional role filter
            is_active: Optional active status filter

        Returns:
            Total count of matching users
        """
        try:
            from app.models.user.user import User
            from sqlalchemy import func

            query = db.query(func.count(User.id))

            if role:
                query = query.filter(User.role == role)

            if is_active is not None:
                query = query.filter(User.is_active == is_active)

            return query.scalar() or 0

        except SQLAlchemyError as e:
            logger.error(f"Database error counting users: {str(e)}")
            raise BusinessLogicException("Failed to count users")

    def get_user_stats(
        self,
        db: Session,
        user_id: UUID,
    ) -> UserStats:
        """
        Get comprehensive statistics for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            UserStats schema

        Raises:
            NotFoundException: If user or stats don't exist
        """
        try:
            stats = self.aggregate_repo.get_user_statistics(db, user_id)
            if not stats:
                raise NotFoundException(f"No statistics available for user {user_id}")

            return UserStats.model_validate(stats)

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error getting stats for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to retrieve user statistics")

    # -------------------------------------------------------------------------
    # Search Operations
    # -------------------------------------------------------------------------

    def search_users(
        self,
        db: Session,
        query: str,
        limit: int = 20,
    ) -> List[UserListItem]:
        """
        Search users by name, email, or phone.

        Args:
            db: Database session
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching UserListItem schemas
        """
        if not query or len(query.strip()) < 2:
            return []

        try:
            search_term = query.strip().lower()

            from app.models.user.user import User
            from sqlalchemy import or_

            users = (
                db.query(User)
                .filter(
                    or_(
                        User.full_name.ilike(f"%{search_term}%"),
                        User.email.ilike(f"%{search_term}%"),
                        User.phone.like(f"%{search_term}%"),
                    )
                )
                .filter(User.is_active == True)
                .limit(limit)
                .all()
            )

            return [UserListItem.model_validate(u) for u in users]

        except SQLAlchemyError as e:
            logger.error(f"Database error searching users with query '{query}': {str(e)}")
            raise BusinessLogicException("Failed to search users")

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_user_create(self, data: UserCreate) -> None:
        """Validate user creation data."""
        # Validate email
        if not data.email:
            raise ValidationException("Email is required")

        if not StringHelper.is_valid_email(data.email):
            raise ValidationException("Invalid email format")

        # Validate phone if provided
        if data.phone:
            normalized_phone = StringHelper.normalize_phone(data.phone)
            if len(normalized_phone) < 10 or len(normalized_phone) > 15:
                raise ValidationException("Phone number must be between 10 and 15 digits")

        # Validate password
        if not data.password or len(data.password) < 8:
            raise ValidationException("Password must be at least 8 characters")

        # Validate full name
        if not data.full_name or len(data.full_name.strip()) < 2:
            raise ValidationException("Full name must be at least 2 characters")

        if len(data.full_name) > 100:
            raise ValidationException("Full name must not exceed 100 characters")

        # Validate role
        valid_roles = ["admin", "staff", "student", "guest"]
        if data.role and data.role not in valid_roles:
            raise ValidationException(f"Invalid role. Must be one of: {valid_roles}")

    def _validate_user_update(self, data: UserUpdate) -> None:
        """Validate user update data."""
        data_dict = data.model_dump(exclude_none=True)

        # Validate email if provided
        if "email" in data_dict and data_dict["email"]:
            if not StringHelper.is_valid_email(data_dict["email"]):
                raise ValidationException("Invalid email format")

        # Validate phone if provided
        if "phone" in data_dict and data_dict["phone"]:
            normalized_phone = StringHelper.normalize_phone(data_dict["phone"])
            if len(normalized_phone) < 10 or len(normalized_phone) > 15:
                raise ValidationException("Phone number must be between 10 and 15 digits")

        # Validate full name if provided
        if "full_name" in data_dict and data_dict["full_name"]:
            if len(data_dict["full_name"].strip()) < 2:
                raise ValidationException("Full name must be at least 2 characters")
            if len(data_dict["full_name"]) > 100:
                raise ValidationException("Full name must not exceed 100 characters")

        # Validate role if provided
        if "role" in data_dict and data_dict["role"]:
            valid_roles = ["admin", "staff", "student", "guest"]
            if data_dict["role"] not in valid_roles:
                raise ValidationException(f"Invalid role. Must be one of: {valid_roles}")

    def _normalize_name(self, name: str) -> str:
        """Normalize a person's name."""
        parts = name.strip().split()
        normalized = " ".join(part.capitalize() for part in parts if part)
        return normalized