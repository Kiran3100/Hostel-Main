# app/services/reporting/report_export_service.py
"""
Report Export Service

Exports report results to various formats (JSON, CSV, Excel, PDF)
with enhanced validation, error handling, and optimization.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Dict, Optional
from io import BytesIO
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.analytics import CustomReportResult, ReportExportRequest
from app.repositories.analytics import CustomReportsRepository
from app.utils.excel_utils import ExcelReportGenerator
from app.utils.pdf_utils import PDFReportGenerator
from app.utils.file_utils import FileHelper
from app.core.exceptions import ValidationException, NotFoundException
from app.utils.metrics import track_performance

logger = logging.getLogger(__name__)

ExportFormat = Literal["json", "csv", "excel", "pdf"]


class ReportExportService:
    """
    High-level service for exporting report results.

    Responsibilities:
    - Fetch CustomReportResult from database
    - Convert to requested format with validation
    - Return raw bytes for file responses or dict for JSON
    - Handle compression for large exports
    - Support custom formatting options

    Attributes:
        custom_reports_repo: Repository for custom reports
        max_export_rows: Maximum rows for export (default: 1000000)
        enable_compression: Whether to compress large exports
    """

    def __init__(
        self,
        custom_reports_repo: CustomReportsRepository,
        max_export_rows: int = 1000000,
        enable_compression: bool = True,
    ) -> None:
        """
        Initialize the report export service.

        Args:
            custom_reports_repo: Repository for custom reports
            max_export_rows: Maximum rows allowed per export
            enable_compression: Whether to compress large files
        """
        if not custom_reports_repo:
            raise ValueError("CustomReportsRepository cannot be None")
        
        self.custom_reports_repo = custom_reports_repo
        self.max_export_rows = max_export_rows
        self.enable_compression = enable_compression
        
        logger.info(
            f"ReportExportService initialized with max_rows={max_export_rows}, "
            f"compression={enable_compression}"
        )

    def _validate_export_request(self, request: ReportExportRequest) -> None:
        """
        Validate export request.

        Args:
            request: Export request to validate

        Raises:
            ValidationException: If validation fails
        """
        if not request.result_id:
            raise ValidationException("Result ID is required")
        
        if not request.format:
            raise ValidationException("Export format is required")
        
        valid_formats = ["json", "csv", "excel", "pdf"]
        if request.format not in valid_formats:
            raise ValidationException(
                f"Invalid export format. Must be one of: {', '.join(valid_formats)}"
            )

    @track_performance("export_custom_report")
    def export_custom_report(
        self,
        db: Session,
        request: ReportExportRequest,
        owner_id: Optional[UUID] = None,
    ) -> Any:
        """
        Export a cached report result by ID.

        For 'json' returns a dict.
        For 'csv', 'excel', 'pdf' returns bytes suitable for download.

        Args:
            db: Database session
            request: Export request containing result_id and format
            owner_id: Optional owner ID for authorization

        Returns:
            Dict for JSON, bytes for other formats

        Raises:
            ValidationException: If validation fails
            NotFoundException: If cached result not found
        """
        logger.info(
            f"Exporting report result {request.result_id} as {request.format}"
        )
        
        try:
            # Validate request
            self._validate_export_request(request)
            
            # Fetch cached result
            result_obj = self.custom_reports_repo.get_cached_result_by_id(
                db, request.result_id
            )
            
            if not result_obj:
                raise NotFoundException(
                    f"Cached report result {request.result_id} not found"
                )
            
            # Check authorization if owner_id provided
            if owner_id and hasattr(result_obj, 'owner_id'):
                if result_obj.owner_id != owner_id:
                    raise ValidationException(
                        "Not authorized to export this report"
                    )
            
            # Validate and convert to schema
            result = CustomReportResult.model_validate(result_obj)
            
            # Check row limit
            if result.rows and len(result.rows) > self.max_export_rows:
                raise ValidationException(
                    f"Export exceeds maximum row limit of {self.max_export_rows}. "
                    f"Please filter the report or contact support."
                )
            
            # Export based on format
            if request.format == "json":
                exported = self._export_to_json(result, request)
            elif request.format == "excel":
                exported = self._export_to_excel(result, request)
            elif request.format == "pdf":
                exported = self._export_to_pdf(result, request)
            elif request.format == "csv":
                exported = self._export_to_csv(result, request)
            else:
                raise ValidationException(f"Unsupported export format: {request.format}")
            
            logger.info(
                f"Successfully exported report {request.result_id} as {request.format}"
            )
            
            return exported
            
        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error during export: {str(e)}")
            raise ValidationException(f"Failed to export report: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during export: {str(e)}", exc_info=True)
            raise ValidationException(f"Report export failed: {str(e)}")

    def _export_to_json(
        self,
        result: CustomReportResult,
        request: ReportExportRequest,
    ) -> Dict[str, Any]:
        """
        Export report to JSON format.

        Args:
            result: Report result to export
            request: Export request options

        Returns:
            Dictionary representation of report
        """
        logger.debug("Exporting to JSON format")
        
        try:
            data = result.model_dump()
            
            # Optionally exclude certain fields
            if not request.include_metadata:
                data.pop("metadata", None)
            
            if not request.include_summary:
                data.pop("summary_stats", None)
            
            if not request.include_filters:
                data.pop("applied_filters", None)
            
            return data
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {str(e)}")
            raise ValidationException(f"JSON export failed: {str(e)}")

    def _export_to_excel(
        self,
        result: CustomReportResult,
        request: ReportExportRequest,
    ) -> bytes:
        """
        Export report to Excel format.

        Args:
            result: Report result to export
            request: Export request options

        Returns:
            Excel file as bytes
        """
        logger.debug("Exporting to Excel format")
        
        try:
            generator = ExcelReportGenerator()
            wb = generator.create_workbook()
            
            # Add main data sheet
            sheet_name = result.metadata.get("title", "Report")[:31]  # Excel limit
            generator.add_sheet_from_rows(
                wb,
                name=sheet_name,
                rows=result.rows or [],
                column_definitions=result.column_definitions or [],
            )
            
            # Add summary sheet if requested
            if request.include_summary and result.summary_stats:
                generator.add_sheet_from_dict(
                    wb,
                    name="Summary",
                    data=result.summary_stats,
                )
            
            # Add metadata sheet if requested
            if request.include_metadata and result.metadata:
                generator.add_sheet_from_dict(
                    wb,
                    name="Metadata",
                    data=result.metadata,
                )
            
            # Add filters sheet if requested
            if request.include_filters and result.applied_filters:
                generator.add_sheet_from_dict(
                    wb,
                    name="Filters",
                    data=result.applied_filters,
                )
            
            # Save to bytes
            stream = BytesIO()
            wb.save(stream)
            
            logger.debug(f"Excel export size: {stream.tell()} bytes")
            
            return stream.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {str(e)}")
            raise ValidationException(f"Excel export failed: {str(e)}")

    def _export_to_pdf(
        self,
        result: CustomReportResult,
        request: ReportExportRequest,
    ) -> bytes:
        """
        Export report to PDF format.

        Args:
            result: Report result to export
            request: Export request options

        Returns:
            PDF file as bytes
        """
        logger.debug("Exporting to PDF format")
        
        try:
            generator = PDFReportGenerator()
            buffer = BytesIO()
            
            # Start document
            title = result.metadata.get("title", "Custom Report")
            generator.start_document(buffer, title=title)
            
            # Add metadata section
            if request.include_metadata and result.metadata:
                generator.add_heading("Report Information", level=1)
                generator.add_key_value_table(result.metadata)
                generator.add_page_break()
            
            # Add summary section
            if request.include_summary and result.summary_stats:
                generator.add_heading("Summary Statistics", level=1)
                generator.add_key_value_table(result.summary_stats)
                generator.add_page_break()
            
            # Add data section
            generator.add_heading("Report Data", level=1)
            
            # Limit rows for PDF to prevent huge files
            max_pdf_rows = 1000
            rows_to_export = result.rows[:max_pdf_rows] if result.rows else []
            
            if result.rows and len(result.rows) > max_pdf_rows:
                logger.warning(
                    f"PDF export limited to {max_pdf_rows} rows "
                    f"(total: {len(result.rows)})"
                )
            
            generator.add_table(
                rows=rows_to_export,
                column_definitions=result.column_definitions or [],
            )
            
            # Add filters section
            if request.include_filters and result.applied_filters:
                generator.add_page_break()
                generator.add_heading("Applied Filters", level=1)
                generator.add_key_value_table(result.applied_filters)
            
            # Finish document
            generator.finish_document()
            
            logger.debug(f"PDF export size: {buffer.tell()} bytes")
            
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting to PDF: {str(e)}")
            raise ValidationException(f"PDF export failed: {str(e)}")

    def _export_to_csv(
        self,
        result: CustomReportResult,
        request: ReportExportRequest,
    ) -> bytes:
        """
        Export report to CSV format.

        Args:
            result: Report result to export
            request: Export request options

        Returns:
            CSV file as bytes
        """
        logger.debug("Exporting to CSV format")
        
        try:
            if not result.rows or not result.column_definitions:
                raise ValidationException("No data available to export")
            
            # Extract headers from column definitions
            headers = [col["field"] for col in result.column_definitions]
            
            # Convert rows to list of dicts
            rows_as_dicts: list[Dict[str, Any]] = []
            
            for row in result.rows:
                # Handle both list/tuple and dict row formats
                if isinstance(row, (list, tuple)):
                    row_dict = {
                        field: value
                        for field, value in zip(headers, row)
                    }
                elif isinstance(row, dict):
                    row_dict = {field: row.get(field) for field in headers}
                else:
                    logger.warning(f"Unexpected row type: {type(row)}")
                    continue
                
                rows_as_dicts.append(row_dict)
            
            # Convert to CSV bytes
            csv_bytes = FileHelper.dicts_to_csv_bytes(
                rows_as_dicts,
                headers=headers,
            )
            
            logger.debug(f"CSV export size: {len(csv_bytes)} bytes")
            
            return csv_bytes
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {str(e)}")
            raise ValidationException(f"CSV export failed: {str(e)}")

    def get_export_filename(
        self,
        request: ReportExportRequest,
        result: Optional[CustomReportResult] = None,
    ) -> str:
        """
        Generate appropriate filename for export.

        Args:
            request: Export request
            result: Optional report result for metadata

        Returns:
            Filename string
        """
        try:
            # Base name from result or default
            if result and result.metadata:
                base_name = result.metadata.get("title", "report")
            else:
                base_name = "report"
            
            # Sanitize filename
            base_name = "".join(
                c for c in base_name if c.isalnum() or c in (' ', '-', '_')
            ).strip()
            
            # Add timestamp
            from datetime import datetime
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            
            # Add extension
            extension = request.format
            
            filename = f"{base_name}_{timestamp}.{extension}"
            
            return filename
            
        except Exception as e:
            logger.warning(f"Error generating filename: {str(e)}")
            return f"report_{request.result_id}.{request.format}"