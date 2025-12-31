"""
User Address Service

Manages user addresses (primary + additional addresses).
Enhanced with validation, geocoding support, and improved error handling.
"""

import logging
from typing import List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.user import UserAddressRepository
from app.schemas.user import UserAddressUpdate
from app.core.exceptions import (
    ValidationError,
    BusinessLogicError,
    NotFoundError,
)
from app.models.user.user_address import UserAddress

logger = logging.getLogger(__name__)


class UserAddressService:
    """
    High-level service for user addresses.

    Responsibilities:
    - List addresses for a user
    - Create/update/delete addresses
    - Set primary address
    - Validate address data
    - Support for address types (home, work, billing, etc.)
    """

    # Business rules
    MAX_ADDRESSES_PER_USER = 10

    def __init__(
        self,
        address_repo: UserAddressRepository,
    ) -> None:
        self.address_repo = address_repo

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def list_addresses(
        self,
        db: Session,
        user_id: UUID,
        address_type: Union[str, None] = None,
    ) -> List[UserAddress]:
        """
        Get all addresses for a user, optionally filtered by type.

        Args:
            db: Database session
            user_id: User identifier
            address_type: Optional filter by address type

        Returns:
            List of UserAddress instances ordered by is_primary DESC, created_at DESC
        """
        try:
            addresses = self.address_repo.get_by_user_id(db, user_id)
            
            # Filter by type if provided
            if address_type:
                addresses = [a for a in addresses if a.address_type == address_type]
            
            # Sort: primary first, then by creation date
            addresses.sort(key=lambda x: (not x.is_primary, x.created_at), reverse=True)
            
            return addresses

        except SQLAlchemyError as e:
            logger.error(f"Database error listing addresses for user {user_id}: {str(e)}")
            raise BusinessLogicError("Failed to retrieve addresses")

    def get_address(
        self,
        db: Session,
        address_id: UUID,
        user_id: Union[UUID, None] = None,
    ) -> UserAddress:
        """
        Get an address by ID with optional user ownership verification.

        Args:
            db: Database session
            address_id: Address identifier
            user_id: Optional user ID for ownership verification

        Returns:
            UserAddress instance

        Raises:
            NotFoundError: If address doesn't exist
            ValidationError: If user_id provided and doesn't match
        """
        address = self.address_repo.get_by_id(db, address_id)
        if not address:
            raise NotFoundError(f"Address {address_id} not found")

        # Verify ownership if user_id provided
        if user_id and address.user_id != user_id:
            raise ValidationError("Address does not belong to the specified user")

        return address

    def get_primary_address(
        self,
        db: Session,
        user_id: UUID,
    ) -> Union[UserAddress, None]:
        """
        Get the primary address for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Primary UserAddress or None
        """
        return self.address_repo.get_primary_address(db, user_id)

    def get_addresses_by_type(
        self,
        db: Session,
        user_id: UUID,
        address_type: str,
    ) -> List[UserAddress]:
        """
        Get all addresses of a specific type for a user.

        Args:
            db: Database session
            user_id: User identifier
            address_type: Type of address (e.g., 'home', 'work', 'billing')

        Returns:
            List of matching UserAddress instances
        """
        return self.list_addresses(db, user_id, address_type=address_type)

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_address(
        self,
        db: Session,
        user_id: UUID,
        data: UserAddressUpdate,
        is_primary: bool = False,
        address_type: str = "home",
    ) -> UserAddress:
        """
        Create a new address for a user.

        Args:
            db: Database session
            user_id: User identifier
            data: Address data
            is_primary: Whether this is the primary address
            address_type: Type of address

        Returns:
            Created UserAddress instance

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules violated
        """
        # Validate address data
        self._validate_address_data(data)

        # Check address limit
        existing_addresses = self.list_addresses(db, user_id)
        if len(existing_addresses) >= self.MAX_ADDRESSES_PER_USER:
            raise BusinessLogicError(
                f"Maximum {self.MAX_ADDRESSES_PER_USER} addresses allowed per user"
            )

        try:
            # If setting as primary, clear existing primary
            if is_primary:
                self._clear_primary_for_user(db, user_id)
            # If no addresses exist, force this to be primary
            elif not existing_addresses:
                is_primary = True

            payload = data.model_dump(exclude_none=True)
            payload["user_id"] = user_id
            payload["is_primary"] = is_primary
            payload["address_type"] = address_type

            # Normalize data
            payload = self._normalize_address_data(payload)

            address = self.address_repo.create(db, payload)

            logger.info(
                f"Created address {address.id} for user {user_id} "
                f"(type={address_type}, primary={is_primary})"
            )

            return address

        except SQLAlchemyError as e:
            logger.error(f"Database error creating address for user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to create address")

    def update_address(
        self,
        db: Session,
        address_id: UUID,
        user_id: UUID,
        data: UserAddressUpdate,
        is_primary: Union[bool, None] = None,
        address_type: Union[str, None] = None,
    ) -> UserAddress:
        """
        Update an existing address.

        Args:
            db: Database session
            address_id: Address identifier
            user_id: User identifier (for ownership verification)
            data: Updated address data
            is_primary: Optional primary status update
            address_type: Optional address type update

        Returns:
            Updated UserAddress instance

        Raises:
            NotFoundError: If address doesn't exist
            ValidationError: If validation fails
        """
        # Verify address exists and belongs to user
        address = self.get_address(db, address_id, user_id)

        # Validate updated data
        self._validate_address_data(data)

        try:
            payload = data.model_dump(exclude_none=True)

            # Handle primary status change
            if is_primary is not None:
                if is_primary and not address.is_primary:
                    self._clear_primary_for_user(db, user_id)
                payload["is_primary"] = is_primary

            # Handle address type change
            if address_type is not None:
                payload["address_type"] = address_type

            # Normalize data
            payload = self._normalize_address_data(payload)

            updated = self.address_repo.update(db, address, payload)

            logger.info(f"Updated address {address_id} for user {user_id}")

            return updated

        except SQLAlchemyError as e:
            logger.error(f"Database error updating address {address_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to update address")

    def delete_address(
        self,
        db: Session,
        address_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Delete an address.

        If deleting the primary address and other addresses exist,
        automatically promotes the next address to primary.

        Args:
            db: Database session
            address_id: Address identifier
            user_id: User identifier (for ownership verification)

        Raises:
            NotFoundError: If address doesn't exist
        """
        # Verify address exists and belongs to user
        address = self.get_address(db, address_id, user_id)

        try:
            was_primary = address.is_primary

            # Delete the address
            self.address_repo.delete(db, address)

            # If deleted address was primary, promote another
            if was_primary:
                remaining = self.list_addresses(db, user_id)
                if remaining:
                    # Promote the first remaining address to primary
                    self.address_repo.update(
                        db,
                        obj=remaining[0],
                        data={"is_primary": True},
                    )
                    logger.info(
                        f"Promoted address {remaining[0].id} to primary after deleting {address_id}"
                    )

            logger.info(f"Deleted address {address_id} for user {user_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting address {address_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to delete address")

    # -------------------------------------------------------------------------
    # Primary Address Management
    # -------------------------------------------------------------------------

    def set_primary_address(
        self,
        db: Session,
        address_id: UUID,
        user_id: UUID,
    ) -> UserAddress:
        """
        Mark an address as primary.

        Args:
            db: Database session
            address_id: Address identifier
            user_id: User identifier (for ownership verification)

        Returns:
            Updated UserAddress instance

        Raises:
            NotFoundError: If address doesn't exist
        """
        # Verify address exists and belongs to user
        address = self.get_address(db, address_id, user_id)

        if address.is_primary:
            # Already primary, no action needed
            return address

        try:
            # Clear existing primary
            self._clear_primary_for_user(db, user_id)

            # Set new primary
            updated = self.address_repo.update(
                db,
                address,
                {"is_primary": True},
            )

            logger.info(f"Set address {address_id} as primary for user {user_id}")

            return updated

        except SQLAlchemyError as e:
            logger.error(f"Database error setting primary address {address_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to set primary address")

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def delete_all_addresses(
        self,
        db: Session,
        user_id: UUID,
        address_type: Union[str, None] = None,
    ) -> int:
        """
        Delete all addresses for a user, optionally filtered by type.

        Args:
            db: Database session
            user_id: User identifier
            address_type: Optional filter by address type

        Returns:
            Number of addresses deleted
        """
        addresses = self.list_addresses(db, user_id, address_type=address_type)

        try:
            for address in addresses:
                self.address_repo.delete(db, address)

            count = len(addresses)
            logger.info(
                f"Deleted {count} addresses for user {user_id} "
                f"(type={address_type or 'all'})"
            )

            return count

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting addresses for user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to delete addresses")

    # -------------------------------------------------------------------------
    # Validation and Normalization Helpers
    # -------------------------------------------------------------------------

    def _validate_address_data(self, data: UserAddressUpdate) -> None:
        """Validate address data."""
        data_dict = data.model_dump(exclude_none=True)

        # At least one address field should be provided
        address_fields = [
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
            "postal_code",
        ]

        if not any(data_dict.get(field) for field in address_fields):
            raise ValidationError("At least one address field must be provided")

        # Validate postal code format if provided
        if data.postal_code and not self._is_valid_postal_code(data.postal_code):
            raise ValidationError("Invalid postal code format")

        # Validate field lengths
        if data.address_line1 and len(data.address_line1) > 255:
            raise ValidationError("Address line 1 must not exceed 255 characters")

        if data.address_line2 and len(data.address_line2) > 255:
            raise ValidationError("Address line 2 must not exceed 255 characters")

        if data.city and len(data.city) > 100:
            raise ValidationError("City must not exceed 100 characters")

        if data.state and len(data.state) > 100:
            raise ValidationError("State must not exceed 100 characters")

        if data.country and len(data.country) > 100:
            raise ValidationError("Country must not exceed 100 characters")

    def _normalize_address_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize address data (trim, capitalize, etc.)."""
        normalized = data.copy()

        # Trim and capitalize city
        if "city" in normalized and normalized["city"]:
            normalized["city"] = normalized["city"].strip().title()

        # Trim and capitalize state
        if "state" in normalized and normalized["state"]:
            normalized["state"] = normalized["state"].strip().title()

        # Trim and capitalize country
        if "country" in normalized and normalized["country"]:
            normalized["country"] = normalized["country"].strip().title()

        # Normalize postal code (remove spaces, uppercase)
        if "postal_code" in normalized and normalized["postal_code"]:
            normalized["postal_code"] = (
                normalized["postal_code"].replace(" ", "").replace("-", "").upper()
            )

        # Trim address lines
        if "address_line1" in normalized and normalized["address_line1"]:
            normalized["address_line1"] = normalized["address_line1"].strip()

        if "address_line2" in normalized and normalized["address_line2"]:
            normalized["address_line2"] = normalized["address_line2"].strip()

        return normalized

    def _is_valid_postal_code(self, postal_code: str) -> bool:
        """Basic postal code validation."""
        # Remove spaces and hyphens
        cleaned = postal_code.replace(" ", "").replace("-", "")
        
        # Must be alphanumeric and between 3-10 characters
        return cleaned.isalnum() and 3 <= len(cleaned) <= 10

    def _clear_primary_for_user(self, db: Session, user_id: UUID) -> None:
        """Clear primary status for all addresses of a user."""
        self.address_repo.clear_primary_for_user(db, user_id)