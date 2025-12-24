"""
User Data Export Service

Exports user-related data for reporting / compliance (GDPR, account export, etc.).
"""

from __future__ import annotations

from typing import Literal, Dict, Any, List
from uuid import UUID
from io import BytesIO

from sqlalchemy.orm import Session

from app.repositories.user import UserAggregateRepository
from app.schemas.user import UserDetail, UserStats
from app.utils.excel_utils import ExcelReportGenerator
from app.utils.pdf_utils import PDFReportGenerator
from app.utils.file_utils import FileHelper
from app.core.exceptions import ValidationException


ExportFormat = Literal["json", "excel", "pdf"]


class UserDataExportService:
    """
    High-level service for exporting user data.

    Supported formats:
    - json (dict)
    - excel (bytes)
    - pdf (bytes)
    """

    def __init__(
        self,
        aggregate_repo: UserAggregateRepository,
    ) -> None:
        self.aggregate_repo = aggregate_repo

    def export_user_data(
        self,
        db: Session,
        user_id: UUID,
        fmt: ExportFormat = "json",
    ) -> Any:
        """
        Export user full profile and activity summary.

        For 'json' returns a dict.
        For 'excel' and 'pdf' returns raw bytes.
        """
        profile = self.aggregate_repo.get_full_user_profile(db, user_id)
        if not profile:
            raise ValidationException("User not found")

        stats = self.aggregate_repo.get_user_statistics(db, user_id)

        profile_schema = UserDetail.model_validate(profile)
        stats_schema = UserStats.model_validate(stats) if stats else None

        data = {
            "profile": profile_schema.model_dump(),
            "stats": stats_schema.model_dump() if stats_schema else None,
        }

        if fmt == "json":
            return data
        elif fmt == "excel":
            return self._export_to_excel(data)
        elif fmt == "pdf":
            return self._export_to_pdf(data)
        else:
            raise ValidationException(f"Unsupported export format: {fmt}")

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _export_to_excel(self, data: Dict[str, Any]) -> bytes:
        """
        Convert user data to an Excel file (single workbook, multiple sheets).
        """
        generator = ExcelReportGenerator()

        # Basic example: create two sheets
        wb = generator.create_workbook()
        generator.add_sheet_from_dict(wb, "Profile", data.get("profile") or {})
        generator.add_sheet_from_dict(wb, "Stats", data.get("stats") or {})

        stream = BytesIO()
        wb.save(stream)
        return stream.getvalue()

    def _export_to_pdf(self, data: Dict[str, Any]) -> bytes:
        """
        Convert user data to a PDF summary.

        Actual implementation depends on your PDFReportGenerator.
        """
        generator = PDFReportGenerator()
        buffer = BytesIO()

        # This is intentionally high level — adapt to your actual generator API.
        generator.start_document(buffer, title="User Data Export")
        generator.add_heading("User Profile")
        generator.add_key_value_table(data.get("profile") or {})
        generator.add_heading("User Statistics")
        generator.add_key_value_table(data.get("stats") or {})
        generator.finish_document()

        return buffer.getvalue()