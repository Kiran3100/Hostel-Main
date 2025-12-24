"""
User Address Service

Manages user addresses (primary + additional addresses).
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.user import UserAddressRepository
from app.schemas.user import UserAddressUpdate
from app.core.exceptions import ValidationException
from app.models.user.user_address import UserAddress


class UserAddressService:
    """
    High-level service for user addresses.

    Responsibilities:
    - List addresses for a user
    - Create/update/delete addresses
    - Set primary address
    """

    def __init__(
        self,
        address_repo: UserAddressRepository,
    ) -> None:
        self.address_repo = address_repo

    def list_addresses(
        self,
        db: Session,
        user_id: UUID,
    ) -> List[UserAddress]:
        """
        Get all addresses for a user.
        """
        return self.address_repo.get_by_user_id(db, user_id)

    def get_primary_address(
        self,
        db: Session,
        user_id: UUID,
    ) -> Optional[UserAddress]:
        """
        Get the primary address for a user.
        """
        return self.address_repo.get_primary_address(db, user_id)

    def create_address(
        self,
        db: Session,
        user_id: UUID,
        data: UserAddressUpdate,
        is_primary: bool = False,
    ) -> UserAddress:
        """
        Create a new address for a user.
        """
        if is_primary:
            self.address_repo.clear_primary_for_user(db, user_id)

        payload = data.model_dump(exclude_none=True)
        payload["user_id"] = user_id
        payload["is_primary"] = is_primary

        address = self.address_repo.create(db, payload)
        return address

    def update_address(
        self,
        db: Session,
        address_id: UUID,
        data: UserAddressUpdate,
        is_primary: Optional[bool] = None,
    ) -> UserAddress:
        """
        Update an existing address.
        """
        address = self.address_repo.get_by_id(db, address_id)
        if not address:
            raise ValidationException("Address not found")

        payload = data.model_dump(exclude_none=True)

        if is_primary is not None:
            if is_primary:
                self.address_repo.clear_primary_for_user(db, address.user_id)
            payload["is_primary"] = is_primary

        updated = self.address_repo.update(db, address, payload)
        return updated

    def delete_address(
        self,
        db: Session,
        address_id: UUID,
    ) -> None:
        """
        Delete an address.
        """
        address = self.address_repo.get_by_id(db, address_id)
        if not address:
            return
        self.address_repo.delete(db, address)

    def set_primary_address(
        self,
        db: Session,
        address_id: UUID,
    ) -> UserAddress:
        """
        Mark an address as primary.
        """
        address = self.address_repo.get_by_id(db, address_id)
        if not address:
            raise ValidationException("Address not found")

        self.address_repo.clear_primary_for_user(db, address.user_id)
        updated = self.address_repo.update(
            db,
            address,
            {"is_primary": True},
        )
        return updated