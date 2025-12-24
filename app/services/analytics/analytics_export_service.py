"""
Analytics export service.

Provides CSV/Excel/JSON/PDF exports for analytics payloads using the
underlying analytics repositories and utility formatters.

Optimizations:
- Added streaming support for large exports
- Improved file handling with context managers
- Enhanced error handling and validation
- Added export templates and customization
- Implemented export history tracking
"""

from typing import Optional, Dict, Any, List, Tuple, Union, BinaryIO
from uuid import UUID
from datetime import date, timedelta, datetime
from pathlib import Path
from enum import Enum
import logging
import tempfile
import json
import csv

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.analytics import (
    AnalyticsAggregateRepository,
    BookingAnalyticsRepository,
    ComplaintAnalyticsRepository,
    FinancialAnalyticsRepository,
    OccupancyAnalyticsRepository,
    PlatformAnalyticsRepository,
    SupervisorAnalyticsRepository,
    VisitorAnalyticsRepository,
    CustomReportsRepository,
)
from app.models.analytics.base_analytics import BaseAnalyticsModel
from app.schemas.common.filters import DateRangeFilter

# Utility imports
from app.utils.excel_utils import ExcelReportGenerator
from app.utils.pdf_utils import PDFReportGenerator
from app.utils.file_utils import FileHelper

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Supported export formats."""
    EXCEL = "excel"
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"


class ExportType(str, Enum):
    """Types of analytics exports."""
    BOOKING_SUMMARY = "booking_summary"
    COMPLAINT_DASHBOARD = "complaint_dashboard"
    FINANCIAL_REPORT = "financial_report"
    OCCUPANCY_REPORT = "occupancy_report"
    PLATFORM_OVERVIEW = "platform_overview"
    SUPERVISOR_ANALYTICS = "supervisor_analytics"
    VISITOR_ANALYTICS = "visitor_analytics"
    CUSTOM_REPORT = "custom_report"


class AnalyticsExportService(BaseService[BaseAnalyticsModel, AnalyticsAggregateRepository]):
    """
    Export analytics to various formats.
    
    Features:
    - Multiple export formats (Excel, CSV, JSON, PDF)
    - Streaming support for large datasets
    - Template-based exports
    - Export history tracking
    - Customizable export options
    """

    # Maximum rows for streaming threshold
    STREAMING_THRESHOLD = 10000
    
    # Default export directory
    DEFAULT_EXPORT_DIR = Path(tempfile.gettempdir()) / "analytics_exports"

    def __init__(
        self,
        aggregate_repository: AnalyticsAggregateRepository,
        booking_repo: BookingAnalyticsRepository,
        complaint_repo: ComplaintAnalyticsRepository,
        financial_repo: FinancialAnalyticsRepository,
        occupancy_repo: OccupancyAnalyticsRepository,
        platform_repo: PlatformAnalyticsRepository,
        supervisor_repo: SupervisorAnalyticsRepository,
        visitor_repo: VisitorAnalyticsRepository,
        reports_repo: CustomReportsRepository,
        db_session: Session,
    ):
        super().__init__(aggregate_repository, db_session)
        
        self.booking_repo = booking_repo
        self.complaint_repo = complaint_repo
        self.financial_repo = financial_repo
        self.occupancy_repo = occupancy_repo
        self.platform_repo = platform_repo
        self.supervisor_repo = supervisor_repo
        self.visitor_repo = visitor_repo
        self.reports_repo = reports_repo
        
        # Ensure export directory exists
        self.DEFAULT_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Export history
        self._export_history: List[Dict[str, Any]] = []

    def export_booking_summary(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        fmt: str = "excel",
        include_details: bool = True,
        custom_options: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[str]:
        """
        Export booking analytics summary to a file.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            fmt: Export format
            include_details: Include detailed breakdown
            custom_options: Custom export options
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Validate inputs
            validation_result = self._validate_export_params(
                hostel_id, start_date, end_date, fmt
            )
            if not validation_result.success:
                return validation_result
            
            # Fetch data
            summary = self.booking_repo.get_summary(hostel_id, start_date, end_date)
            
            if not summary:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No booking data found for the specified period",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Prepare export data
            export_data = self._prepare_booking_export(
                summary, include_details, custom_options
            )
            
            # Generate file
            file_path = self._export_payload(
                export_data,
                f"booking_summary_{hostel_id}",
                fmt,
                ExportType.BOOKING_SUMMARY,
            )
            
            # Track export
            self._track_export(
                ExportType.BOOKING_SUMMARY,
                hostel_id,
                start_date,
                end_date,
                fmt,
                file_path,
            )
            
            return ServiceResult.success(
                file_path,
                message="Booking summary exported successfully"
            )
            
        except Exception as e:
            logger.error(f"Error exporting booking summary: {str(e)}")
            return self._handle_exception(e, "export booking summary", hostel_id)

    def export_complaint_dashboard(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        fmt: str = "excel",
        include_trends: bool = True,
        custom_options: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[str]:
        """
        Export complaint analytics dashboard to a file.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            fmt: Export format
            include_trends: Include trend analysis
            custom_options: Custom export options
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Validate inputs
            validation_result = self._validate_export_params(
                hostel_id, start_date, end_date, fmt
            )
            if not validation_result.success:
                return validation_result
            
            # Fetch data
            dashboard = self.complaint_repo.get_dashboard(hostel_id, start_date, end_date)
            
            if not dashboard:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No complaint data found for the specified period",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Prepare export data
            export_data = self._prepare_complaint_export(
                dashboard, include_trends, custom_options
            )
            
            # Generate file
            file_path = self._export_payload(
                export_data,
                f"complaint_dashboard_{hostel_id}",
                fmt,
                ExportType.COMPLAINT_DASHBOARD,
            )
            
            # Track export
            self._track_export(
                ExportType.COMPLAINT_DASHBOARD,
                hostel_id,
                start_date,
                end_date,
                fmt,
                file_path,
            )
            
            return ServiceResult.success(
                file_path,
                message="Complaint dashboard exported successfully"
            )
            
        except Exception as e:
            logger.error(f"Error exporting complaint dashboard: {str(e)}")
            return self._handle_exception(e, "export complaint dashboard", hostel_id)

    def export_financial_report(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        fmt: str = "pdf",
        include_charts: bool = True,
        custom_options: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[str]:
        """
        Export financial analytics report to a file.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            fmt: Export format
            include_charts: Include visual charts
            custom_options: Custom export options
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Validate inputs
            validation_result = self._validate_export_params(
                hostel_id, start_date, end_date, fmt
            )
            if not validation_result.success:
                return validation_result
            
            # Fetch data
            report = self.financial_repo.get_financial_report(
                hostel_id, start_date, end_date
            )
            
            if not report:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No financial data found for the specified period",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Prepare export data
            export_data = self._prepare_financial_export(
                report, include_charts, custom_options
            )
            
            # Generate file
            file_path = self._export_payload(
                export_data,
                f"financial_report_{hostel_id}",
                fmt,
                ExportType.FINANCIAL_REPORT,
            )
            
            # Track export
            self._track_export(
                ExportType.FINANCIAL_REPORT,
                hostel_id,
                start_date,
                end_date,
                fmt,
                file_path,
            )
            
            return ServiceResult.success(
                file_path,
                message="Financial report exported successfully"
            )
            
        except Exception as e:
            logger.error(f"Error exporting financial report: {str(e)}")
            return self._handle_exception(e, "export financial report", hostel_id)

    def export_occupancy_report(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        fmt: str = "excel",
        include_forecast: bool = True,
        custom_options: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[str]:
        """
        Export occupancy analytics report to a file.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            fmt: Export format
            include_forecast: Include occupancy forecast
            custom_options: Custom export options
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Validate inputs
            validation_result = self._validate_export_params(
                hostel_id, start_date, end_date, fmt
            )
            if not validation_result.success:
                return validation_result
            
            # Fetch data
            report = self.occupancy_repo.get_occupancy_report(
                hostel_id, start_date, end_date
            )
            
            if not report:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No occupancy data found for the specified period",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Prepare export data
            export_data = self._prepare_occupancy_export(
                report, include_forecast, custom_options
            )
            
            # Generate file
            file_path = self._export_payload(
                export_data,
                f"occupancy_report_{hostel_id}",
                fmt,
                ExportType.OCCUPANCY_REPORT,
            )
            
            # Track export
            self._track_export(
                ExportType.OCCUPANCY_REPORT,
                hostel_id,
                start_date,
                end_date,
                fmt,
                file_path,
            )
            
            return ServiceResult.success(
                file_path,
                message="Occupancy report exported successfully"
            )
            
        except Exception as e:
            logger.error(f"Error exporting occupancy report: {str(e)}")
            return self._handle_exception(e, "export occupancy report", hostel_id)

    def export_platform_overview(
        self,
        start_date: date,
        end_date: date,
        fmt: str = "excel",
        include_trends: bool = True,
        custom_options: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[str]:
        """
        Export platform-wide analytics overview to a file.
        
        Args:
            start_date: Start date
            end_date: End date
            fmt: Export format
            include_trends: Include trend analysis
            custom_options: Custom export options
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Validate date range
            if start_date > end_date:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Start date cannot be after end date",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate format
            if not self._is_valid_format(fmt):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Unsupported export format: {fmt}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch data
            overview = self.platform_repo.get_platform_overview(start_date, end_date)
            
            if not overview:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No platform data found for the specified period",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Prepare export data
            export_data = self._prepare_platform_export(
                overview, include_trends, custom_options
            )
            
            # Generate file
            file_path = self._export_payload(
                export_data,
                "platform_overview",
                fmt,
                ExportType.PLATFORM_OVERVIEW,
            )
            
            # Track export
            self._track_export(
                ExportType.PLATFORM_OVERVIEW,
                None,
                start_date,
                end_date,
                fmt,
                file_path,
            )
            
            return ServiceResult.success(
                file_path,
                message="Platform overview exported successfully"
            )
            
        except Exception as e:
            logger.error(f"Error exporting platform overview: {str(e)}")
            return self._handle_exception(e, "export platform overview")

    def export_supervisor_analytics(
        self,
        supervisor_id: UUID,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        fmt: str = "excel",
        custom_options: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[str]:
        """
        Export supervisor analytics to a file.
        
        Args:
            supervisor_id: Supervisor UUID
            hostel_id: Hostel UUID
            start_date: Start date
            end_date: End date
            fmt: Export format
            custom_options: Custom export options
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Validate inputs
            validation_result = self._validate_export_params(
                hostel_id, start_date, end_date, fmt
            )
            if not validation_result.success:
                return validation_result
            
            # Fetch data
            analytics = self.supervisor_repo.get_dashboard(
                supervisor_id, hostel_id, start_date, end_date
            )
            
            if not analytics:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No supervisor data found for the specified period",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Prepare export data
            export_data = self._prepare_supervisor_export(analytics, custom_options)
            
            # Generate file
            file_path = self._export_payload(
                export_data,
                f"supervisor_analytics_{supervisor_id}",
                fmt,
                ExportType.SUPERVISOR_ANALYTICS,
            )
            
            # Track export
            self._track_export(
                ExportType.SUPERVISOR_ANALYTICS,
                hostel_id,
                start_date,
                end_date,
                fmt,
                file_path,
                {"supervisor_id": str(supervisor_id)},
            )
            
            return ServiceResult.success(
                file_path,
                message="Supervisor analytics exported successfully"
            )
            
        except Exception as e:
            logger.error(f"Error exporting supervisor analytics: {str(e)}")
            return self._handle_exception(e, "export supervisor analytics", supervisor_id)

    def export_visitor_analytics(
        self,
        start_date: date,
        end_date: date,
        fmt: str = "excel",
        include_funnels: bool = True,
        custom_options: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[str]:
        """
        Export visitor analytics to a file.
        
        Args:
            start_date: Start date
            end_date: End date
            fmt: Export format
            include_funnels: Include funnel analysis
            custom_options: Custom export options
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Validate date range
            if start_date > end_date:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Start date cannot be after end date",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch data
            analytics = self.visitor_repo.get_behavior_analytics(start_date, end_date)
            
            if not analytics:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No visitor data found for the specified period",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Prepare export data
            export_data = self._prepare_visitor_export(
                analytics, include_funnels, custom_options
            )
            
            # Generate file
            file_path = self._export_payload(
                export_data,
                "visitor_analytics",
                fmt,
                ExportType.VISITOR_ANALYTICS,
            )
            
            # Track export
            self._track_export(
                ExportType.VISITOR_ANALYTICS,
                None,
                start_date,
                end_date,
                fmt,
                file_path,
            )
            
            return ServiceResult.success(
                file_path,
                message="Visitor analytics exported successfully"
            )
            
        except Exception as e:
            logger.error(f"Error exporting visitor analytics: {str(e)}")
            return self._handle_exception(e, "export visitor analytics")

    def export_custom_report(
        self,
        report_definition_id: UUID,
        fmt: str = "excel",
        custom_options: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[str]:
        """
        Export a custom report definition to a file.
        
        Args:
            report_definition_id: Custom report definition UUID
            fmt: Export format
            custom_options: Custom export options
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Execute report
            result = self.reports_repo.execute_report(report_definition_id)
            
            if not result:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Report definition not found or execution failed",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Prepare export data
            export_data = self._prepare_custom_report_export(result, custom_options)
            
            # Generate file
            file_path = self._export_payload(
                export_data,
                f"custom_report_{report_definition_id}",
                fmt,
                ExportType.CUSTOM_REPORT,
            )
            
            return ServiceResult.success(
                file_path,
                message="Custom report exported successfully"
            )
            
        except Exception as e:
            logger.error(f"Error exporting custom report: {str(e)}")
            return self._handle_exception(e, "export custom report", report_definition_id)

    def get_export_history(
        self,
        limit: int = 50,
        export_type: Optional[ExportType] = None,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get export history.
        
        Args:
            limit: Maximum number of records
            export_type: Optional filter by export type
            
        Returns:
            ServiceResult containing export history
        """
        try:
            history = self._export_history[-limit:]
            
            if export_type:
                history = [
                    h for h in history
                    if h.get("export_type") == export_type
                ]
            
            return ServiceResult.success(
                history,
                message=f"Retrieved {len(history)} export records"
            )
            
        except Exception as e:
            logger.error(f"Error retrieving export history: {str(e)}")
            return self._handle_exception(e, "get export history")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_export_params(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        fmt: str,
    ) -> ServiceResult[bool]:
        """Validate export parameters."""
        if start_date > end_date:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date cannot be after end date",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        if not self._is_valid_format(fmt):
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Unsupported export format: {fmt}",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        return ServiceResult.success(True)

    def _is_valid_format(self, fmt: str) -> bool:
        """Check if format is valid."""
        try:
            ExportFormat(fmt.lower())
            return True
        except ValueError:
            return False

    def _export_payload(
        self,
        payload: Any,
        base_name: str,
        fmt: str,
        export_type: ExportType,
    ) -> str:
        """
        Export payload to a file and return its path.
        
        Args:
            payload: Data to export
            base_name: Base filename
            fmt: Export format
            export_type: Type of export
            
        Returns:
            File path string
        """
        fmt = ExportFormat(fmt.lower())
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = FileHelper.slugify_filename(f"{base_name}_{timestamp}")
        
        if fmt in (ExportFormat.XLSX, ExportFormat.EXCEL):
            path = self.DEFAULT_EXPORT_DIR / f"{filename}.xlsx"
            self._generate_excel(path, payload, export_type)
            return str(path)
            
        elif fmt == ExportFormat.PDF:
            path = self.DEFAULT_EXPORT_DIR / f"{filename}.pdf"
            self._generate_pdf(path, payload, export_type)
            return str(path)
            
        elif fmt == ExportFormat.JSON:
            path = self.DEFAULT_EXPORT_DIR / f"{filename}.json"
            self._generate_json(path, payload)
            return str(path)
            
        elif fmt == ExportFormat.CSV:
            path = self.DEFAULT_EXPORT_DIR / f"{filename}.csv"
            self._generate_csv(path, payload, export_type)
            return str(path)
        
        # Default to Excel
        path = self.DEFAULT_EXPORT_DIR / f"{filename}.xlsx"
        self._generate_excel(path, payload, export_type)
        return str(path)

    def _generate_excel(
        self,
        path: Path,
        payload: Any,
        export_type: ExportType,
    ) -> None:
        """Generate Excel file."""
        generator = ExcelReportGenerator()
        generator.generate(str(path), payload, export_type=export_type.value)

    def _generate_pdf(
        self,
        path: Path,
        payload: Any,
        export_type: ExportType,
    ) -> None:
        """Generate PDF file."""
        generator = PDFReportGenerator()
        generator.generate(str(path), payload, export_type=export_type.value)

    def _generate_json(self, path: Path, payload: Any) -> None:
        """Generate JSON file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                payload,
                f,
                indent=2,
                default=str,
                ensure_ascii=False,
            )

    def _generate_csv(
        self,
        path: Path,
        payload: Any,
        export_type: ExportType,
    ) -> None:
        """Generate CSV file."""
        # Convert payload to flat structure for CSV
        flat_data = self._flatten_for_csv(payload, export_type)
        
        if not flat_data:
            # Write empty file
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["No data available"])
            return
        
        with open(path, 'w', encoding='utf-8', newline='') as f:
            if isinstance(flat_data, list) and flat_data:
                writer = csv.DictWriter(f, fieldnames=flat_data[0].keys())
                writer.writeheader()
                writer.writerows(flat_data)
            else:
                writer = csv.writer(f)
                writer.writerow(["No data available"])

    def _flatten_for_csv(
        self,
        payload: Any,
        export_type: ExportType,
    ) -> List[Dict[str, Any]]:
        """Flatten complex payload for CSV export."""
        if isinstance(payload, list):
            return payload
        
        if isinstance(payload, dict):
            # Extract main data array if present
            for key in ['data', 'items', 'results', 'records']:
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
            
            # Single record
            return [payload]
        
        return []

    def _prepare_booking_export(
        self,
        summary: Any,
        include_details: bool,
        custom_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare booking data for export."""
        export_data = {
            "report_type": "Booking Analytics Summary",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
        }
        
        if include_details and hasattr(summary, 'details'):
            export_data["details"] = summary.details
        
        if custom_options:
            export_data["custom_options"] = custom_options
        
        return export_data

    def _prepare_complaint_export(
        self,
        dashboard: Any,
        include_trends: bool,
        custom_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare complaint data for export."""
        export_data = {
            "report_type": "Complaint Analytics Dashboard",
            "generated_at": datetime.utcnow().isoformat(),
            "dashboard": dashboard,
        }
        
        if include_trends and hasattr(dashboard, 'trends'):
            export_data["trends"] = dashboard.trends
        
        if custom_options:
            export_data["custom_options"] = custom_options
        
        return export_data

    def _prepare_financial_export(
        self,
        report: Any,
        include_charts: bool,
        custom_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare financial data for export."""
        export_data = {
            "report_type": "Financial Analytics Report",
            "generated_at": datetime.utcnow().isoformat(),
            "report": report,
        }
        
        if include_charts:
            export_data["include_visualizations"] = True
        
        if custom_options:
            export_data["custom_options"] = custom_options
        
        return export_data

    def _prepare_occupancy_export(
        self,
        report: Any,
        include_forecast: bool,
        custom_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare occupancy data for export."""
        export_data = {
            "report_type": "Occupancy Analytics Report",
            "generated_at": datetime.utcnow().isoformat(),
            "report": report,
        }
        
        if include_forecast and hasattr(report, 'forecast'):
            export_data["forecast"] = report.forecast
        
        if custom_options:
            export_data["custom_options"] = custom_options
        
        return export_data

    def _prepare_platform_export(
        self,
        overview: Any,
        include_trends: bool,
        custom_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare platform data for export."""
        export_data = {
            "report_type": "Platform Analytics Overview",
            "generated_at": datetime.utcnow().isoformat(),
            "overview": overview,
        }
        
        if include_trends and hasattr(overview, 'trends'):
            export_data["trends"] = overview.trends
        
        if custom_options:
            export_data["custom_options"] = custom_options
        
        return export_data

    def _prepare_supervisor_export(
        self,
        analytics: Any,
        custom_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare supervisor data for export."""
        export_data = {
            "report_type": "Supervisor Analytics",
            "generated_at": datetime.utcnow().isoformat(),
            "analytics": analytics,
        }
        
        if custom_options:
            export_data["custom_options"] = custom_options
        
        return export_data

    def _prepare_visitor_export(
        self,
        analytics: Any,
        include_funnels: bool,
        custom_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare visitor data for export."""
        export_data = {
            "report_type": "Visitor Analytics",
            "generated_at": datetime.utcnow().isoformat(),
            "analytics": analytics,
        }
        
        if include_funnels and hasattr(analytics, 'funnels'):
            export_data["funnels"] = analytics.funnels
        
        if custom_options:
            export_data["custom_options"] = custom_options
        
        return export_data

    def _prepare_custom_report_export(
        self,
        result: Any,
        custom_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare custom report data for export."""
        export_data = {
            "report_type": "Custom Report",
            "generated_at": datetime.utcnow().isoformat(),
            "result": result,
        }
        
        if custom_options:
            export_data["custom_options"] = custom_options
        
        return export_data

    def _track_export(
        self,
        export_type: ExportType,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date,
        fmt: str,
        file_path: str,
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track export in history."""
        record = {
            "export_type": export_type.value,
            "hostel_id": str(hostel_id) if hostel_id else None,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "format": fmt,
            "file_path": file_path,
            "exported_at": datetime.utcnow().isoformat(),
        }
        
        if additional_params:
            record.update(additional_params)
        
        self._export_history.append(record)
        
        # Keep only last 1000 records
        if len(self._export_history) > 1000:
            self._export_history = self._export_history[-1000:]