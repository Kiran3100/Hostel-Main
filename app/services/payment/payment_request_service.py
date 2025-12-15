# app/services/payment/payment_request_service.py
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.repositories.core import HostelRepository, StudentRepository, UserRepository
from app.schemas.common.enums import PaymentStatus
from app.schemas.payment import (
    PaymentRequest,
    PaymentInitiation,
    ManualPaymentRequest,
)
from app.services.common import UnitOfWork, errors
from app.services.payment.payment_gateway_service import PaymentGatewayService


class PaymentRequestService:
    """
    High-level payment initiation:

    - Online payment initiation (gateway-based)
    - Manual payment recording (cash/cheque/bank_transfer)
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        gateway_service: PaymentGatewayService,
    ) -> None:
        self._session_factory = session_factory
        self._gateway = gateway_service

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Online payment
    # ------------------------------------------------------------------ #
    def initiate_online_payment(self, data: PaymentRequest) -> PaymentInitiation:
        """
        Create a Payment record with PENDING status and build a gateway order.

        The returned PaymentInitiation contains gateway details for client-side checkout.
        """
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            if data.student_id:
                st = student_repo.get(data.student_id)
                if st is None:
                    raise errors.NotFoundError(f"Student {data.student_id} not found")

            # For online payments, payer is the student.user or direct user later; here we reuse student_id
            payer_id: UUID = data.student_id or UUID(int=0)

            payload = {
                "payer_id": payer_id,
                "hostel_id": data.hostel_id,
                "student_id": data.student_id,
                "booking_id": data.booking_id,
                "payment_type": data.payment_type,
                "amount": data.amount,
                "currency": "INR",
                "payment_period_start": data.payment_period_start,
                "payment_period_end": data.payment_period_end,
                "payment_method": data.payment_method,
                "payment_gateway": data.payment_gateway,
                "payment_status": PaymentStatus.PENDING,
                "due_date": None,
            }
            payment = pay_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

        # Outside UnitOfWork: build gateway request and order
        order_id = f"ORD-{payment.id}"
        description = f"{data.payment_type.value if hasattr(data.payment_type,'value') else str(data.payment_type)}"
        gw_req = self._gateway.build_gateway_request(
            payment_id=payment.id,
            order_id=order_id,
            description=description,
            callback_url=data.success_url or "",
            success_url=data.success_url,
            failure_url=data.failure_url,
        )
        gw_resp = self._gateway.create_gateway_order(gw_req)

        return PaymentInitiation(
            payment_id=payment.id,
            payment_reference=str(payment.id),
            amount=payment.amount,
            currency=payment.currency,
            gateway=data.payment_gateway,
            gateway_order_id=gw_resp.gateway_order_id,
            gateway_key="",
            checkout_url=None,
            checkout_token=None,
            gateway_options=gw_resp.gateway_response,
        )

    # ------------------------------------------------------------------ #
    # Manual payments
    # ------------------------------------------------------------------ #
    def record_manual_payment(self, data: ManualPaymentRequest) -> UUID:
        """
        Record a manual payment (cash/cheque/bank_transfer) as COMPLETED.
        Returns the new Payment.id.
        """
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            st = student_repo.get(data.student_id)
            if st is None:
                raise errors.NotFoundError(f"Student {data.student_id} not found")

            payer_id = st.user_id

            payload = {
                "payer_id": payer_id,
                "hostel_id": data.hostel_id,
                "student_id": data.student_id,
                "booking_id": None,
                "payment_type": data.payment_type,
                "amount": data.amount,
                "currency": "INR",
                "payment_period_start": data.payment_period_start,
                "payment_period_end": data.payment_period_end,
                "payment_method": data.payment_method,
                "payment_gateway": None,
                "payment_status": PaymentStatus.COMPLETED,
                "transaction_id": data.transaction_reference,
                "due_date": None,
                "paid_at": datetime.combine(data.collection_date, datetime.min.time()),
                "failure_reason": None,
            }
            p = pay_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return p.id