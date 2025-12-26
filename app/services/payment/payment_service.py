# app/services/payment/payment_service.py
"""
Payment Service

Core payment orchestration for:
- Creating manual (offline) payments
- Retrieving and listing payments
- High-level summary per student/hostel
- Payment status management
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentRepository, PaymentAggregateRepository
from app.schemas.payment import (
    ManualPaymentRequest,
    PaymentResponse,
    PaymentDetail,
    PaymentListItem,
    PaymentSummary,
    PaymentFilterParams,
    PaymentSortOptions,
)
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.models.base.enums import PaymentStatus, PaymentMethod
from app.core.logging import LoggingContext, logger


class PaymentService:
    """
    High-level orchestration for payments.

    Responsibilities:
    - Manual/offline payment recording
    - Payment retrieval and listing with advanced filtering
    - Payment status updates
    - Summary generation for students and hostels

    Delegates:
    - Persistence to PaymentRepository
    - Analytics to PaymentAggregateRepository
    """

    __slots__ = ("payment_repo", "aggregate_repo")

    def __init__(
        self,
        payment_repo: PaymentRepository,
        aggregate_repo: PaymentAggregateRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # Manual payments (offline)
    # -------------------------------------------------------------------------

    def record_manual_payment(
        self,
        db: Session,
        request: ManualPaymentRequest,
        recorded_by: Optional[UUID] = None,
    ) -> PaymentResponse:
        """
        Record an offline/manual payment (cash/cheque/bank transfer).

        Args:
            db: Database session
            request: Manual payment request details
            recorded_by: UUID of user recording the payment

        Returns:
            PaymentResponse with created payment details

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If business rules are violated
        """
        self._validate_manual_payment_request(request)

        payload = self._prepare_manual_payment_payload(request, recorded_by)

        with LoggingContext(
            payment_method=request.payment_method.value,
            student_id=str(request.student_id) if request.student_id else None,
        ):
            try:
                obj = self.payment_repo.create_manual_payment(db, payload)
                logger.info(
                    f"Manual payment recorded successfully: {obj.id}",
                    extra={
                        "payment_id": str(obj.id),
                        "amount": float(obj.amount),
                        "method": obj.payment_method.value,
                    },
                )
                return PaymentResponse.model_validate(obj)
            except Exception as e:
                logger.error(f"Failed to record manual payment: {str(e)}")
                raise BusinessLogicException(
                    f"Failed to record manual payment: {str(e)}"
                )

    def _validate_manual_payment_request(
        self, request: ManualPaymentRequest
    ) -> None:
        """Validate manual payment request data."""
        if request.amount <= 0:
            raise ValidationException("Payment amount must be positive")

        if request.payment_method not in {
            PaymentMethod.CASH,
            PaymentMethod.CHEQUE,
            PaymentMethod.BANK_TRANSFER,
            PaymentMethod.DEMAND_DRAFT,
        }:
            raise ValidationException(
                f"Invalid manual payment method: {request.payment_method}"
            )

        # Method-specific validation
        if request.payment_method == PaymentMethod.CHEQUE:
            if not request.cheque_number:
                raise ValidationException("Cheque number is required for cheque payments")
            if not request.cheque_date:
                raise ValidationException("Cheque date is required for cheque payments")
            if not request.bank_name:
                raise ValidationException("Bank name is required for cheque payments")

        if request.payment_method == PaymentMethod.BANK_TRANSFER:
            if not request.transaction_reference:
                raise ValidationException(
                    "Transaction reference is required for bank transfers"
                )

    def _prepare_manual_payment_payload(
        self, request: ManualPaymentRequest, recorded_by: Optional[UUID]
    ) -> Dict[str, Any]:
        """Prepare payload for manual payment creation."""
        payload = request.model_dump(exclude_none=True)
        if recorded_by:
            payload["recorded_by"] = recorded_by
        return payload

    # -------------------------------------------------------------------------
    # Retrieval & listing
    # -------------------------------------------------------------------------

    def get_payment(
        self,
        db: Session,
        payment_id: UUID,
        include_relations: bool = False,
    ) -> PaymentDetail:
        """
        Retrieve a single payment by ID.

        Args:
            db: Database session
            payment_id: Payment UUID
            include_relations: Whether to include related entities

        Returns:
            PaymentDetail with payment information

        Raises:
            NotFoundException: If payment not found
        """
        obj = self.payment_repo.get_by_id(
            db, payment_id, include_relations=include_relations
        )
        if not obj:
            raise NotFoundException(f"Payment not found: {payment_id}")

        return PaymentDetail.model_validate(obj)

    def get_payment_by_reference(
        self,
        db: Session,
        payment_reference: str,
    ) -> PaymentDetail:
        """
        Retrieve a payment by its reference number.

        Args:
            db: Database session
            payment_reference: Unique payment reference

        Returns:
            PaymentDetail with payment information

        Raises:
            NotFoundException: If payment not found
        """
        obj = self.payment_repo.get_by_reference(db, payment_reference)
        if not obj:
            raise NotFoundException(
                f"Payment not found with reference: {payment_reference}"
            )

        return PaymentDetail.model_validate(obj)

    def list_payments_for_student(
        self,
        db: Session,
        student_id: UUID,
        filters: Optional[PaymentFilterParams] = None,
        sort: Optional[PaymentSortOptions] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[PaymentListItem], int]:
        """
        List payments for a student with filtering, sorting, and pagination.

        Args:
            db: Database session
            student_id: Student UUID
            filters: Optional filter parameters
            sort: Optional sort options
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (payment list items, total count)

        Raises:
            ValidationException: If pagination parameters are invalid
        """
        self._validate_pagination(page, page_size)

        filters_dict = filters.model_dump(exclude_none=True) if filters else {}
        sort_dict = sort.model_dump(exclude_none=True) if sort else {}

        with LoggingContext(student_id=str(student_id)):
            result = self.payment_repo.search_payments_for_student(
                db=db,
                student_id=student_id,
                filters=filters_dict,
                sort=sort_dict,
                page=page,
                page_size=page_size,
            )

        items = [PaymentListItem.model_validate(o) for o in result["items"]]
        total = result["total"]

        logger.debug(
            f"Retrieved {len(items)} payments for student",
            extra={"student_id": str(student_id), "total": total},
        )

        return items, total

    def list_payments_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        filters: Optional[PaymentFilterParams] = None,
        sort: Optional[PaymentSortOptions] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[PaymentListItem], int]:
        """
        List payments for a hostel with filtering, sorting, and pagination.

        Args:
            db: Database session
            hostel_id: Hostel UUID
            filters: Optional filter parameters
            sort: Optional sort options
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (payment list items, total count)

        Raises:
            ValidationException: If pagination parameters are invalid
        """
        self._validate_pagination(page, page_size)

        filters_dict = filters.model_dump(exclude_none=True) if filters else {}
        sort_dict = sort.model_dump(exclude_none=True) if sort else {}

        with LoggingContext(hostel_id=str(hostel_id)):
            result = self.payment_repo.search_payments_for_hostel(
                db=db,
                hostel_id=hostel_id,
                filters=filters_dict,
                sort=sort_dict,
                page=page,
                page_size=page_size,
            )

        items = [PaymentListItem.model_validate(o) for o in result["items"]]
        total = result["total"]

        logger.debug(
            f"Retrieved {len(items)} payments for hostel",
            extra={"hostel_id": str(hostel_id), "total": total},
        )

        return items, total

    def _validate_pagination(self, page: int, page_size: int) -> None:
        """Validate pagination parameters."""
        if page < 1:
            raise ValidationException("Page number must be >= 1")
        if page_size < 1 or page_size > 1000:
            raise ValidationException("Page size must be between 1 and 1000")

    # -------------------------------------------------------------------------
    # Status updates
    # -------------------------------------------------------------------------

    def mark_payment_status(
        self,
        db: Session,
        payment_id: UUID,
        status: PaymentStatus,
        failure_reason: Optional[str] = None,
        transaction_id: Optional[str] = None,
        updated_by: Optional[UUID] = None,
    ) -> PaymentResponse:
        """
        Update payment status with optional failure reason.

        Args:
            db: Database session
            payment_id: Payment UUID
            status: New payment status
            failure_reason: Optional failure reason for failed payments
            transaction_id: Optional transaction ID
            updated_by: UUID of user updating the status

        Returns:
            PaymentResponse with updated payment

        Raises:
            NotFoundException: If payment not found
            BusinessLogicException: If status transition is invalid
        """
        obj = self.payment_repo.get_by_id(db, payment_id)
        if not obj:
            raise NotFoundException(f"Payment not found: {payment_id}")

        # Validate status transition
        self._validate_status_transition(obj.status, status)

        update_data = {
            "status": status.value,
            "failure_reason": failure_reason,
        }

        if transaction_id:
            update_data["transaction_id"] = transaction_id

        if updated_by:
            update_data["updated_by"] = updated_by

        with LoggingContext(payment_id=str(payment_id)):
            updated = self.payment_repo.update(db, obj, data=update_data)
            logger.info(
                f"Payment status updated: {obj.status.value} -> {status.value}",
                extra={
                    "payment_id": str(payment_id),
                    "old_status": obj.status.value,
                    "new_status": status.value,
                },
            )

        return PaymentResponse.model_validate(updated)

    def _validate_status_transition(
        self, current_status: PaymentStatus, new_status: PaymentStatus
    ) -> None:
        """
        Validate if status transition is allowed.

        Business rules:
        - COMPLETED payments cannot be changed
        - REFUNDED payments cannot be changed
        - CANCELLED payments can only move to PENDING for retry
        """
        if current_status == PaymentStatus.COMPLETED and new_status != PaymentStatus.REFUNDED:
            raise BusinessLogicException(
                "Completed payments can only be refunded, not changed to other statuses"
            )

        if current_status == PaymentStatus.REFUNDED:
            raise BusinessLogicException("Refunded payments cannot be modified")

        if current_status == PaymentStatus.CANCELLED and new_status not in {
            PaymentStatus.PENDING,
            PaymentStatus.INITIATED,
        }:
            raise BusinessLogicException(
                "Cancelled payments can only be reactivated to PENDING or INITIATED"
            )

    # -------------------------------------------------------------------------
    # Bulk operations
    # -------------------------------------------------------------------------

    def bulk_update_status(
        self,
        db: Session,
        payment_ids: List[UUID],
        status: PaymentStatus,
        failure_reason: Optional[str] = None,
        updated_by: Optional[UUID] = None,
    ) -> List[PaymentResponse]:
        """
        Update status for multiple payments in bulk.

        Args:
            db: Database session
            payment_ids: List of payment UUIDs
            status: New payment status
            failure_reason: Optional failure reason
            updated_by: UUID of user performing the update

        Returns:
            List of updated PaymentResponse objects
        """
        if not payment_ids:
            return []

        results = []
        for payment_id in payment_ids:
            try:
                result = self.mark_payment_status(
                    db=db,
                    payment_id=payment_id,
                    status=status,
                    failure_reason=failure_reason,
                    updated_by=updated_by,
                )
                results.append(result)
            except (NotFoundException, BusinessLogicException) as e:
                logger.warning(
                    f"Failed to update payment {payment_id}: {str(e)}",
                    extra={"payment_id": str(payment_id)},
                )
                continue

        logger.info(
            f"Bulk status update completed: {len(results)}/{len(payment_ids)} successful"
        )
        return results

    # -------------------------------------------------------------------------
    # Summary & analytics
    # -------------------------------------------------------------------------

    def get_student_payment_summary(
        self,
        db: Session,
        student_id: UUID,
    ) -> PaymentSummary:
        """
        Get payment summary for a student.

        Args:
            db: Database session
            student_id: Student UUID

        Returns:
            PaymentSummary with aggregated metrics
        """
        data = self.aggregate_repo.get_student_payment_summary(db, student_id)

        if not data:
            return self._create_empty_summary(student_id=student_id)

        return PaymentSummary.model_validate(data)

    def get_hostel_payment_summary(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> PaymentSummary:
        """
        Get payment summary for a hostel.

        Args:
            db: Database session
            hostel_id: Hostel UUID

        Returns:
            PaymentSummary with aggregated metrics
        """
        data = self.aggregate_repo.get_hostel_payment_summary(db, hostel_id)

        if not data:
            return self._create_empty_summary(hostel_id=hostel_id)

        return PaymentSummary.model_validate(data)

    def _create_empty_summary(
        self,
        student_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
    ) -> PaymentSummary:
        """Create an empty payment summary."""
        return PaymentSummary(
            student_id=student_id,
            hostel_id=hostel_id,
            total_paid=Decimal("0.00"),
            total_pending=Decimal("0.00"),
            total_overdue=Decimal("0.00"),
            last_payment_date=None,
            last_payment_amount=Decimal("0.00"),
            next_due_date=None,
            next_due_amount=Decimal("0.00"),
            total_payments=0,
            completed_payments=0,
            pending_payments=0,
        )

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def cancel_payment(
        self,
        db: Session,
        payment_id: UUID,
        cancellation_reason: str,
        cancelled_by: Optional[UUID] = None,
    ) -> PaymentResponse:
        """
        Cancel a pending payment.

        Args:
            db: Database session
            payment_id: Payment UUID
            cancellation_reason: Reason for cancellation
            cancelled_by: UUID of user cancelling the payment

        Returns:
            PaymentResponse with cancelled payment

        Raises:
            BusinessLogicException: If payment cannot be cancelled
        """
        obj = self.payment_repo.get_by_id(db, payment_id)
        if not obj:
            raise NotFoundException(f"Payment not found: {payment_id}")

        if obj.status not in {PaymentStatus.PENDING, PaymentStatus.INITIATED}:
            raise BusinessLogicException(
                f"Cannot cancel payment with status: {obj.status.value}"
            )

        return self.mark_payment_status(
            db=db,
            payment_id=payment_id,
            status=PaymentStatus.CANCELLED,
            failure_reason=cancellation_reason,
            updated_by=cancelled_by,
        )