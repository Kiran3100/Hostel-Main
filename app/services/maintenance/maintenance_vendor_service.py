"""
Maintenance Vendor Service

Comprehensive vendor management for maintenance operations.

Features:
- Vendor registration and profile management
- Contract management with expiry tracking
- Performance tracking and ratings
- Capability and certification management
- Invoice and payment tracking
- Compliance monitoring
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceVendorRepository
from app.schemas.maintenance import (
    MaintenanceVendor,
    VendorContract,
    VendorPerformanceReview,
)
from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.logging import logger


class MaintenanceVendorService:
    """
    High-level service for maintenance vendor management.

    Provides comprehensive vendor lifecycle management from onboarding
    to performance evaluation.
    """

    # Valid vendor status values
    VALID_STATUS = {"active", "inactive", "suspended", "blacklisted"}

    # Minimum acceptable performance rating (out of 5)
    MIN_ACCEPTABLE_RATING = 3.0

    def __init__(self, vendor_repo: MaintenanceVendorRepository) -> None:
        """
        Initialize the vendor service.

        Args:
            vendor_repo: Repository for vendor data persistence
        """
        if not vendor_repo:
            raise ValueError("MaintenanceVendorRepository is required")
        self.vendor_repo = vendor_repo

    # -------------------------------------------------------------------------
    # Vendor CRUD Operations
    # -------------------------------------------------------------------------

    def create_vendor(
        self,
        db: Session,
        data: MaintenanceVendor,
    ) -> MaintenanceVendor:
        """
        Register a new maintenance vendor.

        Args:
            db: Database session
            data: Vendor registration details

        Returns:
            Created MaintenanceVendor

        Raises:
            ValidationException: If vendor data is invalid
            BusinessLogicException: If vendor already exists
        """
        # Validate vendor data
        self._validate_vendor_create(data)

        try:
            # Check for duplicate vendor
            existing = self.vendor_repo.get_by_name(
                db,
                data.vendor_name,
                data.hostel_id
            )
            if existing:
                raise BusinessLogicException(
                    f"Vendor '{data.vendor_name}' already exists for this hostel"
                )

            logger.info(f"Creating vendor: {data.vendor_name}")

            payload = data.model_dump(exclude_none=True)
            
            # Set initial status if not provided
            if "status" not in payload:
                payload["status"] = "active"
            
            # Initialize rating if not provided
            if "average_rating" not in payload:
                payload["average_rating"] = None

            obj = self.vendor_repo.create(db, data=payload)

            logger.info(f"Successfully created vendor {obj.id}: {obj.vendor_name}")

            return MaintenanceVendor.model_validate(obj)

        except ValidationException:
            raise
        except BusinessLogicException:
            raise
        except Exception as e:
            logger.error(
                f"Error creating vendor: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to create vendor: {str(e)}"
            )

    def update_vendor(
        self,
        db: Session,
        vendor_id: UUID,
        data: MaintenanceVendor,
    ) -> MaintenanceVendor:
        """
        Update vendor information.

        Args:
            db: Database session
            vendor_id: UUID of vendor to update
            data: Updated vendor data

        Returns:
            Updated MaintenanceVendor

        Raises:
            ValidationException: If vendor not found or data invalid
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        # Validate update data
        self._validate_vendor_update(data)

        try:
            vendor = self.vendor_repo.get_by_id(db, vendor_id)
            if not vendor:
                raise ValidationException(f"Vendor {vendor_id} not found")

            logger.info(f"Updating vendor {vendor_id}")

            payload = data.model_dump(exclude_none=True)
            updated = self.vendor_repo.update(db, vendor, data=payload)

            logger.info(f"Successfully updated vendor {vendor_id}")

            return MaintenanceVendor.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating vendor {vendor_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update vendor: {str(e)}"
            )

    def get_vendor(
        self,
        db: Session,
        vendor_id: UUID,
    ) -> MaintenanceVendor:
        """
        Retrieve vendor details.

        Args:
            db: Database session
            vendor_id: UUID of the vendor

        Returns:
            MaintenanceVendor details

        Raises:
            ValidationException: If vendor not found
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        try:
            vendor = self.vendor_repo.get_by_id(db, vendor_id)
            if not vendor:
                raise ValidationException(f"Vendor {vendor_id} not found")
            
            return MaintenanceVendor.model_validate(vendor)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving vendor {vendor_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve vendor: {str(e)}"
            )

    def delete_vendor(
        self,
        db: Session,
        vendor_id: UUID,
        soft_delete: bool = True,
    ) -> bool:
        """
        Delete or deactivate a vendor.

        Args:
            db: Database session
            vendor_id: UUID of vendor to delete
            soft_delete: If True, set status to inactive instead of deleting

        Returns:
            True if successful

        Raises:
            ValidationException: If vendor not found
            BusinessLogicException: If vendor has active assignments
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        try:
            vendor = self.vendor_repo.get_by_id(db, vendor_id)
            if not vendor:
                raise ValidationException(f"Vendor {vendor_id} not found")

            # Check for active assignments
            active_assignments = self.vendor_repo.get_active_assignments_count(
                db,
                vendor_id
            )
            if active_assignments > 0:
                raise BusinessLogicException(
                    f"Cannot delete vendor with {active_assignments} active assignments"
                )

            if soft_delete:
                # Deactivate instead of delete
                self.vendor_repo.update(
                    db,
                    vendor,
                    data={
                        "status": "inactive",
                        "deactivated_at": datetime.utcnow(),
                    }
                )
                logger.info(f"Deactivated vendor {vendor_id}")
            else:
                # Hard delete
                self.vendor_repo.delete(db, vendor)
                logger.info(f"Deleted vendor {vendor_id}")

            return True

        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Error deleting vendor {vendor_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to delete vendor: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Vendor Listing and Search
    # -------------------------------------------------------------------------

    def list_vendors_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        min_rating: Optional[float] = None,
    ) -> List[MaintenanceVendor]:
        """
        List vendors for a hostel with optional filtering.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            status_filter: Optional status filter
            category_filter: Optional category filter
            min_rating: Optional minimum rating filter

        Returns:
            List of MaintenanceVendor records
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        if status_filter and status_filter not in self.VALID_STATUS:
            raise ValidationException(f"Invalid status: {status_filter}")

        if min_rating is not None and (min_rating < 0 or min_rating > 5):
            raise ValidationException("Rating must be between 0 and 5")

        try:
            objs = self.vendor_repo.get_by_hostel_id(
                db,
                hostel_id,
                status=status_filter,
                category=category_filter,
                min_rating=min_rating,
            )
            
            vendors = [MaintenanceVendor.model_validate(o) for o in objs]

            logger.debug(
                f"Retrieved {len(vendors)} vendors for hostel {hostel_id}"
            )

            return vendors

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error listing vendors for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve vendors: {str(e)}"
            )

    def search_vendors_by_capability(
        self,
        db: Session,
        hostel_id: UUID,
        capability: str,
    ) -> List[MaintenanceVendor]:
        """
        Search vendors by specific capability or service.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            capability: Required capability/service

        Returns:
            List of qualified vendors
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        if not capability:
            raise ValidationException("Capability is required")

        try:
            vendors = self.vendor_repo.search_by_capability(
                db,
                hostel_id,
                capability
            )

            results = [MaintenanceVendor.model_validate(v) for v in vendors]

            logger.info(
                f"Found {len(results)} vendors with capability '{capability}'"
            )

            return results

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error searching vendors: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to search vendors: {str(e)}"
            )

    def get_top_rated_vendors(
        self,
        db: Session,
        hostel_id: UUID,
        limit: int = 10,
    ) -> List[MaintenanceVendor]:
        """
        Get top-rated vendors for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            limit: Maximum number of vendors to return

        Returns:
            List of top-rated vendors
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            vendors = self.vendor_repo.get_top_rated(
                db,
                hostel_id,
                limit=limit
            )

            return [MaintenanceVendor.model_validate(v) for v in vendors]

        except Exception as e:
            logger.error(
                f"Error getting top-rated vendors: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve top-rated vendors: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Contract Management
    # -------------------------------------------------------------------------

    def list_contracts_for_vendor(
        self,
        db: Session,
        vendor_id: UUID,
        active_only: bool = False,
    ) -> List[VendorContract]:
        """
        List all contracts for a vendor.

        Args:
            db: Database session
            vendor_id: UUID of the vendor
            active_only: If True, return only active contracts

        Returns:
            List of VendorContract records
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        try:
            objs = self.vendor_repo.get_contracts_for_vendor(
                db,
                vendor_id,
                active_only=active_only
            )
            
            contracts = [VendorContract.model_validate(o) for o in objs]

            logger.debug(
                f"Retrieved {len(contracts)} contracts for vendor {vendor_id}"
            )

            return contracts

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving contracts: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve vendor contracts: {str(e)}"
            )

    def create_contract(
        self,
        db: Session,
        contract: VendorContract,
    ) -> VendorContract:
        """
        Create a new vendor contract.

        Args:
            db: Database session
            contract: Contract details

        Returns:
            Created VendorContract

        Raises:
            ValidationException: If contract data is invalid
        """
        self._validate_contract(contract)

        try:
            logger.info(
                f"Creating contract for vendor {contract.vendor_id}"
            )

            payload = contract.model_dump(exclude_none=True)
            obj = self.vendor_repo.create_contract(db=db, data=payload)

            logger.info(
                f"Contract created: {obj.contract_number} "
                f"(valid until {obj.end_date})"
            )

            # TODO: Schedule contract expiry reminder
            # await self._schedule_contract_reminder(obj)

            return VendorContract.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error creating contract: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to create vendor contract: {str(e)}"
            )

    def get_expiring_contracts(
        self,
        db: Session,
        hostel_id: UUID,
        days_ahead: int = 30,
    ) -> List[VendorContract]:
        """
        Get contracts expiring within specified days.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            days_ahead: Number of days to look ahead

        Returns:
            List of expiring contracts
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        if days_ahead < 0:
            raise ValidationException("days_ahead must be non-negative")

        try:
            cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
            
            contracts = self.vendor_repo.get_expiring_contracts(
                db=db,
                hostel_id=hostel_id,
                before_date=cutoff_date,
            )

            results = [VendorContract.model_validate(c) for c in contracts]

            if results:
                logger.warning(
                    f"Found {len(results)} contracts expiring within "
                    f"{days_ahead} days"
                )

            return results

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error getting expiring contracts: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve expiring contracts: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Performance Review Management
    # -------------------------------------------------------------------------

    def list_performance_reviews_for_vendor(
        self,
        db: Session,
        vendor_id: UUID,
        limit: Optional[int] = None,
    ) -> List[VendorPerformanceReview]:
        """
        List performance reviews for a vendor.

        Args:
            db: Database session
            vendor_id: UUID of the vendor
            limit: Optional limit on results

        Returns:
            List of VendorPerformanceReview records
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        try:
            objs = self.vendor_repo.get_performance_reviews_for_vendor(
                db,
                vendor_id,
                limit=limit
            )
            
            reviews = [VendorPerformanceReview.model_validate(o) for o in objs]

            logger.debug(
                f"Retrieved {len(reviews)} performance reviews for "
                f"vendor {vendor_id}"
            )

            return reviews

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving performance reviews: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve performance reviews: {str(e)}"
            )

    def create_performance_review(
        self,
        db: Session,
        review: VendorPerformanceReview,
    ) -> VendorPerformanceReview:
        """
        Create a vendor performance review.

        Updates vendor's average rating automatically.

        Args:
            db: Database session
            review: Performance review details

        Returns:
            Created VendorPerformanceReview

        Raises:
            ValidationException: If review data is invalid
        """
        self._validate_performance_review(review)

        try:
            logger.info(
                f"Creating performance review for vendor {review.vendor_id}"
            )

            payload = review.model_dump(exclude_none=True)
            obj = self.vendor_repo.create_performance_review(db=db, data=payload)

            # Update vendor's average rating
            self._update_vendor_rating(db, review.vendor_id)

            logger.info(
                f"Performance review created with rating {review.overall_rating}"
            )

            # Check if vendor rating is below acceptable threshold
            vendor = self.get_vendor(db, review.vendor_id)
            if (vendor.average_rating is not None and
                vendor.average_rating < self.MIN_ACCEPTABLE_RATING):
                logger.warning(
                    f"Vendor {review.vendor_id} rating "
                    f"({vendor.average_rating:.2f}) below acceptable threshold "
                    f"({self.MIN_ACCEPTABLE_RATING})"
                )
                # TODO: Trigger vendor performance review workflow
                # await self._trigger_vendor_review_workflow(vendor.id)

            return VendorPerformanceReview.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error creating performance review: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to create performance review: {str(e)}"
            )

    def get_vendor_performance_summary(
        self,
        db: Session,
        vendor_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance summary for a vendor.

        Args:
            db: Database session
            vendor_id: UUID of the vendor

        Returns:
            Dictionary with performance metrics
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        try:
            summary = self.vendor_repo.get_performance_summary(db, vendor_id)

            # Enrich with insights
            summary["insights"] = self._generate_performance_insights(summary)

            return summary

        except Exception as e:
            logger.error(
                f"Error getting performance summary: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve performance summary: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Vendor Status Management
    # -------------------------------------------------------------------------

    def suspend_vendor(
        self,
        db: Session,
        vendor_id: UUID,
        reason: str,
    ) -> MaintenanceVendor:
        """
        Suspend a vendor temporarily.

        Args:
            db: Database session
            vendor_id: UUID of vendor to suspend
            reason: Reason for suspension

        Returns:
            Updated MaintenanceVendor

        Raises:
            ValidationException: If vendor not found
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")
        if not reason or len(reason.strip()) < 10:
            raise ValidationException(
                "Suspension reason must be at least 10 characters"
            )

        try:
            vendor = self.vendor_repo.get_by_id(db, vendor_id)
            if not vendor:
                raise ValidationException(f"Vendor {vendor_id} not found")

            updated = self.vendor_repo.update(
                db,
                vendor,
                data={
                    "status": "suspended",
                    "suspension_reason": reason.strip(),
                    "suspended_at": datetime.utcnow(),
                }
            )

            logger.warning(
                f"Vendor {vendor_id} suspended. Reason: {reason}"
            )

            # TODO: Notify vendor and reassign active work
            # await self._notify_vendor_suspension(vendor_id)
            # await self._reassign_vendor_work(vendor_id)

            return MaintenanceVendor.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error suspending vendor: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to suspend vendor: {str(e)}"
            )

    def reactivate_vendor(
        self,
        db: Session,
        vendor_id: UUID,
    ) -> MaintenanceVendor:
        """
        Reactivate a suspended or inactive vendor.

        Args:
            db: Database session
            vendor_id: UUID of vendor to reactivate

        Returns:
            Updated MaintenanceVendor

        Raises:
            ValidationException: If vendor not found
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        try:
            vendor = self.vendor_repo.get_by_id(db, vendor_id)
            if not vendor:
                raise ValidationException(f"Vendor {vendor_id} not found")

            if vendor.status == "blacklisted":
                raise BusinessLogicException(
                    "Cannot reactivate blacklisted vendor"
                )

            updated = self.vendor_repo.update(
                db,
                vendor,
                data={
                    "status": "active",
                    "suspension_reason": None,
                    "suspended_at": None,
                    "reactivated_at": datetime.utcnow(),
                }
            )

            logger.info(f"Vendor {vendor_id} reactivated")

            return MaintenanceVendor.model_validate(updated)

        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Error reactivating vendor: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to reactivate vendor: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Private Validation and Helper Methods
    # -------------------------------------------------------------------------

    def _validate_vendor_create(self, data: MaintenanceVendor) -> None:
        """Validate vendor creation data."""
        if not data.hostel_id:
            raise ValidationException("Hostel ID is required")

        if not data.vendor_name or len(data.vendor_name.strip()) < 3:
            raise ValidationException(
                "Vendor name must be at least 3 characters"
            )

        if not data.contact_person:
            raise ValidationException("Contact person is required")

        if not data.contact_phone:
            raise ValidationException("Contact phone is required")

        if data.email and not self._is_valid_email(data.email):
            raise ValidationException("Invalid email format")

    def _validate_vendor_update(self, data: MaintenanceVendor) -> None:
        """Validate vendor update data."""
        if data.status and data.status not in self.VALID_STATUS:
            raise ValidationException(
                f"Invalid status. Must be one of: {self.VALID_STATUS}"
            )

        if data.email and not self._is_valid_email(data.email):
            raise ValidationException("Invalid email format")

        if data.average_rating is not None:
            if not 0 <= data.average_rating <= 5:
                raise ValidationException("Rating must be between 0 and 5")

    def _validate_contract(self, contract: VendorContract) -> None:
        """Validate vendor contract data."""
        if not contract.vendor_id:
            raise ValidationException("Vendor ID is required")

        if not contract.contract_number:
            raise ValidationException("Contract number is required")

        if not contract.start_date or not contract.end_date:
            raise ValidationException("Start date and end date are required")

        if contract.start_date >= contract.end_date:
            raise ValidationException("End date must be after start date")

        if contract.contract_value is not None and contract.contract_value <= 0:
            raise ValidationException("Contract value must be greater than zero")

    def _validate_performance_review(
        self,
        review: VendorPerformanceReview
    ) -> None:
        """Validate performance review data."""
        if not review.vendor_id:
            raise ValidationException("Vendor ID is required")

        if not review.reviewed_by:
            raise ValidationException("Reviewer ID is required")

        if review.overall_rating is None:
            raise ValidationException("Overall rating is required")

        if not 1 <= review.overall_rating <= 5:
            raise ValidationException("Rating must be between 1 and 5")

        # Validate individual rating components if provided
        ratings = [
            review.quality_rating,
            review.timeliness_rating,
            review.professionalism_rating,
            review.cost_rating,
        ]

        for rating in ratings:
            if rating is not None and not 1 <= rating <= 5:
                raise ValidationException(
                    "All rating components must be between 1 and 5"
                )

    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _update_vendor_rating(self, db: Session, vendor_id: UUID) -> None:
        """
        Recalculate and update vendor's average rating.

        Args:
            db: Database session
            vendor_id: UUID of the vendor
        """
        try:
            avg_rating = self.vendor_repo.calculate_average_rating(db, vendor_id)
            
            vendor = self.vendor_repo.get_by_id(db, vendor_id)
            if vendor:
                self.vendor_repo.update(
                    db,
                    vendor,
                    data={"average_rating": avg_rating}
                )
                logger.info(
                    f"Updated vendor {vendor_id} average rating to {avg_rating:.2f}"
                )

        except Exception as e:
            logger.error(
                f"Error updating vendor rating: {str(e)}",
                exc_info=True
            )
            # Don't raise - this is a background operation

    def _generate_performance_insights(
        self,
        summary: Dict[str, Any]
    ) -> List[str]:
        """
        Generate insights from performance summary.

        Args:
            summary: Performance summary data

        Returns:
            List of insight strings
        """
        insights = []
        
        avg_rating = summary.get("average_rating", 0)
        total_reviews = summary.get("total_reviews", 0)
        on_time_rate = summary.get("on_time_completion_rate", 0)

        if total_reviews == 0:
            insights.append("No performance reviews yet - consider initial evaluation")
            return insights

        if avg_rating >= 4.5:
            insights.append("Excellent performance - preferred vendor")
        elif avg_rating >= 4.0:
            insights.append("Good performance - reliable vendor")
        elif avg_rating >= 3.0:
            insights.append("Satisfactory performance - monitor closely")
        else:
            insights.append("Below expectations - review vendor relationship")

        if on_time_rate < 70:
            insights.append("Timeliness concerns - discuss schedule management")

        if total_reviews < 3:
            insights.append("Limited review history - gather more feedback")

        return insights