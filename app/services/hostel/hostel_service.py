# app/services/hostel/hostel_service.py
from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.hostel import (
    HostelCreate,
    HostelUpdate,
    HostelResponse,
    HostelDetail,
    HostelListItem,
    HostelFilterParams,
    HostelSortOptions,
    HostelVisibilityUpdate,
    HostelStatusUpdate,
)
from app.services.common import UnitOfWork, mapping, pagination, errors


class HostelService:
    """
    Core Hostel service:

    - Create, update, retrieve hostels
    - List hostels with filters (admin side)
    - Change visibility and operational status
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def get_hostel(self, hostel_id: UUID) -> HostelDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)
            hostel = repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")
            return mapping.to_schema(hostel, HostelDetail)

    def get_hostel_by_slug(self, slug: str) -> HostelDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)
            hostel = repo.get_by_slug(slug)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel with slug {slug!r} not found")
            return mapping.to_schema(hostel, HostelDetail)

    # ------------------------------------------------------------------ #
    # Listing for admin (internal use)
    # ------------------------------------------------------------------ #
    def list_hostels(
        self,
        params: PaginationParams,
        filters: Optional[HostelFilterParams] = None,
        sort: Optional[HostelSortOptions] = None,
    ) -> PaginatedResponse[HostelListItem]:
        """
        List hostels with filters and sorting for admin views.

        Note: HostelRepository already has a list_public() helper for
        visitor-facing searches; this listing is more general for admins.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)

            raw_filters = {}
            if filters:
                if filters.city:
                    raw_filters["city"] = filters.city
                if filters.state:
                    raw_filters["state"] = filters.state
                if filters.status is not None:
                    raw_filters["status"] = filters.status
                if filters.is_active is not None:
                    raw_filters["is_active"] = filters.is_active
                if filters.is_public is not None:
                    raw_filters["is_public"] = filters.is_public
                if filters.is_featured is not None:
                    raw_filters["is_featured"] = filters.is_featured
                if filters.is_verified is not None:
                    raw_filters["is_verified"] = filters.is_verified

            # Sorting
            order_by = None
            if sort:
                col_map = {
                    "name": repo.model.name,          # type: ignore[attr-defined]
                    "city": repo.model.city,          # type: ignore[attr-defined]
                    "price": repo.model.starting_price_monthly,  # type: ignore[attr-defined]
                    "rating": repo.model.average_rating,         # type: ignore[attr-defined]
                    "occupancy": repo.model.occupied_beds,       # type: ignore[attr-defined]
                    "created_at": repo.model.created_at,         # type: ignore[attr-defined]
                    "updated_at": repo.model.updated_at,         # type: ignore[attr-defined]
                }
                sort_col = col_map.get(sort.sort_by, repo.model.created_at)  # type: ignore[attr-defined]
                order_by = [sort_col.asc() if sort.sort_order == "asc" else sort_col.desc()]

            records = repo.get_multi(
                skip=params.offset,
                limit=params.limit,
                filters=raw_filters or None,
                order_by=order_by,
            )
            total = repo.count(filters=raw_filters or None)

            return pagination.paginate(
                items=records,
                total_items=total,
                params=params,
                mapper=lambda h: mapping.to_schema(h, HostelListItem),
            )

    # ------------------------------------------------------------------ #
    # Creation
    # ------------------------------------------------------------------ #
    def create_hostel(self, data: HostelCreate) -> HostelDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)

            # Ensure slug uniqueness
            existing = repo.get_by_slug(data.slug)
            if existing is not None:
                raise errors.ConflictError(f"Hostel slug {data.slug!r} is already in use")

            hostel = repo.create(data.model_dump())
            uow.commit()
            return mapping.to_schema(hostel, HostelDetail)

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update_hostel(self, hostel_id: UUID, data: HostelUpdate) -> HostelDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)
            hostel = repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            # Slug change uniqueness check
            if data.slug is not None and data.slug != hostel.slug:
                if repo.get_by_slug(data.slug):
                    raise errors.ConflictError(
                        f"Hostel slug {data.slug!r} is already in use"
                    )

            mapping.update_model_from_schema(hostel, data, exclude_fields=["id"])
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return mapping.to_schema(hostel, HostelDetail)

    # ------------------------------------------------------------------ #
    # Visibility & status
    # ------------------------------------------------------------------ #
    def update_visibility(
        self,
        hostel_id: UUID,
        data: HostelVisibilityUpdate,
    ) -> HostelResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)
            hostel = repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            hostel.is_public = data.is_public  # type: ignore[attr-defined]
            hostel.is_featured = data.is_featured  # type: ignore[attr-defined]
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return mapping.to_schema(hostel, HostelResponse)

    def update_status(
        self,
        hostel_id: UUID,
        data: HostelStatusUpdate,
    ) -> HostelResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_hostel_repo(uow)
            hostel = repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            hostel.status = data.status  # type: ignore[attr-defined]
            hostel.is_active = data.is_active  # type: ignore[attr-defined]
            # Optionally store reason somewhere (e.g., audit log)
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return mapping.to_schema(hostel, HostelResponse)