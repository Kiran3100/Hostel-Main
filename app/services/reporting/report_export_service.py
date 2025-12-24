# app/services/reporting/report_export_service.py
"""
Report Export Service

Exports report results to various formats (JSON, CSV, Excel, PDF).
"""

from __future__ import annotations

from typing import Any, Literal, Dict
from io import BytesIO

from sqlalchemy.orm import Session

from app.schemas.analytics import CustomReportResult, ReportExportRequest
from app.repositories.analytics import CustomReportsRepository
from app.utils.excel_utils import ExcelReportGenerator
from app.utils.pdf_utils import PDFReportGenerator
from app.utils.file_utils import FileHelper
from app.core.exceptions import ValidationException

ExportFormat = Literal["json", "csv", "excel", "pdf"]


class ReportExportService:
    """
    High-level service for exporting report results.

    Responsibilities:
    - Fetch CustomReportResult from DB
    - Convert to requested format
    - Return raw bytes for file responses or dict for JSON
    """

    def __init__(
        self,
        custom_reports_repo: CustomReportsRepository,
    ) -> None:
        self.custom_reports_repo = custom_reports_repo

    def export_custom_report(
        self,
        db: Session,
        request: ReportExportRequest,
    ) -> Any:
        """
        Export a cached report result by id.

        For 'json' returns a dict.
        For 'csv', 'excel', 'pdf' returns bytes suitable for download.
        """
        result_obj = self.custom_reports_repo.get_cached_result_by_id(
            db, request.result_id
        )
        if not result_obj:
            raise ValidationException("Cached report result not found")

        result = CustomReportResult.model_validate(result_obj)

        if request.format == "json":
            return result.model_dump()

        if request.format == "excel":
            return self._export_to_excel(result, request)

        if request.format == "pdf":
            return self._export_to_pdf(result, request)

        if request.format == "csv":
            return self._export_to_csv(result, request)

        raise ValidationException(f"Unsupported export format: {request.format}")

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _export_to_excel(
        self,
        result: CustomReportResult,
        request: ReportExportRequest,
    ) -> bytes:
        generator = ExcelReportGenerator()
        wb = generator.create_workbook()

        # Use a single sheet with the main data
        sheet_name = result.metadata.get("title") or "Report"
        generator.add_sheet_from_rows(
            wb,
            name=sheet_name,
            rows=result.rows,
            column_definitions=result.column_definitions,
        )

        if request.include_summary and result.summary_stats:
            generator.add_sheet_from_dict(
                wb,
                name="Summary",
                data=result.summary_stats,
            )

        stream = BytesIO()
        wb.save(stream)
        return stream.getvalue()

    def _export_to_pdf(
        self,
        result: CustomReportResult,
        request: ReportExportRequest,
    ) -> bytes:
        generator = PDFReportGenerator()
        buffer = BytesIO()

        title = result.metadata.get("title") or "Custom Report"
        generator.start_document(buffer, title=title)

        if request.include_summary and result.summary_stats:
            generator.add_heading("Summary")
            generator.add_key_value_table(result.summary_stats)

        generator.add_heading("Data")
        generator.add_table(
            rows=result.rows,
            column_definitions=result.column_definitions,
        )

        if request.include_filters and result.applied_filters:
            generator.add_heading("Applied Filters")
            generator.add_key_value_table(result.applied_filters)

        generator.finish_document()
        return buffer.getvalue()

    def _export_to_csv(
        self,
        result: CustomReportResult,
        request: ReportExportRequest,
    ) -> bytes:
        """
        Simple CSV export using FileHelper.
        """
        # Convert rows to list-of-dicts using column_definitions
        headers = [col["field"] for col in result.column_definitions]
        rows: list[Dict[str, Any]] = []

        for row in result.rows:
            # row is expected to be a list/tuple in same order as headers
            rows.append({field: value for field, value in zip(headers, row)})

        csv_bytes = FileHelper.dicts_to_csv_bytes(rows, headers=headers)
        return csv_bytes