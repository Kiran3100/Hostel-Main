# app/services/analytics/custom_report_service.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Type
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.repositories.transactions import PaymentRepository, BookingRepository
from app.repositories.services import ComplaintRepository, AttendanceRepository
from app.schemas.analytics.custom_reports import (
    CustomReportRequest,
    CustomReportDefinition,
    CustomReportResult,
    CustomReportField,
    CustomReportFilter,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork


class CustomReportService:
    """
    Very lightweight custom report builder.

    Supported modules (initially):
    - 'payments'  -> txn_payment via PaymentRepository
    - 'bookings'  -> txn_booking via BookingRepository
    - 'complaints'-> svc_complaint via ComplaintRepository
    - 'attendance'-> svc_attendance via AttendanceRepository

    NOTE:
    - This is intentionally conservative: it loads rows via repositories and
      applies filters/aggregations in Python. For large datasets, consider a
      dedicated reporting DB / ETL.
    """

    _MODULE_REPOS: Dict[str, Type[BaseRepository]] = {
        "payments": PaymentRepository,
        "bookings": BookingRepository,
        "complaints": ComplaintRepository,
        "attendance": AttendanceRepository,
    }

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run_report(self, req: CustomReportRequest) -> CustomReportResult:
        """
        Execute a custom report request and return tabular data + summary.
        """
        module = req.module.lower()
        if module not in self._MODULE_REPOS:
            raise ValueError(f"Unsupported module {module!r} for custom reports")

        with UnitOfWork(self._session_factory) as uow:
            repo_cls = self._MODULE_REPOS[module]
            repo: BaseRepository = uow.get_repo(repo_cls)  # type: ignore[type-arg]

            # For simplicity, fetch all rows that match rough period filters via repo,
            # then refine in Python.
            base_filters: Dict[str, Any] = {}
            objs = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=base_filters or None,
            )

        # Apply time period filter (if any) on created_at where available
        objs = list(self._apply_period_filter(objs, req.period))

        # Apply custom filters in Python
        objs = list(self._apply_filters(objs, req.filters or []))

        # Map to rows (dict) according to fields
        rows: List[Dict[str, Any]] = self._build_rows(objs, req.fields)

        # Perform simple aggregations for summary
        summary = self._build_summary(rows, req.fields)

        return CustomReportResult(
            report_id=None,
            report_name=req.report_name,
            generated_at=datetime.utcnow(),
            rows=rows,
            total_rows=len(rows),
            summary=summary if req.include_summary else None,
            charts=None,  # Can be filled by higher-level code if needed
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _apply_period_filter(
        self,
        objs: Iterable[Any],
        period: Optional[DateRangeFilter],
    ) -> Iterable[Any]:
        if not period or (not period.start_date and not period.end_date):
            return objs

        start = period.start_date or date.min
        end = period.end_date or date.max

        for obj in objs:
            created = getattr(obj, "created_at", None)
            if not created or not isinstance(created, datetime):
                yield obj  # if no created_at, keep it
                continue
            d = created.date()
            if d < start or d > end:
                continue
            yield obj

    def _apply_filters(
        self,
        objs: Iterable[Any],
        filters: List[CustomReportFilter],
    ) -> Iterable[Any]:
        def matches(obj: Any, f: CustomReportFilter) -> bool:
            val = getattr(obj, f.field_name, None)
            op = f.operator

            if op == "eq":
                return val == f.value
            if op == "ne":
                return val != f.value
            if op == "gt":
                return val is not None and val > f.value
            if op == "lt":
                return val is not None and val < f.value
            if op == "gte":
                return val is not None and val >= f.value
            if op == "lte":
                return val is not None and val <= f.value
            if op == "in":
                return isinstance(f.value, (list, tuple, set)) and val in f.value
            if op == "contains":
                return isinstance(val, str) and isinstance(f.value, str) and f.value.lower() in val.lower()
            if op == "between":
                if f.value is None or f.value_to is None:
                    return True
                return val is not None and f.value <= val <= f.value_to
            # Fallback: no-op
            return True

        for obj in objs:
            ok = True
            for f in filters:
                if not matches(obj, f):
                    ok = False
                    break
            if ok:
                yield obj

    def _build_rows(
        self,
        objs: Iterable[Any],
        fields: List[CustomReportField],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for obj in objs:
            row: Dict[str, Any] = {}
            for field in fields:
                raw_val = getattr(obj, field.field_name, None)
                key = field.display_label or field.field_name
                row[key] = raw_val
            rows.append(row)
        return rows

    def _build_summary(
        self,
        rows: List[Dict[str, Any]],
        fields: List[CustomReportField],
    ) -> Dict[str, Any]:
        """
        Perform basic aggregations for fields that requested them.
        Supported aggregations: sum, avg, min, max, count.
        """
        summary: Dict[str, Any] = {}
        if not rows:
            return summary

        for f in fields:
            if not f.aggregation or f.aggregation == "none":
                continue
            key = f.display_label or f.field_name
            values = [r.get(key) for r in rows if isinstance(r.get(key), (int, float, Decimal))]
            if not values:
                continue

            agg_name = f.aggregation.lower()
            if agg_name == "sum":
                summary[key + "_sum"] = sum(values)
            elif agg_name == "avg":
                summary[key + "_avg"] = sum(values) / len(values)
            elif agg_name == "min":
                summary[key + "_min"] = min(values)
            elif agg_name == "max":
                summary[key + "_max"] = max(values)
            elif agg_name == "count":
                summary[key + "_count"] = len(values)

        return summary