"""
Complaint export and reporting service.

Handles data export, report generation, and document creation
for complaint management analytics and compliance.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
import csv
import io

from sqlalchemy.orm import Session

from app.models.base.enums import ComplaintCategory, ComplaintStatus, Priority
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_aggregate_repository import (
    ComplaintAggregateRepository,
)
from app.core.exceptions import ValidationError


class ExportFormat(str, Enum):
    """Export file formats."""
    CSV = "CSV"
    EXCEL = "EXCEL"
    PDF = "PDF"
    JSON = "JSON"


class ReportType(str, Enum):
    """Report types."""
    SUMMARY = "SUMMARY"
    DETAILED = "DETAILED"
    ANALYTICS = "ANALYTICS"
    PERFORMANCE = "PERFORMANCE"
    SLA_COMPLIANCE = "SLA_COMPLIANCE"
    FEEDBACK_ANALYSIS = "FEEDBACK_ANALYSIS"


class ComplaintExportService:
    """
    Complaint export and reporting service.
    
    Provides data export, report generation, and document creation
    capabilities for complaint management.
    """

    def __init__(self, session: Session):
        """
        Initialize export service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)
        self.aggregate_repo = ComplaintAggregateRepository(session)

    # ==================== Data Export ====================

    def export_complaints(
        self,
        format: ExportFormat,
        hostel_id: Optional[str] = None,
        status: Optional[List[ComplaintStatus]] = None,
        category: Optional[List[ComplaintCategory]] = None,
        priority: Optional[List[Priority]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        include_comments: bool = False,
        include_attachments: bool = False,
    ) -> Dict[str, Any]:
        """
        Export complaints data in specified format.
        
        Args:
            format: Export format
            hostel_id: Optional hostel filter
            status: Filter by status list
            category: Filter by category list
            priority: Filter by priority list
            date_from: Start date filter
            date_to: End date filter
            include_comments: Include comments in export
            include_attachments: Include attachment URLs
            
        Returns:
            Export result with file data
        """
        # Get complaints
        complaints, total = self.complaint_repo.search_complaints(
            hostel_id=hostel_id,
            status=status,
            category=category,
            priority=priority,
            date_from=date_from,
            date_to=date_to,
            limit=10000,  # Max export limit
        )
        
        if not complaints:
            raise ValidationError("No complaints found for export")
        
        # Generate export based on format
        if format == ExportFormat.CSV:
            return self._export_to_csv(complaints, include_comments, include_attachments)
        elif format == ExportFormat.JSON:
            return self._export_to_json(complaints, include_comments, include_attachments)
        elif format == ExportFormat.EXCEL:
            return self._export_to_excel(complaints, include_comments, include_attachments)
        elif format == ExportFormat.PDF:
            return self._export_to_pdf(complaints, include_comments, include_attachments)
        else:
            raise ValidationError(f"Unsupported export format: {format}")

    def _export_to_csv(
        self,
        complaints: List,
        include_comments: bool,
        include_attachments: bool,
    ) -> Dict[str, Any]:
        """Export complaints to CSV format."""
        output = io.StringIO()
        
        # Define CSV headers
        headers = [
            "Complaint Number",
            "Title",
            "Category",
            "Priority",
            "Status",
            "Opened At",
            "Resolved At",
            "SLA Due At",
            "SLA Breach",
            "Assigned To",
            "Escalated",
            "Rating",
        ]
        
        if include_attachments:
            headers.append("Attachments")
        
        if include_comments:
            headers.append("Comments Count")
        
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        # Write data
        for complaint in complaints:
            row = {
                "Complaint Number": complaint.complaint_number,
                "Title": complaint.title,
                "Category": complaint.category.value,
                "Priority": complaint.priority.value,
                "Status": complaint.status.value,
                "Opened At": complaint.opened_at.isoformat(),
                "Resolved At": complaint.resolved_at.isoformat() if complaint.resolved_at else "",
                "SLA Due At": complaint.sla_due_at.isoformat() if complaint.sla_due_at else "",
                "SLA Breach": "Yes" if complaint.sla_breach else "No",
                "Assigned To": complaint.assigned_to or "",
                "Escalated": "Yes" if complaint.escalated else "No",
                "Rating": complaint.student_rating or "",
            }
            
            if include_attachments:
                row["Attachments"] = ", ".join(complaint.attachments) if complaint.attachments else ""
            
            if include_comments:
                row["Comments Count"] = complaint.total_comments
            
            writer.writerow(row)
        
        csv_data = output.getvalue()
        output.close()
        
        return {
            "success": True,
            "format": "CSV",
            "filename": f"complaints_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "data": csv_data,
            "size": len(csv_data),
            "count": len(complaints),
        }

    def _export_to_json(
        self,
        complaints: List,
        include_comments: bool,
        include_attachments: bool,
    ) -> Dict[str, Any]:
        """Export complaints to JSON format."""
        import json
        
        data = []
        
        for complaint in complaints:
            complaint_data = {
                "id": complaint.id,
                "complaint_number": complaint.complaint_number,
                "title": complaint.title,
                "description": complaint.description,
                "category": complaint.category.value,
                "priority": complaint.priority.value,
                "status": complaint.status.value,
                "opened_at": complaint.opened_at.isoformat(),
                "resolved_at": complaint.resolved_at.isoformat() if complaint.resolved_at else None,
                "closed_at": complaint.closed_at.isoformat() if complaint.closed_at else None,
                "sla_due_at": complaint.sla_due_at.isoformat() if complaint.sla_due_at else None,
                "sla_breach": complaint.sla_breach,
                "assigned_to": complaint.assigned_to,
                "escalated": complaint.escalated,
                "rating": complaint.student_rating,
                "feedback": complaint.student_feedback,
            }
            
            if include_attachments:
                complaint_data["attachments"] = complaint.attachments
            
            if include_comments:
                complaint_data["comments_count"] = complaint.total_comments
                complaint_data["internal_notes_count"] = complaint.internal_notes_count
            
            data.append(complaint_data)
        
        json_data = json.dumps(data, indent=2)
        
        return {
            "success": True,
            "format": "JSON",
            "filename": f"complaints_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "data": json_data,
            "size": len(json_data),
            "count": len(complaints),
        }

    def _export_to_excel(
        self,
        complaints: List,
        include_comments: bool,
        include_attachments: bool,
    ) -> Dict[str, Any]:
        """Export complaints to Excel format (placeholder)."""
        # Would use openpyxl or xlsxwriter library
        return {
            "success": True,
            "format": "EXCEL",
            "message": "Excel export not implemented - use CSV for now",
            "count": len(complaints),
        }

    def _export_to_pdf(
        self,
        complaints: List,
        include_comments: bool,
        include_attachments: bool,
    ) -> Dict[str, Any]:
        """Export complaints to PDF format (placeholder)."""
        # Would use reportlab or weasyprint library
        return {
            "success": True,
            "format": "PDF",
            "message": "PDF export not implemented",
            "count": len(complaints),
        }

    # ==================== Report Generation ====================

    def generate_report(
        self,
        report_type: ReportType,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        format: ExportFormat = ExportFormat.JSON,
    ) -> Dict[str, Any]:
        """
        Generate predefined report.
        
        Args:
            report_type: Type of report
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            format: Output format
            
        Returns:
            Generated report
        """
        if report_type == ReportType.SUMMARY:
            return self._generate_summary_report(hostel_id, date_from, date_to)
        elif report_type == ReportType.ANALYTICS:
            return self._generate_analytics_report(hostel_id, date_from, date_to)
        elif report_type == ReportType.PERFORMANCE:
            return self._generate_performance_report(hostel_id, date_from, date_to)
        elif report_type == ReportType.SLA_COMPLIANCE:
            return self._generate_sla_report(hostel_id, date_from, date_to)
        elif report_type == ReportType.FEEDBACK_ANALYSIS:
            return self._generate_feedback_report(hostel_id, date_from, date_to)
        else:
            raise ValidationError(f"Unsupported report type: {report_type}")

    def _generate_summary_report(
        self,
        hostel_id: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> Dict[str, Any]:
        """Generate executive summary report."""
        summary = self.aggregate_repo.generate_executive_report(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        return {
            "report_type": "SUMMARY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
            "data": summary,
        }

    def _generate_analytics_report(
        self,
        hostel_id: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> Dict[str, Any]:
        """Generate analytics report."""
        from app.services.complaint import ComplaintAnalyticsService
        
        analytics_service = ComplaintAnalyticsService(self.session)
        
        # Get various analytics
        dashboard = analytics_service.get_dashboard_summary(hostel_id=hostel_id)
        trends = analytics_service.get_complaint_trends(hostel_id=hostel_id, days=30)
        category_trends = analytics_service.get_category_performance_trends(
            hostel_id=hostel_id,
            days=30,
        )
        
        return {
            "report_type": "ANALYTICS",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "dashboard": dashboard,
                "trends": trends,
                "category_performance": category_trends,
            },
        }

    def _generate_performance_report(
        self,
        hostel_id: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> Dict[str, Any]:
        """Generate performance report."""
        stats = self.complaint_repo.get_complaint_statistics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        avg_resolution_time = self.complaint_repo.get_average_resolution_time(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        top_categories = self.complaint_repo.get_top_categories(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
            limit=10,
        )
        
        return {
            "report_type": "PERFORMANCE",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
            "data": {
                "statistics": stats,
                "avg_resolution_time_hours": avg_resolution_time,
                "top_categories": top_categories,
            },
        }

    def _generate_sla_report(
        self,
        hostel_id: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> Dict[str, Any]:
        """Generate SLA compliance report."""
        from app.services.complaint import ComplaintSLAService
        
        sla_service = ComplaintSLAService(self.session)
        
        sla_summary = sla_service.get_sla_breach_summary(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        at_risk = sla_service.find_sla_at_risk(hostel_id=hostel_id, hours_threshold=4)
        
        return {
            "report_type": "SLA_COMPLIANCE",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
            "data": {
                "summary": sla_summary,
                "at_risk_count": len(at_risk),
                "at_risk_complaints": [
                    {
                        "complaint_number": c.complaint_number,
                        "title": c.title,
                        "sla_due_at": c.sla_due_at.isoformat() if c.sla_due_at else None,
                        "priority": c.priority.value,
                    }
                    for c in at_risk[:10]
                ],
            },
        }

    def _generate_feedback_report(
        self,
        hostel_id: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> Dict[str, Any]:
        """Generate feedback analysis report."""
        from app.services.complaint import ComplaintFeedbackService
        
        feedback_service = ComplaintFeedbackService(self.session)
        
        satisfaction_metrics = feedback_service.get_satisfaction_metrics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        detailed_ratings = feedback_service.get_detailed_ratings(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        trends = feedback_service.get_feedback_trends(hostel_id=hostel_id, days=30)
        
        return {
            "report_type": "FEEDBACK_ANALYSIS",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
            "data": {
                "satisfaction_metrics": satisfaction_metrics,
                "detailed_ratings": detailed_ratings,
                "trends": trends,
            },
        }

    # ==================== Scheduled Reports ====================

    def generate_daily_report(
        self,
        hostel_id: Optional[str] = None,
        recipients: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate and send daily report.
        
        Args:
            hostel_id: Optional hostel filter
            recipients: List of recipient user IDs
            
        Returns:
            Report generation result
        """
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        date_from = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
        date_to = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        report = self.generate_report(
            report_type=ReportType.SUMMARY,
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        # Send to recipients (placeholder)
        if recipients:
            from app.services.complaint import ComplaintNotificationService
            notification_service = ComplaintNotificationService(self.session)
            
            for recipient in recipients:
                # Would send report via email/notification
                pass
        
        return {
            "success": True,
            "report_type": "DAILY",
            "date": yesterday.isoformat(),
            "recipients_count": len(recipients) if recipients else 0,
            "report": report,
        }

    def generate_weekly_report(
        self,
        hostel_id: Optional[str] = None,
        recipients: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate and send weekly report.
        
        Args:
            hostel_id: Optional hostel filter
            recipients: List of recipient user IDs
            
        Returns:
            Report generation result
        """
        today = datetime.now(timezone.utc).date()
        week_start = today - timedelta(days=today.weekday() + 7)
        week_end = week_start + timedelta(days=6)
        
        date_from = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
        date_to = datetime.combine(week_end, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        report = self.generate_report(
            report_type=ReportType.ANALYTICS,
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        return {
            "success": True,
            "report_type": "WEEKLY",
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "recipients_count": len(recipients) if recipients else 0,
            "report": report,
        }

    def generate_monthly_report(
        self,
        hostel_id: Optional[str] = None,
        recipients: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate and send monthly report.
        
        Args:
            hostel_id: Optional hostel filter
            recipients: List of recipient user IDs
            
        Returns:
            Report generation result
        """
        from calendar import monthrange
        
        today = datetime.now(timezone.utc).date()
        # Previous month
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1
        
        month_start = datetime(year, month, 1).replace(tzinfo=timezone.utc)
        last_day = monthrange(year, month)[1]
        month_end = datetime(year, month, last_day, 23, 59, 59).replace(tzinfo=timezone.utc)
        
        report = self.generate_report(
            report_type=ReportType.PERFORMANCE,
            hostel_id=hostel_id,
            date_from=month_start,
            date_to=month_end,
        )
        
        return {
            "success": True,
            "report_type": "MONTHLY",
            "month": f"{year}-{month:02d}",
            "recipients_count": len(recipients) if recipients else 0,
            "report": report,
        }