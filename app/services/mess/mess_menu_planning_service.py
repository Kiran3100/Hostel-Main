# app/services/mess/mess_menu_planning_service.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import MessMenuRepository
from app.repositories.core import HostelRepository
from app.schemas.common.base import BaseSchema  # only for typing hints if needed
from app.schemas.mess.menu_duplication import (
    DuplicateMenuRequest,
    BulkMenuCreate,
    DuplicateResponse,
)
from app.services.common import UnitOfWork, errors


class MessMenuPlanningService:
    """
    Menu planning & duplication helpers:

    - Duplicate a single menu to another date
    - Bulk-create menus for a date range using an existing menu or pattern
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_menu_repo(self, uow: UnitOfWork) -> MessMenuRepository:
        return uow.get_repo(MessMenuRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Single duplication
    # ------------------------------------------------------------------ #
    def duplicate_menu(self, req: DuplicateMenuRequest) -> DuplicateResponse:
        """
        Duplicate a single menu to a target_date.

        - If a menu already exists on target_date for that hostel,
          raises ConflictError (no override here).
        - If `modifications` is provided, it should be a partial dict of
          MessMenu fields (e.g. breakfast_items, lunch_items, etc.).
        """
        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)

            src = menu_repo.get(req.source_menu_id)
            if src is None:
                raise errors.NotFoundError(f"MessMenu {req.source_menu_id} not found")

            existing = menu_repo.get_for_date(src.hostel_id, req.target_date)
            if existing:
                raise errors.ConflictError(
                    f"Menu already exists for {req.target_date} at this hostel"
                )

            payload = {
                "hostel_id": src.hostel_id,
                "menu_date": req.target_date,
                "day_of_week": req.target_date.strftime("%A"),
                "breakfast_items": list(src.breakfast_items or []),
                "lunch_items": list(src.lunch_items or []),
                "snacks_items": list(src.snacks_items or []),
                "dinner_items": list(src.dinner_items or []),
                "breakfast_time": src.breakfast_time,
                "lunch_time": src.lunch_time,
                "snacks_time": src.snacks_time,
                "dinner_time": src.dinner_time,
                "is_special_menu": src.is_special_menu,
                "special_occasion": src.special_occasion,
                "vegetarian_available": src.vegetarian_available,
                "non_vegetarian_available": src.non_vegetarian_available,
                "vegan_available": src.vegan_available,
                "jain_available": src.jain_available,
            }

            if req.modify_items and req.modifications:
                for field, value in req.modifications.items():
                    if field in payload:
                        payload[field] = value

            created = menu_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            return DuplicateResponse(
                source_menu_id=req.source_menu_id,
                created_menus=[created.id],
                total_created=1,
                skipped=0,
                message="Menu duplicated successfully",
            )

    # ------------------------------------------------------------------ #
    # Bulk creation
    # ------------------------------------------------------------------ #
    def bulk_create_menus(self, req: BulkMenuCreate) -> DuplicateResponse:
        """
        Create menus for a date range based on a source menu or weekly pattern.

        Supported source_type values:
        - 'existing_menu': use `source_menu_id` as template.
        - 'weekly_pattern': use `weekly_pattern` dict:
              { "monday": {...}, "tuesday": {...}, ... }
          where each value is a partial MessMenu payload, e.g.:
              {
                  "breakfast_items": [...],
                  "lunch_items": [...],
                  "snacks_items": [...],
                  "dinner_items": [...]
              }

        NOTE:
        - 'template' source_type is not implemented in this skeleton
          (no MenuTemplate persistence defined yet).
        """
        if req.start_date > req.end_date:
            raise errors.ValidationError("start_date must be <= end_date")

        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(req.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {req.hostel_id} not found")

            source_menu = None
            if req.source_type == "existing_menu":
                if not req.source_menu_id:
                    raise errors.ValidationError(
                        "source_menu_id is required when source_type='existing_menu'"
                    )
                source_menu = menu_repo.get(req.source_menu_id)
                if source_menu is None:
                    raise errors.NotFoundError(
                        f"Source menu {req.source_menu_id} not found"
                    )

            if req.source_type == "template":
                # No MenuTemplate model defined in this codebase; stub.
                raise errors.ServiceError(
                    "Template-based bulk menu creation is not implemented"
                )

            created_ids: List[UUID] = []
            skipped = 0

            cur = req.start_date
            while cur <= req.end_date:
                existing = menu_repo.get_for_date(req.hostel_id, cur)
                if existing:
                    if req.override_existing:
                        # We'll override the first existing record.
                        target = existing[0]
                        self._apply_source_to_menu(
                            target,
                            source_type=req.source_type,
                            source_menu=source_menu,
                            weekly_pattern=req.weekly_pattern,
                            target_date=cur,
                        )
                        uow.session.flush()  # type: ignore[union-attr]
                        created_ids.append(target.id)
                    elif req.skip_existing:
                        skipped += 1
                    else:
                        # Neither override nor skip -> conflict
                        raise errors.ConflictError(
                            f"Menu already exists for {cur}; "
                            "set skip_existing or override_existing."
                        )
                else:
                    payload = self._build_payload_from_source(
                        hostel_id=req.hostel_id,
                        source_type=req.source_type,
                        source_menu=source_menu,
                        weekly_pattern=req.weekly_pattern,
                        target_date=cur,
                    )
                    if payload is None:
                        skipped += 1
                    else:
                        created = menu_repo.create(payload)  # type: ignore[arg-type]
                        created_ids.append(created.id)

                cur += timedelta(days=1)

            uow.commit()

        return DuplicateResponse(
            source_menu_id=req.source_menu_id or UUID(int=0),
            created_menus=created_ids,
            total_created=len(created_ids),
            skipped=skipped,
            message="Bulk menu creation completed",
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _build_payload_from_source(
        self,
        *,
        hostel_id: UUID,
        source_type: str,
        source_menu,
        weekly_pattern: dict | None,
        target_date: date,
    ) -> dict | None:
        """
        Construct a new MessMenu payload based on the given source type.
        Returns None if no data is available for the given day (for patterns).
        """
        base = {
            "hostel_id": hostel_id,
            "menu_date": target_date,
            "day_of_week": target_date.strftime("%A"),
        }

        if source_type == "existing_menu":
            if source_menu is None:
                return None
            base.update(
                {
                    "breakfast_items": list(source_menu.breakfast_items or []),
                    "lunch_items": list(source_menu.lunch_items or []),
                    "snacks_items": list(source_menu.snacks_items or []),
                    "dinner_items": list(source_menu.dinner_items or []),
                    "breakfast_time": source_menu.breakfast_time,
                    "lunch_time": source_menu.lunch_time,
                    "snacks_time": source_menu.snacks_time,
                    "dinner_time": source_menu.dinner_time,
                    "is_special_menu": source_menu.is_special_menu,
                    "special_occasion": source_menu.special_occasion,
                    "vegetarian_available": source_menu.vegetarian_available,
                    "non_vegetarian_available": source_menu.non_vegetarian_available,
                    "vegan_available": source_menu.vegan_available,
                    "jain_available": source_menu.jain_available,
                }
            )
            return base

        if source_type == "weekly_pattern":
            if not weekly_pattern:
                return None
            key = target_date.strftime("%A").lower()
            day_conf = weekly_pattern.get(key)
            if not day_conf:
                return None
            # day_conf is expected to be a partial menu dict.
            base.update(day_conf)
            return base

        # Unknown type
        return None

    def _apply_source_to_menu(
        self,
        menu_obj,
        *,
        source_type: str,
        source_menu,
        weekly_pattern: dict | None,
        target_date: date,
    ) -> None:
        """
        Apply source data to an existing MessMenu instance (for overrides).
        """
        if source_type == "existing_menu" and source_menu is not None:
            menu_obj.menu_date = target_date
            menu_obj.day_of_week = target_date.strftime("%A")
            menu_obj.breakfast_items = list(source_menu.breakfast_items or [])
            menu_obj.lunch_items = list(source_menu.lunch_items or [])
            menu_obj.snacks_items = list(source_menu.snacks_items or [])
            menu_obj.dinner_items = list(source_menu.dinner_items or [])
            menu_obj.breakfast_time = source_menu.breakfast_time
            menu_obj.lunch_time = source_menu.lunch_time
            menu_obj.snacks_time = source_menu.snacks_time
            menu_obj.dinner_time = source_menu.dinner_time
            menu_obj.is_special_menu = source_menu.is_special_menu
            menu_obj.special_occasion = source_menu.special_occasion
            menu_obj.vegetarian_available = source_menu.vegetarian_available
            menu_obj.non_vegetarian_available = source_menu.non_vegetarian_available
            menu_obj.vegan_available = source_menu.vegan_available
            menu_obj.jain_available = source_menu.jain_available
            return

        if source_type == "weekly_pattern" and weekly_pattern:
            key = target_date.strftime("%A").lower()
            day_conf = weekly_pattern.get(key)
            if not day_conf:
                return
            menu_obj.menu_date = target_date
            menu_obj.day_of_week = target_date.strftime("%A")
            for field, value in day_conf.items():
                if hasattr(menu_obj, field):
                    setattr(menu_obj, field, value)