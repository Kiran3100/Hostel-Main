# app/services/payment/payment_service.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.repositories.core import HostelRepository, StudentRepository, UserRepository
from app.schemas.common.enums import PaymentStatus
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.payment import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaymentDetail,
    PaymentListItem,
    PaymentSummary,
)
from app.schemas.payment.payment_filters import (
    PaymentFilterParams,
    PaymentSearchRequest,
)
from app.services.common import UnitOfWork, errors


class PaymentService:
    """
    Core payment service:

    - Create / update payments
    - Retrieve payment detail
    - List & search payments (with filters)
    - Summaries per student / hostel
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

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

    def _is_overdue(self, p) -> bool:
        if p.payment_status != PaymentStatus.PENDING:
            return False
        if not p.due_date:
            return False
        return p.due_date < date.today()

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        p,
        *,
        payer_name: str,
        hostel_name: str,
    ) -> PaymentResponse:
        return PaymentResponse(
            id=p.id,
            created_at=p.created_at,
            updated_at=p.updated_at,
            payment_reference=str(p.id),
            transaction_id=p.transaction_id,
            payer_id=p.payer_id,
            payer_name=payer_name,
            hostel_id=p.hostel_id,
            hostel_name=hostel_name,
            payment_type=p.payment_type,
            amount=p.amount,
            currency=p.currency,
            payment_method=p.payment_method,
            payment_status=p.payment_status,
            paid_at=p.paid_at,
            due_date=p.due_date,
            is_overdue=self._is_overdue(p),
            receipt_number=p.receipt_number,
            receipt_url=p.receipt_url,
        )

    def _to_detail(
        self,
        p,
        *,
        payer_name: str,
        payer_email: str,
        payer_phone: str,
        hostel_name: str,
        student_name: Optional[str],
        booking_reference: Optional[str],
        collected_by_name: Optional[str],
    ) -> PaymentDetail:
        is_overdue = self._is_overdue(p)

        return PaymentDetail(
            id=p.id,
            created_at=p.created_at,
            updated_at=p.updated_at,
            payment_reference=str(p.id),
            transaction_id=p.transaction_id,
            payer_id=p.payer_id,
            payer_name=payer_name,
            payer_email=payer_email,
            payer_phone=payer_phone,
            hostel_id=p.hostel_id,
            hostel_name=hostel_name,
            student_id=p.student_id,
            student_name=student_name,
            booking_id=p.booking_id,
            booking_reference=booking_reference,
            payment_type=p.payment_type,
            amount=p.amount,
            currency=p.currency,
            payment_period_start=p.payment_period_start,
            payment_period_end=p.payment_period_end,
            payment_method=p.payment_method,
            payment_gateway=p.payment_gateway,
            payment_status=p.payment_status,
            paid_at=p.paid_at,
            failed_at=p.failed_at,
            failure_reason=p.failure_reason,
            gateway_response=None,
            receipt_number=p.receipt_number,
            receipt_url=p.receipt_url,
            receipt_generated_at=None,
            refund_amount=Decimal("0"),
            refund_status="none",
            refunded_at=None,
            refund_transaction_id=None,
            refund_reason=None,
            collected_by=None,
            collected_by_name=collected_by_name,
            collected_at=None,
            due_date=p.due_date,
            is_overdue=is_overdue,
            reminder_sent_count=0,
            last_reminder_sent_at=None,
        )

    def _to_list_item(
        self,
        p,
        *,
        payer_name: str,
        hostel_name: str,
    ) -> PaymentListItem:
        return PaymentListItem(
            id=p.id,
            payment_reference=str(p.id),
            payer_name=payer_name,
            hostel_name=hostel_name,
            payment_type=p.payment_type.value if hasattr(p.payment_type, "value") else str(p.payment_type),
            amount=p.amount,
            payment_method=p.payment_method.value
            if hasattr(p.payment_method, "value")
            else str(p.payment_method),
            payment_status=p.payment_status,
            paid_at=p.paid_at,
            due_date=p.due_date,
            is_overdue=self._is_overdue(p),
            created_at=p.created_at,
        )

    # ------------------------------------------------------------------ #
    # Core read
    # ------------------------------------------------------------------ #
    def get_payment(self, payment_id: UUID) -> PaymentDetail:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            user_repo = self._get_user_repo(uow)

            p = pay_repo.get(payment_id)
            if p is None:
                raise errors.NotFoundError(f"Payment {payment_id} not found")

            payer = user_repo.get(p.payer_id)
            if payer is None:
                raise errors.NotFoundError(f"Payer user {p.payer_id} not found")
            payer_name = payer.full_name
            payer_email = payer.email
            payer_phone = getattr(payer, "phone", "")

            hostel = hostel_repo.get(p.hostel_id)
            hostel_name = hostel.name if hostel else ""

            student_name = None
            if p.student_id:
                st = student_repo.get(p.student_id)
                if st and getattr(st, "user", None):
                    student_name = st.user.full_name

            booking_reference = None
            collected_by_name = None

            return self._to_detail(
                p,
                payer_name=payer_name,
                payer_email=payer_email,
                payer_phone=payer_phone,
                hostel_name=hostel_name,
                student_name=student_name,
                booking_reference=booking_reference,
                collected_by_name=collected_by_name,
            )

    # ------------------------------------------------------------------ #
    # Create / update
    # ------------------------------------------------------------------ #
    def create_payment(self, data: PaymentCreate) -> PaymentDetail:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            user_repo = self._get_user_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            payer = user_repo.get(data.payer_id)
            if payer is None:
                raise errors.NotFoundError(f"Payer user {data.payer_id} not found")

            payload = {
                "payer_id": data.payer_id,
                "hostel_id": data.hostel_id,
                "student_id": data.student_id,
                "booking_id": data.booking_id,
                "payment_type": data.payment_type,
                "amount": data.amount,
                "currency": data.currency,
                "payment_period_start": data.payment_period_start,
                "payment_period_end": data.payment_period_end,
                "payment_method": data.payment_method,
                "payment_gateway": data.payment_gateway,
                "payment_status": PaymentStatus.PENDING,
                "transaction_id": data.transaction_id,
                "due_date": data.due_date,
            }
            p = pay_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            student_name = None
            if p.student_id:
                st = student_repo.get(p.student_id)
                if st and getattr(st, "user", None):
                    student_name = st.user.full_name

            return self._to_detail(
                p,
                payer_name=payer.full_name,
                payer_email=payer.email,
                payer_phone=getattr(payer, "phone", ""),
                hostel_name=hostel.name,
                student_name=student_name,
                booking_reference=None,
                collected_by_name=None,
            )

    def update_payment(
        self,
        payment_id: UUID,
        data: PaymentUpdate,
    ) -> PaymentDetail:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)

            p = pay_repo.get(payment_id)
            if p is None:
                raise errors.NotFoundError(f"Payment {payment_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(p, field) and field != "id":
                    setattr(p, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self.get_payment(payment_id)

    # ------------------------------------------------------------------ #
    # Listing & filters
    # ------------------------------------------------------------------ #
    def list_payments(
        self,
        params: PaginationParams,
        filters: Optional[PaymentFilterParams] = None,
    ) -> PaginatedResponse[PaymentListItem]:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                elif filters.hostel_ids:
                    raw_filters["hostel_id"] = filters.hostel_ids
                if filters.student_id:
                    raw_filters["student_id"] = filters.student_id
                if filters.payer_id:
                    raw_filters["payer_id"] = filters.payer_id
                if filters.payment_type:
                    raw_filters["payment_type"] = filters.payment_type
                elif filters.payment_types:
                    raw_filters["payment_type"] = filters.payment_types
                if filters.payment_method:
                    raw_filters["payment_method"] = filters.payment_method
                elif filters.payment_methods:
                    raw_filters["payment_method"] = filters.payment_methods
                if filters.payment_status:
                    raw_filters["payment_status"] = filters.payment_status
                elif filters.payment_statuses:
                    raw_filters["payment_status"] = filters.payment_statuses
                if filters.payment_gateway:
                    raw_filters["payment_gateway"] = filters.payment_gateway

            records: Sequence = pay_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
                order_by=[pay_repo.model.created_at.desc()],  # type: ignore[attr-defined]
            )

            def _matches_advanced(p) -> bool:
                if not filters:
                    return True

                # Amount range
                if filters.amount_min is not None and p.amount < filters.amount_min:
                    return False
                if filters.amount_max is not None and p.amount > filters.amount_max:
                    return False

                # Paid date range
                if filters.paid_date_from or filters.paid_date_to:
                    if not p.paid_at:
                        return False
                    d = p.paid_at.date()
                    if filters.paid_date_from and d < filters.paid_date_from:
                        return False
                    if filters.paid_date_to and d > filters.paid_date_to:
                        return False

                # Due date range
                if filters.due_date_from or filters.due_date_to:
                    if not p.due_date:
                        return False
                    d = p.due_date
                    if filters.due_date_from and d < filters.due_date_from:
                        return False
                    if filters.due_date_to and d > filters.due_date_to:
                        return False

                # Created date range
                if filters.created_date_from or filters.created_date_to:
                    d = p.created_at.date()
                    if filters.created_date_from and d < filters.created_date_from:
                        return False
                    if filters.created_date_to and d > filters.created_date_to:
                        return False

                # Overdue
                if filters.overdue_only:
                    if not self._is_overdue(p):
                        return False

                return True

            filtered = [p for p in records if _matches_advanced(p)]

            # Text search requires payer / hostel names or transaction_id
            if filters and filters.search:
                q = filters.search.lower()
                user_cache: Dict[UUID, str] = {}
                hostel_cache: Dict[UUID, str] = {}
                tmp: List = []
                for p in filtered:
                    if p.payer_id not in user_cache:
                        u = user_repo.get(p.payer_id)
                        user_cache[p.payer_id] = u.full_name if u else ""
                    if p.hostel_id not in hostel_cache:
                        h = hostel_repo.get(p.hostel_id)
                        hostel_cache[p.hostel_id] = h.name if h else ""

                    haystack = " ".join(
                        [
                            str(p.id),
                            p.transaction_id or "",
                            user_cache[p.payer_id],
                            hostel_cache[p.hostel_id],
                        ]
                    ).lower()
                    if q in haystack:
                        tmp.append(p)
                filtered = tmp

            total = len(filtered)
            start = params.offset
            end = start + params.limit
            page_records = filtered[start:end]

            user_cache: Dict[UUID, str] = {}
            hostel_cache: Dict[UUID, str] = {}

            items: List[PaymentListItem] = []
            for p in page_records:
                if p.payer_id not in user_cache:
                    u = user_repo.get(p.payer_id)
                    user_cache[p.payer_id] = u.full_name if u else ""
                if p.hostel_id not in hostel_cache:
                    h = hostel_repo.get(p.hostel_id)
                    hostel_cache[p.hostel_id] = h.name if h else ""
                items.append(
                    self._to_list_item(
                        p,
                        payer_name=user_cache[p.payer_id],
                        hostel_name=hostel_cache[p.hostel_id],
                    )
                )

            return PaginatedResponse[PaymentListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    def search_payments(
        self,
        params: PaginationParams,
        req: PaymentSearchRequest,
    ) -> PaginatedResponse[PaymentListItem]:
        """
        Simple search on reference/payer_name/transaction_id within a hostel.
        """
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            filters: Dict[str, object] = {}
            if req.hostel_id:
                filters["hostel_id"] = req.hostel_id
            if req.payment_status:
                filters["payment_status"] = req.payment_status

            records: Sequence = pay_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

            q = req.query.lower()
            user_cache: Dict[UUID, str] = {}
            hostel_cache: Dict[UUID, str] = {}

            def _matches(p) -> bool:
                if p.payer_id not in user_cache:
                    u = user_repo.get(p.payer_id)
                    user_cache[p.payer_id] = u.full_name if u else ""
                if p.hostel_id not in hostel_cache:
                    h = hostel_repo.get(p.hostel_id)
                    hostel_cache[p.hostel_id] = h.name if h else ""

                terms: List[str] = []
                if req.search_in_reference:
                    terms.append(str(p.id))
                if req.search_in_payer_name:
                    terms.append(user_cache[p.payer_id])
                if req.search_in_transaction_id and p.transaction_id:
                    terms.append(p.transaction_id)

                text = " ".join(terms).lower()
                return q in text

            matched = [p for p in records if _matches(p)]

            def _sort_key(p) -> datetime:
                return p.paid_at or p.created_at

            matched_sorted = sorted(matched, key=_sort_key, reverse=True)
            start = params.offset
            end = start + params.limit
            page_records = matched_sorted[start:end]

            items: List[PaymentListItem] = []
            for p in page_records:
                items.append(
                    self._to_list_item(
                        p,
                        payer_name=user_cache[p.payer_id],
                        hostel_name=hostel_cache[p.hostel_id],
                    )
                )

            return PaginatedResponse[PaymentListItem].create(
                items=items,
                total_items=len(matched_sorted),
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Summaries
    # ------------------------------------------------------------------ #
    def get_summary_for_student(self, student_id: UUID) -> PaymentSummary:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)

            records = pay_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"student_id": student_id},
            )

        total_paid = Decimal("0")
        total_pending = Decimal("0")
        total_overdue = Decimal("0")
        last_payment_date: Optional[date] = None
        last_payment_amount: Optional[Decimal] = None
        next_payment_due_date: Optional[date] = None
        next_payment_amount: Optional[Decimal] = None

        completed = pending = 0

        for p in records:
            if p.payment_status == PaymentStatus.COMPLETED and p.paid_at:
                total_paid += p.amount
                completed += 1
                d = p.paid_at.date()
                if not last_payment_date or d > last_payment_date:
                    last_payment_date = d
                    last_payment_amount = p.amount
            elif p.payment_status == PaymentStatus.PENDING:
                total_pending += p.amount
                pending += 1
                if self._is_overdue(p):
                    total_overdue += p.amount
                if p.due_date:
                    if not next_payment_due_date or p.due_date < next_payment_due_date:
                        next_payment_due_date = p.due_date
                        next_payment_amount = p.amount

        return PaymentSummary(
            entity_id=student_id,
            entity_type="student",
            total_paid=total_paid,
            total_pending=total_pending,
            total_overdue=total_overdue,
            last_payment_date=last_payment_date,
            last_payment_amount=last_payment_amount,
            next_payment_due_date=next_payment_due_date,
            next_payment_amount=next_payment_amount,
            total_payments=len(records),
            completed_payments=completed,
            pending_payments=pending,
        )

    def get_summary_for_hostel(self, hostel_id: UUID) -> PaymentSummary:
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)

            records = pay_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

        total_paid = Decimal("0")
        total_pending = Decimal("0")
        total_overdue = Decimal("0")
        last_payment_date: Optional[date] = None
        last_payment_amount: Optional[Decimal] = None
        next_payment_due_date: Optional[date] = None
        next_payment_amount: Optional[Decimal] = None

        completed = pending = 0

        for p in records:
            if p.payment_status == PaymentStatus.COMPLETED and p.paid_at:
                total_paid += p.amount
                completed += 1
                d = p.paid_at.date()
                if not last_payment_date or d > last_payment_date:
                    last_payment_date = d
                    last_payment_amount = p.amount
            elif p.payment_status == PaymentStatus.PENDING:
                total_pending += p.amount
                pending += 1
                if self._is_overdue(p):
                    total_overdue += p.amount
                if p.due_date:
                    if not next_payment_due_date or p.due_date < next_payment_due_date:
                        next_payment_due_date = p.due_date
                        next_payment_amount = p.amount

        return PaymentSummary(
            entity_id=hostel_id,
            entity_type="hostel",
            total_paid=total_paid,
            total_pending=total_pending,
            total_overdue=total_overdue,
            last_payment_date=last_payment_date,
            last_payment_amount=last_payment_amount,
            next_payment_due_date=next_payment_due_date,
            next_payment_amount=next_payment_amount,
            total_payments=len(records),
            completed_payments=completed,
            pending_payments=pending,
        )