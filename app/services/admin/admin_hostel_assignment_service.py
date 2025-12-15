# app/services/admin/admin_hostel_assignment_service.py
from __future__ import annotations

from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.associations import AdminHostelRepository
from app.repositories.core import AdminRepository, HostelRepository, UserRepository
from app.schemas.admin import (
    AdminHostelAssignment,
    AssignmentCreate,
    AssignmentUpdate,
    BulkAssignment,
    AssignmentList,
    HostelAdminList,
    HostelAdminItem,
)
from app.services.common import UnitOfWork, errors


class AdminHostelAssignmentService:
    """
    Manage admin ↔ hostel assignments.

    - Assign an admin to a hostel
    - Update assignment (permissions / primary flag / active flag)
    - Bulk assign an admin to multiple hostels
    - Revoke assignment
    - List assignments for an admin
    - List admins for a hostel
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_admin_hostel_repo(self, uow: UnitOfWork) -> AdminHostelRepository:
        return uow.get_repo(AdminHostelRepository)

    def _get_admin_repo(self, uow: UnitOfWork) -> AdminRepository:
        return uow.get_repo(AdminRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _build_assignment_schema(
        self,
        assoc,
        *,
        admin_name: str,
        admin_email: str,
        hostel_name: str,
        hostel_city: str,
        assigned_by: Optional[UUID] = None,
        assigned_by_name: Optional[str] = None,
    ) -> AdminHostelAssignment:
        return AdminHostelAssignment(
            id=assoc.id,
            created_at=assoc.created_at,
            updated_at=assoc.updated_at,
            admin_id=assoc.admin_id,
            admin_name=admin_name,
            admin_email=admin_email,
            hostel_id=assoc.hostel_id,
            hostel_name=hostel_name,
            hostel_city=hostel_city,
            assigned_by=assigned_by,
            assigned_by_name=assigned_by_name,
            assigned_date=assoc.assigned_date,
            permission_level=assoc.permission_level,
            permissions=assoc.permissions or {},
            is_active=assoc.is_active,
            is_primary=assoc.is_primary,
            revoked_date=assoc.revoked_date,
            revoked_by=None,
            revoke_reason=assoc.revoke_reason,
        )

    # ------------------------------------------------------------------ #
    # Create / update / revoke
    # ------------------------------------------------------------------ #
    def assign_hostel(
        self,
        data: AssignmentCreate,
        *,
        assigned_by: Optional[UUID] = None,
    ) -> AdminHostelAssignment:
        """
        Assign an admin to a hostel.

        NOTE:
        - `data.admin_id` is expected to be the core_admin.id (Admin model PK).
        """
        with UnitOfWork(self._session_factory) as uow:
            admin_hostel_repo = self._get_admin_hostel_repo(uow)
            admin_repo = self._get_admin_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            admin = admin_repo.get(data.admin_id)
            if admin is None:
                raise errors.NotFoundError(f"Admin {data.admin_id} not found")

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            # Prevent duplicate assignment (regardless of active flag)
            existing = admin_hostel_repo.get_multi(
                skip=0,
                limit=1,
                filters={"admin_id": data.admin_id, "hostel_id": data.hostel_id},
            )
            if existing:
                raise errors.ConflictError(
                    "Admin is already assigned to this hostel"
                )

            # If this is primary, clear other primary flags for this admin
            if data.is_primary:
                admin_hostel_repo.bulk_update(
                    filters={"admin_id": data.admin_id},
                    values={"is_primary": False},
                )

            payload = {
                "admin_id": data.admin_id,
                "hostel_id": data.hostel_id,
                "permission_level": data.permission_level,
                "permissions": data.permissions or {},
                "is_primary": data.is_primary,
                "is_active": True,
            }
            assoc = admin_hostel_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            admin_user = admin.user if getattr(admin, "user", None) else None
            admin_name = admin_user.full_name if admin_user else ""
            admin_email = admin_user.email if admin_user else ""

            assigned_by_name = None
            if assigned_by:
                assigned_by_user = user_repo.get(assigned_by)
                assigned_by_name = (
                    assigned_by_user.full_name if assigned_by_user else None
                )

            return self._build_assignment_schema(
                assoc,
                admin_name=admin_name,
                admin_email=admin_email,
                hostel_name=hostel.name,
                hostel_city=hostel.city,
                assigned_by=assigned_by,
                assigned_by_name=assigned_by_name,
            )

    def update_assignment(
        self,
        assignment_id: UUID,
        data: AssignmentUpdate,
    ) -> AdminHostelAssignment:
        """Update permission level / permissions / primary / active flags."""
        with UnitOfWork(self._session_factory) as uow:
            admin_hostel_repo = self._get_admin_hostel_repo(uow)
            admin_repo = self._get_admin_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            assoc = admin_hostel_repo.get(assignment_id)
            if assoc is None:
                raise errors.NotFoundError(f"Assignment {assignment_id} not found")

            if data.permission_level is not None:
                assoc.permission_level = data.permission_level  # type: ignore[attr-defined]
            if data.permissions is not None:
                assoc.permissions = data.permissions  # type: ignore[attr-defined]
            if data.is_active is not None:
                assoc.is_active = data.is_active  # type: ignore[attr-defined]

            if data.is_primary is not None:
                if data.is_primary:
                    # Clear other primary flags for this admin
                    admin_hostel_repo.bulk_update(
                        filters={"admin_id": assoc.admin_id},
                        values={"is_primary": False},
                    )
                assoc.is_primary = data.is_primary  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            admin = admin_repo.get(assoc.admin_id)
            hostel = hostel_repo.get(assoc.hostel_id)
            admin_user = admin.user if admin and getattr(admin, "user", None) else None

            return self._build_assignment_schema(
                assoc,
                admin_name=admin_user.full_name if admin_user else "",
                admin_email=admin_user.email if admin_user else "",
                hostel_name=hostel.name if hostel else "",
                hostel_city=hostel.city if hostel else "",
            )

    def revoke_assignment(
        self,
        assignment_id: UUID,
        *,
        revoke_reason: str,
        revoked_by: Optional[UUID] = None,
    ) -> AdminHostelAssignment:
        """
        Soft-revoke an assignment (set inactive, set revoked_date + reason).
        """
        from datetime import date as _date

        with UnitOfWork(self._session_factory) as uow:
            admin_hostel_repo = self._get_admin_hostel_repo(uow)
            admin_repo = self._get_admin_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            assoc = admin_hostel_repo.get(assignment_id)
            if assoc is None:
                raise errors.NotFoundError(f"Assignment {assignment_id} not found")

            assoc.is_active = False  # type: ignore[attr-defined]
            assoc.revoked_date = _date.today()  # type: ignore[attr-defined]
            assoc.revoke_reason = revoke_reason  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            admin = admin_repo.get(assoc.admin_id)
            hostel = hostel_repo.get(assoc.hostel_id)
            admin_user = admin.user if admin and getattr(admin, "user", None) else None

            return self._build_assignment_schema(
                assoc,
                admin_name=admin_user.full_name if admin_user else "",
                admin_email=admin_user.email if admin_user else "",
                hostel_name=hostel.name if hostel else "",
                hostel_city=hostel.city if hostel else "",
                assigned_by=None,
                assigned_by_name=None,
            )

    def bulk_assign(
        self,
        data: BulkAssignment,
        *,
        assigned_by: Optional[UUID] = None,
    ) -> List[AdminHostelAssignment]:
        """
        Assign the same admin to multiple hostels.
        """
        responses: List[AdminHostelAssignment] = []
        primary_hostel_id = data.primary_hostel_id

        for hid in data.hostel_ids:
            is_primary = primary_hostel_id is not None and hid == primary_hostel_id
            req = AssignmentCreate(
                admin_id=data.admin_id,
                hostel_id=hid,
                permission_level=data.permission_level,
                permissions=data.permissions,
                is_primary=is_primary,
            )
            responses.append(self.assign_hostel(req, assigned_by=assigned_by))
        return responses

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_assignments_for_admin(self, admin_id: UUID) -> AssignmentList:
        """
        List all hostel assignments for a given admin (core_admin.id).
        """
        with UnitOfWork(self._session_factory) as uow:
            admin_hostel_repo = self._get_admin_hostel_repo(uow)
            admin_repo = self._get_admin_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            admin = admin_repo.get(admin_id)
            if admin is None:
                raise errors.NotFoundError(f"Admin {admin_id} not found")

            admin_user = admin.user if getattr(admin, "user", None) else None
            admin_name = admin_user.full_name if admin_user else ""

            records = admin_hostel_repo.get_multi(
                skip=0,
                limit=0,  # no explicit limit
                filters={"admin_id": admin_id},
            )

            total_hostels = len(records)
            active_hostels = sum(1 for r in records if r.is_active)
            primary_hostel_id: Optional[UUID] = None
            items: List[AdminHostelAssignment] = []

            for assoc in records:
                hostel = hostel_repo.get(assoc.hostel_id)
                if assoc.is_primary:
                    primary_hostel_id = assoc.hostel_id
                items.append(
                    self._build_assignment_schema(
                        assoc,
                        admin_name=admin_name,
                        admin_email=admin_user.email if admin_user else "",
                        hostel_name=hostel.name if hostel else "",
                        hostel_city=hostel.city if hostel else "",
                    )
                )

            return AssignmentList(
                admin_id=admin_id,
                admin_name=admin_name,
                total_hostels=total_hostels,
                active_hostels=active_hostels,
                primary_hostel_id=primary_hostel_id,
                assignments=items,
            )

    def list_admins_for_hostel(self, hostel_id: UUID) -> HostelAdminList:
        """
        List all admins assigned to a hostel.
        """
        with UnitOfWork(self._session_factory) as uow:
            admin_hostel_repo = self._get_admin_hostel_repo(uow)
            admin_repo = self._get_admin_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            records = admin_hostel_repo.get_multi(
                skip=0,
                limit=0,
                filters={"hostel_id": hostel_id},
            )

            total_admins = len(records)
            admins: List[HostelAdminItem] = []

            for assoc in records:
                admin = admin_repo.get(assoc.admin_id)
                admin_user = (
                    admin.user if admin and getattr(admin, "user", None) else None
                )
                admins.append(
                    HostelAdminItem(
                        admin_id=assoc.admin_id,
                        admin_name=admin_user.full_name if admin_user else "",
                        admin_email=admin_user.email if admin_user else "",
                        permission_level=assoc.permission_level,
                        is_primary=assoc.is_primary,
                        assigned_date=assoc.assigned_date,
                        last_active=assoc.last_active,
                    )
                )

            return HostelAdminList(
                hostel_id=hostel_id,
                hostel_name=hostel.name,
                total_admins=total_admins,
                admins=admins,
            )