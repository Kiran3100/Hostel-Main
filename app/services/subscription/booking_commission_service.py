"""
Booking Commission Service

Manages commission records for bookings under subscription programs.

Improvements:
- Enhanced validation and error handling
- Added decimal precision for financial calculations
- Improved logging capabilities
- Better separation of concerns
- Added transaction safety patterns
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.subscription import BookingCommissionRepository
from app.schemas.subscription import (
    BookingCommissionResponse,
    CommissionStatus,
)
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class BookingCommissionService:
    """
    High-level service for booking commissions.

    Responsibilities:
    - Create commission records for bookings
    - Retrieve commissions by id/booking/subscription/hostel
    - Mark commissions as paid/waived/disputed
    - Handle commission lifecycle management
    """

    # Constants for validation
    MIN_COMMISSION_PERCENTAGE = Decimal("0.0")
    MAX_COMMISSION_PERCENTAGE = Decimal("100.0")
    DECIMAL_PLACES = 2

    def __init__(
        self,
        commission_repo: BookingCommissionRepository,
    ) -> None:
        """
        Initialize the commission service.

        Args:
            commission_repo: Repository for commission data access
        """
        if not commission_repo:
            raise ValueError("Commission repository is required")
        self.commission_repo = commission_repo

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    def create_commission_for_booking(
        self,
        db: Session,
        booking_id: UUID,
        subscription_id: UUID,
        hostel_id: UUID,
        booking_amount: float,
        commission_percentage: float,
        currency: str,
        due_date: Optional[datetime] = None,
    ) -> BookingCommissionResponse:
        """
        Create a commission record for a booking.

        The percentage is applied to booking_amount to compute commission_amount
        using Decimal arithmetic for financial precision.

        Args:
            db: Database session
            booking_id: ID of the associated booking
            subscription_id: ID of the subscription plan
            hostel_id: ID of the hostel
            booking_amount: Total booking amount
            commission_percentage: Commission rate as percentage
            currency: ISO currency code (e.g., 'USD', 'EUR')
            due_date: Optional payment due date

        Returns:
            BookingCommissionResponse with created commission details

        Raises:
            ValidationException: If validation fails
        """
        # Validate inputs
        self._validate_commission_inputs(
            booking_amount=booking_amount,
            commission_percentage=commission_percentage,
            currency=currency,
        )

        # Calculate commission with precise decimal arithmetic
        commission_amount = self._calculate_commission_amount(
            booking_amount=booking_amount,
            commission_percentage=commission_percentage,
        )

        commission_data = {
            "booking_id": booking_id,
            "subscription_id": subscription_id,
            "hostel_id": hostel_id,
            "booking_amount": booking_amount,
            "commission_percentage": commission_percentage,
            "commission_amount": commission_amount,
            "currency": currency.upper(),
            "status": CommissionStatus.PENDING.value,
            "due_date": due_date,
        }

        try:
            obj = self.commission_repo.create(db, data=commission_data)
            logger.info(
                f"Commission created for booking {booking_id}: "
                f"{commission_amount} {currency} "
                f"({commission_percentage}% of {booking_amount})"
            )
            return BookingCommissionResponse.model_validate(obj)
        except Exception as e:
            logger.error(f"Failed to create commission for booking {booking_id}: {str(e)}")
            raise ValidationException(f"Failed to create commission: {str(e)}")

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_commission(
        self,
        db: Session,
        commission_id: UUID,
    ) -> BookingCommissionResponse:
        """
        Retrieve a commission record by ID.

        Args:
            db: Database session
            commission_id: UUID of the commission

        Returns:
            BookingCommissionResponse

        Raises:
            ValidationException: If commission not found
        """
        obj = self.commission_repo.get_by_id(db, commission_id)
        if not obj:
            logger.warning(f"Commission not found: {commission_id}")
            raise ValidationException(f"Commission not found with ID: {commission_id}")
        
        return BookingCommissionResponse.model_validate(obj)

    def get_commission_by_booking(
        self,
        db: Session,
        booking_id: UUID,
    ) -> Optional[BookingCommissionResponse]:
        """
        Retrieve commission record for a specific booking.

        Args:
            db: Database session
            booking_id: UUID of the booking

        Returns:
            BookingCommissionResponse or None if not found
        """
        objs = self.commission_repo.get_by_booking_id(db, booking_id)
        if not objs:
            return None
        
        # Return the first (should only be one per booking)
        return BookingCommissionResponse.model_validate(objs[0]) if objs else None

    def list_commissions_for_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        status: Optional[CommissionStatus] = None,
    ) -> List[BookingCommissionResponse]:
        """
        List all commissions for a subscription, optionally filtered by status.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            status: Optional status filter

        Returns:
            List of BookingCommissionResponse objects
        """
        objs = self.commission_repo.get_by_subscription_id(
            db, 
            subscription_id,
            status=status.value if status else None
        )
        return [BookingCommissionResponse.model_validate(o) for o in objs]

    def list_commissions_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        status: Optional[CommissionStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[BookingCommissionResponse]:
        """
        List all commissions for a hostel with optional filters.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            status: Optional status filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of BookingCommissionResponse objects
        """
        objs = self.commission_repo.get_by_hostel_id(
            db,
            hostel_id,
            status=status.value if status else None,
            start_date=start_date,
            end_date=end_date,
        )
        return [BookingCommissionResponse.model_validate(o) for o in objs]

    def get_total_commissions_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        status: Optional[CommissionStatus] = None,
    ) -> Decimal:
        """
        Calculate total commission amount for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            status: Optional status filter

        Returns:
            Total commission amount as Decimal
        """
        commissions = self.list_commissions_for_hostel(
            db, 
            hostel_id=hostel_id, 
            status=status
        )
        return sum(
            (Decimal(str(c.commission_amount)) for c in commissions),
            Decimal("0.00")
        )

    # -------------------------------------------------------------------------
    # Status updates
    # -------------------------------------------------------------------------

    def mark_commission_paid(
        self,
        db: Session,
        commission_id: UUID,
        payment_reference: Optional[str] = None,
        paid_at: Optional[datetime] = None,
    ) -> BookingCommissionResponse:
        """
        Mark a commission as paid.

        Args:
            db: Database session
            commission_id: UUID of the commission
            payment_reference: Optional payment reference/transaction ID
            paid_at: Optional payment timestamp (defaults to now)

        Returns:
            Updated BookingCommissionResponse

        Raises:
            ValidationException: If commission not found or invalid state
        """
        obj = self.commission_repo.get_by_id(db, commission_id)
        if not obj:
            raise ValidationException(f"Commission not found with ID: {commission_id}")

        # Validate current status allows payment
        if obj.status == CommissionStatus.PAID.value:
            logger.warning(f"Commission {commission_id} is already paid")
            raise ValidationException("Commission is already marked as paid")

        if obj.status == CommissionStatus.WAIVED.value:
            logger.warning(f"Cannot mark waived commission {commission_id} as paid")
            raise ValidationException("Cannot mark waived commission as paid")

        paid_date = paid_at or datetime.utcnow()
        
        update_data = {
            "status": CommissionStatus.PAID.value,
            "paid_date": paid_date,
            "payment_reference": payment_reference,
        }

        try:
            updated = self.commission_repo.update(db, obj, data=update_data)
            logger.info(
                f"Commission {commission_id} marked as paid. "
                f"Reference: {payment_reference}, Date: {paid_date}"
            )
            return BookingCommissionResponse.model_validate(updated)
        except Exception as e:
            logger.error(f"Failed to mark commission {commission_id} as paid: {str(e)}")
            raise ValidationException(f"Failed to update commission: {str(e)}")

    def update_commission_status(
        self,
        db: Session,
        commission_id: UUID,
        status: CommissionStatus,
        reason: Optional[str] = None,
    ) -> BookingCommissionResponse:
        """
        Update commission status (e.g., WAIVED, DISPUTED, INVOICED).

        Args:
            db: Database session
            commission_id: UUID of the commission
            status: New commission status
            reason: Optional reason for status change

        Returns:
            Updated BookingCommissionResponse

        Raises:
            ValidationException: If commission not found or invalid transition
        """
        obj = self.commission_repo.get_by_id(db, commission_id)
        if not obj:
            raise ValidationException(f"Commission not found with ID: {commission_id}")

        # Validate status transition
        self._validate_status_transition(
            current_status=CommissionStatus(obj.status),
            new_status=status,
        )

        update_data = {
            "status": status.value,
            "status_reason": reason,
        }

        # Add timestamp for specific statuses
        if status == CommissionStatus.WAIVED:
            update_data["waived_date"] = datetime.utcnow()
        elif status == CommissionStatus.DISPUTED:
            update_data["disputed_date"] = datetime.utcnow()

        try:
            updated = self.commission_repo.update(db, obj, data=update_data)
            logger.info(
                f"Commission {commission_id} status updated to {status.value}. "
                f"Reason: {reason or 'N/A'}"
            )
            return BookingCommissionResponse.model_validate(updated)
        except Exception as e:
            logger.error(
                f"Failed to update commission {commission_id} status to {status.value}: {str(e)}"
            )
            raise ValidationException(f"Failed to update commission status: {str(e)}")

    def bulk_update_commission_status(
        self,
        db: Session,
        commission_ids: List[UUID],
        status: CommissionStatus,
        reason: Optional[str] = None,
    ) -> List[BookingCommissionResponse]:
        """
        Update status for multiple commissions in bulk.

        Args:
            db: Database session
            commission_ids: List of commission UUIDs
            status: New commission status
            reason: Optional reason for status change

        Returns:
            List of updated BookingCommissionResponse objects
        """
        if not commission_ids:
            return []

        updated_commissions = []
        failed_ids = []

        for commission_id in commission_ids:
            try:
                updated = self.update_commission_status(
                    db=db,
                    commission_id=commission_id,
                    status=status,
                    reason=reason,
                )
                updated_commissions.append(updated)
            except ValidationException as e:
                logger.warning(f"Failed to update commission {commission_id}: {str(e)}")
                failed_ids.append(commission_id)

        if failed_ids:
            logger.warning(f"Bulk update failed for {len(failed_ids)} commissions: {failed_ids}")

        return updated_commissions

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_commission_inputs(
        self,
        booking_amount: float,
        commission_percentage: float,
        currency: str,
    ) -> None:
        """
        Validate commission creation inputs.

        Args:
            booking_amount: Booking amount to validate
            commission_percentage: Commission percentage to validate
            currency: Currency code to validate

        Raises:
            ValidationException: If validation fails
        """
        # Validate booking amount
        if booking_amount <= 0:
            raise ValidationException("Booking amount must be positive")

        # Validate commission percentage
        percentage_decimal = Decimal(str(commission_percentage))
        if not (self.MIN_COMMISSION_PERCENTAGE <= percentage_decimal <= self.MAX_COMMISSION_PERCENTAGE):
            raise ValidationException(
                f"Commission percentage must be between "
                f"{self.MIN_COMMISSION_PERCENTAGE}% and {self.MAX_COMMISSION_PERCENTAGE}%"
            )

        # Validate currency code
        if not currency or len(currency) != 3:
            raise ValidationException("Invalid currency code. Must be 3-letter ISO code")

    def _calculate_commission_amount(
        self,
        booking_amount: float,
        commission_percentage: float,
    ) -> float:
        """
        Calculate commission amount with precise decimal arithmetic.

        Args:
            booking_amount: Total booking amount
            commission_percentage: Commission rate as percentage

        Returns:
            Commission amount rounded to 2 decimal places
        """
        amount_decimal = Decimal(str(booking_amount))
        percentage_decimal = Decimal(str(commission_percentage))
        
        commission = amount_decimal * (percentage_decimal / Decimal("100.0"))
        
        # Round to specified decimal places using ROUND_HALF_UP
        rounded_commission = commission.quantize(
            Decimal(10) ** -self.DECIMAL_PLACES,
            rounding=ROUND_HALF_UP
        )
        
        return float(rounded_commission)

    def _validate_status_transition(
        self,
        current_status: CommissionStatus,
        new_status: CommissionStatus,
    ) -> None:
        """
        Validate if a status transition is allowed.

        Args:
            current_status: Current commission status
            new_status: Desired new status

        Raises:
            ValidationException: If transition is not allowed
        """
        # Define allowed transitions
        allowed_transitions = {
            CommissionStatus.PENDING: {
                CommissionStatus.INVOICED,
                CommissionStatus.PAID,
                CommissionStatus.WAIVED,
                CommissionStatus.DISPUTED,
            },
            CommissionStatus.INVOICED: {
                CommissionStatus.PAID,
                CommissionStatus.DISPUTED,
                CommissionStatus.PENDING,
            },
            CommissionStatus.DISPUTED: {
                CommissionStatus.PENDING,
                CommissionStatus.PAID,
                CommissionStatus.WAIVED,
            },
            CommissionStatus.PAID: set(),  # Terminal state
            CommissionStatus.WAIVED: set(),  # Terminal state
        }

        if new_status not in allowed_transitions.get(current_status, set()):
            raise ValidationException(
                f"Invalid status transition from {current_status.value} to {new_status.value}"
            )