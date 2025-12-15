# app/services/reporting/export_service.py
from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional, Protocol

from app.schemas.payment.payment_filters import PaymentExportRequest
from app.services.common import errors


class ExportBackend(Protocol):
    """
    Abstract export backend.

    Implementations may wrap libraries for Excel/PDF generation.
    """

    def export_csv(self, rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> bytes: ...
    def export_excel(self, rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> bytes: ...
    def export_pdf(self, rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> bytes: ...


class SimpleCSVBackend:
    """
    Minimal CSV-only backend implementation.

    - Excel/PDF methods raise NotImplementedError.
    """

    def export_csv(self, rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> bytes:
        if not rows:
            return b""

        # Determine column order
        if columns is None:
            # Preserve insertion order of first row
            columns = list(rows[0].keys())

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return buf.getvalue().encode("utf-8")

    def export_excel(self, rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> bytes:
        raise NotImplementedError("Excel export not implemented for SimpleCSVBackend")

    def export_pdf(self, rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> bytes:
        raise NotImplementedError("PDF export not implemented for SimpleCSVBackend")


class ExportService:
    """
    Generic export service for tabular data.

    - export_table: core primitive (rows + columns -> bytes).
    - export_payments: convenience wrapper for PaymentExportRequest.
    """

    def __init__(self, backend: Optional[ExportBackend] = None) -> None:
        self._backend = backend or SimpleCSVBackend()

    # ------------------------------------------------------------------ #
    # Core export
    # ------------------------------------------------------------------ #
    def export_table(
        self,
        rows: List[Dict[str, Any]],
        *,
        fmt: str,
        columns: Optional[List[str]] = None,
    ) -> bytes:
        """
        Export table rows in the given format ('csv', 'excel', 'pdf').

        Returns raw bytes, suitable for sending as a file response.
        """
        fmt = fmt.lower()
        if fmt == "csv":
            return self._backend.export_csv(rows, columns)
        if fmt == "excel":
            return self._backend.export_excel(rows, columns)
        if fmt == "pdf":
            return self._backend.export_pdf(rows, columns)
        if fmt == "json":
            return json.dumps(rows, default=str).encode("utf-8")
        raise errors.ValidationError(f"Unsupported export format {fmt!r}")

    # ------------------------------------------------------------------ #
    # Payment-specific helper
    # ------------------------------------------------------------------ #
    def export_payments(
        self,
        req: PaymentExportRequest,
        rows: List[Dict[str, Any]],
    ) -> bytes:
        """
        Export payment rows according to PaymentExportRequest.

        The service does NOT fetch payments itself; caller is responsible for
        supplying already-filtered rows (e.g. from PaymentService / custom report).
        """
        fmt = req.format.lower()
        return self.export_table(
            rows,
            fmt=fmt,
            columns=None,  # let backend infer columns
        )