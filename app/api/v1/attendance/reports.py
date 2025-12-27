from typing import Any, List, Optional, Dict
import logging
from datetime import datetime
from functools import wraps

from fastapi import APIRouter, Depends, Query, status, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api import deps
from app.core.exceptions import ValidationError, NotFoundError, PermissionError
from app.core.logging import get_logger
from app.core.cache import cache_response
from app.schemas.attendance import (
    AttendanceReport,
    MonthlyReport,
    StudentMonthlySummary,
    AttendanceComparison,
    AttendanceExportRequest,
    TrendAnalysis,
    WeeklySummary,
    CustomReportConfig,
    ReportSchedule,
    DashboardData,
    ReportJobStatus
)
from app.services.attendance.attendance_report_service import AttendanceReportService

# Configuration Constants
class ReportConfig:
    HOSTEL_CACHE_TTL = 1800  # 30 minutes
    MONTHLY_CACHE_TTL = 3600  # 1 hour
    WEEKLY_CACHE_TTL = 900   # 15 minutes
    TREND_CACHE_TTL = 1800   # 30 minutes
    
    LARGE_EXPORT_THRESHOLD = 10000
    MAX_COMPARISON_ENTITIES = 20
    MIN_COMPARISON_ENTITIES = 2
    
    DATE_REGEX = r"^\d{4}-\d{2}-\d{2}$"
    GRANULARITY_REGEX = r"^(daily|weekly|monthly)$"
    TREND_TYPE_REGEX = r"^(daily|weekly|monthly|comprehensive)$"
    TIME_RANGE_REGEX = r"^(today|week|month|quarter)$"

# Request Models
class HostelReportQuery(BaseModel):
    hostel_id: str = Field(..., description="Unique hostel identifier")
    start_date: str = Field(..., regex=ReportConfig.DATE_REGEX, description="Report start date (YYYY-MM-DD)")
    end_date: str = Field(..., regex=ReportConfig.DATE_REGEX, description="Report end date (YYYY-MM-DD)")
    include_analytics: bool = Field(True, description="Include advanced analytics and trends")
    include_comparisons: bool = Field(False, description="Include peer hostel comparisons")
    granularity: str = Field("daily", regex=ReportConfig.GRANULARITY_REGEX, description="Report granularity")

class MonthlyReportQuery(BaseModel):
    hostel_id: str = Field(..., description="Hostel identifier")
    year: int = Field(..., ge=2000, le=2030, description="Report year")
    month: int = Field(..., ge=1, le=12, description="Report month")
    include_student_details: bool = Field(True, description="Include individual student summaries")
    include_policy_analysis: bool = Field(True, description="Include policy compliance analysis")
    include_recommendations: bool = Field(False, description="Include improvement recommendations")

class StudentReportQuery(BaseModel):
    student_id: str = Field(..., description="Unique student identifier")
    year: int = Field(..., ge=2000, le=2030, description="Report year")
    month: int = Field(..., ge=1, le=12, description="Report month")
    include_comparisons: bool = Field(True, description="Include peer and hostel average comparisons")
    include_predictions: bool = Field(False, description="Include performance predictions and trends")
    include_interventions: bool = Field(True, description="Include intervention recommendations")

class WeeklySummaryQuery(BaseModel):
    hostel_id: str = Field(..., description="Hostel identifier")
    week_start: str = Field(..., regex=ReportConfig.DATE_REGEX, description="Week start date (YYYY-MM-DD, should be Monday)")
    include_daily_breakdown: bool = Field(True, description="Include day-by-day detailed breakdown")
    include_trends: bool = Field(True, description="Include week-over-week trend analysis")

class TrendAnalysisQuery(BaseModel):
    hostel_id: str = Field(..., description="Hostel identifier")
    start_date: str = Field(..., regex=ReportConfig.DATE_REGEX, description="Analysis start date (YYYY-MM-DD)")
    end_date: str = Field(..., regex=ReportConfig.DATE_REGEX, description="Analysis end date (YYYY-MM-DD)")
    trend_type: str = Field("comprehensive", regex=ReportConfig.TREND_TYPE_REGEX, description="Type of trend analysis")
    include_predictions: bool = Field(True, description="Include predictive modeling and forecasting")
    include_seasonal: bool = Field(True, description="Include seasonal pattern analysis")

