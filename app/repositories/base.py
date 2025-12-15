# app/repositories/base.py
from __future__ import annotations

from typing import Any, Dict, Generic, Iterable, Optional, Sequence, Type, TypeVar
from uuid import UUID

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.orm import Session

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with common CRUD and query helpers.

    - Does not commit/rollback; caller manages transactions.
    - Automatically filters out soft-deleted rows if model has `is_deleted` column.
    """

    def __init__(self, session: Session, model: Type[ModelType]):
        self.session = session
        self.model = model

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _base_select(self) -> Select[tuple[ModelType]]:
        stmt = select(self.model)
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(getattr(self.model, "is_deleted").is_(False))
        return stmt

    def _apply_filters(
        self,
        stmt: Select[tuple[ModelType]],
        filters: Optional[Dict[str, Any]] = None,
    ) -> Select[tuple[ModelType]]:
        if not filters:
            return stmt

        for key, value in filters.items():
            if value is None:
                continue
            column = getattr(self.model, key, None)
            if column is None:
                continue

            if isinstance(value, (list, tuple, set)):
                stmt = stmt.where(column.in_(value))
            else:
                stmt = stmt.where(column == value)
        return stmt

    # ------------------------------------------------------------------ #
    # Basic CRUD
    # ------------------------------------------------------------------ #
    def get(self, id_: UUID) -> Optional[ModelType]:
        stmt = self._base_select().where(self.model.id == id_)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[Iterable[Any]] = None,
    ) -> Sequence[ModelType]:
        stmt = self._base_select()
        stmt = self._apply_filters(stmt, filters)

        if order_by:
            stmt = stmt.order_by(*order_by)

        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)

        return self.session.execute(stmt).scalars().all()

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        stmt = select(func.count(self.model.id))
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(getattr(self.model, "is_deleted").is_(False))
        if filters:
            for key, value in filters.items():
                if value is None:
                    continue
                column = getattr(self.model, key, None)
                if column is None:
                    continue
                if isinstance(value, (list, tuple, set)):
                    stmt = stmt.where(column.in_(value))
                else:
                    stmt = stmt.where(column == value)
        return self.session.execute(stmt).scalar_one()

    def create(self, obj_in: Dict[str, Any] | ModelType) -> ModelType:
        if isinstance(obj_in, self.model):
            db_obj = obj_in
        else:
            db_obj = self.model(**obj_in)  # type: ignore[arg-type]
        self.session.add(db_obj)
        # flush to populate PK
        self.session.flush()
        return db_obj

    def update(
        self,
        db_obj: ModelType,
        obj_in: Dict[str, Any] | ModelType,
    ) -> ModelType:
        if isinstance(obj_in, self.model):
            data = {c.name: getattr(obj_in, c.name) for c in self.model.__table__.columns}
        else:
            data = obj_in

        for field, value in data.items():
            if hasattr(db_obj, field) and field != "id":
                setattr(db_obj, field, value)

        self.session.flush()
        return db_obj

    def delete(self, db_obj: ModelType, *, hard_delete: bool = False) -> None:
        """
        Delete an object.

        - If model has `is_deleted` and `hard_delete=False`, marks as soft-deleted.
        - Otherwise performs real DELETE.
        """
        if hasattr(self.model, "is_deleted") and not hard_delete:
            setattr(db_obj, "is_deleted", True)
            if hasattr(self.model, "deleted_at"):
                from datetime import datetime, timezone

                setattr(db_obj, "deleted_at", datetime.now(timezone.utc))
            self.session.flush()
        else:
            self.session.delete(db_obj)
            self.session.flush()

    def delete_by_id(self, id_: UUID, *, hard_delete: bool = False) -> None:
        obj = self.get(id_)
        if obj:
            self.delete(obj, hard_delete=hard_delete)

    # ------------------------------------------------------------------ #
    # Bulk helpers
    # ------------------------------------------------------------------ #
    def bulk_create(self, objs: Iterable[Dict[str, Any] | ModelType]) -> Sequence[ModelType]:
        instances: list[ModelType] = []
        for obj in objs:
            if isinstance(obj, self.model):
                instances.append(obj)
            else:
                instances.append(self.model(**obj))  # type: ignore[arg-type]
        self.session.add_all(instances)
        self.session.flush()
        return instances

    def bulk_update(
        self,
        filters: Dict[str, Any],
        values: Dict[str, Any],
    ) -> int:
        stmt = update(self.model)
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(getattr(self.model, "is_deleted").is_(False))
        for key, value in filters.items():
            column = getattr(self.model, key, None)
            if column is not None:
                stmt = stmt.where(column == value)
        stmt = stmt.values(**values)
        result = self.session.execute(stmt)
        self.session.flush()
        return result.rowcount or 0

    def bulk_delete(
        self,
        filters: Dict[str, Any],
        *,
        hard_delete: bool = False,
    ) -> int:
        if hasattr(self.model, "is_deleted") and not hard_delete:
            # Soft delete
            values: Dict[str, Any] = {"is_deleted": True}
            if hasattr(self.model, "deleted_at"):
                from datetime import datetime, timezone

                values["deleted_at"] = datetime.now(timezone.utc)
            return self.bulk_update(filters, values)

        # Hard delete
        stmt = delete(self.model)
        for key, value in filters.items():
            column = getattr(self.model, key, None)
            if column is not None:
                stmt = stmt.where(column == value)
        result = self.session.execute(stmt)
        self.session.flush()
        return result.rowcount or 0