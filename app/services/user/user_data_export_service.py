"""
User Data Export Service

Exports user-related data for reporting / compliance (GDPR, account export, etc.).
Enhanced with better error handling, data sanitization, and format validation.
"""

from __future__ import annotations

import logging
from typing import Literal, Dict, Any, List, Optional
from uuid import UUID
from io import BytesIO
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.user import UserAggregateRepository
from app.schemas.user import UserDetail, UserStats
from app.utils.excel_utils import ExcelReportGenerator
from app.utils.pdf_utils import PDFReportGenerator
from app.utils.file_utils import FileHelper
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)

ExportFormat = Literal["json", "excel", "pdf", "csv"]


class UserDataExportService:
    """
    High-level service for exporting user data.

    Supported formats:
    - json (dict)
    - excel (bytes)
    - pdf (bytes)
    - csv (bytes)

    Responsibilities:
    - Export user profile data
    - Export user activity statistics
    - Format data according to export type
    - Sanitize sensitive data
    - Generate compliance reports
    """

    def __init__(
        self,
        aggregate_repo: UserAggregateRepository,
    ) -> None:
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # Main Export Methods
    # -------------------------------------------------------------------------

    def export_user_data(
        self,
        db: Session,
        user_id: UUID,
        fmt: ExportFormat = "json",
        include_stats: bool = True,
        include_sensitive: bool = False,
    ) -> Any:
        """
        Export user full profile and activity summary.

        Args:
            db: Database session
            user_id: User identifier
            fmt: Export format ('json', 'excel', 'pdf', 'csv')
            include_stats: Whether to include user statistics
            include_sensitive: Whether to include sensitive data

        Returns:
            For 'json' returns a dict.
            For other formats returns raw bytes.

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If format is unsupported
        """
        try:
            # Get user profile
            profile = self.aggregate_repo.get_full_user_profile(db, user_id)
            if not profile:
                raise NotFoundException(f"User {user_id} not found")

            # Get statistics if requested
            stats = None
            if include_stats:
                stats = self.aggregate_repo.get_user_statistics(db, user_id)

            # Validate to schemas
            profile_schema = UserDetail.model_validate(profile)
            stats_schema = UserStats.model_validate(stats) if stats else None

            # Build export data
            data = self._build_export_data(
                profile_schema,
                stats_schema,
                include_sensitive,
            )

            # Export in requested format
            if fmt == "json":
                return data
            elif fmt == "excel":
                return self._export_to_excel(data, user_id)
            elif fmt == "pdf":
                return self._export_to_pdf(data, user_id)
            elif fmt == "csv":
                return self._export_to_csv(data, user_id)
            else:
                raise ValidationException(f"Unsupported export format: {fmt}")

        except (NotFoundException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error exporting data for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to export user data")
        except Exception as e:
            logger.error(f"Error exporting data for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to export user data")

    def export_multiple_users(
        self,
        db: Session,
        user_ids: List[UUID],
        fmt: ExportFormat = "excel",
        include_stats: bool = False,
    ) -> bytes:
        """
        Export multiple users' data in a single file.

        Args:
            db: Database session
            user_ids: List of user identifiers
            fmt: Export format ('excel', 'csv', 'pdf')
            include_stats: Whether to include statistics

        Returns:
            Raw bytes of the export file

        Raises:
            ValidationException: If format is JSON or unsupported
        """
        if fmt == "json":
            raise ValidationException("JSON format not supported for multiple users")

        if not user_ids:
            raise ValidationException("No user IDs provided")

        try:
            # Collect data for all users
            all_data = []
            
            for user_id in user_ids:
                try:
                    profile = self.aggregate_repo.get_full_user_profile(db, user_id)
                    if not profile:
                        logger.warning(f"User {user_id} not found, skipping")
                        continue

                    stats = None
                    if include_stats:
                        stats = self.aggregate_repo.get_user_statistics(db, user_id)

                    profile_schema = UserDetail.model_validate(profile)
                    stats_schema = UserStats.model_validate(stats) if stats else None

                    user_data = self._build_export_data(
                        profile_schema,
                        stats_schema,
                        include_sensitive=False,  # Never include sensitive in bulk exports
                    )
                    
                    all_data.append(user_data)

                except Exception as e:
                    logger.error(f"Error processing user {user_id}: {str(e)}")
                    continue

            if not all_data:
                raise BusinessLogicException("No valid user data to export")

            # Export based on format
            if fmt == "excel":
                return self._export_multiple_to_excel(all_data)
            elif fmt == "csv":
                return self._export_multiple_to_csv(all_data)
            elif fmt == "pdf":
                return self._export_multiple_to_pdf(all_data)
            else:
                raise ValidationException(f"Unsupported format for bulk export: {fmt}")

        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(f"Error in bulk export: {str(e)}")
            raise BusinessLogicException("Failed to export multiple users")

    def export_gdpr_package(
        self,
        db: Session,
        user_id: UUID,
    ) -> bytes:
        """
        Export complete GDPR data package for a user (PDF format).

        Includes:
        - Full profile data
        - All activity statistics
        - Sensitive information
        - Data usage summary

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            PDF file as bytes

        Raises:
            NotFoundException: If user doesn't exist
        """
        try:
            data = self.export_user_data(
                db=db,
                user_id=user_id,
                fmt="json",
                include_stats=True,
                include_sensitive=True,
            )

            # Add GDPR-specific metadata
            data["gdpr_export"] = {
                "export_date": datetime.utcnow().isoformat(),
                "export_type": "Full Data Package (GDPR Article 15)",
                "data_controller": "Hostel Management System",
                "user_rights": [
                    "Right to access",
                    "Right to rectification",
                    "Right to erasure",
                    "Right to data portability",
                ],
            }

            return self._export_gdpr_to_pdf(data, user_id)

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error creating GDPR package for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to create GDPR data package")

    # -------------------------------------------------------------------------
    # Data Building and Sanitization
    # -------------------------------------------------------------------------

    def _build_export_data(
        self,
        profile: UserDetail,
        stats: Optional[UserStats],
        include_sensitive: bool,
    ) -> Dict[str, Any]:
        """Build export data structure."""
        profile_dict = profile.model_dump()

        # Sanitize sensitive data if not requested
        if not include_sensitive:
            profile_dict = self._sanitize_sensitive_data(profile_dict)

        data = {
            "profile": profile_dict,
            "stats": stats.model_dump() if stats else None,
            "export_metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "includes_sensitive_data": include_sensitive,
            },
        }

        return data

    def _sanitize_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or mask sensitive data fields."""
        sensitive_fields = [
            "password",
            "password_hash",
            "security_questions",
            "two_factor_secret",
        ]

        sanitized = data.copy()

        for field in sensitive_fields:
            if field in sanitized:
                del sanitized[field]

        # Mask email partially
        if "email" in sanitized and sanitized["email"]:
            email = sanitized["email"]
            parts = email.split("@")
            if len(parts) == 2:
                username = parts[0]
                domain = parts[1]
                masked_username = username[:2] + "*" * (len(username) - 2)
                sanitized["email"] = f"{masked_username}@{domain}"

        # Mask phone partially
        if "phone" in sanitized and sanitized["phone"]:
            phone = sanitized["phone"]
            sanitized["phone"] = "*" * (len(phone) - 4) + phone[-4:]

        return sanitized

    # -------------------------------------------------------------------------
    # Format-Specific Export Methods
    # -------------------------------------------------------------------------

    def _export_to_excel(self, data: Dict[str, Any], user_id: UUID) -> bytes:
        """Convert user data to an Excel file."""
        try:
            generator = ExcelReportGenerator()
            wb = generator.create_workbook()

            # Profile sheet
            if data.get("profile"):
                generator.add_sheet_from_dict(wb, "Profile", data["profile"])

            # Stats sheet
            if data.get("stats"):
                generator.add_sheet_from_dict(wb, "Statistics", data["stats"])

            # Metadata sheet
            if data.get("export_metadata"):
                generator.add_sheet_from_dict(wb, "Export Info", data["export_metadata"])

            stream = BytesIO()
            wb.save(stream)
            
            logger.info(f"Exported user {user_id} data to Excel")
            
            return stream.getvalue()

        except Exception as e:
            logger.error(f"Error exporting to Excel for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to generate Excel export")

    def _export_to_pdf(self, data: Dict[str, Any], user_id: UUID) -> bytes:
        """Convert user data to a PDF summary."""
        try:
            generator = PDFReportGenerator()
            buffer = BytesIO()

            generator.start_document(buffer, title=f"User Data Export - {user_id}")
            
            # Profile section
            generator.add_heading("User Profile", level=1)
            if data.get("profile"):
                generator.add_key_value_table(data["profile"])

            # Statistics section
            if data.get("stats"):
                generator.add_heading("User Statistics", level=1)
                generator.add_key_value_table(data["stats"])

            # Metadata section
            if data.get("export_metadata"):
                generator.add_heading("Export Information", level=1)
                generator.add_key_value_table(data["export_metadata"])

            generator.finish_document()

            logger.info(f"Exported user {user_id} data to PDF")

            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error exporting to PDF for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to generate PDF export")

    def _export_to_csv(self, data: Dict[str, Any], user_id: UUID) -> bytes:
        """Convert user data to CSV format."""
        try:
            import csv
            
            buffer = BytesIO()
            
            # Use text wrapper for CSV writer
            from io import TextIOWrapper
            text_buffer = TextIOWrapper(buffer, encoding='utf-8', newline='')
            
            writer = csv.writer(text_buffer)

            # Write profile data
            if data.get("profile"):
                writer.writerow(["Profile Data"])
                writer.writerow(["Field", "Value"])
                for key, value in data["profile"].items():
                    writer.writerow([key, str(value)])
                writer.writerow([])  # Empty row

            # Write stats data
            if data.get("stats"):
                writer.writerow(["Statistics"])
                writer.writerow(["Metric", "Value"])
                for key, value in data["stats"].items():
                    writer.writerow([key, str(value)])

            text_buffer.flush()
            buffer.seek(0)

            logger.info(f"Exported user {user_id} data to CSV")

            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error exporting to CSV for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to generate CSV export")

    def _export_gdpr_to_pdf(self, data: Dict[str, Any], user_id: UUID) -> bytes:
        """Create comprehensive GDPR-compliant PDF export."""
        try:
            generator = PDFReportGenerator()
            buffer = BytesIO()

            generator.start_document(
                buffer,
                title="GDPR Data Export Package",
            )

            # GDPR Header
            generator.add_heading("Personal Data Export", level=1)
            generator.add_paragraph(
                "This document contains all personal data we hold about you, "
                "in accordance with GDPR Article 15 (Right of Access)."
            )

            # GDPR metadata
            if data.get("gdpr_export"):
                generator.add_heading("Export Information", level=2)
                generator.add_key_value_table(data["gdpr_export"])

            # Profile data
            generator.add_heading("Personal Information", level=2)
            if data.get("profile"):
                generator.add_key_value_table(data["profile"])

            # Statistics
            if data.get("stats"):
                generator.add_heading("Account Activity", level=2)
                generator.add_key_value_table(data["stats"])

            # Footer with user rights
            generator.add_heading("Your Rights", level=2)
            generator.add_paragraph(
                "You have the right to:\n"
                "- Request rectification of your data\n"
                "- Request erasure of your data\n"
                "- Object to processing of your data\n"
                "- Request data portability\n"
                "- Withdraw consent at any time"
            )

            generator.finish_document()

            logger.info(f"Generated GDPR export package for user {user_id}")

            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error creating GDPR PDF for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to generate GDPR package")

    # -------------------------------------------------------------------------
    # Bulk Export Methods
    # -------------------------------------------------------------------------

    def _export_multiple_to_excel(self, data_list: List[Dict[str, Any]]) -> bytes:
        """Export multiple users to Excel with one sheet per user."""
        try:
            generator = ExcelReportGenerator()
            wb = generator.create_workbook()

            for idx, data in enumerate(data_list):
                sheet_name = f"User_{idx + 1}"
                profile_data = data.get("profile", {})
                generator.add_sheet_from_dict(wb, sheet_name, profile_data)

            stream = BytesIO()
            wb.save(stream)

            logger.info(f"Exported {len(data_list)} users to Excel")

            return stream.getvalue()

        except Exception as e:
            logger.error(f"Error in bulk Excel export: {str(e)}")
            raise BusinessLogicException("Failed to generate bulk Excel export")

    def _export_multiple_to_csv(self, data_list: List[Dict[str, Any]]) -> bytes:
        """Export multiple users to CSV."""
        try:
            import csv
            
            buffer = BytesIO()
            from io import TextIOWrapper
            text_buffer = TextIOWrapper(buffer, encoding='utf-8', newline='')
            
            writer = csv.writer(text_buffer)

            # Write header row (collect all unique fields)
            all_fields = set()
            for data in data_list:
                if data.get("profile"):
                    all_fields.update(data["profile"].keys())

            headers = sorted(all_fields)
            writer.writerow(headers)

            # Write data rows
            for data in data_list:
                profile = data.get("profile", {})
                row = [profile.get(field, "") for field in headers]
                writer.writerow(row)

            text_buffer.flush()
            buffer.seek(0)

            logger.info(f"Exported {len(data_list)} users to CSV")

            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error in bulk CSV export: {str(e)}")
            raise BusinessLogicException("Failed to generate bulk CSV export")

    def _export_multiple_to_pdf(self, data_list: List[Dict[str, Any]]) -> bytes:
        """Export multiple users to PDF."""
        try:
            generator = PDFReportGenerator()
            buffer = BytesIO()

            generator.start_document(buffer, title="User Data Export (Multiple Users)")
            generator.add_heading("Multiple User Export", level=1)
            generator.add_paragraph(f"Total users: {len(data_list)}")

            for idx, data in enumerate(data_list):
                generator.add_heading(f"User {idx + 1}", level=2)
                if data.get("profile"):
                    generator.add_key_value_table(data["profile"])

            generator.finish_document()

            logger.info(f"Exported {len(data_list)} users to PDF")

            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error in bulk PDF export: {str(e)}")
            raise BusinessLogicException("Failed to generate bulk PDF export")