class DashboardQuery(BaseModel):
    hostel_id: Optional[str] = Field(None, description="Specific hostel filter")
    time_range: str = Field("today", regex=ReportConfig.TIME_RANGE_REGEX, description="Time range for analytics")

# Setup
logger = get_logger(__name__)
router = APIRouter(prefix="/attendance/reports", tags=["attendance:reports"])

def get_report_service(db: Session = Depends(deps.get_db)) -> AttendanceReportService:
    """
    Dependency to provide AttendanceReportService instance.
    
    Args:
        db: Database session with optimized connection pooling
        
    Returns:
        AttendanceReportService instance with performance optimizations
    """
    return AttendanceReportService(db=db)

# Error Handling Decorator
def handle_attendance_errors(func):
    """Decorator to handle common attendance reporting errors consistently."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NotFoundError as e:
            logger.warning(f"Resource not found in {func.__name__}: {e}")
            raise HTTPException(status_code=404, detail=str(e))
        except ValidationError as e:
            logger.warning(f"Validation error in {func.__name__}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except PermissionError as e:
            logger.warning(f"Permission denied in {func.__name__}: {e}")
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    return wrapper

# Endpoints

@router.get(
    "/hostel",
    response_model=AttendanceReport,
    summary="Generate comprehensive hostel attendance report",
    description="Create detailed attendance analytics report for a specific hostel "
                "with customizable metrics, visualizations, and export capabilities.",
    responses={
        200: {"description": "Report generated successfully"},
        400: {"description": "Invalid report parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    }
)
@cache_response(ttl=ReportConfig.HOSTEL_CACHE_TTL)
@handle_attendance_errors
async def generate_hostel_report(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    start_date: str = Query(..., description="Report start date (YYYY-MM-DD)", regex=ReportConfig.DATE_REGEX),
    end_date: str = Query(..., description="Report end date (YYYY-MM-DD)", regex=ReportConfig.DATE_REGEX),
    include_analytics: bool = Query(True, description="Include advanced analytics and trends"),
    include_comparisons: bool = Query(False, description="Include peer hostel comparisons"),
    granularity: str = Query("daily", description="Report granularity", regex=ReportConfig.GRANULARITY_REGEX),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Generate comprehensive attendance report for hostel administration.

    **Report Features:**
    - Detailed attendance statistics and percentages
    - Student-level breakdowns and summaries
    - Room and floor-based analytics
    - Time-based pattern analysis
    - Policy compliance tracking

    **Advanced Analytics:**
    - Trend identification and forecasting
    - Seasonal pattern recognition
    - Anomaly detection and alerts
    - Performance benchmarking

    **Access:** Admin users only
    """
    logger.info(f"Admin {_admin.id} generating hostel report for {hostel_id} from {start_date} to {end_date}")
    
    result = service.generate_hostel_report(
        hostel_id=hostel_id,
        start_date_str=start_date,
        end_date_str=end_date,
        include_analytics=include_analytics,
        include_comparisons=include_comparisons,
        granularity=granularity,
        actor_id=_admin.id,
    )
    
    logger.info(f"Hostel report generated successfully for {hostel_id}")
    return result

