"""
Maintenance Vendor Service

Manages maintenance vendors, their contracts, and performance.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceVendorRepository
from app.schemas.maintenance import (
    MaintenanceVendor,
    VendorContract,
    VendorPerformanceReview,
)
from app.core.exceptions import ValidationException


class MaintenanceVendorService:
    """
    High-level service for maintenance vendors.
    """

    def __init__(self, vendor_repo: MaintenanceVendorRepository) -> None:
        self.vendor_repo = vendor_repo

    # -------------------------------------------------------------------------
    # Vendor CRUD
    # -------------------------------------------------------------------------

    def create_vendor(
        self,
        db: Session,
        data: MaintenanceVendor,
    ) -> MaintenanceVendor:
        obj = self.vendor_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return MaintenanceVendor.model_validate(obj)

    def update_vendor(
        self,
        db: Session,
        vendor_id: UUID,
        data: MaintenanceVendor,
    ) -> MaintenanceVendor:
        vendor = self.vendor_repo.get_by_id(db, vendor_id)
        if not vendor:
            raise ValidationException("Vendor not found")

        updated = self.vendor_repo.update(
            db,
            vendor,
            data=data.model_dump(exclude_none=True),
        )
        return MaintenanceVendor.model_validate(updated)

    def get_vendor(
        self,
        db: Session,
        vendor_id: UUID,
    ) -> MaintenanceVendor:
        vendor = self.vendor_repo.get_by_id(db, vendor_id)
        if not vendor:
            raise ValidationException("Vendor not found")
        return MaintenanceVendor.model_validate(vendor)

    def list_vendors_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[MaintenanceVendor]:
        objs = self.vendor_repo.get_by_hostel_id(db, hostel_id)
        return [MaintenanceVendor.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Contracts & performance
    # -------------------------------------------------------------------------

    def list_contracts_for_vendor(
        self,
        db: Session,
        vendor_id: UUID,
    ) -> List[VendorContract]:
        objs = self.vendor_repo.get_contracts_for_vendor(db, vendor_id)
        return [VendorContract.model_validate(o) for o in objs]

    def list_performance_reviews_for_vendor(
        self,
        db: Session,
        vendor_id: UUID,
    ) -> List[VendorPerformanceReview]:
        objs = self.vendor_repo.get_performance_reviews_for_vendor(db, vendor_id)
        return [VendorPerformanceReview.model_validate(o) for o in objs)