# app/services/hostel/hostel_admin_view_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository, StudentRepository
from app.repositories.transactions import (
    PaymentRepository,
    BookingRepository,
    SubscriptionRepository,
    SubscriptionPlanRepository,
)
from app.repositories.services import ComplaintRepository, MaintenanceRepository
from app.schemas.common.enums import (
    PaymentStatus,
    BookingStatus,
    StudentStatus,
    SubscriptionPlan as SubscriptionPlanEnum,
)
from app.schemas.hostel import HostelAdminView, HostelSettings
from app.services.common import UnitOfWork, errors


class HostelSettingsStore(Protocol):
    """
    Abstract storage for per-hostel admin settings.

    Implementations can use a dedicated DB table, Redis, etc.
    """

    def get_settings(self, hostel_id: UUID) -> Optional[dict]: ...
    def save_settings(self, hostel_id: UUID, data: dict) -> None: ...


class HostelAdminViewService:
    """
    Admin-facing hostel dashboard service.

    - Build HostelAdminView (aggregated stats & status)
    - Get/update HostelSettings (config; store-backed)
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        settings_store: Optional[HostelSettingsStore] = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings_store = settings_store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_booking_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    def _get_complaint_repo(self, uow: UnitOfWork) -> ComplaintRepository:
        return uow.get_repo(ComplaintRepository)

    def _get_maintenance_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def _get_sub_repo(self, uow: UnitOfWork) -> SubscriptionRepository:
        return uow.get_repo(SubscriptionRepository)

    def _get_plan_repo(self, uow: UnitOfWork) -> SubscriptionPlanRepository:
        return uow.get_repo(SubscriptionPlanRepository)

    def _today(self) -> date:
        return date.today()

    # ------------------------------------------------------------------ #
    # Admin view
    # ------------------------------------------------------------------ #
    def get_admin_view(self, hostel_id: UUID) -> HostelAdminView:
        """
        Build a single HostelAdminView for admin dashboard.

        Aggregates:
        - Capacity & occupancy
        - Student counts
        - Financial (this month's revenue, outstanding)
        - Pending bookings/complaints/maintenance
        - Subscription plan & expiry
        - Ratings & reviews
        """
        today = self._today()

        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            payment_repo = self._get_payment_repo(uow)
            booking_repo = self._get_booking_repo(uow)
            complaint_repo = self._get_complaint_repo(uow)
            maintenance_repo = self._get_maintenance_repo(uow)
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            # Capacity & occupancy
            total_rooms = hostel.total_rooms or 0
            total_beds = hostel.total_beds or 0
            occupied_beds = hostel.occupied_beds or 0
            available_beds = max(0, total_beds - occupied_beds)
            occupancy_percentage = (
                Decimal(str(occupied_beds / total_beds * 100))
                if total_beds > 0
                else Decimal("0")
            )

            # Students
            students = student_repo.list_for_hostel(hostel_id, status=None)
            total_students = len(students)
            active_students = sum(
                1
                for s in students
                if s.student_status == StudentStatus.ACTIVE
            )

            # Financial: this month's revenue + outstanding
            payments = payment_repo.get_multi(filters={"hostel_id": hostel_id})
            total_revenue_this_month = Decimal("0")
            outstanding_payments = Decimal("0")
            for p in payments:
                if (
                    p.payment_status == PaymentStatus.COMPLETED
                    and p.paid_at is not None
                ):
                    paid_date = p.paid_at.date()
                    if paid_date.year == today.year and paid_date.month == today.month:
                        total_revenue_this_month += p.amount
                if p.payment_status == PaymentStatus.PENDING:
                    outstanding_payments += p.amount

            # Pending items
            pending_bookings = len(
                booking_repo.list_pending_for_hostel(hostel_id)
            )
            pending_complaints = len(
                complaint_repo.list_open_for_hostel(
                    hostel_id,
                    category=None,
                    priority=None,
                )
            )
            pending_maintenance = len(
                maintenance_repo.list_open_for_hostel(
                    hostel_id,
                    category=None,
                    priority=None,
                )
            )

            # Subscription
            active_sub = sub_repo.get_active_for_hostel(hostel_id, as_of=today)
            subscription_plan: Optional[SubscriptionPlanEnum] = None
            subscription_expires_at = None
            if active_sub:
                plan = plan_repo.get(active_sub.plan_id)
                if plan:
                    subscription_plan = plan.plan_type
                subscription_expires_at = active_sub.end_date

            # Ratings/reviews from hostel snapshot
            avg_rating = Decimal(str(hostel.average_rating or 0.0))
            total_reviews = hostel.total_reviews or 0

            return HostelAdminView(
                id=hostel.id,
                name=hostel.name,
                slug=hostel.slug,
                status=hostel.status,
                is_active=hostel.is_active,
                is_public=hostel.is_public,
                is_featured=hostel.is_featured,
                is_verified=hostel.is_verified,
                total_rooms=total_rooms,
                total_beds=total_beds,
                occupied_beds=occupied_beds,
                available_beds=available_beds,
                occupancy_percentage=occupancy_percentage,
                total_students=total_students,
                active_students=active_students,
                total_revenue_this_month=total_revenue_this_month,
                outstanding_payments=outstanding_payments,
                pending_bookings=pending_bookings,
                pending_complaints=pending_complaints,
                pending_maintenance=pending_maintenance,
                subscription_plan=subscription_plan,
                subscription_expires_at=subscription_expires_at,
                average_rating=avg_rating,
                total_reviews=total_reviews,
            )

    # ------------------------------------------------------------------ #
    # Settings (optional; store-backed)
    # ------------------------------------------------------------------ #
    def get_settings(self, hostel_id: UUID) -> HostelSettings:
        """
        Retrieve settings for a hostel, creating defaults if none exist.

        Requires a HostelSettingsStore to be configured.
        """
        if not self._settings_store:
            # If no store is wired, return defaults (not persisted)
            return HostelSettings()

        record = self._settings_store.get_settings(hostel_id)
        if record:
            return HostelSettings.model_validate(record)

        # Create default settings and persist
        settings = HostelSettings()
        self._settings_store.save_settings(hostel_id, settings.model_dump())
        return settings

    def update_settings(
        self,
        hostel_id: UUID,
        data: HostelSettings,
    ) -> HostelSettings:
        """
        Update and persist settings for a hostel.

        Requires a HostelSettingsStore.
        """
        if not self._settings_store:
            raise errors.ServiceError(
                "HostelSettingsStore is not configured for HostelAdminViewService"
            )

        current = self.get_settings(hostel_id)
        update_data = data.model_dump(exclude_unset=True)
        new_settings = current.model_copy(update=update_data)
        self._settings_store.save_settings(hostel_id, new_settings.model_dump())
        return new_settings