@router.get(
    "/monthly",
    response_model=MonthlyReport,
    summary="Generate detailed monthly attendance report",
    description="Create comprehensive monthly attendance summary with statistical "
                "analysis, compliance tracking, and actionable insights.",
    responses={
        200: {"description": "Monthly report generated successfully"},
        400: {"description": "Invalid month/year parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    }
)
@cache_response(ttl=ReportConfig.MONTHLY_CACHE_TTL)
@handle_attendance_errors
async def generate_monthly_report(
    hostel_id: str = Query(..., description="Hostel identifier"),
    year: int = Query(..., ge=2000, le=2030, description="Report year"),
    month: int = Query(..., ge=1, le=12, description="Report month"),
    include_student_details: bool = Query(True, description="Include individual student summaries"),
    include_policy_analysis: bool = Query(True, description="Include policy compliance analysis"),
    include_recommendations: bool = Query(False, description="Include improvement recommendations"),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Generate comprehensive monthly attendance report with deep analytics.

    **Monthly Analytics:**
    - Daily attendance averages and patterns
    - Weekly trend analysis and variations
    - Student performance rankings and insights
    - Room and floor comparative analysis
    - Policy violation tracking and trends

    **Access:** Admin users only
    """
    logger.info(f"Admin {_admin.id} generating monthly report for {hostel_id} for {year}-{month:02d}")
    
    result = service.generate_monthly_report(
        hostel_id=hostel_id,
        year=year,
        month=month,
        include_student_details=include_student_details,
        include_policy_analysis=include_policy_analysis,
        include_recommendations=include_recommendations,
        actor_id=_admin.id,
    )
    
    logger.info(f"Monthly report generated successfully for {hostel_id}")
    return result

@router.get(
    "/students/{student_id}",
    response_model=StudentMonthlySummary,
    summary="Generate individual student attendance report",
    description="Create detailed attendance report for a specific student with "
                "performance analytics, pattern recognition, and intervention insights.",
    responses={
        200: {"description": "Student report generated successfully"},
        404: {"description": "Student not found"},
        403: {"description": "Insufficient permissions"},
    }
)
@handle_attendance_errors
async def generate_student_report(
    student_id: str,
    year: int = Query(..., ge=2000, le=2030, description="Report year"),
    month: int = Query(..., ge=1, le=12, description="Report month"),
    include_comparisons: bool = Query(True, description="Include peer and hostel average comparisons"),
    include_predictions: bool = Query(False, description="Include performance predictions and trends"),
    include_interventions: bool = Query(True, description="Include intervention recommendations"),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Generate comprehensive individual student attendance analysis.

    **Student Analytics:**
    - Personal attendance percentage and ranking
    - Daily attendance pattern analysis
    - Absence and lateness trend identification
    - Policy compliance and violation tracking

    **Access:** Admin and Supervisor users
    """
    logger.info(f"Admin {_admin.id} generating student report for {student_id} for {year}-{month:02d}")
    
    result = service.generate_student_report(
        student_id=student_id,
        year=year,
        month=month,
        include_comparisons=include_comparisons,
        include_predictions=include_predictions,
        include_interventions=include_interventions,
        actor_id=_admin.id,
    )
    
    logger.info(f"Student report generated successfully for {student_id}")
    return result

@router.post(
    "/compare",
    response_model=AttendanceComparison,
    summary="Generate comparative attendance analysis",
    description="Compare attendance metrics across multiple entities with statistical "
                "analysis, ranking, and performance insights.",
    responses={
        200: {"description": "Comparison analysis completed successfully"},
        202: {"description": "Large comparison queued for background processing"},
        400: {"description": "Invalid comparison parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
@handle_attendance_errors
async def compare_attendance(
    payload: AttendanceComparison,
    background_tasks: BackgroundTasks,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Generate sophisticated comparative attendance analysis across entities.

    **Comparison Types:**
    - Multi-hostel performance benchmarking
    - Student cohort comparative analysis
    - Room and floor performance rankings
    - Time period comparative studies

    **Access:** Admin users only
    """
    logger.info(f"Admin {_admin.id} generating comparison analysis for {len(payload.entities)} entities")
    
    # Validate comparison entities
    if len(payload.entities) < ReportConfig.MIN_COMPARISON_ENTITIES:
        raise ValidationError(f"At least {ReportConfig.MIN_COMPARISON_ENTITIES} entities required for comparison")
    
    if len(payload.entities) > ReportConfig.MAX_COMPARISON_ENTITIES:
        # Process large comparisons in background
        job_id = service.queue_background_comparison(payload, _admin.id)
        background_tasks.add_task(service.process_large_comparison, job_id, _admin.id)
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "processing", 
                "job_id": job_id,
                "message": "Large comparison queued for background processing"
            }
        )
    
    result = service.compare_attendance(payload=payload, actor_id=_admin.id)
    logger.info(f"Comparison analysis completed successfully")
    return result

@router.get(
    "/weekly-summary",
    response_model=WeeklySummary,
    summary="Generate weekly attendance summary with trends",
    description="Create focused weekly attendance summary with day-by-day analysis "
                "and week-over-week trend comparisons.",
    responses={
        200: {"description": "Weekly summary generated successfully"},
        400: {"description": "Invalid week parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=ReportConfig.WEEKLY_CACHE_TTL)
@handle_attendance_errors
async def get_weekly_summary(
    hostel_id: str = Query(..., description="Hostel identifier"),
    week_start: str = Query(..., description="Week start date (YYYY-MM-DD, should be Monday)", regex=ReportConfig.DATE_REGEX),
    include_daily_breakdown: bool = Query(True, description="Include day-by-day detailed breakdown"),
    include_trends: bool = Query(True, description="Include week-over-week trend analysis"),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Generate focused weekly attendance summary with comprehensive day-level analysis.

    **Weekly Analysis:**
    - Day-by-day attendance percentages
    - Weekly attendance average and median
    - Workday vs weekend pattern analysis
    - Daily peak and low attendance identification

    **Access:** Admin users only
    """
    logger.info(f"Admin {_admin.id} generating weekly summary for {hostel_id} week starting {week_start}")
    
    result = service.get_weekly_summary(
        hostel_id=hostel_id,
        week_start_str=week_start,
        include_daily_breakdown=include_daily_breakdown,
        include_trends=include_trends,
        actor_id=_admin.id,
    )
    
    logger.info(f"Weekly summary generated successfully")
    return result

@router.get(
    "/trend",
    response_model=TrendAnalysis,
    summary="Generate advanced attendance trend analysis",
    description="Perform sophisticated trend analysis with predictive modeling, "
                "seasonal adjustments, and statistical forecasting.",
    responses={
        200: {"description": "Trend analysis completed successfully"},
        400: {"description": "Invalid trend analysis parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=ReportConfig.TREND_CACHE_TTL)
@handle_attendance_errors
async def get_trend_analysis(
    hostel_id: str = Query(..., description="Hostel identifier"),
    start_date: str = Query(..., description="Analysis start date (YYYY-MM-DD)", regex=ReportConfig.DATE_REGEX),
    end_date: str = Query(..., description="Analysis end date (YYYY-MM-DD)", regex=ReportConfig.DATE_REGEX),
    trend_type: str = Query("comprehensive", description="Type of trend analysis", regex=ReportConfig.TREND_TYPE_REGEX),
    include_predictions: bool = Query(True, description="Include predictive modeling and forecasting"),
    include_seasonal: bool = Query(True, description="Include seasonal pattern analysis"),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Generate advanced attendance trend analysis with predictive capabilities.

    **Trend Analysis Features:**
    - Linear and polynomial trend fitting
    - Moving average calculations (7-day, 30-day)
    - Seasonal decomposition and analysis
    - Cyclical pattern identification
    - Anomaly detection and explanation

    **Access:** Admin users only
    """
    logger.info(f"Admin {_admin.id} generating trend analysis for {hostel_id} from {start_date} to {end_date}")
    
    result = service.get_trend_analysis(
        hostel_id=hostel_id,
        start_date_str=start_date,
        end_date_str=end_date,
        trend_type=trend_type,
        include_predictions=include_predictions,
        include_seasonal=include_seasonal,
        actor_id=_admin.id,
    )
    
    logger.info(f"Trend analysis completed successfully")
    return result

@router.post(
    "/export",
    summary="Export attendance data in multiple formats",
    description="Export comprehensive attendance data with customizable formatting, "
                "filtering, and delivery options for external analysis and reporting.",
    responses={
        200: {"description": "Export completed successfully"},
        202: {"description": "Export queued for background processing"},
        400: {"description": "Invalid export parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
@handle_attendance_errors
async def export_attendance_report(
    payload: AttendanceExportRequest,
    background_tasks: BackgroundTasks,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Export attendance data with comprehensive formatting and delivery options.

    **Export Formats:**
    - CSV for spreadsheet analysis
    - Excel with multiple sheets and formatting
    - PDF reports with charts and visualizations
    - JSON for API integration

    **Access:** Admin users only
    """
    logger.info(f"Admin {_admin.id} initiating export: format={payload.format}")
    
    # Estimate export size and processing time
    export_estimate = service.estimate_export_size(payload)
    
    if export_estimate.estimated_records > ReportConfig.LARGE_EXPORT_THRESHOLD:
        # Queue large exports for background processing
        job_id = service.queue_background_export(payload, _admin.id)
        background_tasks.add_task(service.process_background_export, job_id, _admin.id)
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "queued",
                "job_id": job_id,
                "estimated_completion": export_estimate.estimated_completion_time,
                "estimated_records": export_estimate.estimated_records
            }
        )
    else:
        # Process small exports immediately
        result = service.export_report(payload=payload, actor_id=_admin.id)
        logger.info(f"Export completed successfully")
        return result

@router.post(
    "/custom",
    summary="Generate custom report with advanced configuration",
    description="Create custom attendance report with user-defined metrics, "
                "visualizations, and analytical components.",
    responses={
        200: {"description": "Custom report generated successfully"},
        400: {"description": "Invalid report configuration"},
        403: {"description": "Insufficient permissions"},
    }
)
@handle_attendance_errors
async def generate_custom_report(
    config: CustomReportConfig,
    background_tasks: BackgroundTasks,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Generate highly customizable attendance report based on user specifications.

    **Custom Configuration:**
    - User-defined metrics and KPIs
    - Custom date ranges and groupings
    - Flexible filtering and sorting
    - Personalized visualization options

    **Access:** Admin users only
    """
    logger.info(f"Admin {_admin.id} generating custom report")
    
    result = service.generate_custom_report(config=config, actor_id=_admin.id)
    
    # Save configuration for future use if requested
    if getattr(config, 'save_template', False):
        background_tasks.add_task(service.save_report_template, config, _admin.id)
    
    logger.info(f"Custom report generated successfully")
    return result

@router.get(
    "/schedule",
    response_model=List[ReportSchedule],
    summary="Get scheduled report configurations",
    description="Retrieve list of scheduled automated reports with their configurations and status",
    responses={
        200: {"description": "Scheduled reports retrieved successfully"},
        403: {"description": "Insufficient permissions"},
    }
)
@handle_attendance_errors
async def get_scheduled_reports(
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> List[ReportSchedule]:
    """
    Get list of scheduled automated attendance reports.

    **Schedule Information:**
    - Report configuration and parameters
    - Execution frequency and timing
    - Last execution status and results
    - Next scheduled execution time

    **Access:** Admin users only
    """
    result = service.get_scheduled_reports(actor_id=_admin.id)
    return result

@router.post(
    "/schedule",
    response_model=ReportSchedule,
    status_code=status.HTTP_201_CREATED,
    summary="Create scheduled report automation",
    description="Set up automated report generation with customizable scheduling and delivery",
    responses={
        201: {"description": "Report schedule created successfully"},
        400: {"description": "Invalid schedule configuration"},
        403: {"description": "Insufficient permissions"},
    }
)
@handle_attendance_errors
async def create_report_schedule(
    schedule: ReportSchedule,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> ReportSchedule:
    """
    Create automated report schedule with customizable parameters.

    **Scheduling Options:**
    - Daily, weekly, monthly, and quarterly frequencies
    - Custom cron-like scheduling expressions
    - Business day and holiday awareness
    - Time zone specification and handling

    **Access:** Admin users only
    """
    logger.info(f"Admin {_admin.id} creating report schedule")
    
    result = service.create_report_schedule(schedule=schedule, actor_id=_admin.id)
    
    logger.info(f"Report schedule {result.id} created successfully")
    return result

@router.put(
    "/schedule/{schedule_id}",
    response_model=ReportSchedule,
    summary="Update scheduled report configuration",
    description="Modify existing automated report schedule settings",
    responses={
        200: {"description": "Report schedule updated successfully"},
        400: {"description": "Invalid schedule configuration"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Schedule not found"},
    }
)
@handle_attendance_errors
async def update_report_schedule(
    schedule_id: str,
    schedule: ReportSchedule,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> ReportSchedule:
    """Update existing report schedule configuration."""
    logger.info(f"Admin {_admin.id} updating report schedule {schedule_id}")
    
    result = service.update_report_schedule(
        schedule_id=schedule_id,
        schedule=schedule,
        actor_id=_admin.id
    )
    
    logger.info(f"Report schedule {schedule_id} updated successfully")
    return result

@router.delete(
    "/schedule/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete scheduled report",
    description="Remove automated report schedule",
    responses={
        204: {"description": "Report schedule deleted successfully"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Schedule not found"},
    }
)
@handle_attendance_errors
async def delete_report_schedule(
    schedule_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> None:
    """Delete automated report schedule."""
    logger.info(f"Admin {_admin.id} deleting report schedule {schedule_id}")
    
    service.delete_report_schedule(schedule_id=schedule_id, actor_id=_admin.id)
    
    logger.info(f"Report schedule {schedule_id} deleted successfully")

@router.get(
    "/analytics/dashboard-data",
    response_model=DashboardData,
    summary="Get real-time dashboard analytics data",
    description="Retrieve optimized data for real-time attendance analytics dashboards",
    responses={
        200: {"description": "Dashboard data retrieved successfully"},
        403: {"description": "Insufficient permissions"},
    }
)
@handle_attendance_errors
async def get_dashboard_analytics(
    hostel_id: Optional[str] = Query(None, description="Specific hostel filter"),
    time_range: str = Query("today", description="Time range for analytics", regex=ReportConfig.TIME_RANGE_REGEX),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> DashboardData:
    """
    Get optimized real-time data for attendance analytics dashboards.

    **Dashboard Metrics:**
    - Real-time attendance counts and percentages
    - Live check-in/out status updates
    - Current alert and violation statuses
    - Performance trend indicators

    **Access:** Admin users only
    """
    result = service.get_dashboard_data(
        hostel_id=hostel_id,
        time_range=time_range,
        actor_id=_admin.id
    )
    return result

@router.get(
    "/jobs/{job_id}/status",
    response_model=ReportJobStatus,
    summary="Get report job status",
    description="Check the status of a background report generation job",
    responses={
        200: {"description": "Job status retrieved successfully"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Job not found"},
    }
)
@handle_attendance_errors
async def get_job_status(
    job_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> ReportJobStatus:
    """Get status of background report generation job."""
    result = service.get_job_status(job_id=job_id, actor_id=_admin.id)
    return result

@router.get(
    "/jobs/{job_id}/download",
    summary="Download completed report",
    description="Download the result of a completed background report job",
    responses={
        200: {"description": "File downloaded successfully"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Job not found or not completed"},
    }
)
@handle_attendance_errors
async def download_job_result(
    job_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> FileResponse:
    """Download the result file from a completed background job."""
    file_path = service.get_job_result_file(job_id=job_id, actor_id=_admin.id)
    
    return FileResponse(
        path=file_path,
        filename=f"attendance_report_{job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel or delete report job",
    description="Cancel a running job or delete a completed job",
    responses={
        204: {"description": "Job cancelled/deleted successfully"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Job not found"},
    }
)
@handle_attendance_errors
async def cancel_job(
    job_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> None:
    """Cancel a running job or delete a completed job."""
    service.cancel_job(job_id=job_id, actor_id=_admin.id)